"""The Claude provider with a fake Anthropic client: requests, checks and the one retry, costs, prompts, regenerate.

FakeAnthropic replays scripted replies (JSON plus usage numbers) through the same `messages.stream()`
shape the SDK has, and records every request. No network, $0. The one live test writes a real
outline (a few cents) and is skipped without ANTHROPIC_API_KEY.
"""
import base64
import io
import json
import os
import shutil
import threading

import anthropic
import httpx2
import pytest
from dotenv import load_dotenv
from PIL import Image

from core import actions, db
from core.config import ROOT
from core.context import make_ctx
from core.engine import Engine
from providers import checks, make_providers, prompts
from providers.claude import ClaudeLLM
from providers.images import StubImages
from providers.llm import NoMeter, StubLLM
from replies import PLACES, outline_data, script_data

load_dotenv(ROOT / ".env")  # only the live test uses the key

USAGE = {"input": 2000, "cache_write": 1500, "cache_read": 0, "output": 3000}


# --- fake Anthropic client -----------------------------------------------------------------

class Block:
    def __init__(self, type_: str, text: str = "") -> None:
        self.type, self.text = type_, text


class Usage:
    def __init__(self, input, cache_write, cache_read, output) -> None:  # noqa: A002
        self.input_tokens, self.cache_creation_input_tokens = input, cache_write
        self.cache_read_input_tokens, self.output_tokens = cache_read, output


class Message:
    def __init__(self, text: str, usage: dict, stop: str) -> None:
        self.content = [Block("thinking"), Block("text", text)]
        self.usage = Usage(**usage)
        self.stop_reason, self.stop_details = stop, None


class Stream:
    def __init__(self, message: Message) -> None:
        self.message = message

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> bool:
        return False

    @property
    def text_stream(self):
        text = self.message.content[1].text
        for i in range(0, len(text), 7):  # small chunks, so keys get split across them
            yield text[i:i + 7]

    def get_final_message(self) -> Message:
        return self.message

    def close(self) -> None:
        pass


class Hang:
    """A reply that streams a little, then waits until Stop closes the stream (Claude mid-script)."""

    def __init__(self) -> None:
        self.started, self.closed = threading.Event(), threading.Event()


class HangingStream(Stream):
    def __init__(self, hang: Hang) -> None:
        super().__init__(Message("", USAGE, "end_turn"))
        self.hang = hang

    def close(self) -> None:
        self.hang.closed.set()

    @property
    def text_stream(self):
        yield '{"scenes": [{"beat": 1, "narration": "Day 1. The power'
        self.hang.started.set()
        if not self.hang.closed.wait(10):
            raise AssertionError("never stopped")
        raise httpx2.ReadError("the stream was closed")


class FakeAnthropic:
    """Each reply: a dict (sent back as JSON), an exception (raised), (dict, usage, stop_reason), or a ready Message.
    `client.messages.stream` and `client.beta.messages.stream` (server-side fallback) both land here. Picture
    checks (the schema with `seen`) are answered with `checks` and recorded in `checks_asked` instead, so the
    scripted replies and `requests` stay in stage order; `checks = None` makes them scripted like the rest."""

    def __init__(self, *replies) -> None:
        self.replies = list(replies)
        self.requests: list[dict] = []
        self.checks: dict | None = {"seen": "A placeholder frame.", "problems": []}
        self.checks_asked: list[dict] = []
        self.reviews_asked: list[dict] = []
        self.messages = self
        self.beta = self

    def stream(self, **request):
        properties = request["output_config"]["format"]["schema"]["properties"]
        if self.checks is not None and "seen" in properties:
            self.checks_asked.append({**request, "messages": list(request["messages"])})
            return Stream(Message(json.dumps(self.checks), USAGE, "end_turn"))
        if "verdict" in properties:  # the reviewer passes every draft unless a test scripts it (core/review.py)
            self.reviews_asked.append({**request, "messages": list(request["messages"])})
            return Stream(Message(json.dumps({"verdict": "fine", "problems": []}), USAGE, "end_turn"))
        self.requests.append({**request, "messages": list(request["messages"])})
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        if isinstance(reply, Message):
            return Stream(reply)
        if isinstance(reply, Hang):
            return HangingStream(reply)
        data, usage, stop = reply if isinstance(reply, tuple) else (reply, USAGE, "end_turn")
        return Stream(Message(json.dumps(data), usage, stop))


def api_error(cls, status: int):
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    return cls("nope", response=httpx2.Response(status, request=request), body=None)


# --- fixtures and helpers ----------------------------------------------------------------------

@pytest.fixture
def ctx(tmp_path):
    root = tmp_path / "project"  # a copy, so prompt edits never touch the real prompts/
    root.mkdir()
    shutil.copy(ROOT / "stickfleet.yaml", root)
    for name in ("channels", "prompts"):
        shutil.copytree(ROOT / name, root / name)
    return make_ctx(root=root, data_dir=tmp_path / "data",
                    overrides={"mode": "live", "providers": {"llm": "claude", "tts": "stub", "images": "stub",
                                                             "video": "stub"},
                               "stub": {"scenes": 6}, "engine": {"retry_backoff_s": 0},
                               "render": {"engine": "ffmpeg"}, "topics": {"competitors": "off"},
                               "models": {"critic": "off"}})  # scripted replies stay in stage order; the review path is tested with stubs


def use(ctx, *replies) -> FakeAnthropic:
    fake = FakeAnthropic(*replies)
    ctx.llm = ClaudeLLM(ctx.config, client=fake)
    return fake


def run(ctx) -> None:
    Engine(ctx).run_until_idle()


def video(ctx, vid):
    with ctx.connect() as conn:
        return db.get_video(conn, vid)


def costs(ctx, vid) -> list[dict]:
    with ctx.connect() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM costs WHERE video_id = ? ORDER BY id", (vid,))]


def cards(ctx, vid, kind) -> list[dict]:
    with ctx.connect() as conn:
        rows = conn.execute("""SELECT * FROM messages WHERE video_id = ? AND json_extract(card_json, '$.kind') = ?
                               ORDER BY id""", (vid, kind)).fetchall()
    return [{**dict(r), "card": json.loads(r["card_json"])} for r in rows]


def user_text(request: dict, i: int = 0) -> str:
    return request["messages"][i]["content"]


def outlined(ctx, fake_outline: dict | None = None):
    """A new video with an outline waiting for review. Returns (video id, fake)."""
    fake = use(ctx, fake_outline or outline_data())
    vid = actions.new_video(ctx, "zombie", "Day 1 to Day 365 in a flooded subway")
    run(ctx)
    assert video(ctx, vid)["state"] == "outlined"
    return vid, fake


# --- tests ---------------------------------------------------------------------------------------

def test_outline_request_cost_and_card(ctx):
    vid, fake = outlined(ctx)
    [req] = fake.requests
    channel = ctx.channel("zombie")

    assert req["model"] == "claude-opus-5-5" and req["max_tokens"] == 48000
    [system] = req["system"]
    assert system["cache_control"] == {"type": "ephemeral"}
    assert channel.scenario_family in system["text"] and "8 to 10 beats" in system["text"]
    assert "{" not in system["text"].replace("{\"", "")  # every placeholder filled
    assert req["output_config"]["effort"] == "high"
    assert req["output_config"]["format"]["type"] == "json_schema"
    assert "Day 1 to Day 365 in a flooded subway" in user_text(req) and "(none)" in user_text(req)
    assert "current outline" not in user_text(req)

    outline = json.loads(video(ctx, vid)["outline_json"])
    assert outline["topic"] == "Day 1 to Day 365 in a flooded subway" and len(outline["beats"]) == 9
    assert "If it is their own story" in user_text(req)
    [cost] = costs(ctx, vid)
    assert cost["provider"] == "llm" and cost["simulated"] == 0
    assert cost["usd"] == pytest.approx((2000 * 4 + 1500 * 5 + 3000 * 20) / 1e6)
    detail = json.loads(cost["detail"])
    assert detail["model"] == "claude-opus-5-5" and detail["output"] == 3000 and detail["stop"] == "end_turn"
    assert detail["estimate_usd"] > cost["usd"]  # the guard checks the most a call can cost
    [card] = cards(ctx, vid, "outline")
    assert card["card"]["version"] == 1 and card["card"]["beats"][0]["label"] == "Day 1"
    assert card["card"]["cast"][0]["name"] == "Rosa" and card["card"]["beats"][1]["cast"] == ["Rosa"]
    assert card["card"]["tracker"][0] == {"item": "Water", "unit": "L", "start": "20"}
    assert outline["backstory"].startswith("The river broke")


class Attempt:
    """One entry of usage.iterations when a server-side fallback ran."""

    def __init__(self, type_, model, input, cache_write, cache_read, output) -> None:  # noqa: A002
        self.type, self.model = type_, model
        self.input_tokens, self.cache_creation_input_tokens = input, cache_write
        self.cache_read_input_tokens, self.output_tokens = cache_read, output


def test_a_refusal_partway_is_finished_by_the_fallback_model(ctx):
    text = json.dumps(outline_data())
    cut = len(text) // 2
    message = Message(text, USAGE, "end_turn")
    message.content = [Block("thinking"), Block("text", text[:cut]), Block("fallback"), Block("text", text[cut:])]
    message.model = "claude-opus-4-8"
    message.usage.iterations = [Attempt("message", "claude-opus-5-5", 2000, 1500, 0, 3000),
                                Attempt("fallback_message", "claude-opus-4-8", 2500, 0, 0, 2000)]
    vid, fake = outlined(ctx, message)

    [req] = fake.requests
    assert req["fallbacks"] == "default" and req["betas"] == ["server-side-fallback-2026-07-01"]
    assert len(json.loads(video(ctx, vid)["outline_json"])["beats"]) == 9  # both halves joined into one reply
    [cost] = costs(ctx, vid)
    detail = json.loads(cost["detail"])
    # each attempt at its own model's rates; one with no listed price is costed at the requested model's
    assert cost["usd"] == pytest.approx(((2000 * 4 + 1500 * 5 + 3000 * 20) + (2500 * 4 + 2000 * 20)) / 1e6)
    assert detail["model"] == "claude-opus-4-8" and detail["output"] == 5000
    assert [a["model"] for a in detail["attempts"]] == ["claude-opus-5-5", "claude-opus-4-8"]
    assert detail["attempts"][1]["priced_as"] == "claude-opus-5-5"

    # a retry after failed checks sends the reply back without the thinking from before the fallback
    from providers.claude import _echo
    assert [b.type for b in _echo(message.content)] == ["text", "fallback", "text"]

    ctx.config.claude["fallbacks"] = None  # off: the plain endpoint, no fallback fields
    fake.replies.append(outline_data(hook="Again."))
    actions.regenerate(ctx, vid, "outline")
    run(ctx)
    assert "fallbacks" not in fake.requests[-1] and "betas" not in fake.requests[-1]


def stop_while_writing(ctx, vid, fake) -> None:
    """Run the script stage on a thread, wait for Claude to start streaming, press Stop."""
    from stages import script as script_stage
    hang = Hang()
    fake.replies.insert(0, hang)
    worker = threading.Thread(target=script_stage.run_once, args=(ctx,))
    worker.start()
    assert hang.started.wait(10)
    actions.stop_writing(ctx, vid)
    worker.join(10)
    assert not worker.is_alive()


def test_stop_takes_the_note_back_to_change_it(ctx):
    outline = outline_data()
    vid, fake = outlined(ctx, outline)
    fake.replies.append(script_data(outline))
    actions.approve(ctx, vid, "outline")
    run(ctx)
    assert video(ctx, vid)["state"] == "scripted"
    with pytest.raises(actions.ActionError, match="isn't writing anything"):
        actions.stop_writing(ctx, vid)

    actions.revise(ctx, vid, "script", "richer backgrounds")
    stop_while_writing(ctx, vid, fake)
    v = video(ctx, vid)
    assert v["state"] == "scripted" and v["draft_note"] == "richer backgrounds" and v["script_json"]
    with ctx.connect() as conn:
        assert db.notes(conn, vid, "script") == []  # taken back, so it won't go with the next revision
    card = cards(ctx, vid, "script")[-1]
    assert card["card_status"] == "active" and card["card"]["draft_note"] == "richer backgrounds"
    stopped = json.loads(costs(ctx, vid)[-1]["detail"])
    assert stopped["stop"] == "stopped" and stopped["approx"] is True and stopped["output"] > 0

    fake.replies.append(script_data(outline))  # the changed note is the one Claude gets
    actions.revise(ctx, vid, "script", "richer backgrounds, and Dan is a combat veteran")
    run(ctx)
    text = user_text(fake.requests[-1])
    assert "Dan is a combat veteran" in text and video(ctx, vid)["draft_note"] is None


def test_stopping_a_first_script_goes_back_to_the_outline(ctx):
    vid, fake = outlined(ctx)
    actions.approve(ctx, vid, "outline")
    stop_while_writing(ctx, vid, fake)
    v = video(ctx, vid)
    assert v["state"] == "outlined" and v["draft_note"] is None
    assert cards(ctx, vid, "outline")[-1]["card_status"] == "active"


def test_revise_keeps_the_draft_and_regenerate_starts_fresh(ctx):
    vid, fake = outlined(ctx)
    fake.replies += [outline_data(hook="Revised hook."), outline_data(hook="Fresh hook.")]

    actions.revise(ctx, vid, "outline", "open on the storm")
    run(ctx)
    revise = fake.requests[1]
    assert "Here is the current outline" in user_text(revise)
    assert "A storm, a locked door" in user_text(revise) and "1. open on the storm" in user_text(revise)

    actions.regenerate(ctx, vid, "outline")
    run(ctx)
    with pytest.raises(actions.ActionError):
        actions.regenerate(ctx, vid, "script")  # no script is waiting
    fresh = fake.requests[2]
    assert "current outline" not in user_text(fresh) and "Revised hook" not in user_text(fresh)
    assert "1. open on the storm" in user_text(fresh)  # the note is kept

    assert json.loads(video(ctx, vid)["outline_json"])["hook"] == "Fresh hook."
    found = cards(ctx, vid, "outline")
    assert [c["card"]["version"] for c in found] == [1, 2, 3]
    assert [c["card_status"] for c in found] == ["revised", "regenerated", "active"]


def test_failed_checks_get_one_retry_with_the_problems(ctx):
    bad = outline_data(n=7)
    bad["beats"][3]["skill"] = ""
    fake = use(ctx, bad, outline_data())
    vid = actions.new_video(ctx, "zombie", "Thirty days in a mall")
    run(ctx)

    assert video(ctx, vid)["state"] == "outlined"
    first, second = fake.requests
    assert len(second["messages"]) == 3
    assert second["messages"][1]["role"] == "assistant"
    fix = second["messages"][2]["content"]
    assert "there are 7 beats; it needs 8 to 10" in fix and "beat 4 has no skill" in fix
    assert second["system"] == first["system"]  # same cached prefix
    assert len(costs(ctx, vid)) == 2  # both calls cost money


def test_failing_twice_stops_at_once_with_the_problems(ctx):
    fake = use(ctx, outline_data(n=7), outline_data(n=7))
    vid = actions.new_video(ctx, "zombie", "Thirty days in a mall")
    run(ctx)

    v = video(ctx, vid)
    assert v["state"] == "failed" and v["resume_state"] == "new"
    assert "failed its checks twice" in v["error"] and "7 beats" in v["error"]
    assert len(fake.requests) == 2  # not 2 per attempt × 3 attempts
    assert len(costs(ctx, vid)) == 2
    assert cards(ctx, vid, "error")


def test_script_streams_progress_and_is_saved_in_pipeline_shape(ctx):
    vid, fake = outlined(ctx)
    outline = json.loads(video(ctx, vid)["outline_json"])
    fake.replies.append(script_data(outline))
    actions.approve(ctx, vid, "outline")
    run(ctx)

    req = fake.requests[1]
    assert req["max_tokens"] == 128000 and "Beat 1 | Day 1 | Beat 1 (hero beat)" in user_text(req)
    assert "{visual_guide}" not in req["system"][0]["text"] and "One frame, one moment" in req["system"][0]["text"]
    v = video(ctx, vid)
    assert v["state"] == "scripted"
    script = json.loads(v["script_json"])
    assert len(script) == 54 and script[0]["idx"] == 1 and script[0]["beat_idx"] == 0
    assert script[-1]["beat_idx"] == 8 and {s["motion"] for s in script} == {"kenburns", "clip"}
    [progress] = cards(ctx, vid, "progress")
    assert progress["card"]["unit"] == "scenes" and progress["card"]["done"] == 54
    assert progress["card_status"] == "done" and progress["text"] == "script 54 scenes"
    [card] = cards(ctx, vid, "script")
    assert card["card"]["scene_count"] == 54 and card["card"]["word_count"] == 54 * 35
    assert [p["name"] for p in card["card"]["places"]] == ["the flat", "the street"]
    first, second = card["card"]["beats"][1]["scenes"][:2]
    assert first["place"] == "the street" and first["cast"] == ["Rosa"] and first["tracker"] == "Water 19.5 L · Food 13.5 days"
    assert second["tracker"] is None
    assert script[6]["move"] == "he heads out" and json.loads(v["places_json"])[0]["id"] == "flat"
    assert "Cast:\n- Rosa, a lost kid." in user_text(req) and "Tracker: Water, 20 L at the start" in user_text(req)

    fake.replies.append(script_data(outline))
    actions.revise(ctx, vid, "script", "more about the water")
    run(ctx)
    revise = user_text(fake.requests[2])
    assert "Here is the current script" in revise and '"narration": "Scene 1 of beat 1.' in revise
    assert '{"id": "flat", "name": "the flat"' in revise and '"move": "he heads out"' in revise


def test_checks_name_each_problem():
    outline = outline_data()
    script = script_data(outline)["scenes"]
    assert checks.script(script, outline, 8, PLACES) == []
    script[4]["narration"] = " ".join(["word"] * 52)
    script[1]["motion"] = "clip"           # scene 2 is in beat 1, a hero beat: allowed
    script[6]["motion"] = "clip"           # scene 7 is in beat 2, which isn't
    script[30]["label"] = "Day 2"          # goes back in time
    script[31]["label"] = "Tuesday"
    script = [s for s in script if s["beat"] != 9]
    problems = checks.script(script, outline, 4, PLACES)
    assert "scene 5's narration is 52 words; keep each scene to 30 to 40" in problems
    assert "scene 7 is a clip in beat 2, which isn't a hero beat" in problems
    assert any("goes back in time" in p for p in problems)
    assert any("label 'Tuesday'" in p for p in problems)
    assert "beat 9 has no scenes" in problems
    assert "there are 5 clip scenes; this channel allows 4" in problems

    short = [s for n, s in enumerate(script_data(outline)["scenes"]) if n not in (19, 20)]  # hero beat 4 keeps 4
    assert checks.script(short, outline, 8, PLACES) == [
        "beat 4 is a hero beat but has only 4 scenes; give it 7 to 9, with the build-up, the moment and the aftermath"]

    told = lambda *labels: [{"label": label} for label in labels]  # noqa: E731
    assert checks._every_day(told("Day 1", "Day 1", "Day 2-4", "Day 5", "Day 9", "Day 10 to 15", "Day 17")) == [
        "scene 5 jumps from Day 5 to Day 9, skipping Days 6 to 8; tell every day, on its own or a few quiet ones "
        "together, like \"Day 6-8\"",
        "scene 6 tells 6 days at once (Day 10 to 15); keep a stretch to 3 days",
        "scene 7 jumps from Day 10 to 15 to Day 17, skipping Day 16; tell every day, on its own or a few quiet ones "
        "together, like \"Day 16\""]
    assert checks._every_day(told("Day 30", "Day 1", "Day 2"), 1) == []  # after a cold open
    assert checks._every_day(told(*[f"Day {d}-{d + 4}" for d in range(1, 50, 5)])) == []  # 50 days: 5 at once
    assert checks._every_day(told("Week 1", "Week 3")) == []  # weeks and months aren't checked

    o = outline_data(n=9, heroes=2)
    o["beats"][5]["skill"] = o["beats"][2]["skill"]
    problems = checks.outline(o)
    assert "2 beats are hero beats; it needs 3 to 4" in problems
    assert any("beat 6 teaches the same skill as beat 3" in p for p in problems)
    assert checks.titles(["A", "a", "x" * 101]) == ["title 3 is 101 characters; YouTube allows 100",
                                                     "two titles are the same"]

    # a cold open may start on a later day once, within the first scenes; after that, time only moves forward
    labels = lambda *days: [(f"scene {n}", f"Day {d}") for n, d in enumerate(days, 1)]  # noqa: E731
    assert checks._timeline(labels(30, 30, 1, 2, 5), checks.COLD_OPEN_SCENES) == []
    assert checks._timeline(labels(30, 1, 2, 1), checks.COLD_OPEN_SCENES) == ["scene 4: Day 1 comes after Day 2, which "
                                                                              "goes back in time"]
    late = labels(1, 2, 3, 4, 5, 6, 7, 2)
    assert checks._timeline(late, checks.COLD_OPEN_SCENES) == ["scene 8: Day 2 comes after Day 7, which goes back in time"]
    assert checks._timeline(labels(30, 1)) == ["scene 2: Day 1 comes after Day 30, which goes back in time"]  # outlines
    assert checks.description("Open cold on the worst moment, then rewind to the promise: a SEAL with an arsenal who can "
                              "barely walk, thirty days to cover two miles to the last convoy out of the city.") == [
        "the description reads like the outline's note (\"open cold\"); write it for viewers"]
    assert checks.description("Too short.") == ["the description is 10 characters; keep it to 150 to 900"]
    assert checks.description("You're a Navy SEAL sent home with a rebuilt knee the week the dead came. Thirty days, two "
                              "miles to the last convoy, and everyone on the street has seen your cane. Told day by "
                              "day from Day 1, a stick-figure zombie survival story.") == []
    assert checks.thumb_texts(["NO WATER LEFT", "ALONE", "HE WASN'T ALONE AT ALL", "WHY 🔥 NOW"]) == [
        "there are 4 thumb_texts; it needs 3", "thumb_text 2 is 1 word; keep it to 2 to 4",
        "thumb_text 3 is 5 words; keep it to 2 to 4",
        "thumb_text 4 has characters the thumbnail font can't draw; use plain letters, numbers and ! ? ' - : . , & $ %"]


def test_continuity_checks_name_each_problem():
    outline = outline_data()
    scenes = script_data(outline)["scenes"]  # 6 scenes a beat: beat 2 is scenes 7 to 12, on the street, with Rosa
    scenes[6]["move"] = ""                      # scene 7 is on the street after the flat, and doesn't say how
    scenes[12]["move"] = "he flies home"        # scene 13 quotes words its line doesn't have
    scenes[8]["place"] = "roof"
    scenes[36]["cast"] = ["Rosa"]               # scene 37 is in beat 7, which doesn't list her
    scenes[37]["cast"] = ["Ghost"]
    scenes[42]["tracker"] = [{"item": "Water", "amount": -1}]
    scenes[43]["shot"] = "aerial"
    scenes[48]["looks"] = [{"who": "Ghost", "now": " "}]
    for s in scenes:
        if s["beat"] == 3:                      # the last beat that lists Rosa never names her
            s["narration"] = s["narration"].replace("Rosa is here. ", "")
        if s["beat"] == 5:
            s["tracker"] = []
    problems = checks.script(scenes, outline, 8, PLACES + [{"id": "flat", "name": "", "look": "x"}])
    assert problems == [
        "scene 44: shot must be wide, medium or close-up, not 'aerial'",
        "place 3 has no name", "places 1 and 3 have the same id (flat)",
        "scene 7 goes from flat to street, so its move must quote the words in its narration that tell where we are now",
        "scene 9: place 'roof' isn't one of the places",
        "scene 13's move ('he flies home') isn't in its narration word for word",
        "scene 37 shows Rosa, but the outline doesn't list them in beat 7",
        "scene 38 has 'Ghost' in its cast, but the outline's cast has no one by that name",
        "scene 43's tracker lists water; list every tracked item once: food, water",
        "scene 43's tracker has an amount that isn't a number of 0 or more",
        "scene 49's looks names 'Ghost'; use \"the stick figure\" or a cast name",
        "scene 49's look for Ghost has no now; say what they have on, or \"as usual\"",
        "beat 5 never shows the tracker; give the first scene of every beat one",
        "Rosa's part ends in beat 3, the last beat that lists them, but no line in it names them; say there what "
        "happens to them"]

    scenes = script_data(outline)["scenes"]     # a cold open on Day 30 may show her before she comes in
    scenes[0]["label"] = scenes[1]["label"] = "Day 30"
    scenes[0]["cast"] = ["Rosa"]
    assert checks.script(scenes, outline, 8, PLACES) == []
    old = {k: v for k, v in outline.items() if k not in ("cast", "tracker")}  # an outline from before the tracker
    for s in scenes:
        s["cast"], s["tracker"] = [], []
    assert checks.script(scenes, old, 8, PLACES) == []

    o = outline_data()
    o["cast"].append({"name": "rosa ", "look": "", "role": "her twin", "thread": "She waits."})
    o["beats"][4]["cast"] = ["Marco"]
    o["tracker"] = o["tracker"][:1]
    o["backstory"] = " "
    assert checks.outline(o) == [
        "the backstory is empty", "cast member 2 has no look", "cast members 1 and 2 are both called rosa",
        "beat 5 lists 'Marco' in its cast, but the cast has no one by that name",
        "the tracker has 1 item; it needs 2 to 4"]


def test_next_part_outline_starts_from_the_story_so_far(ctx):
    from stages import outline as outline_stage
    outline = outline_data()
    vid, fake = outlined(ctx, outline)
    fake.replies.append(script_data(outline))
    actions.approve(ctx, vid, "outline")
    run(ctx)
    actions.approve(ctx, vid, "script")  # the scenes exist now, so where part 1 ends is known

    redrawn = outline_data()
    redrawn["cast"][0]["look"] = "a girl in a green coat"  # a returning character keeps her look
    fake.replies.append(redrawn)
    nxt = actions.next_part(ctx, vid, "they reach the boat")
    assert outline_stage.run_once(ctx)
    text = user_text(fake.requests[-1])
    assert "This video is Part 2 of a series" in text and "Part 1:" in text and "they reach the boat" in text
    assert "How it ended on screen: Scene 52 of beat 9." in text
    assert "What people had on at the end: the stick figure: a rain poncho" in text
    assert "Where the tracker stood at the end: Water 16 L; Food 10 days" in text
    second = json.loads(video(ctx, nxt)["outline_json"])
    assert second["part"] == 2 and second["cast"][0]["look"] == "a stick-figure girl in a yellow raincoat"


def test_prompt_edits_apply_on_the_next_call_and_bad_placeholders_stop(ctx):
    path = ctx.config.root / "prompts" / "outline.md"
    text = path.read_text(encoding="utf-8")
    path.write_text(text.replace("## What to write", "Always include a dog.\n\n## What to write"), encoding="utf-8")
    vid, fake = outlined(ctx)
    assert "Always include a dog." in fake.requests[0]["system"][0]["text"]

    path.write_text(text.replace("## What to write", "Mood: {mood}\n\n## What to write"), encoding="utf-8")
    actions.regenerate(ctx, vid, "outline")
    run(ctx)
    v = video(ctx, vid)
    assert v["state"] == "failed" and "{mood}" in v["error"] and "isn't a placeholder" in v["error"]
    assert len(fake.requests) == 1  # nothing was sent

    path.write_text(text.replace("## What to write", "The idea is {idea}.\n\n## What to write"), encoding="utf-8")
    fake.replies.append(outline_data())
    actions.retry(ctx, vid)
    run(ctx)
    assert "above the user-turn line" in video(ctx, vid)["error"]

    path.write_text(text, encoding="utf-8")
    actions.retry(ctx, vid)
    run(ctx)
    assert video(ctx, vid)["state"] == "outlined" and len(fake.requests) == 2


def test_picture_check_sends_the_pictures_and_returns_what_is_wrong(ctx, tmp_path):
    fake = use(ctx, {"seen": "A boy kneels beside a towel on the floor.",
                     "noticed": ["The towel is on the floor.", "The flashlight is on the left."],
                     "problems": ["Eli's hands press the folded towel onto the stick figure's knee, not the floor", " "]})
    fake.checks = None  # answer this check from the scripted reply
    before, after = tmp_path / "s031.png", tmp_path / "s032.png"
    for path in (before, after):
        Image.new("RGB", (1920, 1080), "white").save(path)
    values = {"idx": 32, "label": "Day 14", "shot": "close-up", "narration": "Then the blood. You talk Eli through it.",
              "visual_prompt": "Close-up: Eli's small hands pressing a folded towel hard on the stick figure's knee.",
              "people": "the stick figure (the main character): a knee brace; Eli: a boy in a red cap",
              "images": "Image 1 is the moment before this scene, as it was drawn; image 2 is the new picture to check."}
    problems = ctx.llm.check_picture(ctx.channel("zombie"), "still", values, [before, after], NoMeter())
    assert problems == ["Eli's hands press the folded towel onto the stick figure's knee, not the floor"]

    [req] = fake.requests
    assert req["model"] == "claude-sonnet-5-5" and req["max_tokens"] == 4000
    assert req["output_config"]["effort"] == "medium"
    assert list(req["output_config"]["format"]["schema"]["properties"]) == ["seen", "noticed", "problems"]  # look, then judge
    blocks = req["messages"][0]["content"]
    assert [b["type"] for b in blocks] == ["image", "image", "text"]
    with Image.open(io.BytesIO(base64.b64decode(blocks[0]["source"]["data"]))) as img:
        assert img.size == (1280, 720) and blocks[0]["source"]["media_type"] == "image/jpeg"
    text = blocks[2]["text"]
    assert text.startswith("Scene 32 (Day 14), a close-up.") and "pressing a folded towel" in text
    assert "Eli: a boy in a red cap" in text and "image 2 is the new picture to check" in text
    system = req["system"][0]["text"]
    assert "Check, in this order" in system and ctx.channel("zombie").style_prompt in system and "{" not in system


def test_budget_guard_refuses_before_calling(ctx):
    fake = use(ctx)
    vid = actions.new_video(ctx, "zombie", "Thirty days in a mall")
    with ctx.connect() as conn:
        conn.execute("UPDATE videos SET cost_usd = 49.9 WHERE id = ?", (vid,))
    run(ctx)
    v = video(ctx, vid)
    assert v["state"] == "failed" and "over its $50.00 budget" in v["error"]
    assert fake.requests == []


def test_api_errors(ctx, monkeypatch):
    fake = use(ctx, api_error(anthropic.AuthenticationError, 401))
    vid = actions.new_video(ctx, "zombie", "Thirty days in a mall")
    run(ctx)
    assert "ANTHROPIC_API_KEY" in video(ctx, vid)["error"] and len(fake.requests) == 1  # no retries

    fake.replies += [api_error(anthropic.InternalServerError, 500)] * 3
    actions.retry(ctx, vid)
    run(ctx)  # a server error is worth retrying: 3 attempts, then the error card
    assert len(fake.requests) == 4 and "InternalServerError" in video(ctx, vid)["error"]

    fake.replies.append((outline_data(), USAGE, "max_tokens"))
    actions.retry(ctx, vid)
    run(ctx)
    assert "claude.max_tokens.outline" in video(ctx, vid)["error"] and len(costs(ctx, vid)) == 1

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    ctx.llm = ClaudeLLM(ctx.config)
    actions.retry(ctx, vid)
    run(ctx)
    assert "needs ANTHROPIC_API_KEY in .env" in video(ctx, vid)["error"]


def test_provider_switch(ctx):
    llm, tts, images, video_ = make_providers(ctx.config)
    assert isinstance(llm, ClaudeLLM) and isinstance(images, StubImages)
    ctx.config.mode = "stub"
    assert isinstance(make_providers(ctx.config)[0], StubLLM)  # mode: stub wins over providers
    ctx.config.mode = "live"
    ctx.config.providers["images"] = "midjourney"
    with pytest.raises(ValueError, match="providers.images: 'midjourney' isn't available; use stub or fal"):
        make_providers(ctx.config)


def test_end_to_end_with_claude_writing(ctx, monkeypatch):
    """Small limits so the stub voice, stills and ffmpeg render stay quick; costs split real vs simulated."""
    for name, value in (("BEATS", (3, 4)), ("HERO_BEATS", (1, 2)), ("HERO_SCENES_OK", 1), ("SCENES", (4, 8)),
                        ("TOTAL_WORDS_OK", (100, 400))):
        monkeypatch.setattr(checks, name, value)
    outline = outline_data(n=3, heroes=1)
    words = {"titles": ["One", "Two", "Three"], "thumb_texts": ["NO WATER LEFT", "DAY 365", "HE WASN'T ALONE"],
             "description": "You're on a rooftop with a week of water and the streets full of the dead below. Day by "
                            "day, from Day 1, this is how you last until the river goes down. A stick-figure survival story."}
    fake = use(ctx, outline, script_data(outline, n=6), {**words, "thumb_texts": ["TOO MANY WORDS FOR THIS"] * 3},
               words, {"narration": " ".join(["better"] * 32)})
    vid = actions.new_video(ctx, "zombie", "A week on a rooftop")
    run(ctx)
    assert "3 to 4 beats" in fake.requests[0]["system"][0]["text"]
    actions.approve(ctx, vid, "outline")
    run(ctx)
    actions.approve(ctx, vid, "script")
    run(ctx)
    assert video(ctx, vid)["state"] == "assembled"
    render = cards(ctx, vid, "render")[-1]["card"]
    assert render["titles"] == ["One", "Two", "Three"]
    assert render["thumb_texts"] == ["NO WATER LEFT", "DAY 365", "HE WASN'T ALONE"]
    assert fake.requests[2]["output_config"]["effort"] == "medium"
    assert "2 to 4 words and at most 24 characters" in fake.requests[2]["system"][0]["text"]  # what the checks take
    assert "thumb_text 1 is 5 words" in user_text(fake.requests[3], 2)  # the retry lists the problem

    actions.flag_scenes(ctx, vid, [2], "narration", "say what he hears")
    run(ctx)
    regen = user_text(fake.requests[4])
    assert "Scene 2 (Day 1) needs its line rewritten" in regen and "say what he hears" in regen
    assert "The line before it: Scene 1 of beat 1." in regen and "The line after it: Scene 3 of beat 2." in regen
    with ctx.connect() as conn:
        line = conn.execute("SELECT narration FROM scenes WHERE video_id = ? AND idx = 2", (vid,)).fetchone()[0]
    assert line == " ".join(["better"] * 32)

    rows = costs(ctx, vid)
    assert {r["simulated"] for r in rows if r["provider"] == "llm"} == {0}
    assert {r["simulated"] for r in rows if r["provider"] != "llm"} == {1}
    stages = [r["stage"] for r in rows if r["provider"] == "llm"]
    assert [s for s in stages if s != "check"] == ["outline", "script", "thumbs", "thumbs", "regen"]
    assert stages.count("check") == 7 == len(fake.checks_asked)  # the poncho look, then each of the 6 stills once
    asked = [c["messages"][0]["content"] for c in fake.checks_asked]
    assert "redrawn with: a rain poncho" in asked[0][-1]["text"] and len(asked[0]) == 3  # before and after
    assert asked[1][-1]["text"].startswith("Scene 1 (Day 1), a medium.") and len(asked[1]) == 3  # reference, new
    assert "The line before it: (this is the first scene)" in asked[1][-1]["text"]
    assert asked[2][-1]["text"].startswith("Scene 2 (Day 1), a medium.") and len(asked[2]) == 4  # follows scene 1
    assert "Image 2 is the moment before this scene" in asked[2][-1]["text"]
    assert "The line before it: Scene 1 of beat 1." in asked[2][-1]["text"]


@pytest.mark.live
@pytest.mark.skipif(not os.environ.get("ANTHROPIC_API_KEY"), reason="needs ANTHROPIC_API_KEY")
def test_live_outline(ctx):
    """A real outline with the real prompt (a few cents). The provider's checks must pass."""
    ctx.llm = ClaudeLLM(ctx.config)
    vid = actions.new_video(ctx, "zombie", "Day 1 to Day 30 trapped in a shopping mall")
    run(ctx)
    v = video(ctx, vid)
    assert v["state"] == "outlined", v["error"]
    outline = json.loads(v["outline_json"])
    assert checks.outline({k: v for k, v in outline.items() if k != "topic"}) == []
    [cost] = costs(ctx, vid)
    detail = json.loads(cost["detail"])
    print(f"\nlive outline: ${cost['usd']:.3f}, {detail}\n{prompts.outline_text(outline)}")

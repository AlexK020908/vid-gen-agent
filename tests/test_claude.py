"""The Claude provider with a fake Anthropic client: requests, checks and the one retry, costs, prompts, regenerate.

FakeAnthropic replays scripted replies (JSON plus usage numbers) through the same `messages.stream()`
shape the SDK has, and records every request. No network, $0. The one live test writes a real
outline (a few cents) and is skipped without ANTHROPIC_API_KEY.
"""
import json
import os
import shutil
import threading

import anthropic
import httpx2
import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient

from core import actions, db
from core.config import ROOT
from core.context import make_ctx
from core.engine import Engine
from providers import checks, make_providers, prompts
from providers.claude import ClaudeLLM
from providers.images import StubImages
from providers.llm import StubLLM
from server.app import create_app

load_dotenv(ROOT / ".env")  # only the live test uses the key

DAYS = [1, 2, 3, 5, 7, 10, 14, 21, 30, 45, 60, 75, 90, 120, 150, 180, 210, 240, 270, 300, 330, 350, 360, 365, 366]
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
    `client.messages.stream` and `client.beta.messages.stream` (server-side fallback) both land here."""

    def __init__(self, *replies) -> None:
        self.replies = list(replies)
        self.requests: list[dict] = []
        self.messages = self
        self.beta = self

    def stream(self, **request):
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


# --- replies ---------------------------------------------------------------------------------

def outline_data(n: int = 22, heroes: int = 6, **changes) -> dict:
    """Rosa is in beats 2 and 3, so her thread ends in beat 3."""
    step = n // heroes
    hero = set(range(0, step * heroes, step))
    beats = [{"label": f"Day {DAYS[i]}", "title": f"Beat {i + 1}", "summary": f"What happens in beat {i + 1}.",
              "skill": f"skill number {i + 1}", "hero": i in hero, "cast": ["Rosa"] if i in (1, 2) else []}
             for i in range(n)]
    return {"hook": "A storm, a locked door, and nobody coming.",
            "backstory": "The river broke its banks in the night and took the power with it.",
            "cast": [{"name": "Rosa", "look": "a stick-figure girl in a yellow raincoat", "role": "a lost kid",
                      "thread": "He finds her on Day 2 and gets her to her mother on Day 3."}],
            "tracker": [{"item": "Water", "unit": "L", "start": 20}, {"item": "Food", "unit": "days", "start": 14}],
            "beats": beats, "ending": "He walks out.", **changes}


PLACES = [{"id": "flat", "name": "the flat", "look": "A small flat: a sofa on the left, a window at the back."},
          {"id": "street", "name": "the street", "look": "A flooded street of brick houses, a bus stop on the right."}]


def script_data(outline: dict, n: int = 110, words: int = 35) -> dict:
    """Beats alternate between the flat and the street, and each move is told in the line. Each beat's first scene
    carries the tracker, and the cast are named in every scene of the beats that list them."""
    beats = outline["beats"]
    per = [n // len(beats) + (1 if i < n % len(beats) else 0) for i in range(len(beats))]
    scenes = []
    for b, count in enumerate(per):
        place = PLACES[b % 2]["id"]
        cast = list(beats[b].get("cast") or [])
        for k in range(count):
            move = ("he heads out" if place == "street" else "back home") if scenes and scenes[-1]["place"] != place else ""
            line = (f"Scene {len(scenes) + 1} of beat {b + 1}. " + (f"{move.capitalize()}. " if move else "")
                    + "".join(f"{name} is here. " for name in cast) + " ".join(["word"] * words))
            tracker = [{"item": t["item"], "amount": t["start"] - b / 2} for t in outline.get("tracker") or []]
            scenes.append({"beat": b + 1, "label": beats[b]["label"], "place": place, "cast": cast,
                           "narration": " ".join(line.split()[:words]), "move": move,
                           "tracker": tracker if k == 0 else [], "set_change": "",
                           "shot": "close-up" if k == 2 else "medium",
                           "visual_prompt": f"the stick figure in beat {b + 1}, shot {k + 1}",
                           "motion": "clip" if k == 0 and beats[b]["hero"] else "kenburns"})
    return {"places": PLACES, "scenes": scenes}


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
                               "agent": {"comment_on_gates": False}, "render": {"engine": "ffmpeg"}, "topics": {"competitors": "off"}})


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
    assert channel.scenario_family in system["text"] and "20 to 25 beats" in system["text"]
    assert "{" not in system["text"].replace("{\"", "")  # every placeholder filled
    assert req["output_config"]["effort"] == "high"
    assert req["output_config"]["format"]["type"] == "json_schema"
    assert "Day 1 to Day 365 in a flooded subway" in user_text(req) and "(none)" in user_text(req)
    assert "current outline" not in user_text(req)

    outline = json.loads(video(ctx, vid)["outline_json"])
    assert outline["topic"] == "Day 1 to Day 365 in a flooded subway" and len(outline["beats"]) == 22
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
    assert len(json.loads(video(ctx, vid)["outline_json"])["beats"]) == 22  # both halves joined into one reply
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

    with TestClient(create_app(ctx, run_engine=False), base_url="http://localhost") as client:
        assert client.post(f"/api/videos/{vid}/regenerate", json={"gate": "outline"}).status_code == 200
        run(ctx)
        again = client.post(f"/api/videos/{vid}/regenerate", json={"gate": "script"})
        assert again.status_code == 409  # no script is waiting
    fresh = fake.requests[2]
    assert "current outline" not in user_text(fresh) and "Revised hook" not in user_text(fresh)
    assert "1. open on the storm" in user_text(fresh)  # the note is kept

    assert json.loads(video(ctx, vid)["outline_json"])["hook"] == "Fresh hook."
    found = cards(ctx, vid, "outline")
    assert [c["card"]["version"] for c in found] == [1, 2, 3]
    assert [c["card_status"] for c in found] == ["revised", "regenerated", "active"]


def test_failed_checks_get_one_retry_with_the_problems(ctx):
    bad = outline_data(n=18)
    bad["beats"][3]["skill"] = ""
    fake = use(ctx, bad, outline_data())
    vid = actions.new_video(ctx, "zombie", "Thirty days in a mall")
    run(ctx)

    assert video(ctx, vid)["state"] == "outlined"
    first, second = fake.requests
    assert len(second["messages"]) == 3
    assert second["messages"][1]["role"] == "assistant"
    fix = second["messages"][2]["content"]
    assert "there are 18 beats; it needs 20 to 25" in fix and "beat 4 has no skill" in fix
    assert second["system"] == first["system"]  # same cached prefix
    assert len(costs(ctx, vid)) == 2  # both calls cost money


def test_failing_twice_stops_at_once_with_the_problems(ctx):
    fake = use(ctx, outline_data(n=18), outline_data(n=18))
    vid = actions.new_video(ctx, "zombie", "Thirty days in a mall")
    run(ctx)

    v = video(ctx, vid)
    assert v["state"] == "failed" and v["resume_state"] == "new"
    assert "failed its checks twice" in v["error"] and "18 beats" in v["error"]
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
    assert len(script) == 110 and script[0]["idx"] == 1 and script[0]["beat_idx"] == 0
    assert script[-1]["beat_idx"] == 21 and {s["motion"] for s in script} == {"kenburns", "clip"}
    [progress] = cards(ctx, vid, "progress")
    assert progress["card"]["unit"] == "scenes" and progress["card"]["done"] == 110
    assert progress["card_status"] == "done" and progress["text"] == "script 110 scenes"
    [card] = cards(ctx, vid, "script")
    assert card["card"]["scene_count"] == 110 and card["card"]["word_count"] == 110 * 35
    assert [p["name"] for p in card["card"]["places"]] == ["the flat", "the street"]
    first, second = card["card"]["beats"][1]["scenes"][:2]
    assert first["place"] == "the street" and first["cast"] == ["Rosa"] and first["tracker"] == "Water 19.5 L · Food 13.5 days"
    assert second["tracker"] is None
    assert script[5]["move"] == "he heads out" and json.loads(v["places_json"])[0]["id"] == "flat"
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
    script[5]["motion"] = "clip"           # scene 6 is in beat 2, which isn't
    script[60]["label"] = "Day 2"          # goes back in time
    script[61]["label"] = "Tuesday"
    script = [s for s in script if s["beat"] != 9]
    problems = checks.script(script, outline, 6, PLACES)
    assert "scene 5's narration is 52 words; keep each scene to 30 to 40" in problems
    assert "scene 6 is a clip in beat 2, which isn't a hero beat" in problems
    assert any("goes back in time" in p for p in problems)
    assert any("label 'Tuesday'" in p for p in problems)
    assert "beat 9 has no scenes" in problems
    assert "there are 8 clip scenes; this channel allows 6" in problems

    o = outline_data(n=22, heroes=4)
    o["beats"][5]["skill"] = o["beats"][2]["skill"]
    problems = checks.outline(o)
    assert "4 beats are hero beats; it needs 5 to 7" in problems
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
    assert checks.thumb_texts(["NO WATER LEFT", "ALONE", "HE WASN'T ALONE AT ALL", "WHY 🔥 NOW"]) == [
        "there are 4 thumb_texts; it needs 3", "thumb_text 2 is 1 word; keep it to 2 to 4",
        "thumb_text 3 is 5 words; keep it to 2 to 4",
        "thumb_text 4 has characters the thumbnail font can't draw; use plain letters, numbers and ! ? ' - : . , & $ %"]


def test_continuity_checks_name_each_problem():
    outline = outline_data()
    scenes = script_data(outline)["scenes"]  # 5 scenes a beat: beat 2 is scenes 6 to 10, on the street, with Rosa
    scenes[5]["move"] = ""                      # scene 6 is on the street after the flat, and doesn't say how
    scenes[10]["move"] = "he flies home"        # scene 11 quotes words its line doesn't have
    scenes[7]["place"] = "roof"
    scenes[30]["cast"] = ["Rosa"]               # scene 31 is in beat 7, which doesn't list her
    scenes[31]["cast"] = ["Ghost"]
    scenes[35]["tracker"] = [{"item": "Water", "amount": -1}]
    scenes[36]["shot"] = "aerial"
    for s in scenes:
        if s["beat"] == 3:                      # the last beat that lists Rosa never names her
            s["narration"] = s["narration"].replace("Rosa is here. ", "")
        if s["beat"] == 5:
            s["tracker"] = []
    problems = checks.script(scenes, outline, 8, PLACES + [{"id": "flat", "name": "", "look": "x"}])
    assert problems == [
        "scene 37: shot must be wide, medium or close-up, not 'aerial'",
        "place 3 has no name", "places 1 and 3 have the same id (flat)",
        "scene 6 goes from flat to street, so its move must quote the words in its narration that tell where we are now",
        "scene 8: place 'roof' isn't one of the places",
        "scene 11's move ('he flies home') isn't in its narration word for word",
        "scene 31 shows Rosa, but the outline doesn't list them in beat 7",
        "scene 32 has 'Ghost' in its cast, but the outline's cast has no one by that name",
        "scene 36's tracker lists water; list every tracked item once: food, water",
        "scene 36's tracker has an amount that isn't a number of 0 or more",
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
    for name, value in (("BEATS", (3, 4)), ("HERO_BEATS", (1, 2)), ("SCENES", (4, 8)), ("TOTAL_WORDS_OK", (100, 400))):
        monkeypatch.setattr(checks, name, value)
    outline = outline_data(n=3, heroes=1)
    words = {"titles": ["One", "Two", "Three"], "thumb_texts": ["NO WATER LEFT", "DAY 365", "HE WASN'T ALONE"]}
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
    assert [r["stage"] for r in rows if r["provider"] == "llm"] == ["outline", "script", "thumbs", "thumbs", "regen"]


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

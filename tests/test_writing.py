"""The Claude Code session writes (BUILD.md phase 19): the outline, the script in parts, the reviewer's reads, flagged
scenes' rewrites and topic ideas, each a job answered over MCP and checked as it comes in. Pictures and voices are
stubs. $0."""
import json
import time

import pytest

from core import actions, db, jobs, performance
from core.context import make_ctx
from core.engine import Engine
from providers import checks
from providers.session import SessionLLM
from replies import outline_data, script_data
from server import claude_code
from stages import topics
from test_session import TITLES
from test_tools import call, result

SMALL = (("BEATS", (3, 4)), ("HERO_BEATS", (1, 2)), ("HERO_SCENES_OK", 1), ("SCENES", (4, 8)),
         ("TOTAL_WORDS_OK", (100, 400)))  # a 6-scene script, so the stub voice, stills and render stay quick
LINE = " ".join(["closer"] * 32)


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    for name, value in SMALL:
        monkeypatch.setattr(checks, name, value)
    ctx = make_ctx(data_dir=tmp_path, overrides={"mode": "stub", "stub": {"scenes": 6}, "engine": {"retry_backoff_s": 0},
                                                 "render": {"engine": "ffmpeg"},
                                                 "topics": {"competitors": "off", "cadence": False},
                                                 "youtube": {"reach": False, "signin_check": False}})
    ctx.llm = SessionLLM(ctx.config, fallback=ctx.llm)  # the writing from the session; the picture checks from the stub
    return ctx


def run(ctx) -> None:
    Engine(ctx).run_until_idle()


def waiting(ctx) -> list:
    with ctx.connect() as conn:
        return jobs.pending(conn)


def the_job(ctx, kind: str) -> int:
    [job] = waiting(ctx)
    assert job["kind"] == kind, (job["kind"], job["what"])
    return job["id"]


def brief(ctx, job: int, again: bool = False) -> str:
    return result(ctx, "take_job", {"job_id": job, "again": again}).content[0].text


def answer(ctx, job: int, reply, **part) -> tuple[str, bool]:
    return call(ctx, "answer_job", {"job_id": job, "answer": reply, **part})


def accepted(ctx, job: int, reply, **part) -> str:
    said, err = answer(ctx, job, reply, **part)
    assert not err, said
    return said


def video(ctx, vid: int):
    with ctx.connect() as conn:
        return db.get_video(conn, vid)


def said(ctx, vid: int | None = None) -> list[str]:
    with ctx.connect() as conn:
        if vid is None:
            rows = conn.execute("""SELECT m.text FROM messages m JOIN threads t ON t.id = m.thread_id
                                   WHERE t.video_id IS NULL ORDER BY m.id""")
        else:
            rows = conn.execute("SELECT text FROM messages WHERE video_id = ? ORDER BY id", (vid,))
        return [r["text"] or "" for r in rows]


def outlined(ctx, idea: str = "A week on a rooftop") -> int:
    """A new video whose outline the session writes and its reviewer passes."""
    vid = actions.new_video(ctx, "zombie", idea)
    run(ctx)
    accepted(ctx, the_job(ctx, "outline"), outline_data(n=3, heroes=1))
    run(ctx)
    accepted(ctx, the_job(ctx, "critic"), {"verdict": "fine", "problems": []})
    run(ctx)
    assert video(ctx, vid)["state"] == "outlined"
    return vid


def test_a_video_written_by_the_session(ctx):
    vid = actions.new_video(ctx, "zombie", "A week on a rooftop")
    run(ctx)
    job = the_job(ctx, "outline")
    asked = brief(ctx, job)
    assert "The hook checklist" in asked and "A week on a rooftop" in asked and '"hook"' in asked
    assert any(f"Waiting for Claude Code: the outline (job {job})" in t for t in said(ctx, vid))
    assert video(ctx, vid)["attempts"] == 0 and video(ctx, vid)["error"] is None  # parked, not failed
    assert accepted(ctx, job, outline_data(n=3, heroes=1)) == "Accepted: the outline. The video carries on."

    run(ctx)  # the reviewer's read is a job of its own, for the critic agent
    review = the_job(ctx, "critic")
    asked = brief(ctx, review)
    assert "hand the job to the critic agent" in asked and "Review this outline:" in asked
    assert "the verdict is revise but no problems" in answer(ctx, review, {"verdict": "revise", "problems": []})[0]
    accepted(ctx, review, {"verdict": "fine", "problems": []})
    run(ctx)
    assert video(ctx, vid)["state"] == "outlined"

    actions.approve(ctx, vid, "outline")
    run(ctx)
    job = the_job(ctx, "script")
    assert "send it in parts" in brief(ctx, job)
    outline = json.loads(video(ctx, vid)["outline_json"])
    script = script_data(outline, n=6)  # 2 scenes a beat
    beat = [{"scenes": script["scenes"][i:i + 2]} for i in (0, 2, 4)]
    beat[0]["places"] = script["places"]
    assert accepted(ctx, job, beat[0], part=1) == ("Part 1 accepted: 1 part in (scenes 2, places 2). Send part 2, "
                                                   "with last=true on the final part.")
    early, err = answer(ctx, job, beat[2], part=3)
    assert err and "part 3 can't come yet: 1 part is in, so the next is part 2" in early
    short = {"scenes": [{**beat[1]["scenes"][0], "narration": "Rosa is here. Too short."}, beat[1]["scenes"][1]]}
    wrong, err = answer(ctx, job, short, part=2)
    assert err and wrong.startswith("Part 2 not accepted") and "scene 3's narration is 5 words" in wrong
    accepted(ctx, job, beat[1], part=2)
    assert "So far: 2 parts in (scenes 4, places 2)" in brief(ctx, job, again=True)  # a worker coming back sees them
    clip = {"scenes": [beat[2]["scenes"][0], {**beat[2]["scenes"][1], "motion": "clip"}]}
    whole, err = answer(ctx, job, clip, part=3, last=True)
    assert err and "The parts are kept (3 parts in (scenes 6, places 2))" in whole
    assert "scene 6 is a clip in beat 3, which isn't a hero beat" in whole
    assert accepted(ctx, job, beat[2], part=3, last=True) == "Accepted: the script. The video carries on."

    run(ctx)  # the reviewer finds something; its notes go back to the writer as a rewrite job
    review = the_job(ctx, "critic")
    assert "Review this script written from it." in brief(ctx, review)
    accepted(ctx, review, {"verdict": "revise", "problems": [
        {"where": "scene 3", "what": "Rosa turns up from nowhere.", "fix": "Say she was hiding under the stairs."}]})
    run(ctx)
    rewrite = the_job(ctx, "script")
    assert "Reviewer, scene 3: Rosa turns up from nowhere. Fix: Say she was hiding under the stairs." in brief(ctx, rewrite)
    fixed = {**script, "scenes": [*script["scenes"][:2], {**script["scenes"][2], "visual_prompt": "Rosa under the stairs"},
                                  *script["scenes"][3:]]}
    accepted(ctx, rewrite, fixed)  # a whole reply is fine too
    run(ctx)
    assert video(ctx, vid)["state"] == "scripted"
    assert json.loads(video(ctx, vid)["script_json"])[2]["visual_prompt"] == "Rosa under the stairs"
    assert any(t.startswith("The reviewer found 1 thing in the script") for t in said(ctx, vid))

    actions.approve(ctx, vid, "script")
    run(ctx)
    accepted(ctx, the_job(ctx, "titles"), TITLES)
    run(ctx)
    assert video(ctx, vid)["state"] == "assembled"

    actions.flag_scenes(ctx, vid, [2, 5], "narration", "say what he hears")
    run(ctx)  # one job a scene, each scene waiting for its own while nothing counts as a failed attempt
    fixes = sorted(waiting(ctx), key=lambda j: j["scene_idx"])  # the scenes run in parallel
    assert [(j["kind"], j["scene_idx"], j["what"]) for j in fixes] == [
        ("regen", 2, "the fix for scene 2"), ("regen", 5, "the fix for scene 5")]
    with ctx.connect() as conn:
        held = conn.execute("SELECT idx, state, attempts, lease_until FROM scenes WHERE video_id = ? AND idx IN (2, 5)",
                            (vid,)).fetchall()
    assert all(r["state"] == "flagged" and r["attempts"] == 0 and r["lease_until"] > time.time() for r in held)
    assert "say what he hears" in brief(ctx, fixes[0]["id"])
    assert "the line is 3 words" in answer(ctx, fixes[0]["id"], {"narration": "He hears it."})[0]
    for j in fixes:
        accepted(ctx, j["id"], {"narration": LINE})
    run(ctx)
    assert video(ctx, vid)["state"] == "assembled"
    with ctx.connect() as conn:
        lines = [r["narration"] for r in conn.execute("SELECT narration FROM scenes WHERE video_id = ? ORDER BY idx",
                                                      (vid,))]
        spent = conn.execute("""SELECT COUNT(*) FROM costs WHERE video_id = ? AND provider = 'llm'
                                AND stage IN ('outline', 'script', 'critic', 'thumbs', 'regen')""", (vid,)).fetchone()[0]
    assert lines[1] == lines[4] == LINE and lines[0] != LINE
    assert spent == 0 and waiting(ctx) == []


def test_a_long_brief_goes_to_a_file(ctx, monkeypatch):
    monkeypatch.setattr(claude_code, "BRIEF_MAX", 2000)
    actions.new_video(ctx, "zombie", "A week on a rooftop")
    run(ctx)
    job = the_job(ctx, "outline")
    asked = brief(ctx, job)
    path = ctx.config.data_dir / "jobs" / f"job-{job}.md"
    assert f"so it's in {path}: read all of it" in asked and "## Instructions" not in asked
    assert '"hook"' in asked  # the reply's shape stays in the reply
    written = path.read_text(encoding="utf-8")
    assert "## Instructions" in written and "A week on a rooftop" in written and "The hook checklist" in written


def test_stop_drops_a_waiting_rewrite_and_gives_the_note_back(ctx):
    vid = outlined(ctx)
    actions.revise(ctx, vid, "outline", "make the storm worse")
    run(ctx)
    job = the_job(ctx, "outline")
    actions.stop_writing(ctx, vid)
    assert waiting(ctx) == []
    run(ctx)  # the stage wakes at once and stops
    v = video(ctx, vid)
    assert v["state"] == "outlined" and v["draft_note"] == "make the storm worse"
    with ctx.connect() as conn:
        assert jobs.get(conn, job)["status"] == "superseded"
    assert ("Stopped. Back to the card, with your note kept as its draft note to change and send again with revise: "
            "make the storm worse") in said(ctx, vid)


def ideas(count: int, start: int = 1) -> dict:
    return {"topics": [{"title": f"Day 1 to Day 30 on idea {n}", "why": "Rooftops do well this month.",
                        "family": "rooftop", "based_on": [1]} for n in range(start, start + count)]}


def queued(ctx) -> list[str]:
    with ctx.connect() as conn:
        return [r["title"] for r in conn.execute("SELECT title FROM topics WHERE status = 'queued' ORDER BY id")]


def test_topic_ideas_wait_for_the_session(ctx):
    ctx.config.topics["competitors"] = "stub"
    ctx.channel("zombie").competitors = ["UCaaaaaaaaaaaaaaaaaaaaaa"]
    count = int(ctx.config.topics.get("propose", 3))
    topics.run_once(ctx)  # the check runs, and its ideas become a job
    job = the_job(ctx, "topic")
    row = waiting(ctx)[0]
    assert row["video_id"] is None and row["channel_id"] == "zombie"
    home = said(ctx)
    assert any("Waiting for Claude Code: Topic ideas for" in t and f"(job {job})" in t for t in home)
    assert not any("Couldn't get topic ideas" in t for t in home)
    topics.run_once(ctx)
    assert [j["id"] for j in waiting(ctx)] == [job]  # the check isn't due again, so nothing new
    assert "a day)" in brief(ctx, job)  # the numbered hits the ideas cite
    assert accepted(ctx, job, ideas(count)).endswith("The ideas post within seconds.")
    topics.run_once(ctx)  # finds the answer and posts the round
    assert queued(ctx) == [f"Day 1 to Day 30 on idea {n}" for n in range(1, count + 1)]
    with ctx.connect() as conn:
        assert jobs.to_resume(conn) == []
        card = conn.execute("""SELECT card_json FROM messages WHERE json_extract(card_json, '$.kind') = 'topics'
                               """).fetchone()
    assert card is not None
    topics.run_once(ctx)
    assert len(queued(ctx)) == count  # posted once

    asked, err = call(ctx, "suggest_topics", {"count": 2})
    again = the_job(ctx, "topic")
    assert not err and asked.startswith(f"The topic ideas are a job for you: job {again}.")
    accepted(ctx, again, ideas(2, start=10))
    topics.run_once(ctx)
    assert queued(ctx)[-2:] == ["Day 1 to Day 30 on idea 10", "Day 1 to Day 30 on idea 11"]


def test_a_winners_follow_ups_wait_for_the_session(ctx):
    from test_loop import live_video, others, reading
    others(ctx, 48)
    vid = live_video(ctx, "Day 1 to Day 365 in a flooded subway", family="underground")
    reading(ctx, vid, 48, avd_pct=50.0, ctr=6.0, views=4000)
    assert performance.judge(ctx, vid, 48) == "winner"
    job = the_job(ctx, "topic")
    row = waiting(ctx)[0]
    assert row["video_id"] == vid and row["what"] == f"Follow-ups to #{vid}"
    assert not any("follow-up ideas failed" in t for t in said(ctx))
    accepted(ctx, job, ideas(performance.FOLLOW_UPS))
    topics.run_once(ctx)
    with ctx.connect() as conn:
        ranked = performance.ranked_topics(conn, "zombie")
    assert [t["source"] for t in ranked[:performance.FOLLOW_UPS]] == ["own_analytics"] * performance.FOLLOW_UPS
    assert ranked[0]["title"] == "Day 1 to Day 30 on idea 1"


def test_a_waiting_scene_holds_its_place_when_scenes_go_in_order(ctx):
    vid = actions.new_video(ctx, "zombie", "Three scenes")
    with ctx.connect() as conn:
        conn.execute("UPDATE videos SET state = 'generating' WHERE id = ?", (vid,))
        for idx in (1, 2, 3):
            conn.execute("""INSERT INTO scenes (video_id, idx, beat_idx, narration, visual_prompt, motion, state,
                              lease_until) VALUES (?, ?, 0, 'a line', 'a picture', 'kenburns', 'voiced', ?)""",
                         (vid, idx, time.time() + 900 if idx == 1 else None))  # scene 1 waits for Claude Code
        assert db.claim_scenes(conn, "voiced", 1, 60, 3, in_order=True) == []
        assert [s["idx"] for s in db.claim_scenes(conn, "voiced", 1, 60, 3)] == [2]  # parallel stages move on

"""The Claude Code session doing Claude's work (BUILD.md phase 17): jobs, the MCP endpoint, titles end to end. $0.
The rest of the writing is in tests/test_writing.py (phase 19) and the looking in tests/test_looking.py (phase 20);
here they stay with the stub."""
import asyncio
import json
import socket
import threading
import time

import pytest
import uvicorn
from mcp import Client

from core import actions, db, jobs
from core.context import make_ctx
from core.engine import Engine
from providers.llm import LLM
from providers.session import SessionLLM
from server import claude_code
from server.app import create_app

TITLES ={"titles": ["I Survived 100 Days on a Raft", "The Raft That Wouldn't Sink", "100 Days Adrift"],
          "thumb_texts": ["100 DAYS ADRIFT", "IT WON'T SINK", "NO LAND"],
          "description": "A stick figure wakes on a raft with no land in sight and twenty litres of water. Over a "
                         "hundred days he learns the sea's rules, loses most of what he has, and finds a way home."}


@pytest.fixture
def ctx(tmp_path):
    ctx = make_ctx(data_dir=tmp_path, overrides={"mode": "stub", "stub": {"scenes": 6}, "engine": {"retry_backoff_s": 0},
                                                 "render": {"engine": "ffmpeg", "pictures": "puppet", "puppet_fps": 4},
                                                 "topics": {"competitors": "off"}})
    others = tuple(name for name in vars(LLM) if not name.startswith("_") and name != "titles")
    ctx.llm = SessionLLM(ctx.config, ctx.llm, stubbed=others)  # titles from the session, the rest from the stub
    return ctx


def run(ctx) -> None:
    Engine(ctx).run_until_idle()


def call(server, *calls):
    """Runs tool calls in order on one in-process MCP connection; returns each result."""
    async def go():
        async with Client(server) as client:
            return [await client.call_tool(name, args) for name, args in calls]
    return asyncio.run(go())


def text(result) -> str:
    return result.content[0].text


def to_titles(ctx) -> int:
    vid = actions.new_video(ctx, "zombie", "Day 1 to Day 100 on a raft")
    run(ctx)
    actions.approve(ctx, vid, "outline")
    run(ctx)
    actions.approve(ctx, vid, "script")
    run(ctx)
    return vid


def test_titles_by_the_session(ctx):
    vid = to_titles(ctx)
    with ctx.connect() as conn:
        video = db.get_video(conn, vid)
        waiting = jobs.pending(conn)
        said = [r["text"] for r in conn.execute("SELECT text FROM messages WHERE video_id = ?", (vid,))]
    assert video["state"] == "generating" and video["thumbs_json"] is None
    assert video["attempts"] == 0 and video["error"] is None  # parked, not failed
    assert [(j["kind"], j["video_id"], j["what"]) for j in waiting] == [("titles", vid, "the titles")]
    job = waiting[0]["id"]
    assert any(f"Waiting for Claude Code: the titles (job {job})" in (t or "") for t in said)

    run(ctx)  # running again finds the same job: no second one, no second notice
    with ctx.connect() as conn:
        assert [j["id"] for j in jobs.pending(conn)] == [job]

    server = claude_code.make_server(ctx)
    listed, waited, brief, wrong, right, again = call(
        server, ("jobs", {}), ("wait", {"seconds": 30}), ("take_job", {"job_id": job}),
        ("answer_job", {"job_id": job, "answer": {**TITLES, "titles": TITLES["titles"][:2]}}),
        ("answer_job", {"job_id": job, "answer": TITLES}), ("take_job", {"job_id": job}))
    assert json.loads(text(listed))[0]["job_id"] == job
    assert json.loads(text(waited))["jobs_waiting"][0]["job_id"] == job  # returned at once: a job was waiting
    assert "## Instructions" in text(brief) and "## Reply with JSON in this shape" in text(brief)
    assert "thumb_texts" in text(brief) and "Day 1 to Day 100 on a raft" in text(brief)
    assert wrong.is_error and "there are 2 titles; it needs 3" in text(wrong)
    assert not right.is_error and text(right).startswith("Accepted")
    assert again.is_error and "answered" in text(again)

    run(ctx)
    with ctx.connect() as conn:
        video = db.get_video(conn, vid)
        spent = conn.execute("SELECT COUNT(*) AS n FROM costs WHERE video_id = ? AND stage = 'thumbs' AND provider = 'llm'",
                             (vid,)).fetchone()["n"]
    assert video["state"] == "assembled"
    assert json.loads(video["thumbs_json"])["titles"] == TITLES["titles"]
    assert spent == 0

    status, sheet = call(server, ("status", {"video_id": vid}), ("contact_sheet", {"video_id": vid}))
    assert json.loads(text(status))["waiting_on_the_owner"]["card"] == "render"
    assert "scenes 1–6 of 6" in text(sheet) and sheet.content[1].type == "image"


def test_answer_after_a_restart(ctx):
    """With no check registered (the server restarted), an answer is only checked as JSON; the stage's own check
    then finds what's wrong and asks again with the problems, as a new job."""
    vid = to_titles(ctx)
    with ctx.connect() as conn:
        job = jobs.pending(conn)[0]["id"]
    jobs._checks.clear()
    server = claude_code.make_server(ctx)
    accepted, = call(server, ("answer_job", {"job_id": job, "answer": {**TITLES, "thumb_texts": ["ADRIFT"] * 3}}))
    assert text(accepted).startswith("Accepted")
    run(ctx)
    with ctx.connect() as conn:
        retry = jobs.pending(conn)
    assert len(retry) == 1 and retry[0]["id"] != job and retry[0]["video_id"] == vid
    brief, fixed = call(server, ("take_job", {"job_id": retry[0]["id"]}),
                        ("answer_job", {"job_id": retry[0]["id"], "answer": TITLES}))
    assert "## Your earlier reply" in text(brief) and "## What was wrong with it" in text(brief)
    assert "thumb_text 1 is 1 word" in text(brief)
    assert text(fixed).startswith("Accepted")
    run(ctx)
    with ctx.connect() as conn:
        assert db.get_video(conn, vid)["state"] == "assembled"


def test_jobs_take_and_supersede(ctx):
    with ctx.connect() as conn:
        a, new = jobs.park(conn, "k1", "titles", "the titles", "sys", [{"role": "user", "content": "one"}], {}, None,
                           channel_id="zombie")
        assert new and jobs.park(conn, "k1", "titles", "the titles", "sys", [], {}, None, channel_id="zombie") == (a, False)
        jobs.take(conn, a)
        with pytest.raises(ValueError, match="taken 0 min ago"):
            jobs.take(conn, a)
        jobs.take(conn, a, again=True)
        b, _ = jobs.park(conn, "k2", "titles", "the titles", "sys", [], {}, None, channel_id="zombie")
        assert [j["id"] for j in jobs.pending(conn)] == [b]  # the newer request replaced the older one
        assert jobs.answer(conn, b, "not json")[0].startswith("the reply isn't the JSON")
        assert jobs.answer(conn, b, "{}") == [] and jobs.answer_for(conn, "k2") == (b, "{}")


def test_every_call_is_a_job(ctx, tmp_path):
    """Nothing is left on another path: each of the LLM protocol's calls parks as a job of its own kind."""
    llm, zombie = SessionLLM(ctx.config), ctx.channel("zombie")
    picture = tmp_path / "picture.png"
    picture.write_bytes(zombie.character_ref.read_bytes())
    sheet = lambda d: []  # noqa: E731
    outline = {"hook": "h", "beats": [], "ending": "e"}
    want = {"what": "a gull", "meters": 1, "moves": True}
    calls = {"check_picture": lambda m: llm.check_picture(zombie, "still", {"idx": 1}, [picture], m),
             "map_stage": lambda m: llm.map_stage(zombie, "the flat", picture, m),
             "name_parts": lambda m: llm.name_parts(zombie, picture, ["head"], m),
             "inventory": lambda m: llm.inventory(zombie, "- Rosa: a girl", "1. a line", [], m),
             "scene_sheet": lambda m: llm.scene_sheet(zombie, {"idx": 1}, {}, sheet, m),
             "cast_short": lambda m: llm.cast_short(zombie, {"outline": outline, "notes": [], "lines": "", "people": "", "things": "",
                                                             "built_in": "", "character_format": "", "thing_format": ""}, sheet, m),
             "pick_thing": lambda m: llm.pick_thing(zombie, want, [], picture, [], m),
             "check_thing": lambda m: llm.check_thing(zombie, want, {"clips": {}, "size": [1, 1, 1]}, picture, 1, m),
             "direct": lambda m: llm.direct(zombie, {"outline": outline, "notes": [], "lines": "", "total": 1, "people": "", "things": "",
                                                     "stances": "", "language": "", "example": ""}, sheet, m),
             "check_film": lambda m: llm.check_film(zombie, "1. a shot", picture, m)}
    for name, ask in calls.items():
        meter = type("M", (), {"stopped": False, "channel_id": "zombie", "what": f"the {name}"})()
        with pytest.raises(jobs.NeedsClaude):
            ask(meter)
    with ctx.connect() as conn:
        kinds = {r["what"]: r["kind"] for r in conn.execute("SELECT what, kind FROM claude_jobs")}
    assert kinds == {"the check_picture": "picture", "the map_stage": "map", "the name_parts": "parts",
                     "the inventory": "inventory", "the scene_sheet": "sheet", "the cast_short": "cast",
                     "the pick_thing": "source", "the check_thing": "thing", "the direct": "direct", "the check_film": "film"}
    assert {name for name in vars(LLM) if not name.startswith("_")} == {
        "outline", "script", "revise_visual", "rewrite_line", "titles", "topics", "check_picture", "map_stage",
        "name_parts", "critique", "scene_sheet", "inventory", "cast_short", "pick_thing", "check_thing", "direct",
        "check_film"}  # the writing's jobs are in test_writing.py


def test_endpoint_over_http(ctx):
    app = create_app(ctx, run_engine=False)
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 20
    while not server.started:
        assert time.time() < deadline, "the server didn't start"
        time.sleep(0.05)
    try:
        async def go():
            async with Client(f"http://127.0.0.1:{port}/mcp") as client:
                tools = {t.name for t in (await client.list_tools()).tools}
                return tools, client.instructions, await client.call_tool("jobs", {})
        tools, instructions, listed = asyncio.run(go())
    finally:
        server.should_exit = True
        thread.join(10)
    assert {"jobs", "take_job", "answer_job", "wait", "contact_sheet", "status", "review", "news", "new_video",
            "approve", "flag_scenes", "publish"} <= tools
    assert "no API key is spent" in instructions and "there's no browser app" in instructions
    assert json.loads(text(listed)) == []

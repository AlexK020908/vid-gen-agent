"""The Claude Code session doing Claude's work (BUILD.md phase 17): jobs, the MCP endpoint, titles end to end. $0."""
import asyncio
import json
import socket
import threading
import time

import pytest
import uvicorn
from mcp import Client

from agent.harness import AgentHub
from core import actions, db, jobs
from core.context import make_ctx
from core.engine import Engine
from core.errors import FinalError
from providers.session import SessionLLM
from server import claude_code
from server.app import create_app

TITLES = {"titles": ["I Survived 100 Days on a Raft", "The Raft That Wouldn't Sink", "100 Days Adrift"],
          "thumb_texts": ["100 DAYS ADRIFT", "IT WON'T SINK", "NO LAND"],
          "description": "A stick figure wakes on a raft with no land in sight and twenty litres of water. Over a "
                         "hundred days he learns the sea's rules, loses most of what he has, and finds a way home."}


@pytest.fixture
def ctx(tmp_path):
    ctx = make_ctx(data_dir=tmp_path, overrides={"mode": "stub", "stub": {"scenes": 6}, "engine": {"retry_backoff_s": 0},
                                                 "render": {"engine": "ffmpeg", "pictures": "puppet", "puppet_fps": 4},
                                                 "topics": {"competitors": "off"}})
    ctx.llm = SessionLLM(ctx.config, fallback=ctx.llm)  # titles from the session, the rest from the stub
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
    assert json.loads(text(status))["waiting_on"]["card"] == "render"
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


def test_calls_not_moved_yet_never_reach_the_api(ctx):
    llm = SessionLLM(ctx.config)
    with pytest.raises(FinalError, match="doesn't do the outline yet"):
        llm.outline(ctx.channel("zombie"), "an idea", [], None, None)


def test_endpoint_over_http(ctx):
    app = create_app(ctx, run_engine=False, agents=AgentHub(ctx, online=False))
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
    assert {"jobs", "take_job", "answer_job", "wait", "contact_sheet", "status", "new_video", "flag_scenes"} <= tools
    assert "approve" not in tools and "publish" not in tools
    assert "no API key is spent" in instructions
    assert json.loads(text(listed)) == []

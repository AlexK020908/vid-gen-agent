"""The chat runs the fleet (BUILD.md phase 18): a stub video from idea to scheduled with only MCP tools, review of
each card, news, errors, the permission prompts' list, and the local-only check on /mcp. $0."""
import asyncio
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from mcp import Client

from core import db
from core.config import ROOT
from core.context import make_ctx
from core.engine import Engine
from server import claude_code
from server.app import create_app
from server.tools import ASK


@pytest.fixture
def ctx(tmp_path):
    return make_ctx(data_dir=tmp_path, overrides={"mode": "stub", "stub": {"scenes": 6}, "engine": {"retry_backoff_s": 0},
                                                  "render": {"engine": "ffmpeg"}, "topics": {"competitors": "off"}})


def run(ctx) -> None:
    Engine(ctx).run_until_idle()


def result(ctx, name: str, args: dict | None = None):
    """One tool call over an in-process MCP connection, as the Claude Code session makes it."""
    async def go():
        async with Client(claude_code.make_server(ctx)) as client:
            return await client.call_tool(name, args or {})
    return asyncio.run(go())


def call(ctx, name: str, args: dict | None = None) -> tuple[str, bool]:
    r = result(ctx, name, args)
    return r.content[0].text, bool(r.is_error)


def ok(ctx, name: str, args: dict | None = None) -> str:
    said, err = call(ctx, name, args)
    assert not err, said
    return said


def test_idea_to_scheduled_with_only_tools(ctx):
    started = ok(ctx, "new_video", {"idea": "Day 1 to Day 100 on a raft"})
    vid = int(started.split("#")[1].split(".")[0])
    run(ctx)

    listed = json.loads(ok(ctx, "status"))
    assert listed["channels"][0]["channel"] == "zombie" and not listed["channels"][0]["youtube"]["connected"]
    first = listed["videos"][0]
    assert (first["video_id"], first["state"], first["waiting_on_the_owner"]) == (
        vid, "waiting for outline review", "outline")
    outline = json.loads(ok(ctx, "review", {"video_id": vid}).split("\n", 1)[1])
    assert outline["kind"] == "outline" and outline["beats"][0]["n"] == 1
    assert "The raft tips at dawn." in ok(ctx, "edit_outline", {"video_id": vid, "ops": [
        {"op": "set_hook", "text": "The raft tips at dawn."}]})
    ok(ctx, "approve", {"video_id": vid, "gate": "outline"})
    run(ctx)

    script = ok(ctx, "review", {"video_id": vid})
    summary = json.loads(script.split("\n", 1)[1].rsplit("\n", 1)[0])
    full = Path(summary["full_script"]).read_text(encoding="utf-8")
    assert summary["scenes"] == 6 and "**1.**" in full and "> Picture:" in full
    ok(ctx, "approve", {"video_id": vid, "gate": "script"})
    run(ctx)

    render = result(ctx, "review", {"video_id": vid})
    shown = json.loads(render.content[0].text.split("\n", 1)[1].split("\nThe thumbnails follow")[0])
    assert Path(shown["video_file"]).is_file() and Path(shown["thumbnails"]["1"]).is_file()
    assert len(shown["titles"]) == 3 and len(shown["scenes"]) == 6
    assert [c.type for c in render.content[1:]] == ["image"] * len(shown["thumbnails"])
    said, err = call(ctx, "approve", {"video_id": vid, "gate": "render"})
    assert err and "pick a title" in said
    assert ok(ctx, "pick", {"video_id": vid, "title_idx": 1, "thumb_idx": 2}) == "Picked title option 1 and thumbnail 2."
    assert "The publish card is waiting" in ok(ctx, "approve", {"video_id": vid, "gate": "render"})

    publish = result(ctx, "review", {"video_id": vid})
    card = json.loads(publish.content[0].text.split("\n", 1)[1])
    assert card["kind"] == "publish" and card["privacy"] == "private" and card["goes_public"]
    assert Path(card["thumbnail"]).is_file() and publish.content[1].type == "image"
    ok(ctx, "update_publish", {"video_id": vid, "tags": ["raft", "survival"]})
    assert "practice mode" in ok(ctx, "publish", {"video_id": vid})
    run(ctx)

    info = json.loads(ok(ctx, "status", {"video_id": vid}))
    assert info["state"] == "scheduled" and info["youtube_id"] == f"stub-{vid}" and info["waiting_on_the_owner"] is None
    news = json.loads(ok(ctx, "news"))["news"]
    texts = [n["text"] for n in news]
    assert any(t.startswith(f"Started video #{vid}") for t in texts) and "Outline ready for review." in texts
    assert any("Scheduled on YouTube as stub-" in (t or "") for t in texts)
    assert {n.get("card") for n in news} >= {"outline", "script", "render", "publish"}
    assert ok(ctx, "news") == "Nothing new since the last look."
    assert json.loads(ok(ctx, "status"))["news_unseen"] == 0


def test_flags_and_errors_come_back_as_error_results(ctx):
    vid = int(ok(ctx, "new_video", {"idea": "Flags"}).split("#")[1].split(".")[0])
    run(ctx)
    ok(ctx, "approve", {"video_id": vid, "gate": "outline"})
    run(ctx)
    ok(ctx, "approve", {"video_id": vid, "gate": "script"})
    run(ctx)
    said, err = call(ctx, "flag_scenes", {"video_id": vid, "idxs": [2], "kind": "narration"})
    assert err and "how the line should change" in said
    assert "Sent scenes 2, 4 back for new pictures" in ok(ctx, "flag_scenes", {"video_id": vid, "idxs": [2, 4],
                                                                                "kind": "visual", "note": "darker"})
    run(ctx)
    assert json.loads(ok(ctx, "status", {"video_id": vid}))["state"] == "assembled"

    assert call(ctx, "review", {"video_id": 999}) == ("there's no video #999", True)
    said, err = call(ctx, "approve", {"video_id": vid, "gate": "outline"})
    assert err and said == f"video {vid} is assembled; this needs it to be outlined"
    with ctx.connect() as conn:
        conn.execute("UPDATE videos SET state = 'failed', error = 'ffmpeg exited 1', resume_state = 'assembled' "
                     "WHERE id = ?", (vid,))
    ctx.events.emit("stage_failed", vid)
    failed = json.loads(ok(ctx, "review", {"video_id": vid}).split("\n", 1)[1])
    assert failed["kind"] == "error" and failed["error"] == "ffmpeg exited 1" and failed["blocked_scenes"] == []
    assert ok(ctx, "retry", {"video_id": vid}) == "Retrying; the video is waiting for render review again."
    assert json.loads(ok(ctx, "status", {"video_id": vid}))["state"] == "assembled"


def test_what_was_posted_before_the_chat_counts_as_seen(ctx):
    with ctx.connect() as conn:
        conn.execute("ALTER TABLE messages DROP COLUMN seen_at")  # a database from before phase 18
        conn.execute("""INSERT INTO messages (thread_id, role, text, created_at)
                        VALUES ((SELECT id FROM threads LIMIT 1), 'system', 'old news', 1)""")
    db.init(ctx.config.db_path)
    with ctx.connect() as conn:
        assert conn.execute("SELECT seen_at FROM messages WHERE text = 'old news'").fetchone()[0] == 1
    assert ok(ctx, "news") == "Nothing new since the last look."


def test_the_permission_prompts_cover_what_spends_or_changes_youtube(ctx):
    """claude-settings.json goes in .claude/settings.json (here and in the workspace folder): Claude Code asks the
    owner before each of these, even in auto mode."""
    settings = json.loads((ROOT / "claude-settings.json").read_text(encoding="utf-8"))["permissions"]
    assert settings["allow"] == ["mcp__stickfleet__*"]
    assert settings["ask"] == [f"mcp__stickfleet__{name}" for name in ASK]
    async def names():
        async with Client(claude_code.make_server(ctx)) as client:
            return {t.name for t in (await client.list_tools()).tools}
    assert set(ASK) <= asyncio.run(names())


def test_mcp_is_local_only(ctx):
    with TestClient(create_app(ctx, run_engine=False), base_url="http://localhost") as http:
        assert http.post("/mcp", headers={"Host": "evil.example"}).status_code == 403
        assert http.post("/mcp", headers={"Origin": "https://evil.example"}).status_code == 403
        assert http.get("/api/channels").status_code == 404  # the browser's API is gone

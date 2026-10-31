"""The chat agent with a fake SDK client: tools, thread binding, the path guard, confirm cards, turns, resume.

FakeClient replays scripted turns but runs the real tools, the real PreToolUse hook and the real
can_use_tool callback, so everything except the model itself is exercised. No network, $0.
"""
import asyncio
import json
import os
import re
import shutil
import threading
import time
import uuid
from pathlib import Path

import jsonschema
import pytest
from claude_agent_sdk import (
    AssistantMessage,
    PermissionResultDeny,
    ResultMessage,
    StreamEvent,
    SystemMessage,
    TextBlock,
    ToolPermissionContext,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)
from dotenv import load_dotenv
from fastapi.testclient import TestClient

from agent.harness import AgentHub, allowed_path, path_guard
from agent.tools import build_tools, load_thread
from core import actions, cards
from core.config import ROOT
from core.context import make_ctx
from core.engine import Engine
from server.app import create_app

load_dotenv(ROOT / ".env")  # only the live test uses the key; every other test injects a fake client

FLEET_TOOLS = {"new_video", "status", "show", "revise", "regenerate", "edit_outline", "flag_scenes", "edit_scene",
               "pick", "set_schedule", "update_publish", "retry", "update_video", "stop_writing"}
HOME_TOOLS = {"topics", "start_topic", "dismiss_topic", "suggest_topics"}  # only in a channel's home thread


# --- fake SDK client -------------------------------------------------------------------

class Fake:
    """Makes FakeClients. Turns are shared: each turn any client runs takes the next script."""

    def __init__(self, *turns, cost=0.02, totals=None):
        self.turns = list(turns)
        self.cost = cost
        self.totals = totals if totals is not None else {}  # session id → spend, as the CLI restores on resume
        self.clients: list[FakeClient] = []
        self.prompts: list[str] = []
        self.results: list[tuple[str, str, bool]] = []
        self.done = 0
        self.active = 0
        self.max_active = 0

    def __call__(self, options, tools):
        client = FakeClient(self, options, tools)
        self.clients.append(client)
        return client


class FakeClient:
    def __init__(self, fake: Fake, options, tools):
        self.fake, self.options = fake, options
        self.tools = {t.name: t for t in tools}
        self.session_id = options.resume or f"session-{len(fake.clients) + 1}"
        self.total = fake.totals.get(options.resume, 0.0) if options.resume else 0.0
        self.interrupted = threading.Event()

    async def connect(self):
        pass

    async def disconnect(self):
        pass

    async def query(self, prompt):
        self.fake.prompts.append(prompt)

    async def interrupt(self):
        self.interrupted.set()

    async def receive_response(self):
        steps = self.fake.turns.pop(0) if self.fake.turns else [("text", "ok")]
        self.fake.active += 1
        self.fake.max_active = max(self.fake.max_active, self.fake.active)
        try:
            yield SystemMessage("init", {"session_id": self.session_id})
            for step in steps:
                mid = f"msg_{uuid.uuid4().hex[:8]}"
                if step[0] == "text":
                    yield AssistantMessage([TextBlock(step[1])], "fake", message_id=mid)
                elif step[0] == "stream":  # text deltas, then the full message the CLI sends after them
                    yield StreamEvent("u", self.session_id, {"type": "message_start", "message": {"id": mid}})
                    yield StreamEvent("u", self.session_id, {"type": "content_block_start", "index": 0,
                                                             "content_block": {"type": "text", "text": ""}})
                    for piece in step[1]:
                        yield StreamEvent("u", self.session_id, {"type": "content_block_delta", "index": 0,
                                                                 "delta": {"type": "text_delta", "text": piece}})
                    yield StreamEvent("u", self.session_id, {"type": "content_block_stop", "index": 0})
                    yield AssistantMessage([TextBlock("".join(step[1]))], "fake", message_id=mid)
                elif step[0] == "tool":
                    _, name, args = step
                    tid = f"toolu_{mid}"
                    yield AssistantMessage([ToolUseBlock(tid, name, args)], "fake", message_id=mid)
                    text, is_error = await self._call(tid, name, args)
                    self.fake.results.append((name, text, is_error))
                    yield UserMessage([ToolResultBlock(tid, text, is_error)])
                elif step[0] == "wait":  # hold the turn open until the test releases it or Stop is clicked
                    gate = step[1]
                    await asyncio.to_thread(lambda: _wait_any(gate, self.interrupted))
                if self.interrupted.is_set():
                    break
            self.total += self.fake.cost
            self.fake.totals[self.session_id] = self.total
            stopped = self.interrupted.is_set()
            yield ResultMessage(subtype="error_during_execution" if stopped else "success", duration_ms=1,
                                duration_api_ms=1, is_error=stopped, num_turns=1, session_id=self.session_id,
                                total_cost_usd=self.total,
                                terminal_reason="aborted_streaming" if stopped else "completed")
            self.fake.done += 1  # runs once the harness has handled the result
        finally:
            self.fake.active -= 1

    async def _call(self, tid, name, args):
        if name.startswith("mcp__fleet__"):
            tool = self.tools[name.removeprefix("mcp__fleet__")]
            try:
                jsonschema.validate(args, tool.input_schema)  # the SDK validates before calling the handler
            except jsonschema.ValidationError as e:
                return f"Input validation error: {e.message}", True
            out = await tool.handler(args)
            return out["content"][0]["text"], bool(out.get("is_error"))
        assert name in self.options.tools, f"{name} is not loaded"
        for matcher in self.options.hooks["PreToolUse"]:
            if re.fullmatch(matcher.matcher, name):
                for hook in matcher.hooks:
                    out = await hook({"hook_event_name": "PreToolUse", "tool_name": name, "tool_input": args},
                                     tid, {"signal": None})
                    spec = out.get("hookSpecificOutput", {})
                    if spec.get("permissionDecision") == "deny":
                        return spec["permissionDecisionReason"], True
        if name not in self.options.allowed_tools:
            verdict = await self.options.can_use_tool(name, args, ToolPermissionContext(tool_use_id=tid))
            if isinstance(verdict, PermissionResultDeny):
                return verdict.message, True
        path = Path(self.options.cwd, args["file_path"])
        if name == "Read":
            return path.read_text(encoding="utf-8"), False
        text = path.read_text(encoding="utf-8")
        path.write_text(text.replace(args["old_string"], args["new_string"], 1), encoding="utf-8")
        return "The file has been updated.", False


def _wait_any(*events, timeout=10.0):
    end = time.time() + timeout
    while time.time() < end and not any(e.is_set() for e in events):
        time.sleep(0.01)


# --- fixtures and helpers ------------------------------------------------------------------

@pytest.fixture
def ctx(tmp_path):
    # A copy of the project, so Edit tests never touch the real prompts/.
    root = tmp_path / "project"
    root.mkdir()
    shutil.copy(ROOT / "stickfleet.yaml", root)
    for name in ("channels", "prompts"):
        shutil.copytree(ROOT / name, root / name)
    return make_ctx(root=root, data_dir=tmp_path / "data",
                    overrides={"mode": "stub", "stub": {"scenes": 6}, "engine": {"retry_backoff_s": 0},
                               "agent": {"comment_on_gates": False}, "render": {"engine": "ffmpeg"}, "topics": {"competitors": "off"}})


def serve(ctx, fake):
    app = create_app(ctx, run_engine=False, agents=AgentHub(ctx, make_client=fake))
    return TestClient(app, base_url="http://localhost")


def wait_until(fn, timeout=10.0, what="condition"):
    end = time.time() + timeout
    while time.time() < end:
        value = fn()
        if value:
            return value
        time.sleep(0.02)
    raise AssertionError(f"timed out waiting for {what}")


def settle(client, thread_id, fake, turns):
    wait_until(lambda: fake.done >= turns, what=f"{turns} turns")
    wait_until(lambda: not thread_row(client, thread_id)["running"], what="turn to end")


def thread_row(client, thread_id):
    return next(t for t in client.get("/api/threads").json() if t["id"] == thread_id)


def messages(client, thread_id):
    return client.get(f"/api/threads/{thread_id}/messages").json()


def chat(client, thread_id, text):
    r = client.post(f"/api/threads/{thread_id}/chat", json={"text": text})
    assert r.status_code == 200, r.text


def home_id(ctx):
    with ctx.connect() as conn:
        return cards.home_thread_id(conn, "zombie")


def video_thread_id(ctx, vid):
    with ctx.connect() as conn:
        return cards.thread_id(conn, vid)


def call(tools, name, args):
    out = asyncio.run(next(t for t in tools if t.name == name).handler(args))
    return out["content"][0]["text"], bool(out.get("is_error"))


def to_render_review(ctx, vid):
    engine = Engine(ctx)
    engine.run_until_idle()
    actions.approve(ctx, vid, "outline")
    engine.run_until_idle()
    if actions.status(ctx, video_id=vid)["state"] == "scripted":
        actions.approve(ctx, vid, "script")
        engine.run_until_idle()
    assert actions.status(ctx, video_id=vid)["state"] == "assembled"


# --- tools ---------------------------------------------------------------------------------------

def test_no_gate_verbs_and_only_read_and_edit(ctx):
    vid = actions.new_video(ctx, "zombie", "Tools")
    for thread_id, expected in ((home_id(ctx), FLEET_TOOLS | HOME_TOOLS), (video_thread_id(ctx, vid), FLEET_TOOLS)):
        thread = load_thread(ctx, thread_id)
        names = {t.name for t in build_tools(ctx, thread)}
        assert names == expected
        assert not [n for n in names if n.startswith(("approve", "publish", "request_publish", "delete"))]
        options = AgentHub(ctx, online=False).options(thread, build_tools(ctx, thread), None)
        assert options.tools == ["Read", "Edit"]  # no Bash, Write, web or Task
        assert "Edit" not in options.allowed_tools and "Read" in options.allowed_tools
        assert options.setting_sources == [] and options.strict_mcp_config


def test_tools_bind_to_their_thread(ctx):
    vid = actions.new_video(ctx, "zombie", "Binding")
    to_render_review(ctx, vid)

    video_tools = build_tools(ctx, load_thread(ctx, video_thread_id(ctx, vid)))
    flag = next(t for t in video_tools if t.name == "flag_scenes")
    assert "video_id" not in flag.input_schema["properties"]  # a video thread can only touch its own video
    text, err = call(video_tools, "flag_scenes", {"idxs": [2], "kind": "visual", "note": "darker"})
    assert not err and "2" in text
    assert actions.status(ctx, video_id=vid)["state"] == "generating"

    home_tools = build_tools(ctx, load_thread(ctx, home_id(ctx)))
    text, err = call(home_tools, "status", {})
    assert not err and json.loads(text)["videos"][0]["id"] == vid
    text, err = call(home_tools, "retry", {})
    assert err and "which video" in text
    with ctx.connect() as conn:  # a video on another channel is out of reach from this home thread
        conn.execute("INSERT INTO channels (id, name) VALUES ('other', 'Other')")
        other = conn.execute("INSERT INTO videos (channel_id, state, created_at, updated_at) "
                             "VALUES ('other', 'failed', 0, 0)").lastrowid
    text, err = call(home_tools, "retry", {"video_id": other})
    assert err and f"no video #{other}" in text
    with ctx.connect() as conn:
        assert conn.execute("SELECT state FROM videos WHERE id = ?", (other,)).fetchone()["state"] == "failed"


def test_action_errors_come_back_as_error_results(ctx):
    vid = actions.new_video(ctx, "zombie", "Errors")
    tools = build_tools(ctx, load_thread(ctx, video_thread_id(ctx, vid)))
    text, err = call(tools, "revise", {"gate": "outline", "note": "open on the storm"})
    assert err and "is new; this needs it to be outlined" in text
    Engine(ctx).run_until_idle()
    text, err = call(tools, "edit_outline", {"ops": [{"op": "set_hook"}]})
    assert err and "missing field 'text'" in text
    text, err = call(tools, "edit_outline", {"ops": [{"op": "move_beat", "beat": 2, "to": 1}]})
    assert not err and '"n": 1' in text
    text, err = call(tools, "status", {})
    status = json.loads(text)
    assert status["state"] == "outlined" and status["waiting_on"]["card"] == "outline"


def test_path_guard(ctx):
    root = ctx.config.root
    hook = path_guard(root)

    def decision(path):
        out = asyncio.run(hook({"tool_input": {"file_path": path}}, None, {"signal": None}))
        return out.get("hookSpecificOutput", {}).get("permissionDecision", "allow")

    assert decision("prompts/outline.md") == "allow"
    assert decision(str(root / "prompts" / "outline.md")) == "allow"
    assert decision(str(root / "channels" / "zombie.yaml")) == "allow"
    assert decision("prompts/../core/db.py") == "deny"
    assert decision("../plan.md") == "deny"
    assert decision(str(root / "prompts" / ".." / "stickfleet.yaml")) == "deny"
    assert decision(str(root / "core" / "db.py")) == "deny"
    assert decision(str(root / "prompts_backup" / "x.md")) == "deny"  # a name that only starts with prompts
    assert decision(str(root / "prompts")) == "deny"
    assert decision("C:/Windows/win.ini") == "deny"
    assert decision("") == "deny"
    assert not allowed_path(root, None)


# --- turns through the server ------------------------------------------------------------------

def test_turn_streams_text_and_posts_tool_lines(ctx):
    fake = Fake([("tool", "mcp__fleet__new_video", {"idea": "Day 1 to Day 30 in a sunken submarine"}),
                 ("stream", ["Started ", "**#1**", ", writing the outline now."])])
    home = home_id(ctx)
    with serve(ctx, fake) as client:
        chat(client, home, "start a video about a submarine")
        settle(client, home, fake, 1)
        msgs = messages(client, home)

    assert [m["role"] for m in msgs] == ["user", "tool", "system", "assistant"]
    assert msgs[1]["card"] == {"kind": "tool", "name": "new_video", "detail": "Day 1 to Day 30 in a sunken submarine",
                               "error": None}
    assert msgs[2]["text"].startswith("Started video #1")
    assert msgs[3]["text"] == "Started **#1**, writing the outline now."  # streamed, not posted twice
    assert fake.prompts[0].startswith("<now>") and fake.prompts[0].endswith("start a video about a submarine")
    assert actions.status(ctx, video_id=1)["state"] == "new"
    thread = load_thread(ctx, home)
    assert thread.sdk_session_id == "session-1" and thread.agent_cost_usd == pytest.approx(0.02)


def test_session_resumes_and_cost_carries_over_a_restart(ctx):
    vid = actions.new_video(ctx, "zombie", "Resume")
    tid = video_thread_id(ctx, vid)
    first = Fake([("text", "hello")])
    with serve(ctx, first) as client:
        chat(client, tid, "hi")
        settle(client, tid, first, 1)
    assert load_thread(ctx, tid).sdk_session_id == "session-1"

    second = Fake([("text", "welcome back")], totals=first.totals)
    with serve(ctx, second) as client:
        chat(client, tid, "still there?")
        settle(client, tid, second, 1)
    assert second.clients[0].options.resume == "session-1"
    assert load_thread(ctx, tid).agent_cost_usd == pytest.approx(0.04)  # restored 0.02 + this turn's 0.02
    assert actions.status(ctx, video_id=vid)["cost_usd"] == pytest.approx(0.04)


def test_messages_mid_turn_are_queued_into_the_next_turn(ctx):
    release = threading.Event()
    fake = Fake([("wait", release), ("text", "first")], [("text", "second")])
    vid = actions.new_video(ctx, "zombie", "Queue")
    tid = video_thread_id(ctx, vid)
    with serve(ctx, fake) as client:
        chat(client, tid, "one")
        wait_until(lambda: fake.active == 1, what="first turn")
        assert thread_row(client, tid)["running"]
        chat(client, tid, "two")
        chat(client, tid, "three")
        time.sleep(0.2)
        assert len(fake.prompts) == 1
        release.set()
        settle(client, tid, fake, 2)
        texts = [m["text"] for m in messages(client, tid) if m["role"] == "assistant"]

    assert fake.max_active == 1 and len(fake.prompts) == 2
    assert fake.prompts[1].endswith("two\n\nthree")
    assert texts == ["first", "second"]


def test_stop_interrupts_and_drops_the_queue(ctx):
    never = threading.Event()
    fake = Fake([("wait", never), ("text", "should not appear")])
    vid = actions.new_video(ctx, "zombie", "Stop")
    tid = video_thread_id(ctx, vid)
    with serve(ctx, fake) as client:
        chat(client, tid, "do a long thing")
        wait_until(lambda: fake.active == 1, what="turn")
        chat(client, tid, "and then this")
        assert client.post(f"/api/threads/{tid}/stop").status_code == 200
        settle(client, tid, fake, 1)
        msgs = messages(client, tid)
    assert fake.clients[0].interrupted.is_set() and len(fake.prompts) == 1
    assert msgs[-1]["role"] == "system" and msgs[-1]["text"] == "Stopped."
    assert not any(m["text"] == "should not appear" for m in msgs)


def test_edit_needs_a_confirm_card(ctx):
    path = ctx.config.root / "prompts" / "outline.md"  # the fixture's copy, not the real prompt
    path.write_text("# Outline prompt (placeholder)\n\nWrite an outline.\n", encoding="utf-8")
    original = path.read_text(encoding="utf-8")
    fake = Fake(
        [("tool", "Read", {"file_path": str(path)}),
         ("tool", "Edit", {"file_path": str(path), "old_string": "(placeholder)", "new_string": "(draft)"}),
         ("text", "Changed it.")],
        [("tool", "Edit", {"file_path": str(path), "old_string": "(draft)", "new_string": "(final)"}),
         ("text", "Okay, left it.")],
        [("tool", "Edit", {"file_path": "core/db.py", "old_string": "a", "new_string": "b"})],
    )
    home = home_id(ctx)

    def confirm_card():
        found = [m for m in messages(client, home)
                 if m["card"] and m["card"]["kind"] == "confirm" and m["card_status"] == "active"]
        return found[0] if found else None

    with serve(ctx, fake) as client:
        chat(client, home, "call the outline prompt a draft")
        card = wait_until(confirm_card, what="confirm card")
        assert "-# Outline prompt (placeholder)" in card["card"]["diff"]
        assert "+# Outline prompt (draft)" in card["card"]["diff"]
        assert card["card"]["path"] == "prompts/outline.md"
        assert path.read_text(encoding="utf-8") == original  # nothing changes before Approve
        assert client.post(f"/api/confirm/{card['id']}", json={"allow": True}).status_code == 200
        settle(client, home, fake, 1)
        assert "(draft)" in path.read_text(encoding="utf-8")

        chat(client, home, "now call it final")
        card = wait_until(confirm_card, what="second confirm card")
        assert client.post(f"/api/confirm/{card['id']}", json={"allow": False}).status_code == 200
        settle(client, home, fake, 2)
        assert "(draft)" in path.read_text(encoding="utf-8")
        again = client.post(f"/api/confirm/{card['id']}", json={"allow": True})
        assert again.status_code == 409

        chat(client, home, "edit the code")
        settle(client, home, fake, 3)
        msgs = messages(client, home)

    statuses = [m["card_status"] for m in msgs if m["card"] and m["card"]["kind"] == "confirm"]
    assert statuses == ["approved", "denied"]  # the edit outside prompts/ never reached a confirm card
    tool_errors = [m["card"]["error"] for m in msgs if m["role"] == "tool"]
    assert tool_errors[:2] == [None, None]
    assert "denied" in tool_errors[2] and "Only files under prompts/" in tool_errors[3]


def test_gate_comment_after_a_new_card_but_not_a_repost(ctx):
    ctx.config.agent["comment_on_gates"] = True
    fake = Fake([("text", "Strong hook.\nBeat 3 drags; cut it.")])
    with serve(ctx, fake) as client:
        created = client.post("/api/videos", json={"channel_id": "zombie", "idea": "Gate comment"}).json()
        Engine(ctx).run_until_idle()
        tid = created["thread_id"]
        settle(client, tid, fake, 1)
        client.post(f"/api/videos/{created['video_id']}/edit_outline",
                    json={"ops": [{"op": "set_hook", "text": "The hatch won't open."}]})
        time.sleep(0.3)
        msgs = messages(client, tid)
    assert len(fake.prompts) == 1 and "two-line take" in fake.prompts[0] and '"card": "outline"' in fake.prompts[0]
    card = next(m for m in msgs if m["card"] and m["card"]["kind"] == "outline")
    comment = next(m for m in msgs if m["role"] == "assistant")
    assert comment["id"] > card["id"] and comment["text"].startswith("Strong hook.")


def test_budget_used_up(ctx):
    vid = actions.new_video(ctx, "zombie", "Budget")
    tid = video_thread_id(ctx, vid)
    with ctx.connect() as conn:
        conn.execute("UPDATE threads SET agent_cost_usd = ? WHERE id = ?",
                     (ctx.config.agent["budget_usd_per_session"], tid))
    fake = Fake()
    with serve(ctx, fake) as client:
        chat(client, tid, "hello?")
        wait_until(lambda: any("budget" in (m["text"] or "") for m in messages(client, tid)), what="budget notice")
    assert fake.clients == []


@pytest.mark.live
@pytest.mark.skipif(not os.environ.get("ANTHROPIC_API_KEY"), reason="needs ANTHROPIC_API_KEY")
def test_live_agent_starts_a_video(ctx):
    home = home_id(ctx)
    with TestClient(create_app(ctx, run_engine=False), base_url="http://localhost") as client:
        chat(client, home, "Start a video about surviving 30 days in a flooded subway station.")
        wait_until(lambda: actions.status(ctx, channel_id="zombie")["videos"], timeout=180, what="a new video")
        wait_until(lambda: not thread_row(client, home)["running"], timeout=180, what="turn to end")
    assert load_thread(ctx, home).sdk_session_id

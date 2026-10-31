"""Runs the chat agent: one Claude Agent SDK client per thread.

Each thread gets a worker task that owns its client from connect to disconnect (the SDK needs a client to
stay in the task that connected it) and runs queued messages one turn at a time. Messages that arrive
mid-turn are queued and sent together as the next turn.

Permissions: the fleet tools and Read are allowed outright; Edit is not, so the SDK asks `can_use_tool`,
which posts a confirm card with the diff and waits for the person's Approve or Deny. A PreToolUse hook
denies Read and Edit anywhere outside prompts/ and channels/. Bash, Write, web and Task are not loaded.
"""
from __future__ import annotations

import asyncio
import difflib
import json
import logging
import os
import time
import warnings
from pathlib import Path
from typing import Any, Callable

from claude_agent_sdk import (
    AssistantMessage,
    CanUseToolShadowedWarning,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    HookMatcher,
    PermissionResultAllow,
    PermissionResultDeny,
    ResultMessage,
    StreamEvent,
    SystemMessage,
    TextBlock,
    ToolPermissionContext,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
    create_sdk_mcp_server,
)

from agent import tools as fleet
from core import cards, costs, db
from core.errors import ActionError
from core.events import Event

log = logging.getLogger("stickfleet.agent")

# Read and the fleet tools are allowed outright on purpose; only Edit should reach can_use_tool.
warnings.filterwarnings("ignore", category=CanUseToolShadowedWarning)

SYSTEM_PROMPT = Path(__file__).with_name("system.md")
EDITABLE_DIRS = ("prompts", "channels")
COMMENT_GATES = ("outline", "script", "render")
STREAM_FLUSH_S = 0.25
OFFLINE = ("The assistant is offline: add ANTHROPIC_API_KEY to .env and restart `run.py serve`. "
           "The card buttons still work.")
GATE_COMMENT = """A new {gate} card was just posted for the person to review. Its content:

{card}

Give a two-line take, no preamble and no tools. Line 1: the strongest thing about it. Line 2: the weakest \
beat or scene, and what you'd change."""

MakeClient = Callable[[ClaudeAgentOptions, list], Any]


def _default_client(options: ClaudeAgentOptions, tools: list) -> ClaudeSDKClient:
    return ClaudeSDKClient(options)


# --- file access ----------------------------------------------------------------------

def allowed_path(root: Path, raw: str | None) -> bool:
    """True if `raw` (relative to root, or absolute) resolves inside prompts/ or channels/."""
    if not raw:
        return False
    full = os.path.normcase(os.path.realpath(Path(root, raw)))
    for name in EDITABLE_DIRS:
        base = os.path.normcase(os.path.realpath(root / name))
        if full.startswith(base + os.sep):
            return True
    return False


def path_guard(root: Path):
    """PreToolUse hook for Read and Edit."""
    async def hook(input_data: dict, tool_use_id: str | None, context: Any) -> dict:
        if allowed_path(root, (input_data.get("tool_input") or {}).get("file_path")):
            return {}
        return {"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": "Only files under prompts/ and channels/ can be read or edited.",
        }}
    return hook


def confirm_card(root: Path, tool_name: str, tool_input: dict) -> dict:
    """A confirm card for an Edit: a unified diff of the whole file when the edit applies, else of the strings."""
    raw = str(tool_input.get("file_path", ""))
    path = Path(root, raw)
    try:
        rel = path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        rel = raw
    old, new = tool_input.get("old_string", ""), tool_input.get("new_string", "")
    try:
        before = path.read_text(encoding="utf-8")
    except OSError:
        before = None
    if before is not None and old and old in before:
        after = before.replace(old, new) if tool_input.get("replace_all") else before.replace(old, new, 1)
    else:
        before, after = old, new
    diff = "\n".join(difflib.unified_diff(before.splitlines(), after.splitlines(), f"a/{rel}", f"b/{rel}",
                                          lineterm=""))
    return {"kind": "confirm", "tool": tool_name, "title": f"Edit {rel}", "path": rel, "diff": diff,
            "input": tool_input}


def _result_text(block: ToolResultBlock) -> str:
    if isinstance(block.content, str):
        return block.content
    return " ".join(c.get("text", "") for c in block.content or [] if isinstance(c, dict))


# --- one thread ---------------------------------------------------------------------------

class ThreadAgent:
    def __init__(self, hub: AgentHub, thread_id: int) -> None:
        self.hub, self.ctx, self.thread_id = hub, hub.ctx, thread_id
        self.video_id = fleet.load_thread(self.ctx, thread_id).video_id
        self.inbox: asyncio.Queue[str] = asyncio.Queue()
        self.running = False
        self.stopping = False
        self.client: Any = None
        self.resumed = False
        self.cost_base = 0.0
        self._reset_stream()
        self.task = asyncio.create_task(self._work(), name=f"agent-thread-{thread_id}")

    # --- turns ---

    async def _work(self) -> None:
        try:
            while True:
                prompts = [await self.inbox.get()]
                while not self.inbox.empty():
                    prompts.append(self.inbox.get_nowait())
                await self._turn("\n\n".join(prompts))
        finally:
            await self._disconnect()

    async def _turn(self, text: str) -> None:
        thread = fleet.load_thread(self.ctx, self.thread_id)
        if thread.agent_cost_usd >= self.hub.budget:
            self._post("system", f"This thread's assistant budget (${self.hub.budget:.2f}) is used up. The card "
                                 "buttons still work; raise agent.budget_usd_per_session in stickfleet.yaml to go on.")
            return
        self.stopping = False
        self._set_running(True)
        try:
            for attempt in (1, 2):
                self._reset_stream()
                try:
                    await self._run(thread, f"<now>{fleet.describe(self.ctx, thread)}</now>\n\n{text}")
                    return
                except Exception as e:
                    stale_resume = self.resumed and not self.output_seen
                    await self._disconnect()
                    if attempt == 1 and stale_resume:
                        # The saved session is gone (e.g. ~/.claude was cleared): start a fresh one.
                        log.warning("thread %s: resume failed (%s); starting a new session", self.thread_id, e)
                        self._save_session(None)
                        thread = fleet.load_thread(self.ctx, self.thread_id)
                        continue
                    log.exception("thread %s: agent turn failed", self.thread_id)
                    self._post("system", f"The assistant hit an error and stopped: {e}")
                    return
        finally:
            self._flush(final=True)
            self._set_running(False)

    async def _run(self, thread: fleet.Thread, prompt: str) -> None:
        if self.client is None:
            tools = fleet.build_tools(self.ctx, thread)
            options = self.hub.options(thread, tools, self._can_use_tool)
            client = self.hub.make_client(options, tools)
            await client.connect()
            self.client, self.resumed = client, options.resume is not None
            # A resumed session reports its earlier spend in total_cost_usd; a fresh one starts at zero.
            self.cost_base = 0.0 if self.resumed else thread.agent_cost_usd
        await self.client.query(prompt)
        async for msg in self.client.receive_response():
            self._on_message(msg)

    async def _disconnect(self) -> None:
        client, self.client = self.client, None
        if client is not None:
            try:
                await client.disconnect()
            except Exception:
                log.exception("thread %s: disconnect failed", self.thread_id)

    async def stop(self) -> None:
        while not self.inbox.empty():
            self.inbox.get_nowait()
        if self.running and self.client is not None:
            self.stopping = True
            await asyncio.wait_for(self.client.interrupt(), timeout=10)

    # --- what comes back ---

    def _on_message(self, msg: Any) -> None:
        if isinstance(msg, StreamEvent):
            self._on_stream(msg.event)
        elif isinstance(msg, SystemMessage):
            if msg.subtype == "init" and msg.data.get("session_id"):
                self._save_session(msg.data["session_id"])
        elif isinstance(msg, AssistantMessage):
            if msg.parent_tool_use_id:
                return
            self.output_seen = True
            streamed = msg.message_id in self.streamed or (msg.message_id is None and self.streamed)
            for block in msg.content:
                if isinstance(block, TextBlock) and not streamed and block.text.strip():
                    self._post("assistant", block.text.strip())
                elif isinstance(block, ToolUseBlock):
                    self._tool_line(block)
        elif isinstance(msg, UserMessage) and isinstance(msg.content, list):
            for block in msg.content:
                if isinstance(block, ToolResultBlock) and block.is_error:
                    self._tool_failed(block)
        elif isinstance(msg, ResultMessage):
            self._on_result(msg)

    def _reset_stream(self) -> None:
        self.output_seen = False
        self.streamed: set[str] = set()
        self.stream_id: str | None = None
        self.text = ""
        self.text_row: int | None = None
        self.flushed = ""
        self.flushed_at = 0.0
        self.tool_rows: dict[str, tuple[int, dict]] = {}

    def _on_stream(self, ev: dict) -> None:
        kind = ev.get("type")
        if kind == "message_start":
            self.stream_id = (ev.get("message") or {}).get("id")
        elif kind == "content_block_start":
            self._flush(final=True)
            self.text, self.text_row, self.flushed = "", None, ""
        elif kind == "content_block_delta" and (ev.get("delta") or {}).get("type") == "text_delta":
            self.output_seen = True
            self.text += ev["delta"].get("text", "")
            if self.stream_id:
                self.streamed.add(self.stream_id)
            self._flush()
        elif kind == "content_block_stop":
            self._flush(final=True)

    def _flush(self, final: bool = False) -> None:
        """Post or update the streaming assistant message, at most every STREAM_FLUSH_S unless final."""
        text = self.text.strip()
        if not text or text == self.flushed:
            return
        if self.text_row is None:
            self.text_row = self._post("assistant", text)["id"]
        elif final or time.monotonic() - self.flushed_at >= STREAM_FLUSH_S:
            with self.ctx.connect() as conn:
                cards.update_text(self.ctx, conn, self.text_row, text)
        else:
            return
        self.flushed, self.flushed_at = text, time.monotonic()

    def _tool_line(self, block: ToolUseBlock) -> None:
        name, detail = fleet.describe_call(block.name, block.input, self.ctx.config.root)
        card = {"kind": "tool", "name": name, "detail": detail, "error": None}
        row = self._post("tool", f"{name} {detail}".strip(), card=card, status=None)
        self.tool_rows[block.id] = (row["id"], card)

    def _tool_failed(self, block: ToolResultBlock) -> None:
        if block.tool_use_id not in self.tool_rows:
            return
        row_id, card = self.tool_rows[block.tool_use_id]
        card = {**card, "error": _result_text(block).strip()[:300] or "failed"}
        with self.ctx.connect() as conn:
            cards.update_card(self.ctx, conn, row_id, card)

    def _on_result(self, msg: ResultMessage) -> None:
        if msg.session_id:
            self._save_session(msg.session_id)
        if msg.total_cost_usd is not None:
            self._record_cost(self.cost_base + msg.total_cost_usd)
        if self.stopping or msg.terminal_reason in ("aborted_streaming", "aborted_tools"):
            self._post("system", "Stopped.")
        elif msg.subtype == "error_max_budget_usd":
            self._post("system", f"Stopped: this thread's assistant budget (${self.hub.budget:.2f}) is used up.")
        elif msg.is_error:
            detail = "; ".join(msg.errors or []) or msg.result or msg.subtype
            self._post("system", f"The assistant hit an error: {detail}")

    def _record_cost(self, session_total: float) -> None:
        """Keep the highest session total seen, and log the increase against the video."""
        with self.ctx.connect() as conn, db.tx(conn):
            row = conn.execute("SELECT agent_cost_usd FROM threads WHERE id = ?", (self.thread_id,)).fetchone()
            delta = session_total - row["agent_cost_usd"]
            if delta <= 1e-9:
                return
            conn.execute("UPDATE threads SET agent_cost_usd = ? WHERE id = ?", (session_total, self.thread_id))
            costs.log(conn, self.video_id, "agent", "claude", delta)

    # --- permission prompt: Edit ---

    async def _can_use_tool(self, tool_name: str, tool_input: dict, context: ToolPermissionContext):
        if tool_name != "Edit":
            return PermissionResultDeny(message=f"{tool_name} isn't available in Stick Fleet.")
        card = confirm_card(self.ctx.config.root, tool_name, tool_input)
        message_id = self._post("card", "Approve this change?", card=card)["id"]
        future: asyncio.Future[bool] = asyncio.get_running_loop().create_future()
        self.hub.pending[message_id] = (self.thread_id, future)
        try:
            allow = await future
        finally:
            self.hub.pending.pop(message_id, None)
            with self.ctx.connect() as conn:
                row = conn.execute("SELECT card_status FROM messages WHERE id = ?", (message_id,)).fetchone()
                if row["card_status"] == "active":  # the turn was stopped while the card waited
                    cards.set_message_status(self.ctx, conn, message_id, "superseded")
        if allow:
            return PermissionResultAllow()
        return PermissionResultDeny(message="The person denied this edit. Ask what they'd like instead.")

    # --- small helpers ---

    def _post(self, role: str, text: str, card: dict | None = None, status: str | None = "active") -> dict:
        with self.ctx.connect() as conn:
            return cards.post(self.ctx, conn, self.thread_id, role, text=text, card=card,
                              video_id=self.video_id, status=status)

    def _save_session(self, session_id: str | None) -> None:
        with self.ctx.connect() as conn:
            conn.execute("UPDATE threads SET sdk_session_id = ? WHERE id = ? AND sdk_session_id IS NOT ?",
                         (session_id, self.thread_id, session_id))

    def _set_running(self, running: bool) -> None:
        self.running = running
        self.ctx.events.emit("turn", None, thread_id=self.thread_id, running=running)


# --- all threads ----------------------------------------------------------------------------

class AgentHub:
    """Owns every thread's agent. Call start() inside the server's event loop and close() on shutdown."""

    def __init__(self, ctx, make_client: MakeClient | None = None, online: bool | None = None) -> None:
        self.ctx = ctx
        self.make_client = make_client or _default_client
        self.online = (make_client is not None or bool(os.environ.get("ANTHROPIC_API_KEY"))) if online is None else online
        self.budget = float(ctx.config.agent.get("budget_usd_per_session", 2))
        self.agents: dict[int, ThreadAgent] = {}
        self.pending: dict[int, tuple[int, asyncio.Future]] = {}  # confirm message id → (thread id, future)
        self.loop: asyncio.AbstractEventLoop | None = None

    def start(self, loop: asyncio.AbstractEventLoop) -> None:
        self.loop = loop
        with self.ctx.connect() as conn, db.tx(conn):
            # Nothing can answer a confirm card from before a restart.
            conn.execute("""UPDATE messages SET card_status = 'superseded' WHERE card_status = 'active'
                            AND json_extract(card_json, '$.kind') = 'confirm'""")
        self.ctx.events.subscribe(self._on_event)

    async def close(self) -> None:
        self.ctx.events.unsubscribe(self._on_event)
        tasks = [a.task for a in self.agents.values()]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.wait(tasks, timeout=15)
        self.agents.clear()

    def options(self, thread: fleet.Thread, tools: list, can_use_tool) -> ClaudeAgentOptions:
        root = self.ctx.config.root
        return ClaudeAgentOptions(
            model=self.ctx.config.models.get("agent"),
            system_prompt=SYSTEM_PROMPT.read_text(encoding="utf-8") + "\n\n## This thread\n\n"
            + fleet.thread_brief(self.ctx, thread),
            mcp_servers={fleet.SERVER: create_sdk_mcp_server(fleet.SERVER, tools=tools)},
            tools=["Read", "Edit"],
            allowed_tools=[*fleet.tool_names(tools), "Read"],
            can_use_tool=can_use_tool,
            hooks={"PreToolUse": [HookMatcher(matcher="Read|Edit", hooks=[path_guard(root)])]},
            cwd=str(root),
            resume=thread.sdk_session_id,
            max_budget_usd=max(0.01, self.budget - thread.agent_cost_usd),
            include_partial_messages=True,
            setting_sources=[],  # ignore ~/.claude and project settings, hooks and plugins
            strict_mcp_config=True,  # and any MCP servers configured outside this app
        )

    # --- called from the server (on the loop) ---

    def send(self, thread_id: int, text: str) -> None:
        self._agent(thread_id).inbox.put_nowait(text)

    def running(self, thread_id: int) -> bool:
        agent = self.agents.get(thread_id)
        return bool(agent and agent.running)

    async def interrupt(self, thread_id: int) -> None:
        for message_id, (tid, future) in list(self.pending.items()):
            if tid == thread_id and not future.done():
                with self.ctx.connect() as conn:
                    cards.set_message_status(self.ctx, conn, message_id, "denied")
                future.set_result(False)
        agent = self.agents.get(thread_id)
        if agent is not None:
            await agent.stop()

    def resolve_confirm(self, message_id: int, allow: bool) -> None:
        with self.ctx.connect() as conn:
            row = conn.execute("SELECT card_json, card_status FROM messages WHERE id = ?", (message_id,)).fetchone()
            if row is None or not row["card_json"] or json.loads(row["card_json"])["kind"] != "confirm":
                raise LookupError(f"no confirm card {message_id}")
            _, future = self.pending.get(message_id, (None, None))
            if future is None or future.done():
                if row["card_status"] == "active":
                    cards.set_message_status(self.ctx, conn, message_id, "superseded")
                raise ActionError("this change isn't waiting any more (the turn stopped or the server restarted)")
            cards.set_message_status(self.ctx, conn, message_id, "approved" if allow else "denied")
        future.set_result(allow)

    def _agent(self, thread_id: int) -> ThreadAgent:
        agent = self.agents.get(thread_id)
        if agent is None or agent.task.done():
            agent = self.agents[thread_id] = ThreadAgent(self, thread_id)
        return agent

    # --- gate comments ---

    def _on_event(self, ev: Event) -> None:
        """Runs on stage threads; hop onto the loop."""
        if ev.kind != "gate_reached" or ev.data.get("repost") or ev.data.get("gate") not in COMMENT_GATES:
            return
        if self.online and self.ctx.config.agent.get("comment_on_gates") and self.loop is not None:
            self.loop.call_soon_threadsafe(self._gate_comment, ev.video_id, ev.data["gate"])

    def _gate_comment(self, video_id: int, gate: str) -> None:
        with self.ctx.connect() as conn:
            thread_id = cards.thread_id(conn, video_id)
            rows = cards.active_cards(conn, video_id, gate)
        agent = self.agents.get(thread_id)
        if not rows or (agent and (agent.running or not agent.inbox.empty())):
            return  # skip while another turn is running
        card = fleet.card_summary(json.loads(rows[-1]["card_json"]))
        self.send(thread_id, GATE_COMMENT.format(gate=gate, card=json.dumps(card, indent=1)))

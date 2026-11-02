"""Local web app: REST endpoints for the card buttons and the chat, a websocket for live updates, the built UI, and
the MCP endpoint at /mcp that the Claude Code session connects to (server/claude_code.py).

There is no login, so the server binds to localhost and refuses requests whose Host or Origin is not
local. Without the Origin check, any web page you visit could POST to /publish from your browser.
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from agent.harness import OFFLINE, AgentHub
from core import actions, cards
from core.context import Ctx, make_ctx
from core.engine import Engine
from core.errors import ActionError
from core.events import Event
from server import claude_code
from youtube import auth

log = logging.getLogger("stickfleet.server")

WEB_DIST = Path(__file__).resolve().parent / "web" / "dist"
LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
NOT_BUILT = """<!doctype html><meta charset="utf-8"><title>Stick Fleet</title>
<body style="font: 16px system-ui; margin: 3rem">
<h1>The UI isn't built yet</h1><pre>cd server/web
npm install
npm run build</pre><p>Then reload this page. The API is already running at <code>/api</code>.</p></body>"""

THREAD_SQL = """
SELECT t.id, t.channel_id, t.video_id, t.title, t.created_at, v.state, v.cost_usd, v.error,
  (SELECT COUNT(*) FROM messages m
     WHERE m.thread_id = t.id AND m.role = 'card' AND m.card_status = 'active') AS waiting,
  (SELECT MAX(m.id) FROM messages m WHERE m.thread_id = t.id) AS last_message_id
FROM threads t LEFT JOIN videos v ON v.id = t.video_id
"""


# --- request bodies ------------------------------------------------------------

class NewVideo(BaseModel):
    channel_id: str
    idea: str


class NextPart(BaseModel):
    idea: str = ""


class Gate(BaseModel):
    gate: str


class Revise(BaseModel):
    gate: str
    note: str


class OutlineEdits(BaseModel):
    ops: list[dict]


class Flag(BaseModel):
    idxs: list[int]
    kind: str
    note: str = ""


class SceneEdit(BaseModel):
    idx: int
    visual_prompt: str | None = None
    narration: str | None = None


class Pick(BaseModel):
    title_idx: int | None = None
    thumb_idx: int | None = None
    title: str | None = None


class Swap(BaseModel):
    title_idx: int | None = None
    thumb_idx: int | None = None


class PublishFields(BaseModel):
    title: str | None = None
    description: str | None = None
    tags: list[str] | None = None
    publish_at: float | None = None
    ai_disclosure: bool | None = None


class Chat(BaseModel):
    text: str


class Confirm(BaseModel):
    allow: bool


# --- websocket fan-out -----------------------------------------------------------

class Hub:
    """Forwards bus events to websocket clients. Listeners run on stage threads, so hop onto the loop."""

    def __init__(self, ctx: Ctx, agents: AgentHub) -> None:
        self.ctx = ctx
        self.agents = agents
        self.loop: asyncio.AbstractEventLoop | None = None
        self.clients: set[asyncio.Queue] = set()

    def on_event(self, ev: Event) -> None:
        if self.loop is None or not self.clients:
            return
        out = []
        if ev.kind in ("message", "message_updated"):
            out.append({"type": ev.kind, "message": ev.data["message"]})
        elif ev.kind == "turn":
            out.append({"type": "turn", "thread_id": ev.data["thread_id"], "running": ev.data["running"]})
        if ev.video_id is not None:
            with self.ctx.connect() as conn:
                row = conn.execute(THREAD_SQL + " WHERE t.video_id = ?", (ev.video_id,)).fetchone()
            if row is not None:
                out.append({"type": "thread", "thread": {**dict(row), "running": self.agents.running(row["id"])}})
        for payload in out:
            self.loop.call_soon_threadsafe(self._broadcast, payload)

    def _broadcast(self, payload: dict) -> None:
        for queue in list(self.clients):
            queue.put_nowait(payload)


def _is_local(hosts: frozenset[str], host: str | None, origin: str | None) -> bool:
    if urlsplit("//" + (host or "")).hostname not in hosts:
        return False
    return origin is None or urlsplit(origin).hostname in hosts


# --- app -------------------------------------------------------------------------

def create_app(ctx: Ctx | None = None, run_engine: bool = True, hosts: frozenset[str] = LOCAL_HOSTS,
               agents: AgentHub | None = None) -> FastAPI:
    ctx = ctx or make_ctx()
    agents = agents or AgentHub(ctx)
    hub = Hub(ctx, agents)
    ctx.events.subscribe(hub.on_event)
    engine = Engine(ctx)
    mcp = claude_code.make_manager(claude_code.make_server(ctx))

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        hub.loop = asyncio.get_running_loop()
        agents.start(hub.loop)
        task = asyncio.create_task(engine.run_forever()) if run_engine else None
        async with mcp.run():
            yield
        await agents.close()
        engine.stop()
        if task is not None:
            with suppress(asyncio.TimeoutError):
                await asyncio.wait_for(task, timeout=15)

    connecting = asyncio.Lock()  # one Google sign-in at a time

    app = FastAPI(title="Stick Fleet", lifespan=lifespan)
    app.state.ctx = ctx
    app.state.agents = agents

    @app.middleware("http")
    async def local_only(request: Request, call_next):
        if not _is_local(hosts, request.headers.get("host"), request.headers.get("origin")):
            return JSONResponse({"detail": "local requests only"}, status_code=403)
        return await call_next(request)

    @app.exception_handler(ActionError)
    async def action_error(request: Request, exc: ActionError):
        return JSONResponse({"detail": str(exc)}, status_code=409)

    @app.exception_handler(ValueError)
    async def value_error(request: Request, exc: ValueError):
        return JSONResponse({"detail": str(exc)}, status_code=400)

    @app.exception_handler(LookupError)
    async def not_found(request: Request, exc: LookupError):
        return JSONResponse({"detail": str(exc)}, status_code=404)

    # --- reads -----------------------------------------------------------------

    @app.get("/api/channels")
    def channels() -> list[dict]:
        with ctx.connect() as conn:
            out = []
            for c in ctx.config.channels.values():
                yt = auth.status(ctx, c.id)
                yt["signin_error"] = conn.execute("SELECT signin_error FROM channels WHERE id = ?",
                                                  (c.id,)).fetchone()[0]
                out.append({
                    "id": c.id, "name": c.name, "budget_usd": c.budget_usd, "gates": c.gates,
                    "home_thread_id": cards.home_thread_id(conn, c.id),
                    "youtube": {**yt, "mode": ctx.config.youtube.get("mode", "stub"),
                                "channel_id": c.youtube.get("channel_id")},
                })
            return out

    @app.post("/api/channels/{channel_id}/connect")
    async def connect(channel_id: str) -> dict:
        """Opens Google's consent screen in this machine's browser and waits (up to 5 min) for the sign-in."""
        ctx.channel(channel_id)
        if connecting.locked():
            raise ActionError("a Google sign-in is already waiting in your browser")
        def note(text: str) -> None:  # leave a record in the channel's home thread
            with ctx.connect() as conn:
                cards.post(ctx, conn, cards.home_thread_id(conn, channel_id), "system", text=text)

        async with connecting:
            try:
                result = await asyncio.to_thread(auth.connect, ctx, channel_id)
            except Exception as e:
                note(f"YouTube connect failed: {e}")
                raise
        note(f"Connected to YouTube channel {result['title']} ({result['youtube_channel_id']}).")
        return result

    @app.get("/api/agent")
    def agent() -> dict:
        return {"online": agents.online, "model": ctx.config.models.get("agent"),
                "budget_usd_per_session": agents.budget}

    @app.get("/api/threads")
    def threads() -> list[dict]:
        with ctx.connect() as conn:
            rows = conn.execute(THREAD_SQL + " ORDER BY t.channel_id, t.video_id IS NOT NULL, t.id DESC").fetchall()
        return [{**dict(r), "running": agents.running(r["id"])} for r in rows]

    @app.get("/api/threads/{thread_id}/messages")
    def messages(thread_id: int) -> list[dict]:
        with ctx.connect() as conn:
            rows = conn.execute("SELECT * FROM messages WHERE thread_id = ? ORDER BY id", (thread_id,)).fetchall()
            return [cards.to_dict(r) for r in rows]

    @app.get("/api/videos/{video_id}")
    def video(video_id: int) -> dict:
        info = actions.status(ctx, video_id=video_id)
        with ctx.connect() as conn:
            rows = conn.execute("SELECT * FROM scenes WHERE video_id = ? ORDER BY idx", (video_id,)).fetchall()
        info["scene_list"] = [
            {"idx": s["idx"], "label": s["label"], "state": s["state"], "regen_count": s["regen_count"],
             "narration": s["narration"], "visual_prompt": s["visual_prompt"],
             "preview_url": cards.preview_url(s["still_path"])}
            for s in rows
        ]
        return info

    # --- card buttons: thin wrappers over core.actions ---------------------------

    @app.post("/api/videos")
    def new_video(body: NewVideo) -> dict:
        video_id = actions.new_video(ctx, body.channel_id, body.idea)
        with ctx.connect() as conn:
            return {"video_id": video_id, "thread_id": cards.thread_id(conn, video_id)}

    @app.post("/api/topics/{topic_id}/start")
    def start_topic(topic_id: int) -> dict:
        video_id = actions.start_topic(ctx, topic_id)
        with ctx.connect() as conn:
            return {"video_id": video_id, "thread_id": cards.thread_id(conn, video_id)}

    @app.post("/api/topics/{topic_id}/dismiss")
    def dismiss_topic(topic_id: int) -> dict:
        actions.dismiss_topic(ctx, topic_id)
        return {"ok": True}

    @app.post("/api/videos/{video_id}/next_part")
    def next_part(video_id: int, body: NextPart) -> dict:
        new_id = actions.next_part(ctx, video_id, body.idea)
        with ctx.connect() as conn:
            return {"video_id": new_id, "thread_id": cards.thread_id(conn, new_id)}

    @app.post("/api/videos/{video_id}/stop_writing")
    def stop_writing(video_id: int) -> dict:
        actions.stop_writing(ctx, video_id)
        return {"ok": True}

    @app.post("/api/videos/{video_id}/swap")
    def swap(video_id: int, body: Swap) -> dict:
        return {"ok": True, "changed": actions.apply_swap(ctx, video_id, body.title_idx, body.thumb_idx)}

    @app.post("/api/videos/{video_id}/keep")
    def keep(video_id: int) -> dict:
        actions.keep_swap(ctx, video_id)
        return {"ok": True}

    @app.post("/api/videos/{video_id}/approve")
    def approve(video_id: int, body: Gate) -> dict:
        actions.approve(ctx, video_id, body.gate)
        return {"ok": True}

    @app.post("/api/videos/{video_id}/revise")
    def revise(video_id: int, body: Revise) -> dict:
        actions.revise(ctx, video_id, body.gate, body.note)
        return {"ok": True}

    @app.post("/api/videos/{video_id}/regenerate")
    def regenerate(video_id: int, body: Gate) -> dict:
        actions.regenerate(ctx, video_id, body.gate)
        return {"ok": True}

    @app.post("/api/videos/{video_id}/edit_outline")
    def edit_outline(video_id: int, body: OutlineEdits) -> dict:
        actions.edit_outline(ctx, video_id, body.ops)
        return {"ok": True}

    @app.post("/api/videos/{video_id}/flag")
    def flag(video_id: int, body: Flag) -> dict:
        actions.flag_scenes(ctx, video_id, body.idxs, body.kind, body.note)
        return {"ok": True}

    @app.post("/api/videos/{video_id}/edit_scene")
    def edit_scene(video_id: int, body: SceneEdit) -> dict:
        actions.edit_scene(ctx, video_id, body.idx, body.visual_prompt, body.narration)
        return {"ok": True}

    @app.post("/api/videos/{video_id}/pick")
    def pick(video_id: int, body: Pick) -> dict:
        actions.pick(ctx, video_id, body.title_idx, body.thumb_idx, body.title)
        return {"ok": True}

    @app.post("/api/videos/{video_id}/publish_fields")
    def publish_fields(video_id: int, body: PublishFields) -> dict:
        actions.update_publish(ctx, video_id, **body.model_dump(exclude_none=True))
        return {"ok": True}

    @app.post("/api/videos/{video_id}/publish")
    def publish(video_id: int, body: PublishFields) -> dict:
        actions.request_publish(ctx, video_id, **body.model_dump(exclude_none=True))
        return {"ok": True}

    @app.post("/api/videos/{video_id}/retry")
    def retry(video_id: int) -> dict:
        actions.retry(ctx, video_id)
        return {"ok": True}

    # --- chat: async so the agent's queues live on the server's loop --------------------

    @app.post("/api/threads/{thread_id}/chat")
    async def chat(thread_id: int, body: Chat) -> dict:
        text = body.text.strip()
        if not text:
            raise ActionError("the message is empty")
        with ctx.connect() as conn:
            thread = conn.execute("SELECT * FROM threads WHERE id = ?", (thread_id,)).fetchone()
            if thread is None:
                raise HTTPException(404, f"no thread {thread_id}")
            message = cards.post(ctx, conn, thread_id, "user", text=text, video_id=thread["video_id"])
            if not agents.online:
                cards.post(ctx, conn, thread_id, "assistant", text=OFFLINE, video_id=thread["video_id"])
        if agents.online:
            agents.send(thread_id, text)
        return message

    @app.post("/api/threads/{thread_id}/stop")
    async def stop(thread_id: int) -> dict:
        await agents.interrupt(thread_id)
        return {"ok": True}

    @app.post("/api/confirm/{message_id}")
    async def confirm(message_id: int, body: Confirm) -> dict:
        agents.resolve_confirm(message_id, body.allow)
        return {"ok": True}

    # --- live updates ---------------------------------------------------------------

    @app.websocket("/ws")
    async def ws(socket: WebSocket) -> None:
        if not _is_local(hosts, socket.headers.get("host"), socket.headers.get("origin")):
            await socket.close(code=1008)
            return
        await socket.accept()
        queue: asyncio.Queue = asyncio.Queue()
        hub.clients.add(queue)

        async def pump() -> None:
            while True:
                await socket.send_json(await queue.get())

        sender = asyncio.create_task(pump())
        try:
            while True:
                await socket.receive_text()  # the client only pings; this notices the disconnect
        except WebSocketDisconnect:
            pass
        finally:
            sender.cancel()
            hub.clients.discard(queue)

    # --- the Claude Code session's MCP endpoint (server/claude_code.py) ---------------

    app.add_route("/mcp", claude_code.endpoint(mcp))

    # --- files ----------------------------------------------------------------------

    app.mount("/media", StaticFiles(directory=ctx.config.media_dir), name="media")
    if WEB_DIST.is_dir():
        app.mount("/", StaticFiles(directory=WEB_DIST, html=True), name="web")
    else:
        @app.get("/", response_class=HTMLResponse)
        def not_built() -> str:
            return NOT_BUILT

    return app

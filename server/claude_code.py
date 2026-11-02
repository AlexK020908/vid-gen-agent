"""The MCP endpoint the Claude Code session connects to: http://localhost:8000/mcp (.mcp.json), served by run.py serve.

It serves the chat agent's tools (agent/tools.py), as they work in a channel's home thread: tools that act on a
video take its video_id, and with more than one channel the others take `channel`. On top of those, the tools
for Claude's work (core/jobs.py): `jobs`, `take_job`, `answer_job`, `wait`, and `contact_sheet` to look at a
video's pictures. There's no approve or publish tool, as for the chat agent: those stay buttons in the browser.
"""
from __future__ import annotations

import asyncio
import base64
import io
import json
import logging
import time
from contextlib import suppress

import mcp_types as types
from mcp.server.lowlevel import Server
from mcp.server.streamable_http_manager import StreamableHTTPASGIApp, StreamableHTTPSessionManager
from mcp.server.transport_security import TransportSecuritySettings
from PIL import Image, ImageDraw

from agent.tools import STATE_TEXT, build_tools, load_thread, waiting_card
from core import jobs
from core.errors import ActionError
from providers.images import preview_path

log = logging.getLogger("stickfleet.claude_code")

INSTRUCTIONS = """Stick Fleet makes narrated YouTube videos. The app does the voice, pictures, rendering and \
uploading; you do Claude's part of the work, so no API key is spent on it.

Claude's work waits as jobs. `jobs` lists them; `take_job` gives one's instructions (the prompt, any pictures, \
and the JSON shape to reply with); `answer_job` sends your JSON reply. It's checked at once by the same code \
checks the pipeline uses: fix what they say and answer again. Once it passes, the video carries on. `wait` \
holds until a job or a card arrives. Approving a card and publishing stay buttons in the browser \
(http://localhost:8000): tell the person when a card is waiting for them."""

WAKE = {"claude_job", "gate_reached", "stage_failed"}
SHEET_COLS, SHEET_TILE, SHEET_MAX = 4, 320, 24  # contact sheet: 4 across, 320 px each, 24 scenes a sheet


def _text(text: str, error: bool = False) -> types.CallToolResult:
    return types.CallToolResult(content=[types.TextContent(type="text", text=text)], is_error=error)


def _obj(props: dict, required: tuple = ()) -> dict:
    return {"type": "object", "properties": props, "required": list(required), "additionalProperties": False}


JOB_TOOLS = [
    types.Tool(name="jobs", description="Claude's work waiting for you, oldest first: each job's id, what it is, "
               "the video (and scene), and whether a worker has taken it.", input_schema=_obj({})),
    types.Tool(name="take_job", description="Take a job: its instructions, the request, any pictures, and the JSON "
               "shape to reply with. Marks it taken so other workers leave it.",
               input_schema=_obj({"job_id": {"type": "integer"},
                                  "again": {"type": "boolean", "description": "Take it although another worker "
                                            "took it in the last 15 minutes (that worker is gone)."}}, ("job_id",))),
    types.Tool(name="answer_job", description="Send your reply to a job. It's checked at once; if anything's wrong "
               "you get the list and the job stays waiting, so fix it and answer again. Once it passes, the video "
               "carries on.",
               input_schema=_obj({"job_id": {"type": "integer"},
                                  "answer": {"type": ["object", "string"],
                                             "description": "The reply: JSON in the shape take_job gave."}},
                                 ("job_id", "answer"))),
    types.Tool(name="wait", description="Wait until a job arrives, a card is waiting for the person, or a video "
               "fails (or the time is up), then say what's waiting. Returns at once if a job is already waiting.",
               input_schema=_obj({"seconds": {"type": "integer", "minimum": 1, "maximum": 600,
                                              "description": "How long to wait at most; 120 if left out."}})),
    types.Tool(name="contact_sheet", description="A video's pictures as one image, numbered by scene, 24 at a "
               "time, so you can look at them.",
               input_schema=_obj({"video_id": {"type": "integer"},
                                  "from_idx": {"type": "integer", "minimum": 1,
                                               "description": "The first scene; 1 if left out."}}, ("video_id",))),
]


def make_server(ctx) -> Server:
    channels = sorted(ctx.config.channels)

    def home(channel_id: str):
        with ctx.connect() as conn:
            row = conn.execute("SELECT id FROM threads WHERE channel_id = ? AND video_id IS NULL",
                               (channel_id,)).fetchone()
        if row is None:
            raise ActionError(f"there's no channel {channel_id!r}; the channels are {', '.join(channels)}")
        return load_thread(ctx, row["id"])

    fleet = {t.name: t for t in build_tools(ctx, home(channels[0]))}
    fleet_tools = []
    for t in fleet.values():
        schema = json.loads(json.dumps(t.input_schema))
        if len(channels) > 1:
            schema["properties"]["channel"] = {"type": "string", "enum": channels,
                                               "description": "Which channel, for a tool without a video_id."}
        fleet_tools.append(types.Tool(name=t.name, description=t.description, input_schema=schema))
    schemas = {t.name: t.input_schema for t in [*fleet_tools, *JOB_TOOLS]}

    def channel_for(args: dict) -> str:
        if args.get("channel"):
            return args.pop("channel")
        if args.get("video_id") is not None:
            with ctx.connect() as conn:
                row = conn.execute("SELECT channel_id FROM videos WHERE id = ?", (args["video_id"],)).fetchone()
            if row is None:
                raise ActionError(f"there's no video #{args['video_id']}")
            return row["channel_id"]
        if len(channels) == 1:
            return channels[0]
        raise ActionError(f"say which channel ({', '.join(channels)})")

    async def call_fleet(name: str, args: dict) -> types.CallToolResult:
        args = dict(args)
        thread = await asyncio.to_thread(home, channel_for(args))
        tool = {t.name: t for t in build_tools(ctx, thread)}[name]
        result = await tool.handler(args)
        return _text("\n".join(c["text"] for c in result["content"]), bool(result.get("is_error")))

    # --- jobs ---

    def list_jobs() -> list[dict]:
        now = time.time()
        with ctx.connect() as conn:
            rows = jobs.pending(conn)
        return [{"job_id": r["id"], "what": r["what"], "kind": r["kind"], "video_id": r["video_id"],
                 "scene": r["scene_idx"], "waiting_min": int((now - r["created_at"]) // 60),
                 "taken_min_ago": None if r["taken_at"] is None else int((now - r["taken_at"]) // 60)}
                for r in rows]

    def take_job(args: dict) -> types.CallToolResult:
        with ctx.connect() as conn:
            row = jobs.take(conn, args["job_id"], bool(args.get("again")))
        where = f" for video #{row['video_id']}" if row["video_id"] else ""
        parts = [f"Job {row['id']}: {row['what']}{where}. Reply with answer_job(job_id={row['id']}, answer=<JSON>).",
                 "## Instructions\n" + row["system"]]
        images: list[types.ImageContent] = []
        heading = {"user": "## The request", "assistant": "## Your earlier reply"}
        for n, m in enumerate(json.loads(row["messages_json"])):
            title = "## What was wrong with it" if m["role"] == "user" and n else heading[m["role"]]
            content = m["content"]
            if isinstance(content, str):
                parts.append(f"{title}\n{content}")
                continue
            texts = []
            for b in content:
                if b.get("type") == "image":
                    images.append(types.ImageContent(type="image", data=b["source"]["data"],
                                                     mime_type=b["source"]["media_type"]))
                    texts.append(f"(picture {len(images)}, attached)")
                else:
                    texts.append(b.get("text") or "")
            parts.append(title + "\n" + "\n".join(texts))
        parts.append("## Reply with JSON in this shape\n" + json.dumps(json.loads(row["schema_json"]), indent=1))
        return types.CallToolResult(content=[types.TextContent(type="text", text="\n\n".join(parts)), *images])

    def answer_job(args: dict) -> types.CallToolResult:
        answer = args["answer"]
        text = answer if isinstance(answer, str) else json.dumps(answer)
        with ctx.connect() as conn:
            row = jobs.get(conn, args["job_id"])
            problems = jobs.answer(conn, args["job_id"], text)
        if problems:
            return _text("Not accepted; the job is still waiting. Fix these and answer again:\n"
                         + "\n".join(f"- {p}" for p in problems), error=True)
        ctx.events.emit("claude_answered", row["video_id"], job_id=row["id"])
        return _text(f"Accepted: {row['what']}. The video carries on.")

    def summary() -> str:
        with ctx.connect() as conn:
            rows = conn.execute("""SELECT id, state FROM videos WHERE state NOT IN ('live', 'scheduled')
                                   ORDER BY id DESC LIMIT 10""").fetchall()
            videos = []
            for r in rows:
                card = waiting_card(conn, r["id"])
                videos.append({"video_id": r["id"], "state": STATE_TEXT[r["state"]],
                               "card_waiting_for_the_person": card["kind"] if card else None})
        return json.dumps({"jobs_waiting": list_jobs(), "videos": videos})

    async def wait(args: dict) -> types.CallToolResult:
        seconds = min(max(int(args.get("seconds") or 120), 1), 600)
        if any(j["taken_min_ago"] is None for j in await asyncio.to_thread(list_jobs)):
            return _text(await asyncio.to_thread(summary))
        loop, woke = asyncio.get_running_loop(), asyncio.Event()

        def on(ev) -> None:
            if ev.kind in WAKE:
                loop.call_soon_threadsafe(woke.set)

        ctx.events.subscribe(on)
        try:
            with suppress(asyncio.TimeoutError):
                await asyncio.wait_for(woke.wait(), seconds)
        finally:
            ctx.events.unsubscribe(on)
        return _text(await asyncio.to_thread(summary))

    def contact_sheet(args: dict) -> types.CallToolResult:
        start = int(args.get("from_idx") or 1)
        with ctx.connect() as conn:
            rows = conn.execute("""SELECT idx, still_path FROM scenes WHERE video_id = ? AND idx >= ?
                                   AND still_path IS NOT NULL ORDER BY idx""", (args["video_id"], start)).fetchall()
            total = conn.execute("SELECT COUNT(*) AS n FROM scenes WHERE video_id = ?",
                                 (args["video_id"],)).fetchone()["n"]
        if not rows:
            return _text(f"Video #{args['video_id']} has no pictures from scene {start} on yet.", error=True)
        shown = rows[:SHEET_MAX]
        tile_h = SHEET_TILE * 9 // 16
        sheet = Image.new("RGB", (SHEET_COLS * SHEET_TILE, -(-len(shown) // SHEET_COLS) * (tile_h + 22)), "white")
        draw = ImageDraw.Draw(sheet)
        for n, r in enumerate(shown):
            still = ctx.config.media_dir / r["still_path"]
            src = preview_path(still) if preview_path(still).exists() else still
            x, y = n % SHEET_COLS * SHEET_TILE, n // SHEET_COLS * (tile_h + 22)
            with Image.open(src) as img:
                sheet.paste(img.convert("RGB").resize((SHEET_TILE - 4, tile_h - 4)), (x + 2, y + 2))
            draw.text((x + 4, y + tile_h + 3), f"scene {r['idx']}", fill="black")
        buf = io.BytesIO()
        sheet.save(buf, "JPEG", quality=80)
        last = shown[-1]["idx"]
        more = f"; call again with from_idx={last + 1} for the rest" if len(rows) > len(shown) else ""
        return types.CallToolResult(content=[
            types.TextContent(type="text", text=f"Video #{args['video_id']}, scenes {shown[0]['idx']}–{last} of "
                                                f"{total}{more}."),
            types.ImageContent(type="image", data=base64.b64encode(buf.getvalue()).decode(), mime_type="image/jpeg")])

    # --- the protocol ---

    async def on_list_tools(_ctx, _params) -> types.ListToolsResult:
        return types.ListToolsResult(tools=[*fleet_tools, *JOB_TOOLS])

    async def on_call_tool(_ctx, params: types.CallToolRequestParams) -> types.CallToolResult:
        name, args = params.name, dict(params.arguments or {})
        try:
            if name in fleet:
                return await call_fleet(name, args)
            if name == "jobs":
                return _text(json.dumps(await asyncio.to_thread(list_jobs)))
            if name == "take_job":
                return await asyncio.to_thread(take_job, args)
            if name == "answer_job":
                return await asyncio.to_thread(answer_job, args)
            if name == "wait":
                return await wait(args)
            if name == "contact_sheet":
                return await asyncio.to_thread(contact_sheet, args)
            return _text(f"there's no tool {name!r}", error=True)
        except (ActionError, ValueError, LookupError) as e:
            return _text(str(e), error=True)
        except Exception as e:  # a crash reads as a failed call, not a dropped connection
            log.exception("tool %s failed", name)
            return _text(f"{type(e).__name__}: {e}", error=True)

    return Server("stickfleet", instructions=INSTRUCTIONS, get_tool_input_schema=schemas.get,
                  on_list_tools=on_list_tools, on_call_tool=on_call_tool)


def make_manager(server: Server) -> StreamableHTTPSessionManager:
    local = TransportSecuritySettings(enable_dns_rebinding_protection=True,
                                      allowed_hosts=["127.0.0.1:*", "localhost:*", "[::1]:*"],
                                      allowed_origins=["http://127.0.0.1:*", "http://localhost:*", "http://[::1]:*"])
    return StreamableHTTPSessionManager(app=server, json_response=True, security_settings=local)


def endpoint(manager: StreamableHTTPSessionManager) -> StreamableHTTPASGIApp:
    return StreamableHTTPASGIApp(manager)

"""The MCP endpoint the Claude Code session connects to: http://localhost:8000/mcp (.mcp.json), served by run.py serve.

The chat is how the owner runs the fleet, so this serves the fleet tools (server/tools.py: status, review, news,
approve, publish and the rest), and the tools for Claude's work (core/jobs.py): `jobs`, `take_job`, `answer_job`,
`wait`, and `contact_sheet` to look at a video's pictures.
"""
from __future__ import annotations

import asyncio
import base64
import io
import json
import logging
import time
from contextlib import suppress
from pathlib import Path

import mcp_types as types
from mcp.server.lowlevel import Server
from mcp.server.streamable_http_manager import StreamableHTTPASGIApp, StreamableHTTPSessionManager
from mcp.server.transport_security import TransportSecuritySettings
from PIL import Image, ImageDraw

from core import jobs
from core.errors import ActionError
from providers.images import preview_path
from providers.session import LOOKING
from server.tools import STATE_TEXT, make_tools, waiting_card

log = logging.getLogger("stickfleet.claude_code")

INSTRUCTIONS = """Stick Fleet makes narrated YouTube videos. The app does the voice, pictures, rendering and \
uploading. This chat is how the owner runs it (there's no browser app), and you do Claude's part of the work, so \
no API key is spent on it.

Running the channels: `status` lists the channels, their videos and which card waits on the owner. `review` gives \
a waiting card in full: show the owner what they decide on (the outline, the script file to open, the video file \
to watch, the title and thumbnail options). `news` gives what the app posted since the last look. Then do what \
the owner says: `approve`, `revise` with their note, `edit_outline`, `flag_scenes`, `pick`, `update_publish`, \
`publish`. Approve, flag, restage, edit a scene, retry, publish or swap only when the owner asks for it in this chat: those \
spend money or change YouTube, and Claude Code asks the owner to confirm each one.

Claude's work waits as jobs: the outline, the script, the reviewer's read of each, rewrites of flagged scenes, \
titles and topic ideas, and the looking (picture checks, place maps, part names, the props list, a staging sheet \
per scene). `jobs` lists them; `take_job` gives one's instructions (the prompt, any pictures, and the JSON shape \
to reply with; a long one comes as a file to read whole); `answer_job` sends your JSON reply. It's checked at once \
by the same code checks the pipeline uses: fix what they say and answer again. Once it passes, the video carries \
on. A script goes in parts, whole beats at a time in order (`part` 1, 2, ..., and `last` on the final one), each \
checked as it arrives. A review job (kind `critic`) goes to the `critic` agent with just its job id, so a fresh \
reader judges the draft rather than the one who wrote it. The looking jobs (kinds picture, map, parts, inventory, \
sheet) go to the `worker` agent, so their pictures and one-per-scene briefs stay out of the main chat. `wait` \
holds (up to 50 seconds; call it again to keep waiting) until a job arrives, a card waits on the owner, or \
something needs them. The `stickfleet` skill has the rest."""

WAKE = {"claude_job", "gate_reached", "stage_failed", "blocked", "topics_proposed", "swap_suggested", "metrics",
        "published", "went_live"}
SHEET_COLS, SHEET_TILE, SHEET_MAX = 4, 320, 24  # contact sheet: 4 across, 320 px each, 24 scenes a sheet
BRIEF_MAX = 30_000  # characters; a longer brief (a script's review or rewrite) goes to a file, under MCP's output cap
PICTURE_WIDTH = 1280  # a job's pictures are sent this wide as JPEGs: enough to see a towel beside a knee
WAIT_MAX = 50  # seconds; Claude Code gives up on a tool call after about a minute (a 65 s wait timed out, Nov 2, 2026)
PARTS = {"script": "This reply is long, so send it in parts: answer_job with part=1, 2, ... in order, each part one "
                   "or more whole beats (their `scenes`), the final one with last=true. Part 1 carries `places`; a "
                   "place first used later can come in that part's own `places`. Each part is checked as it arrives "
                   "against the script so far, and the last against the whole script. To fix an accepted part, send "
                   "it again with its number."}


def _text(text: str, error: bool = False) -> types.CallToolResult:
    return types.CallToolResult(content=[types.TextContent(type="text", text=text)], is_error=error)


def _obj(props: dict, required: tuple = ()) -> dict:
    return {"type": "object", "properties": props, "required": list(required), "additionalProperties": False}


def _picture(block: dict) -> types.ImageContent | None:
    """A request's picture (providers/claude.py `_image`: its path) as a JPEG PICTURE_WIDTH across; None if the file
    is gone."""
    path = Path(block["path"])
    if not path.exists():
        return None
    with Image.open(path) as img:
        img = img.convert("RGB")
        img.thumbnail((PICTURE_WIDTH, PICTURE_WIDTH))
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=85)
    return types.ImageContent(type="image", data=base64.b64encode(buf.getvalue()).decode(), mime_type="image/jpeg")


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
               "carries on. A long reply (a script) goes in parts: part 1, 2, ..., last=true on the final one.",
               input_schema=_obj({"job_id": {"type": "integer"},
                                  "answer": {"type": ["object", "string"],
                                             "description": "The reply: JSON in the shape take_job gave (or one "
                                                            "part of it)."},
                                  "part": {"type": "integer", "minimum": 1,
                                           "description": "This is part N of the reply; leave out for a whole "
                                                          "reply. Sending an accepted part's number again replaces "
                                                          "it."},
                                  "last": {"type": "boolean",
                                           "description": "With part: this is the final part, so check the "
                                                          "parts together as the whole reply."}},
                                 ("job_id", "answer"))),
    types.Tool(name="wait", description="Wait until a job arrives, a card is waiting for the person, or a video "
               "fails (or the time is up), then say what's waiting. Returns at once if a job is already waiting, or "
               "if one of those happened since the last wait returned. Call it again to keep waiting.",
               input_schema=_obj({"seconds": {"type": "integer", "minimum": 1, "maximum": WAIT_MAX,
                                              "description": f"How long to wait at most; {WAIT_MAX} if left out."}})),
    types.Tool(name="contact_sheet", description="A video's pictures as one image, numbered by scene, 24 at a "
               "time, so you can look at them.",
               input_schema=_obj({"video_id": {"type": "integer"},
                                  "from_idx": {"type": "integer", "minimum": 1,
                                               "description": "The first scene; 1 if left out."}}, ("video_id",))),
]


def make_server(ctx) -> Server:
    fleet = make_tools(ctx)
    fleet_tools = [tool for tool, _ in fleet.values()]
    schemas = {t.name: t.input_schema for t in [*fleet_tools, *JOB_TOOLS]}

    async def call_fleet(name: str, args: dict) -> types.CallToolResult:
        out = await asyncio.to_thread(fleet[name][1], args)  # the actions block on SQLite; keep the loop free
        return out if isinstance(out, types.CallToolResult) else _text(out)

    # --- jobs ---

    def list_jobs() -> list[dict]:
        now = time.time()
        with ctx.connect() as conn:
            rows = jobs.pending(conn)
        return [{"job_id": r["id"], "what": r["what"], "kind": r["kind"], "video_id": r["video_id"],
                 "scene": r["scene_idx"], "waiting_min": int((now - r["created_at"]) // 60),
                 "taken_min_ago": None if r["taken_at"] is None else int((now - r["taken_at"]) // 60),
                 **({"parts": jobs.parts_so_far(r)} if r["parts_json"] else {})}
                for r in rows]

    def take_job(args: dict) -> types.CallToolResult:
        with ctx.connect() as conn:
            row = jobs.take(conn, args["job_id"], bool(args.get("again")))
        where = f" for video #{row['video_id']}" if row["video_id"] else ""
        head = [f"Job {row['id']}: {row['what']}{where}. Reply with answer_job(job_id={row['id']}, answer=<JSON>)."]
        if row["kind"] in PARTS:
            head.append(PARTS[row["kind"]])
        if row["parts_json"]:
            head.append(f"So far: {jobs.parts_so_far(row)}. Carry on with the next part.")
        if row["kind"] == "critic":
            head.append("This is a review: if you wrote the draft, hand the job to the critic agent instead.")
        if row["kind"] in LOOKING:
            head.append("This is a looking job: the worker agent does these, so if you're the main chat, hand the "
                        "waiting looking jobs to it instead.")
        parts = ["## Instructions\n" + row["system"]]
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
                    picture = _picture(b)
                    if picture is None:
                        texts.append(f"(a picture that's gone: {b['path']})")
                        continue
                    images.append(picture)
                    texts.append(f"(picture {len(images)}, attached)")
                else:
                    texts.append(b.get("text") or "")
            parts.append(title + "\n" + "\n".join(texts))
        shape = "## Reply with JSON in this shape\n" + json.dumps(json.loads(row["schema_json"]), indent=1)
        brief = "\n\n".join(parts)
        if len(brief) > BRIEF_MAX:
            path = ctx.config.data_dir / "jobs" / f"job-{row['id']}.md"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(brief + "\n\n" + shape + "\n", encoding="utf-8")
            head.append(f"The brief is long ({len(brief):,} characters), so it's in {path}: read all of it before "
                        "answering.")
            brief = ""
        text = "\n\n".join(p for p in ["\n".join(head), brief, shape] if p)
        return types.CallToolResult(content=[types.TextContent(type="text", text=text), *images])

    def answer_job(args: dict) -> types.CallToolResult:
        answer, part, last = args["answer"], args.get("part"), bool(args.get("last"))
        text = answer if isinstance(answer, str) else json.dumps(answer)
        with ctx.connect() as conn:
            problems = jobs.answer(conn, args["job_id"], text, part, last)
            row = jobs.get(conn, args["job_id"])
        listed = "\n".join(f"- {p}" for p in problems)
        if problems and part is not None and not last:
            return _text(f"Part {part} not accepted (the parts before it are kept). Fix these and send it "
                         f"again:\n{listed}", error=True)
        if problems:
            kept = (f" The parts are kept ({jobs.parts_so_far(row)}): send the ones that need fixing again by "
                    "number, the final one with last=true." if part is not None else "")
            return _text(f"Not accepted; the job is still waiting.{kept} Fix these and answer again:\n{listed}",
                         error=True)
        if part is not None and not last:
            return _text(f"Part {part} accepted: {jobs.parts_so_far(row)}. Send part {part + 1}, with last=true "
                         "on the final part.")
        ctx.events.emit("claude_answered", row["video_id"], job_id=row["id"])
        on = "The video carries on." if row["video_id"] and row["kind"] != "topic" else "The ideas post within seconds."
        return _text(f"Accepted: {row['what']}. {on}")

    def summary() -> str:
        with ctx.connect() as conn:
            rows = conn.execute("""SELECT id, state FROM videos WHERE state NOT IN ('live', 'scheduled')
                                   ORDER BY id DESC LIMIT 10""").fetchall()
            videos = []
            for r in rows:
                card = waiting_card(conn, r["id"])
                videos.append({"video_id": r["id"], "state": STATE_TEXT[r["state"]],
                               "waiting_on_the_owner": card["kind"] if card else None})
            unseen = conn.execute("""SELECT COUNT(*) FROM messages WHERE seen_at IS NULL
                                     AND role IN ('system', 'card')""").fetchone()[0]
        return json.dumps({"jobs_waiting": list_jobs(), "videos": videos, "news_unseen": unseen})

    # A card that arrives between two waits (the session answers a job, the stage runs on and reaches a gate before
    # the next wait starts) would otherwise go unseen until the wait times out: a wait returns at once for anything
    # that woke since the last one returned. Counted, not timed: the clock can't tell two moments in one tick apart.
    marks = {"woke": 0, "told": 0}

    def note(ev) -> None:
        if ev.kind in WAKE:
            marks["woke"] += 1

    ctx.events.subscribe(note)

    async def wait(args: dict) -> types.CallToolResult:
        seconds = min(max(int(args.get("seconds") or WAIT_MAX), 1), WAIT_MAX)
        missed = marks["woke"] > marks["told"]
        if missed or any(j["taken_min_ago"] is None for j in await asyncio.to_thread(list_jobs)):
            marks["told"] = marks["woke"]
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
        marks["told"] = marks["woke"]
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
        except KeyError as e:
            return _text(f"missing field {e}", error=True)
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

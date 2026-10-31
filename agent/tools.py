"""The chat agent's tools: thin wrappers over core.actions, bound to one chat thread.

In a video thread every tool acts on that thread's video. In a channel's home thread, tools that act on a
video take a `video_id`, which must belong to the channel. There is deliberately no approve, publish or
delete tool: those stay card buttons, so the agent can never pass a gate on the person's behalf.

Numbers are 1-based, as the cards show them: beats, scenes, title options and thumbnail options.
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from claude_agent_sdk import SdkMcpTool, create_sdk_mcp_server, tool

from core import actions, db
from core.errors import ActionError

SERVER = "fleet"

STATE_TEXT = {
    "new": "writing the outline",
    "outlined": "waiting for outline review",
    "outline_approved": "writing the script",
    "scripted": "waiting for script review",
    "generating": "generating voice, pictures and clips",
    "assembled": "waiting for render review",
    "render_approved": "waiting for the Publish click",
    "publishing": "uploading",
    "scheduled": "scheduled on YouTube",
    "live": "live on YouTube",
    "failed": "failed",
    "blocked": "blocked",
}

OUTLINE_OP = {
    "type": "object",
    "properties": {
        "op": {"type": "string",
               "enum": ["set_hook", "set_ending", "edit_beat", "cut_beat", "move_beat", "add_beat"]},
        "beat": {"type": "integer", "description": "Beat number (edit_beat, cut_beat, move_beat)."},
        "to": {"type": "integer", "description": "move_beat: the beat's new position."},
        "after": {"type": "integer", "description": "add_beat: insert after this beat (0 = at the start)."},
        "text": {"type": "string", "description": "set_hook / set_ending: the new text."},
        "label": {"type": "string", "description": "Day label, e.g. 'Day 12'."},
        "title": {"type": "string"},
        "summary": {"type": "string"},
        "skill": {"type": "string", "description": "The survival skill the beat shows."},
        "hero": {"type": "boolean", "description": "Hero beats get AI video clips."},
    },
    "required": ["op"],
    "additionalProperties": False,
}


@dataclass
class Thread:
    id: int
    channel_id: str
    video_id: int | None
    title: str
    sdk_session_id: str | None
    agent_cost_usd: float

    @property
    def home(self) -> bool:
        return self.video_id is None


def load_thread(ctx, thread_id: int) -> Thread:
    with ctx.connect() as conn:
        row = conn.execute("SELECT * FROM threads WHERE id = ?", (thread_id,)).fetchone()
    if row is None:
        raise ValueError(f"no thread {thread_id}")
    return Thread(row["id"], row["channel_id"], row["video_id"], row["title"], row["sdk_session_id"],
                  float(row["agent_cost_usd"]))


def tool_names(tools: list[SdkMcpTool]) -> list[str]:
    return [f"mcp__{SERVER}__{t.name}" for t in tools]


def make_tools(ctx, thread: Thread):
    """The in-process MCP server for one thread."""
    return create_sdk_mcp_server(SERVER, tools=build_tools(ctx, thread))


# --- what the agent sees ---------------------------------------------------------

def _clip(text: str | None, n: int) -> str:
    text = (text or "").strip()
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def _local(ts: float | None) -> str | None:
    return datetime.fromtimestamp(ts).astimezone().isoformat(timespec="minutes") if ts else None


def card_summary(card: dict) -> dict:
    """A compact view of a review card for the model: enough to act on, without media URLs."""
    kind = card["kind"]
    if kind == "outline":
        return {"card": "outline", "version": card["version"], "topic": card["topic"], "hook": card["hook"],
                "ending": card["ending"],
                "beats": [{k: b[k] for k in ("n", "label", "title", "summary", "skill", "hero")} for b in card["beats"]]}
    if kind == "script":
        return {"card": "script", "version": card["version"], "scenes": card["scene_count"],
                "words": card["word_count"], "minutes": card["est_minutes"],
                "beats": [{"n": b["n"], "title": b["title"],
                           "scenes": [{"idx": s["idx"], "narration": _clip(s["narration"], 160)} for s in b["scenes"]]}
                          for b in card["beats"]]}
    if kind == "render":
        picked = card["picked"]
        return {"card": "render", "titles": {i + 1: t for i, t in enumerate(card["titles"])},
                "thumbnails": len(card["thumbs"]),
                "thumbnail_texts": {i + 1: t for i, t in enumerate(card.get("thumb_texts") or [])},
                "picked": {"title": picked["title"],
                           "thumbnail": None if picked["thumb_idx"] is None else picked["thumb_idx"] + 1},
                "cost_usd": card["cost_usd"], "budget_usd": card["budget_usd"],
                "scenes": [{"idx": s["idx"], "beat": s["beat"], "label": s["label"],
                            "narration": _clip(s["narration"], 120), "visual_prompt": _clip(s["visual_prompt"], 120),
                            "regenerated": s["regen_count"]} for s in card["scenes"]]}
    if kind == "publish":
        return {"card": "publish", "title": card["title"], "description": _clip(card["description"], 400),
                "tags": card["tags"], "goes_public": _local(card["publish_at"]), "privacy": card["privacy"],
                "youtube_mode": card["youtube_mode"]}
    if kind == "error":
        return {"card": "error", "state": card["state"], "error": card["error"]}
    return {"card": kind}


def waiting_card(conn, video_id: int) -> dict | None:
    row = conn.execute(
        """SELECT card_json FROM messages WHERE video_id = ? AND role = 'card' AND card_status = 'active'
           AND json_extract(card_json, '$.kind') != 'confirm' ORDER BY id DESC LIMIT 1""",
        (video_id,),
    ).fetchone()
    return json.loads(row["card_json"]) if row else None


def describe(ctx, thread: Thread) -> str:
    """One paragraph of fresh state, sent at the top of every turn."""
    now = datetime.now().astimezone().strftime("%a %d %b %Y %H:%M %Z (UTC%z)")
    with ctx.connect() as conn:
        if thread.home:
            rows = conn.execute(
                """SELECT v.id, v.state, t.title FROM videos v LEFT JOIN topics t ON t.id = v.topic_id
                   WHERE v.channel_id = ? ORDER BY v.id DESC LIMIT 8""", (thread.channel_id,)
            ).fetchall()
            listed = "; ".join(f"#{r['id']} {_clip(r['title'], 50)} ({STATE_TEXT[r['state']]})" for r in rows)
            return f"It is {now}. Recent videos: {listed or 'none yet'}."
        video = db.get_video(conn, thread.video_id)
        card = waiting_card(conn, thread.video_id)
    budget = ctx.channel(video["channel_id"]).budget_usd
    text = (f"It is {now}. Video #{video['id']} is {STATE_TEXT[video['state']]}. "
            f"Cost so far ${video['cost_usd']:.2f} of ${budget:.0f}.")
    if video["error"]:
        text += f" Error: {video['error']}"
    if card:
        version = f" v{card['version']}" if card.get("version", 1) > 1 else ""
        text += f" Waiting on the person: the {card['kind']} card{version}."
    else:
        text += " Nothing is waiting on the person."
    return text


def thread_brief(ctx, thread: Thread) -> str:
    """The fixed facts about a thread, appended to the system prompt."""
    channel = ctx.channel(thread.channel_id)
    root = ctx.config.root
    files = [root / "prompts" / f"{n}.md" for n in ("outline", "script", "visual", "regen")]
    files.append(root / "channels" / f"{channel.id}.yaml")
    lines = [
        f"Channel: {channel.name} (id {channel.id}). Scenario family: {channel.scenario_family}.",
        f"Review gates on this channel: {', '.join(channel.gates)}. Budget per video: ${channel.budget_usd:.0f}.",
    ]
    if thread.home:
        lines.append("This is the channel's home thread. Use new_video to start a video, or start_topic for one of "
                     "the queued topic ideas (topics lists them, with the competitor hits they build on). Tools "
                     "that act on a video need its video_id; the state at the top of each message lists recent "
                     "videos.")
    else:
        lines.append(f"This is the thread for video #{thread.video_id}: \"{thread.title}\". "
                     "Every tool acts on this video.")
    lines.append("Files you may Read, and change with Edit after the person approves the diff:")
    lines += [f"- {p}" for p in files]
    return "\n".join(lines)


# --- the tools ---------------------------------------------------------------------

def _result(text: str, error: bool = False) -> dict[str, Any]:
    out: dict[str, Any] = {"content": [{"type": "text", "text": text}]}
    if error:
        out["is_error"] = True
    return out


def _wrap(fn: Callable[[dict], str]):
    async def handler(args: dict) -> dict[str, Any]:
        try:
            return _result(await asyncio.to_thread(fn, args))  # actions block on SQLite; keep the loop free
        except KeyError as e:
            return _result(f"missing field {e}", error=True)
        except (ActionError, ValueError) as e:
            return _result(str(e), error=True)
    return handler


def build_tools(ctx, thread: Thread) -> list[SdkMcpTool]:
    home = thread.home

    def schema(props: dict, required: tuple = (), video: str = "required") -> dict:
        props, req = dict(props), list(required)
        if home and video != "none":
            props["video_id"] = {"type": "integer", "description": "Which video in this channel, e.g. 12 for #12."}
            if video == "required":
                req.append("video_id")
        return {"type": "object", "properties": props, "required": req, "additionalProperties": False}

    def video_of(args: dict) -> int:
        if not home:
            return thread.video_id
        vid = args.get("video_id")
        if vid is None:
            raise ActionError("say which video (video_id); this is the channel's home thread")
        with ctx.connect() as conn:
            row = conn.execute("SELECT channel_id FROM videos WHERE id = ?", (vid,)).fetchone()
        if row is None or row["channel_id"] != thread.channel_id:
            raise ActionError(f"there is no video #{vid} in this channel")
        return int(vid)

    def state_of(vid: int) -> str:
        with ctx.connect() as conn:
            return db.get_video(conn, vid)["state"]

    # --- handlers ---

    def new_video(args: dict) -> str:
        vid = actions.new_video(ctx, thread.channel_id, args["idea"])
        return f"Started video #{vid}. It's writing the outline; the outline card will appear in the video's thread."

    def status(args: dict) -> str:
        if home and args.get("video_id") is None:
            return json.dumps(actions.status(ctx, channel_id=thread.channel_id))
        vid = video_of(args)
        info = actions.status(ctx, video_id=vid)
        info["state_text"] = STATE_TEXT[info["state"]]
        info["publish_at"] = _local(info["publish_at"])
        with ctx.connect() as conn:
            card = waiting_card(conn, vid)
        info["waiting_on"] = card_summary(card) if card else None
        return json.dumps(info)

    def show(args: dict) -> str:
        actions.show(ctx, video_of(args), args["card"])
        return f"Posted the {args['card']} card again at the bottom of the video's thread."

    def revise(args: dict) -> str:
        actions.revise(ctx, video_of(args), args["gate"], args["note"])
        return f"Sent the {args['gate']} back with the note. A new version gets posted when it's rewritten."

    def regenerate(args: dict) -> str:
        actions.regenerate(ctx, video_of(args), args["gate"])
        return f"Writing a fresh {args['gate']} with the current prompts. A new card gets posted when it's done."

    def edit_outline(args: dict) -> str:
        vid = video_of(args)
        actions.edit_outline(ctx, vid, args["ops"])
        with ctx.connect() as conn:
            card = waiting_card(conn, vid)
        return "Outline updated; the card was re-posted. It now reads: " + json.dumps(card_summary(card))

    def flag_scenes(args: dict) -> str:
        vid, idxs, kind = video_of(args), list(args["idxs"]), args["kind"]
        actions.flag_scenes(ctx, vid, idxs, kind, args.get("note", ""))
        listed = ", ".join(map(str, idxs))
        if state_of(vid) == "blocked":
            return (f"Flagged {listed}, but at least one has been redone {actions.MAX_REGENS} times, so the video is "
                    "blocked. The person (or edit_scene) needs to rewrite that scene's prompt, then Retry.")
        what = "new pictures" if kind == "visual" else "rewritten lines"
        return f"Sent scenes {listed} back for {what}. A new render card comes when they're redone."

    def edit_scene(args: dict) -> str:
        vid, idx = video_of(args), args["idx"]
        actions.edit_scene(ctx, vid, idx, args.get("visual_prompt"), args.get("narration"))
        if state_of(vid) == "blocked":
            return f"Saved scene {idx}. The video is still blocked; the person clicks Retry on the card to go on."
        return f"Saved scene {idx}; it's being regenerated as written."

    def pick(args: dict) -> str:
        title_n, thumb_n, title = args.get("title_idx"), args.get("thumb_idx"), args.get("title")
        if title_n is None and thumb_n is None and title is None:
            raise ActionError("give title_idx, thumb_idx or title")
        actions.pick(ctx, video_of(args), None if title_n is None else title_n - 1,
                     None if thumb_n is None else thumb_n - 1, title)
        done = []
        if title is not None or title_n is not None:
            done.append(f"title \"{title}\"" if title is not None else f"title option {title_n}")
        if thumb_n is not None:
            done.append(f"thumbnail {thumb_n}")
        return "Picked " + " and ".join(done) + "."

    def set_schedule(args: dict) -> str:
        try:
            when = datetime.fromisoformat(args["when"])
        except ValueError:
            raise ActionError(f"can't read {args['when']!r} as an ISO date and time, e.g. 2026-11-03T15:00") from None
        ts = when.timestamp()  # a time without an offset is taken as local time
        actions.update_publish(ctx, video_of(args), publish_at=ts)
        return f"It will go public at {_local(ts)}."

    def update_publish(args: dict) -> str:
        fields = {k: args[k] for k in ("title", "description", "tags") if k in args}
        if not fields:
            raise ActionError("give a title, description or tags")
        actions.update_publish(ctx, video_of(args), **fields)
        return f"Saved the {', '.join(fields)} on the publish card."

    def retry(args: dict) -> str:
        vid = video_of(args)
        actions.retry(ctx, vid)
        return f"Retrying; the video is {STATE_TEXT[state_of(vid)]} again."

    def topics(args: dict) -> str:
        from core import performance
        from stages import topics as topic_stage
        with ctx.connect() as conn:
            rows = performance.ranked_topics(conn, thread.channel_id)
            holds = performance.held(conn, thread.channel_id)
        hits = topic_stage.ranked(ctx, ctx.channel(thread.channel_id))[:8]
        return json.dumps({
            "queued_topics_best_first": [{"topic_id": r["id"], "idea": r["title"], "why": r["why"],
                                          "family": r["family"], "rank": round(r["rank"]), "rank_note": r["note"],
                                          "follow_up_to_a_winner": r["source"] == "own_analytics"} for r in rows],
            "families_on_hold": {f: _local(until) for f, until in holds.items()},
            "competitor_hits": [{"title": h["title"], "channel": h["channel"], "views": h["views"],
                                 "views_per_day": round(h["per_day"])} for h in hits],
        })

    def start_topic(args: dict) -> str:
        vid = actions.start_topic(ctx, args["topic_id"], thread.channel_id)
        return f"Started video #{vid} from topic {args['topic_id']}. It's writing the outline."

    def dismiss_topic(args: dict) -> str:
        actions.dismiss_topic(ctx, args["topic_id"], thread.channel_id)
        return f"Dismissed topic {args['topic_id']}; it won't be proposed again."

    def stop_writing(args: dict) -> str:
        vid = video_of(args)
        actions.stop_writing(ctx, vid)
        return ("Stopping. The video goes back to its card; if Claude was revising with a note, that note is back "
                "in the card's note box for the person to change.")

    def update_video(args: dict) -> str:
        vid = video_of(args)
        actions.suggest_swap(ctx, vid, args.get("reason"))
        return (f"Posted a card in video #{vid}'s thread with its other thumbnails and titles. Nothing changes on "
                "YouTube until the person picks one and clicks Apply.")

    def suggest_topics(args: dict) -> str:
        from stages import topics as topic_stage
        ids = topic_stage.propose(ctx, ctx.channel(thread.channel_id), args.get("count"))
        return f"Queued {len(ids)} topic ideas (topic ids {', '.join(map(str, ids))}); their card is in this thread."

    specs = [
        ("new_video", "Start a new video on this channel from an idea (a survival scenario).",
         schema({"idea": {"type": "string"}}, ("idea",), video="none"), new_video),
        ("status", "Where a video is in the pipeline, its cost, and the full content of the card waiting for review."
         + (" Without video_id, lists this channel's videos." if home else ""),
         schema({}, video="optional"), status),
        ("show", "Post the waiting review card again at the bottom of the thread, e.g. when the person can't find it.",
         schema({"card": {"type": "string", "enum": list(actions.CARD_STATES)}}, ("card",)), show),
        ("revise", "Send the outline or script back to be rewritten, with a note saying what to change. For small "
         "outline changes (move, cut, rename a beat) prefer edit_outline.",
         schema({"gate": {"type": "string", "enum": ["outline", "script"]}, "note": {"type": "string"}},
                ("gate", "note")), revise),
        ("regenerate", "Write the waiting outline or script again from scratch with the current prompts/ files, "
         "keeping every note given so far. Use it after a prompt edit is approved, to see what the new prompt "
         "writes. Inline edits on the waiting card are lost.",
         schema({"gate": {"type": "string", "enum": ["outline", "script"]}}, ("gate",)), regenerate),
        ("edit_outline", "Edit the outline waiting for review without rewriting it. Ops apply in order and each sees "
         "the outline as the previous op left it, so cut several beats from the highest number down.",
         schema({"ops": {"type": "array", "items": OUTLINE_OP, "minItems": 1}}, ("ops",)), edit_outline),
        ("flag_scenes", "At render review, send scenes back. kind=visual makes a new picture (and clip); "
         "kind=narration rewrites and re-voices the line and needs a note saying how.",
         schema({"idxs": {"type": "array", "items": {"type": "integer"}, "minItems": 1},
                 "kind": {"type": "string", "enum": list(actions.FLAG_KINDS)},
                 "note": {"type": "string", "description": "What's wrong / what to change."}},
                ("idxs", "kind")), flag_scenes),
        ("edit_scene", "Rewrite one scene's picture prompt and/or narration exactly as given and regenerate it. "
         "This is also the fix for a blocked scene.",
         schema({"idx": {"type": "integer"}, "visual_prompt": {"type": "string"}, "narration": {"type": "string"}},
                ("idx",)), edit_scene),
        ("pick", "At render review, choose a title option and/or thumbnail option (numbered from 1), or set a "
         "custom title.",
         schema({"title_idx": {"type": "integer", "minimum": 1}, "thumb_idx": {"type": "integer", "minimum": 1},
                 "title": {"type": "string"}}), pick),
        ("set_schedule", "Set when the video goes public. ISO 8601; without an offset it's the person's local time.",
         schema({"when": {"type": "string", "description": "e.g. 2026-11-03T15:00"}}, ("when",)), set_schedule),
        ("update_publish", "Change the title, description or tags on the publish card before the person publishes.",
         schema({"title": {"type": "string"}, "description": {"type": "string"},
                 "tags": {"type": "array", "items": {"type": "string"}}}), update_publish),
        ("retry", "Retry a failed or blocked video from where it stopped.", schema({}), retry),
        ("stop_writing", "Stop Claude while it writes or rewrites an outline or script, e.g. when the person wants "
         "to change the note they sent. The video goes back to its card with that note back in the box.",
         schema({}), stop_writing),
        ("update_video", "For a live video, post a card offering its other thumbnails and titles (from the render "
         "card), e.g. when its click-through is low. It doesn't change anything itself: the person picks and clicks "
         "Apply.", schema({"reason": {"type": "string", "description": "One line on why, shown on the card."}}),
         update_video),
    ]
    if home:
        specs += [
            ("topics", "The queued topic ideas (with topic_id and why) and competitors' recent hits ranked by views "
             "per day, which the ideas build on.", schema({}, video="none"), topics),
            ("start_topic", "Start a video from a queued topic idea.",
             schema({"topic_id": {"type": "integer"}}, ("topic_id",), video="none"), start_topic),
            ("dismiss_topic", "Drop a queued topic idea; it won't be proposed again.",
             schema({"topic_id": {"type": "integer"}}, ("topic_id",), video="none"), dismiss_topic),
            ("suggest_topics", "Ask for new topic ideas now, built on the latest competitor hits (a Claude call, "
             "usually about $0.05). They post as a card here.",
             schema({"count": {"type": "integer", "minimum": 1, "maximum": 6}}, video="none"), suggest_topics),
        ]
    return [tool(name, description, input_schema)(_wrap(fn)) for name, description, input_schema, fn in specs]


def describe_call(name: str, args: dict, root: Path) -> tuple[str, str]:
    """(short tool name, one-line detail) for the muted tool line in the chat."""
    short = name.removeprefix(f"mcp__{SERVER}__")
    if short in ("Read", "Edit"):
        path = Path(str(args.get("file_path", "")))
        try:
            path = path.resolve().relative_to(root.resolve())
        except ValueError:
            pass
        return short, path.as_posix()
    parts: list[str] = []
    if "video_id" in args:
        parts.append(f"#{args['video_id']}")
    if short == "flag_scenes":
        parts += [", ".join(map(str, args.get("idxs", []))), args.get("kind", "")]
    elif short == "edit_outline":
        parts.append(", ".join(_op_text(op) for op in args.get("ops", [])))
    elif short == "edit_scene":
        parts.append(f"scene {args.get('idx')}")
    elif short == "pick":
        parts += [f"{k.removesuffix('_idx')} {args[k]}" for k in ("title_idx", "thumb_idx") if k in args]
        if "title" in args:
            parts.append(f"\"{_clip(args['title'], 60)}\"")
    elif short in ("revise", "regenerate", "show"):
        parts.append(args.get("gate") or args.get("card") or "")
    elif short == "new_video":
        parts.append(_clip(args.get("idea"), 80))
    elif short in ("start_topic", "dismiss_topic"):
        parts.append(f"topic {args.get('topic_id')}")
    elif short == "set_schedule":
        parts.append(args.get("when", ""))
    elif short == "update_publish":
        parts.append(", ".join(k for k in ("title", "description", "tags") if k in args))
    return short, " · ".join(p for p in parts if p)


def _op_text(op: dict) -> str:
    kind = op.get("op", "?")
    if kind == "move_beat":
        return f"move beat {op.get('beat')} to {op.get('to')}"
    if kind in ("cut_beat", "edit_beat"):
        return f"{kind.split('_')[0]} beat {op.get('beat')}"
    if kind == "add_beat":
        return f"add beat after {op.get('after', 'the end')}"
    return kind.replace("_", " ")

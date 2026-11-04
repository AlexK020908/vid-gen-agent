"""The fleet tools: everything the owner does to the channels, run from the Claude Code chat over MCP (served at /mcp
by server/claude_code.py). Thin wrappers over core.actions. They replaced the browser's card buttons and the in-app
chat agent in phase 18 (BUILD.md).

A video tool takes `video_id`. A channel tool takes `channel`, which can be left out while there's one channel.
Numbers are 1-based, as `review` shows them: beats, scenes, title options and thumbnail options.

The tools in ASK spend money or change YouTube. .claude/settings.json makes Claude Code ask the owner before each
one, even in auto mode, so the session can't pass a gate or publish by itself (tests/test_tools.py keeps the
settings file and ASK the same).
"""
from __future__ import annotations

import base64
import io
import json
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import mcp_types as types
from PIL import Image

from core import actions, cards, db, jobs
from core.errors import ActionError

ASK = ("approve", "flag_scenes", "restage", "edit_scene", "retry", "publish", "go_public_now", "apply_swap")

STATE_TEXT = {
    "new": "writing the outline",
    "outlined": "waiting for outline review",
    "outline_approved": "writing the script",
    "scripted": "waiting for script review",
    "generating": "generating voice, pictures and clips",
    "assembled": "waiting for render review",
    "render_approved": "waiting to be published",
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

NEWS_MAX = 40   # news items in one reply; older unseen ones are counted, not listed
THUMB_W = 480   # thumbnails come back this wide


def _text(text: str, error: bool = False) -> types.CallToolResult:
    return types.CallToolResult(content=[types.TextContent(type="text", text=text)], is_error=error)


def _clip(text: str | None, n: int) -> str:
    text = (text or "").strip()
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def _local(ts: float | None) -> str | None:
    return datetime.fromtimestamp(ts).astimezone().isoformat(timespec="minutes") if ts else None


def _picture(path: Path, width: int = THUMB_W) -> types.ImageContent:
    with Image.open(path) as img:
        img = img.convert("RGB")
        img = img.resize((width, round(img.height * width / img.width)))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=85)
    return types.ImageContent(type="image", data=base64.b64encode(buf.getvalue()).decode(), mime_type="image/jpeg")


def card_summary(card: dict) -> dict:
    """A compact view of a card: enough to act on. `review` gives the whole thing."""
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
    if kind == "character":
        return {"card": "character", "people": list(card["people"]), "things": list(card["things"])}
    return _brief(card)


def _brief(card: dict) -> dict:
    """What `news` says about a card: its kind, plus the gist of the ones that aren't reviewed with `review`."""
    kind = card["kind"]
    if kind == "topics":
        return {"card": "topics", "simulated": card["simulated"], "follow_ups_to": card["winner_video_id"],
                "topics": [{"topic_id": t["id"], "idea": t["title"], "why": t["why"], "status": t["status"]}
                           for t in card["topics"]]}
    if kind == "metrics":
        return {"card": "metrics", "after_h": card["after_h"], "views": card["views"], "ctr": card["ctr"],
                "avd_pct": card["avd_pct"], "subs_gained": card["subs_gained"], "verdict": card["verdict"],
                "simulated": card["simulated"]}
    if kind == "swap":
        return {"card": "swap", "reason": card["reason"], "title": card["title"],
                "thumbnail": None if card["thumb_idx"] is None else card["thumb_idx"] + 1}
    return {"card": kind}


def waiting_card(conn, video_id: int) -> dict | None:
    row = conn.execute(
        """SELECT card_json FROM messages WHERE video_id = ? AND role = 'card' AND card_status = 'active'
           AND json_extract(card_json, '$.kind') NOT IN ('confirm', 'metrics') ORDER BY id DESC LIMIT 1""",
        (video_id,),
    ).fetchone()
    return json.loads(row["card_json"]) if row else None


def make_tools(ctx) -> dict[str, tuple[types.Tool, Callable[[dict], Any]]]:
    """name -> (the tool as MCP lists it, its handler). A handler takes the arguments and returns text or a
    CallToolResult; it blocks on SQLite, so the server runs it in a thread."""
    channels = sorted(ctx.config.channels)
    connecting = threading.Lock()  # one Google sign-in at a time

    def obj(props: dict, required: tuple = (), channel: bool = False) -> dict:
        props = dict(props)
        if channel:
            props["channel"] = {"type": "string", "enum": channels,
                                "description": "Which channel; can be left out while there's only one."}
        return {"type": "object", "properties": props, "required": list(required), "additionalProperties": False}

    def video(props: dict | None = None, required: tuple = ()) -> dict:
        return obj({"video_id": {"type": "integer", "description": "Which video, e.g. 12 for #12."}, **(props or {})},
                   ("video_id", *required))

    def channel_of(args: dict) -> str:
        if args.get("channel"):
            ctx.channel(args["channel"])
            return args["channel"]
        if len(channels) == 1:
            return channels[0]
        raise ActionError(f"say which channel ({', '.join(channels)})")

    def video_of(args: dict) -> int:
        vid = int(args["video_id"])
        with ctx.connect() as conn:
            if conn.execute("SELECT 1 FROM videos WHERE id = ?", (vid,)).fetchone() is None:
                raise ActionError(f"there's no video #{vid}")
        return vid

    def state_of(vid: int) -> str:
        with ctx.connect() as conn:
            return db.get_video(conn, vid)["state"]

    def media(url: str | None) -> str | None:
        """A card's /media/... link as the file on this machine."""
        return str(ctx.abs(url.removeprefix("/media/"))) if url else None

    def home_note(channel_id: str, text: str) -> None:
        with ctx.connect() as conn:
            cards.post(ctx, conn, cards.home_thread_id(conn, channel_id), "system", text=text)

    def yours(what: str) -> str:
        """With the session writing (providers.llm: session), the writing a tool sets off is a job for this chat."""
        if ctx.config.provider("llm") != "session":
            return ""
        return f" {what} is a job for you: it shows in `jobs` within seconds (or `wait` for it)."

    # --- reading ---

    def status(args: dict) -> str:
        if args.get("video_id") is not None:
            vid = video_of(args)
            info = actions.status(ctx, video_id=vid)
            info["state_text"] = STATE_TEXT[info["state"]]
            info["publish_at"] = _local(info["publish_at"])
            with ctx.connect() as conn:
                card = waiting_card(conn, vid)
            info["waiting_on_the_owner"] = card_summary(card) if card else None
            return json.dumps(info)
        from youtube import auth
        wanted = [channel_of(args)] if args.get("channel") else channels
        out = {"channels": [], "videos": []}
        with ctx.connect() as conn:
            for cid in wanted:
                c = ctx.channel(cid)
                yt = auth.status(ctx, cid)
                signin_error = conn.execute("SELECT signin_error FROM channels WHERE id = ?", (cid,)).fetchone()[0]
                out["channels"].append({
                    "channel": cid, "name": c.name, "budget_usd": c.budget_usd, "gates": c.gates,
                    "youtube": {"mode": ctx.config.youtube.get("mode", "stub"), "connected": yt["connected"],
                                "signed_in_as": yt["title"], "missing_scopes": yt["missing_scopes"],
                                "client_secret": yt["client_secret"], "signin_error": signin_error or yt["error"]}})
            for cid in wanted:
                for v in actions.status(ctx, channel_id=cid)["videos"]:
                    card = waiting_card(conn, v["id"])
                    out["videos"].append({"video_id": v["id"], "channel": cid, "topic": _clip(v["topic"], 100),
                                          "state": STATE_TEXT[v["state"]], "cost_usd": round(v["cost_usd"], 2),
                                          "waiting_on_the_owner": card["kind"] if card else None})
            out["news_unseen"] = conn.execute("""SELECT COUNT(*) FROM messages WHERE seen_at IS NULL
                                                 AND role IN ('system', 'card')""").fetchone()[0]
        return json.dumps(out)

    def write_script(card: dict) -> Path:
        path = ctx.config.data_dir / "review" / f"video-{card['video_id']}-script-v{card['version']}.md"
        lines = [f"# #{card['video_id']} script, version {card['version']}: {card['topic']}", "",
                 f"{card['scene_count']} scenes, {card['word_count']} words, about {card['est_minutes']} minutes."]
        if card.get("draft_note"):
            lines += ["", f"Your note, taken back by Stop (send it again with revise, changed or not): "
                          f"{card['draft_note']}"]
        if card.get("places"):
            lines += ["", "## Places", *[f"- **{p['name']}**: {p['look']}" for p in card["places"]]]
        for b in card["beats"]:
            lines += ["", f"## Beat {b['n']}. {b['label']}: {b['title']}"]
            for s in b["scenes"]:
                extra = [f"{k.replace('_', ' ')}: {s[k]}" for k in ("place", "tracker", "set_change", "looks") if s.get(k)]
                if s.get("cast"):
                    extra.append("cast: " + ", ".join(s["cast"]))
                if s.get("motion") == "clip":
                    extra.append("clip")
                lines += ["", f"**{s['idx']}.** {s['narration']}", f"> Picture: {s['visual_prompt']}"]
                if extra:
                    lines.append("> " + " · ".join(extra))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path

    def review(args: dict) -> str | types.CallToolResult:
        vid = video_of(args)
        with ctx.connect() as conn:
            row = db.get_video(conn, vid)
            card = waiting_card(conn, vid)
            if card is None:
                return f"Nothing is waiting for the owner on #{vid}; it's {STATE_TEXT[row['state']]}."
            kind = card["kind"]
            if kind in cards.BUILDERS:
                card = cards.build(ctx, conn, vid, kind)  # fresh, not the snapshot that was posted
            blocked = conn.execute(
                """SELECT idx, narration, visual_prompt, regen_count FROM scenes WHERE video_id = ? AND regen_count >= ?
                   ORDER BY idx""", (vid, actions.MAX_REGENS)).fetchall() if kind == "error" else []
        head = f"#{vid} is {STATE_TEXT[row['state']]}. The {kind} card:\n"
        thumbs = json.loads(row["thumbs_json"] or '{"thumbs": []}')["thumbs"]
        if kind == "script":
            path = write_script(card)
            out = {"version": card["version"], "topic": card["topic"], "scenes": card["scene_count"],
                   "words": card["word_count"], "minutes": card["est_minutes"], "draft_note": card["draft_note"],
                   "beats": [{"n": b["n"], "label": b["label"], "title": b["title"],
                              "scenes": f"{b['scenes'][0]['idx']}–{b['scenes'][-1]['idx']}" if b["scenes"] else None}
                             for b in card["beats"]],
                   "full_script": str(path)}
            return head + json.dumps(out, indent=1) + ("\nEvery line and picture prompt is in full_script: read it "
                                                       "there, and give the owner the path to open.")
        if kind == "render":
            picked = card["picked"]
            out = {"topic": card["topic"], "video_file": media(card["video_url"]),
                   "highlight_reel": media(card["highlight_url"]),
                   "minutes": round((card["duration_ms"] or 0) / 60000, 1),
                   "titles": {i + 1: t for i, t in enumerate(card["titles"])},
                   "thumbnails": {i + 1: media(u) for i, u in enumerate(card["thumbs"])},
                   "thumbnail_texts": {i + 1: t for i, t in enumerate(card["thumb_texts"])},
                   "picked": {"title": picked["title"],
                              "thumbnail": None if picked["thumb_idx"] is None else picked["thumb_idx"] + 1},
                   "cost_usd": card["cost_usd"], "budget_usd": card["budget_usd"],
                   "scenes": [{"idx": s["idx"], "beat": s["beat"], "label": s["label"], "motion": s["motion"],
                               "narration": _clip(s["narration"], 140), "regenerated": s["regen_count"]}
                              for s in card["scenes"]]}
            note = ("\nThe thumbnails follow, in order. contact_sheet shows the scenes' pictures. Approving needs a "
                    "title and a thumbnail picked (pick).")
            if card["frames_url"]:
                out["frame_sheet"] = media(card["frames_url"])
                note = "\nA short has no thumbnail: approving needs a title picked (pick). Its frame sheet follows."
                thumbs = [row["frames_path"]]
                out.pop("thumbnails"), out.pop("thumbnail_texts"), out.pop("highlight_reel")
            return types.CallToolResult(content=[
                types.TextContent(type="text", text=head + json.dumps(out, indent=1) + note),
                *[_picture(ctx.abs(p)) for p in thumbs]])
        if kind == "character":
            sheets = [Path(p) for p in (*card["people"].values(), *card["things"].values()) if Path(p).exists()]
            note = "\nTheir sheets follow, in order. Approve to film it, or revise with a note to direct it again."
            return types.CallToolResult(content=[
                types.TextContent(type="text", text=head + json.dumps(card, indent=1) + note),
                *[_picture(p) for p in sheets]])
        if kind == "publish":
            out = {**card, "thumbnail": media(card["thumbnail"]), "goes_public": _local(card["publish_at"])}
            content: list = [types.TextContent(type="text", text=head + json.dumps(out, indent=1))]
            if out["thumbnail"] and Path(out["thumbnail"]).exists():
                content.append(_picture(Path(out["thumbnail"])))
            return types.CallToolResult(content=content)
        if kind == "swap":
            out = {"reason": card["reason"], "live": card["live"], "title": card["title"],
                   "thumbnail": None if card["thumb_idx"] is None else card["thumb_idx"] + 1,
                   "titles": {i + 1: t for i, t in enumerate(card["titles"])},
                   "thumbnails": {i + 1: media(u) for i, u in enumerate(card["thumbs"])}}
            return types.CallToolResult(content=[
                types.TextContent(type="text", text=head + json.dumps(out, indent=1) + "\nThe thumbnails follow."),
                *[_picture(ctx.abs(p)) for p in thumbs]])
        if kind == "error":
            card = {**card, "blocked_scenes": [dict(s) for s in blocked]}
        return head + json.dumps(card, indent=1)

    def news(args: dict) -> str:
        with ctx.connect() as conn, db.tx(conn):
            rows = conn.execute(
                """SELECT m.*, t.channel_id FROM messages m JOIN threads t ON t.id = m.thread_id
                   WHERE m.seen_at IS NULL AND m.role IN ('system', 'card') ORDER BY m.id""").fetchall()
            if rows:
                conn.execute("""UPDATE messages SET seen_at = ? WHERE seen_at IS NULL AND role IN ('system', 'card')
                                AND id <= ?""", (time.time(), rows[-1]["id"]))
        if not rows:
            return "Nothing new since the last look."
        items = []
        for r in rows[-NEWS_MAX:]:
            item = {"when": _local(r["created_at"]), "channel": r["channel_id"], "video_id": r["video_id"],
                    "text": r["text"]}
            if r["card_json"]:
                item.update(_brief(json.loads(r["card_json"])))
            items.append(item)
        older = len(rows) - len(items)
        return json.dumps({"older_not_listed": older, "news": items} if older else {"news": items})

    def topics(args: dict) -> str:
        from core import performance
        from stages import topics as topic_stage
        cid = channel_of(args)
        with ctx.connect() as conn:
            rows = performance.ranked_topics(conn, cid)
            holds = performance.held(conn, cid)
        hits = topic_stage.ranked(ctx, ctx.channel(cid))[:8]
        return json.dumps({
            "queued_topics_best_first": [{"topic_id": r["id"], "idea": r["title"], "why": r["why"],
                                          "family": r["family"], "rank": round(r["rank"]), "rank_note": r["note"],
                                          "follow_up_to_a_winner": r["source"] == "own_analytics"} for r in rows],
            "families_on_hold": {f: _local(until) for f, until in holds.items()},
            "competitor_hits": [{"title": h["title"], "channel": h["channel"], "views": h["views"],
                                 "views_per_day": round(h["per_day"])} for h in hits],
        })

    # --- starting videos ---

    def new_video(args: dict) -> str:
        vid = actions.new_video(ctx, channel_of(args), args["idea"])
        return f"Started video #{vid}." + (yours("The outline") or " It's writing the outline.")

    def next_part(args: dict) -> str:
        vid = actions.next_part(ctx, video_of(args), args.get("idea") or "")
        return (f"Started video #{vid} as the next part. Its outline picks up where this one ended, with the same "
                "cast, places and looks." + yours("The outline"))

    def start_topic(args: dict) -> str:
        vid = actions.start_topic(ctx, args["topic_id"])
        return f"Started video #{vid} from topic {args['topic_id']}." + (yours("The outline")
                                                                          or " It's writing the outline.")

    def dismiss_topic(args: dict) -> str:
        actions.dismiss_topic(ctx, args["topic_id"])
        return f"Dismissed topic {args['topic_id']}; it won't be proposed again."

    def suggest_topics(args: dict) -> str:
        from stages import topics as topic_stage
        try:
            ids = topic_stage.propose(ctx, ctx.channel(channel_of(args)), args.get("count"))
        except jobs.NeedsClaude as e:
            return (f"The topic ideas are a job for you: job {e.job_id}. Once it's answered they're queued and posted "
                    "(news, topics).")
        return f"Queued {len(ids)} topic ideas (topic ids {', '.join(map(str, ids))})."

    # --- the gates ---

    def approve(args: dict) -> str:
        vid, gate = video_of(args), args["gate"]
        actions.approve(ctx, vid, gate)
        return {"outline": f"Approved the outline of #{vid}. The script is written next." + yours("The script"),
                "script": f"Approved the script of #{vid}. The voice, pictures and clips are being made; the render "
                          "card comes when the video is put together.",
                "render": f"Approved the render of #{vid}. The publish card is waiting: review it, then publish.",
                "character": f"Approved the cast of #{vid}. It's being filmed; the render card comes when that's done."}[gate]

    def revise(args: dict) -> str:
        actions.revise(ctx, video_of(args), args["gate"], args["note"])
        return (f"Sent the {args['gate']} back with the note. A new version comes when it's rewritten."
                + yours("The rewrite"))

    def regenerate(args: dict) -> str:
        actions.regenerate(ctx, video_of(args), args["gate"])
        return (f"Writing a fresh {args['gate']} with the current prompts. A new card comes when it's done."
                + yours(f"The {args['gate']}"))

    def edit_outline(args: dict) -> str:
        vid = video_of(args)
        actions.edit_outline(ctx, vid, args["ops"])
        with ctx.connect() as conn:
            card = waiting_card(conn, vid)
        return "Outline updated. It now reads: " + json.dumps(card_summary(card))

    def flag_scenes(args: dict) -> str:
        vid, idxs, kind = video_of(args), list(args["idxs"]), args["kind"]
        actions.flag_scenes(ctx, vid, idxs, kind, args.get("note", ""))
        listed = ", ".join(map(str, idxs))
        if state_of(vid) == "blocked":
            return (f"Flagged {listed}, but at least one has been redone {actions.MAX_REGENS} times, so the video is "
                    "blocked. Rewrite that scene's prompt with edit_scene, then retry.")
        what = "new pictures" if kind == "visual" else "rewritten lines"
        jobs_too = yours("Each scene's rewrite") if args.get("note") else ""
        return f"Sent scenes {listed} back for {what}. A new render card comes when they're redone." + jobs_too

    def restage(args: dict) -> str:
        vid = video_of(args)
        actions.restage(ctx, vid)
        if str(ctx.config.render.get("pictures", "generative")).lower() == "puppet":
            made = ("Staging the whole video again: maps made before the mapping changed and the props list come back "
                    "as looking jobs, then a sheet per scene; new props or crowd puppets are painted (cents).")
        else:
            made = ("Painting the whole video again: every still, each looked at by a picture check (looking jobs), "
                    "then the clips the script chose.")
        return made + " A new render card comes when it's put together again."

    def edit_scene(args: dict) -> str:
        vid, idx = video_of(args), args["idx"]
        actions.edit_scene(ctx, vid, idx, args.get("visual_prompt"), args.get("narration"), args.get("motion"))
        if state_of(vid) in ("blocked", "failed"):
            return f"Saved scene {idx}. The video is still {state_of(vid)}; retry it to go on."
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
        fields = {k: args[k] for k in ("title", "description", "tags", "ai_disclosure") if k in args}
        if not fields:
            raise ActionError("give a title, description, tags or ai_disclosure")
        actions.update_publish(ctx, video_of(args), **fields)
        return f"Saved the {', '.join(fields)} for publishing."

    def publish(args: dict) -> str:
        vid = video_of(args)
        actions.request_publish(ctx, vid)
        with ctx.connect() as conn:
            row = db.get_video(conn, vid)
        live = ctx.config.youtube.get("mode", "stub") == "live"
        where = "Uploading it to YouTube as private" if live else "Publishing in practice mode (nothing is uploaded)"
        return f"{where}; it goes public {_local(row['publish_at'])}. news says when it's scheduled."

    def go_public_now(args: dict) -> str:
        vid = video_of(args)
        actions.go_public_now(ctx, vid)
        return ("It's public on YouTube now. Within a few minutes the app sees it, marks it live and posts the link; "
                "its 48 h and 7 d metrics count from now.")

    def retry(args: dict) -> str:
        vid = video_of(args)
        actions.retry(ctx, vid)
        return f"Retrying; the video is {STATE_TEXT[state_of(vid)]} again."

    def stop_writing(args: dict) -> str:
        actions.stop_writing(ctx, video_of(args))
        return ("Stopping. The video goes back to its card; if it was being revised with a note, that note is kept "
                "as the draft note for the next revise.")

    # --- live videos ---

    def suggest_swap(args: dict) -> str:
        vid = video_of(args)
        actions.suggest_swap(ctx, vid, args.get("reason"))
        return (f"Posted a swap card on #{vid} with its other thumbnails and titles; review shows them. Nothing "
                "changes on YouTube until apply_swap.")

    def apply_swap(args: dict) -> str:
        title_n, thumb_n = args.get("title_idx"), args.get("thumb_idx")
        changed = actions.apply_swap(ctx, video_of(args), None if title_n is None else title_n - 1,
                                     None if thumb_n is None else thumb_n - 1)
        parts = [f"the title to \"{changed['title']}\""] if "title" in changed else []
        if "thumb_idx" in changed:
            parts.append(f"the thumbnail to option {changed['thumb_idx'] + 1}")
        return f"Changed {' and '.join(parts)}."

    def keep_swap(args: dict) -> str:
        actions.keep_swap(ctx, video_of(args))
        return "Kept the title and thumbnail as they are."

    def connect_youtube(args: dict) -> str:
        from youtube import auth
        cid = channel_of(args)
        if not connecting.acquire(blocking=False):
            raise ActionError("a Google sign-in is already waiting in the browser")
        try:
            result = auth.connect(ctx, cid)
        except Exception as e:
            home_note(cid, f"YouTube connect failed: {e}")
            raise
        finally:
            connecting.release()
        home_note(cid, f"Connected to YouTube channel {result['title']} ({result['youtube_channel_id']}).")
        return f"Connected {cid} to the YouTube channel {result['title']} ({result['youtube_channel_id']})."

    gate = {"type": "string", "enum": ["outline", "script"]}
    specs = [
        ("status", "Without video_id: each channel (its YouTube connection and budget), its videos with their "
         "state and what card waits on the owner, and how much news is unseen. With video_id: where that video is, "
         "its cost, metrics, and a summary of the card waiting on the owner.",
         obj({"video_id": {"type": "integer"}}, channel=True), status),
        ("review", "The card waiting on the owner for a video, in full, so you can show them what to decide. "
         "Outline: every beat. Script: a summary, and the whole script written to a file to read and open. "
         "Render: the video and highlight-reel files, the title and thumbnail options (thumbnails as pictures). "
         "Publish: every field and when it goes public. Error: what failed and any blocked scenes. Swap: the options.",
         video(), review),
        ("news", "What the app posted since the last call, oldest first: new cards, notices, sign-in problems, topic "
         "ideas, metrics, published and went live. Each item is shown once.", obj({}), news),
        ("topics", "The queued topic ideas (with topic_id and why) and competitors' recent hits ranked by views "
         "per day, which the ideas build on.", obj({}, channel=True), topics),
        ("new_video", "Start a new video from an idea (a survival scenario).",
         obj({"idea": {"type": "string"}}, ("idea",), channel=True), new_video),
        ("next_part", "Start the next part of a series from this video, once its script is approved. The story, "
         "cast, places, looks and tracker carry on. `idea` is the owner's direction for the new part, or their own "
         "story for it; leave it out to carry the story on.", video({"idea": {"type": "string"}}), next_part),
        ("start_topic", "Start a video from a queued topic idea.",
         obj({"topic_id": {"type": "integer"}}, ("topic_id",)), start_topic),
        ("dismiss_topic", "Drop a queued topic idea; it won't be proposed again.",
         obj({"topic_id": {"type": "integer"}}, ("topic_id",)), dismiss_topic),
        ("suggest_topics", "Ask for new topic ideas now, built on the latest competitor hits.",
         obj({"count": {"type": "integer", "minimum": 1, "maximum": 6}}, channel=True), suggest_topics),
        ("approve", "Approve the outline, script or render card, when the owner says to. Approving the script starts "
         "the paid voice, pictures and clips; approving the render needs a title and thumbnail picked first.",
         video({"gate": {"type": "string", "enum": ["outline", "script", "render", "character"]}}, ("gate",)), approve),
        ("revise", "Send the outline or script back to be rewritten, with a note saying what to change. For small "
         "outline changes (move, cut, rename a beat) use edit_outline.",
         video({"gate": {"type": "string", "enum": ["outline", "script", "character"]}, "note": {"type": "string"}},
               ("gate", "note")), revise),
        ("regenerate", "Write the waiting outline or script again from scratch with the current prompts/ files, "
         "keeping every note given so far. Edits made to the waiting one are lost.",
         video({"gate": gate}, ("gate",)), regenerate),
        ("edit_outline", "Edit the outline waiting for review without rewriting it. Ops apply in order and each sees "
         "the outline as the previous op left it, so cut several beats from the highest number down.",
         video({"ops": {"type": "array", "items": OUTLINE_OP, "minItems": 1}}, ("ops",)), edit_outline),
        ("flag_scenes", "At render review, send scenes back. kind=visual makes a new picture (and clip); "
         "kind=narration rewrites and re-voices the line and needs a note saying how. Costs money.",
         video({"idxs": {"type": "array", "items": {"type": "integer"}, "minItems": 1},
                "kind": {"type": "string", "enum": list(actions.FLAG_KINDS)},
                "note": {"type": "string", "description": "What's wrong / what to change."}}, ("idxs", "kind")),
         flag_scenes),
        ("restage", "Make the whole video's pictures again, keeping the voice, the way render.pictures is set now "
         "(at render review, or when it failed): after the picture pipeline was fixed, or switched. Puppet: maps made "
         "before the mapping changed, the props list and every scene's sheet come back as looking jobs, and new props "
         "or crowd puppets are painted (cents). Painted: every still is painted again (about 4 cents each, with a "
         "picture check for each) and the script's clips made (about 90 cents each). Costs money.", video(), restage),
        ("edit_scene", "Rewrite one scene's picture prompt and/or narration exactly as given and regenerate it, "
         "and/or set its motion (kenburns: a still with a slow pan; clip: animated). A motion change alone keeps the "
         "picture: a clip scene made kenburns drops its clip. At render review, or when the video is blocked or "
         "failed (then retry). This is also the fix for a blocked scene. Costs money.",
         video({"idx": {"type": "integer"}, "visual_prompt": {"type": "string"}, "narration": {"type": "string"},
                "motion": {"type": "string", "enum": ["kenburns", "clip"]}}, ("idx",)), edit_scene),
        ("pick", "At render review, choose a title option and/or thumbnail option (numbered from 1), or set a "
         "custom title.",
         video({"title_idx": {"type": "integer", "minimum": 1}, "thumb_idx": {"type": "integer", "minimum": 1},
                "title": {"type": "string"}}), pick),
        ("set_schedule", "Set when the video goes public. ISO 8601; without an offset it's the owner's local time.",
         video({"when": {"type": "string", "description": "e.g. 2026-11-03T15:00"}}, ("when",)), set_schedule),
        ("update_publish", "Change the title, description, tags or AI-content label before publishing.",
         video({"title": {"type": "string"}, "description": {"type": "string"},
                "tags": {"type": "array", "items": {"type": "string"}}, "ai_disclosure": {"type": "boolean"}}),
         update_publish),
        ("publish", "Publish an approved video, when the owner says to: it's uploaded as private and scheduled to "
         "go public at its time (live YouTube mode), or written out in practice mode.", video(), publish),
        ("go_public_now", "Make a video that's scheduled on YouTube public now instead of at its go-public time, "
         "when the owner says to. Changes YouTube.", video(), go_public_now),
        ("retry", "Retry a failed or blocked video from where it stopped.", video(), retry),
        ("stop_writing", "Stop an outline or script being written or rewritten, e.g. when the owner wants to change "
         "the note they sent. The video goes back to its card.", video(), stop_writing),
        ("suggest_swap", "For a live video, offer its other thumbnails and titles from the render (e.g. when its "
         "click-through is low). Changes nothing by itself.",
         video({"reason": {"type": "string", "description": "One line on why."}}), suggest_swap),
        ("apply_swap", "Change a live video's title and/or thumbnail on YouTube to another option (numbered from "
         "1), when the owner says to.",
         video({"title_idx": {"type": "integer", "minimum": 1}, "thumb_idx": {"type": "integer", "minimum": 1}}),
         apply_swap),
        ("keep_swap", "Close a swap card, keeping the live video's title and thumbnail.", video(), keep_swap),
        ("connect_youtube", "Sign a channel in to YouTube: Google's sign-in page opens in the owner's browser, and "
         "this waits up to 5 minutes for them to finish.", obj({}, channel=True), connect_youtube),
    ]
    return {name: (types.Tool(name=name, description=description, input_schema=schema), fn)
            for name, description, schema, fn in specs}

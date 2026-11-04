"""Publish metadata: description with chapters, default schedule, validation."""
from __future__ import annotations

import json
import sqlite3
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from core.errors import ActionError

DAYS = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
EDITABLE = {"title", "description", "tags", "publish_at", "ai_disclosure"}
DISCLOSURE = "Narration, images and animation in this video were made with AI tools and edited by a person."
LIVE_LEAD_S = 15 * 60  # a real upload takes a while; a publishAt that passes first makes YouTube publish at once


def fmt_ts(ms: int) -> str:
    total = int(ms // 1000)
    hours, rem = divmod(total, 3600)
    minutes, seconds = divmod(rem, 60)
    return f"{hours}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes}:{seconds:02d}"


def next_slot(slot: str, now: datetime | None = None) -> float:
    """'Sat 15:00 America/New_York' -> epoch of the next such slot at least an hour away."""
    day, hm, tz = slot.split()
    zone = ZoneInfo(tz)
    now = (now or datetime.now(zone)).astimezone(zone)
    hour, minute = (int(x) for x in hm.split(":"))
    ahead = (DAYS[day[:3].lower()] - now.weekday()) % 7
    slot_time = (now + timedelta(days=ahead)).replace(hour=hour, minute=minute, second=0, microsecond=0)
    if slot_time <= now + timedelta(hours=1):
        slot_time += timedelta(days=7)
    return slot_time.timestamp()


def free_slot(slots: list[str], taken: list[float], now: datetime | None = None) -> float:
    """The next time in a channel's weekly slots that no other video of theirs goes public, for a channel posting several a
    week. Each slot's next few weeks are tried, soonest first."""
    times = sorted(next_slot(s, now) + week * 7 * 86400 for s in slots for week in range(26))
    return next((t for t in times if all(abs(t - other) >= 3600 for other in taken)), times[-1])


def description(outline: dict, chapters: list[dict], ai_disclosure: bool, previous: str | None = None,
                blurb: str | None = None, credits: list[str] | None = None) -> str:
    """`blurb` is the viewer-facing paragraph Claude writes with the titles (thumbs_json["description"]); videos
    from before it existed fall back to the outline's hook. `previous` is the line pointing back at the part
    before, for a next part already on YouTube. `credits` are the licenses of what's on screen that ask for one."""
    lines = ([previous, ""] if previous else []) + [blurb or outline.get("hook", "")]
    if chapters:
        lines += ["", "Chapters"]
    lines += [f"{fmt_ts(c['t_ms'])} {c['title']}" for c in chapters]
    if credits:
        lines += ["", "3D models:", *credits]
    if ai_disclosure:
        lines += ["", DISCLOSURE]
    return "\n".join(lines).strip()


def publish_meta(ctx, conn: sqlite3.Connection, video: sqlite3.Row) -> dict:
    """What the publish card shows and what publish() sends; saved edits override defaults."""
    channel = ctx.channel(video["channel_id"])
    yt = channel.youtube
    outline = json.loads(video["outline_json"] or "{}")
    chapters = json.loads(video["chapters_json"] or "[]")
    thumbs = json.loads(video["thumbs_json"] or "{}")
    saved = json.loads(video["publish_json"] or "{}")
    ai = bool(saved.get("ai_disclosure", yt.get("ai_disclosure", True)))
    thumb_idx = video["thumb_idx"]
    credits = json.loads(video["direction_json"] or "{}").get("credits")
    meta = {
        "title": video["title"] or outline.get("topic", ""),
        "description": description(outline, chapters, ai, _previous_part(conn, video), thumbs.get("description"), credits),
        "tags": list(yt.get("tags") or ["stick figure", "day by day", "survival"]) + [channel.name.lower()],
        "publish_at": video["publish_at"] or _slot(conn, video, yt),
        "privacy": "private",  # with publishAt set, YouTube flips it public at that time
        "ai_disclosure": ai,
        "made_for_kids": False,
        "category_id": str(yt.get("category_id", 24)),
        "playlist_id": yt.get("playlist_id"),
        "thumbnail": thumbs.get("thumbs", [None] * 3)[thumb_idx] if thumb_idx is not None else None,
        "captions": video["srt_path"],
        "chapters": chapters,
    }
    meta.update({k: v for k, v in saved.items() if k in EDITABLE})
    return meta


def _slot(conn: sqlite3.Connection, video: sqlite3.Row, yt: dict) -> float:
    if not yt.get("publish_slots"):
        return next_slot(yt.get("publish_slot") or "Sat 15:00 UTC")
    taken = [r["publish_at"] for r in conn.execute(
        "SELECT publish_at FROM videos WHERE channel_id = ? AND id != ? AND publish_at IS NOT NULL",
        (video["channel_id"], video["id"]))]
    return free_slot(list(yt["publish_slots"]), taken)


def _previous_part(conn: sqlite3.Connection, video: sqlite3.Row) -> str | None:
    if not video["prev_video_id"]:
        return None
    prev = conn.execute("SELECT part, youtube_id FROM videos WHERE id = ?", (video["prev_video_id"],)).fetchone()
    if not prev or not prev["youtube_id"] or prev["youtube_id"].startswith("stub-"):
        return None
    return f"Part {video['part']}. Missed Part {prev['part'] or 1}? https://youtu.be/{prev['youtube_id']}"


def validate(meta: dict) -> None:
    title = (meta.get("title") or "").strip()
    if not title:
        raise ActionError("the title is empty")
    if len(title) > 100:
        raise ActionError(f"the title is {len(title)} characters; YouTube allows 100")
    if len(meta.get("description") or "") > 5000:
        raise ActionError("the description is over YouTube's 5,000 character limit")
    for field in ("title", "description"):
        if any(ch in (meta.get(field) or "") for ch in "<>"):
            raise ActionError(f"YouTube rejects < and > in the {field}")
    if float(meta.get("publish_at") or 0) < time.time() + 60:
        raise ActionError("the publish time must be in the future")
    chapters = meta.get("chapters") or []
    if chapters and (len(chapters) < 3 or chapters[0]["t_ms"] != 0):
        raise ActionError("YouTube needs at least 3 chapters starting at 0:00")
    if any(b["t_ms"] - a["t_ms"] < 10_000 for a, b in zip(chapters, chapters[1:])):
        raise ActionError("YouTube ignores chapters shorter than 10 seconds")

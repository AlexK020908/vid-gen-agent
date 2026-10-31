"""Series: a video can continue an earlier one as its next part (videos.prev_video_id, videos.part).

The next part's outline is written from the story so far (every earlier part's outline and how it ended on
screen). Returning cast keep their looks word for word, so their reference pictures match. Places continue from
where the earlier parts left them, with the same reference pictures and set changes (core/actions.py
start_generating). The main character's looks and the tracker start where the last part ended. Reference
pictures already drawn for an earlier part are copied instead of drawn again (stages/stills.py).
"""
from __future__ import annotations

import json
import sqlite3

from core import db
from providers import prompts


def earlier_parts(conn: sqlite3.Connection, video: sqlite3.Row) -> list[sqlite3.Row]:
    """The parts before this one, oldest first."""
    parts, prev = [], video["prev_video_id"]
    while prev:
        row = db.get_video(conn, prev)
        parts.insert(0, row)
        prev = row["prev_video_id"]
    return parts


def end_state(conn: sqlite3.Connection, video_id: int) -> tuple[dict, dict]:
    """(tracked amounts, looks) as the video's last scene leaves them; looks as {who: [their looks so far]}."""
    amounts, looks = {}, {}
    for s in db.scenes_for(conn, video_id):
        amounts.update({t["item"]: t["amount"] for t in json.loads(s["tracker_json"] or "[]")})
        looks = looks_of(s)
    return amounts, looks


def looks_of(scene) -> dict[str, list[str]]:
    """A scene's looks_json as {who: [looks so far, newest last]}; scenes written before the history kept only
    the newest."""
    return {who: v if isinstance(v, list) else [v] for who, v in json.loads(scene["looks_json"] or "{}").items()}


def story_so_far(conn: sqlite3.Connection, video: sqlite3.Row) -> str:
    """Every earlier part's outline and how it ended, oldest first, then where things stood at the end."""
    blocks = []
    parts = earlier_parts(conn, video)
    for part in parts:
        lines = [f"Part {part['part'] or 1}:", prompts.outline_text(json.loads(part["outline_json"]))]
        scenes = db.scenes_for(conn, part["id"])
        if scenes:
            lines += ["", "How it ended on screen: " + " ".join(s["narration"] for s in scenes[-3:])]
        blocks.append("\n".join(lines))
    last = parts[-1]
    units = {t["item"]: t["unit"] for t in json.loads(last["outline_json"]).get("tracker") or []}
    amounts, looks = end_state(conn, last["id"])
    if amounts:
        blocks.append("Where the tracker stood at the end: " + "; ".join(
            f"{item} {prompts.amount(a)} {units.get(item, '')}".strip() for item, a in amounts.items()))
    if looks:
        blocks.append("What people had on at the end: " + "; ".join(f"{who}: {chain[-1]}" for who, chain in looks.items()))
    return "\n\n".join(blocks)


def keep_looks(conn: sqlite3.Connection, video: sqlite3.Row, outline: dict) -> None:
    """Returning cast members keep the look an earlier part gave them, word for word, so their reference
    picture is the same one."""
    before = {}
    for part in earlier_parts(conn, video):
        before.update({c["name"].lower(): c["look"] for c in json.loads(part["outline_json"]).get("cast") or []})
    for c in outline.get("cast") or []:
        if c["name"].lower() in before:
            c["look"] = before[c["name"].lower()]


def earlier_places(conn: sqlite3.Connection, video: sqlite3.Row) -> list[dict]:
    """Every place the earlier parts used, as the last part left them: each with its set changes so far."""
    if not video["prev_video_id"]:
        return []
    return json.loads(db.get_video(conn, video["prev_video_id"])["places_json"] or "[]")


def places_text(places: list[dict]) -> str:
    """The earlier parts' places, one per line, as the script turn shows them."""
    if not places:
        return "(none: this is the first part)"
    return "\n".join(f"{p['id']} | {p['name']} | {p['look']}"
                     + (" Since then: " + " ".join(p["changes"]) if p.get("changes") else "") for p in places)

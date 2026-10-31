"""Stage 2: Claude writes the one-page outline. Stops at Gate 1.

A video sent back with a note still has its last outline, and that draft is revised; `regenerate`
clears it, so a fresh outline is written with the current prompts (and every note so far).
"""
import json

from core import db
from core.stage import run_video_stage

NAME = "outline"


def run_once(ctx) -> bool:
    return run_video_stage(ctx, NAME, "new", _work)


def _work(ctx, conn, video) -> None:
    channel = ctx.channel(video["channel_id"])
    topic = conn.execute("SELECT title FROM topics WHERE id = ?", (video["topic_id"],)).fetchone()["title"]
    previous = json.loads(video["outline_json"]) if video["outline_json"] else None
    outline = ctx.llm.outline(channel, topic, db.notes(conn, video["id"], "outline"), previous,
                              ctx.meter(conn, video, NAME, "the outline"))
    with db.tx(conn):
        db.transition(conn, video["id"], "new", "outlined", outline_json=json.dumps(outline), script_json=None,
                      places_json=None)
    ctx.events.emit("gate_reached", video["id"], gate="outline")

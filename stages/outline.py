"""Stage 2: Claude writes the one-page outline. Stops at Gate 1.

A video sent back with a note still has its last outline, and that draft is revised; `regenerate`
clears it, so a fresh outline is written with the current prompts (and every note so far).

The draft is only saved before the reviewer's pass when Stop comes during it (back to that draft): a stage waiting
for the Claude Code session runs again from the top, and must ask for the same outline it asked for before.
"""
import json

from core import db, review, series
from core.errors import Stopped
from core.stage import run_video_stage
from providers import prompts

NAME = "outline"


def run_once(ctx) -> bool:
    return run_video_stage(ctx, NAME, "new", _work)


def _work(ctx, conn, video) -> None:
    channel = ctx.channel(video["channel_id"])
    topic = conn.execute("SELECT title FROM topics WHERE id = ?", (video["topic_id"],)).fetchone()["title"]
    previous = json.loads(video["outline_json"]) if video["outline_json"] else None
    sequel = None
    if video["prev_video_id"]:  # a next part: the story so far, and the owner's direction if they gave one
        sequel = {"part": video["part"], "story": series.story_so_far(conn, video)}
        if topic == f"Part {video['part']}":
            topic = "(nothing: carry the story on the way the last part set it up)"
    notes = db.notes(conn, video["id"], "outline")
    outline = ctx.llm.outline(channel, topic, notes, previous, ctx.meter(conn, video, NAME, "the outline"), sequel)
    try:
        outline = review.reviewed(ctx, conn, video, channel, "outline", {"outline": prompts.outline_text(outline)},
                                  outline, lambda found: ctx.llm.outline(
                                      channel, topic, notes + found, outline,
                                      ctx.meter(conn, video, NAME, "the outline, revised"), sequel))
    except Stopped:  # back to the draft the reviewer was reading (core/stage.py back_to_review)
        db.update_video(conn, video["id"], outline_json=json.dumps(outline))
        raise
    if sequel:
        series.keep_looks(conn, video, outline)
        thread = conn.execute("SELECT title FROM threads WHERE video_id = ?", (video["id"],)).fetchone()
        outline.update(part=video["part"], topic=thread["title"])
    with db.tx(conn):
        db.transition(conn, video["id"], "new", "outlined", outline_json=json.dumps(outline), script_json=None,
                      places_json=None)
    ctx.events.emit("gate_reached", video["id"], gate="outline")

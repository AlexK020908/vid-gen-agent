"""Stage 3: Claude writes the scene-by-scene script. Stops at Gate 1b if the channel has it on.

Like the outline, a script sent back with a note is revised from its last draft; `regenerate`
clears the draft for a fresh one. While it streams, the thread shows how many scenes are written.
The scenes go in script_json and the places they're drawn in go in places_json. As with the outline, the draft
is only saved before the reviewer's pass when Stop comes during it.
"""
import json

from core import actions, db, review, series, transitions
from core.errors import Stopped
from core.stage import run_video_stage
from providers import checks, prompts

NAME = "script"


def run_once(ctx) -> bool:
    return run_video_stage(ctx, NAME, "outline_approved", _work)


def _work(ctx, conn, video) -> None:
    channel = ctx.channel(video["channel_id"])
    outline = json.loads(video["outline_json"])
    previous = ({"places": json.loads(video["places_json"] or "[]"), "scenes": json.loads(video["script_json"])}
                if video["script_json"] else None)

    def progress(n: int) -> None:
        ctx.events.emit("stage_progress", video["id"], stage=NAME, done=n, total=checks.SCENES[1], unit="scenes")

    progress(0)
    notes, earlier = db.notes(conn, video["id"], "script"), series.places_text(series.earlier_places(conn, video))
    script = ctx.llm.script(channel, outline, notes, previous, ctx.meter(conn, video, NAME, "the script"), progress,
                            earlier)
    try:
        script = review.reviewed(ctx, conn, video, channel, "script",
                                 {"outline": prompts.outline_text(outline), "script": prompts.script_text(script)},
                                 script, lambda found: ctx.llm.script(
                                     channel, outline, notes + found, script,
                                     ctx.meter(conn, video, NAME, "the script, revised"), progress, earlier))
        script = transitions.checked_script(ctx, conn, video, channel, outline, script, lambda found: ctx.llm.script(
            channel, outline, notes + found, script, ctx.meter(conn, video, NAME, "the script, revised for its joins"),
            progress, earlier))
    except Stopped:  # back to the draft the reviewer or the check of the joins was reading
        db.update_video(conn, video["id"], script_json=json.dumps(script["scenes"]),
                        places_json=json.dumps(script["places"]))
        raise
    with db.tx(conn):
        db.transition(conn, video["id"], "outline_approved", "scripted", script_json=json.dumps(script["scenes"]),
                      places_json=json.dumps(script["places"]))
        if not channel.script_gate:
            actions.start_generating(conn, video["id"])
    if channel.script_gate:
        ctx.events.emit("gate_reached", video["id"], gate="script")
    else:
        ctx.events.emit("stage_progress", video["id"], stage=NAME, done=len(script["scenes"]),
                        total=len(script["scenes"]))

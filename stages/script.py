"""Stage 3: Claude writes the scene-by-scene script. Stops at Gate 1b if the channel has it on.

Like the outline, a script sent back with a note is revised from its last draft; `regenerate`
clears the draft for a fresh one. While it streams, the thread shows how many scenes are written.
The scenes go in script_json and the places they're drawn in go in places_json.
"""
import json

from core import actions, db, series
from core.stage import run_video_stage
from providers import checks

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
    script = ctx.llm.script(channel, outline, db.notes(conn, video["id"], "script"), previous,
                            ctx.meter(conn, video, NAME, "the script"), progress,
                            series.places_text(series.earlier_places(conn, video)))
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

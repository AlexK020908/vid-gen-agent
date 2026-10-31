"""Stage 8: stitch every scene into the final video, highlight reel, captions and chapters. Stops at Gate 2.

render.engine picks Remotion or ffmpeg. If Remotion fails for any reason, ffmpeg renders instead and the
thread says why, so a broken Node install never blocks a video.

Remotion also draws the corner box with the day and the tracked amounts (statuses below); ffmpeg doesn't.
"""
import json
import logging

from core import db
from core.stage import run_video_stage
from providers import checks
from providers.prompts import amount
from render.render import render_video

log = logging.getLogger("stickfleet.assemble")

NAME = "assemble"
READY = """AND thumbs_json IS NOT NULL
           AND EXISTS (SELECT 1 FROM scenes s WHERE s.video_id = videos.id)
           AND NOT EXISTS (SELECT 1 FROM scenes s WHERE s.video_id = videos.id AND s.state != 'ok')"""


def run_once(ctx) -> bool:
    return run_video_stage(ctx, NAME, "generating", _work, where=READY, lease_s=4 * 3600)


def _work(ctx, conn, video) -> None:
    scenes = db.scenes_for(conn, video["id"])
    outline = json.loads(video["outline_json"])
    beats = outline["beats"]
    items = [{
        "idx": s["idx"], "beat_idx": s["beat_idx"], "narration": s["narration"], "duration_ms": s["duration_ms"],
        "audio": str(ctx.abs(s["audio_path"])), "still": str(ctx.abs(s["still_path"])),
        "clip": str(ctx.abs(s["clip_path"])) if s["motion"] == "clip" and s["clip_path"] else None,
        "words": json.loads(s["words_json"] or "[]"), "status": status,
    } for s, status in zip(scenes, statuses(scenes, outline.get("tracker") or []))]

    def progress(unit: str | None):  # Remotion reports percent, ffmpeg counts scenes
        return lambda done, total: ctx.events.emit("stage_progress", video["id"], stage=NAME, done=done,
                                                   total=total, unit=unit)

    out_dir = ctx.media(video["id"]) / "render"
    engine = ctx.config.render.get("engine", "ffmpeg")
    try:
        result = render_video(items, beats, out_dir, progress("%" if engine == "remotion" else None), engine,
                              ctx.config.render)
    except Exception as e:
        if engine == "ffmpeg":
            raise
        log.exception("%s render failed on video %s; falling back to ffmpeg", engine, video["id"])
        ctx.events.emit("notice", video["id"], text=f"Remotion render failed, so ffmpeg rendered this one "
                                                    f"(no Ken Burns or captions). Reason: {str(e)[:300]}")
        result = render_video(items, beats, out_dir, progress(None), "ffmpeg")
    old = [video["video_path"], video["highlight_path"], video["srt_path"]]
    with db.tx(conn):
        for s, (start, end) in zip(scenes, result["timings"]):
            db.update_scene(conn, s["id"], audio_start_ms=start, audio_end_ms=end)
        db.transition(conn, video["id"], "generating", "assembled",
                      video_path=ctx.rel(result["video"]), highlight_path=ctx.rel(result["highlight"]),
                      srt_path=ctx.rel(result["srt"]), chapters_json=json.dumps(result["chapters"]),
                      duration_ms=result["duration_ms"])
    for rel in old:  # previous pass, replaced by this one
        path = ctx.abs(rel)
        if path:
            path.unlink(missing_ok=True)
    ctx.events.emit("gate_reached", video["id"], gate="render")


def statuses(scenes, tracker: list[dict]) -> list[dict | None]:
    """The corner box for each scene, or None. It shows when a scene starts a new day or changes a tracked amount:
    the day, every tracked amount as it now stands, and an arrow on the ones that just moved. When the story goes
    back in time (after a cold open), the amounts start over, so Day 1's supplies don't show as a jump up."""
    units = {t["item"]: t["unit"] for t in tracker}
    have: dict[str, float] = {}
    out, label, day = [], None, None
    for s in scenes:
        snapshot = {t["item"]: t["amount"] for t in json.loads(s["tracker_json"] or "[]") if t.get("item") in units}
        today = checks._day(s["label"] or "")
        if today is not None and day is not None and today < day:
            have = {}
        moved = {k: v - have[k] for k, v in snapshot.items() if k in have and v != have[k]}
        shows = s["label"] != label or bool(moved) or bool(snapshot.keys() - have.keys())
        have.update(snapshot)
        label, day = s["label"], today if today is not None else day
        if not shows:
            out.append(None)
            continue
        rows = [{"item": item, "amount": amount(have[item]), "unit": unit,
                 "change": f"{'▼' if moved[item] < 0 else '▲'} {amount(abs(moved[item]))}" if item in moved else None,
                 "down": moved.get(item, 0) < 0}
                for item, unit in units.items() if item in have]
        out.append({"day": label or "", "rows": rows})
    return out

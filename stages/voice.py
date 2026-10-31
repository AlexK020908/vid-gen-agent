"""Stage 4: one audio file per scene plus word timestamps. The audio is the timeline."""
import json

from core import db
from core.stage import run_scene_stage

NAME = "voice"


def run_once(ctx) -> bool:
    return run_scene_stage(ctx, NAME, "pending", _work, done_sql="audio_path IS NOT NULL")


def _work(ctx, conn, video, scene) -> tuple[dict, str]:
    channel = ctx.channel(video["channel_id"])
    out = ctx.media(video["id"]) / "audio" / f"s{scene['idx']:03d}_r{scene['regen_count']}.{ctx.tts.ext}"
    before, after = db.neighbors(conn, video["id"], scene["idx"])  # so the voice flows from scene to scene
    with ctx.reserve(conn, video, ctx.tts.price(scene["narration"]), f"voice for scene {scene['idx']}", "tts"):
        result, usd = ctx.tts.speak(channel, scene["narration"], out, before, after)
        ctx.log_cost(conn, video["id"], NAME, "tts", usd)
    return {"audio_path": ctx.rel(out), "duration_ms": result["duration_ms"],
            "words_json": json.dumps(result["words"])}, "voiced"

"""Stage 4: one audio file per scene plus word timestamps. The audio is the timeline."""
import json

from core import db, formats
from core.stage import run_scene_stage
from render import narration

NAME = "voice"
LIFTED = 1.05      # how far a question's voice has to rise at its end (render/narration.py)
RETAKES = 2        # the most a flat question is taken again, at about a cent each


def run_once(ctx) -> bool:
    return run_scene_stage(ctx, NAME, "pending", _work, done_sql="audio_path IS NOT NULL")


def _work(ctx, conn, video, scene) -> tuple[dict, str]:
    channel = ctx.channel(video["channel_id"])
    out = ctx.media(video["id"]) / "audio" / f"s{scene['idx']:03d}_r{scene['regen_count']}.{ctx.tts.ext}"
    before, after = db.neighbors(conn, video["id"], scene["idx"])  # so the voice flows from scene to scene
    with ctx.reserve(conn, video, ctx.tts.price(scene["narration"]), f"voice for scene {scene['idx']}", "tts"):
        result, usd = ctx.tts.speak(channel, scene["narration"], out, before, after)
        ctx.log_cost(conn, video["id"], NAME, "tts", usd)
    if channel.format == formats.CHARACTER:
        out, result = _short_take(ctx, conn, video, channel, scene, out, result, before, after)
    return {"audio_path": ctx.rel(out), "duration_ms": result["duration_ms"],
            "words_json": json.dumps(result["words"])}, "voiced"


def _short_take(ctx, conn, video, channel, scene, out, result, before, after):
    """A short's line cut to its speech. A question has to sound like one: if its end doesn't rise, it's taken again, and
    the take that rose most is kept. Takes vary, so this usually needs one more at most."""
    final, trimmed = narration.trimmed(out, result)
    if not scene["narration"].rstrip().endswith("?"):
        return final, trimmed
    best, lift = (final, trimmed), narration.question_lift(final) or 0.0
    for take in range(1, RETAKES + 1):
        if lift >= LIFTED:
            break
        again = out.with_name(f"{out.stem}_take{take}{out.suffix}")
        with ctx.reserve(conn, video, ctx.tts.price(scene["narration"]), f"another take of scene {scene['idx']}", "tts"):
            raw, usd = ctx.tts.speak(channel, scene["narration"], again, before, after)
            ctx.log_cost(conn, video["id"], NAME, "tts", usd)
        cut = narration.trimmed(again, raw)
        rose = narration.question_lift(cut[0]) or 0.0
        if rose > lift:
            best, lift = cut, rose
    return best

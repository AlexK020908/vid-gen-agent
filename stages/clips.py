"""Stage 6: hero clips for motion=clip scenes, started from the scene's own still.

If a clip would push the video over budget, the scene is downgraded to Ken Burns instead of failing.
Clips run in parallel, so each one holds its price against the budget until it's done (ctx.reserve).
"""
import json

from core import series
from core.stage import run_scene_stage
from providers import checks

NAME = "clips"


def run_once(ctx) -> bool:
    return run_scene_stage(ctx, NAME, "still_done", _work, done_sql="state = 'ok'")


def _work(ctx, conn, video, scene) -> tuple[dict, str]:
    existing = ctx.abs(scene["clip_path"])
    if scene["motion"] != "clip" or (existing and existing.exists()):
        return {}, "ok"
    channel = ctx.channel(video["channel_id"])
    seconds = ctx.video.seconds
    with ctx.reserve(conn, video, ctx.video.price(seconds), f"the clip for scene {scene['idx']}", "video",
                     downgrade=True) as fits:
        if not fits:
            ctx.events.emit("notice", video["id"],
                            text=f"Scene {scene['idx']}: clip downgraded to Ken Burns to stay under budget.")
            return {"motion": "kenburns"}, "ok"
        out = ctx.media(video["id"]) / "clips" / f"s{scene['idx']:03d}_r{scene['regen_count']}.mp4"
        usd = ctx.video.clip(channel, ctx.abs(scene["still_path"]), scene["visual_prompt"], out, seconds,
                             wearing=wearing_of(scene))
        ctx.log_cost(conn, video["id"], NAME, "video", usd)
    return {"clip_path": ctx.rel(out)}, "ok"


def wearing_of(scene) -> str:
    """What the people in the picture have on beyond their usual look (scenes.looks_json), for those the picture
    shows only: the main character when the visual prompt names them, and the scene's cast. A look sent for
    someone who isn't in it gets drawn onto whoever is (video 3: a raider ran down the stairs in the main
    character's knee brace, cane in hand)."""
    shown = set(json.loads(scene["cast_json"] or "[]"))
    if checks.HERO in scene["visual_prompt"].lower():
        shown.add(checks.HERO)
    return "; ".join(f"{who}: {chain[-1]}" for who, chain in series.looks_of(scene).items() if who in shown)

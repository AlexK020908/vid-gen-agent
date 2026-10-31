"""Stage 6: hero clips for motion=clip scenes, started from the scene's own still.

If a clip would push the video over budget, the scene is downgraded to Ken Burns instead of failing.
Clips run in parallel, so each one holds its price against the budget until it's done (ctx.reserve).
"""
from core.stage import run_scene_stage

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
        usd = ctx.video.clip(channel, ctx.abs(scene["still_path"]), scene["visual_prompt"], out, seconds)
        ctx.log_cost(conn, video["id"], NAME, "video", usd)
    return {"clip_path": ctx.rel(out)}, "ok"

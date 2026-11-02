"""Stage 7: 3 thumbnails, 3 titles and the YouTube description. Needs only the script, so it runs alongside the stills.

Claude writes the titles, a few words for each thumbnail and the viewer-facing description (the chapters and the
AI disclosure go under it in core/metadata.py); the picture comes from the image provider and the words are drawn
on in code (providers/images.py caption).
"""
import json
import time

from core import db
from core.stage import run_video_stage
from providers.images import caption

NAME = "thumbs"


def run_once(ctx) -> bool:
    return run_video_stage(ctx, NAME, "generating", _work, where="AND thumbs_json IS NULL")


def _work(ctx, conn, video) -> None:
    channel = ctx.channel(video["channel_id"])
    written = ctx.llm.titles(channel, json.loads(video["outline_json"]), ctx.meter(conn, video, NAME, "the titles"))
    titles, texts = written["titles"][:3], written["thumb_texts"][:3]
    paths = []
    stamp = int(time.time())
    for i, (title, text) in enumerate(zip(titles, texts)):
        out = ctx.media(video["id"]) / "thumbs" / f"t{i}_{stamp}.png"
        with ctx.reserve(conn, video, ctx.images.thumb_price, "a thumbnail", "images"):
            ctx.log_cost(conn, video["id"], NAME, "images", ctx.images.thumbnail(channel, title, i, out))
        caption(out, text)
        paths.append(ctx.rel(out))
    db.update_video(conn, video["id"], thumbs_json=json.dumps({"titles": titles, "thumbs": paths, "texts": texts,
                                                               "description": written.get("description", "")}))
    ctx.events.emit("stage_progress", video["id"], stage=NAME, done=len(paths), total=3,
                    cost_usd=db.get_video(conn, video["id"])["cost_usd"])

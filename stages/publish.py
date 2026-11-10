"""Stage 9: upload private with publishAt, then thumbnail, captions, playlist; or, for a channel on Instagram, post the
short as a Reel there at once (instagram/reels.py), and it's live.

Only runs after `publish`. In youtube.mode (or instagram.mode) stub it writes what it would send and sends nothing.
Live: each finished step is recorded in publish_json["steps"], so a Retry after a failure part-way through
resumes instead of uploading or posting twice.
"""
import json
import time
from datetime import datetime, timezone

from core import db
from core.errors import ActionError
from core.stage import fail, run_video_stage
from youtube import client, quota

NAME = "publish"
# step -> the API call it makes; a step whose call can't be skipped stays in the quota check
STEPS = {"upload": "videos.insert", "thumbnail": "thumbnails.set", "captions": "captions.insert",
         "playlist": "playlistItems.insert"}
MIN_LEAD_S = 10 * 60  # a publishAt in the past makes YouTube publish at once, so don't start that close


def run_once(ctx) -> bool:
    return run_video_stage(ctx, NAME, "publishing", _work, lease_s=3600)


def _request(meta: dict) -> dict:
    publish_at = datetime.fromtimestamp(meta["publish_at"], timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "snippet": {"title": meta["title"], "description": meta["description"], "tags": meta["tags"],
                    "categoryId": meta["category_id"], "defaultLanguage": "en"},
        "status": {"privacyStatus": meta["privacy"], "publishAt": publish_at,
                   "selfDeclaredMadeForKids": meta["made_for_kids"],
                   "containsSyntheticMedia": meta["ai_disclosure"]},
    }


def _work(ctx, conn, video) -> None:
    meta = json.loads(video["publish_json"])
    if meta.get("to") == "instagram":
        _instagram(ctx, conn, video, meta)
        return
    if ctx.config.youtube.get("mode", "stub") != "live":
        request = {
            "videos.insert": {"file": video["video_path"], **_request(meta)},
            "thumbnails.set": meta["thumbnail"],
            "captions.insert": meta["captions"],
            "playlistItems.insert": meta["playlist_id"],
        }
        out = ctx.media(video["id"]) / "publish_request.json"
        out.write_text(json.dumps(request, indent=2), encoding="utf-8")
        youtube_id, live = f"stub-{video['id']}", False
    else:
        try:
            youtube_id = _live(ctx, conn, video, meta)
        except client.YouTubeError as e:
            if e.retriable:
                raise  # counted as an attempt; the stage tries again with backoff
            fail(ctx, conn, video["id"], NAME, str(e), final=True)
            return
        except ActionError as e:  # needs the person: reconnect, quota, phone verification
            fail(ctx, conn, video["id"], NAME, str(e), final=True)
            return
        if youtube_id is None:
            return
        live = True
    with db.tx(conn):
        db.transition(conn, video["id"], "publishing", "scheduled", youtube_id=youtube_id)
    ctx.events.emit("published", video["id"], youtube_id=youtube_id, publish_at=meta["publish_at"], live=live)


def _live(ctx, conn, video, meta: dict) -> str | None:
    steps = meta.setdefault("steps", {})

    def done(step: str, value, **fields) -> None:
        steps[step] = value
        db.update_video(conn, video["id"], publish_json=json.dumps(meta), **fields)

    todo = [s for s in STEPS if s not in steps]
    quota.check(conn, [STEPS[s] for s in todo])  # refuse now rather than stop half-way
    yt = client.Client(ctx, video["channel_id"])

    if "upload" not in steps:
        found = None
        if steps.get("upload_started"):  # an earlier attempt may have finished without us hearing back
            found = yt.find_upload(meta["title"], steps["upload_started"])
        if found:
            ctx.events.emit("notice", video["id"], text=f"Found the earlier upload ({found}); not uploading again.")
        else:
            if meta["publish_at"] < time.time() + MIN_LEAD_S:
                with db.tx(conn):
                    db.transition(conn, video["id"], "publishing", "render_approved")
                ctx.events.emit("notice", video["id"], text="The go-public time has passed (or is minutes away). "
                                                            "Pick a new time, then Publish again.")
                ctx.events.emit("gate_reached", video["id"], gate="publish")
                return None
            steps["upload_started"] = time.time()
            db.update_video(conn, video["id"], publish_json=json.dumps(meta))
            shown = -1

            def progress(fraction: float) -> None:
                nonlocal shown
                pct = int(fraction * 100)
                if pct != shown:
                    shown = pct
                    ctx.events.emit("stage_progress", video["id"], stage="upload", done=pct, total=100, unit="%")

            found = yt.upload(ctx.abs(video["video_path"]), _request(meta), progress)
            progress(1.0)  # the last chunk's reply carries no progress
        done("upload", found, youtube_id=found)
    youtube_id = steps["upload"]

    if "thumbnail" not in steps:
        if meta.get("thumbnail"):
            yt.set_thumbnail(youtube_id, ctx.abs(meta["thumbnail"]))
        done("thumbnail", bool(meta.get("thumbnail")))
    if "captions" not in steps:
        done("captions", yt.insert_captions(youtube_id, ctx.abs(meta["captions"])) if meta.get("captions") else None)
    if "playlist" not in steps:
        done("playlist", yt.add_to_playlist(youtube_id, meta["playlist_id"]) if meta.get("playlist_id") else None)
    return youtube_id


def _instagram(ctx, conn, video, meta: dict) -> None:
    from instagram import auth, reels
    from instagram.client import Client, InstagramError

    if ctx.config.instagram.get("mode", "stub") != "live":
        request = {"account_id": meta["account_id"], "username": meta["username"], "file": video["video_path"],
                   "media_type": "REELS", "caption": meta["caption"], "is_ai_generated": meta["ai_disclosure"]}
        (ctx.media(video["id"]) / "instagram_request.json").write_text(json.dumps(request, indent=2), encoding="utf-8")
        posted, live = {"media_id": f"stub-ig-{video['id']}", "permalink": None}, False
    else:
        steps = meta.setdefault("steps", {})

        def save(_steps) -> None:
            db.update_video(conn, video["id"], publish_json=json.dumps(meta))

        try:
            cl = ctx.instagram or Client(auth.require(), ctx.config.instagram.get("version", "v27.0"))
            reel = ctx.media(video["id"]) / "render" / "instagram.mp4"
            if not steps.get("uploaded"):
                reels.prepare(ctx.abs(video["video_path"]), reel)
            posted = reels.post(cl, meta["account_id"], reel, meta["caption"], meta["ai_disclosure"], steps, save)
        except InstagramError as e:
            if e.retriable:
                raise  # counted as an attempt; the stage tries again with backoff
            fail(ctx, conn, video["id"], NAME, str(e), final=True)
            return
        except ActionError as e:  # no token, or a file Meta won't take: needs the owner
            fail(ctx, conn, video["id"], NAME, str(e), final=True)
            return
        live = True
    with db.tx(conn):
        db.transition(conn, video["id"], "publishing", "live", instagram_id=posted["media_id"],
                      publish_json=json.dumps({**meta, "permalink": posted["permalink"]}))
    ctx.events.emit("published", video["id"], instagram_id=posted["media_id"], permalink=posted["permalink"],
                    username=meta["username"], publish_at=meta["publish_at"], live=live)

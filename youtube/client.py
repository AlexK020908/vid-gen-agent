"""The YouTube Data API calls Stick Fleet makes. Every call is booked in the quota ledger first.

Not built on purpose: deleting videos, playlists, captions or comments, and anything touching channel
ownership or managers. Do those in YouTube Studio.
"""
from __future__ import annotations

import io
import os
from datetime import datetime
from pathlib import Path
from typing import Callable

from google.auth.exceptions import RefreshError
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload, MediaIoBaseUpload
from PIL import Image

from core.errors import ActionError
from youtube import auth, quota

RETRIABLE = {500, 502, 503, 504}
CHUNK = 16 * 1024 * 1024
THUMB_MAX_BYTES = 2 * 1024 * 1024  # YouTube's limit for custom thumbnails
HINTS = {
    "quotaExceeded": "YouTube's daily quota is used up; Retry after midnight Pacific time.",
    "uploadLimitExceeded": "this channel has hit YouTube's upload limit for now; Retry later.",
}
THUMB_HINT = "Custom thumbnails need a phone-verified channel (youtube.com/verify)."
# What videos.update may set in the snippet. It clears anything left out, so a title change sends these back.
WRITABLE_SNIPPET = ("title", "description", "tags", "categoryId", "defaultLanguage", "defaultAudioLanguage")
WRITABLE_STATUS = ("embeddable", "license", "publicStatsViewable", "selfDeclaredMadeForKids", "containsSyntheticMedia")


class YouTubeError(ActionError):
    def __init__(self, message: str, retriable: bool = False) -> None:
        super().__init__(message)
        self.retriable = retriable


def _error(method: str, e: HttpError) -> YouTubeError:
    details = e.error_details if isinstance(e.error_details, list) else []
    reasons = [d.get("reason") for d in details if isinstance(d, dict) and d.get("reason")]
    hint = next((HINTS[r] for r in reasons if r in HINTS), "")
    if method == "thumbnails.set" and e.status_code == 403:
        hint = THUMB_HINT
    code = f" {reasons[0]}" if reasons else ""
    return YouTubeError(f"YouTube {method} failed ({e.status_code}{code}): {e.reason} {hint}".strip(),
                        retriable=e.status_code in RETRIABLE)


def service_for(ctx, channel_id: str):
    if ctx.youtube is not None:
        return ctx.youtube(channel_id)
    return build("youtube", "v3", credentials=auth.credentials(ctx, channel_id), cache_discovery=False)


def api_for(ctx, name: str, version: str, channel_id: str):
    """Another Google API (youtubeAnalytics v2, youtubereporting v1) with the channel's sign-in."""
    if name in ctx.google:
        return ctx.google[name](channel_id)
    return build(name, version, credentials=auth.credentials(ctx, channel_id), cache_discovery=False)


def public_service(ctx):
    """The Data API for public data (competitors' videos), with YOUTUBE_API_KEY: no channel sign-in needed."""
    if "public" in ctx.google:
        return ctx.google["public"](None)
    key = os.environ.get("YOUTUBE_API_KEY")
    if not key:
        raise ActionError("competitor topics need YOUTUBE_API_KEY in .env: in Google Cloud, Credentials, Create "
                          "credentials, API key, restricted to YouTube Data API v3 (see .env.example)")
    return build("youtube", "v3", developerKey=key, cache_discovery=False)


def run(ctx, method: str, request) -> dict:
    """Book `method` in the quota ledger, then execute `request`, with Google's errors made readable."""
    with ctx.connect() as conn:
        quota.spend(conn, method)
    try:
        return request.execute(num_retries=3)
    except HttpError as e:
        raise _error(method, e) from e


def _thumbnail_media(path: Path):
    if path.stat().st_size <= THUMB_MAX_BYTES:
        mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
        return MediaFileUpload(str(path), mimetype=mime)
    buf = io.BytesIO()
    with Image.open(path) as img:
        img.convert("RGB").save(buf, "JPEG", quality=88)
    return MediaIoBaseUpload(buf, mimetype="image/jpeg")


class Client:
    def __init__(self, ctx, channel_id: str) -> None:
        self.ctx = ctx
        self.channel_id = channel_id
        self.yt = service_for(ctx, channel_id)

    def _book(self, method: str) -> None:
        with self.ctx.connect() as conn:
            quota.spend(conn, method)

    def _run(self, method: str, request) -> dict:
        self._book(method)
        try:
            return request.execute(num_retries=3)
        except HttpError as e:
            raise _error(method, e) from e
        except RefreshError as e:
            raise ActionError(f"Connect the channel again: Google refused the stored sign-in ({e})") from e

    def upload(self, path: Path, body: dict, progress: Callable[[float], None] | None = None) -> str:
        """Resumable upload; returns the new video id. `body` holds snippet and status."""
        self._book("videos.insert")
        media = MediaFileUpload(str(path), mimetype="video/mp4", chunksize=CHUNK, resumable=True)
        request = self.yt.videos().insert(part=",".join(body), body=body, media_body=media)
        response = None
        try:
            while response is None:
                status, response = request.next_chunk(num_retries=5)
                if status and progress:
                    progress(status.progress())
        except HttpError as e:
            raise _error("videos.insert", e) from e
        except RefreshError as e:
            raise ActionError(f"Connect the channel again: Google refused the stored sign-in ({e})") from e
        if "id" not in response:
            raise YouTubeError(f"YouTube took the upload but returned no video id: {response}")
        return response["id"]

    def set_thumbnail(self, video_id: str, path: Path) -> None:
        self._run("thumbnails.set", self.yt.thumbnails().set(videoId=video_id, media_body=_thumbnail_media(path)))

    def insert_captions(self, video_id: str, srt: Path, language: str = "en", name: str = "English") -> str:
        body = {"snippet": {"videoId": video_id, "language": language, "name": name, "isDraft": False}}
        media = MediaFileUpload(str(srt), mimetype="application/octet-stream")
        return self._run("captions.insert", self.yt.captions().insert(part="snippet", body=body, media_body=media))["id"]

    def add_to_playlist(self, video_id: str, playlist_id: str) -> str:
        body = {"snippet": {"playlistId": playlist_id, "resourceId": {"kind": "youtube#video", "videoId": video_id}}}
        return self._run("playlistItems.insert", self.yt.playlistItems().insert(part="snippet", body=body))["id"]

    def update_title(self, video_id: str, title: str) -> None:
        """Change a video's title. videos.update clears every snippet field it isn't sent, so the current
        snippet is read first and sent back whole with only the title changed."""
        items = self._run("videos.list", self.yt.videos().list(part="snippet", id=video_id)).get("items") or []
        if not items:
            raise YouTubeError(f"YouTube has no video {video_id} on this channel")
        snippet = {k: v for k, v in items[0]["snippet"].items() if k in WRITABLE_SNIPPET}
        body = {"id": video_id, "snippet": {**snippet, "title": title}}
        self._run("videos.update", self.yt.videos().update(part="snippet", body=body))

    def make_public(self, video_id: str) -> None:
        """Make a video public now, dropping its scheduled publishAt. videos.update resets every status field it
        isn't sent, so the current status is read first and sent back with only the privacy changed."""
        items = self._run("videos.list", self.yt.videos().list(part="status", id=video_id)).get("items") or []
        if not items:
            raise YouTubeError(f"YouTube has no video {video_id} on this channel")
        current = items[0]["status"]
        status = {k: v for k, v in current.items() if k in WRITABLE_STATUS}
        if "selfDeclaredMadeForKids" not in status and "madeForKids" in current:
            status["selfDeclaredMadeForKids"] = current["madeForKids"]
        body = {"id": video_id, "status": {**status, "privacyStatus": "public"}}
        self._run("videos.update", self.yt.videos().update(part="status", body=body))

    def whoami(self) -> str:
        """The YouTube channel id this sign-in is for (1 quota unit): the daily sign-in check."""
        return self._channel("id")["id"]

    def video_views(self, video_id: str) -> int:
        """The public view count, which YouTube updates within minutes (Analytics lags a day or two)."""
        items = self._run("videos.list", self.yt.videos().list(part="statistics", id=video_id)).get("items") or []
        if not items:
            raise YouTubeError(f"YouTube has no video {video_id} on this channel")
        return int(items[0].get("statistics", {}).get("viewCount", 0))

    def video_status(self, video_id: str) -> dict:
        items = self._run("videos.list", self.yt.videos().list(part="status,processingDetails", id=video_id))
        if not items.get("items"):
            raise YouTubeError(f"YouTube has no video {video_id} on this channel")
        video = items["items"][0]
        status = video["status"]
        return {"privacy": status.get("privacyStatus"), "upload": status.get("uploadStatus"),
                "publish_at": status.get("publishAt"),
                "processing": video.get("processingDetails", {}).get("processingStatus")}

    def _channel(self, part: str) -> dict:
        items = self._run("channels.list", self.yt.channels().list(part=part, mine=True)).get("items") or []
        if not items:
            raise ActionError("this sign-in has no YouTube channel; Connect the channel again")
        return items[0]

    def recent_uploads(self, limit: int = 10) -> list[dict]:
        uploads = self._channel("contentDetails")["contentDetails"]["relatedPlaylists"]["uploads"]
        resp = self._run("playlistItems.list",
                         self.yt.playlistItems().list(part="snippet", playlistId=uploads, maxResults=limit))
        return [{"video_id": it["snippet"]["resourceId"]["videoId"], "title": it["snippet"]["title"],
                 "uploaded_at": datetime.fromisoformat(it["snippet"]["publishedAt"].replace("Z", "+00:00")).timestamp()}
                for it in resp.get("items") or []]

    def find_upload(self, title: str, since: float) -> str | None:
        """A video with this title uploaded after `since`: an upload whose reply we never got."""
        for item in self.recent_uploads():
            if item["title"] == title and item["uploaded_at"] >= since - 60:
                return item["video_id"]
        return None

    def channel_overview(self) -> dict:
        channel = self._channel("snippet,statistics")
        stats = channel.get("statistics", {})
        with self.ctx.connect() as conn:
            used = quota.used(conn)
        return {"youtube_channel_id": channel["id"], "title": channel["snippet"]["title"],
                "subscribers": int(stats.get("subscriberCount", 0)), "videos": int(stats.get("videoCount", 0)),
                "views": int(stats.get("viewCount", 0)), "recent": self.recent_uploads(5),
                "quota_used": used, "quota_limits": quota.LIMITS}

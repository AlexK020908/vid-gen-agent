"""Competitors' recent long-form uploads and their view counts, for the topic scorer (stages/topics.py).

Read through the YouTube Data API with YOUTUBE_API_KEY (public data, no sign-in): one channels.list for
every competitor's uploads playlist, one playlistItems.list per competitor, one videos.list per 50 videos.
That's about 3 quota units per competitor per check. YouTube's RSS feeds would cost nothing, but they have
answered 404 for hours at a time since December 2025, so they aren't used.
"""
from __future__ import annotations

import re
import time
from datetime import datetime

from core.errors import ActionError
from youtube import client

DURATION = re.compile(r"P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?$")


def seconds(iso: str) -> int:
    """An ISO 8601 duration as YouTube writes it (PT25M3S) in seconds; 0 if it can't be read."""
    m = DURATION.match(iso or "")
    if not m:
        return 0
    d, h, mi, s = (int(g or 0) for g in m.groups())
    return ((d * 24 + h) * 60 + mi) * 60 + s


def age_days(published_at: float, checked_at: float) -> float:
    """Days since publish when the views were read, at least 1, so a video a few hours old isn't ranked first
    on a handful of views."""
    return max(1.0, (checked_at - published_at) / 86400)


def _ts(rfc3339: str) -> float:
    return datetime.fromisoformat(rfc3339.replace("Z", "+00:00")).timestamp()


def fetch(ctx, competitor_ids: list[str], recent_days: float, min_s: int, max_s: int = 0) -> tuple[list[dict], list[str]]:
    """(videos, competitor ids YouTube doesn't know). Each video: youtube_id, competitor_id, competitor_name,
    title, published_at, duration_s, views."""
    svc = client.public_service(ctx)
    since = time.time() - recent_days * 86400
    channels = client.run(ctx, "channels.list", svc.channels().list(
        part="snippet,contentDetails", id=",".join(competitor_ids), maxResults=50)).get("items") or []
    found = {c["id"]: c for c in channels}
    unknown = [c for c in competitor_ids if c not in found]

    recent: dict[str, dict] = {}  # video id → its channel
    for cid, c in found.items():
        uploads = c.get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads")
        if not uploads:
            continue
        try:
            items = client.run(ctx, "playlistItems.list", svc.playlistItems().list(
                part="contentDetails", playlistId=uploads, maxResults=50)).get("items") or []
        except ActionError as e:
            if "playlistNotFound" in str(e):  # a channel with no public uploads
                continue
            raise
        for it in items:
            details = it.get("contentDetails", {})
            published = details.get("videoPublishedAt")
            if published and _ts(published) >= since:
                recent[details["videoId"]] = c

    videos = []
    ids = list(recent)
    for start in range(0, len(ids), 50):
        batch = ids[start:start + 50]
        items = client.run(ctx, "videos.list", svc.videos().list(
            part="snippet,statistics,contentDetails", id=",".join(batch), maxResults=50)).get("items") or []
        for v in items:
            snippet = v.get("snippet", {})
            length = seconds(v.get("contentDetails", {}).get("duration", ""))
            if length < min_s or (max_s and length > max_s) or snippet.get("liveBroadcastContent", "none") != "none":
                continue  # Shorts and clips (or, for a Shorts channel, long videos), or a stream that's live or upcoming
            c = recent[v["id"]]
            videos.append({
                "youtube_id": v["id"], "competitor_id": c["id"], "competitor_name": c.get("snippet", {}).get("title"),
                "title": snippet.get("title", ""), "published_at": _ts(snippet["publishedAt"]),
                "duration_s": length, "views": int(v.get("statistics", {}).get("viewCount", 0)),
            })
    return videos, unknown


STUB_SETTINGS = ["in a Zombie Apocalypse", "on a Deserted Island", "in Nuclear Winter", "in a Flooded City",
                 "in the Wild West", "in an Ice Age", "in a Haunted Forest", "on Mars"]


def stub(competitor_ids: list[str], now: float | None = None) -> list[dict]:
    """Made-up recent hits for `topics.competitors: stub`, so the topic cards can be tried at $0."""
    now = now or time.time()
    videos = []
    for i, setting in enumerate(STUB_SETTINGS):
        cid = competitor_ids[i % len(competitor_ids)]
        days = 3 + 9 * i
        videos.append({
            "youtube_id": f"stub-{cid[-6:]}-{i}", "competitor_id": cid, "competitor_name": "Made-up competitor",
            "title": f"Day 1 to Day {100 * (i % 3 + 1)} Surviving {setting}", "published_at": now - days * 86400,
            "duration_s": 1500 + 60 * i, "views": int(days * (90_000 - 9_000 * i)),
        })
    return videos

"""Local ledger of YouTube API quota, so a call is refused before Google would refuse it.

Uploads have their own bucket (100 videos.insert calls a day); every other call shares 10,000 units a day.
Both are per Google Cloud project, so one ledger covers every channel. Google resets them at midnight
Pacific time. Costs: https://developers.google.com/youtube/v3/determine_quota_cost
"""
from __future__ import annotations

import sqlite3
from collections import Counter
from datetime import datetime
from typing import Iterable
from zoneinfo import ZoneInfo

from core import db
from core.errors import ActionError

PACIFIC = ZoneInfo("America/Los_Angeles")
LIMITS = {"uploads": 100, "shared": 10_000}
COSTS = {
    "videos.insert": ("uploads", 1),
    "videos.list": ("shared", 1),
    "videos.update": ("shared", 50),
    "channels.list": ("shared", 1),
    "playlistItems.list": ("shared", 1),
    "thumbnails.set": ("shared", 50),
    "playlistItems.insert": ("shared", 50),
    "captions.insert": ("shared", 400),
}


class QuotaExceeded(ActionError):
    pass


def today(now: datetime | None = None) -> str:
    return (now or datetime.now(PACIFIC)).astimezone(PACIFIC).date().isoformat()


def used(conn: sqlite3.Connection, day: str | None = None) -> dict[str, int]:
    out = dict.fromkeys(LIMITS, 0)
    for row in conn.execute("SELECT bucket, units FROM quota WHERE date = ?", (day or today(),)):
        out[row["bucket"]] = row["units"]
    return out


def need(methods: Iterable[str]) -> dict[str, int]:
    total: Counter[str] = Counter()
    for method in methods:
        bucket, units = COSTS[method]
        total[bucket] += units
    return dict(total)


def check(conn: sqlite3.Connection, methods: Iterable[str]) -> None:
    """Raise unless all of these calls fit in what's left of today's quota."""
    have = used(conn)
    for bucket, units in need(methods).items():
        if have[bucket] + units > LIMITS[bucket]:
            raise QuotaExceeded(
                f"not enough YouTube {bucket} quota left today: {have[bucket]:,} of {LIMITS[bucket]:,} used, "
                f"this needs {units:,}. It resets at midnight Pacific time; Retry after that."
            )


def spend(conn: sqlite3.Connection, method: str) -> None:
    """Record one call (before making it: Google counts failed calls too)."""
    bucket, units = COSTS[method]
    with db.tx(conn):
        check(conn, [method])
        conn.execute(
            """INSERT INTO quota (date, bucket, units) VALUES (?, ?, ?)
               ON CONFLICT(date, bucket) DO UPDATE SET units = units + excluded.units""",
            (today(), bucket, units),
        )

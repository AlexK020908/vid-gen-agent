"""Impressions and click-through rate, from the YouTube Reporting API's channel_reach_basic_a1 report.

The Analytics API has no impressions or CTR, so each connected channel gets a reporting job (created the
first time reach is imported). YouTube then writes one CSV per day (Pacific days, a day or two late; the
first ones within 48 hours, with 30 days of history), kept 30-60 days. Each import downloads the reports
created since the last one; a newer report for a day already imported replaces it (YouTube's backfills).
"""
from __future__ import annotations

import csv
import io
from datetime import date, datetime

from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload

from core import db
from youtube import client
from youtube.quota import PACIFIC

REPORT_TYPE = "channel_reach_basic_a1"
JOB_NAME = "Stick Fleet reach"


def _execute(method: str, request) -> dict:
    """Reporting API calls have their own quota, so they aren't booked in the Data API ledger."""
    try:
        return request.execute(num_retries=3)
    except HttpError as e:
        raise client._error(method, e) from e


def _download(svc, url: str) -> bytes:
    """Google's documented way to fetch a report: a media request pointed at its downloadUrl."""
    request = svc.media().download(resourceName=" ")
    request.uri = url
    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, request, chunksize=-1)
    done = False
    while not done:
        _, done = downloader.next_chunk(num_retries=3)
    return buf.getvalue()


def day_of(rfc3339: str) -> str:
    """The Pacific date a report covers, from its startTime."""
    return datetime.fromisoformat(rfc3339.replace("Z", "+00:00")).astimezone(PACIFIC).date().isoformat()


def parse(text: str) -> dict[str, tuple[int, float | None]]:
    """video id → (impressions, CTR as the report gives it), summed over the report's other dimensions."""
    totals: dict[str, list[float]] = {}
    for row in csv.DictReader(io.StringIO(text)):
        video = row.get("video_id")
        if not video:
            continue
        impressions = int(float(row.get("video_thumbnail_impressions") or 0))
        ctr = float(row.get("video_thumbnail_impressions_ctr") or 0)
        t = totals.setdefault(video, [0, 0.0])
        t[0] += impressions
        t[1] += impressions * ctr
    return {v: (int(n), (clicks / n if n else None)) for v, (n, clicks) in totals.items()}


def ensure_job(ctx, conn, channel_id: str, svc) -> str:
    row = conn.execute("SELECT reach_job_id FROM channels WHERE id = ?", (channel_id,)).fetchone()
    if row["reach_job_id"]:
        return row["reach_job_id"]
    jobs = _execute("jobs.list", svc.jobs().list()).get("jobs") or []
    job = next((j for j in jobs if j.get("reportTypeId") == REPORT_TYPE), None)  # one made earlier
    if job is None:
        job = _execute("jobs.create", svc.jobs().create(body={"reportTypeId": REPORT_TYPE, "name": JOB_NAME}))
    conn.execute("UPDATE channels SET reach_job_id = ? WHERE id = ?", (job["id"], channel_id))
    return job["id"]


def import_new(ctx, channel_id: str) -> list[str]:
    """Download the reach reports created since the last import. Returns the days stored."""
    svc = client.api_for(ctx, "youtubereporting", "v1", channel_id)
    with ctx.connect() as conn:
        job = ensure_job(ctx, conn, channel_id, svc)
        after = conn.execute("SELECT reach_after FROM channels WHERE id = ?", (channel_id,)).fetchone()[0]
    reports, token = [], None
    while True:
        params = {"jobId": job, **({"createdAfter": after} if after else {}), **({"pageToken": token} if token else {})}
        page = _execute("jobs.reports.list", svc.jobs().reports().list(**params))
        reports += page.get("reports") or []
        token = page.get("nextPageToken")
        if not token:
            break

    stored = []
    for report in sorted(reports, key=lambda r: r["createTime"]):
        day = day_of(report["startTime"])
        with ctx.connect() as conn:
            have = conn.execute("SELECT created FROM reach_days WHERE channel_id = ? AND day = ?",
                                (channel_id, day)).fetchone()
        if have and have["created"] >= report["createTime"]:
            continue
        rows = parse(_download(svc, report["downloadUrl"]).decode("utf-8-sig"))
        with ctx.connect() as conn, db.tx(conn):
            for video, (impressions, ctr) in rows.items():
                conn.execute("INSERT OR REPLACE INTO reach (youtube_id, day, impressions, ctr) VALUES (?, ?, ?, ?)",
                             (video, day, impressions, ctr))
            conn.execute("INSERT OR REPLACE INTO reach_days (channel_id, day, report_id, created) VALUES (?, ?, ?, ?)",
                         (channel_id, day, report["id"], report["createTime"]))
        stored.append(day)
    if reports:
        newest = max(r["createTime"] for r in reports)
        with ctx.connect() as conn:
            conn.execute("UPDATE channels SET reach_after = ? WHERE id = ?", (newest, channel_id))
    return stored


def window(conn, channel_id: str, youtube_id: str, days: list[str]) -> tuple[int, float | None] | None:
    """(impressions, CTR) over `days`, or None until every one of those days has been imported."""
    have = {r["day"] for r in conn.execute(
        f"SELECT day FROM reach_days WHERE channel_id = ? AND day IN ({','.join('?' * len(days))})",
        (channel_id, *days))}
    if have != set(days):
        return None
    rows = conn.execute(f"SELECT impressions, ctr FROM reach WHERE youtube_id = ? AND day IN "
                        f"({','.join('?' * len(days))})", (youtube_id, *days)).fetchall()
    impressions = sum(r["impressions"] for r in rows)
    clicks = sum(r["impressions"] * (r["ctr"] or 0) for r in rows)
    return impressions, (clicks / impressions if impressions else None)


def pacific_days(start: float, end: float) -> list[str]:
    """Every Pacific date from the one holding `start` through the one holding `end`."""
    first = datetime.fromtimestamp(start, PACIFIC).date().toordinal()
    last = datetime.fromtimestamp(end, PACIFIC).date().toordinal()
    return [date.fromordinal(n).isoformat() for n in range(first, last + 1)]

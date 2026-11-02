"""Stage 10: confirm scheduled videos went public, then record how each is doing 48 h and 7 days later.

Metrics: views from the Data API (YouTube's public count, minutes behind), average view duration and
percentage and subscribers gained from the Analytics API (a day or two behind, so the 48 h numbers are
partial), and impressions and click-through rate from the Reporting API's daily reach files
(youtube/reporting.py), filled in when every day of the window has arrived. Each reading posts a card in
the video's thread. A metrics problem never fails a live video: it's posted once and tried again later.
With youtube.mode: stub, or a video uploaded in stub mode, the numbers are made up and marked so.

A complete reading is judged against the channel's medians (core/performance.py), which can queue follow-up
ideas, suggest a thumbnail/title swap, or hold a topic family. Once a day each connected channel's sign-in is
checked, so a refused token shows up in the home thread before the next publish needs it.
"""
import logging
import time
from datetime import datetime

from googleapiclient.errors import HttpError

from core import cards, db, performance
from core.errors import ActionError
from core.stage import fail, run_video_stage
from youtube import auth, client, reporting
from youtube.quota import PACIFIC

NAME = "analytics"
RECHECK_S = 15 * 60
GIVE_UP_S = 24 * 3600
WINDOWS_H = (48, 168)
METRICS_RETRY_S = 3600
REACH_EVERY_S = 6 * 3600  # reach files land once a day, at no fixed hour
SIGNIN_EVERY_S = 24 * 3600
SIGNIN_RETRY_S = 3600
ANALYTICS = "views,averageViewDuration,averageViewPercentage,subscribersGained"

log = logging.getLogger("stickfleet.analytics")


def run_once(ctx) -> bool:
    went_live = run_video_stage(ctx, NAME, "scheduled", _work, where="AND publish_at <= ?", params=(time.time(),))
    measured = _measure_once(ctx)
    reach = _reach_once(ctx)
    signin = _signin_once(ctx)
    return went_live or measured or reach or signin


def _work(ctx, conn, video) -> float | None:
    stub_upload = (video["youtube_id"] or "").startswith("stub-")  # published before youtube.mode went live
    if ctx.config.youtube.get("mode", "stub") == "live" and not stub_upload:
        try:
            status = client.Client(ctx, video["channel_id"]).video_status(video["youtube_id"])
        except ActionError as e:
            if getattr(e, "retriable", False):
                return RECHECK_S
            fail(ctx, conn, video["id"], NAME, str(e), final=True)
            return None
        if status["upload"] in ("rejected", "failed", "deleted"):
            fail(ctx, conn, video["id"], NAME, f"YouTube says the upload is {status['upload']}; open it in Studio",
                 final=True)
            return None
        if status["privacy"] != "public":
            if time.time() > video["publish_at"] + GIVE_UP_S:
                fail(ctx, conn, video["id"], NAME, f"still {status['privacy']} a day after its go-public time; "
                                                   "check it in Studio, then Retry", final=True)
                return None
            return RECHECK_S  # YouTube flips it a little after publishAt; look again later
    with db.tx(conn):
        db.transition(conn, video["id"], "scheduled", "live")
    ctx.events.emit("went_live", video["id"])
    return None


# --- metrics at 48 h and 7 days ---------------------------------------------------------------------

def _due_sql() -> str:
    return " OR ".join(f"(publish_at + {h * 3600} <= ? AND NOT EXISTS (SELECT 1 FROM metrics m "
                       f"WHERE m.video_id = videos.id AND m.after_h = {h}))" for h in WINDOWS_H)


def _measure_once(ctx) -> bool:
    now = time.time()
    with ctx.connect() as conn:
        video = db.claim_video(conn, "live", ctx.lease_s, f"AND ({_due_sql()})", (now,) * len(WINDOWS_H))
        if video is None:
            return False
        have = {r[0] for r in conn.execute("SELECT after_h FROM metrics WHERE video_id = ?", (video["id"],))}
        after_h = next(h for h in WINDOWS_H if h not in have and video["publish_at"] + h * 3600 <= now)
        try:
            values = _read(ctx, conn, video, after_h)
        except (ActionError, HttpError) as e:
            message = f"Couldn't read the numbers at {_label(after_h)}: {e}. Trying again in an hour."
            if message != video["error"]:
                cards.post(ctx, conn, cards.thread_id(conn, video["id"]), "system", text=message,
                           video_id=video["id"])
            db.update_video(conn, video["id"], lease_until=now + METRICS_RETRY_S, error=message)
            return True
        with db.tx(conn):
            conn.execute(
                """INSERT INTO metrics (video_id, captured_at, after_h, views, avd_seconds, avd_pct, impressions, ctr,
                     subs_gained, simulated) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (video["id"], now, after_h, values["views"], values["avd_seconds"], values["avd_pct"],
                 values["impressions"], values["ctr"], values["subs_gained"], values["simulated"]))
            db.update_video(conn, video["id"], lease_until=None, error=None)
    ctx.events.emit("metrics", video["id"], after_h=after_h)
    performance.judge(ctx, video["id"], after_h)  # waits for the CTR if the reach files aren't in yet
    return True


def _label(after_h: int) -> str:
    return f"{after_h} hours" if after_h < 72 else f"{after_h // 24} days"


def _pacific(ts: float) -> str:
    return datetime.fromtimestamp(ts, PACIFIC).date().isoformat()


def _read(ctx, conn, video, after_h: int) -> dict:
    if ctx.config.youtube.get("mode", "stub") != "live" or (video["youtube_id"] or "").startswith("stub-"):
        return _made_up(video, after_h)
    youtube_id = video["youtube_id"]
    views = client.Client(ctx, video["channel_id"]).video_views(youtube_id)
    analytics = client.api_for(ctx, "youtubeAnalytics", "v2", video["channel_id"])
    try:
        table = analytics.reports().query(ids="channel==MINE", startDate=_pacific(video["publish_at"]),
                                          endDate=_pacific(time.time()), metrics=ANALYTICS,
                                          filters=f"video=={youtube_id}").execute(num_retries=3)
    except HttpError as e:
        raise client._error("reports.query", e) from e
    names = [c["name"] for c in table.get("columnHeaders") or []]
    row = dict(zip(names, (table.get("rows") or [[]])[0]))
    days = reporting.pacific_days(video["publish_at"], video["publish_at"] + after_h * 3600 - 1)
    reach = reporting.window(conn, video["channel_id"], youtube_id, days)
    return {"views": views, "avd_seconds": row.get("averageViewDuration"), "avd_pct": row.get("averageViewPercentage"),
            "subs_gained": row.get("subscribersGained"), "impressions": reach[0] if reach else None,
            "ctr": reach[1] if reach else None, "simulated": 0}


def _made_up(video, after_h: int) -> dict:
    """Stub numbers, the same for the same video, so the cards can be tried."""
    views = (1200 + 137 * (video["id"] % 7)) * (1 if after_h == 48 else 3)
    pct = 42.0 - video["id"] % 5
    return {"views": views, "avd_seconds": round((video["duration_ms"] or 1_500_000) / 1000 * pct / 100),
            "avd_pct": pct, "subs_gained": views // 150, "impressions": views * 11,
            "ctr": 3.5 + 0.8 * (video["id"] % 4), "simulated": 1}


# --- reach (impressions, CTR) from the Reporting API -------------------------------------------------

def _reach_once(ctx) -> bool:
    if ctx.config.youtube.get("mode", "stub") != "live" or not ctx.config.youtube.get("reach", True):
        return False
    now = time.time()
    did = False
    for channel in ctx.config.channels.values():
        with ctx.connect() as conn:
            row = conn.execute("SELECT reach_checked_at, reach_error FROM channels WHERE id = ?",
                               (channel.id,)).fetchone()
        if row["reach_checked_at"] and now - row["reach_checked_at"] < REACH_EVERY_S:
            continue
        try:
            if not auth.stored(channel.id):
                continue
            reporting.import_new(ctx, channel.id)
            error = None
        except Exception as e:  # say why once; the next check is REACH_EVERY_S later anyway
            error = str(e) or type(e).__name__
        with ctx.connect() as conn:
            conn.execute("UPDATE channels SET reach_checked_at = ?, reach_error = ? WHERE id = ?",
                         (now, error, channel.id))
            if error and error != row["reach_error"]:
                cards.post(ctx, conn, cards.home_thread_id(conn, channel.id), "system",
                           text=f"Couldn't fetch YouTube's impressions report: {error}")
        if error is None:
            _fill_reach(ctx, channel.id)
        did = True
    return did


def _fill_reach(ctx, channel_id: str) -> None:
    """Fill impressions and CTR into readings whose every day has now arrived."""
    with ctx.connect() as conn:
        rows = conn.execute(
            """SELECT m.rowid AS id, m.video_id, m.after_h, v.youtube_id, v.publish_at FROM metrics m
               JOIN videos v ON v.id = m.video_id
               WHERE v.channel_id = ? AND m.impressions IS NULL AND m.simulated = 0""", (channel_id,)).fetchall()
        for r in rows:
            days = reporting.pacific_days(r["publish_at"], r["publish_at"] + r["after_h"] * 3600 - 1)
            reach = reporting.window(conn, channel_id, r["youtube_id"], days)
            if reach is None:
                continue
            conn.execute("UPDATE metrics SET impressions = ?, ctr = ? WHERE rowid = ?", (*reach, r["id"]))
            ctx.events.emit("metrics_updated", r["video_id"], after_h=r["after_h"])
            performance.judge(ctx, r["video_id"], r["after_h"])


# --- the daily sign-in check ---------------------------------------------------------------------------

def _signin_once(ctx) -> bool:
    if ctx.config.youtube.get("mode", "stub") != "live" or not ctx.config.youtube.get("signin_check", True):
        return False
    now = time.time()
    did = False
    for channel in ctx.config.channels.values():
        with ctx.connect() as conn:
            row = conn.execute("SELECT signin_checked_at, signin_error FROM channels WHERE id = ?",
                               (channel.id,)).fetchone()
        if row["signin_checked_at"] and now - row["signin_checked_at"] < SIGNIN_EVERY_S:
            continue
        try:
            if not auth.stored(channel.id):
                continue
        except Exception:  # the keychain itself is unavailable; `status` already says so
            continue
        checked_at, error = now, None
        try:
            seen = client.Client(ctx, channel.id).whoami()
            expected = channel.youtube.get("channel_id")
            if expected and seen != expected:
                error = (f"the stored sign-in is for YouTube channel {seen}, not {expected}; connect again (connect_youtube) and pick "
                         "the right brand channel")
        except ActionError as e:
            if getattr(e, "retriable", False):  # YouTube had a moment; look again in an hour
                checked_at = now - SIGNIN_EVERY_S + SIGNIN_RETRY_S
            else:
                error = str(e)
        except Exception:  # no network, most likely: look again in an hour without crying wolf
            log.warning("sign-in check for %s failed", channel.id, exc_info=True)
            checked_at = now - SIGNIN_EVERY_S + SIGNIN_RETRY_S
        with ctx.connect() as conn:
            conn.execute("UPDATE channels SET signin_checked_at = ?, signin_error = ? WHERE id = ?",
                         (checked_at, error, channel.id))
            home = cards.home_thread_id(conn, channel.id)
            if error and error != row["signin_error"]:
                cards.post(ctx, conn, home, "system", text=f"YouTube sign-in check failed: {error}. Publishing will "
                                                           "fail until it's fixed (Reconnect under the channel).")
            elif not error and row["signin_error"]:
                cards.post(ctx, conn, home, "system", text="The YouTube sign-in works again.")
        did = True
    return did

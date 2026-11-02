"""How a channel's videos do against each other, and what the pipeline does about it (plan.md "Month 2 on").

A reading (48 hours or 7 days after going public) is judged once it's complete (its CTR has arrived), against
the median of the channel's last ROLLING readings at the same point: above on both AVD % and CTR is a winner,
below on both a loser, anything else mixed. Until MIN_VIDEOS readings exist there's nothing to compare to, so
it's "early" and nothing happens. Then:

- a 48-hour winner queues follow-up ideas at the top of the topic queue (the surge);
- a 48-hour reading with CTR below the median posts a thumbnail/title swap card;
- a 7-day loser holds its topic's family (the setting tag each idea gets) for HOLD_DAYS: queued topics in
  that family drop to the bottom and new ideas avoid it.

Queued topics are ranked by competitor views per day, times what the channel's own winners and losers over
the last OWN_DAYS say about their family.
"""
from __future__ import annotations

import json
import logging
import statistics
import time

from core import cards, db, jobs

MIN_VIDEOS = 3   # readings needed before a median means anything
ROLLING = 10     # the medians use the channel's latest 10 readings at the same point
HOLD_DAYS = 28
OWN_DAYS = 56
FOLLOW_UPS = 2

log = logging.getLogger("stickfleet.performance")


def medians(conn, channel_id: str, after_h: int, exclude_video: int, simulated: int) -> dict | None:
    rows = conn.execute(
        """SELECT m.avd_pct, m.ctr FROM metrics m JOIN videos v ON v.id = m.video_id
           WHERE v.channel_id = ? AND m.after_h = ? AND m.video_id != ? AND m.simulated = ?
             AND m.avd_pct IS NOT NULL AND m.ctr IS NOT NULL
           ORDER BY m.captured_at DESC LIMIT ?""",
        (channel_id, after_h, exclude_video, simulated, ROLLING)).fetchall()
    if len(rows) < MIN_VIDEOS:
        return None
    return {"avd_pct": statistics.median(r["avd_pct"] for r in rows),
            "ctr": statistics.median(r["ctr"] for r in rows), "n": len(rows)}


def verdict(reading, med: dict) -> str:
    if reading["avd_pct"] > med["avd_pct"] and reading["ctr"] > med["ctr"]:
        return "winner"
    if reading["avd_pct"] < med["avd_pct"] and reading["ctr"] < med["ctr"]:
        return "loser"
    return "mixed"


def judge(ctx, video_id: int, after_h: int) -> str | None:
    """Judge a complete reading once and act on it. Returns the verdict, or None if it isn't ready or was judged."""
    with ctx.connect() as conn:
        video = db.get_video(conn, video_id)
        m = conn.execute("SELECT * FROM metrics WHERE video_id = ? AND after_h = ?", (video_id, after_h)).fetchone()
        if m is None or m["verdict"] is not None or m["ctr"] is None or m["avd_pct"] is None:
            return None
        med = medians(conn, video["channel_id"], after_h, video_id, m["simulated"])
        result = verdict(m, med) if med else "early"
        conn.execute("""UPDATE metrics SET verdict = ?, median_avd_pct = ?, median_ctr = ?, median_n = ?
                        WHERE video_id = ? AND after_h = ?""",
                     (result, med and med["avd_pct"], med and med["ctr"], med and med["n"], video_id, after_h))
    ctx.events.emit("metrics_updated", video_id, after_h=after_h)
    if med is None:
        return result
    channel = ctx.channel(video["channel_id"])
    if after_h == 48 and result == "winner":
        _surge(ctx, channel, video, m, med)
    if after_h == 48 and m["ctr"] < med["ctr"] and video["thumbs_json"] and video["state"] == "live":
        ctx.events.emit("swap_suggested", video_id, reason=f"Click-through at 48 hours is {m['ctr']:.1f}%, below "
                                                           f"this channel's median of {med['ctr']:.1f}%.")
    if after_h == 168 and result == "loser":
        _hold(ctx, channel, video)
    return result


def _surge(ctx, channel, video, reading, med: dict) -> None:
    from stages import topics  # stages import core, not the other way round
    try:
        topics.follow_ups(ctx, channel, video, reading, med)
    except jobs.NeedsClaude:  # a job for the Claude Code session; the topics stage posts the ideas once it's done
        pass
    except Exception as e:  # a failed round shouldn't lose the judgment; say so where the ideas would have gone
        log.exception("follow-ups for video %s failed", video["id"])
        with ctx.connect() as conn:
            cards.post(ctx, conn, cards.home_thread_id(conn, channel.id), "system",
                       text=f"#{video['id']} is a winner at 48 hours, but its follow-up ideas failed: {e}. Ask for "
                            "them with suggest_topics.")


def _hold(ctx, channel, video) -> None:
    now = time.time()
    with ctx.connect() as conn:
        topic = conn.execute("SELECT family FROM topics WHERE id = ?", (video["topic_id"],)).fetchone()
        family = topic["family"] if topic else None
        if not family:  # a typed idea has no family tag, so there's nothing to hold
            return
        until = now + HOLD_DAYS * 86400
        conn.execute("INSERT INTO family_holds (channel_id, family, until, video_id, created_at) VALUES (?, ?, ?, ?, ?)",
                     (channel.id, family, until, video["id"], now))
        cards.post(ctx, conn, cards.home_thread_id(conn, channel.id), "system", video_id=video["id"],
                   text=f"#{video['id']} \"{video['title']}\" did worse than this channel's median on watch time and "
                        f"click-through at 7 days, so {family!r} topics go to the bottom of the queue until "
                        f"{time.strftime('%a %d %b', time.localtime(until))}.")
        affected = [r["id"] for r in conn.execute(
            "SELECT id FROM topics WHERE channel_id = ? AND status = 'queued' AND family = ?", (channel.id, family))]
    for topic_id in affected:  # their cards show the hold
        ctx.events.emit("topic_changed", None, topic_id=topic_id)


def held(conn, channel_id: str, now: float | None = None) -> dict[str, float]:
    """family → until, for the channel's holds still running."""
    rows = conn.execute("SELECT family, MAX(until) AS until FROM family_holds WHERE channel_id = ? AND until > ? "
                        "GROUP BY family", (channel_id, now or time.time())).fetchall()
    return {r["family"]: r["until"] for r in rows}


def own_results(conn, channel_id: str, now: float | None = None) -> dict[str, int]:
    """family → winners minus losers among the channel's judged readings over the last OWN_DAYS."""
    since = (now or time.time()) - OWN_DAYS * 86400
    rows = conn.execute(
        """SELECT t.family, m.verdict FROM metrics m JOIN videos v ON v.id = m.video_id JOIN topics t ON t.id = v.topic_id
           WHERE v.channel_id = ? AND m.captured_at >= ? AND m.verdict IN ('winner', 'loser') AND t.family IS NOT NULL""",
        (channel_id, since)).fetchall()
    out: dict[str, int] = {}
    for r in rows:
        out[r["family"]] = out.get(r["family"], 0) + (1 if r["verdict"] == "winner" else -1)
    return out


def rank(score: float, family: str | None, holds: dict, own: dict) -> tuple[float, str | None]:
    """(rank, why) for one queued topic: held families rank 0; others are scaled by the family's own results."""
    if family and family in holds:
        return 0.0, f"held until {time.strftime('%a %d %b', time.localtime(holds[family]))}: {family!r} did poorly here"
    net = max(-2, min(2, own.get(family, 0))) if family else 0
    note = None if not net else f"{family!r} has done {'well' if net > 0 else 'poorly'} here ({net:+d})"
    return score * (1 + 0.25 * net), note


def ranked_topics(conn, channel_id: str, now: float | None = None) -> list[dict]:
    """The channel's queued topics, best first, each with its rank and why."""
    holds, own = held(conn, channel_id, now), own_results(conn, channel_id, now)
    out = []
    for t in conn.execute("SELECT * FROM topics WHERE channel_id = ? AND status = 'queued'", (channel_id,)):
        value, note = rank(t["score"], t["family"], holds, own)
        out.append({**dict(t), "rank": value, "note": note})
    return sorted(out, key=lambda t: (-t["rank"], t["id"]))


def swap_since(conn, video, swap) -> float | None:
    """CTR over the whole days since a swap, once their reach files are all in (None before)."""
    from youtube import reporting
    start = swap["applied_at"] + 86400  # the first whole day after it
    days = reporting.pacific_days(start, time.time() - 2 * 86400)  # the files run a day or two behind
    if not days or not video["youtube_id"]:
        return None
    window = reporting.window(conn, video["channel_id"], video["youtube_id"], days)
    return window[1] if window else None


def based_on_video(video_id: int) -> str:
    """How a follow-up records the channel's own video it builds on, in topics.based_on."""
    return json.dumps([f"video:{video_id}"])

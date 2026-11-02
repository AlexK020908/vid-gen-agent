"""Stage 1: topic pick. Competitors' recent hits, Claude's topic ideas, and the weekly cadence, per channel.

Every topics.poll_every_h, a channel's competitors are checked (youtube/competitors.py, or made-up videos with
topics.competitors: stub, checked on their own only while the LLM is a stub too) and their recent long-form
uploads ranked by views per day since publish. When fewer
than topics.propose topics are queued, Claude proposes that many as variants of the top hits; they post as a
card in the channel's home thread, each with Start and Dismiss. A failed check posts its reason there once
and is tried again an hour later.

Each idea gets a family tag (its kind of setting). Queued topics are ranked by core/performance.py: competitor
views per day, scaled by how the channel's own videos in that family did, with held families last. A 48-hour
winner's follow-ups come through follow_ups() here.

The cadence: a channel that has published before, with nothing in progress, starts its top-ranked queued topic
topics.lead_days before its next slot (last go-public time + baseline_cadence_days). It stops at the outline
gate like any video.

With the Claude Code session writing, a round of ideas is a job no stage is parked on: the round marks its job
with what to run (core/jobs.py resume_with), and once the session has answered, this stage runs the round again,
which finds the answer and posts the ideas.
"""
import json
import logging
import time

from core import actions, cards, db, jobs, performance
from core.errors import ActionError
from youtube import competitors

NAME = "topics"
RETRY_S = 3600
DONE = ("scheduled", "live")  # every other state is a video in progress
TAKEN_SHOWN = 200             # the newest topics Claude is told not to repeat

log = logging.getLogger("stickfleet.topics")


def run_once(ctx) -> bool:
    now = time.time()
    did = _resume(ctx)
    for channel in ctx.config.channels.values():
        did = _poll_if_due(ctx, channel, now) or did
        did = _cadence(ctx, channel, now) or did
    return did


def _setting(ctx, name: str, default):
    return ctx.config.topics.get(name, default)


def _source(ctx) -> str:
    source = _setting(ctx, "competitors", "stub")
    if source not in ("stub", "youtube", "off"):
        raise ValueError(f"topics.competitors must be stub, youtube or off, not {source!r}")
    return source


def _interval(ctx) -> float:
    return float(_setting(ctx, "poll_every_h", 24)) * 3600


def _poll_if_due(ctx, channel, now: float) -> bool:
    source = _source(ctx)
    if source == "off" or not channel.competitors:
        return False
    if source == "stub" and not ctx.is_stub("llm"):  # don't pay Claude for ideas built on made-up videos
        return False
    with ctx.connect() as conn:
        row = conn.execute("SELECT polled_at, poll_error FROM channels WHERE id = ?", (channel.id,)).fetchone()
    if row["polled_at"] is not None and now - row["polled_at"] < _interval(ctx):
        return False
    try:
        poll(ctx, channel, now)
        with ctx.connect() as conn:
            queued = conn.execute("SELECT COUNT(*) FROM topics WHERE channel_id = ? AND status = 'queued'",
                                  (channel.id,)).fetchone()[0]
        count = int(_setting(ctx, "propose", 3))
        if queued < count:
            propose(ctx, channel, count)
    except jobs.NeedsClaude:  # the ideas are a job for the session now; _resume posts them once it's answered
        pass
    except Exception as e:  # ActionError, FinalError, BudgetExceeded, or a bug: say so once, try again later
        log.exception("topics for %s failed", channel.id)
        message = str(e) or type(e).__name__
        with ctx.connect() as conn:
            conn.execute("UPDATE channels SET polled_at = ?, poll_error = ? WHERE id = ?",
                         (now - _interval(ctx) + RETRY_S, message, channel.id))
            if message != row["poll_error"]:
                cards.post(ctx, conn, cards.home_thread_id(conn, channel.id), "system",
                           text=f"Couldn't get topic ideas: {message}. Trying again in an hour.")
    return True


def poll(ctx, channel, now: float | None = None) -> list[dict]:
    """Check the channel's competitors and store what they've uploaded lately. Returns the ranked hits."""
    now = now or time.time()
    source = _source(ctx)
    if source == "stub":
        videos, unknown = competitors.stub(channel.competitors, now), []
    else:
        videos, unknown = competitors.fetch(ctx, channel.competitors, float(_setting(ctx, "recent_days", 90)),
                                            int(float(_setting(ctx, "min_minutes", 8)) * 60))
    simulated = int(source == "stub")
    with ctx.connect() as conn, db.tx(conn):
        for v in videos:
            conn.execute(
                """INSERT INTO competitor_videos (youtube_id, competitor_id, competitor_name, title, published_at,
                     duration_s, views, checked_at, simulated) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(youtube_id) DO UPDATE SET competitor_name = excluded.competitor_name,
                     title = excluded.title, views = excluded.views, checked_at = excluded.checked_at""",
                (v["youtube_id"], v["competitor_id"], v["competitor_name"], v["title"], v["published_at"],
                 v["duration_s"], v["views"], now, simulated))
            conn.execute("INSERT INTO competitor_views (youtube_id, captured_at, views) VALUES (?, ?, ?)",
                         (v["youtube_id"], now, v["views"]))
        conn.execute("UPDATE channels SET polled_at = ?, poll_error = NULL WHERE id = ?", (now, channel.id))
        if unknown:
            cards.post(ctx, conn, cards.home_thread_id(conn, channel.id), "system",
                       text=f"YouTube has no channel {', '.join(unknown)}; check competitors in "
                            f"channels/{channel.id}.yaml (a channel id starts with UC).")
    return ranked(ctx, channel, now)


def ranked(ctx, channel, now: float | None = None) -> list[dict]:
    """The competitors' recent long-form uploads, best first by views per day since publish."""
    now = now or time.time()
    if not channel.competitors:
        return []
    since = now - float(_setting(ctx, "recent_days", 90)) * 86400
    with ctx.connect() as conn:
        rows = conn.execute(
            f"""SELECT * FROM competitor_videos WHERE competitor_id IN ({','.join('?' * len(channel.competitors))})
                AND published_at >= ? AND simulated = ?""",
            (*channel.competitors, since, int(_source(ctx) == "stub"))).fetchall()
    hits = []
    for r in rows:
        age = competitors.age_days(r["published_at"], r["checked_at"])
        hits.append({"youtube_id": r["youtube_id"], "title": r["title"], "channel": r["competitor_name"] or
                     r["competitor_id"], "views": r["views"], "age_days": age, "per_day": r["views"] / age})
    return sorted(hits, key=lambda h: h["per_day"], reverse=True)


def propose(ctx, channel, count: int | None = None) -> list[int]:
    """Ask the LLM for topic ideas built on the top hits; queue them and post the card. Returns topic ids."""
    count = count or int(_setting(ctx, "propose", 3))
    hits = ranked(ctx, channel)[:int(_setting(ctx, "shown", 8))]
    if not hits:
        raise ActionError("there are no recent competitor videos to build on yet; the next check will "
                                  "look again (competitors in the channel YAML, topics.recent_days)")
    with ctx.connect() as conn:
        taken, families, held = _known(conn, channel)
        meter = ctx.channel_meter(conn, NAME, f"Topic ideas for {channel.name}", channel.id)
        try:
            ideas = ctx.llm.topics(channel, hits, taken, count, meter, families, held)
        except jobs.NeedsClaude as e:
            jobs.resume_with(conn, e.job_id, {"round": "competitors", "channel": channel.id, "count": count})
            raise
    ids = []
    with ctx.connect() as conn, db.tx(conn):
        for idea in ideas:
            built_on = [hits[n - 1] for n in idea["based_on"]]
            ids.append(_queue(conn, channel, idea, max(h["per_day"] for h in built_on), "competitor",
                              json.dumps([h["youtube_id"] for h in built_on])))
    ctx.events.emit("topics_proposed", None, channel_id=channel.id, topic_ids=ids,
                    simulated=_source(ctx) == "stub")
    return ids


def follow_ups(ctx, channel, video, reading, med: dict) -> list[int]:
    """The surge: ideas following up the channel's own 48-hour winner, queued at the top."""
    with ctx.connect() as conn:
        topic = conn.execute("SELECT title, family FROM topics WHERE id = ?", (video["topic_id"],)).fetchone()
        taken, families, held = _known(conn, channel)
        title = video["title"] or topic["title"]
        hit = {"youtube_id": video["youtube_id"], "title": title, "channel": f"{channel.name} (this channel)",
               "views": reading["views"] or 0, "age_days": 2.0, "per_day": (reading["views"] or 0) / 2}
        winner = {"title": title, "family": topic["family"], "views": reading["views"] or 0,
                  "avd_pct": reading["avd_pct"], "median_avd_pct": med["avd_pct"], "ctr": reading["ctr"],
                  "median_ctr": med["ctr"]}
        meter = ctx.channel_meter(conn, NAME, f"Follow-ups to #{video['id']}", channel.id, video["id"])
        try:
            ideas = ctx.llm.topics(channel, [hit], taken, performance.FOLLOW_UPS, meter, families, held, winner)
        except jobs.NeedsClaude as e:
            jobs.resume_with(conn, e.job_id, {"round": "winner", "channel": channel.id, "video_id": video["id"]})
            raise
        top = max((t["rank"] for t in performance.ranked_topics(conn, channel.id)), default=0)
    with ctx.connect() as conn, db.tx(conn):
        ids = [_queue(conn, channel, idea, top + 1, "own_analytics", performance.based_on_video(video["id"]))
               for idea in ideas]
    ctx.events.emit("topics_proposed", None, channel_id=channel.id, topic_ids=ids, simulated=bool(reading["simulated"]),
                    winner_video_id=video["id"])
    return ids


def _resume(ctx) -> bool:
    """Rounds of ideas whose job the session has answered: run each again, which finds the answer and posts them.
    The mark is cleared first, so a round that fails says so once instead of every loop."""
    with ctx.connect() as conn:
        answered = jobs.to_resume(conn)
    for job in answered:
        what = json.loads(job["resume_json"])
        with ctx.connect() as conn:
            jobs.resumed(conn, job["id"])
        channel = ctx.config.channels.get(what["channel"])
        if channel is None:
            continue
        try:
            if what["round"] == "winner":
                _follow_ups_again(ctx, channel, what["video_id"])
            else:
                propose(ctx, channel, what["count"])
        except jobs.NeedsClaude:  # the request changed since (new hits, new topics): a new job, marked again
            pass
        except Exception as e:
            log.exception("topic ideas from job %s failed", job["id"])
            with ctx.connect() as conn:
                cards.post(ctx, conn, cards.home_thread_id(conn, channel.id), "system",
                           text=f"Couldn't post the topic ideas from job {job['id']}: {e}. Ask for them again with "
                                "suggest_topics.")
    return bool(answered)


def _follow_ups_again(ctx, channel, video_id: int) -> None:
    """A winner's follow-ups, from the reading and the medians it was judged against (core/performance.py)."""
    with ctx.connect() as conn:
        video = db.get_video(conn, video_id)
        reading = conn.execute("SELECT * FROM metrics WHERE video_id = ? AND after_h = 48", (video_id,)).fetchone()
    follow_ups(ctx, channel, video, reading, {"avd_pct": reading["median_avd_pct"], "ctr": reading["median_ctr"]})


def _known(conn, channel) -> tuple[list[str], list[str], list[str]]:
    """(topics the channel has, family tags in use, families on hold), for a round of ideas."""
    taken = [r["title"] for r in conn.execute(
        "SELECT title FROM topics WHERE channel_id = ? ORDER BY id DESC LIMIT ?", (channel.id, TAKEN_SHOWN))]
    families = [r["family"] for r in conn.execute(
        "SELECT DISTINCT family FROM topics WHERE channel_id = ? AND family IS NOT NULL ORDER BY family", (channel.id,))]
    return taken, families, sorted(performance.held(conn, channel.id))


def _queue(conn, channel, idea: dict, score: float, source: str, based_on: str) -> int:
    return conn.execute(
        """INSERT INTO topics (channel_id, title, score, source, status, why, based_on, family, created_at)
           VALUES (?, ?, ?, ?, 'queued', ?, ?, ?, ?)""",
        (channel.id, idea["title"], score, source, idea["why"], based_on, idea.get("family"), time.time())).lastrowid


def _cadence(ctx, channel, now: float) -> bool:
    if not _setting(ctx, "cadence", True):
        return False
    done = ",".join(f"'{s}'" for s in DONE)
    with ctx.connect() as conn:
        busy = conn.execute(f"SELECT 1 FROM videos WHERE channel_id = ? AND state NOT IN ({done}) LIMIT 1",
                            (channel.id,)).fetchone()
        last = conn.execute(f"SELECT MAX(publish_at) FROM videos WHERE channel_id = ? AND state IN ({done})",
                            (channel.id,)).fetchone()[0]
        if busy or last is None:  # something's being made, or the channel hasn't published yet
            return False
        slot = last + channel.baseline_cadence_days * 86400
        if now < slot - float(_setting(ctx, "lead_days", 5)) * 86400:
            return False
        ranked = [t for t in performance.ranked_topics(conn, channel.id, now) if t["rank"] > 0]  # held ones wait
    if not ranked:
        return False
    topic = ranked[0]
    when = time.strftime("%a %d %b", time.localtime(slot))
    actions.start_topic(ctx, topic["id"], note=f"the top queued topic, since the next slot ({when}) is near")
    return True

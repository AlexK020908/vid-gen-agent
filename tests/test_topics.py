"""Topics and metrics: the competitor check, topic ideas (stub and Claude), Start and Dismiss, the cadence,
metrics at 48 h and 7 days, and the reach report import.

Google's APIs are small fakes (the Data API as an API key sees it, Analytics, Reporting), and Claude's ideas
are answered as the session would answer its job. No network, $0. The live test reads real competitor videos
with YOUTUBE_API_KEY (free, a few quota units) and is skipped without it.
"""
import json
import os
import shutil
import time
from datetime import datetime, timezone

import pytest
from dotenv import load_dotenv
from googleapiclient.errors import HttpError
from httplib2 import Response

from core import actions, cards, db, jobs
from core.config import ROOT
from core.context import make_ctx
from core.engine import Engine
from core.errors import ActionError
from providers.session import SessionLLM
from stages import analytics, topics
from youtube import auth, client, competitors, quota, reporting

load_dotenv(ROOT / ".env")  # only the live test uses the key
DAY = 86400


# --- fake Google APIs ----------------------------------------------------------------------------

class Req:
    def __init__(self, result=None, error: Exception | None = None) -> None:
        self.result, self.error = result, error

    def execute(self, num_retries: int = 0):
        if self.error:
            raise self.error
        return self.result


class Resource:
    def __init__(self, **methods) -> None:
        self.__dict__.update(methods)


def iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).isoformat().replace("+00:00", "Z")


def upload(vid: str, days_ago: float, views: int, minutes: int = 25, live: str = "none") -> dict:
    return {"id": vid, "published": time.time() - days_ago * DAY, "views": views, "minutes": minutes, "live": live}


def http_error(status: int, reason: str) -> HttpError:
    body = json.dumps({"error": {"code": status, "message": reason, "errors": [{"reason": reason}]}}).encode()
    return HttpError(Response({"status": status}), body)


class FakePublic:
    """The Data API with an API key: channels, their uploads playlists, and videos."""

    def __init__(self, channels: dict[str, tuple[str, list[dict]]], error: Exception | None = None) -> None:
        self.data, self.error, self.calls = channels, error, []

    def _req(self, method: str, result) -> Req:
        self.calls.append(method)
        return Req(result, self.error)

    def channels(self):
        return Resource(list=lambda part, id, maxResults: self._req("channels.list", {"items": [
            {"id": cid, "snippet": {"title": name}, "contentDetails": {"relatedPlaylists": {"uploads": "UU" + cid[2:]}}}
            for cid, (name, _) in self.data.items() if cid in id.split(",")]}))

    def playlistItems(self):
        def items(part, playlistId, maxResults):
            _, videos = self.data["UC" + playlistId[2:]]
            return self._req("playlistItems.list", {"items": [
                {"contentDetails": {"videoId": v["id"], "videoPublishedAt": iso(v["published"])}} for v in videos]})
        return Resource(list=items)

    def videos(self):
        everything = {v["id"]: v for _, videos in self.data.values() for v in videos}
        return Resource(list=lambda part, id, maxResults: self._req("videos.list", {"items": [
            {"id": v["id"], "snippet": {"title": f"Video {v['id']}", "publishedAt": iso(v["published"]),
                                        "liveBroadcastContent": v["live"]},
             "statistics": {"viewCount": str(v["views"])}, "contentDetails": {"duration": f"PT{v['minutes']}M7S"}}
            for vid in id.split(",") if (v := everything.get(vid))]}))


class FakeChannelApi:
    """The channel's own Data API (view counts) and Analytics API (watch time, subscribers)."""

    def __init__(self, views: int, analytics_row: list) -> None:
        self.views, self.row, self.queries = views, analytics_row, []

    def videos(self):
        return Resource(list=lambda part, id: Req({"items": [{"id": id, "statistics": {"viewCount": str(self.views)}}]}))

    def reports(self):
        def query(**kw):
            self.queries.append(kw)
            return Req({"columnHeaders": [{"name": n} for n in analytics.ANALYTICS.split(",")],
                        "rows": [self.row] if self.row else None})
        return Resource(query=query)


class FakeReporting:
    """jobs.list / jobs.create / jobs.reports.list; the files themselves come from `files` (url → CSV)."""

    def __init__(self) -> None:
        self.jobs_made, self.listed, self.reports, self.files = [], [], [], {}

    def add(self, day_start: float, rows: list[tuple[str, int, float]], created: str) -> None:
        rid = f"r{len(self.reports) + 1}"
        url = f"https://youtubereporting.googleapis.com/v1/media/{rid}"
        self.reports.append({"id": rid, "startTime": iso(day_start), "createTime": created, "downloadUrl": url})
        self.files[url] = ("date,channel_id,video_id,video_thumbnail_impressions,video_thumbnail_impressions_ctr\n"
                           + "".join(f"20261001,UCme,{v},{n},{c}\n" for v, n, c in rows)).encode()

    def jobs(self):
        def report_list(jobId, createdAfter=None, pageToken=None):
            self.listed.append(createdAfter)
            return Req({"reports": [r for r in self.reports if not createdAfter or r["createTime"] > createdAfter]})

        def create(body):
            self.jobs_made.append(body)
            return Req({"id": "job1", **body})
        return Resource(list=lambda: Req({"jobs": []}), create=create, reports=lambda: Resource(list=report_list))


# --- fixtures ----------------------------------------------------------------------------------------

@pytest.fixture
def ctx(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    shutil.copy(ROOT / "stickfleet.yaml", root)
    for name in ("channels", "prompts"):
        shutil.copytree(ROOT / name, root / name)
    ctx = make_ctx(root=root, data_dir=tmp_path / "data",
                   overrides={"mode": "stub", "stub": {"scenes": 6}, "engine": {"retry_backoff_s": 0},
                              "render": {"engine": "ffmpeg"},
                              "topics": {"competitors": "stub"}})
    ctx.channel("zombie").competitors = ["UCaaaaaaaaaaaaaaaaaaaaaa", "UCbbbbbbbbbbbbbbbbbbbbbb"]
    return ctx


def run(ctx) -> None:
    Engine(ctx).run_until_idle()


def home_messages(ctx) -> list[dict]:
    with ctx.connect() as conn:
        home = cards.home_thread_id(conn, "zombie")
        return [cards.to_dict(r) for r in conn.execute("SELECT * FROM messages WHERE thread_id = ? ORDER BY id",
                                                       (home,))]


def topic_cards(ctx) -> list[dict]:
    return [m for m in home_messages(ctx) if m["card"] and m["card"]["kind"] == "topics"]


def published(ctx, days_ago: float, youtube_id: str = "stub-1") -> int:
    """A video that went public `days_ago` days ago."""
    vid = actions.new_video(ctx, "zombie", f"Published {days_ago} days ago")
    with ctx.connect() as conn:
        conn.execute("UPDATE videos SET state = 'live', publish_at = ?, youtube_id = ?, duration_ms = 1500000 "
                     "WHERE id = ?", (time.time() - days_ago * DAY, youtube_id, vid))
    return vid


def force_poll(ctx) -> None:
    with ctx.connect() as conn:
        conn.execute("UPDATE channels SET polled_at = 0")


# --- the competitor check ---------------------------------------------------------------------------

def test_check_ranks_competitors_recent_long_uploads(ctx):
    ctx.config.topics["competitors"] = "youtube"
    a, b = ctx.channel("zombie").competitors
    fake = FakePublic({
        a: ("Stick Survival", [upload("v1", 2, 300_000), upload("v2", 10, 500_000), upload("short", 1, 1_000_000, 1),
                               upload("old", 200, 9_000_000), upload("premiere", 0.1, 0, 25, "upcoming")]),
        b: ("Day By Day", [upload("v3", 0.3, 40_000), upload("v4", 30, 3_000_000)]),
    })
    ctx.google["public"] = lambda _: fake
    ctx.channel("zombie").competitors.append("UCnobodynobodynobodynobo")

    hits = topics.poll(ctx, ctx.channel("zombie"))
    assert [h["youtube_id"] for h in hits] == ["v1", "v4", "v2", "v3"]  # views a day: 150k, 100k, 50k, 40k (1-day floor)
    assert hits[0]["channel"] == "Stick Survival" and hits[0]["per_day"] == pytest.approx(150_000, rel=0.01)
    assert fake.calls == ["channels.list", "playlistItems.list", "playlistItems.list", "videos.list"]
    with ctx.connect() as conn:
        assert quota.used(conn)["shared"] == 4
        assert conn.execute("SELECT COUNT(*) FROM competitor_views").fetchone()[0] == 4
    assert any("YouTube has no channel UCnobodynobodynobodynobo" in (m["text"] or "") for m in home_messages(ctx))
    assert competitors.seconds("PT1H2M3S") == 3723 and competitors.seconds("P1DT1S") == 86401


def test_check_errors_are_posted_once_and_retried_in_an_hour(ctx, monkeypatch):
    ctx.config.topics["competitors"] = "youtube"
    ctx.google["public"] = lambda _: FakePublic({}, error=http_error(400, "keyInvalid"))
    run(ctx)
    run(ctx)  # not due again yet
    force_poll(ctx)
    run(ctx)  # due, fails the same way: not posted twice
    said = [m["text"] for m in home_messages(ctx) if "Couldn't get topic ideas" in (m["text"] or "")]
    assert len(said) == 1 and "keyInvalid" in said[0] and "Trying again in an hour" in said[0]
    with ctx.connect() as conn:
        polled = conn.execute("SELECT polled_at FROM channels WHERE id = 'zombie'").fetchone()[0]
    assert polled + 24 * 3600 == pytest.approx(time.time() + topics.RETRY_S, abs=5)

    del ctx.google["public"]
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    with pytest.raises(ActionError, match="YOUTUBE_API_KEY"):
        client.public_service(ctx)


# --- topic ideas, Start and Dismiss ----------------------------------------------------------------------

def test_ideas_card_start_and_dismiss(ctx):
    run(ctx)
    [msg] = topic_cards(ctx)
    card = msg["card"]
    assert msg["card_status"] == "active" and card["simulated"] and len(card["topics"]) == 3
    first = card["topics"][0]
    assert first["status"] == "queued" and first["based_on"][0]["per_day"] > 0 and first["based_on"][0]["url"] is None
    assert "made-up competitor data" in msg["text"]
    with ctx.connect() as conn:
        cost = conn.execute("SELECT * FROM costs WHERE stage = 'topics'").fetchone()
    assert cost["video_id"] is None and cost["provider"] == "llm" and cost["simulated"] == 1

    from test_tools import call
    started, err = call(ctx, "start_topic", {"topic_id": first["id"]})
    vid = int(started.split("#")[1].split()[0])
    assert not err and started == f"Started video #{vid} from topic {first['id']}. It's writing the outline."
    assert call(ctx, "dismiss_topic", {"topic_id": card["topics"][1]["id"]})[1] is False
    again, err = call(ctx, "start_topic", {"topic_id": first["id"]})
    assert err and "already started" in again
    with ctx.connect() as conn:
        assert db.get_video(conn, vid)["topic_id"] == first["id"]
    [msg] = topic_cards(ctx)
    assert [t["status"] for t in msg["card"]["topics"]] == ["used", "dismissed", "queued"]
    assert msg["card"]["topics"][0]["video_id"] == vid and msg["card_status"] == "active"

    actions.dismiss_topic(ctx, card["topics"][2]["id"])
    assert topic_cards(ctx)[0]["card_status"] == "done"  # nothing left to decide

    force_poll(ctx)
    run(ctx)  # the queue is empty, so the next check proposes a new round, none of them repeats
    second = topic_cards(ctx)[1]["card"]["topics"]
    assert len(second) == 3 and not {t["title"] for t in second} & {t["title"] for t in card["topics"]}


def test_the_session_writes_ideas_from_the_ranked_hits(ctx):
    ctx.config.mode = "live"
    ctx.config.providers.update(llm="session", tts="stub", images="stub", video="stub")
    ctx.llm = SessionLLM(ctx.config)
    actions.new_video(ctx, "zombie", "Day 1 to Day 365 stranded on an oil rig")
    idea = {"title": "Day 1 to Day 365 in a sinking submarine", "why": "Builds on hit 1.", "family": "ocean",
            "based_on": [1, 3]}
    bad = {"topics": [{**idea, "title": "day 1 to day 365 stranded on an oil rig"},
                      {**idea, "title": "Somewhere else", "based_on": [9]}]}
    good = {"topics": [idea, {**idea, "title": "Day 1 to Day 100 on a frozen ferry", "based_on": [2]},
                       {**idea, "title": "Day 1 to Day 1000 in a lighthouse", "based_on": [4]}]}
    with ctx.connect() as conn:  # the video above is beside the point here
        conn.execute("UPDATE videos SET state = 'outlined'")
    assert topics.run_once(ctx) is False  # made-up hits never go to Claude on their own
    with ctx.connect() as conn:
        assert jobs.pending(conn) == []
    topics.poll(ctx, ctx.channel("zombie"))
    with pytest.raises(jobs.NeedsClaude):  # asked for (run.py topics --propose, the chat's suggest_topics)
        topics.propose(ctx, ctx.channel("zombie"))

    with ctx.connect() as conn:
        [job] = jobs.pending(conn)
    first = json.loads(job["messages_json"])[0]["content"]
    hits = topics.ranked(ctx, ctx.channel("zombie"))
    assert f'1. "{hits[0]["title"]}" by Made-up competitor' in first and "a day)" in first
    assert "- Day 1 to Day 365 stranded on an oil rig" in first and "Propose 3 topics." in first
    with ctx.connect() as conn:
        problems = jobs.answer(conn, job["id"], json.dumps(bad))
        assert "there are 2 topics; it needs 3" in problems and any("is one this channel already has" in p
                                                                     for p in problems)
        assert "topic 2 cites hit 9; the hits are numbered 1 to 8" in problems
        assert jobs.answer(conn, job["id"], json.dumps(good)) == []
    topics.run_once(ctx)  # the answered round is queued and posted
    with ctx.connect() as conn:
        rows = conn.execute("SELECT * FROM topics WHERE source = 'competitor' ORDER BY id").fetchall()
        llm = conn.execute("SELECT COUNT(*) FROM costs WHERE stage = 'topics'").fetchone()[0]
    assert [r["title"] for r in rows] == [t["title"] for t in good["topics"]]
    assert json.loads(rows[0]["based_on"]) == [hits[0]["youtube_id"], hits[2]["youtube_id"]]
    assert rows[0]["score"] == pytest.approx(hits[0]["per_day"]) and rows[1]["score"] == pytest.approx(hits[1]["per_day"])
    assert llm == 0  # the session's ideas cost nothing


# --- the cadence ----------------------------------------------------------------------------------------

def test_cadence_starts_the_top_topic_when_the_next_slot_is_near(ctx):
    run(ctx)  # three queued ideas
    published(ctx, days_ago=0.5)
    run(ctx)  # next slot in 6.5 days, more than lead_days away: nothing
    with ctx.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM videos").fetchone()[0] == 1
        conn.execute("UPDATE videos SET publish_at = ?", (time.time() - 3 * DAY,))
        top = conn.execute("SELECT id, title FROM topics WHERE status = 'queued' ORDER BY score DESC").fetchone()
    run(ctx)
    run(ctx)  # the new video is in progress, so no second start
    with ctx.connect() as conn:
        videos = conn.execute("SELECT * FROM videos ORDER BY id").fetchall()
    assert len(videos) == 2 and videos[1]["topic_id"] == top["id"] and videos[1]["state"] == "outlined"
    assert any(f"Started video #{videos[1]['id']}: {top['title']} (the top queued topic" in (m["text"] or "")
               for m in home_messages(ctx))

    ctx.config.topics["cadence"] = False
    with ctx.connect() as conn:
        conn.execute("UPDATE videos SET state = 'live', publish_at = ? WHERE id = ?", (time.time() - 3 * DAY,
                                                                                       videos[1]["id"]))
    run(ctx)
    with ctx.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM videos").fetchone()[0] == 2


def test_cadence_waits_for_a_first_video(ctx):
    run(ctx)
    run(ctx)
    with ctx.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM videos").fetchone()[0] == 0


# --- metrics -----------------------------------------------------------------------------------------------

def test_stub_metrics_at_48_hours_and_7_days(ctx):
    ctx.config.topics["competitors"] = "off"
    vid = published(ctx, days_ago=1)
    run(ctx)
    assert actions.status(ctx, vid)["metrics"] == []
    with ctx.connect() as conn:
        conn.execute("UPDATE videos SET publish_at = ? WHERE id = ?", (time.time() - 49 * 3600, vid))
    run(ctx)
    run(ctx)
    [m] = actions.status(ctx, vid)["metrics"]
    assert m["after_h"] == 48 and m["simulated"] == 1 and m["views"] > 0 and m["impressions"] == m["views"] * 11
    with ctx.connect() as conn:
        msgs = [cards.to_dict(r) for r in conn.execute(
            "SELECT * FROM messages WHERE video_id = ? AND json_extract(card_json, '$.kind') = 'metrics'", (vid,))]
        conn.execute("UPDATE videos SET publish_at = ? WHERE id = ?", (time.time() - 8 * DAY, vid))
    assert len(msgs) == 1 and msgs[0]["card_status"] == "done" and msgs[0]["card"]["simulated"]
    run(ctx)
    assert [m["after_h"] for m in actions.status(ctx, vid)["metrics"]] == [48, 168]


def test_live_metrics_and_reach_filled_in_when_the_files_arrive(ctx, monkeypatch):
    ctx.config.topics["competitors"] = "off"
    ctx.config.youtube.update(mode="live", reach=True)
    vid = published(ctx, days_ago=49 / 24, youtube_id="yt123")
    with ctx.connect() as conn:
        publish_at = db.get_video(conn, vid)["publish_at"]
    days = reporting.pacific_days(publish_at, publish_at + 48 * 3600 - 1)
    api = FakeChannelApi(views=5400, analytics_row=[5100, 412.0, 27.4, 31])
    rep = FakeReporting()
    ctx.youtube = lambda channel_id: api
    ctx.google.update(youtubeAnalytics=lambda channel_id: api, youtubereporting=lambda channel_id: rep)
    monkeypatch.setattr(auth, "stored", lambda channel_id: {"refresh_token": "rt", "scopes": auth.SCOPES})
    monkeypatch.setattr(reporting, "_download", lambda svc, url: rep.files[url])
    start_of = {d: datetime.fromisoformat(d).replace(hour=12, tzinfo=quota.PACIFIC).timestamp() for d in days}
    for d in days[:-1]:  # the last day's file hasn't arrived yet
        rep.add(start_of[d], [("yt123", 1000, 4.0), ("other", 50, 1.0)], f"{d}T20:00:00Z")

    run(ctx)
    [m] = actions.status(ctx, vid)["metrics"]
    assert (m["views"], m["avd_seconds"], m["avd_pct"], m["subs_gained"], m["simulated"]) == (5400, 412.0, 27.4, 31, 0)
    assert m["impressions"] is None  # not every day of the window is in yet
    with ctx.connect() as conn:  # so it isn't judged yet either
        assert conn.execute("SELECT verdict FROM metrics WHERE video_id = ?", (vid,)).fetchone()[0] is None
    q = api.queries[0]
    assert q["ids"] == "channel==MINE" and q["filters"] == "video==yt123" and q["metrics"] == analytics.ANALYTICS
    assert rep.jobs_made == [{"reportTypeId": "channel_reach_basic_a1", "name": "Stick Fleet reach"}]

    rep.add(start_of[days[-1]], [("yt123", 500, 10.0), ("yt123", 500, 0.0)], f"{days[-1]}T21:00:00Z")
    rep.add(start_of[days[0]], [("yt123", 2000, 4.0)], f"{days[-1]}T22:00:00Z")  # a backfill of the first day
    with ctx.connect() as conn:
        conn.execute("UPDATE channels SET reach_checked_at = 0")
    run(ctx)
    [m] = actions.status(ctx, vid)["metrics"]
    middle = 1000 * (len(days) - 2)
    assert m["impressions"] == 2000 + middle + 1000
    assert m["ctr"] == pytest.approx((2000 * 4 + middle * 4 + 500 * 10) / m["impressions"])
    assert rep.listed[1] == f"{days[-2]}T20:00:00Z" and len(rep.jobs_made) == 1  # only newer files, same job
    with ctx.connect() as conn:
        card = cards.to_dict(conn.execute(
            "SELECT * FROM messages WHERE video_id = ? AND json_extract(card_json, '$.kind') = 'metrics'",
            (vid,)).fetchone())["card"]
    assert card["impressions"] == m["impressions"]  # the card was updated in place
    assert card["verdict"] == "early"  # judged once complete: the only video, so nothing to compare to


def test_a_sign_in_from_before_a_new_scope_asks_to_reconnect(ctx, monkeypatch):
    old = [s for s in auth.SCOPES if not s.endswith("youtube.readonly")]
    monkeypatch.setattr(auth, "stored", lambda channel_id: {"refresh_token": "rt", "scopes": old, "title": "Mine"})
    assert auth.status(ctx, "zombie")["missing_scopes"] == ["youtube.readonly"]


# --- live (real API, free) --------------------------------------------------------------------------------

@pytest.mark.live
@pytest.mark.skipif(not os.environ.get("YOUTUBE_API_KEY"), reason="needs YOUTUBE_API_KEY")
def test_live_competitors(ctx):
    ids = make_ctx().channel("zombie").competitors
    videos, unknown = competitors.fetch(ctx, ids, 90, 8 * 60)
    print(f"\nlive competitors: {len(videos)} recent long uploads from {ids}; unknown ids: {unknown}")
    for v in sorted(videos, key=lambda v: v["views"], reverse=True)[:5]:
        print(f"  {v['views']:>12,}  {v['title']}  ({v['competitor_name']})")
    assert all(v["duration_s"] >= 8 * 60 for v in videos)

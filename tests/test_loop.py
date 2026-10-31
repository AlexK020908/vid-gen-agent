"""The own-data loop: verdicts against the channel's medians, the surge, swap cards (stub and live), family holds,
topic ranking, and the daily sign-in check.

Readings are written straight into `metrics` so the medians are exact; the engine runs where the flow matters.
Google's APIs and Claude are fakes. No network, $0.
"""
import json
import shutil
import time

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from agent.harness import AgentHub
from agent.tools import build_tools, load_thread
from core import actions, cards, db, performance
from core.config import ROOT
from core.context import make_ctx
from core.engine import Engine
from providers.claude import ClaudeLLM
from server.app import create_app
from stages import topics
from test_agent import call
from test_claude import FakeAnthropic, user_text
from test_topics import Req, Resource, home_messages, http_error, topic_cards
from youtube import auth, quota

DAY = 86400


@pytest.fixture
def ctx(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    shutil.copy(ROOT / "stickfleet.yaml", root)
    for name in ("channels", "prompts"):
        shutil.copytree(ROOT / name, root / name)
    ctx = make_ctx(root=root, data_dir=tmp_path / "data",
                   overrides={"mode": "stub", "stub": {"scenes": 6}, "engine": {"retry_backoff_s": 0},
                              "agent": {"comment_on_gates": False}, "render": {"engine": "ffmpeg"},
                              "topics": {"competitors": "stub", "cadence": False},
                              "youtube": {"reach": False, "signin_check": False}})
    ctx.channel("zombie").competitors = ["UCaaaaaaaaaaaaaaaaaaaaaa"]
    return ctx


def run(ctx) -> None:
    Engine(ctx).run_until_idle()


def live_video(ctx, title: str, family: str | None = None, days_ago: float = 2.1, youtube_id: str | None = None) -> int:
    """A live video with three thumbnails and titles from its render card; the first of each is picked."""
    vid = actions.new_video(ctx, "zombie", title)
    thumbs = []
    for i in range(3):
        path = ctx.media(vid) / "thumbs" / f"t{i}.png"
        Image.new("RGB", (1280, 720), (40 * i, 80, 120)).save(path)
        thumbs.append(ctx.rel(path))
    options = {"titles": [title, f"{title}: Could You Last?", f"I Survived {title}"], "thumbs": thumbs,
               "texts": ["DAY 365", "NO WAY OUT", "ALONE"]}
    with ctx.connect() as conn:
        conn.execute("""UPDATE videos SET state = 'live', publish_at = ?, youtube_id = ?, title = ?, thumb_idx = 0,
                        thumbs_json = ?, duration_ms = 1500000 WHERE id = ?""",
                     (time.time() - days_ago * DAY, youtube_id or f"stub-{vid}", title, json.dumps(options), vid))
        conn.execute("UPDATE topics SET family = ? WHERE id = (SELECT topic_id FROM videos WHERE id = ?)", (family, vid))
    return vid


def reading(ctx, vid: int, after_h: int, avd_pct: float, ctr: float | None, views: int = 2000, verdict=None,
            captured_ago: float = 0) -> None:
    with ctx.connect() as conn:
        conn.execute(
            """INSERT INTO metrics (video_id, captured_at, after_h, views, avd_seconds, avd_pct, impressions, ctr,
                 subs_gained, simulated, verdict) VALUES (?, ?, ?, ?, 600, ?, ?, ?, 10, 0, ?)""",
            (vid, time.time() - captured_ago, after_h, views, avd_pct, None if ctr is None else views * 10, ctr, verdict))


def others(ctx, after_h: int, avd_pct: float = 40.0, ctr: float = 5.0, n: int = 3) -> None:
    """`n` earlier videos with the same reading, so the medians are exactly these."""
    for i in range(n):
        reading(ctx, live_video(ctx, f"Earlier video {after_h}-{i}", days_ago=30), after_h, avd_pct, ctr,
                captured_ago=(i + 1) * DAY)


def swap_cards(ctx, vid: int) -> list[dict]:
    with ctx.connect() as conn:
        return [cards.to_dict(r) for r in conn.execute(
            "SELECT * FROM messages WHERE video_id = ? AND json_extract(card_json, '$.kind') = 'swap' ORDER BY id",
            (vid,))]


# --- verdicts --------------------------------------------------------------------------------------

def test_early_until_there_are_three_to_compare(ctx):
    vid = live_video(ctx, "Day 1 to Day 365 in a flooded subway")
    reading(ctx, vid, 48, 60.0, 9.0)
    assert performance.judge(ctx, vid, 48) == "early"
    assert performance.judge(ctx, vid, 48) is None  # judged once
    assert not swap_cards(ctx, vid) and not topic_cards(ctx)

    pending = live_video(ctx, "Day 1 to Day 100 on a raft")
    reading(ctx, pending, 48, 50.0, None)  # the reach files aren't in yet
    assert performance.judge(ctx, pending, 48) is None


def test_a_48_hour_winner_gets_follow_ups_at_the_top(ctx):
    run(ctx)  # three competitor ideas in the queue
    others(ctx, 48)
    vid = live_video(ctx, "Day 1 to Day 365 in a flooded subway", family="underground")
    reading(ctx, vid, 48, avd_pct=50.0, ctr=6.0, views=4000)
    assert performance.judge(ctx, vid, 48) == "winner"

    with ctx.connect() as conn:
        m = conn.execute("SELECT * FROM metrics WHERE video_id = ?", (vid,)).fetchone()
        ranked = performance.ranked_topics(conn, "zombie")
    assert (m["verdict"], m["median_avd_pct"], m["median_ctr"], m["median_n"]) == ("winner", 40.0, 5.0, 3)
    assert [t["source"] for t in ranked[:2]] == ["own_analytics"] * 2 and ranked[2]["source"] == "competitor"
    assert ranked[0]["title"] == "Day 1 to Day 365 in a flooded subway: the second year"
    msg = topic_cards(ctx)[-1]
    assert msg["card"]["winner_video_id"] == vid and "is beating this channel's medians 48 hours in" in msg["text"]
    with ctx.connect() as conn:  # follow-ups stay out of held families too
        conn.execute("INSERT INTO family_holds (channel_id, family, until, created_at) VALUES ('zombie', 'ocean', ?, ?)",
                     (time.time() + DAY, time.time()))
    other = live_video(ctx, "Day 1 to Day 365 in a bunker", family="underground")
    reading(ctx, other, 48, avd_pct=55.0, ctr=7.0)
    performance.judge(ctx, other, 48)
    assert all(t["family"] != "ocean" for t in topic_cards(ctx)[-1]["card"]["topics"])
    hit = msg["card"]["topics"][0]["based_on"][0]
    assert hit["title"] == f"#{vid} Day 1 to Day 365 in a flooded subway" and hit["channel"] == "this channel"
    assert not swap_cards(ctx, vid)  # its click-through is above the median


def test_claude_follow_ups_and_held_families(ctx):
    ctx.config.mode = "live"
    ctx.config.providers.update(llm="claude", tts="stub", images="stub", video="stub")
    others(ctx, 48)
    vid = live_video(ctx, "Day 1 to Day 365 in a flooded subway", family="underground")
    with ctx.connect() as conn:
        conn.execute("INSERT INTO family_holds (channel_id, family, until, created_at) VALUES ('zombie', 'ocean', ?, ?)",
                     (time.time() + DAY, time.time()))
    idea = {"title": "Day 366 to Day 730 in the flooded subway", "why": "The sequel.", "family": "underground",
            "based_on": [1]}
    fake = FakeAnthropic({"topics": [idea, {**idea, "title": "Day 1 to Day 365 on an oil rig", "family": "ocean"}]},
                         {"topics": [idea, {**idea, "title": "Day 1 to Day 365 in the sewers"}]})
    ctx.llm = ClaudeLLM(ctx.config, client=fake)
    reading(ctx, vid, 48, avd_pct=50.0, ctr=6.0, views=4000)
    assert performance.judge(ctx, vid, 48) == "winner"

    first = user_text(fake.requests[0])
    assert "This channel's own video is beating its medians 48 hours after going public" in first
    assert "click-through 6.0% against 5.0%" in first and "Families on hold (don't propose them): ocean" in first
    assert '1. "Day 1 to Day 365 in a flooded subway" by Lone Stick Survivor (this channel)' in first
    assert "Propose 2 follow-ups" in first and "Family tags in use here: underground" in first
    assert "is in the 'ocean' family, which is on hold" in user_text(fake.requests[1], 2)
    with ctx.connect() as conn:
        rows = conn.execute("SELECT title, family, source FROM topics WHERE source = 'own_analytics'").fetchall()
    assert [(r["title"], r["family"]) for r in rows] == [(idea["title"], "underground"),
                                                         ("Day 1 to Day 365 in the sewers", "underground")]


# --- the swap card --------------------------------------------------------------------------------------

def test_low_click_through_suggests_a_swap_applied_in_stub_mode(ctx):
    others(ctx, 48, ctr=5.0)
    vid = live_video(ctx, "Day 1 to Day 365 in a flooded subway")
    reading(ctx, vid, 48, avd_pct=45.0, ctr=3.0)
    assert performance.judge(ctx, vid, 48) == "mixed"
    [msg] = swap_cards(ctx, vid)
    card = msg["card"]
    assert msg["card_status"] == "active" and not card["live"] and card["thumb_idx"] == 0 and len(card["thumbs"]) == 3
    assert "Click-through at 48 hours is 3.0%, below this channel's median of 5.0%." in msg["text"]

    app = create_app(ctx, run_engine=False, agents=AgentHub(ctx, online=False))
    with TestClient(app, base_url="http://localhost") as http:
        r = http.post(f"/api/videos/{vid}/swap", json={"thumb_idx": 2, "title_idx": 1})
        assert r.json()["changed"] == {"title": card["titles"][1], "thumb_idx": 2}
        again = http.post(f"/api/videos/{vid}/swap", json={"thumb_idx": 2, "title_idx": 1})
        assert again.status_code == 409 and "different from the current one" in again.json()["detail"]
        assert http.post(f"/api/videos/{vid}/keep").status_code == 409  # nothing waiting now
    request = json.loads((ctx.media(vid) / "swap_request.json").read_text(encoding="utf-8"))
    assert request["videos.update"]["snippet"]["title"] == card["titles"][1] and "thumbnails.set" in request
    with ctx.connect() as conn:
        video = db.get_video(conn, vid)
        swap = conn.execute("SELECT * FROM swaps WHERE video_id = ?", (vid,)).fetchone()
        texts = [r["text"] for r in conn.execute("SELECT text FROM messages WHERE video_id = ?", (vid,))]
    assert (video["title"], video["thumb_idx"]) == (card["titles"][1], 2)
    assert (swap["old_title"], swap["new_thumb_idx"], swap["ctr_before"], swap["live"]) == (card["title"], 2, 3.0, 0)
    assert swap_cards(ctx, vid)[0]["card_status"] == "approved"
    assert any("Changed the title to" in (t or "") and "nothing was sent" in t for t in texts)

    # the 7-day reading says what changed and what click-through was before
    with ctx.connect() as conn:
        conn.execute("UPDATE videos SET publish_at = ? WHERE id = ?", (time.time() - 8 * DAY, vid))
    run(ctx)
    with ctx.connect() as conn:
        week = cards.to_dict(conn.execute(
            """SELECT * FROM messages WHERE video_id = ? AND json_extract(card_json, '$.kind') = 'metrics'""",
            (vid,)).fetchone())["card"]
    assert week["after_h"] == 168 and week["swap"]["ctr_before"] == 3.0 and week["swap"]["thumb"] == 2

    # the agent can post the card again, but only a person applies it
    with ctx.connect() as conn:
        thread = load_thread(ctx, cards.thread_id(conn, vid))
    text, err = call(build_tools(ctx, thread), "update_video", {"reason": "Try the scarier one."})
    assert not err and "Nothing changes on YouTube" in text
    assert [m["card_status"] for m in swap_cards(ctx, vid)] == ["approved", "active"]
    actions.keep_swap(ctx, vid)
    assert swap_cards(ctx, vid)[-1]["card_status"] == "kept"


class FakeYouTube:
    """The channel's Data API for a live swap: videos.list (snippet), videos.update, thumbnails.set."""

    def __init__(self, thumb_error=None) -> None:
        self.updates, self.thumbs, self.thumb_error = [], [], thumb_error

    def videos(self):
        snippet = {"title": "Old title", "description": "Chapters: 0:00 Day 1", "tags": ["survival", "zombie"],
                   "categoryId": "24", "defaultLanguage": "en", "publishedAt": "2026-10-20T15:00:00Z",
                   "channelTitle": "Day by Day Zombie", "thumbnails": {"default": {"url": "x"}}}
        return Resource(list=lambda part, id: Req({"items": [{"id": id, "snippet": snippet}]}),
                        update=lambda part, body: (self.updates.append((part, body)), Req({"id": body["id"]}))[1])

    def thumbnails(self):
        return Resource(set=lambda videoId, media_body: (self.thumbs.append(videoId), Req({}, self.thumb_error))[1])


def test_live_swap_sends_the_whole_snippet_back(ctx):
    ctx.config.youtube["mode"] = "live"
    fake = FakeYouTube()
    ctx.youtube = lambda channel_id: fake
    vid = live_video(ctx, "Old title", youtube_id="yt9")
    changed = actions.apply_swap(ctx, vid, title_idx=2, thumb_idx=1)
    assert changed == {"title": "I Survived Old title", "thumb_idx": 1}
    [(part, body)] = fake.updates
    assert part == "snippet" and body == {"id": "yt9", "snippet": {
        "title": "I Survived Old title", "description": "Chapters: 0:00 Day 1", "tags": ["survival", "zombie"],
        "categoryId": "24", "defaultLanguage": "en"}}  # nothing cleared, nothing read-only sent
    assert fake.thumbs == ["yt9"]
    with ctx.connect() as conn:
        assert quota.used(conn)["shared"] == 1 + 50 + 50

    # a thumbnail YouTube refuses: the title change still counts, and the reason is shown
    fake = FakeYouTube(thumb_error=http_error(403, "forbidden"))
    ctx.youtube = lambda channel_id: fake
    vid = live_video(ctx, "Another", youtube_id="yt10")
    with pytest.raises(actions.ActionError, match="phone-verified"):
        actions.apply_swap(ctx, vid, title_idx=1, thumb_idx=2)
    with ctx.connect() as conn:
        video = db.get_video(conn, vid)
    assert (video["title"], video["thumb_idx"]) == ("Another: Could You Last?", 0)


# --- holds and ranking ----------------------------------------------------------------------------------

def test_a_7_day_loser_holds_its_family_and_ranking_uses_own_results(ctx):
    run(ctx)  # ideas: oil rig (ocean), flooded subway (underground), shopping mall (city)
    others(ctx, 168)
    loser = live_video(ctx, "Day 1 to Day 365 adrift at sea", family="ocean", days_ago=8)
    reading(ctx, loser, 168, avd_pct=30.0, ctr=3.0)
    assert performance.judge(ctx, loser, 168) == "loser"
    assert any("'ocean' topics go to the bottom of the queue until" in (m["text"] or "") for m in home_messages(ctx))

    winner = live_video(ctx, "Day 1 to Day 100 in a bunker", family="underground", days_ago=8)
    reading(ctx, winner, 48, 50.0, 6.0, verdict="winner")
    with ctx.connect() as conn:
        ranked = performance.ranked_topics(conn, "zombie")
    by_family = {t["family"]: t for t in ranked}
    assert ranked[-1]["family"] == "ocean" and by_family["ocean"]["rank"] == 0
    assert by_family["ocean"]["note"].startswith("held until")
    assert by_family["underground"]["rank"] == pytest.approx(by_family["underground"]["score"] * 1.25)
    assert by_family["underground"]["note"] == "'underground' has done well here (+1)"
    card = topic_cards(ctx)[0]["card"]
    assert next(t for t in card["topics"] if t["family"] == "ocean")["note"].startswith("held until")

    new = topics.propose(ctx, ctx.channel("zombie"))  # new ideas stay out of a held family
    with ctx.connect() as conn:
        families = [r["family"] for r in conn.execute(
            f"SELECT family FROM topics WHERE id IN ({','.join('?' * len(new))})", new)]
    assert families and "ocean" not in families

    # the cadence skips held topics
    ctx.config.topics["cadence"] = True
    with ctx.connect() as conn:
        conn.execute("UPDATE videos SET publish_at = ? WHERE state = 'live'", (time.time() - 3 * DAY,))
        conn.execute("UPDATE topics SET status = 'dismissed' WHERE status = 'queued' AND family != 'ocean'")
    run(ctx)
    with ctx.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM videos WHERE state != 'live'").fetchone()[0] == 0


# --- the daily sign-in check ------------------------------------------------------------------------------

def test_daily_sign_in_check(ctx, monkeypatch):
    ctx.config.youtube.update(mode="live", signin_check=True)
    ctx.config.topics["competitors"] = "off"
    ctx.channel("zombie").youtube["channel_id"] = "UCmine"
    monkeypatch.setattr(auth, "stored", lambda channel_id: {"refresh_token": "rt", "scopes": auth.SCOPES})
    answer = {"items": [{"id": "UCother"}]}
    error = {"value": None}

    class Channels:
        def channels(self):
            return Resource(list=lambda part, mine: Req(answer, error["value"]))
    ctx.youtube = lambda channel_id: Channels()

    def check_now():
        with ctx.connect() as conn:
            conn.execute("UPDATE channels SET signin_checked_at = 0")
        run(ctx)

    def said(text):
        return [m["text"] for m in home_messages(ctx) if text in (m["text"] or "")]

    run(ctx)
    run(ctx)  # not due again
    assert len(said("the stored sign-in is for YouTube channel UCother, not UCmine")) == 1
    app = create_app(ctx, run_engine=False, agents=AgentHub(ctx, online=False))
    with TestClient(app, base_url="http://localhost") as http:
        assert "UCother" in http.get("/api/channels").json()[0]["youtube"]["signin_error"]

    error["value"] = http_error(401, "authError")
    check_now()
    assert len(said("YouTube sign-in check failed: YouTube channels.list failed (401 authError)")) == 1
    check_now()  # the same complaint isn't posted twice
    assert len(said("401 authError")) == 1

    error["value"], answer["items"] = None, [{"id": "UCmine"}]
    check_now()
    assert said("The YouTube sign-in works again.")
    with ctx.connect() as conn:
        assert conn.execute("SELECT signin_error FROM channels WHERE id = 'zombie'").fetchone()[0] is None

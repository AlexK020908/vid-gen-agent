"""Phase 31: Reels posted to Instagram, with a fake Meta and an in-memory keychain (no network, $0).

What matters most is that a short is never posted twice and never posted without the owner's word: every way a post can be
cut off part-way is resumed from its record, and a publish whose reply never came is looked for before trying again.
"""
import json
import time
from dataclasses import replace

import keyring
import pytest

from core import actions, db, metadata
from core.context import make_ctx
from core.engine import Engine
from core.errors import ActionError
from instagram import auth, reels
from instagram.client import InstagramError
from render import ffmpeg
from test_pipeline import to_render_review
from test_tools import call

IG = "17841470487910257"


# --- a fake Meta --------------------------------------------------------------------------------------------------

class FakeMeta:
    """Records every call. `fail` maps a call's name to errors raised in turn the next times it's made; `statuses` is
    what the status checks say, one after another (the last one repeats)."""

    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self.fail: dict[str, list[Exception]] = {}
        self.statuses = ["FINISHED"]
        self.posts: list[dict] = []          # what's on the account, newest first
        self.containers = 0
        self.published_containers: set[str] = set()

    def _maybe_fail(self, name: str) -> None:
        if self.fail.get(name):
            raise self.fail[name].pop(0)

    def account(self, ig_id):
        return {"id": ig_id, "username": "cavemanfilms.tv", "media_count": len(self.posts)}

    def limit(self, ig_id):
        return {"quota_usage": len(self.posts), "quota_total": 100, "quota_duration": 86400}

    def create_reel(self, ig_id, caption, ai_generated, thumb_offset_ms=None):
        self.calls.append(("create", ig_id, caption, ai_generated))
        self._maybe_fail("create")
        self.containers += 1
        cid = f"c{self.containers}"
        return {"id": cid, "uri": f"https://rupload.facebook.com/ig-api-upload/v27.0/{cid}"}

    def upload(self, uri, path):
        self.calls.append(("upload", uri.rsplit("/", 1)[1], path.stat().st_size))
        self._maybe_fail("upload")

    def status(self, container):
        self.calls.append(("status", container))
        if container in self.published_containers:
            return "PUBLISHED"
        return self.statuses.pop(0) if len(self.statuses) > 1 else self.statuses[0]

    def why(self, container):
        return "the video's audio couldn't be read"

    def publish(self, ig_id, container):
        self.calls.append(("publish", container))
        media = f"m{len(self.posts) + 1}"
        self.posts.insert(0, {"id": media, "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S+0000", time.gmtime())})
        self.published_containers.add(container)
        self._maybe_fail("publish")              # Meta posted it, but the reply was lost
        return media

    def recent(self, ig_id, count=5):
        self.calls.append(("recent",))
        return self.posts[:count]

    def media(self, media_id):
        return {"id": media_id, "permalink": f"https://www.instagram.com/reel/{media_id}/"}

    def named(self, name):
        return [c for c in self.calls if c[0] == name]


@pytest.fixture(autouse=True)
def no_waiting(monkeypatch):
    monkeypatch.setattr(reels, "CHECKS_S", (0,) * 5)
    monkeypatch.setattr(reels, "UPLOAD_WAITS_S", (0, 0))


def _post(meta, steps, path, **kw):
    saved = []
    try:
        return reels.post(meta, IG, path, "A caption", True, steps, lambda s: saved.append(json.loads(json.dumps(s))), **kw)
    finally:
        _post.saved = saved


@pytest.fixture
def clip(tmp_path):
    out = tmp_path / "short.mp4"
    _make(out, seconds=4)
    return out


def _make(out, seconds, size="108x192", rate=44100, fps=30):
    ffmpeg.run(["-f", "lavfi", "-i", f"testsrc=size={size}:rate={fps}:duration={seconds}",
                "-f", "lavfi", "-i", f"sine=frequency=440:sample_rate={rate}:duration={seconds}",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", out])


# --- one post, and every way it can be cut off -------------------------------------------------------------------

def test_a_post_makes_a_container_uploads_waits_and_publishes_once(clip):
    meta, steps = FakeMeta(), {}
    meta.statuses = ["IN_PROGRESS", "IN_PROGRESS", "FINISHED"]
    out = _post(meta, steps, clip)
    assert out == {"media_id": "m1", "permalink": "https://www.instagram.com/reel/m1/"}
    assert [c[0] for c in meta.calls if c[0] != "status"] == ["create", "upload", "publish"]
    assert meta.named("create")[0][3] is True                       # Meta's AI info label asked for
    assert len(meta.named("status")) == 3
    assert _post.saved[-1]["media_id"] == "m1"                      # the record is saved as it goes


def test_an_upload_refused_once_is_sent_again_at_once_into_the_same_container(clip):
    meta, steps = FakeMeta(), {}            # the upload host's reply on the first real post, Nov 10, 2026
    meta.fail["upload"] = [InstagramError("Instagram upload failed: Request processing failed")]
    _post(meta, steps, clip)
    assert len(meta.named("create")) == 1 and len(meta.named("upload")) == 2 and len(meta.named("publish")) == 1
    assert {c[1] for c in meta.named("upload")} == {"c1"}


def test_an_upload_cut_off_every_try_waits_for_retry_and_goes_again_into_the_same_container(clip):
    meta, steps = FakeMeta(), {}
    meta.fail["upload"] = [InstagramError("dropped", retriable=True)] * 3
    with pytest.raises(InstagramError) as e:
        _post(meta, steps, clip)
    assert e.value.retriable and len(meta.named("upload")) == 3
    assert steps["container"]["id"] == "c1" and not steps.get("uploaded")
    _post(meta, steps, clip)
    assert len(meta.named("create")) == 1 and len(meta.named("upload")) == 4 and len(meta.named("publish")) == 1


def test_a_refused_token_is_not_sent_again(clip):
    meta, steps = FakeMeta(), {}
    meta.fail["upload"] = [InstagramError("Meta refused the Instagram token", code=190)]
    with pytest.raises(InstagramError) as e:
        _post(meta, steps, clip)
    assert not e.value.retriable and len(meta.named("upload")) == 1


def test_a_publish_whose_reply_was_lost_is_found_not_posted_again(clip):
    meta, steps = FakeMeta(), {}
    meta.fail["publish"] = [InstagramError("timed out", retriable=True)]
    with pytest.raises(InstagramError):
        _post(meta, steps, clip)
    assert "media_id" not in steps and len(meta.posts) == 1          # it did go up
    out = _post(meta, steps, clip)
    assert out["media_id"] == "m1" and len(meta.named("publish")) == 1 and len(meta.posts) == 1


def test_published_but_not_found_stops_rather_than_risk_a_second_post(clip):
    meta, steps = FakeMeta(), {}
    meta.fail["publish"] = [InstagramError("timed out", retriable=True)]
    with pytest.raises(InstagramError):
        _post(meta, steps, clip)
    meta.posts.clear()                                               # say it can't be seen among the newest
    with pytest.raises(InstagramError, match="Look on the account before posting it again"):
        _post(meta, steps, clip)
    assert len(meta.named("publish")) == 1


def test_a_publish_turned_down_is_tried_again_into_the_same_container(clip):
    meta, steps = FakeMeta(), {}
    meta.fail["publish"] = [InstagramError("busy", retriable=True)]
    meta.publish_orig = meta.publish

    def refused(ig_id, container):                                   # refused outright: nothing went up
        meta.calls.append(("publish", container))
        raise meta.fail["publish"].pop(0)
    meta.publish = refused
    with pytest.raises(InstagramError):
        _post(meta, steps, clip)
    meta.publish = meta.publish_orig
    out = _post(meta, steps, clip)
    assert out["media_id"] == "m1" and len(meta.named("create")) == 1 and len(meta.posts) == 1


def test_a_video_meta_cant_process_is_said_and_retry_starts_a_fresh_upload(clip):
    meta, steps = FakeMeta(), {}
    meta.statuses = ["ERROR", "FINISHED"]
    with pytest.raises(InstagramError, match="audio couldn't be read") as e:
        _post(meta, steps, clip)
    assert not e.value.retriable and steps["failed"]
    _post(meta, steps, clip)
    assert [c[1] for c in meta.named("upload")] == ["c1", "c2"] and len(meta.posts) == 1


def test_still_processing_after_ten_minutes_is_retried_without_uploading_again(clip):
    meta, steps = FakeMeta(), {}
    meta.statuses = ["IN_PROGRESS"] * 5 + ["FINISHED"]
    with pytest.raises(InstagramError) as e:
        _post(meta, steps, clip)
    assert e.value.retriable and steps["uploaded"]
    _post(meta, steps, clip)
    assert len(meta.named("upload")) == 1 and len(meta.posts) == 1


def test_a_container_near_meta_s_24_hours_is_made_again(clip):
    meta, steps = FakeMeta(), {}
    meta.fail["upload"] = [InstagramError("dropped", retriable=True)] * 3
    with pytest.raises(InstagramError):
        _post(meta, steps, clip)
    _post(meta, steps, clip, now=lambda: time.time() + 23.5 * 3600)
    assert len(meta.named("create")) == 2 and meta.named("upload")[-1][1] == "c2"


def test_a_finished_post_is_never_sent_again(clip):
    meta, steps = FakeMeta(), {}
    _post(meta, steps, clip)
    _post(meta, steps, clip)
    assert len(meta.named("publish")) == 1 and len(meta.named("create")) == 1


# --- the file and the caption -------------------------------------------------------------------------------------

def test_a_short_is_made_to_meta_s_rules_without_redrawing_a_picture_that_fits(tmp_path, clip):
    out = reels.prepare(clip, tmp_path / "reel.mp4")
    info = reels.describe(out)
    assert info["video"]["codec"] == "h264" and info["audio"] == {"codec": "aac", "rate": 48000, "channels": 2}
    assert reels.problems(out) == []
    with out.open("rb") as f:                                         # the moov atom comes before the picture data
        head = f.read(4096)
    assert b"moov" in head


def _flash_and_click(out, size="108x192", pix="yuv420p"):
    """Black until exactly 1 s, then white, with a click at exactly 1 s: x264 with its usual reordered frames, and AAC at
    44.1 kHz in an MP4 with the usual edit list, as our renders are."""
    ffmpeg.run(["-f", "lavfi", "-i", f"color=black:size={size}:rate=30:duration=4,drawbox=c=white:t=fill:enable='gte(t,1)'",
                "-f", "lavfi", "-i", "aevalsrc='if(between(t,1,1.002),0.9,0)':s=44100:d=4",
                "-c:v", "libx264", "-pix_fmt", pix, "-c:a", "aac", "-shortest", out])


def _white_and_click(path):
    import array
    import re
    import subprocess
    shown = subprocess.run([ffmpeg.exe(), "-v", "info", "-i", str(path), "-vf", "showinfo", "-f", "null", "-"],
                           capture_output=True, text=True).stderr
    white = next(float(m.group(1)) for m in re.finditer(r"pts_time:([\d.]+).*?mean:\[(\d+)", shown) if int(m.group(2)) > 128)
    raw = subprocess.run([ffmpeg.exe(), "-v", "error", "-i", str(path), "-f", "s16le", "-ac", "1", "-ar", "48000", "-"],
                         capture_output=True).stdout
    samples = array.array("h")
    samples.frombytes(raw)
    click = next(i for i, x in enumerate(samples) if abs(x) > 8000) / 48000
    return white, click


@pytest.mark.parametrize("size,pix", [("108x192", "yuv420p"), ("2560x1440", "yuv444p")], ids=["copied", "re-encoded"])
def test_with_no_edit_list_picture_and_sound_still_land_on_their_moment(tmp_path, size, pix):
    # The owner on the systems shorts: every sound is a line running, and it has to be on its frame. Meta's "no edit
    # lists" put the sound 21 ms late and the picture two frames late until prepare() made up for both.
    src = tmp_path / "src.mp4"
    _flash_and_click(src, size, pix)
    assert _white_and_click(src) == (1.0, 1.0)
    white, click = _white_and_click(reels.prepare(src, tmp_path / "reel.mp4"))
    assert abs(white - 1.0) < 1e-3 and abs(click - 1.0) < 1e-3


def test_what_breaks_meta_s_rules_is_said_in_words(tmp_path):
    short = tmp_path / "short.mp4"
    _make(short, seconds=2)
    assert any("runs 2.0 s" in p for p in reels.problems(short))
    with pytest.raises(ActionError, match=r"doesn't fit Instagram's rules for Reels: it runs 2\.\d s"):
        reels.prepare(short, tmp_path / "reel.mp4")
    assert reels.problems(tmp_path / "missing.mp4") == [f"there's no file at {tmp_path / 'missing.mp4'}"]


def test_a_wide_or_odd_picture_is_redrawn_to_fit(tmp_path):
    wide = tmp_path / "wide.mp4"
    ffmpeg.run(["-f", "lavfi", "-i", "testsrc=size=2560x1440:rate=30:duration=3.2", "-c:v", "libx264", "-pix_fmt",
                "yuv444p", wide])
    out = reels.prepare(wide, tmp_path / "reel.mp4")
    info = reels.describe(out)["video"]
    assert info["width"] == 1920 and info["pix"].startswith("yuv420p") and reels.problems(out) == []


def test_the_caption_is_just_the_title_and_the_hashtags():
    text = reels.caption("Why doesn't a woodpecker get a concussion?", ["facts", "#science", "bird brains"])
    assert text == "Why doesn't a woodpecker get a concussion?" + chr(10) * 2 + "#facts #science #birdbrains"
    assert reels.caption("Just a title") == "Just a title"
    assert reels.caption_problems(text) == []


def test_the_models_credits_fit_one_line_kept_apart_from_the_caption():
    credits = ['"Human Brain" by RISD Nature Lab (https://sketchfab.com/3d-models/human-brain-06dd), licensed under CC BY 4.0: '
               'http://creativecommons.org/licenses/by/4.0/',
               '"Skull downloadable" by @martinjario (https://sketchfab.com/3d-models/skull-1a9d), licensed under CC BY 4.0: '
               'http://creativecommons.org/licenses/by/4.0/',
               '"Picus viridis, skull" by Museu de Ciències Naturals de Barcelona (https://sketchfab.com/3d-models/picus-a195), '
               'licensed under CC BY 4.0: http://creativecommons.org/licenses/by/4.0/']
    assert reels.credit_line(credits) == ("3D models adapted from RISD Nature Lab, martinjario and "
                                          "Museu de Ciències Naturals de Barcelona (CC BY 4.0).")
    assert reels.credit_line(['"Eagle" by Ann (https://x)', "Owl by Bob, CC BY"]) == \
        "3D models adapted from Ann and Owl by Bob, CC BY (CC BY 4.0)."     # a line in another shape is kept whole
    assert reels.credit_line([]) == ""


def test_a_caption_over_instagram_s_limits_is_refused():
    assert reels.caption_problems("") == ["the caption is empty"]
    assert "2201 characters" in reels.caption_problems("x" * 2201)[0]
    assert "31 hashtags" in reels.caption_problems(" ".join(f"#t{i}" for i in range(31)))[0]
    assert "21 accounts" in reels.caption_problems(" ".join(f"@u{i}" for i in range(21)))[0]
    assert reels.caption_problems("mail me at a@b.com, #1 fan") == []


# --- the token ----------------------------------------------------------------------------------------------------

def test_the_token_lives_in_the_keychain_only():
    with pytest.raises(ActionError, match="instagram connect"):
        auth.require()
    auth.store("  EAAtoken \n")
    assert keyring.get_password("stickfleet-instagram", "token") == "EAAtoken" and auth.require() == "EAAtoken"
    with pytest.raises(ActionError, match="empty"):
        auth.store("   ")


def test_meta_s_errors_say_what_to_do_and_whether_to_try_again():
    import httpx2
    from instagram.client import _error

    def said(status, body):
        return _error("publish", httpx2.Response(status, json=body))
    token = said(400, {"error": {"message": "Error validating access token", "code": 190}})
    assert "make a new one" in str(token).lower() and not token.retriable
    assert said(400, {"error": {"message": "Please retry", "code": 2, "is_transient": True}}).retriable
    assert said(500, {"error": {"message": "oops", "code": 100}}).retriable
    refused = said(400, {"error": {"message": "The video file you selected is in a format that we don't support.",
                                   "error_user_msg": "Unsupported format", "code": 352}})
    assert not refused.retriable and "Unsupported format" in str(refused)
    assert said(400, {"debug_info": {"retriable": True, "type": "ProcessingFailedError", "message": "busy"}}).retriable


def test_the_token_never_goes_in_a_url():
    import httpx2
    from instagram.client import Client
    seen = []

    def handler(request):
        seen.append(request)
        return httpx2.Response(200, json={"id": "1", "name": "Reel Publisher System User"})
    cl = Client("SECRET", http=httpx2.Client(transport=httpx2.MockTransport(handler)))
    cl.whoami()
    assert "SECRET" not in str(seen[0].url) and seen[0].headers["authorization"] == "Bearer SECRET"


# --- through the pipeline -----------------------------------------------------------------------------------------

@pytest.fixture
def ig_ctx(tmp_path):
    ctx = make_ctx(data_dir=tmp_path, overrides={"mode": "stub", "stub": {"scenes": 6}, "engine": {"retry_backoff_s": 0},
                                                 "render": {"engine": "ffmpeg"}, "topics": {"competitors": "off"}})
    zombie = ctx.config.channels["zombie"]
    ctx.config.channels["zombie"] = replace(zombie, instagram={"account_id": IG, "username": "cavemanfilms.tv",
                                                               "hashtags": ["facts"]})
    return ctx


def _approved(ctx) -> int:
    vid = actions.new_video(ctx, "zombie", "Day 1 to Day 365 on an oil rig")
    to_render_review(ctx, vid)
    actions.pick(ctx, vid, title_idx=0, thumb_idx=0)
    actions.approve(ctx, vid, "render")
    return vid


def _video(ctx, vid):
    with ctx.connect() as conn:
        return db.get_video(conn, vid)


def test_publish_posts_the_short_at_once_and_it_is_live_with_its_link(ig_ctx, tmp_path, monkeypatch):
    ctx = ig_ctx
    vid = _approved(ctx)
    with ctx.connect() as conn:
        card = metadata.publish_meta(ctx, conn, _video(ctx, vid))
    assert card["to"] == "instagram" and card["caption"].endswith("#facts") and card["ai_disclosure"] is False   # the owner turned the label down, Nov 10

    actions.update_publish(ctx, vid, caption="Day one. #facts")
    with pytest.raises(ActionError, match="an Instagram post has a title, a caption and the AI label"):
        actions.update_publish(ctx, vid, tags=["x"])

    ctx.config.instagram["mode"] = "live"
    with pytest.raises(ActionError, match="no Instagram token yet"):
        actions.request_publish(ctx, vid)
    auth.store("EAAtoken")
    ctx.instagram = FakeMeta()
    monkeypatch.setattr(reels, "prepare", lambda src, out: (out.parent.mkdir(parents=True, exist_ok=True),
                                                            out.write_bytes(src.read_bytes()), out)[2])
    said, err = call(ctx, "publish", {"video_id": vid})
    assert not err and "Posting it to Instagram @cavemanfilms.tv now" in said
    Engine(ctx).run_until_idle()

    v = _video(ctx, vid)
    assert v["state"] == "live" and v["instagram_id"] == "m1" and v["youtube_id"] is None
    assert ctx.instagram.named("create")[0][2] == "Day one. #facts"
    assert json.loads(v["publish_json"])["permalink"] == "https://www.instagram.com/reel/m1/"
    with ctx.connect() as conn:
        texts = [r["text"] for r in conn.execute("SELECT text FROM messages WHERE video_id = ?", (vid,))]
    assert any("Posted to Instagram @cavemanfilms.tv: https://www.instagram.com/reel/m1/" in t for t in texts)

    # two days on, there are no YouTube numbers to read for it, and nothing tries
    with ctx.connect() as conn:
        conn.execute("UPDATE videos SET publish_at = ? WHERE id = ?", (time.time() - 3 * 86400, vid))
    Engine(ctx).run_until_idle()
    with ctx.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM metrics WHERE video_id = ?", (vid,)).fetchone()[0] == 0
    with pytest.raises(ActionError, match="an Instagram post has neither"):
        actions.suggest_swap(ctx, vid)


def test_in_practice_mode_nothing_is_sent_and_what_would_be_is_written_out(ig_ctx):
    ctx = ig_ctx
    vid = _approved(ctx)
    ctx.instagram = FakeMeta()
    actions.request_publish(ctx, vid)
    Engine(ctx).run_until_idle()
    v = _video(ctx, vid)
    assert v["state"] == "live" and v["instagram_id"] == f"stub-ig-{vid}" and ctx.instagram.calls == []
    sent = json.loads((ctx.media(vid) / "instagram_request.json").read_text(encoding="utf-8"))
    assert sent["account_id"] == IG and sent["media_type"] == "REELS" and sent["is_ai_generated"] is False


def test_a_failed_post_waits_for_retry_and_carries_on_where_it_stopped(ig_ctx, monkeypatch):
    ctx = ig_ctx
    vid = _approved(ctx)
    ctx.config.instagram["mode"] = "live"
    auth.store("EAAtoken")
    ctx.instagram = meta = FakeMeta()
    meta.statuses = ["ERROR", "FINISHED"]
    monkeypatch.setattr(reels, "prepare", lambda src, out: (out.parent.mkdir(parents=True, exist_ok=True),
                                                            out.write_bytes(src.read_bytes()), out)[2])
    actions.request_publish(ctx, vid)
    Engine(ctx).run_until_idle()
    v = _video(ctx, vid)
    assert v["state"] == "failed" and "audio couldn't be read" in v["error"] and meta.posts == []
    actions.retry(ctx, vid)
    Engine(ctx).run_until_idle()
    v = _video(ctx, vid)
    assert v["state"] == "live" and len(meta.posts) == 1 and len(meta.named("publish")) == 1


def test_a_youtube_channel_is_untouched(tmp_path):
    ctx = make_ctx(data_dir=tmp_path, overrides={"mode": "stub", "stub": {"scenes": 6}, "engine": {"retry_backoff_s": 0},
                                                 "render": {"engine": "ffmpeg"}, "topics": {"competitors": "off"}})
    assert not ctx.config.channels["zombie"].on_instagram
    vid = _approved(ctx)
    with pytest.raises(ActionError, match="a YouTube video has no"):
        actions.update_publish(ctx, vid, caption="x")
    actions.request_publish(ctx, vid)
    Engine(ctx).run_until_idle()
    assert _video(ctx, vid)["state"] == "scheduled" and _video(ctx, vid)["instagram_id"] is None

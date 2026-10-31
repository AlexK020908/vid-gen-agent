"""YouTube publishing and sign-in with a fake API service and an in-memory keychain (no network, $0).

Also the Remotion render, when render/remotion/node_modules exists.
"""
import json
import re
import shutil
import time

import httplib2
import keyring
import keyring.backend
import pytest
import yaml
from fastapi.testclient import TestClient
from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials
from googleapiclient.errors import HttpError

from agent.harness import AgentHub
from core import actions, db
from core.config import ROOT
from core.context import make_ctx
from core.errors import ActionError
from render import ffmpeg, remotion_render
from server.app import create_app
from test_pipeline import run, to_render_review
from youtube import auth, quota

TOKEN = {"refresh_token": "rt-1", "scopes": auth.SCOPES, "youtube_channel_id": "UCfake", "title": "Fake Zombie"}


# --- fakes -------------------------------------------------------------------

def http_error(status: int, reason: str, message: str = "nope") -> HttpError:
    content = json.dumps({"error": {"message": message, "errors": [{"reason": reason, "message": message}]}})
    return HttpError(httplib2.Response({"status": status}), content.encode(), uri="https://fake")


class Request:
    def __init__(self, service, method: str, kwargs: dict) -> None:
        self.service, self.method, self.kwargs = service, method, kwargs

    def execute(self, num_retries: int = 0):
        return self.service.call(self.method, self.kwargs)

    def next_chunk(self, num_retries: int = 0):  # the whole file in one chunk
        return None, self.service.call(self.method, self.kwargs)


class Resource:
    def __init__(self, service, name: str) -> None:
        self.service, self.name = service, name

    def __getattr__(self, verb: str):
        return lambda **kwargs: Request(self.service, f"{self.name}.{verb}", kwargs)


class FakeYouTube:
    """Stands in for googleapiclient's youtube v3 service. `fail[method]` is a list of exceptions to raise next."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []
        self.fail: dict[str, list[Exception]] = {}
        self.privacy = "private"
        self.uploads: list[dict] = []

    def videos(self): return Resource(self, "videos")
    def thumbnails(self): return Resource(self, "thumbnails")
    def captions(self): return Resource(self, "captions")
    def playlistItems(self): return Resource(self, "playlistItems")
    def channels(self): return Resource(self, "channels")

    def methods(self) -> list[str]:
        return [m for m, _ in self.calls]

    def call(self, method: str, kw: dict) -> dict:
        self.calls.append((method, kw))
        if method == "videos.insert":  # YouTube has the file even if the reply gets lost below
            self.uploads.append({"snippet": {"title": kw["body"]["snippet"]["title"], "publishedAt": "2099-01-01T00:00:00Z",
                                             "resourceId": {"videoId": "yt123"}}})
        if self.fail.get(method):
            raise self.fail[method].pop(0)
        return {
            "videos.insert": {"id": "yt123"},
            "thumbnails.set": {},
            "captions.insert": {"id": "cap1"},
            "playlistItems.insert": {"id": "pli1"},
            "videos.list": {"items": [{"status": {"privacyStatus": self.privacy, "uploadStatus": "processed"}}]},
            "channels.list": {"items": [{"id": "UCfake", "snippet": {"title": "Fake Zombie"},
                                         "contentDetails": {"relatedPlaylists": {"uploads": "UUfake"}}}]},
            "playlistItems.list": {"items": self.uploads},
        }[method]


class MemoryKeyring(keyring.backend.KeyringBackend):
    priority = 1

    def __init__(self) -> None:
        super().__init__()
        self.store: dict[tuple[str, str], str] = {}

    def get_password(self, service, username):
        return self.store.get((service, username))

    def set_password(self, service, username, password):
        self.store[(service, username)] = password


# --- fixtures -------------------------------------------------------------------

@pytest.fixture
def memory_keyring():
    old = keyring.get_keyring()
    backend = MemoryKeyring()
    keyring.set_keyring(backend)
    auth._cache.clear()
    yield backend
    keyring.set_keyring(old)
    auth._cache.clear()


@pytest.fixture
def ctx(tmp_path, memory_keyring):
    # A copy of the project: connecting writes youtube.channel_id into the channel YAML.
    root = tmp_path / "project"
    root.mkdir()
    shutil.copy(ROOT / "stickfleet.yaml", root)
    shutil.copytree(ROOT / "channels", root / "channels")
    (root / "secrets").mkdir()
    (root / "secrets" / "client_secret.json").write_text(json.dumps({"installed": {
        "client_id": "cid.apps.googleusercontent.com", "client_secret": "csecret",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth", "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": ["http://localhost"]}}), encoding="utf-8")
    ctx = make_ctx(root=root, data_dir=tmp_path / "data",
                   overrides={"mode": "stub", "stub": {"scenes": 6}, "engine": {"retry_backoff_s": 0},
                              "render": {"engine": "ffmpeg"}, "topics": {"competitors": "off"}, "youtube": {"mode": "live", "reach": False, "signin_check": False}})
    ctx.youtube_fake = FakeYouTube()
    ctx.youtube = lambda channel_id: ctx.youtube_fake
    ctx.channel("zombie").youtube["playlist_id"] = "PLseries"
    return ctx


def ready_to_publish(ctx) -> int:
    vid = actions.new_video(ctx, "zombie", "Day 1 to Day 365 on an oil rig")
    to_render_review(ctx, vid)
    actions.pick(ctx, vid, title_idx=0, thumb_idx=0)
    actions.approve(ctx, vid, "render")
    return vid


def connect(ctx) -> None:
    keyring.set_password(auth.SERVICE, "zombie", json.dumps(TOKEN))


def get(ctx, vid):
    with ctx.connect() as conn:
        return db.get_video(conn, vid)


def texts(ctx, vid) -> list[str]:
    with ctx.connect() as conn:
        return [r["text"] for r in conn.execute("SELECT text FROM messages WHERE video_id = ? ORDER BY id", (vid,))]


# --- publish -------------------------------------------------------------------

def test_publish_sequence_then_live(ctx):
    vid = ready_to_publish(ctx)
    with pytest.raises(ActionError, match="connect Lone Stick Survivor to YouTube first"):
        actions.request_publish(ctx, vid)
    connect(ctx)
    actions.request_publish(ctx, vid)
    run(ctx)

    v, yt = get(ctx, vid), ctx.youtube_fake
    assert v["state"] == "scheduled" and v["youtube_id"] == "yt123"
    assert yt.methods() == ["videos.insert", "thumbnails.set", "captions.insert", "playlistItems.insert"]
    insert = yt.calls[0][1]
    assert insert["part"] == "snippet,status"
    status = insert["body"]["status"]
    assert status["privacyStatus"] == "private" and status["containsSyntheticMedia"] is True
    assert status["selfDeclaredMadeForKids"] is False
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", status["publishAt"])
    assert yt.calls[2][1]["body"]["snippet"] == {"videoId": "yt123", "language": "en", "name": "English",
                                                 "isDraft": False}
    assert yt.calls[3][1]["body"]["snippet"]["playlistId"] == "PLseries"
    steps = json.loads(v["publish_json"])["steps"]
    assert steps["upload"] == "yt123" and steps["captions"] == "cap1" and steps["playlist"] == "pli1"
    with ctx.connect() as conn:
        assert quota.used(conn) == {"uploads": 1, "shared": 500}
        upload = conn.execute("""SELECT card_json, card_status FROM messages WHERE video_id = ?
                                 AND json_extract(card_json, '$.stage') = 'upload'""", (vid,)).fetchone()
    assert json.loads(upload["card_json"])["done"] == 100 and upload["card_status"] == "done"
    assert any("studio.youtube.com/video/yt123/edit" in (t or "") for t in texts(ctx, vid))

    # After publishAt: still private on YouTube, so it waits; then public, so it goes live.
    with ctx.connect() as conn:
        db.update_video(conn, vid, publish_at=time.time() - 1)
    run(ctx)
    assert get(ctx, vid)["state"] == "scheduled" and get(ctx, vid)["lease_until"] > time.time() + 60
    yt.privacy = "public"
    with ctx.connect() as conn:
        db.update_video(conn, vid, lease_until=None)
    run(ctx)
    assert get(ctx, vid)["state"] == "live"
    assert "Video is live: https://youtu.be/yt123" in texts(ctx, vid)


def test_retry_resumes_after_a_failed_step(ctx):
    vid = ready_to_publish(ctx)
    connect(ctx)
    yt = ctx.youtube_fake
    yt.fail["captions.insert"] = [http_error(503, "backendError")] * 3
    actions.request_publish(ctx, vid)
    run(ctx)
    v = get(ctx, vid)
    assert v["state"] == "failed" and v["resume_state"] == "publishing" and "captions.insert failed (503" in v["error"]
    assert v["youtube_id"] == "yt123"  # stored as soon as the upload finished

    actions.retry(ctx, vid)
    run(ctx)
    assert get(ctx, vid)["state"] == "scheduled"
    counts = {m: yt.methods().count(m) for m in set(yt.methods())}
    assert counts == {"videos.insert": 1, "thumbnails.set": 1, "captions.insert": 4, "playlistItems.insert": 1}


def test_lost_upload_reply_is_found_instead_of_uploading_twice(ctx):
    vid = ready_to_publish(ctx)
    connect(ctx)
    yt = ctx.youtube_fake
    yt.fail["videos.insert"] = [TimeoutError("the connection dropped after the last chunk")]
    actions.request_publish(ctx, vid)
    run(ctx)
    assert get(ctx, vid)["state"] == "scheduled"
    assert yt.methods().count("videos.insert") == 1
    assert any("Found the earlier upload (yt123)" in (t or "") for t in texts(ctx, vid))


def test_errors_that_need_the_person_fail_at_once(ctx):
    vid = ready_to_publish(ctx)
    connect(ctx)
    ctx.youtube_fake.fail["thumbnails.set"] = [http_error(403, "forbidden", "The thumbnail can't be set.")]
    actions.request_publish(ctx, vid)
    run(ctx)
    v = get(ctx, vid)
    assert v["state"] == "failed" and "phone-verified" in v["error"]
    assert ctx.youtube_fake.methods().count("thumbnails.set") == 1  # not retried


def test_quota_refused_before_uploading(ctx):
    vid = ready_to_publish(ctx)
    connect(ctx)
    with ctx.connect() as conn:
        conn.execute("INSERT INTO quota (date, bucket, units) VALUES (?, 'shared', 9700)", (quota.today(),))
    actions.request_publish(ctx, vid)
    run(ctx)
    v = get(ctx, vid)
    assert v["state"] == "failed" and "not enough YouTube shared quota" in v["error"]
    assert ctx.youtube_fake.calls == []


def test_past_publish_time_goes_back_to_the_card(ctx):
    vid = ready_to_publish(ctx)
    connect(ctx)
    with pytest.raises(ActionError, match="at least 15 minutes away"):
        actions.request_publish(ctx, vid, publish_at=time.time() + 300)
    actions.request_publish(ctx, vid, publish_at=time.time() + 3600)
    with ctx.connect() as conn:  # the click was a while ago; the slot is now minutes away
        db.update_video(conn, vid, publish_json=json.dumps({**json.loads(get(ctx, vid)["publish_json"]),
                                                            "publish_at": time.time() + 60}))
    run(ctx)
    assert get(ctx, vid)["state"] == "render_approved"
    assert ctx.youtube_fake.calls == []
    with ctx.connect() as conn:
        active = conn.execute("""SELECT COUNT(*) FROM messages WHERE video_id = ? AND card_status = 'active'
                                 AND json_extract(card_json, '$.kind') = 'publish'""", (vid,)).fetchone()[0]
    assert active == 1


# --- sign-in --------------------------------------------------------------------

class FakeFlow:
    def __init__(self, creds) -> None:
        self.creds = creds
        self.kwargs: dict = {}

    def run_local_server(self, **kwargs):
        self.kwargs = kwargs
        return self.creds


def test_connect_stores_token_in_keychain_and_channel_id_in_yaml(ctx, memory_keyring, monkeypatch):
    creds = Credentials(token="at", refresh_token="rt-new", scopes=auth.SCOPES, granted_scopes=auth.SCOPES)
    flow = FakeFlow(creds)
    monkeypatch.setattr(auth.InstalledAppFlow, "from_client_secrets_file", lambda path, scopes: flow)
    monkeypatch.setattr(auth, "build", lambda *a, **kw: ctx.youtube_fake)

    result = auth.connect(ctx, "zombie")
    assert result == {"channel_id": "zombie", "youtube_channel_id": "UCfake", "title": "Fake Zombie"}
    assert flow.kwargs["prompt"] == "consent" and flow.kwargs["port"] == 0
    stored = json.loads(memory_keyring.store[(auth.SERVICE, "zombie")])
    assert stored["refresh_token"] == "rt-new" and "csecret" not in json.dumps(stored)
    text = (ctx.config.root / "channels" / "zombie.yaml").read_text(encoding="utf-8")
    assert re.search(r"^  channel_id: UCfake +# filled in by Connect channel$", text, re.M)
    assert yaml.safe_load(text)["youtube"]["channel_id"] == "UCfake"
    assert ctx.channel("zombie").youtube["channel_id"] == "UCfake"
    with ctx.connect() as conn:
        assert conn.execute("SELECT youtube_channel_id FROM channels WHERE id = 'zombie'").fetchone()[0] == "UCfake"

    # Loading: client id and secret come from client_secret.json, the refresh token from the keychain.
    seen = {}
    monkeypatch.setattr(Credentials, "refresh", lambda self, request: seen.update(
        client_id=self.client_id, refresh_token=self.refresh_token))
    auth.credentials(ctx, "zombie")
    assert seen == {"client_id": "cid.apps.googleusercontent.com", "refresh_token": "rt-new"}

    def revoked(self, request):
        raise RefreshError("invalid_grant: Token has been expired or revoked.")
    monkeypatch.setattr(Credentials, "refresh", revoked)
    auth._cache.clear()
    with pytest.raises(ActionError, match="Connect the channel again"):
        auth.credentials(ctx, "zombie")


def test_connect_refuses_a_partial_grant(ctx, monkeypatch):
    creds = Credentials(token="at", refresh_token="rt", scopes=auth.SCOPES, granted_scopes=auth.SCOPES[:1])
    monkeypatch.setattr(auth.InstalledAppFlow, "from_client_secrets_file", lambda path, scopes: FakeFlow(creds))
    with pytest.raises(ActionError, match="youtube.force-ssl, youtube.readonly, yt-analytics.readonly"):
        auth.connect(ctx, "zombie")


def test_credentials_without_a_token(ctx):
    with pytest.raises(ActionError, match="Connect the channel again"):
        auth.credentials(ctx, "zombie")


def test_set_channel_id_keeps_comments(tmp_path):
    path = tmp_path / "c.yaml"
    path.write_text("id: c  # the id\nyoutube:\n  # which channel\n  playlist_id: null\n  ai_disclosure: true\n"
                    "competitors: []\n", encoding="utf-8")
    auth.set_channel_id(path, "UCabc")
    assert path.read_text(encoding="utf-8") == ("id: c  # the id\nyoutube:\n  # which channel\n  playlist_id: null\n"
                                                "  ai_disclosure: true\n  channel_id: UCabc\ncompetitors: []\n")
    auth.set_channel_id(path, "UCxyz")
    assert yaml.safe_load(path.read_text(encoding="utf-8"))["youtube"]["channel_id"] == "UCxyz"


def test_connect_endpoint_and_channel_status(ctx, monkeypatch):
    monkeypatch.setattr(auth, "connect", lambda ctx, channel_id: (
        connect(ctx), {"channel_id": channel_id, "youtube_channel_id": "UCfake", "title": "Fake Zombie"})[1])
    app = create_app(ctx, run_engine=False, agents=AgentHub(ctx, online=False))
    with TestClient(app, base_url="http://localhost") as client:
        yt = client.get("/api/channels").json()[0]["youtube"]
        assert yt["mode"] == "live" and yt["client_secret"] and not yt["connected"]
        assert client.post("/api/channels/zombie/connect").json()["title"] == "Fake Zombie"
        yt = client.get("/api/channels").json()[0]["youtube"]
        assert yt["connected"] and yt["title"] == "Fake Zombie"
        home = client.get("/api/channels").json()[0]["home_thread_id"]
        assert client.get(f"/api/threads/{home}/messages").json()[-1]["text"].startswith("Connected to YouTube channel")


def test_no_delete_calls_in_the_youtube_package():
    for path in (ROOT / "youtube").glob("*.py"):
        assert not re.search(r"\.delete\w*\s*\(", path.read_text(encoding="utf-8")), f"{path.name} calls a delete"


# --- Remotion ------------------------------------------------------------------

def media_duration_ms(path) -> int:
    out = ffmpeg.probe(path)
    h, m, s = re.search(r"Duration: (\d+):(\d+):([\d.]+)", out).groups()
    return round((int(h) * 3600 + int(m) * 60 + float(s)) * 1000)


@pytest.mark.skipif(remotion_render.missing() is not None, reason="Remotion isn't installed (render/remotion)")
def test_remotion_renders_and_matches_the_audio(tmp_path):
    from core.config import load
    from providers.images import StubImages
    from providers.tts import StubTTS
    from providers.video import StubVideo
    from render.render import render_video

    channel = load().channels["zombie"]
    items = []
    for idx, line in enumerate(["Day one. The radio goes quiet.", "I fill every bottle with water, just in case.",
                                "By night the street is empty."], start=1):
        still, audio = tmp_path / f"s{idx}.png", tmp_path / f"s{idx}.wav"
        StubImages().still(channel, line, f"S{idx}", still)
        result, _ = StubTTS().speak(channel, line, audio)
        clip = None
        if idx == 2:
            clip = tmp_path / "c2.mp4"
            StubVideo().clip(channel, still, line, clip, 2)
        items.append({"idx": idx, "beat_idx": idx - 1, "narration": line, "duration_ms": result["duration_ms"],
                      "audio": str(audio), "still": str(still), "clip": str(clip) if clip else None,
                      "words": result["words"]})
    beats = [{"label": f"Day {n}", "title": f"Beat {n}"} for n in (1, 2, 3)]
    seen = []
    out = render_video(items, beats, tmp_path / "render", lambda d, t: seen.append(d), "remotion")
    total = sum(i["duration_ms"] for i in items)
    assert out["duration_ms"] == total
    assert abs(media_duration_ms(out["video"]) - total) <= 100
    assert out["highlight"].exists() and media_duration_ms(out["highlight"]) <= total + 100
    assert seen and seen[-1] == 100
    assert not list((tmp_path / "render").glob("*_public"))  # staging folder cleaned up

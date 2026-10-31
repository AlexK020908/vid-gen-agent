"""ElevenLabs voice, fal pictures and fal clips with fakes: requests, word timings, the reference upload,
retries, costs, the budget downgrade, thumbnail captions and how a clip sits in the render.

ElevenLabs is faked at the HTTP layer (httpx2's MockTransport) and returns a real MP3; fal is a fake
client object plus a fake file host that serves real PNGs and MP4s. Real ffmpeg, no network, $0. The
live tests (a fraction of a cent, about $0.04, and about $0.35 for a 3-second clip) are skipped without
the keys.
"""
import base64
import io
import json
import os
import shutil
import threading
from pathlib import Path

import fal_client
import httpx2
import pytest
from dotenv import load_dotenv
from PIL import Image, ImageChops, ImageStat

from core import actions, db
from core.config import ROOT
from core.context import make_ctx
from core.engine import Engine
from core.errors import FinalError
from providers import prompts
from providers.elevenlabs import ElevenLabsTTS, words_from
from providers.fal import FalImages, FalVideo
from providers.images import CAPTION_FILL, StubImages
from providers.tts import StubTTS
from render import ffmpeg
from render.render import render_video

load_dotenv(ROOT / ".env")  # only the live tests use the keys


# --- fakes ---------------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def mp3(tmp_path_factory) -> bytes:
    path = tmp_path_factory.mktemp("audio") / "tone.mp3"
    ffmpeg.run(["-f", "lavfi", "-i", "sine=frequency=330:duration=2", "-c:a", "libmp3lame", "-b:a", "128k", path])
    return path.read_bytes()


class FakeElevenLabs:
    """Answers with-timestamps requests: the MP3 above and evenly spaced character timings over 2 s.
    `errors` is a list of (status, body, headers) answered first, in order."""

    def __init__(self, mp3: bytes, *errors) -> None:
        self.mp3, self.errors, self.requests = mp3, list(errors), []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        body = json.loads(request.content)
        self.requests.append({"path": request.url.path, "params": dict(request.url.params), "body": body,
                              "key": request.headers.get("xi-api-key")})
        if self.errors:
            status, payload, headers = self.errors.pop(0)
            return httpx2.Response(status, json=payload, headers=headers)
        chars = list(body["text"])
        step = 2.0 / len(chars)
        alignment = {"characters": chars, "character_start_times_seconds": [i * step for i in range(len(chars))],
                     "character_end_times_seconds": [(i + 1) * step for i in range(len(chars))]}
        return httpx2.Response(200, json={"audio_base64": base64.b64encode(self.mp3).decode(),
                                          "alignment": alignment, "normalized_alignment": alignment})


def png(size=(1376, 768), color=(250, 250, 250)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, "PNG")
    return buf.getvalue()


@pytest.fixture(scope="module")
def mp4(tmp_path_factory) -> bytes:
    """A 2-second clip whose every frame differs (testsrc2), so a held frame is easy to tell from a moving one."""
    path = tmp_path_factory.mktemp("video") / "clip.mp4"
    ffmpeg.run(["-f", "lavfi", "-i", "testsrc2=size=640x360:rate=24:duration=2", "-pix_fmt", "yuv420p", path])
    return path.read_bytes()


class FakeFal:
    """Stands in for fal_client.SyncClient. `fail` is a list of exceptions raised by subscribe first.
    Image-to-video models answer with a clip, after `wait` seconds (so parallel calls overlap)."""

    def __init__(self, *fail, wait: float = 0) -> None:
        self.uploads, self.calls, self.fail, self.wait = [], [], list(fail), wait

    def upload_file(self, path):
        self.uploads.append(Path(path))
        return f"https://v3.fal.media/files/ref{len(self.uploads)}.png"

    def subscribe(self, application, arguments, client_timeout=None):
        self.calls.append({"model": application, **arguments})
        if self.fail:
            raise self.fail.pop(0)
        if "image-to-video" in application:
            threading.Event().wait(self.wait)  # time.sleep is patched out in these tests
            return {"video": {"url": f"https://v3.fal.media/files/clip{len(self.calls)}.mp4"}, "seed": 1}
        return {"images": [{"url": f"https://v3.fal.media/files/out{len(self.calls)}.png"}], "description": ""}


def image_host(clip: bytes = b"") -> httpx2.Client:
    """fal's file host: a PNG for pictures, `clip` for .mp4 links."""
    return httpx2.Client(transport=httpx2.MockTransport(
        lambda request: httpx2.Response(200, content=clip if request.url.path.endswith(".mp4") else png())))


def fal_error(status: int, error_type: str | None = None):
    return fal_client.FalClientHTTPError("nope", status, {}, response=None, error_type=error_type)


# --- fixtures --------------------------------------------------------------------------------------

@pytest.fixture
def ctx(tmp_path, monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)  # retries back off instantly
    root = tmp_path / "project"
    root.mkdir()
    shutil.copy(ROOT / "stickfleet.yaml", root)
    for name in ("channels", "prompts"):
        shutil.copytree(ROOT / name, root / name)
    ctx = make_ctx(root=root, data_dir=tmp_path / "data",
                   overrides={"mode": "live", "providers": {"llm": "stub", "tts": "elevenlabs", "images": "fal",
                                                            "video": "stub"},
                              "stub": {"scenes": 6}, "engine": {"retry_backoff_s": 0},
                              "agent": {"comment_on_gates": False}, "render": {"engine": "ffmpeg"}, "topics": {"competitors": "off"}})
    ctx.channel("zombie").voice_id = "voice123"
    return ctx


def use_voice(ctx, fake: FakeElevenLabs) -> ElevenLabsTTS:
    http = httpx2.Client(transport=httpx2.MockTransport(fake), headers={"xi-api-key": "test-key"})
    ctx.tts = ElevenLabsTTS(ctx.config, http=http)
    return ctx.tts


def use_fal(ctx, fake: FakeFal) -> FalImages:
    ctx.images = FalImages(ctx.config, client=fake, http=image_host())
    return ctx.images


def use_clips(ctx, fake: FakeFal, clip: bytes) -> FalVideo:
    ctx.video = FalVideo(ctx.config, client=fake, http=image_host(clip))
    return ctx.video


def to_render_review(ctx, topic="A week on a rooftop", at_script=None) -> int:
    vid = actions.new_video(ctx, "zombie", topic)
    Engine(ctx).run_until_idle()
    actions.approve(ctx, vid, "outline")
    Engine(ctx).run_until_idle()
    if at_script:
        at_script(vid)
    actions.approve(ctx, vid, "script")
    Engine(ctx).run_until_idle()
    return vid


def scenes(ctx, vid) -> dict:
    with ctx.connect() as conn:
        return {s["idx"]: s for s in db.scenes_for(conn, vid)}


def frame(video_path, t: float, out: Path) -> Image.Image:
    ffmpeg.run(["-ss", f"{t:.3f}", "-i", video_path, "-frames:v", "1", out])
    with Image.open(out) as img:
        return img.convert("RGB")


def difference(a: Image.Image, b: Image.Image) -> float:
    return sum(ImageStat.Stat(ImageChops.difference(a, b)).mean) / 3


def video(ctx, vid):
    with ctx.connect() as conn:
        return db.get_video(conn, vid)


# --- voice ------------------------------------------------------------------------------------------

def test_words_from_character_timings():
    text = "Day 1. He runs."
    chars = list(text)
    alignment = {"characters": chars, "character_start_times_seconds": [i * 0.1 for i in range(len(chars))],
                 "character_end_times_seconds": [i * 0.1 + 0.1 for i in range(len(chars))]}
    assert words_from(alignment, text, 1500) == [
        {"word": "Day", "start_ms": 0, "end_ms": 300}, {"word": "1.", "start_ms": 400, "end_ms": 600},
        {"word": "He", "start_ms": 700, "end_ms": 900}, {"word": "runs.", "start_ms": 1000, "end_ms": 1500}]
    assert [w["start_ms"] for w in words_from(None, "a b c", 900)] == [0, 300, 600]  # no timings: evenly spaced


def test_voice_request_and_result(ctx, mp3, tmp_path):
    fake = FakeElevenLabs(mp3)
    tts = use_voice(ctx, fake)
    text = "Day 3. The water is rising, and he has one bottle left."
    result, usd = tts.speak(ctx.channel("zombie"), text, tmp_path / "s003.mp3", before="Line two.", after="Line four.")

    [req] = fake.requests
    assert req["path"] == "/v1/text-to-speech/voice123/with-timestamps" and req["key"] == "test-key"
    assert req["params"] == {"output_format": "mp3_44100_128"}
    assert req["body"] == {"text": text, "model_id": "eleven_multilingual_v2", "previous_text": "Line two.",
                           "next_text": "Line four."}
    assert (tmp_path / "s003.mp3").read_bytes() == mp3
    assert 1900 <= result["duration_ms"] <= 2200  # read from the MP3, not the timings
    assert [w["word"] for w in result["words"]] == text.split()
    assert usd == pytest.approx(len(text) * ctx.config.elevenlabs["price_per_char"])


def test_voice_retries_when_busy_and_stops_on_what_needs_you(ctx, mp3, tmp_path, monkeypatch):
    channel, out = ctx.channel("zombie"), tmp_path / "a.mp3"
    busy = (429, {"detail": {"status": "too_many_concurrent_requests", "message": "busy"}}, {"retry-after": "0"})
    fake = FakeElevenLabs(mp3, busy, (503, {"detail": "down"}, {}))
    use_voice(ctx, fake).speak(channel, "one two three", out)
    assert len(fake.requests) == 3

    fake = FakeElevenLabs(mp3, *[(500, {"detail": "down"}, {})] * 5)
    with pytest.raises(RuntimeError, match="ElevenLabs 500: down"):
        use_voice(ctx, fake).speak(channel, "one two three", out)
    assert len(fake.requests) == 5

    fake = FakeElevenLabs(mp3, (401, {"detail": {"status": "quota_exceeded", "message": "out of credits"}}, {}))
    with pytest.raises(FinalError, match="out of credits"):
        use_voice(ctx, fake).speak(channel, "one two three", out)
    fake = FakeElevenLabs(mp3, (404, {"detail": {"status": "voice_not_found", "message": "no such voice"}}, {}))
    with pytest.raises(FinalError, match="no such voice"):
        use_voice(ctx, fake).speak(channel, "one two three", out)
    assert len(fake.requests) == 1

    channel.voice_id = "elevenlabs_voice_xxx"
    with pytest.raises(FinalError, match="set voice_id in channels/zombie.yaml"):
        use_voice(ctx, fake).speak(channel, "one two three", out)
    channel.voice_id = "voice123"
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    with pytest.raises(FinalError, match="ELEVENLABS_API_KEY"):
        ElevenLabsTTS(ctx.config).speak(channel, "one two three", out)


# --- pictures -----------------------------------------------------------------------------------------

def test_still_sends_the_reference_and_comes_back_1080p(ctx, tmp_path):
    fake = FakeFal()
    images = use_fal(ctx, fake)
    channel = ctx.channel("zombie")
    usd = images.still(channel, "The stick figure bails water out of a flooded tunnel.", "Day 3", tmp_path / "a.png")
    images.still(channel, "The stick figure sleeps on a bench.", "Day 4", tmp_path / "b.png")

    assert usd == pytest.approx(0.044)
    assert fake.uploads == [channel.character_ref]  # uploaded once, reused
    call = fake.calls[0]
    assert call["model"] == "google/nano-banana-2.1/edit"
    assert call["image_urls"] == ["https://v3.fal.media/files/ref1.png"]
    assert call["aspect_ratio"] == "16:9" and call["resolution"] == "1K" and call["output_format"] == "png"
    assert "bails water out of a flooded tunnel" in call["prompt"] and channel.style_prompt in call["prompt"]
    assert "{" not in call["prompt"]
    with Image.open(tmp_path / "a.png") as img:
        assert img.size == (1920, 1080)

    os.utime(channel.character_ref, (1, 1))  # a new reference picture is uploaded again
    images.still(channel, "The stick figure at dawn.", "Day 5", tmp_path / "c.png")
    assert len(fake.uploads) == 2

    usd = images.thumbnail(channel, "Day 1 to Day 365 in a Flooded Subway", 1, tmp_path / "t.png")
    assert usd == pytest.approx(0.044) and '"Day 1 to Day 365 in a Flooded Subway"' in fake.calls[-1]["prompt"]
    assert "Draw version 2" in fake.calls[-1]["prompt"]
    with Image.open(tmp_path / "t.png") as img:
        assert img.size == (1280, 720)


def test_places_and_cast_are_drawn_once_then_sent_with_each_still(ctx, tmp_path):
    fake = FakeFal()
    images = use_fal(ctx, fake)
    channel = ctx.channel("zombie")
    images.place(channel, "the flat", "A small flat: a sofa on the left, a window at the back.", tmp_path / "flat.png")
    images.change_place(channel, tmp_path / "flat.png", "The window is boarded up.", tmp_path / "flat1.png")
    images.person(channel, "Rosa", "a stick-figure girl in a yellow raincoat", tmp_path / "rosa.png")
    images.still(channel, "Rosa and the stick figure by the boarded window.", "Day 3", tmp_path / "s.png",
                 place=("the flat", "A small flat.", tmp_path / "flat1.png"),
                 people=[("Rosa", "a stick-figure girl in a yellow raincoat", tmp_path / "rosa.png"),
                         ("Max", "a small brown dog", None)])

    place, change, person, still = fake.calls
    assert fake.uploads == [channel.character_ref, tmp_path / "flat.png", tmp_path / "flat1.png", tmp_path / "rosa.png"]
    assert "the flat" in place["prompt"] and "a sofa on the left" in place["prompt"] and "Nobody in it" in place["prompt"]
    assert place["image_urls"] == ["https://v3.fal.media/files/ref1.png"]  # the character, for the style
    assert change["image_urls"] == ["https://v3.fal.media/files/ref2.png"] and "The window is boarded up." in change["prompt"]
    assert person["aspect_ratio"] == "2:3" and "Rosa, a stick-figure girl in a yellow raincoat" in person["prompt"]
    with Image.open(tmp_path / "rosa.png") as img:
        assert img.size == (1024, 1536)
    assert still["image_urls"] == ["https://v3.fal.media/files/ref1.png", "https://v3.fal.media/files/ref3.png",
                                   "https://v3.fal.media/files/ref4.png"]
    assert ("Reference image 1 is the main character. Image 2 is the place: the flat. Image 3 is Rosa. Max, who has "
            "no reference image, is a small brown dog.") in still["prompt"]
    assert "keep its layout, furniture" in still["prompt"] and "{" not in still["prompt"]

    images.still(channel, "Close-up: his hands on the tape.", "Day 3", tmp_path / "c.png",
                 place=("the flat", "A small flat: a sofa on the left.", None))
    close = fake.calls[-1]  # a close-up gets the place in words, not its picture
    assert close["image_urls"] == ["https://v3.fal.media/files/ref1.png"]
    assert "The scene happens in the flat: A small flat: a sofa on the left." in close["prompt"]


def test_picture_errors(ctx, tmp_path, monkeypatch):
    channel, out = ctx.channel("zombie"), tmp_path / "x.png"
    with pytest.raises(FinalError, match="FAL_KEY and your fal balance"):
        use_fal(ctx, FakeFal(fal_error(401))).still(channel, "p", "l", out)
    with pytest.raises(FinalError, match="Change the scene's picture prompt"):
        use_fal(ctx, FakeFal(fal_error(422, "content_policy_violation"))).still(channel, "p", "l", out)
    with pytest.raises(RuntimeError, match="fal.ai 500"):
        use_fal(ctx, FakeFal(fal_error(500))).still(channel, "p", "l", out)

    empty = FakeFal()
    empty.subscribe = lambda *a, **k: {"images": [], "description": "blocked"}
    with pytest.raises(RuntimeError, match="no picture: blocked"):
        use_fal(ctx, empty).still(channel, "p", "l", out)

    (ctx.config.root / "prompts" / "still.md").write_text("Draw {scene}", encoding="utf-8")
    with pytest.raises(prompts.PromptError, match=r"\{scene\}"):
        use_fal(ctx, FakeFal()).still(channel, "p", "l", out)

    channel.character_ref = tmp_path / "missing.png"
    with pytest.raises(FinalError, match="character reference"):
        use_fal(ctx, FakeFal()).thumbnail(channel, "t", 0, out)
    monkeypatch.delenv("FAL_KEY", raising=False)
    channel.character_ref = ROOT / "channels" / "zombie" / "character.png"
    with pytest.raises(FinalError, match="FAL_KEY in .env"):
        FalImages(ctx.config).thumbnail(channel, "t", 0, out)


# --- the pipeline -----------------------------------------------------------------------------------------

def test_pipeline_with_real_voice_and_pictures(ctx, mp3):
    voice, pictures = FakeElevenLabs(mp3), FakeFal()
    use_voice(ctx, voice)
    use_fal(ctx, pictures)
    vid = actions.new_video(ctx, "zombie", "A week on a rooftop")
    Engine(ctx).run_until_idle()
    actions.approve(ctx, vid, "outline")
    Engine(ctx).run_until_idle()
    actions.approve(ctx, vid, "script")
    Engine(ctx).run_until_idle()

    v = video(ctx, vid)
    assert v["state"] == "assembled", v["error"]
    with ctx.connect() as conn:
        scenes = db.scenes_for(conn, vid)
        costs = conn.execute("SELECT provider, simulated, COUNT(*) AS n FROM costs WHERE video_id = ? "
                             "GROUP BY provider, simulated", (vid,)).fetchall()
    assert len(scenes) == 6 and all(s["audio_path"].endswith(".mp3") for s in scenes)
    assert all(1900 <= s["duration_ms"] <= 2200 for s in scenes)
    assert json.loads(scenes[0]["words_json"])[0]["word"] == scenes[0]["narration"].split()[0]
    by_text = {r["body"]["text"]: r["body"] for r in voice.requests}
    second = by_text[scenes[1]["narration"]]
    assert second["previous_text"] == scenes[0]["narration"] and second["next_text"] == scenes[2]["narration"]
    assert "previous_text" not in by_text[scenes[0]["narration"]]
    # 6 stills, 3 thumbnails, and the stub script's references: 2 places, the shelter once changed, and Rosa.
    # Each reference file is uploaded once (the character too), however many stills use it.
    assert len(pictures.calls) == 6 + 3 + 4 and len(pictures.uploads) == 1 + 4
    assert {(r["provider"], r["simulated"]): r["n"] for r in costs} == {
        ("tts", 0): 6, ("images", 0): 13, ("llm", 1): 3, ("video", 1): 1}
    assert abs(v["duration_ms"] - sum(s["duration_ms"] for s in scenes)) < 400

    thumbs = json.loads(v["thumbs_json"])  # the stub's thumbnail words, drawn on in the upper left
    assert thumbs["texts"] == ["365 DAYS ALONE", "THE WORST NIGHT", "HOW DID I LAST?"]
    with Image.open(ctx.abs(thumbs["thumbs"][0])) as img:
        corner = img.convert("RGB").crop((0, 0, 640, 300))
        assert next(n for n, color in corner.getcolors(1 << 20) if color == CAPTION_FILL) > 5000


# --- clips -----------------------------------------------------------------------------------------------

def test_clip_animates_the_scene_still(ctx, mp4, tmp_path):
    fake = FakeFal()
    video = use_clips(ctx, fake, mp4)
    channel, still = ctx.channel("zombie"), tmp_path / "still.png"
    StubImages().still(channel, "p", "Day 3", still)
    usd = video.clip(channel, still, "The stick figure bails water. He scoops faster as it rises.",
                     tmp_path / "c.mp4", video.seconds)

    assert video.seconds == 8 and usd == pytest.approx(8 * 0.112)  # Kling 3.0 Pro, silent
    assert fake.uploads == [still]  # the scene's own still is the first frame
    [call] = fake.calls
    assert call["model"] == "fal-ai/kling-video/v3/pro/image-to-video"
    assert call["start_image_url"] == "https://v3.fal.media/files/ref1.png"
    assert call["duration"] == "8" and call["generate_audio"] is False
    assert "He scoops faster as it rises." in call["prompt"] and channel.style_prompt in call["prompt"]
    assert "{" not in call["prompt"] and "No cuts" in call["prompt"]
    assert (tmp_path / "c.mp4").read_bytes() == mp4 and not (tmp_path / "c.part.mp4").exists()

    # another model is a config change: its own field names, lengths and price
    config = make_ctx(root=ctx.config.root, data_dir=tmp_path / "d2", overrides={
        "models": {"clip": "wan/v2.6/image-to-video"}, "fal": {"clips": {"seconds": 10}}}).config
    fake = FakeFal()
    wan = FalVideo(config, client=fake, http=image_host(mp4))
    assert wan.clip(channel, still, "p", tmp_path / "w.mp4", 10) == pytest.approx(1.5)
    call = fake.calls[0]
    assert call["image_url"] == "https://v3.fal.media/files/ref1.png" and "start_image_url" not in call
    assert call["duration"] == "10" and call["resolution"] == "1080p" and call["enable_prompt_expansion"] is False

    with pytest.raises(ValueError, match="makes clips of 5, 10, 15 seconds"):
        FalVideo(make_ctx(root=ctx.config.root, data_dir=tmp_path / "d3",
                          overrides={"models": {"clip": "wan/v2.6/image-to-video"}}).config)
    with pytest.raises(ValueError, match="fal.clips.models doesn't describe"):
        FalVideo(make_ctx(root=ctx.config.root, data_dir=tmp_path / "d4",
                          overrides={"models": {"clip": "fal-ai/someone-else"}}).config)


def test_clip_errors(ctx, mp4, tmp_path):
    channel, still, out = ctx.channel("zombie"), tmp_path / "still.png", tmp_path / "c.mp4"
    StubImages().still(channel, "p", "Day 3", still)
    with pytest.raises(FinalError, match="refused this clip"):
        use_clips(ctx, FakeFal(fal_error(422, "content_policy_violation")), mp4).clip(channel, still, "p", out, 8)
    with pytest.raises(FinalError, match="can't make a 20-second clip"):
        use_clips(ctx, FakeFal(), mp4).clip(channel, still, "p", out, 20)

    nothing = FakeFal()
    nothing.subscribe = lambda *a, **k: {"seed": 1}
    with pytest.raises(RuntimeError, match="no clip"):
        use_clips(ctx, nothing, mp4).clip(channel, still, "p", out, 8)
    with pytest.raises(RuntimeError, match="isn't a playable video"):
        use_clips(ctx, FakeFal(), b"<html>not a video</html>").clip(channel, still, "p", out, 8)
    assert not out.exists() and not out.with_suffix(".part.mp4").exists()


def test_budget_downgrades_clips_running_in_parallel(ctx, mp4):
    ctx.tts = StubTTS()
    use_fal(ctx, FakeFal())
    fake = FakeFal(wait=0.3)  # the three clips overlap, so each must see the others' money held
    clips = use_clips(ctx, fake, mp4)
    clips.price_per_s = 2.5   # $20 a clip: two fit under the $50 budget, three don't
    notices = []
    ctx.events.subscribe(lambda e: notices.append(e.data["text"]) if e.kind == "notice" else None)

    def three_clips(vid):  # scene rows are made from the script when it's approved
        with ctx.connect() as conn:
            script = json.loads(video(ctx, vid)["script_json"])
            for s in script[:3]:
                s["motion"] = "clip"
            db.update_video(conn, vid, script_json=json.dumps(script))

    vid = to_render_review(ctx, at_script=three_clips)
    v = video(ctx, vid)
    assert v["state"] == "assembled", v["error"]
    made = [s for s in scenes(ctx, vid).values() if s["clip_path"]]
    assert len(fake.calls) == len(made) == 2
    assert sum(1 for n in notices if "clip downgraded to Ken Burns" in n) == 1
    assert [s["motion"] for s in scenes(ctx, vid).values()].count("clip") == 2
    assert v["cost_usd"] < ctx.channel("zombie").budget_usd


def test_flagged_clip_scene_redoes_its_still_and_clip(ctx, mp4):
    pictures, clips = FakeFal(), FakeFal()
    ctx.tts = StubTTS()
    use_fal(ctx, pictures)
    use_clips(ctx, clips, mp4)
    vid = to_render_review(ctx)
    [hero] = [s for s in scenes(ctx, vid).values() if s["motion"] == "clip"]
    assert len(clips.calls) == 1 and clips.uploads[0].name == f"s{hero['idx']:03d}_r0.png"
    stills_before = len(pictures.calls)

    actions.flag_scenes(ctx, vid, [hero["idx"]], "visual", "make him run")
    Engine(ctx).run_until_idle()
    scene = scenes(ctx, vid)[hero["idx"]]
    assert video(ctx, vid)["state"] == "assembled"
    assert scene["regen_count"] == 1 and scene["still_path"].endswith("_r1.png")
    assert scene["clip_path"].endswith("_r1.mp4")
    assert len(pictures.calls) == stills_before + 1 and len(clips.calls) == 2
    assert clips.uploads[-1].name == f"s{hero['idx']:03d}_r1.png"  # the new clip starts from the new still
    assert "make him run" in clips.calls[-1]["prompt"]


def test_clip_plays_once_then_holds_its_last_frame(mp4, tmp_path):
    channel = make_ctx(data_dir=tmp_path / "data").channel("zombie")
    clip, still, audio = tmp_path / "c.mp4", tmp_path / "s.png", tmp_path / "a.wav"
    clip.write_bytes(mp4)
    StubImages().still(channel, "p", "Day 1", still)
    line = "The water keeps rising and he climbs onto the roof of the car to wait."
    result, _ = StubTTS().speak(channel, line, audio)
    assert result["duration_ms"] > 3500  # longer than the 2-second clip
    items = [{"idx": 1, "beat_idx": 0, "narration": line, "duration_ms": result["duration_ms"], "audio": str(audio),
              "still": str(still), "clip": str(clip), "words": result["words"]}]
    out = render_video(items, [{"label": "Day 1", "title": "Water"}], tmp_path / "render", engine="ffmpeg")["video"]

    end = result["duration_ms"] / 1000
    moving, held, still_held = (frame(out, t, tmp_path / f"f{t}.png") for t in (0.5, 2.4, end - 0.3))
    assert difference(held, still_held) < 1  # after the clip ends, its last frame stays (a loop would move on)
    assert difference(moving, held) > 10     # and it isn't the first second again


# --- live (real APIs, a few cents) -------------------------------------------------------------------------

@pytest.mark.live
@pytest.mark.skipif(not os.environ.get("ELEVENLABS_API_KEY"), reason="needs ELEVENLABS_API_KEY")
def test_live_voice(ctx, tmp_path):
    voice_id = os.environ.get("STICKFLEET_TEST_VOICE_ID") or make_ctx().channel("zombie").voice_id
    if voice_id.startswith("elevenlabs_voice_"):
        pytest.skip("set voice_id in channels/zombie.yaml (or STICKFLEET_TEST_VOICE_ID)")
    ctx.channel("zombie").voice_id = voice_id
    text = "Day 1. The power goes out at noon, and by sunset the street is completely quiet."
    result, usd = ElevenLabsTTS(ctx.config).speak(ctx.channel("zombie"), text, tmp_path / "live.mp3")
    assert result["duration_ms"] > 2000 and [w["word"] for w in result["words"]] == text.split()
    print(f"\nlive voice: {tmp_path / 'live.mp3'}, {result['duration_ms']} ms, ${usd:.4f}")


@pytest.mark.live
@pytest.mark.skipif(not os.environ.get("FAL_KEY"), reason="needs FAL_KEY")
def test_live_still(ctx, tmp_path):
    out = tmp_path / "live.png"
    FalImages(ctx.config).still(ctx.channel("zombie"), "The stick figure stands on a rooftop at dawn, looking "
                                "out over a silent city. Wide shot, calm.", "Day 1", out)
    with Image.open(out) as img:
        assert img.size == (1920, 1080)
    print(f"\nlive still: {out}")


@pytest.mark.live
@pytest.mark.skipif(not os.environ.get("FAL_KEY"), reason="needs FAL_KEY")
def test_live_clip(ctx, tmp_path):
    video = FalVideo(ctx.config)
    seconds = video.lengths[0]  # the shortest the model makes: 3 s of Kling 3.0 Pro is about $0.34
    still, out = tmp_path / "still.png", tmp_path / "live.mp4"
    StubImages().still(ctx.channel("zombie"), "The stick figure on a rooftop", "Day 1", still)
    usd = video.clip(ctx.channel("zombie"), still, "The stick figure waves slowly.", out, seconds)
    assert abs(ffmpeg.duration_ms(out) - seconds * 1000) < 1500
    print(f"\nlive clip: {out}, ${usd:.2f}")

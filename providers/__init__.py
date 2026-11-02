"""Provider factory. `providers:` in stickfleet.yaml picks one per kind; `mode: stub` makes them all stubs.

Stub providers cost $0 and need no keys. Real ones: llm `session` (the Claude Code session, providers/session.py;
there's no Claude API path), tts `elevenlabs`, images and video `fal`.
"""
from __future__ import annotations

from providers.images import StubImages
from providers.llm import StubLLM
from providers.tts import StubTTS
from providers.video import StubVideo

KINDS = ("llm", "tts", "images", "video")
REAL = {"llm": "session", "tts": "elevenlabs", "images": "fal", "video": "fal"}


def _stub_video(config) -> StubVideo:
    from providers.fal import clip_settings
    try:
        _, spec, seconds = clip_settings(config)
    except ValueError:  # a stub doesn't need the clip model to be set up
        return StubVideo()
    return StubVideo(float(spec["price_per_s"]), seconds)


def _make(config, kind: str):
    name = config.provider(kind)
    if name == "stub":
        return {"llm": lambda: StubLLM(int(config.stub.get("scenes", 12))), "tts": StubTTS,
                "images": StubImages, "video": lambda: _stub_video(config)}[kind]()
    if kind == "llm" and name == "session":
        from providers.session import SessionLLM
        return SessionLLM(config)
    if kind == "tts" and name == "elevenlabs":
        from providers.elevenlabs import ElevenLabsTTS
        return ElevenLabsTTS(config)
    if kind == "images" and name == "fal":
        from providers.fal import FalImages
        return FalImages(config)
    if kind == "video" and name == "fal":
        from providers.fal import FalVideo
        return FalVideo(config)
    real = REAL.get(kind)
    raise ValueError(f"providers.{kind}: {name!r} isn't available; use stub{f' or {real}' if real else ''}")


def make_providers(config) -> tuple:
    return tuple(_make(config, kind) for kind in KINDS)

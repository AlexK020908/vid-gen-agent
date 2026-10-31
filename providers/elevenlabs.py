"""ElevenLabs voice: one MP3 per scene with word timestamps (POST /v1/text-to-speech/{voice_id}/with-timestamps).

The lines before and after each scene go along as previous_text / next_text, so the voice keeps its flow
across 120 separate requests. The character timings ElevenLabs returns are grouped into the words that
captions and chapters use, and the scene's length is read from the MP3 itself. ElevenLabs caps parallel
requests by plan, so this provider keeps its own limit (elevenlabs.concurrency) under engine.parallel_calls.
"""
from __future__ import annotations

import base64
import os
import threading
import time
from pathlib import Path

import httpx2

from core.errors import FinalError
from render import ffmpeg

API = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/with-timestamps"
RETRIES = 4          # 429 (busy, or over the plan's parallel limit), 5xx and dropped connections, before giving up
TIMEOUT_S = 120


def _detail(response: httpx2.Response) -> str:
    try:
        detail = response.json().get("detail", response.text)
    except ValueError:
        return response.text[:300]
    if isinstance(detail, dict):
        return detail.get("message") or detail.get("status") or str(detail)
    return str(detail)[:300]


def words_from(alignment: dict | None, text: str, duration_ms: int) -> list[dict]:
    """Group per-character timings into words. Without timings, space the words evenly."""
    if not alignment or not alignment.get("characters"):
        words = text.split()
        step = duration_ms / max(1, len(words))
        return [{"word": w, "start_ms": round(i * step), "end_ms": round((i + 1) * step)} for i, w in enumerate(words)]
    out, word, start, end = [], "", 0.0, 0.0
    for ch, s, e in zip(alignment["characters"], alignment["character_start_times_seconds"],
                        alignment["character_end_times_seconds"]):
        if ch.isspace():
            if word:
                out.append({"word": word, "start_ms": round(start * 1000), "end_ms": round(end * 1000)})
                word = ""
            continue
        if not word:
            start = s
        word, end = word + ch, e
    if word:
        out.append({"word": word, "start_ms": round(start * 1000), "end_ms": round(end * 1000)})
    return out


class ElevenLabsTTS:
    ext = "mp3"

    def __init__(self, config, http: httpx2.Client | None = None) -> None:
        settings = config.elevenlabs
        self.model = config.models.get("voice") or "eleven_multilingual_v2"
        self.output_format = settings.get("output_format", "mp3_44100_128")
        self.price_per_char = float(settings.get("price_per_char", 0.00008))
        self.voice_settings = settings.get("voice_settings") or None
        self._slots = threading.BoundedSemaphore(int(settings.get("concurrency", 4)))
        self._http = http  # tests pass a client with a fake transport

    def price(self, text: str) -> float:
        return len(text) * self.price_per_char

    @property
    def http(self) -> httpx2.Client:
        if self._http is None:
            key = os.environ.get("ELEVENLABS_API_KEY")
            if not key:
                raise FinalError("ElevenLabs needs ELEVENLABS_API_KEY in .env (see .env.example). Add it, restart, "
                                 "then Retry")
            self._http = httpx2.Client(headers={"xi-api-key": key}, timeout=TIMEOUT_S)
        return self._http

    def speak(self, channel, text: str, out: Path, before: str | None = None,
              after: str | None = None) -> tuple[dict, float]:
        voice = (channel.voice_id or "").strip()
        if not voice or voice.startswith("elevenlabs_voice_"):
            raise FinalError(f"set voice_id in channels/{channel.id}.yaml to an ElevenLabs voice ID (in ElevenLabs: "
                             "Voices, open the voice, copy its ID), then Retry")
        body: dict = {"text": text, "model_id": self.model}
        if before:
            body["previous_text"] = before
        if after:
            body["next_text"] = after
        if self.voice_settings:
            body["voice_settings"] = self.voice_settings
        data = self._post(API.format(voice_id=voice), body)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(base64.b64decode(data["audio_base64"]))
        duration_ms = ffmpeg.duration_ms(out)
        words = words_from(data.get("alignment") or data.get("normalized_alignment"), text, duration_ms)
        return {"duration_ms": duration_ms, "words": words}, self.price(text)

    def _post(self, url: str, body: dict) -> dict:
        for attempt in range(RETRIES + 1):
            wait = 2 ** attempt
            with self._slots:
                try:
                    response = self.http.post(url, params={"output_format": self.output_format}, json=body)
                except httpx2.TransportError as e:
                    response, error = None, f"{type(e).__name__}: {e}"
            if response is not None:
                if response.status_code == 200:
                    return response.json()
                if response.status_code in (401, 403):
                    raise FinalError(f"ElevenLabs turned down the request ({_detail(response)}). Check "
                                     "ELEVENLABS_API_KEY and your plan's credits, then Retry")
                error = f"ElevenLabs {response.status_code}: {_detail(response)}"
                if response.status_code != 429 and response.status_code < 500:
                    raise FinalError(f"{error}. Check models.voice and the channel's voice_id, then Retry")
                wait = float(response.headers.get("retry-after") or wait)
            if attempt < RETRIES:
                time.sleep(wait)
        raise RuntimeError(error)

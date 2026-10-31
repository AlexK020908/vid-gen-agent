"""Speech: one audio file per scene plus word timestamps. The real one is providers/elevenlabs.py.

A TTS provider has `ext` (the audio file type), `price(text)` and `speak(channel, text, out, before, after)`,
which returns ({duration_ms, words: [{word, start_ms, end_ms}]}, usd). `before` and `after` are the
neighboring scenes' lines, for a voice that flows across scenes.
"""
from __future__ import annotations

import wave
from pathlib import Path


class StubTTS:
    """Silent WAV sized to the narration at 145 words per minute, with evenly spaced word timestamps."""

    price_per_char = 0.00008  # ElevenLabs list price, $0.08 per 1,000 characters, for simulated costs
    ext = "wav"

    def __init__(self, wpm: int = 145, rate: int = 8000) -> None:
        self.wpm = wpm
        self.rate = rate

    def price(self, text: str) -> float:
        return len(text) * self.price_per_char

    def speak(self, channel, text: str, out: Path, before: str | None = None,
              after: str | None = None) -> tuple[dict, float]:
        words = text.split()
        duration_ms = max(1500, round(len(words) / self.wpm * 60_000))
        out.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(out), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(self.rate)
            w.writeframes(b"\x00\x00" * (duration_ms * self.rate // 1000))
        step = duration_ms / max(1, len(words))
        timed = [{"word": word, "start_ms": round(i * step), "end_ms": round((i + 1) * step)}
                 for i, word in enumerate(words)]
        return {"duration_ms": duration_ms, "words": timed}, self.price(text)

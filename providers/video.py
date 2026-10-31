"""Hero clips (image-to-video). The real one is providers/fal.py (FalVideo)."""
from __future__ import annotations

from pathlib import Path

from render import ffmpeg


class StubVideo:
    """A slow pan across the scene's own still, so clip scenes look different in the render.

    Its price and length are the configured fal clip model's (fal.clips), for simulated costs.
    """

    def __init__(self, price_per_s: float = 0.112, seconds: int = 8) -> None:
        self.price_per_s, self.seconds = price_per_s, seconds

    def price(self, seconds: float) -> float:
        return seconds * self.price_per_s

    def clip(self, channel, still: Path, prompt: str, out: Path, seconds: float) -> float:
        out.parent.mkdir(parents=True, exist_ok=True)
        pan = f"scale=2112:1188,crop=1920:1080:(iw-1920)*t/{seconds}:(ih-1080)*t/{seconds},format=yuv420p"
        tmp = out.with_suffix(".part.mp4")
        ffmpeg.run(["-loop", "1", "-framerate", str(ffmpeg.FPS), "-i", still, "-t", str(seconds),
                    "-vf", pan, *ffmpeg.VIDEO_OUT, tmp])
        tmp.replace(out)
        return self.price(seconds)

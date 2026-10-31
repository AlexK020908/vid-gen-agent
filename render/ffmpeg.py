"""ffmpeg runner. Uses a system ffmpeg if present, else the copy bundled with imageio-ffmpeg."""
from __future__ import annotations

import functools
import re
import shutil
import subprocess

W, H, FPS = 1920, 1080, 30
FIT = f"scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,setsar=1,format=yuv420p"
VIDEO_OUT = ["-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-r", str(FPS),
             "-video_track_timescale", "15360"]
AUDIO_OUT = ["-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "128k"]


@functools.cache
def exe() -> str:
    found = shutil.which("ffmpeg")
    if found:
        return found
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def run(args: list) -> None:
    proc = subprocess.run([exe(), "-hide_banner", "-loglevel", "error", "-y", *map(str, args)],
                          capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {proc.stderr.strip()[-800:]}")


def probe(path) -> str:
    """ffmpeg's description of a media file (what `ffmpeg -i` prints), e.g. to read its Duration line."""
    return subprocess.run([exe(), "-hide_banner", "-i", str(path)], capture_output=True, text=True).stderr


def duration_ms(path) -> int:
    """Length of an audio or video file, from ffmpeg's Duration line."""
    m = re.search(r"Duration: (\d+):(\d+):(\d+(?:\.\d+)?)", probe(path))
    if not m:
        raise RuntimeError(f"can't read the length of {path}")
    hours, minutes, seconds = int(m.group(1)), int(m.group(2)), float(m.group(3))
    return round((hours * 3600 + minutes * 60 + seconds) * 1000)

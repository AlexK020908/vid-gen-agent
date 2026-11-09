"""Measures a rendered systems short against its timeline, from the MP4 itself, so a short whose code, dots and sound
don't line up never reaches the owner. make.render runs it on every render and refuses a short that fails.

The owner, Nov 9: "make it so that everything lines up, like if there is a sound, or if a request hits db or cache, the
relevant lines of code executes, not make an AI judge it after, this can be deterministic". The timeline makes the code's
lines and the sounds from the same events (sim._code, sim._drawn); this checks the render kept them together:
- the MP4's sound sits where the WAV put it (the encoder can shift it);
- every line-running tick has an onset in the MP4's own audio at its moment;
- every code line is lit on the frame its event happens (its request lands, or the cache answers), and no line lights
  up on a frame without one.
"""
from __future__ import annotations

import array
import math
import subprocess
import wave
from pathlib import Path

RATE = 44100
WINDOW = 220            # 5 ms
FPS = 30
MOST_OFFSET = 0.020     # seconds the MP4's sound may sit from the WAV's
LIT = 12                # grey levels a lit line stands above its darkest of the last frames
PROBE = 24              # px in from the code panel's right edge, where no code reaches


def _ffmpeg() -> str:
    from render import ffmpeg
    return ffmpeg.exe()


def _envelope(x: array.array) -> list[float]:
    """The energy of how fast the sound changes, every 5 ms: the soft pad and bass barely move it, a tick jumps it."""
    out = []
    for i in range(0, len(x) - WINDOW, WINDOW):
        s, prev = 0.0, x[i]
        for v in x[i + 1:i + WINDOW]:
            d = v - prev
            s += d * d
            prev = v
        out.append(s)
    return out


def _sound(mp4: Path, wav: Path, tl: dict) -> list[str]:
    raw = subprocess.run([_ffmpeg(), "-v", "error", "-i", str(mp4), "-ac", "1", "-ar", str(RATE), "-f", "s16le", "-"],
                         capture_output=True, check=True).stdout
    got = array.array("h")
    got.frombytes(raw)
    with wave.open(str(wav)) as w:
        made = array.array("h")
        made.frombytes(w.readframes(w.getnframes()))
    ea, eb = _envelope(got), _envelope(made)
    n = min(len(ea), len(eb))
    lag = max(range(-40, 41), key=lambda k: sum(ea[i + k] * eb[i] for i in range(50, n - 50)))
    out = []
    if abs(lag * WINDOW / RATE) > MOST_OFFSET:
        out.append(f"the MP4's sound is {lag * WINDOW / RATE * 1000:+.0f} ms off the timeline")
    ticks = sorted({round(c[0], 4) for c in tl["cues"] if c[1] in ("code", "drop") and c[0] < tl["duration"] - 0.05})
    missing = []
    for t in ticks:
        k = int(round(t * RATE / WINDOW))
        before = sum(ea[max(0, k - 6):k - 1]) / 5
        if not max(ea[k:k + 3], default=0) > 1.5 * before:
            missing.append(t)
    if missing:
        out.append(f"{len(missing)} of {len(ticks)} code ticks aren't heard at their moment, the first at "
                   f"{missing[0]:.3f} s")
    return out


def _picture(mp4: Path, tl: dict) -> list[str]:
    code = tl.get("code")
    blocks = [b for b in (code or {}).get("blocks", []) if b["lines"]]
    if not blocks:
        return []
    g = tl["geometry"]
    most = max(len(b["lines"]) for b in blocks)
    x, top, h = int(g["right"]) - PROBE, int(g["code_top"]), int(g["code_pad"] + most * g["code_line"])
    raw = subprocess.run([_ffmpeg(), "-v", "error", "-i", str(mp4), "-vf", f"format=gray,crop=2:{h}:{x}:{top}",
                          "-f", "rawvideo", "-"], capture_output=True, check=True).stdout
    frames = [raw[i:i + 2 * h:2] for i in range(0, len(raw), 2 * h)]
    row = lambda line: int(g["code_pad"] + (line - 1) * g["code_line"] + g["code_line"] / 2)  # noqa: E731
    stop = (tl.get("end") or {}).get("from", tl["duration"])
    events = [(math.ceil(a * FPS - 1e-6), line) for b in blocks for line, a, _, _ in b["hl"] if a < stop]
    dark = [(n, line) for n, line in events if n < len(frames)
            and frames[n][row(line)] < min(frames[m][row(line)] for m in range(max(0, n - 40), n + 1)) + LIT]
    out = []
    if dark:
        n, line = dark[0]
        out.append(f"{len(dark)} of {len(events)} code lines aren't lit on the frame they run, the first line {line} "
                   f"at {n / FPS:.3f} s")
    starts = set(events)
    stray = [(n, line) for n in range(1, min(len(frames), int(stop * FPS))) for line in range(1, most + 1)
             if frames[n][row(line)] - frames[n - 1][row(line)] > LIT and (n, line) not in starts]
    if stray:
        n, line = stray[0]
        out.append(f"code lines light up {len(stray)} times with nothing running them, the first line {line} at "
                   f"{n / FPS:.3f} s")
    return out


def problems(mp4: Path, wav: Path, tl: dict) -> list[str]:
    """What's out of step in a rendered short, measured from the MP4; empty when its sound, its dots and its code line
    up."""
    mp4, wav = Path(mp4), Path(wav)
    return _sound(mp4, wav, tl) + _picture(mp4, tl)

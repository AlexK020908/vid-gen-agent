"""A systems short's whole soundtrack as one WAV, made by code from the timeline's cues: no samples to license.

- with code on screen, a soft tick each time a request runs a line, pitched by the line (A minor pentatonic, rising
  down the code), made from the same events that light the line, so every sound is a line running;
- without code, a soft tick when a request lands, pitched by the node it lands on (a request's trips are whole
  sixteenth notes, so the ticks fall on the beat), and a lower one when an answer gets back;
- a dull thunk when a request is lost, a buzz when a node fails, a soft whoosh when nodes appear, a chime on the end
  card;
- a music bed the whole way: a pad of four chords, one a bar, over a plucked bass on the eighth notes and a soft kick
  on the beat. The short is a whole number of bars (sim.py), so the bed loops with the picture.
"""
from __future__ import annotations

import array
import math
import wave
from pathlib import Path

from render import sfx

RATE = 44100
PEAK = 0.89
# A minor pentatonic, from the first node a request lands on up
TICKS = (880.0, 1046.5, 1174.7, 1318.5, 1568.0, 1760.0)
CHORDS = ((220.0, 261.63, 329.63), (174.61, 220.0, 261.63), (261.63, 329.63, 392.0), (196.0, 246.94, 293.66))
ROOTS = (110.0, 87.31, 130.81, 98.0)
GAINS = {"tick": 0.30, "code": 0.28, "return": 0.16, "drop": 0.42, "fail": 0.40, "appear": 0.20, "chime": 0.42}
MUSIC = 0.20


def _blip(freq: float, length: float = 0.09, decay: float = 0.028) -> list[float]:
    n = int(length * RATE)
    return [(math.sin(2 * math.pi * freq * i / RATE) + 0.25 * math.sin(4 * math.pi * freq * i / RATE))
            * min(1.0, i / (0.002 * RATE)) * math.exp(-i / (decay * RATE)) for i in range(n)]


def _thunk() -> list[float]:
    n = int(0.16 * RATE)
    out, ph = [], 0.0
    for i in range(n):
        f = 190 - 100 * i / n
        ph += 2 * math.pi * f / RATE
        out.append(math.sin(ph) * math.exp(-i / (0.045 * RATE)))
    return out


def _chime(base: float = 1046.5) -> list[float]:
    n = int(1.6 * RATE)
    parts = ((1.0, 1.0, 0.9), (2.0, 0.45, 0.6), (2.76, 0.3, 0.4), (5.4, 0.12, 0.2))
    return [sum(a * math.sin(2 * math.pi * base * r * i / RATE) * math.exp(-i / (d * RATE)) for r, a, d in parts)
            * min(1.0, i / (0.003 * RATE)) / 1.9 for i in range(n)]


def _norm(x: list[float]) -> list[float]:
    peak = max(1e-9, max(abs(v) for v in x))
    return [v / peak for v in x]


def bed(seconds: float, beat: float) -> list[float]:
    """The music: whole bars of a pad, a plucked bass on the eighth notes and a soft kick on the beat."""
    n = int(round(seconds * RATE))
    beat_n = 60.0 / beat * RATE
    bar_n = 4 * beat_n
    out = [0.0] * n
    two_pi = 2 * math.pi
    # the pad: each chord's notes, two slightly apart, with a breath of the octave; chords crossfade at the bar line
    fade = int(0.05 * RATE)
    for i in range(n):
        bar = int(i // bar_n)
        into = i - bar * bar_n
        chord = CHORDS[bar % 4]
        v = 0.0
        for f in chord:
            v += math.sin(two_pi * f * i / RATE) + math.sin(two_pi * f * 1.004 * i / RATE)
        if into < fade and i > fade:
            w = into / fade
            prev = CHORDS[(bar - 1) % 4]
            u = 0.0
            for f in prev:
                u += math.sin(two_pi * f * i / RATE) + math.sin(two_pi * f * 1.004 * i / RATE)
            v = w * v + (1 - w) * u
        swell = 0.85 + 0.15 * math.sin(two_pi * into / bar_n)
        out[i] = v * 0.055 * swell
    # the bass: the chord's root plucked on every eighth note
    eighth = beat_n / 2
    pluck_len = int(eighth * 0.9)
    k = 0
    while k * eighth < n:
        start = int(k * eighth)
        root = ROOTS[int(start // bar_n) % 4]
        for j in range(min(pluck_len, n - start)):
            env = math.exp(-j / (0.09 * RATE)) * min(1.0, j / (0.004 * RATE))
            out[start + j] += 0.16 * env * (math.sin(two_pi * root * j / RATE) + 0.3 * math.sin(two_pi * 2 * root * j / RATE))
        k += 1
    # the kick: a soft low thump on each beat
    k = 0
    kick_len = int(0.18 * RATE)
    while k * beat_n < n:
        start = int(k * beat_n)
        ph = 0.0
        for j in range(min(kick_len, n - start)):
            ph += two_pi * (95 - 50 * j / kick_len) / RATE
            out[start + j] += 0.22 * math.sin(ph) * math.exp(-j / (0.06 * RATE))
        k += 1
    edge = int(0.012 * RATE)   # no click where the loop joins
    for j in range(min(edge, n)):
        out[j] *= j / edge
        out[n - 1 - j] *= j / edge
    return out


def mix(timeline: dict, out: Path, music: bool = True) -> Path:
    """The soundtrack for a timeline (sim.timeline), written to `out` as 16-bit mono WAV."""
    seconds = float(timeline["duration"])
    n = int(round(seconds * RATE))
    buf = [v * MUSIC for v in _norm(bed(seconds, float(timeline["beat"])))] if music else [0.0] * n
    pitch = {node: TICKS[i % len(TICKS)] for i, node in enumerate(timeline.get("pitch") or [])}
    sounds: dict[str, list[float]] = {}

    def sound(kind: str, node) -> list[float]:
        key = f"{kind}:{node}"
        if key not in sounds:
            if kind == "tick":
                sounds[key] = _norm(_blip(pitch.get(node, TICKS[0])))
            elif kind == "code":
                sounds[key] = _norm(_blip(TICKS[(int(node) - 1) % len(TICKS)]))
            elif kind == "return":
                sounds[key] = _norm(_blip(440.0, 0.12, 0.04))
            elif kind == "drop":
                sounds[key] = _norm(_thunk())
            elif kind == "fail":
                sounds[key] = _norm(sfx.error())
            elif kind == "appear":
                sounds[key] = _norm(sfx.whoosh(0.5, 300, 1500, 19))
            else:
                sounds[key] = _norm(_chime())
        return sounds[key]

    together: dict[float, int] = {}         # ticks sounding at once share their loudness
    for t, kind, _ in timeline.get("cues") or []:
        if kind in ("tick", "code"):
            together[round(float(t), 4)] = together.get(round(float(t), 4), 0) + 1
    for t, kind, node in timeline.get("cues") or []:
        if kind not in GAINS:
            continue
        s = sound(kind, node)
        g = GAINS[kind] / (math.sqrt(together.get(round(float(t), 4), 1)) if kind in ("tick", "code") else 1)
        start = int(round(float(t) * RATE))
        for j, v in enumerate(s[: max(0, n - start)]):
            buf[start + j] += g * v
    peak = max(1e-9, max(abs(v) for v in buf))
    scale = PEAK / peak if peak > PEAK else 1.0
    data = array.array("h", (int(max(-1.0, min(1.0, v * scale)) * 32767) for v in buf))
    out.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(data.tobytes())
    return out

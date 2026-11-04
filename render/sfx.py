"""Sound effects for the machine shorts, made by code: no samples to license, the same every time.

Each kind is a few lines of maths (decaying partials for metal, filtered noise for air and fire), written once to
data/sfx/<kind>.wav (44.1 kHz mono) and reused. `make(kind)` returns the path. The timelines' and storyboard's
event names map onto these kinds in ALIASES.
"""
from __future__ import annotations

import array
import math
import random
import wave
from pathlib import Path

RATE = 44100


def _noise(n, seed):
    rng = random.Random(seed)
    return [rng.uniform(-1, 1) for _ in range(n)]


def _lowpass(x, cutoff):
    """One-pole lowpass at `cutoff` Hz (a list or a function of the sample index for a sweep)."""
    out, y = [], 0.0
    for i, v in enumerate(x):
        c = cutoff(i) if callable(cutoff) else cutoff
        a = 1 - math.exp(-2 * math.pi * c / RATE)
        y += a * (v - y)
        out.append(y)
    return out


def _highpass(x, cutoff):
    low = _lowpass(x, cutoff)
    return [a - b for a, b in zip(x, low)]


def _env(n, attack, decay):
    """A rise over `attack` seconds then an exponential fall with time constant `decay`."""
    a = max(1, int(attack * RATE))
    return [i / a if i < a else math.exp(-(i - a) / (decay * RATE)) for i in range(n)]


def _partials(n, freqs, decay, seed=1):
    rng = random.Random(seed)
    phases = [rng.uniform(0, 6.28) for _ in freqs]
    return [sum(math.sin(2 * math.pi * f * i / RATE + p) * math.exp(-i / (decay * RATE * (1 + k * 0.15)))
                for k, (f, p) in enumerate(zip(freqs, phases))) / len(freqs) for i in range(n)]


def _seconds(s):
    return int(s * RATE)


def tap():
    n = _seconds(0.35)
    ping = _partials(n, [2400, 3610, 5210, 7020], 0.05, seed=2)
    click = [v * e for v, e in zip(_highpass(_noise(n, 3), 3000), _env(n, 0.001, 0.006))]
    return [0.55 * a + 0.5 * b for a, b in zip(ping, click)]


def tap_heavy():
    n = _seconds(0.5)
    ping = _partials(n, [1800, 2750, 4100], 0.08, seed=4)
    thump = [math.sin(2 * math.pi * 140 * i / RATE) * math.exp(-i / (0.05 * RATE)) for i in range(n)]
    return [0.6 * a + 0.5 * b for a, b in zip(ping, thump)]


def impact_heavy():
    n = _seconds(1.6)
    clang = _partials(n, [220, 341, 517, 803, 1210, 1650], 0.45, seed=5)
    sub = [math.sin(2 * math.pi * (55 + 30 * math.exp(-i / (0.03 * RATE))) * i / RATE) * math.exp(-i / (0.25 * RATE))
           for i in range(n)]
    crack = [v * e for v, e in zip(_lowpass(_noise(n, 6), 2500), _env(n, 0.001, 0.04))]
    return [0.5 * a + 0.7 * b + 0.6 * c for a, b, c in zip(clang, sub, crack)]


def thud():
    n = _seconds(0.5)
    sub = [math.sin(2 * math.pi * (70 + 40 * math.exp(-i / (0.02 * RATE))) * i / RATE) * math.exp(-i / (0.09 * RATE))
           for i in range(n)]
    dirt = [v * e for v, e in zip(_lowpass(_noise(n, 7), 600), _env(n, 0.002, 0.06))]
    return [0.9 * a + 0.5 * b for a, b in zip(sub, dirt)]


def clank():
    n = _seconds(0.6)
    metal = _partials(n, [620, 940, 1480, 2210], 0.12, seed=8)
    knock = [v * e for v, e in zip(_lowpass(_noise(n, 9), 1800), _env(n, 0.001, 0.02))]
    return [0.7 * a + 0.6 * b for a, b in zip(metal, knock)]


def whoosh(length=0.6, low=300, high=2600, seed=10):
    n = _seconds(length)
    mid = n / 2
    shaped = _lowpass(_noise(n, seed), lambda i: low + (high - low) * math.exp(-((i - mid) / (0.25 * n)) ** 2))
    return [v * math.sin(math.pi * i / n) ** 2 * 2.2 for i, v in enumerate(shaped)]


def riser():
    n = _seconds(1.4)
    air = _lowpass(_noise(n, 11), lambda i: 300 + 4000 * (i / n) ** 2)
    tone = [math.sin(2 * math.pi * (180 + 500 * (i / n) ** 2) * i / RATE) for i in range(n)]
    return [(0.9 * a + 0.25 * b) * (i / n) ** 1.5 * (1 - max(0, (i - 0.9 * n) / (0.1 * n))) for i, (a, b)
            in enumerate(zip(air, tone))]


def explosion(length=1.8, seed=12):
    n = _seconds(length)
    roar = _lowpass(_noise(n, seed), lambda i: 200 + 2800 * math.exp(-i / (0.12 * RATE)))
    sub = [math.sin(2 * math.pi * (45 + 60 * math.exp(-i / (0.04 * RATE))) * i / RATE) for i in range(n)]
    env = _env(n, 0.004, 0.35)
    return [(1.6 * a + 0.8 * b) * e for a, b, e in zip(roar, sub, env)]


def hiss(length=0.7, seed=13):
    n = _seconds(length)
    air = _highpass(_noise(n, seed), 2500)
    return [v * math.sin(math.pi * i / n) * 0.9 for i, v in enumerate(air)]


def crackle(length=0.5, seed=14):
    n = _seconds(length)
    rng = random.Random(seed)
    out = [0.0] * n
    for _ in range(40):
        at = rng.randrange(n - 400)
        for k in range(300):
            out[at + k] += rng.uniform(-1, 1) * math.exp(-k / 40)
    return _highpass(out, 1500)


def hum(length=1.5, base=70, seed=15):
    n = _seconds(length)
    buzz = [math.sin(2 * math.pi * base * i / RATE) + 0.5 * math.sin(2 * math.pi * base * 2.01 * i / RATE)
            for i in range(n)]
    fade = [min(1, i / (0.1 * RATE), (n - i) / (0.2 * RATE)) for i in range(n)]
    grit = _lowpass(_noise(n, seed), 400)
    return [(0.4 * a + 0.3 * g) * f for a, g, f in zip(buzz, grit, fade)]


def click():
    n = _seconds(0.12)
    return [v * e for v, e in zip(_highpass(_noise(n, 16), 2000), _env(n, 0.0005, 0.004))]


def error():
    n = _seconds(0.55)
    tone = [math.copysign(1, math.sin(2 * math.pi * (180 if i < n / 2 else 140) * i / RATE)) * 0.3 for i in range(n)]
    return [v * min(1, (n - i) / (0.05 * RATE)) for i, v in enumerate(_lowpass(tone, 1500))]


def pop():
    n = _seconds(0.15)
    return [math.sin(2 * math.pi * (600 - 2000 * i / n) * i / RATE) * math.exp(-i / (0.03 * RATE)) for i in range(n)]


def scrape(length=1.2, seed=17):
    n = _seconds(length)
    grain = _lowpass(_noise(n, seed), 900)
    return [v * (0.6 + 0.4 * math.sin(2 * math.pi * 7 * i / RATE)) * math.sin(math.pi * i / n) * 1.4
            for i, v in enumerate(grain)]


KINDS = {
    "tap": tap, "tap_heavy": tap_heavy, "impact_heavy": impact_heavy, "thud": thud, "clank": clank,
    "whoosh": whoosh, "whoosh_low": lambda: whoosh(0.9, 150, 1200, 18), "whoosh_soft": lambda: whoosh(0.5, 300, 1500, 19),
    "whoosh_slow": lambda: whoosh(1.4, 200, 1400, 20), "riser": riser, "explosion": explosion,
    "explosion_muffled": lambda: [v * 0.8 for v in _lowpass(explosion(1.6, 21), 900)], "hiss": hiss,
    "crackle": crackle, "hum": hum, "click": click, "error": error, "pop": pop, "scrape": scrape,
}
ALIASES = {
    "reverse_whoosh": "whoosh_low", "rattle": "crackle", "winch": "hum", "shing": "tap", "clunk": "clank",
    "clunk_heavy": "impact_heavy", "slide": "scrape", "extend": "scrape", "spray": "hiss", "spark": "crackle",
    "flip": "click", "drone": "hum", "ignition": "explosion_muffled", "roar": "explosion_muffled",
    "exhaust": "hiss", "boom": "explosion", "impact": "impact_heavy", "impact_boom": "impact_heavy",
    "engine_loop": "hum",
}


def kind_of(event: str) -> str | None:
    kind = ALIASES.get(event, event)
    return kind if kind in KINDS else None


def make(kind: str, folder: Path) -> Path:
    folder = Path(folder)
    out = folder / f"{kind}.wav"
    if out.exists():
        return out
    folder.mkdir(parents=True, exist_ok=True)
    samples = KINDS[kind]()
    peak = max(1e-6, max(abs(v) for v in samples))
    data = array.array("h", (int(max(-1, min(1, v / peak * 0.9)) * 32767) for v in samples))
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(data.tobytes())
    return out

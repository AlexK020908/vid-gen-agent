"""A short's narration, line by line in an ElevenLabs voice.

Two ways to time it:
- `read()` voices each line at the voice's own pace and leaves the timing to the picture, which follows the voice
  (render/retime.py moves a timeline written to other times onto it). This is the default: the owner found lines
  squeezed into someone else's timing rushed, with no room between a problem and its answer.
- `fit()` fits each line to a slot it must fill, with ffmpeg's atempo (the pitch stays the voice's). A line longer
  than its slot is sped up, one much shorter slowed a little. A line too long even at the fastest spills into the
  pause after it: the next line starts just after and is sped up to catch up, so the read never drifts far from its
  marks.

Each line's voice file and word times are kept by a hash of its voice, speed and text, so running again never pays
twice. ElevenLabs' previous and next text are passed, so lines flow as one read and a question sounds like one.
"""
from __future__ import annotations

import array
import hashlib
import json
import math
import wave
from dataclasses import replace
from pathlib import Path

from providers.elevenlabs import ElevenLabsTTS
from render import ffmpeg

FASTEST, SLOWEST = 1.45, 0.88   # the most fit() speeds a line up or slows it, as atempo factors
GAP = 0.04                      # the least breath between one line's end and the next one's start
CAPTION_MAX = 64                # characters a caption holds, on the box's two lines
QUIET = 0.012                   # a 10 ms window quieter than this (of full scale) is silence
LEAD, TAIL = 0.03, 0.06         # the room kept before a line's first sound and after its last
SCRAP_GAP = 0.15                # silence that cuts a scrap of sound off from a line's words: longer than a stop inside a word (about 0.07 s)
SCRAP_MOST = 0.2                # the longest a scrap at either end can be
MOST_TEMPO = 1.15               # the most read() speeds a slow voice up to reach its pace: the ear doesn't mind this
DUCK = 0.6                      # how much of its volume a sound effect keeps when it lands on a spoken line
PITCH_LOW, PITCH_HIGH = 70, 300  # the range a speaking voice's pitch is looked for in, Hz
VOICED = 0.45                   # how strongly a stretch has to repeat to count as voiced
LIFT_FRAMES = 5                 # how many voiced moments count as a line's end, 40 ms each


def _atempo(factor: float) -> str:
    """ffmpeg's atempo takes 0.5 to 2 per filter: chain them for anything beyond."""
    parts = []
    while factor > 2.0:
        parts.append(2.0)
        factor /= 2.0
    while factor < 0.5:
        parts.append(0.5)
        factor /= 0.5
    parts.append(factor)
    return ",".join(f"atempo={p:.4f}" for p in parts)


def _voiced(config, channel, voice_id: str, lines: list[dict], out_dir: Path, speed: float, tts, model=None):
    """Each line voiced (or found from an earlier run): yields (i, key, decoded wav, seconds, words, dollars).
    Words are [{word, start, end}] in seconds from the line's start. `model` is models.voice unless given."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    tts = tts or ElevenLabsTTS(replace(config, elevenlabs={**config.elevenlabs, "speed": speed},
                                       models={**config.models, **({"voice": model} if model else {})}))
    voice = replace(channel, voice_id=voice_id)
    for i, line in enumerate(lines):
        key = hashlib.sha256(json.dumps([voice_id, speed, line["text"], *([model] if model else [])]).encode())
        key = key.hexdigest()[:16]
        raw = out_dir / f"raw_{key}.mp3"
        timing = out_dir / f"words_{key}.json"
        usd = 0.0
        if not raw.exists():
            result, usd = tts.speak(voice, line["text"], raw, before=lines[i - 1]["text"] if i else None,
                                    after=lines[i + 1]["text"] if i + 1 < len(lines) else None)
            timing.write_text(json.dumps(result.get("words") or []), encoding="utf-8")
        decoded = raw.with_suffix(".wav")   # an MP3's stated length counts its encoder padding: measure the samples
        if not decoded.exists():
            ffmpeg.run(["-i", raw, "-ar", 44100, "-ac", 1, decoded])
        words = [{"word": w["word"], "start": w["start_ms"] / 1000, "end": w["end_ms"] / 1000}
                 for w in (json.loads(timing.read_text(encoding="utf-8")) if timing.exists() else [])]
        yield i, key, decoded, ffmpeg.duration_ms(decoded) / 1000, words, usd


def _ends(path: Path, starts: list[float] | None = None) -> tuple[float, float]:
    """Where a line's speech starts and stops, in seconds, with a little room at each end. `starts` are its words' start
    times in seconds, if known.

    A short scrap of sound cut off from the words by silence at either end isn't the line: ElevenLabs is shown the lines
    either side, and a take can end on the first sound of the next one (the woodpecker's "...a sponge. s-" before "So
    what", which the owner heard as "s--- so"), or be a breath. It's dropped unless a word starts in it."""
    with wave.open(str(path)) as w:
        rate, n = w.getframerate(), w.getnframes()
        samples = array.array("h", w.readframes(n))
    size = int(rate * 0.01)
    loud = [i for i in range(0, n - size, size)
            if math.sqrt(sum(s * s for s in samples[i:i + size]) / size) / 32768 > QUIET]
    if not loud:
        return 0.0, n / rate
    runs = [[loud[0], loud[0] + size]]   # stretches of sound, in samples, split where SCRAP_GAP of silence falls
    for i in loud[1:]:
        if (i - runs[-1][1]) / rate >= SCRAP_GAP:
            runs.append([i, i + size])
        else:
            runs[-1][1] = i + size
    starts = starts or []
    short = lambda run: (run[1] - run[0]) / rate <= SCRAP_MOST
    while len(runs) > 1 and short(runs[-1]) and not any(t >= (runs[-2][1] + runs[-1][0]) / 2 / rate for t in starts):
        runs.pop()
    while len(runs) > 1 and short(runs[0]) and starts and min(starts) >= (runs[0][1] + runs[1][0]) / 2 / rate:
        runs.pop(0)
    return max(0.0, runs[0][0] / rate - LEAD), min(n / rate, runs[-1][1] / rate + TAIL)


def trimmed(path: Path, result: dict) -> tuple[Path, dict]:
    """A voiced line cut to its speech, as a wav, with its words moved to match: a voice leaves silence at both ends, and the
    pauses between lines are the layout's to set. `result` is what tts.speak returned."""
    path = Path(path)
    decoded = path.with_name(f"{path.stem}.full.wav")
    ffmpeg.run(["-i", path, "-ar", 44100, "-ac", 1, decoded])
    a, b = _ends(decoded, [w["start_ms"] / 1000 for w in result.get("words") or []])
    final = path.with_name(f"{path.stem}.speech.wav")
    ffmpeg.run(["-i", decoded, "-af", f"atrim=start={a:.3f}:end={b:.3f},asetpts=PTS-STARTPTS", "-ar", 44100, "-ac", 1, final])
    decoded.unlink(missing_ok=True)
    length = ffmpeg.duration_ms(final)
    shift = round(a * 1000)
    words = [{**w, "start_ms": max(0, min(length, w["start_ms"] - shift)), "end_ms": max(0, min(length, w["end_ms"] - shift))}
             for w in result.get("words") or []]
    return final, {"duration_ms": length, "words": words}


def _pitch(samples: list[float], rate: int) -> float | None:
    """A stretch of voice's pitch in Hz, by autocorrelation, or None if it's silent or not voiced."""
    if not samples or math.sqrt(sum(s * s for s in samples) / len(samples)) < QUIET:
        return None
    low, high = int(rate / PITCH_HIGH), int(rate / PITCH_LOW)
    energy = sum(s * s for s in samples)
    best, at = 0.0, None
    for lag in range(low, min(high, len(samples) - 1), 2):
        score = sum(a * b for a, b in zip(samples, samples[lag:])) / energy
        if score > best:
            best, at = score, lag
    return rate / at if at and best > VOICED else None


def question_lift(path: Path) -> float | None:
    """How far a line's voice rises at its end: the pitch of its last few voiced moments over the median of the rest. Above
    about 1.05 it sounds like a question. None if too little of it is voiced to say. A question read flat was the owner's
    complaint about the first cloned read; on eleven_v4 it varies from take to take, so a flat one is simply taken again."""
    with wave.open(str(path)) as w:
        rate, n = w.getframerate(), w.getnframes()
        data = array.array("h", w.readframes(n))
    step, size = int(rate * 0.04), int(rate * 0.04)
    pitches = [p for i in range(0, n - size, step) if (p := _pitch([s / 32768 for s in data[i:i + size:2]], rate // 2))]
    if len(pitches) < 8:
        return None
    tail = sorted(pitches[-LIFT_FRAMES:])[LIFT_FRAMES // 2]
    rest = sorted(pitches[:-LIFT_FRAMES])
    return tail / rest[len(rest) // 2]


def read(config, channel, voice_id: str, lines: list[dict], out_dir: Path, speed: float = 1.0, tts=None,
         model: str | None = None, pace: float | None = None) -> tuple[list[dict], float]:
    """`lines`: [{text}]. Returns ([{src, duration, words, text}], dollars spent). Each line is trimmed to its speech:
    a voice can leave silence at both ends, and the pauses between lines are the layout's to set. `pace`, in characters
    a second, brings a slow voice up to it with one gentle tempo over the whole read (at most MOST_TEMPO; never
    slower than voiced). `model` is models.voice unless given. `tts` is ElevenLabs unless a test passes its own
    (anything with speak(channel, text, out, before, after))."""
    voiced, spent = [], 0.0
    for i, key, decoded, _seconds, words, usd in _voiced(config, channel, voice_id, lines, out_dir, speed, tts, model):
        spent += usd
        voiced.append((lines[i]["text"], key, decoded, _ends(decoded, [w["start"] for w in words]), words))
    speech = sum(b - a for _text, _key, _decoded, (a, b), _words in voiced)
    chars = sum(len(text) for text, *_rest in voiced)
    tempo = min(MOST_TEMPO, max(1.0, pace * speech / chars)) if pace else 1.0
    out = []
    for text, key, decoded, (a, b), words in voiced:
        final = Path(out_dir) / f"read_{key}_{tempo:.3f}_{a:.2f}_{b:.2f}.wav"   # named by its cut too, so a better trim is used
        if not final.exists():
            ffmpeg.run(["-i", decoded, "-af", f"atrim=start={a:.3f}:end={b:.3f},asetpts=PTS-STARTPTS,atempo={tempo:.4f}",
                        "-ar", 44100, "-ac", 1, final])
        moved = [{"word": w["word"], "start": max(0.0, (w["start"] - a) / tempo), "end": max(0.0, (w["end"] - a) / tempo)}
                 for w in words]
        out.append({"src": str(final), "duration": ffmpeg.duration_ms(final) / 1000, "words": moved, "text": text})
    return out, spent


def duck(sounds: list[dict], read_lines: list[dict], starts: list[float], voice: str = "voice.wav") -> list[dict]:
    """A short's sounds with any effect that lands on a spoken line played quieter, so it never covers the words."""
    spoken = [(start, start + line["duration"]) for line, start in zip(read_lines, starts)]
    return [{**s, "volume": round(s.get("volume", 1) * DUCK, 3)} if s["src"] != voice and any(a <= s["from"] <= b for a, b in spoken)
            else s for s in sounds]


def track(read_lines: list[dict], starts: list[float], out: Path) -> Path:
    """A read as one file, each line at its start, leveled as a whole, so the narration sits at one steady loudness
    (-16 LUFS, peaks under -1.5 dB) under whatever else a short plays."""
    inputs, delays = [], []
    for i, (line, start) in enumerate(zip(read_lines, starts)):
        inputs += ["-i", line["src"]]
        delays.append(f"[{i}:a]adelay={round(start * 1000)}[a{i}]")
    joined = "".join(f"[a{i}]" for i in range(len(read_lines)))
    graph = ";".join(delays) + f";{joined}amix=inputs={len(read_lines)}:normalize=0,loudnorm=I=-16:TP=-1.5[out]"
    ffmpeg.run([*inputs, "-filter_complex", graph, "-map", "[out]", "-ar", 44100, out])
    return out


def _phrases(words: list[str]) -> list[list[str]]:
    """A sentence as captions: one if it fits, else split where a comma falls nearest its middle (or, with no comma,
    at the word nearest it), and those split again if they must be."""
    text = " ".join(words)
    if len(text) <= CAPTION_MAX or len(words) < 2:
        return [words]
    ends, at = [], 0
    for i, word in enumerate(words[:-1], 1):
        at += len(word) + 1
        ends.append((not word.endswith((",", ".", ";", ":", "?", "!")), abs(at - len(text) / 2), i))
    _no_comma, _off_middle, i = min(ends)
    return _phrases(words[:i]) + _phrases(words[i:])


def captions(read: list[dict], starts: list[float]) -> list[dict]:
    """A read's captions, [{text, from, to}] in seconds, each from its first word as the voice says it until the next
    caption, so the box stays up through a pause. `read` is read()'s lines and `starts` where each one starts."""
    out = []
    for line, start in zip(read, starts):
        words = line["text"].split()
        times = line["words"] if len(line["words"]) == len(words) else [
            {"start": line["duration"] * i / len(words)} for i in range(len(words))]
        at = 0
        for phrase in _phrases(words):
            out.append({"text": " ".join(phrase), "from": round(start + times[at]["start"], 3)})
            at += len(phrase)
    for caption, after in zip(out, out[1:]):
        caption["to"] = round(after["from"] - 0.07, 3)
    if out:
        out[-1]["to"] = round(starts[-1] + read[-1]["duration"] + 0.5, 3)
    return out


def fit(config, channel, voice_id: str, lines: list[dict], out_dir: Path, speed: float = 1.0,
        tts=None) -> tuple[list[dict], float]:
    """`lines`: [{text, start, end}] in seconds. Returns ([{src, from, duration, factor}], dollars spent)."""
    spent, out = 0.0, []
    clock = 0.0   # when the line before ends: a line that spilled over pushes the next one, which then catches up
    for i, key, decoded, have, _words, usd in _voiced(config, channel, voice_id, lines, out_dir, speed, tts):
        spent += usd
        line = lines[i]
        start = max(line["start"], clock + GAP)
        slot = max(0.3, line["end"] - start)
        factor = have / slot
        factor = min(FASTEST, factor) if factor > 1.0 else max(SLOWEST, factor) if factor < 0.85 else 1.0
        fitted = Path(out_dir) / f"line_{i:02d}_{key}_{factor:.3f}.wav"
        if not fitted.exists():
            ffmpeg.run(["-i", decoded, "-af", _atempo(factor), "-ar", 44100, "-ac", 1, fitted])
        clock = start + have / factor
        out.append({"src": str(fitted), "from": round(start, 3), "duration": have / factor, "factor": round(factor, 3),
                    "text": line["text"]})
    return out, spent

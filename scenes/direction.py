"""A whole short as the agent directs it (prompts/character/direct.md): scenes laid end to end in the short's own time, the
voice coming first. A scene in the language (scenes/spec.py) counts from its own start, so code turns each one into that
before it's checked or rendered. The length and captions are never written: they come from the voice.
"""
from __future__ import annotations

import math

from scenes import spec as scene_spec

MEET = 0.05      # how far apart two scenes can be and still count as one starting where the last ended (s)
CAPTION_WORDS = 4
PAUSE_MS, LONG_PAUSE_MS, LAST_PAUSE_MS = 500, 900, 1200   # the owner: "breathing room between every senetence"


def pauses(scenes: list[dict]) -> list[int]:
    """The silence after each line, in ms: room after every one, and more after a question or where the story moves on, so
    the "But" that follows has somewhere to land."""
    out = []
    for s, after in zip(scenes, [*scenes[1:], None]):
        if after is None:
            out.append(LAST_PAUSE_MS)
        elif s["narration"].rstrip().endswith("?") or after["beat_idx"] != s["beat_idx"]:
            out.append(LONG_PAUSE_MS)
        else:
            out.append(PAUSE_MS)
    return out


def lines(scenes: list[dict], pauses: list[int]) -> dict:
    """Each narrated line on the short's clock, with each word's time, and the short's end. `scenes` have narration,
    duration_ms and words (timed from the line's start); `pauses` is the silence after each, in ms."""
    out, at = [], 0
    for s, pause in zip(scenes, pauses):
        words = [{"word": w["word"], "t": round((at + w["start_ms"]) / 1000, 2), "to": round((at + w["end_ms"]) / 1000, 2)}
                 for w in s.get("words") or []]
        out.append({"idx": s["idx"], "text": s["narration"], "shows": s.get("shows", ""), "from": round(at / 1000, 2),
                    "to": round((at + s["duration_ms"]) / 1000, 2), "words": words})
        at += s["duration_ms"] + pause
    return {"lines": out, "total": round(at / 1000, 2)}


def lines_text(timeline: dict) -> str:
    """The narration as the director reads it."""
    rows = []
    for line in timeline["lines"]:
        said = " ".join(f"{w['word']}@{w['t']}" for w in line["words"]) or line["text"]
        rows.append(f"{line['idx']}. {line['from']} to {line['to']} s. Shows: {line['shows'] or '(the director decides)'}\n   {said}")
    return "\n".join(rows)


def _shift(value, by: float):
    return round(value - by, 3) if isinstance(value, (int, float)) and not isinstance(value, bool) else value


def local(scene: dict) -> dict:
    """A directed scene in its own time, with its length, as the scene language has it."""
    begin = float(scene["from"])
    out = {k: v for k, v in scene.items() if k not in ("from", "to", "captions")}
    out["length"] = round(float(scene["to"]) - begin, 3)
    out["happens"] = [{**e, **({"t": _shift(e["t"], begin)} if "t" in e else {}),
                       **({"to": _shift(e["to"], begin)} if isinstance(e.get("to"), (int, float)) else {})}
                      for e in scene.get("happens") or []]
    out["shots"] = [{**s, "t": _shift(s.get("t"), begin)} for s in scene.get("shots") or []]
    return out


def _times(scene: dict) -> bool:
    return all(isinstance(scene.get(k), (int, float)) and math.isfinite(scene[k]) for k in ("from", "to"))


def mark_problems(marks, total: float) -> list[str]:
    """What's drawn over the picture: a big number counting up, on the short's clock.
    {"kind": "count", "from": s, "to": s, "start": n, "end": n, "text": what it counts, "tone": a color, "at": [x, y] as shares of the picture}"""
    out = []
    for i, m in enumerate(marks or []):
        label = f"mark {i + 1}"
        if not isinstance(m, dict) or m.get("kind") != "count":
            out.append(f"{label}: kind is count")
            continue
        if not (_is_number(m.get("from")) and _is_number(m.get("to")) and 0 <= m["from"] < m["to"] <= total + MEET):
            out.append(f"{label}: from and to are seconds of the short, in order")
        if not (_is_number(m.get("start")) and _is_number(m.get("end"))):
            out.append(f"{label}: start and end are the numbers it counts between")
        if not str(m.get("text") or "").strip():
            out.append(f"{label}: text says what it counts")
    return out


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def tags(marks) -> list[dict]:
    """A direction's marks as what the short's renderer draws."""
    return [{"tone": "red", "at": [0.5, 0.36], **m} for m in marks or []]


def check(direction: dict, total: float, people: list[str], stances: list[str], things: dict) -> list[str]:
    """Everything wrong with a direction, in words: the scenes have to cover the short exactly, and each has to pass the
    scene language's own check. `people` are the ids it may cast."""
    scenes = direction.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        return ["scenes: there has to be at least one"]
    out, at = mark_problems(direction.get("marks"), total), 0.0
    for i, scene in enumerate(scenes):
        label = f"scene {i + 1}"
        if not isinstance(scene, dict) or not _times(scene):
            out.append(f"{label}: needs from and to, in seconds of the short")
            continue
        if abs(scene["from"] - at) > MEET:
            out.append(f"{label}: starts at {scene['from']}, and the last ended at {round(at, 2)}: they have to meet")
        if scene["to"] <= scene["from"]:
            out.append(f"{label}: to has to come after from")
            continue
        at = scene["to"]
        out += [f"{label}: don't write {key}: code works it out" for key in ("length", "captions") if key in scene]
        out += [f"{label}: {p}" for p in scene_spec.check(local(scene), people, stances, things)]
    if abs(at - total) > MEET:
        out.append(f"the last scene ends at {round(at, 2)}, and the short ends at {total}")
    return out


def captions(timeline: dict) -> list[dict]:
    """The big captions, from the voice: a few words at a time, breaking after punctuation, each up until the next starts.
    In seconds of the short."""
    out = []
    for line in timeline["lines"]:
        group: list[dict] = []
        for i, word in enumerate(line["words"]):
            group.append(word)
            ends = word["word"].rstrip()[-1:] in ".,?!;:"
            if ends or len(group) == CAPTION_WORDS or i == len(line["words"]) - 1:
                out.append({"text": " ".join(w["word"] for w in group), "from": group[0]["t"], "to": word["to"]})
                group = []
    for a, b in zip(out, out[1:]):
        a["to"] = min(b["from"], a["to"] + 0.25)     # a moment to read it, but never over the next
    return out

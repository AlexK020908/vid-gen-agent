"""A whole short as the agent directs it (prompts/character/direct.md): scenes laid end to end in the short's own time, the
voice coming first. A scene in the language (scenes/spec.py) counts from its own start, so code turns each one into that
before it's checked or rendered. The length and captions are never written: they come from the voice.
"""
from __future__ import annotations

import math

from scenes import spec as scene_spec

MEET = 0.05      # how far apart two scenes can be and still count as one starting where the last ended (s)
CAPTION_WORDS = 4
MOST_IDLE = 4.5      # how long a person can be in a scene with nothing to do: time for a reaction, and no more (s)
PERSON_ACTS = ("hold", "bite", "wear", "strike", "knock", "move", "act", "walk")     # an expression, a look or a glow alone is standing there
MOST_STILL = 2.5     # how long a shot can hold with neither the camera nor anything in it moving (s)
MOVING = ("rock", "slide", "spin", "strike", "fly", "go", "walk", "act", "knock", "squash", "play", "move", "rings", "sparks")
MOST_REPEATS = 2     # how many times the same picture can come up in a short
PAUSE_MS, LONG_PAUSE_MS, LAST_PAUSE_MS = 500, 900, 1200   # the owner: "breathing room between every senetence"


def pauses(scenes: list[dict], gaps: tuple | list | None = None) -> list[int]:
    """The silence after each line, in ms: room after every one, and more after a question or where the story moves on, so
    the "But" that follows has somewhere to land. `gaps` is a channel's own (line, long, last), in place of the usual three."""
    line, long, last = gaps or (PAUSE_MS, LONG_PAUSE_MS, LAST_PAUSE_MS)
    out = []
    for s, after in zip(scenes, [*scenes[1:], None]):
        if after is None:
            out.append(last)
        elif s["narration"].rstrip().endswith("?") or after["beat_idx"] != s["beat_idx"]:
            out.append(long)
        else:
            out.append(line)
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


def _idle_people(scene: dict) -> list[str]:
    """Who just stands there. A person is in a shot to do something, or to react for a moment."""
    out = []
    length = float(scene["to"]) - float(scene["from"])
    if length <= MOST_IDLE:
        return out
    for pid, entry in (scene.get("cast") or {}).items():
        if entry.get("type") != "person":
            continue
        acts = any(e.get("who") == pid and e.get("do") in PERSON_ACTS for e in scene.get("happens") or [])
        seen = any(not shot.get("shows") or pid in shot["shows"] for shot in scene.get("shots") or [])
        if seen and not acts:
            out.append(f"{pid} just stands there for {round(length, 1)} s. A person is only in a shot to do something or to react for a moment: "
                       f"give them something to do, or leave them out of this scene")
    return out


def _still_shots(scene: dict) -> list[str]:
    """A shot held with nothing moving in it. The camera can stay still while something happens, and something can stay still while the
    camera travels. Both still at once is a photograph."""
    out = []
    shots = [s for s in scene.get("shots") or [] if isinstance(s, dict) and isinstance(s.get("t"), (int, float))]
    ends = [s["t"] for s in shots[1:]] + [scene["to"]]
    for shot, end in zip(shots, ends):
        if end - shot["t"] <= MOST_STILL or "to" in shot:
            continue
        moving = False
        for e in scene.get("happens") or []:
            if e.get("do") not in MOVING or not isinstance(e.get("t"), (int, float)):
                continue
            until = e["t"] + (e["over"] if isinstance(e.get("over"), (int, float)) else 1.0)
            if e["t"] < end and until > shot["t"]:
                moving = True
                break
        if not moving:
            out.append(f"the shot at {shot['t']} s holds for {round(end - shot['t'], 1)} s with nothing moving. Have the camera travel with `to`, or have something happen")
    return out


def _picture(scene: dict, shot: dict) -> tuple:
    """What a shot shows, near enough: two shots with the same of these look like the same picture to a viewer."""
    frame = float(shot.get("frame") or 1.0)
    angle = shot.get("angle") or [0, 0]
    return (scene.get("set"), shot.get("on"), round(math.log(max(frame, 0.01), 1.3)), round(float(angle[0]) / 20), round(float(angle[1]) / 20))


def _same_pictures(scenes: list) -> list[str]:
    """The same picture coming back again and again. A cut has to show something new."""
    seen: dict[tuple, list[float]] = {}
    for scene in scenes:
        if not isinstance(scene, dict):
            continue
        for shot in scene.get("shots") or []:
            if isinstance(shot, dict) and "on" in shot:
                seen.setdefault(_picture(scene, shot), []).append(shot.get("t", 0))
    return [f"the same picture of {key[1]} comes up {len(times)} times, at {', '.join(str(t) for t in times)} s: at most {MOST_REPEATS}. Show something new instead"
            for key, times in seen.items() if len(times) > MOST_REPEATS]


def check(direction: dict, total: float, people: list[str], stances: list[str], things: dict, moves: list[str] | None = None) -> list[str]:
    """Everything wrong with a direction, in words: the scenes have to cover the short exactly, and each has to pass the
    scene language's own check. `people` are the ids it may cast, `stances` what they can hold, `moves` what they can do."""
    scenes = direction.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        return ["scenes: there has to be at least one"]
    out, at = mark_problems(direction.get("marks"), total) + _same_pictures(scenes), 0.0
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
        out += [f"{label}: {p}" for p in _idle_people(scene)]
        out += [f"{label}: {p}" for p in _still_shots(scene)]
        out += [f"{label}: {p}" for p in scene_spec.check(local(scene), people, stances, things, moves)]
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

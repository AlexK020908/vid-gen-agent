"""A whole short as the agent directs it (prompts/character/direct.md): scenes laid end to end in the short's own time, the
voice coming first. A scene in the language (scenes/spec.py) counts from its own start, so code turns each one into that
before it's checked or rendered. The length and captions are never written: they come from the voice.
"""
from __future__ import annotations

import math

from core import phrasing
from scenes import spec as scene_spec

MEET = 0.05      # how far apart two scenes can be and still count as one starting where the last ended (s)
CAPTION_WORDS = 5      # most words a big caption holds; four or fewer unless a phrase needs the fifth (core/phrasing.py)
MOST_IDLE = 4.5      # how long a person can be in a scene with nothing to do: time for a reaction, and no more (s)
PERSON_ACTS = ("hold", "bite", "wear", "strike", "knock", "move", "act", "walk")     # an expression, a look or a glow alone is standing there
MOST_STILL = 2.5     # how long a shot can hold with neither the camera nor anything in it moving (s)
MOVING = ("rock", "slide", "spin", "strike", "fly", "go", "walk", "act", "knock", "squash", "play", "move", "rings", "sparks", "fill", "pour", "air")
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
    out = {k: v for k, v in scene.items() if k not in ("from", "to", "captions", "anew")}
    out["length"] = round(float(scene["to"]) - begin, 3)
    out["happens"] = [{**e, **({"t": _shift(e["t"], begin)} if "t" in e else {}),
                       **({"to": _shift(e["to"], begin)} if isinstance(e.get("to"), (int, float)) else {}),
                       **({"leave": [{**g, "t": _shift(g["t"], begin)} if isinstance(g, dict) and "t" in g else g for g in e["leave"]]} if isinstance(e.get("leave"), list) else {})}
                      for e in scene.get("happens") or []]
    out["shots"] = [{**s, "t": _shift(s.get("t"), begin)} for s in scene.get("shots") or []]
    return out


def _times(scene: dict) -> bool:
    return all(isinstance(scene.get(k), (int, float)) and math.isfinite(scene[k]) for k in ("from", "to"))


MARK_KINDS = ("count", "label", "fail", "ok", "warn", "question", "title")
LABEL_WORDS = 3          # a label names a thing: a word or two
MARK_AT = {"count": [0.5, 0.36], "fail": [0.5, 0.3], "ok": [0.5, 0.3], "warn": [0.5, 0.3], "question": [0.5, 0.3], "title": [0.5, 0.17],
           "stamp": [0.5, 0.11]}     # a stamp (a date, a few words in a box) is only used by films written straight in Blender, so far
TITLE_LINE = 12          # letters a title's line holds, big, across the picture: a longer one breaks between words
MARK_TONES = ("yellow", "white", "blue", "red", "green")      # render/remotion/src/shorts/types.ts TONES
LABEL_SIZE, TAG_SIZE = 54, 74    # px on the 1080-wide picture: reference A's are 32 and 38, too small to read beside these shorts' big captions


def mark_problems(marks, total: float, scenes: list | None = None) -> list[str]:
    """What's drawn over the picture, on the short's clock (prompts/character/direct.md):
    {"kind": "count", "from": s, "to": s, "start": n, "end": n, "text": what it counts, "tone": a color, "at": [x, y] as shares of the picture}
    {"kind": "label", "on": an aim in the scene playing then, "text": its name, "from": s, "to": s, "side": "left" or "right"}: a dot on it and its name, following it
    {"kind": "fail", "text": what went wrong, "from": s, "to": s, "at": [x, y], "icon": "x" or "clock"}: a red cross and its words
    {"kind": "warn", "text": what it warns of, "from": s, "to": s, "at": [x, y]}: a yellow warning sign and its words
    {"kind": "ok", "text": what worked, "from": s, "to": s, "at": [x, y]}: a green tick and its words
    {"kind": "title", "text": a name, "from": s, "to": s}: big across the top of the picture, the name of what's been built as it's said
    {"kind": "question", "from": s, "to": s, "at": [x, y]}: a big question mark"""
    out = []
    for i, m in enumerate(marks or []):
        label = f"mark {i + 1}"
        if not isinstance(m, dict) or m.get("kind") not in MARK_KINDS:
            out.append(f"{label}: kind is one of {', '.join(MARK_KINDS)}")
            continue
        if not (_is_number(m.get("from")) and _is_number(m.get("to")) and 0 <= m["from"] < m["to"] <= total + MEET):
            out.append(f"{label}: from and to are seconds of the short, in order")
            continue
        kind, text = m["kind"], str(m.get("text") or "").strip()
        if "tone" in m and m["tone"] not in MARK_TONES:
            out.append(f"{label}: tone is one of {', '.join(MARK_TONES)}")
        if kind != "question" and not text:
            out.append(f"{label}: text says what it {'counts' if kind == 'count' else 'is' if kind == 'label' else 'warns of' if kind == 'warn' else 'says worked' if kind == 'ok' else 'says went wrong'}")
        if kind == "count" and not (_is_number(m.get("start")) and _is_number(m.get("end"))):
            out.append(f"{label}: start and end are the numbers it counts between")
        if kind == "fail" and m.get("icon", "x") not in ("x", "clock"):
            out.append(f"{label}: icon is x or clock")
        if kind == "label":
            out += _label_problems(m, label, text, scenes)
    return out


def _label_problems(m: dict, label: str, text: str, scenes: list | None) -> list[str]:
    """A label names one thing in one scene: it follows that thing on screen, so it can't outlast the scene it's in."""
    out = []
    if len(text.split()) > LABEL_WORDS:
        out.append(f"{label}: a label names a thing in a word or two, not {len(text.split())}")
    if m.get("side", "right") not in ("left", "right"):
        out.append(f"{label}: side is left or right")
    on = m.get("on")
    if not (isinstance(on, str) and on.partition(":")[0]):
        out.append(f"{label}: on is what it names, as a shot's on is: \"tank:surface\"")
        return out
    if scenes is None:
        return out
    home = _scene_of(scenes, m)
    if home is None:
        out.append(f"{label}: {m['from']} to {m['to']} s isn't inside one scene: a label follows a thing in one scene, so split it at the cut")
    elif on.partition(":")[0] not in (scenes[home].get("cast") or {}):
        out.append(f"{label}: {on.partition(':')[0]!r} isn't in the scene playing then (scene {home + 1})")
    return out


def _scene_of(scenes: list, m: dict) -> int | None:
    """The scene a mark's time lies inside, if it lies inside one."""
    for i, s in enumerate(scenes):
        if isinstance(s, dict) and _times(s) and s["from"] - MEET <= m["from"] and m["to"] <= s["to"] + MEET:
            return i
    return None


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def tags(marks) -> list[dict]:
    """A direction's marks as what the short's renderer draws over the picture, its labels aside."""
    return [{"tone": "red", "at": MARK_AT[m["kind"]], **({"size": TAG_SIZE} if m.get("kind") in ("fail", "ok", "warn") else {}), **m,
             **({"text": _title_lines(str(m.get("text") or ""))} if m.get("kind") == "title" else {})}
            for m in marks or [] if m.get("kind") != "label"]


def _title_lines(text: str) -> str:
    """A title's words in lines short enough to stay in the picture at its size: "SUBMERSIBLE\\nPUMP"."""
    lines: list[str] = []
    for word in text.upper().split():
        if lines and len(lines[-1]) + 1 + len(word) <= TITLE_LINE:
            lines[-1] += " " + word
        else:
            lines.append(word)
    return "\n".join(lines)


def anchors_for(marks, scene: dict) -> list[str]:
    """The aims a scene tracks on screen, for the labels drawn on it."""
    return sorted({m["on"] for m in marks or [] if m.get("kind") == "label" and _scene_of([scene], m) == 0})


def labels(marks, scenes: list) -> list[dict]:
    """A direction's labels as the renderer draws them: each on its scene's track of the thing it names, "scene:aim"."""
    out = []
    for m in marks or []:
        if m.get("kind") == "label":
            home = _scene_of(scenes, m)
            out.append({"label": str(m["text"]).upper(), "anchor": f"{home}:{m['on']}", "tone": m.get("tone", "yellow"),
                        "from": m["from"], "to": m["to"], "side": m.get("side", "right"), "size": LABEL_SIZE})
    return out


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
            if isinstance(e.get("to"), (int, float)) and e.get("do") in ("pour", "air", "spin", "play"):     # what goes on until it's stopped
                until = e["to"]
            elif e.get("do") in ("air", "spin", "play") and "to" not in e:
                until = scene["to"]
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


PLACED_BY = ("at", "on", "onto", "to", "by", "against", "inside", "near", "height", "facing", "points", "up", "size")     # what puts a thing where it is
LEVEL_NEAR = 0.005       # meters two levels can differ and read as the same
PLACE_NEAR = 0.01        # meters, or degrees, two placings can differ and read as the same
GOES_ELSEWHERE = ("go", "fly", "walk")      # what leaves a thing or a person somewhere else than the scene put them


def _same(a, b) -> bool:
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) <= PLACE_NEAR
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(_same(x, y) for x, y in zip(a, b))
    return a == b


def _where(scene: dict) -> tuple:
    place = scene.get("place") or {}
    return (scene.get("set"), place.get("sky"), place.get("ground"), place.get("turn"))


def _moved_off(scene: dict, cid: str) -> bool:
    """Whether something in the scene leaves it somewhere else than its cast entry puts it."""
    net, known = [0.0, 0.0, 0.0], True
    moved = False
    for e in scene.get("happens") or []:
        if e.get("prop") != cid and e.get("who") != cid:
            continue
        if e.get("do") in GOES_ELSEWHERE or (e.get("do") == "slide" and "until" in e):
            moved, known = True, False                       # how far it went isn't written down
        elif e.get("do") == "slide" and "from" not in e:
            by = e.get("by")
            moved = True
            if isinstance(by, (list, tuple)) and len(by) == 3 and all(_is_number(v) for v in by):
                net = [a + b for a, b in zip(net, by)]
            else:
                known = False
    if moved and known and all(abs(v) <= PLACE_NEAR for v in net):
        return False                                         # it slid away and slid back, in the picture: a garment lifted and dropped back where it lay
    return moved


def _set_down(scene: dict, cid: str) -> bool:
    """Whether the scene brings it to where it rests, in the picture: a slide from somewhere else."""
    return any(e.get("do") == "slide" and e.get("prop") == cid and "from" in e for e in scene.get("happens") or [])


def _levels(scene: dict, cid: str, entry: dict) -> tuple[dict, dict]:
    """A thing's liquid levels as the scene starts and as it ends, by part: (above, level), None for full."""
    start = {entry.get("part"): (entry.get("above"), entry.get("level"))}
    end = dict(start)
    fills = [e for e in scene.get("happens") or [] if e.get("do") == "fill" and e.get("prop") == cid and _is_number(e.get("t"))]
    for e in sorted(fills, key=lambda e: e["t"]):
        above = end.get(e.get("part"), start[entry.get("part")])[0]
        end[e.get("part")] = (above, e.get("level"))
    return start, end


def _carry_problems(scenes: list) -> list[str]:
    """What doesn't carry from one scene to the next time the same thing's seen. A scene is staged afresh, so nothing in the stage keeps a
    liquid's level or a thing's place from the scene before: this does. A level that ends at one height and starts the next scene at another, or a
    thing that's somewhere else with nothing having moved it, is a jump the viewer sees. `anew`: [cast ids] on a scene says which start afresh
    on purpose: the picture has said time has passed, or it's the same moment shown again, as a slow-motion replay is."""
    again = "If the picture says time has passed, or it's the same moment shown again, list {} in this scene's `anew`"
    out, last = [], {}        # id -> (scene number, scene, its cast entry, the levels it ended at)
    for i, scene in enumerate(scenes):
        if not isinstance(scene, dict) or not _times(scene) or not isinstance(scene.get("cast"), dict):
            continue
        label = f"scene {i + 1}"
        anew = set(scene.get("anew") or [])
        for cid, entry in scene["cast"].items():
            if not isinstance(entry, dict):
                continue
            start, end = _levels(scene, cid, entry)
            seen = last.get(cid)
            last[cid] = (i + 1, scene, entry, end)
            if not seen or cid in anew:
                continue
            n, before, was, ended = seen
            if (was.get("prop"), was.get("character")) != (entry.get("prop"), entry.get("character")):
                continue                                         # the same name on another thing
            for part, (above, level) in start.items():
                if part not in ended or ended[part][0] != above or "level" not in entry and ended[part][1] is None:
                    continue
                old = ended[part][1]
                if (old is None) != (level is None) or (_is_number(old) and _is_number(level) and abs(old - level) > LEVEL_NEAR):
                    said = lambda v: "full" if v is None else f"at {v}"
                    out.append(f"{label}: {cid}'s liquid starts {said(level)}, but scene {n} left it {said(old)}. A scene is staged afresh, so carry "
                               f"the level over: start it {said(old)}, or show it getting there with a `fill` in scene {n}. "
                               + again.format(cid))
            if _where(before) != _where(scene):
                continue                                         # another place: where it stands there says nothing about here
            moved = [k for k in PLACED_BY if not _same(was.get(k), entry.get(k))]
            if moved and not _moved_off(before, cid) and not _set_down(scene, cid):
                out.append(f"{label}: {cid} is somewhere else than scene {n} left it ({', '.join(moved)} changed), and nothing moved it. Keep it "
                           f"where it was, move it there in scene {n}, or set it down in the picture with a `slide` from where it was. "
                           + again.format(cid))
            elif not moved and _moved_off(before, cid):
                out.append(f"{label}: {cid} is back where scene {n} started it, but it moved away in that scene. Start it where it ended up, "
                           f"or show it coming back. " + again.format(cid))
    return out


def check(direction: dict, total: float, people: list[str], stances: list[str], things: dict, moves: list[str] | None = None) -> list[str]:
    """Everything wrong with a direction, in words: the scenes have to cover the short exactly, and each has to pass the
    scene language's own check. `people` are the ids it may cast, `stances` what they can hold, `moves` what they can do."""
    scenes = direction.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        return ["scenes: there has to be at least one"]
    out, at = mark_problems(direction.get("marks"), total, scenes) + _same_pictures(scenes) + _carry_problems(scenes), 0.0
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
        tracked = {**local(scene), "anchors": anchors_for(direction.get("marks"), scene)}     # what its labels name has to be there to name
        out += [f"{label}: {p}" for p in scene_spec.check(tracked, people, stances, things, moves)]
    if abs(at - total) > MEET:
        out.append(f"the last scene ends at {round(at, 2)}, and the short ends at {total}")
    return out


def captions(timeline: dict) -> list[dict]:
    """The big captions, from the voice: a few words at a time, breaking after punctuation and between phrases, never
    inside one (core/phrasing.py), each up until the next starts. In seconds of the short."""
    out = []
    for line in timeline["lines"]:
        clause: list[dict] = []
        for i, word in enumerate(line["words"]):
            clause.append(word)
            if phrasing.ends(word["word"]) or i == len(line["words"]) - 1:
                at = 0
                for piece in phrasing.split([w["word"] for w in clause], CAPTION_WORDS):
                    group = clause[at:at + len(piece)]
                    out.append({"text": " ".join(w["word"] for w in group), "from": group[0]["t"], "to": group[-1]["to"]})
                    at += len(piece)
                clause = []
    for a, b in zip(out, out[1:]):
        a["to"] = min(b["from"], a["to"] + 0.25)     # a moment to read it, but never over the next
    return out

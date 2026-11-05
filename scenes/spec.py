"""The scene language: what the agent writes to direct a short, checked in code before Blender starts (CHARACTERS.md).

The style it's built for holds strong poses and does the rest with cuts every second or so, wide lenses close up, a
slow-motion hit and glows. People barely act; things are placed and struck. Code works out the contacts and physics, so a
scene says what happens, not where every hand goes. Times are seconds from the scene's start. Meters and degrees.

Everything is held to physical truth by code. When a scene's staged, its meshes are measured against each other frame by frame:
anything that passes through something, hangs in the air unsaid, or stands in front of the lens gets the scene refused, in words,
before a frame is rendered. So don't work out heights by hand: say what a thing is `on`.

A scene:
  length    seconds
  set       one of SETS. sky_counter is a matte wooden counter, its top at z 0, level across the picture before a clean blue
            backdrop, lit for showing things up close: use it for anything on a surface. sky_set is the plain blue with a floor,
            for people
  cast      id -> who or what's in it:
    {"type": "person", "character": an id in characters/specs, "at": [x, y], "facing": degrees (0 faces -y, toward the
     default camera) or another cast id, "stance": a body clip they hold, "life": how fast it plays, 0.22 by default}
    {"type": "prop", "prop": one of PROPS, "at": [x, y, z], "points": [x, y, z], "up": [x, y, z]}
    {"type": "prop", "prop": a thing in things/specs (a bird, a bench, an apple),
     "on": another cast id, or "set" for the counter or floor: it comes down until the two touch, and rests there. With "on",
           `at` is just [x, y], or left out to center it: its "by" spot (or its middle) over the other's "onto" spot (or its middle),
     "to": "id:spot": it's fixed to another thing at a point, from any side, its "by" spot (or its middle) meeting that spot exactly:
           a shaft into a motor, blades on a hub, a lid on a hinge. It stays where it's put, and the two may overlap,
     "at": [x, y, z] where its underside sits, for what isn't on anything, "floats": true if it's meant to hang in the air,
           a marker such as an arrow or a bulb over a head,
     "facing": degrees or a cast id, as for a person, or "points" and "up" [x, y, z] to aim its own z and y,
     "size": times its real size, 1 by default}
  touching  optional, [[id, id], ...]: what's meant to overlap, such as a shaft inside the motor that turns it
  happens   what happens, each with "do" and "t" unless it's for the whole scene:
    wear       who, prop, size                                    for the whole scene; a hat. The head and the inside of the hat
                                                                  are measured, it's fitted and seated, it rides on the head, and
                                                                  the hair under it is gone. `size` only to overrule the fit
    spin       prop, to, rate, axis, about, ease, start           turning on the spot from t until `to`, `rate` turns a second (minus
                                                                  for the other way), about its own axis x, y or z through a spot
                                                                  (or its middle), reaching speed over `ease` seconds, from `start`
                                                                  degrees. Choose the axis so the lens sees it turn: a thing
                                                                  turning in a plane edge-on to the lens is a line sliding about
    slide      prop, over, from or by, ease                       straight along a line, level, keeping its turn. `from` [x, y, z] is
                                                                  how far off its resting place it starts (there until t), so it's
                                                                  set down exactly; `by` is how far it goes from where it is. ease
                                                                  is in (speeding up), out (slowing) or inout, the default
    lit        on ("id" or "id:spot"), color (one of COLORS), to, radius, soft, strength, only, fade, cover, rim
                                                                  the thing's own surface lights up from t until `to`, and can't
                                                                  leave its edges. A flash on the word that names it: whole, about
                                                                  0.5 s. Heat: a spot with a `radius` in meters, on the inside of a
                                                                  pan. `only`: part ids of a built thing. strength about 1; much
                                                                  above that it washes to white. Whole, its edges burn brightest with a
                                                                  soft halo and its middle keeps some of its own color: `rim` (0 to 1,
                                                                  0.45 by default) sets how much, and `cover` how far it covers, so
                                                                  metal stays metal at about 0.5. A patch fades over the `soft` share
                                                                  of its radius: 0.12 for a crisp edge right at the floor of a pan
    flow       on ("id" or "id:spot"), color, to, radii, along, side, arcs, arc, turn, pulses, speed, width, steady, peak,
               beads, bead_color, reverse
                                                                  thin light running on a thing: white-hot lines with their color in
                                                                  the halo, the way current or a signal is shown. radii: circles around
                                                                  the spot in meters, laid on the surface facing `side` (top or under),
                                                                  and stopping at its edge. arcs and arc (degrees): only that much of
                                                                  each circle, spaced round it, for streaks. along: a part of a built
                                                                  thing that has a line (a pipe or spiral) instead. pulses and speed:
                                                                  brighter stretches running along it, per line and per second. beads:
                                                                  how many beads run along it, thicker and softer. reverse: seconds
                                                                  between turning back. width in meters, 0.0012 by default. lift:
                                                                  meters above its part's line, to draw a coil's line on the glass over it
    tint       prop, color (a name or [r, g, b]), to, amount      its own color moving toward this from t until `to`: a steak browning
    hold       who, prop, hand (R or L), grip (one of GRIPS)      for the whole scene; the arm follows the prop
    bite       who, prop, yaw                                     for the whole scene; held in the teeth, turned by yaw
    move       prop, grip, over (seconds)                         a held prop goes to another grip
    strike     who, prop, target, along, over (seconds it falls)  lands at t on a prop, `along` meters from its origin,
                                                                  or on a person ("id:forehead"). Code ends the arc on the
                                                                  surface, and whoever holds a struck prop reels, more the
                                                                  further out it's hit; a struck person reels too
    fly        prop, from, to, over, hits, slow                   thrown, on gravity's arc, arriving at t + over. from and
                                                                  to are aims or [x, y, z]. If it `hits` a person they
                                                                  reel and it bounces away, falling to the floor. `slow`
                                                                  is the share of real time, for slow motion
    go         prop, through, over, move, then, speed, lands, hits,   under its own power, nose first, through these places
               ends_facing                                        (aims or [x, y, z]) from wherever it is, leaning into
                                                                  turns. `move` plays on the way, `then` once it's there.
                                                                  If it `lands` it slows down, flares and stops on the last
                                                                  place, and rides on it if that's a person. If it `hits` a
                                                                  person they reel and it falls. Otherwise it flies on
    play       prop, move, to, speed                              a thing's clip from t until `to`, looping; speed below 1
                                                                  is slow motion. run.py thing lists a thing's moves
    rock       prop, over, times, degrees, axis, about            a whole thing tipping about a place on it, for what has no
                                                                  clip: it draws back `degrees`, 20 by default, and snaps to
                                                                  where it stood, `times` times in `over` seconds, so each
                                                                  snap lands at t + over x k / times. Place it so where it
                                                                  stands is the contact. axis is pitch (draws its nose up),
                                                                  roll or yaw. about is one of its spots, or its underside
    expression who, name (one of EXPRESSIONS or null), amount
    face       who, keys {face shape: value}, over
    gaze       who, x, y                                          -1 to 1: their left, and up
    glow       who, on (one of GLOW_PLACES), color (one of COLORS), to (seconds), radius, strength
                                                                  on a person's skin. strength 0 to 1, 1 by default: about 0.5 keeps
                                                                  the skin showing, and full is flat paint in a close shot
    rings      on ("id:along"), color, reach, over, count, width  thin clean circles spreading from a point to `reach` meters and
                                                                  fading over `over` seconds, facing the shot's lens: a force going
                                                                  out, a hit, a field
    sparks     on ("id:along"), kind, count                       `count` of them, 26 by default: a bird's peck wants about 6, or a close
                                                                  shot fills with them. Bright sparks for metal on metal, or kind "chips": what
                                                                  flies off wood or stone. A strike's own come with its
                                                                  "sparks": false, true or "chips"
    knock      who, size (degrees), axis [x, y, z]                a blow: head, neck and chest ring down together
  shots     cuts, in order, the first at 0:
    {"t": when, "on": what it's aimed at (see `aim`), "frame": meters of picture top to bottom, "angle": [round them,
     up], 0 being in front of them, "square": true: `round` counts from the set rather than from the way a thing faces, so
     [0, up] looks straight across the counter and its edges stay level, "lens": mm (20 to 30 is the style, close and wide), "fstop",
     "push": how much nearer it ends up, as a share of the distance, "drift": [x, y, z] meters it slides, "shows": cast ids, if only
     some are in this shot: something near the lens is cleared this way, "follow": true: it moves with a moving prop, "ahead": seconds:
     it aims at where its subject will be this long after the shot starts, for a close-up of a landing}
    A cut is a clear change: the same angle at a clearly different size, or a clearly new angle. A small swing between two
    shots of about the same size reads as the screen wobbling, and is refused. So is a push or a drift fast enough to see as
    a move rather than feel: at most PUSH_PER_SECOND of the distance a second
  captions  [{"t", "to", "text"}]

`aim` is a person's "id:" plus one of AIMS, or a prop's "id:along" in meters, or one of a thing's spots ("id:head"). A shot
on a thing is relative to the way it's heading then, so angle [0, 0] sees its face.
"""
from __future__ import annotations

import difflib
import json
import math
from pathlib import Path

SETS = ("gym", "sky_set", "sky_counter", "desert_lot", "studio", "workbench", "engine_void")
PROPS = ("katana", "long_sword", "stick", "ball")
EXPRESSIONS = ("happy", "smile", "surprised", "shocked", "scared", "angry", "yelling", "sad", "disgusted", "thinking",
               "curious")
ROCK_AXES = ("pitch", "roll", "yaw")
SPARKS = ("sparks", "chips")
GRIPS = ("low_cross", "ready", "raised", "overhead", "at_side", "forward")
GLOW_PLACES = ("jaw", "forehead", "chest", "stomach", "neck")
COLORS = ("green", "red", "blue", "yellow", "white", "orange", "cream", "cyan", "salmon", "gold", "ice")
AIMS = ("eyes", "mouth", "forehead", "jaw", "neck", "chest", "stomach", "hips", "body", "crown", "shoulder_r", "shoulder_l",
        "hand_r", "hand_l")
EVENTS = {
    "hold": ("who", "prop", "hand", "grip"),
    "bite": ("who", "prop"),
    "move": ("t", "prop", "grip", "over"),
    "strike": ("t", "who", "prop", "target"),
    "fly": ("t", "prop", "from", "to", "over"),
    "go": ("t", "prop", "through", "over"),
    "play": ("t", "prop", "move"),
    "rock": ("t", "prop", "over"),
    "expression": ("t", "who", "name"),
    "face": ("t", "who", "keys"),
    "gaze": ("t", "who"),
    "glow": ("t", "who", "on", "color", "to"),
    "aura": ("t", "on", "color", "to"),     # what `lit` was called: kept so a short directed before still films
    "lit": ("t", "on", "color"),
    "flow": ("t", "on", "color"),
    "tint": ("t", "prop", "color"),
    "wear": ("who", "prop"),
    "spin": ("t", "prop"),
    "slide": ("t", "prop", "over"),
    "rings": ("t", "on"),
    "sparks": ("t", "on"),
    "knock": ("t", "who", "size"),
}
LONGEST_SHOT = 4.0    # the style cuts about every second; anything held longer than this has lost it
ROCK_DEGREES = 18.0   # a cut that swings less than this, between shots of about the same size, reads as the screen wobbling
SAME_SIZE = 1.3       # shots within this ratio of each other's size count as about the same size
PUSH_PER_SECOND = 0.05      # the reference's camera creeps at most: a faster push throbs from cut to cut
AXES = ("x", "y", "z")
EASES = ("in", "out", "inout")


class Refused(ValueError):
    """A scene the stage wouldn't build, because it isn't physically right. `problems` says what's wrong, each in words."""

    def __init__(self, problems: list[str]):
        super().__init__("; ".join(problems))
        self.problems = problems


def load(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _num(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _named(label: str, value, choices) -> list[str]:
    if value in choices:
        return []
    close = difflib.get_close_matches(str(value), [str(c) for c in choices], n=3, cutoff=0.5)
    hint = f"; did you mean {', '.join(close)}?" if close else f"; the choices are {', '.join(map(str, choices))}"
    return [f"{label}: no {value!r}{hint}"]


def _aim(label: str, value, cast: dict, things: dict | None = None) -> list[str]:
    who, _, part = str(value).partition(":")
    if who not in cast:
        return [f"{label}: nothing called {who!r} in the cast"]
    if cast[who].get("type") == "person":
        return _named(label, part, AIMS)
    if part == "" or _num(_float(part)):
        return []
    spots = (things or {}).get(cast[who].get("prop"), {}).get("spots") or []
    if part in spots:
        return []
    return [f"{label}: {part!r} isn't meters along {who}" + (f" or a spot on it: {', '.join(spots)}" if spots else "")]


def _float(text: str):
    try:
        return float(text)
    except ValueError:
        return None


def _resting_problems(cid: str, c: dict, cast: dict, things: dict) -> list[str]:
    """What's wrong with how a thing says it's resting on another."""
    out = []
    if c.get("prop") not in things:
        out.append(f"cast {cid}: only a thing from the library can be `on` something")
        return out
    under = c["on"]
    if under != "set" and under not in cast:
        out.append(f"cast {cid}: it's on {under!r}, who isn't in the cast")
    elif under == cid:
        out.append(f"cast {cid}: it can't be on itself")
    elif under != "set" and cast[under].get("prop") not in things:
        out.append(f"cast {cid}: it's on {under!r}, which isn't a thing from the library")
    if "at" in c and not (isinstance(c["at"], list) and len(c["at"]) == 2 and all(_num(v) for v in c["at"])):
        out.append(f"cast {cid}: with `on`, its at is just [x, y], or left out to center it")
    if "by" in c and c["by"] not in things[c["prop"]].get("spots", []):
        out.append(f"cast {cid}: by {c['by']!r} isn't a spot on it")
    if "onto" in c and (under == "set" or c["onto"] not in things.get(cast.get(under, {}).get("prop"), {}).get("spots", [])):
        out.append(f"cast {cid}: onto {c['onto']!r} isn't a spot on {under}")
    return out


def _fixed_problems(cid: str, c: dict, cast: dict, things: dict) -> list[str]:
    """What's wrong with how a thing says it's fixed to another."""
    if "on" in c:
        return [f"cast {cid}: it's on something or fixed to something, not both"]
    if c.get("prop") not in things:
        return [f"cast {cid}: only a thing from the library can be fixed `to` something"]
    other, _, spot = str(c["to"]).partition(":")
    out = []
    if other == cid:
        out.append(f"cast {cid}: it can't be fixed to itself")
    elif cast.get(other, {}).get("prop") not in things:
        out.append(f"cast {cid}: it's fixed to {other!r}, which isn't a thing in the cast")
    elif spot not in things[cast[other]["prop"]].get("spots", []):
        out.append(f"cast {cid}: to {c['to']!r} needs a spot on {other}: {', '.join(things[cast[other]['prop']].get('spots', [])) or 'it has none'}")
    if "by" in c and c["by"] not in things[c["prop"]].get("spots", []):
        out.append(f"cast {cid}: by {c['by']!r} isn't a spot on it")
    return out


def _cast_problems(cast: dict, characters: list[str], clips: list[str], things: dict) -> list[str]:
    out = []
    for cid, c in cast.items():
        kind = c.get("type")
        if kind == "person":
            out += _named(f"cast {cid}: character", c.get("character"), characters)
            out += _named(f"cast {cid}: stance", c.get("stance"), clips)
            at = c.get("at", [0, 0])
            if not (isinstance(at, list) and len(at) == 2 and all(_num(v) for v in at)):
                out.append(f"cast {cid}: at needs [x, y]")
            facing = c.get("facing", 0)
            if not _num(facing) and facing not in cast:
                out.append(f"cast {cid}: facing {facing!r} is neither degrees nor in the cast")
        elif kind == "prop":
            out += _named(f"cast {cid}: prop", c.get("prop"), (*PROPS, *things))
            if "size" in c and not (_num(c["size"]) and c["size"] > 0):
                out.append(f"cast {cid}: size {c['size']!r} isn't a number above 0")
            if "on" in c:
                out += _resting_problems(cid, c, cast, things)
            if "to" in c:
                out += _fixed_problems(cid, c, cast, things)
            facing = c.get("facing", 0)
            if not _num(facing) and facing not in cast:
                out.append(f"cast {cid}: facing {facing!r} is neither degrees nor in the cast")
        else:
            out.append(f"cast {cid}: type {kind!r} isn't person or prop")
    return out


def _event_problems(e: dict, i: int, scene: dict, things: dict) -> list[str]:
    cast, length = scene["cast"], scene["length"]
    kind = e.get("do")
    if kind not in EVENTS:
        return _named(f"happens {i}: do", kind, tuple(EVENTS))
    label = f"happens {i} ({kind})"
    out = [f"{label}: missing {key}" for key in EVENTS[kind] if key not in e]
    if out:
        return out
    if "t" in e and not (_num(e["t"]) and 0 <= e["t"] <= length):
        out.append(f"{label}: t {e['t']!r} is outside the scene")
    for key in ("who",):
        if key in e and cast.get(e[key], {}).get("type") != "person":
            out.append(f"{label}: {e[key]!r} isn't a person in the cast")
    if "prop" in e and cast.get(e["prop"], {}).get("type") != "prop":
        out.append(f"{label}: {e['prop']!r} isn't a prop in the cast")
    if kind == "strike":
        if cast.get(e["target"], {}).get("type") == "prop":
            if not _num(e.get("along")):
                out.append(f"{label}: say how far along {e['target']} it lands, in meters")
        else:
            out += _aim(f"{label}: target", e["target"], cast, things)
    if kind == "fly":
        for key in ("from", "to"):
            if not (isinstance(e[key], list) and len(e[key]) == 3):
                out += _aim(f"{label}: {key}", e[key], cast, things)
        if not (_num(e["over"]) and e["over"] > 0):
            out.append(f"{label}: over needs seconds")
        if "hits" in e and cast.get(e["hits"], {}).get("type") != "person":
            out.append(f"{label}: hits {e['hits']!r}, who isn't a person in the cast")
    if kind == "go":
        through = e["through"]
        if not (isinstance(through, list) and through):
            out.append(f"{label}: through needs a list of places")
        else:
            for stop in through:
                if not (isinstance(stop, list) and len(stop) == 3):
                    out += _aim(f"{label}: through", stop, cast, things)
        if not (_num(e["over"]) and e["over"] > 0):
            out.append(f"{label}: over needs seconds")
        if "hits" in e and cast.get(e["hits"], {}).get("type") != "person":
            out.append(f"{label}: hits {e['hits']!r}, who isn't a person in the cast")
        if "ends_facing" in e and not _num(e["ends_facing"]) and e["ends_facing"] not in cast:
            out.append(f"{label}: ends_facing {e['ends_facing']!r} is neither degrees nor in the cast")
    if kind == "rock":
        entry = things.get(cast.get(e["prop"], {}).get("prop"))
        if entry is None:
            out.append(f"{label}: {e['prop']} isn't a thing from the library")
        elif "about" in e and e["about"] not in entry.get("spots", []):
            out.append(f"{label}: about {e['about']!r} isn't a spot on it: {', '.join(entry.get('spots', [])) or 'it has none'}")
        out += _named(f"{label}: axis", e.get("axis", "pitch"), ROCK_AXES)
        if not (_num(e["over"]) and e["over"] > 0):
            out.append(f"{label}: over needs seconds")
        if not (isinstance(e.get("times", 1), int) and e.get("times", 1) > 0):
            out.append(f"{label}: times has to be a whole number above 0")
        if not (_num(e.get("degrees", 20)) and 0 < e.get("degrees", 20) <= 120):
            out.append(f"{label}: degrees has to be above 0, and 120 at most")
    if kind in ("go", "play"):
        moves = things.get(cast.get(e["prop"], {}).get("prop"), {}).get("moves") or []
        for key in ("move", "then"):
            if key in e:
                out += _named(f"{label}: {key}", e[key], moves) if moves else [f"{label}: {e['prop']} has no moves"]
        if "speed" in e and not (_num(e["speed"]) and e["speed"] > 0):
            out.append(f"{label}: speed {e['speed']!r} isn't a number above 0")
    if kind == "hold":
        out += _named(f"{label}: hand", e["hand"], ("R", "L"))
    if kind in ("hold", "move"):
        out += _named(f"{label}: grip", e["grip"], GRIPS)
    if kind == "expression" and e["name"] is not None:
        out += _named(f"{label}: name", e["name"], EXPRESSIONS)
    if kind == "glow":
        out += _named(f"{label}: on", e["on"], GLOW_PLACES)
        out += _named(f"{label}: color", e["color"], COLORS)
        if not (_num(e["to"]) and e["t"] < e["to"]):
            out.append(f"{label}: to must come after t")
    if kind in ("rings", "sparks"):
        out += _aim(f"{label}: on", e["on"], cast, things)
    if kind == "sparks" and "kind" in e:
        out += _named(f"{label}: kind", e["kind"], SPARKS)
    if kind == "strike" and isinstance(e.get("sparks"), str):
        out += _named(f"{label}: sparks", e["sparks"], SPARKS)
    if kind in ("aura", "lit", "flow"):
        who, _, part = str(e["on"]).partition(":")
        entry = things.get(cast.get(who, {}).get("prop"))
        if entry is None:
            out.append(f"{label}: {who!r} isn't a thing from the library: a person's is `glow`")
            return out
        if part and part not in entry.get("spots", []):
            out.append(f"{label}: {part!r} isn't a spot on {who}: {', '.join(entry.get('spots', [])) or 'it has none'}")
        out += _named(f"{label}: color", e["color"], COLORS)
        if "to" in e and not (_num(e["to"]) and e["t"] < e["to"]):
            out.append(f"{label}: to must come after t")
        if kind == "flow":
            if "along" in e and e["along"] not in entry.get("lines", []):
                out.append(f"{label}: along {e['along']!r} isn't a line on {who}: {', '.join(entry.get('lines', [])) or 'it has none'}")
            elif "along" not in e and not (isinstance(e.get("radii"), list) and e["radii"] and all(_num(r) and r > 0 for r in e["radii"])):
                out.append(f"{label}: needs radii, a list of meters, or along, a line on {who}")
            if "side" in e and e["side"] not in ("top", "under"):
                out.append(f"{label}: side is top or under")
        if kind == "lit" and "radius" in e and not part:
            out.append(f"{label}: a radius needs a spot to be around: on \"{who}:a spot\"")
    if kind == "wear":
        if e["prop"] in cast and cast[e["prop"]].get("prop") not in things:
            out.append(f"{label}: only a thing from the library can be worn")
    if kind == "tint":
        if not (e["color"] in COLORS or (isinstance(e["color"], list) and len(e["color"]) == 3 and all(_num(v) and 0 <= v <= 1 for v in e["color"]))):
            out.append(f"{label}: color is one of {', '.join(COLORS)}, or [r, g, b], each 0 to 1")
    if kind == "spin":
        entry = things.get(cast.get(e["prop"], {}).get("prop"))
        if entry is None:
            out.append(f"{label}: {e['prop']} isn't a thing from the library")
        else:
            if "about" in e and e["about"] not in entry.get("spots", []):
                out.append(f"{label}: about {e['about']!r} isn't a spot on it: {', '.join(entry.get('spots', [])) or 'it has none'}")
            out += _named(f"{label}: axis", e.get("axis", "z"), AXES)
        if "rate" in e and not _num(e["rate"]):
            out.append(f"{label}: rate is turns a second")
        if "to" in e and not (_num(e["to"]) and e["t"] < e["to"]):
            out.append(f"{label}: to must come after t")
    if kind == "slide":
        if ("from" in e) == ("by" in e):
            out.append(f"{label}: says from or by, one of them")
        for key in ("from", "by"):
            if key in e and not (isinstance(e[key], list) and len(e[key]) == 3 and all(_num(v) for v in e[key])):
                out.append(f"{label}: {key} is [x, y, z] meters")
        if not (_num(e["over"]) and e["over"] > 0):
            out.append(f"{label}: over needs seconds")
        out += _named(f"{label}: ease", e.get("ease", "inout"), EASES)
    return out


def _way(shot: dict) -> tuple[float, float, float]:
    around, up = (math.radians(v) for v in shot.get("angle", (0, 0)))
    return math.sin(around) * math.cos(up), -math.cos(around) * math.cos(up), math.sin(up)


def _cut_problems(shots: list[dict], cast: dict) -> list[str]:
    """Shots of one subject that cut with too small a swing, and pushes fast enough to throb."""
    out = []
    for i, (a, b) in enumerate(zip(shots, shots[1:]), 1):
        if str(a.get("on")).partition(":")[0] != str(b.get("on")).partition(":")[0] or bool(a.get("square")) != bool(b.get("square")):
            continue
        if not (_num(a.get("frame")) and _num(b.get("frame")) and a["frame"] > 0 and b["frame"] > 0):
            continue
        across = sum(x * y for x, y in zip(_way(a), _way(b)))
        swing = math.degrees(math.acos(max(-1.0, min(1.0, across))))
        size = max(a["frame"], b["frame"]) / min(a["frame"], b["frame"])
        if 0.5 < swing < ROCK_DEGREES and size < SAME_SIZE:
            out.append(f"shot {i}: it swings only {swing:.0f} degrees from the last at about the same size, which reads as the screen "
                       f"wobbling. Keep the angle and change the size by more than {SAME_SIZE}x, or swing at least {ROCK_DEGREES:.0f} degrees")
    return out


def check(scene: dict, characters: list[str], clips: list[str], things: dict | None = None) -> list[str]:
    """Everything wrong with a scene, in words. `things` is things/build.py's menu: each thing's moves and spots."""
    things = things or {}
    if not isinstance(scene, dict):
        return ["a scene is a JSON object"]
    out = [f"{key}: missing" for key in ("length", "set", "cast", "shots") if key not in scene]
    if out:
        return out
    if not (_num(scene["length"]) and 0.5 <= scene["length"] <= 180):
        out.append(f"length: {scene['length']!r} isn't between 0.5 and 180 seconds")
        return out
    out += _named("set", scene["set"], SETS)
    out += _cast_problems(scene["cast"], characters, clips, things)
    if out:
        return out
    for i, e in enumerate(scene.get("happens") or []):
        out += _event_problems(e, i, scene, things)
    held = {e["prop"] for e in scene.get("happens") or [] if e.get("do") in ("hold", "bite") and "prop" in e}
    for e in scene.get("happens") or []:
        if e.get("do") == "strike" and e.get("prop") not in held:
            out.append(f"strike: {e.get('who')} has to hold {e.get('prop')} to strike with it")
    shots = scene["shots"]
    if not shots or shots[0].get("t") != 0:
        out.append("shots: the first has to start at 0")
    times = [s.get("t", -1) for s in shots] + [scene["length"]]
    for i, s in enumerate(shots):
        label = f"shot {i}"
        out += _aim(f"{label}: on", s.get("on"), scene["cast"], things)
        if not (_num(s.get("frame")) and 0.05 <= s["frame"] <= 40):
            out.append(f"{label}: frame {s.get('frame')!r} isn't how many meters of picture")
        if not (_num(s.get("lens", 28)) and 12 <= s.get("lens", 28) <= 135):
            out.append(f"{label}: lens {s.get('lens')!r} isn't in mm")
        if times[i + 1] <= times[i]:
            out.append(f"{label}: starts after the next one")
        elif times[i + 1] - times[i] > LONGEST_SHOT:
            out.append(f"{label}: {times[i + 1] - times[i]:.1f} s is too long: this style cuts about every second")
        elif abs(s.get("push", 0)) > PUSH_PER_SECOND * (times[i + 1] - times[i]) + 1e-6:
            out.append(f"{label}: a push of {s['push']} over {times[i + 1] - times[i]:.1f} s moves fast enough to see, and throbs from cut to "
                       f"cut. At most {PUSH_PER_SECOND} a second, or hold still")
        for cid in s.get("shows") or []:
            if cid not in scene["cast"]:
                out.append(f"{label}: shows {cid!r}, who isn't in the cast")
    out += _cut_problems(shots, scene["cast"])
    for pair in scene.get("touching") or []:
        if not (isinstance(pair, list) and len(pair) == 2 and all(cid in scene["cast"] for cid in pair)):
            out.append(f"touching: {pair!r} is a pair of cast ids")
    for i, c in enumerate(scene.get("captions") or []):
        if not (isinstance(c.get("text"), str) and _num(c.get("t")) and _num(c.get("to")) and c["t"] < c["to"]):
            out.append(f"caption {i}: needs text, t, and a later to")
    return out

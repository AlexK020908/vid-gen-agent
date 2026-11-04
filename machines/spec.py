"""The machine spec: what a machine is made of, checked in code.

A spec is JSON:
  name     what it is ("diesel pile hammer")
  steps    the stages the story builds it in, in order ("an iron block", "split into ram and anvil", ...); a part
           says from which step it's there and until which, so the machine grows as the story does
  parts    named parts, each a shape with its sizes in meters, a palette material, a place, and optionally a
           parent, a joint, a group, whether a cutaway cuts it, and its steps
  anchors  named points on parts for a label's dot: name -> [part, [x, y, z] on the part]
  couple   parts driven by others: a crank turning drives a piston (crank) and tilts its connecting rod (rod),
           a gear drives a gear, a part follows another
  contacts pairs of parts allowed to touch or sit inside one another (the overlap check skips them)

Shapes (kind and what it needs):
  box       size [x, y, z], bevel
  cylinder  r, h, bevel                    standing on its origin, along its z
  tube      r_out, r_in, h
  cone      r1 (bottom), r2 (top), h
  lathe     points [[r, z], ...]           turned about its z: pistons, nails, cups
  sphere    r
  torus     major, minor, arc (degrees), axis
  extrude   outline [[x, z], ...], depth, bevel   a flat outline in its x-z plane, thick along y: brackets, cams, levers
  pipe      path [[x, y, z], ...], r, bend  a tube along a path with rounded bends: pipes, hoses, cables
  rods      pairs [[[x, y, z], [x, y, z]], ...], r
  truss     length, width, bays, chord, lace   a square lattice boom along z (a crane's)
  spring    r, wire, turns, h              a coil along z that squashes with its joint
  spiral    r_in, r_out, turns, wire       a flat coil of wire in its x-y plane: a cooker's coil
  text      body, height, depth            letters in the x-z plane facing -y: a name printed on a can
  group     nothing: an empty that holds other parts (a hammer's pivot)

A part marked "helper" is never drawn: another part lists it under "subtract" to have it cut out of itself, which
makes holes (an engine block's bores, its crankcase).

Joints: {"type": slide | hinge | spin | stretch, "axis": x | y | z, "min", "max", "rest", "check"}. "check" is
the [min, max] the overlap test tries, when a part can move further than it's ever used with everything there
(a ram thrown high before its guide rods exist). A slide moves the part
along the axis by its value (meters), a hinge or spin turns it about the axis through its origin (degrees), a
stretch makes it that long along the axis (meters: a crane's cable, driven by its hook's height). A shot only
sets joint values, so everything a part carries moves with it and the mechanics stay true.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

PALETTE = ("steel", "bright_steel", "black_steel", "dark_steel", "pile_paint", "glass_rod", "safety_yellow", "hazard_stripes", "cut", "chrome",
           "rubber", "white_paint", "red_paint", "blue_paint", "orange_paint", "barrier_stripes", "air", "wood",
           "pale_wood", "wood_cut", "sand", "far", "soil_top", "soil_mid", "soil_low", "soil_deep", "copper", "stainless", "cast_iron",
           "black_glass", "bakelite", "counter_wood")

SHAPES = {
    "box": ("size",),
    "cylinder": ("r", "h"),
    "tube": ("r_out", "r_in", "h"),
    "cone": ("r1", "r2", "h"),
    "lathe": ("points",),
    "sphere": ("r",),
    "torus": ("major", "minor"),
    "extrude": ("outline", "depth"),
    "pipe": ("path", "r"),
    "rods": ("pairs", "r"),
    "truss": ("length", "width", "bays"),
    "spring": ("r", "wire", "turns", "h"),
    "spiral": ("r_in", "r_out", "turns", "wire"),
    "text": ("body", "height"),
    "group": (),
}
JOINTS = ("slide", "hinge", "spin", "stretch")
AXES = ("x", "y", "z")
COUPLINGS = ("crank", "rod", "gear", "follow")
BIGGEST = 500.0    # meters: nothing a machine short shows is bigger (a crane's boom, a lot)
SMALLEST = 0.0002  # meters: a nail's point is about this


def load(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _num(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _vec(value, n=3) -> bool:
    return isinstance(value, list) and len(value) == n and all(_num(v) for v in value)


def _size_problems(pid: str, part: dict) -> list[str]:
    out = []
    kind = part["kind"]
    for key in ("r", "h", "r_out", "r_in", "r1", "r2", "major", "minor", "depth", "length", "width", "wire", "bevel",
                "chord", "lace", "bend", "height"):
        if key in part:
            v = part[key]
            if not _num(v) or v < 0:
                out.append(f"part {pid}: {key} must be a number of meters, 0 or more (got {v!r})")
            elif v > BIGGEST:
                out.append(f"part {pid}: {key} is {v} m, more than the {BIGGEST:g} m anything here is")
            elif key in ("r", "h", "r_out", "major", "minor", "depth", "length", "width", "wire") and v < SMALLEST:
                out.append(f"part {pid}: {key} is {v} m, too small to see")
    if kind == "box":
        if not _vec(part.get("size")) or any(v <= 0 for v in part["size"]):
            out.append(f"part {pid}: a box's size is [x, y, z] in meters, each more than 0")
    if kind == "tube" and _num(part.get("r_in")) and _num(part.get("r_out")) and part["r_in"] >= part["r_out"]:
        out.append(f"part {pid}: a tube's r_in ({part['r_in']}) must be less than its r_out ({part['r_out']})")
    if kind == "lathe":
        pts = part.get("points")
        if not isinstance(pts, list) or len(pts) < 3 or not all(_vec(p, 2) for p in pts):
            out.append(f"part {pid}: a lathe's points are at least 3 [radius, height] pairs")
        elif any(p[0] < 0 for p in pts):
            out.append(f"part {pid}: a lathe's radii can't be negative")
    if kind == "extrude":
        pts = part.get("outline")
        if not isinstance(pts, list) or len(pts) < 3 or not all(_vec(p, 2) for p in pts):
            out.append(f"part {pid}: an extrude's outline is at least 3 [x, z] points")
    if kind == "pipe":
        path = part.get("path")
        if not isinstance(path, list) or len(path) < 2 or not all(_vec(p) for p in path):
            out.append(f"part {pid}: a pipe's path is at least 2 [x, y, z] points")
    if kind == "rods":
        pairs = part.get("pairs")
        if not isinstance(pairs, list) or not pairs or not all(
                isinstance(p, list) and len(p) == 2 and all(_vec(q) for q in p) for p in pairs):
            out.append(f"part {pid}: rods' pairs are [[x, y, z], [x, y, z]] point pairs")
    if kind == "spiral" and _num(part.get("r_in")) and _num(part.get("r_out")) and not 0 <= part["r_in"] < part["r_out"]:
        out.append(f"part {pid}: a spiral's r_in ({part['r_in']}) must be 0 or more and less than its r_out ({part['r_out']})")
    if kind == "torus" and "arc" in part and not (_num(part["arc"]) and 0 < part["arc"] <= 360):
        out.append(f"part {pid}: a torus's arc is degrees, more than 0 and at most 360")
    if kind == "truss" and not (isinstance(part.get("bays"), int) and part["bays"] >= 1):
        out.append(f"part {pid}: a truss's bays is a whole number, 1 or more")
    return out


def check(spec: dict) -> list[str]:
    """Every problem with a spec, in words the writer can fix; empty when it's good."""
    out: list[str] = []
    if not isinstance(spec.get("name"), str) or not spec["name"].strip():
        out.append("a spec needs a name")
    steps = spec.get("steps") or []
    if not isinstance(steps, list) or not all(isinstance(s, str) and s.strip() for s in steps):
        out.append("steps is a list of what each stage of the machine is, in words")
        steps = []
    parts = spec.get("parts")
    if not isinstance(parts, list) or not parts:
        return out + ["a spec needs parts"]
    ids: dict[str, dict] = {}
    for i, part in enumerate(parts):
        if not isinstance(part, dict) or not isinstance(part.get("id"), str) or not part["id"].strip():
            out.append(f"part {i + 1} needs an id")
            continue
        pid = part["id"]
        if pid in ids:
            out.append(f"two parts are called {pid}")
        ids[pid] = part
    for pid, part in ids.items():
        kind = part.get("kind")
        if kind not in SHAPES:
            out.append(f"part {pid}: kind must be one of {', '.join(SHAPES)} (got {kind!r})")
            continue
        for need in SHAPES[kind]:
            if need not in part:
                out.append(f"part {pid}: a {kind} needs {need}")
        if kind != "group" and not part.get("helper"):
            if part.get("material") not in PALETTE:
                out.append(f"part {pid}: material must be one of the palette ({', '.join(PALETTE)}), "
                           f"not {part.get('material')!r}")
        out += _size_problems(pid, part)
        for key in ("at", "rot"):
            if key in part and not _vec(part[key]):
                out.append(f"part {pid}: {key} is [x, y, z]")
        if "scale" in part and not (_num(part["scale"]) and part["scale"] > 0 or _vec(part["scale"])):
            out.append(f"part {pid}: scale is a number or [x, y, z]")
        parent = part.get("parent")
        if parent is not None and parent not in ids:
            out.append(f"part {pid}: its parent {parent!r} isn't a part")
        if "steps" in part:
            rng = part["steps"]
            ok = (isinstance(rng, list) and len(rng) == 2 and isinstance(rng[0], int)
                  and (rng[1] is None or isinstance(rng[1], int)))
            if not ok:
                out.append(f"part {pid}: steps is [first, last] step numbers (last null for to the end)")
            elif steps and not (1 <= rng[0] <= len(steps) and (rng[1] is None or rng[0] <= rng[1] <= len(steps))):
                out.append(f"part {pid}: steps {rng} are outside the machine's {len(steps)} steps")
        joint = part.get("joint")
        if joint is not None:
            if joint.get("type") not in JOINTS or joint.get("axis") not in AXES:
                out.append(f"part {pid}: a joint is a slide, hinge or spin along x, y or z")
            lo, hi = joint.get("min", 0), joint.get("max", 0)
            if joint.get("type") != "spin" and not (_num(lo) and _num(hi) and lo <= hi):
                out.append(f"part {pid}: its joint's min must be at most its max")
            rest = joint.get("rest", lo)
            if joint.get("type") != "spin" and _num(rest) and _num(lo) and _num(hi) and not lo <= rest <= hi:
                out.append(f"part {pid}: its joint rests at {rest}, outside {lo} to {hi}")
    out += _cycles(ids)
    for name, anchor in (spec.get("anchors") or {}).items():
        if not (isinstance(anchor, list) and len(anchor) == 2 and anchor[0] in ids and _vec(anchor[1])):
            out.append(f"anchor {name}: is [part, [x, y, z]] on a part that exists")
    for c in spec.get("couple") or []:
        if c.get("type") not in COUPLINGS:
            out.append(f"a coupling's type is one of {', '.join(COUPLINGS)}")
            continue
        for key in ("driver", "driven"):
            if c.get(key) not in ids:
                out.append(f"a {c['type']} coupling's {key} {c.get(key)!r} isn't a part")
            elif not ids[c[key]].get("joint"):
                out.append(f"a {c['type']} coupling's {key} {c[key]} has no joint to drive or be driven")
        if c["type"] in ("crank", "rod") and not (_num(c.get("throw")) and _num(c.get("rod"))
                                                  and 0 < c["throw"] < c["rod"]):
            out.append(f"a {c['type']} coupling needs throw (the crank's radius) less than rod "
                       "(the connecting rod's length)")
    for pid, part in ids.items():
        for hole in part.get("subtract") or []:
            if hole not in ids or not ids[hole].get("helper"):
                out.append(f"part {pid}: it subtracts {hole!r}, which must be a part marked helper")
    for pair in spec.get("contacts") or []:
        if not (isinstance(pair, list) and len(pair) == 2 and all(p in ids for p in pair)):
            out.append(f"contact {pair}: is a pair of parts that exist")
    return out


def _cycles(ids: dict[str, dict]) -> list[str]:
    out = []
    for pid in ids:
        seen, cur = {pid}, ids[pid].get("parent")
        while cur is not None and cur in ids:
            if cur in seen:
                out.append(f"part {pid}: its parents go round in a circle")
                break
            seen.add(cur)
            cur = ids[cur].get("parent")
    return out


def at_step(spec: dict, step: int) -> list[str]:
    """The ids of the parts there at `step` (1-based), a parent's absence taking its children with it."""
    ids = {p["id"]: p for p in spec["parts"]}

    def there(pid):
        rng = ids[pid].get("steps") or [1, None]
        here = rng[0] <= step and (rng[1] is None or step <= rng[1])
        parent = ids[pid].get("parent")
        return here and (parent is None or there(parent))

    return [pid for pid in ids if there(pid)]

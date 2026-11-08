"""A thing: anything a scene needs that isn't a person, a bird or a bench, written as a short JSON file in things/specs/ and
kept for reuse (CHARACTERS.md). `run.py thing --search <words>` looks for one, cheapest source first, and shows pictures to
choose from; `run.py thing <id>` fetches it, makes it the right size, and renders a sheet to look at.

A spec:
  what     what it is, in words
  source   where it comes from:
    {"kind": "polyhaven", "asset": an id}        free, CC0, real scans of everyday things. Needs no key
    {"kind": "sketchfab", "uid": a model's id}   free, and needs SKETCHFAB_TOKEN. Its license is read from Sketchfab when it's
                                                 fetched: CC0, or CC-BY, whose credit goes in the video's description
    {"kind": "url", "url": where, "member": the file, if it's in a zip, "license": "CC0" or "CC-BY", "page": the page saying
     so, "credit": the wording, for CC-BY}
    {"kind": "generate", "prompt": what to make}  a 3D model made to order on fal. It costs money, so only with --spend
    {"kind": "built", "parts": [...]}            made here from exact shapes, free, in the machine kit's format (machines/spec.py):
                                                 each part has an id, a kind and its sizes in meters, a material, and optionally
                                                 at, rot and parent. A material is one of the palette's, or a part's own
                                                 {"color": [r, g, b], "metal": 0 to 1, "rough": 0 to 1, "coat": 0 to 1, "glow": n, "pores": how wide the holes in it are, in meters, for a sponge or bread,
                                                 "clear": how much you see through it, 0 to 1}. clear_glass in the palette is a clean glass: a tube, a beaker,
                                                 a dish, a pane, with what's in it showing.
                                                 A part with "liquid": true is what's in it, shaped as it is at its fullest: water in a cup, mercury in a
                                                 tube, a drink in a straw. It's never solid: things go into it and nothing rests on it, and a scene says how
                                                 full it is (scenes/spec.py, `level` and `fill`), its top always flat and level whichever way it's turned.
                                                 Make it a fraction of a millimeter inside what holds it.
                                                 Anything simple and geometric comes out sharper this way than from a download:
                                                 a magnet, a pan, a stand, a coil, an arrow, a counter's fittings. A scan is for
                                                 what can't be drawn: food, animals, faces
  meters   how long its longest side is in real life, as it rests. A built thing is already its real size, so it has none
  turn     optional, degrees around z, so that its front is what the sheet's front view shows. Forward is -y, as for a person
  tilt     optional, [x, y] degrees, to stand it the right way up
  smooth   optional, true: welds a faceted model and shades it smooth, for one that looks like cut paper
  trim     optional, [boxes]: takes off what's inside each, as it stands after turn and tilt, such as the stand a museum mounted it on.
           A box gives a range on any of x, y and z, as shares of the model's whole size: {"y": [0, 0.5], "z": [0, 0.3]}
  trim_pale optional, [{"near": [x, y, z], "radius": meters, "above": 0 to 1}]: takes off faces paler than that near a place, in meters from its middle as a spot is:
           what's left of a white mount on a bird's toes, which a box would take the toes with
  colors   optional, {a material's name: [r, g, b]}, each 0 to 1, for a model that came grey or whose picture is no good: it takes
           the place of the picture. thing.json lists its materials
  moves    optional, {name: {"clip": a clip in the file, "from": frame, "to": frame}}, to name them or cut one clip into
           several. Left out, every clip in the file is a move by its own name. thing.json lists the file's clips
  rest     optional, a move: it stands in that move's first frame when nothing's playing
  spots    optional, {name: [x, y, z]}: places on it, in meters from its middle as it rests. A shot or an effect aims at
           "id:name". "grip" is where a hand closes on it. On a built thing they're in the same meters as its parts instead
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from machines import spec as machine_spec

SPECS = Path(__file__).resolve().parent / "specs"
LICENSES = ("CC0", "CC-BY")
KINDS = {"polyhaven": ("asset",), "sketchfab": ("uid",), "url": ("url", "license", "page"), "generate": ("prompt",), "built": ("parts",)}
OPTIONAL = ("turn", "tilt", "smooth", "colors", "moves", "rest", "spots", "trim", "trim_pale")


def all_ids() -> list[str]:
    return sorted(p.stem for p in SPECS.glob("*.json"))


def path_for(tid: str) -> Path:
    return SPECS / f"{tid}.json"


def load(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _num(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _built_problems(parts) -> list[str]:
    """A built thing's parts, by the machine kit's own check. A part's own paint is checked here, as the kit knows only its palette."""
    if not isinstance(parts, list):
        return ["source: parts is a list"]
    out, plain = [], []
    for part in parts:
        material = part.get("material") if isinstance(part, dict) else None
        if isinstance(material, dict):
            unknown = set(material) - {"color", "metal", "rough", "coat", "glow", "pores", "clear"}
            if unknown:
                out.append(f"part {part.get('id')}: its material has no {', '.join(sorted(unknown))}")
            color = material.get("color")
            if not (isinstance(color, list) and len(color) == 3 and all(_num(v) and 0 <= v <= 1 for v in color)):
                out.append(f"part {part.get('id')}: its material's color has to be [r, g, b], each 0 to 1")
            if "clear" in material and not (_num(material["clear"]) and 0 <= material["clear"] <= 1):
                out.append(f"part {part.get('id')}: clear is how much you see through it, 0 to 1")
            plain.append({**part, "material": "steel"})
        else:
            plain.append(part)
        if isinstance(part, dict) and "liquid" in part and not (part["liquid"] is True and part.get("kind") not in ("group", "spring", "spiral", "text", "rods", "truss")):
            out.append(f"part {part.get('id')}: liquid is true, on a part shaped like what it fills at its fullest")
    return out + machine_spec.check({"name": "built", "parts": plain})


def _source_problems(source) -> list[str]:
    if not isinstance(source, dict) or source.get("kind") not in KINDS:
        return [f"source: kind has to be one of {', '.join(KINDS)}"]
    out = [f"source: missing {key}" for key in KINDS[source["kind"]] if not source.get(key)]
    if source["kind"] == "built" and source.get("parts"):
        out += _built_problems(source["parts"])
    if source["kind"] == "url":
        if source.get("license") not in LICENSES:
            out.append(f"source: license {source.get('license')!r} isn't one we can use: {', '.join(LICENSES)}")
        elif source["license"] == "CC-BY" and not source.get("credit"):
            out.append("source: CC-BY needs the credit's wording")
    return out


def check(spec: dict) -> list[str]:
    """Everything wrong with a spec, in words."""
    if not isinstance(spec, dict):
        return ["a thing is a JSON object"]
    out = [f"{key}: missing" for key in ("what", "source") if key not in spec]
    if out:
        return out
    built = isinstance(spec["source"], dict) and spec["source"].get("kind") == "built"
    if "meters" not in spec and not built:
        return ["meters: missing"]
    out += _source_problems(spec["source"])
    known = {"what", "source", "meters", *OPTIONAL}
    out += [f"{key}: not something a thing has; it has {', '.join(sorted(known))}" for key in spec if key not in known]
    if "meters" in spec and not (_num(spec["meters"]) and 0.005 <= spec["meters"] <= 200):
        out.append(f"meters: {spec['meters']!r} isn't a real size, from 0.005 to 200")
    if "turn" in spec and not _num(spec["turn"]):
        out.append("turn: has to be degrees")
    if "tilt" in spec and not (isinstance(spec["tilt"], list) and len(spec["tilt"]) == 2 and all(_num(v) for v in spec["tilt"])):
        out.append("tilt: has to be [x, y] degrees")
    for name, color in (spec.get("colors") or {}).items():
        if not (isinstance(color, list) and len(color) == 3 and all(_num(v) and 0 <= v <= 1 for v in color)):
            out.append(f"color {name}: has to be [r, g, b], each 0 to 1")
    moves = spec.get("moves") or {}
    for name, move in moves.items():
        if not (isinstance(move, dict) and isinstance(move.get("clip"), str)):
            out.append(f"move {name}: says which clip it is")
        elif not (_num(move.get("from", 0)) and _num(move.get("to", 1)) and move.get("from", 0) < move.get("to", 1)):
            out.append(f"move {name}: from has to come before to")
    for name, at in (spec.get("spots") or {}).items():
        if not (isinstance(at, list) and len(at) == 3 and all(_num(v) for v in at)):
            out.append(f"spot {name}: has to be [x, y, z] meters")
    return out

"""The character spec: a person, written as JSON and checked in code before Blender starts (CHARACTERS.md).

A spec:
  name        what the story calls them. Invented: never a real person, or another creator's character
  gender      male or female
  preset      a starting person by name ("David", "Maya"), from `run.py characters --options`
  age         20 to 80
  hair        a hairstyle by name, or false for bald
  hair_color  a name from HAIR; the brows follow it
  eyes        a name from EYES
  outfit      an outfit by name
  footwear    a pair of shoes by name
  face_hair   optional, men only, a beard by name. Left out, they're clean-shaven: a preset can bring its own beard
  brows       optional, Eyebrows_001 to Eyebrows_009
  lipstick    optional, women only, how much of it, 0 to 1: a muted rose. It warms lips that render grey on darker skin
  clothes     optional, {part of a garment's name: [r, g, b]}, each 0 to 1. person.json lists an outfit's garments
  keys        optional, {slider: value}: face and body sliders such as "Stylized", "Eye Scale" or "jaw_width"
"""
from __future__ import annotations

import difflib
import json
import math
from pathlib import Path

SPECS = Path(__file__).resolve().parent / "specs"
REQUIRED = ("name", "gender", "preset", "age", "hair", "hair_color", "eyes", "outfit", "footwear")
OPTIONAL = ("face_hair", "brows", "lipstick", "clothes", "keys")
# saved on every person as keys a shot can blend (blender/people.py's EXPRESSIONS)
EXPRESSIONS = ("happy_smile", "Smile", "big_surprise", "flabbergasted", "unpleasant_surprise", "Angry", "angry_yell",
               "Sad", "Disgust", "concentrated", "intrigued")
# what each color means to the add-on's hair material, found by looking: its lightness runs far past 1
HAIR = {
    "black": {"lightness": 0.25, "redness": 0.3},
    "dark_brown": {"lightness": 0.7, "redness": 0.4},
    "brown": {"lightness": 1.1, "redness": 0.38},
    "light_brown": {"lightness": 1.7, "redness": 0.42},
    "red": {"lightness": 1.6, "redness": 0.8},
    "blonde": {"lightness": 3.2, "redness": 0.35},
    "grey": {"lightness": 1.5, "redness": 0.1, "salt_and_pepper": 0.8},
    "white": {"lightness": 2.0, "redness": 0.05, "salt_and_pepper": 1.0},
}
BROWS = {"black": 0.15, "dark_brown": 0.3, "brown": 0.55, "light_brown": 0.8, "red": 0.8, "blonde": 1.2, "grey": 0.9,
         "white": 1.3}
EYES = {"blue": [0.17, 0.33, 0.62], "brown": [0.20, 0.09, 0.03], "dark_brown": [0.13, 0.055, 0.02],
        "green": [0.16, 0.32, 0.14], "hazel": [0.28, 0.20, 0.07], "grey": [0.20, 0.24, 0.28]}
BROW_NAMES = tuple(f"Eyebrows_{i:03d}" for i in range(1, 10))


def load(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def path_for(cid: str) -> Path:
    return SPECS / f"{cid}.json"


def all_ids() -> list[str]:
    return sorted(p.stem for p in SPECS.glob("*.json"))


def _name(path: str) -> str:
    return path.replace("\\", "/").rsplit("/", 1)[-1].rsplit(".", 1)[0]


def _lookup(paths: list[str]) -> dict[str, str]:
    """Name -> path. A name in two folders means the first."""
    found: dict[str, str] = {}
    for path in paths:
        found.setdefault(_name(path), path)
    return found


def _num(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _named(label: str, value, choices) -> list[str]:
    if value in choices:
        return []
    close = difflib.get_close_matches(str(value), [str(c) for c in choices], n=3, cutoff=0.5)
    hint = f"; did you mean {', '.join(close)}?" if close else f"; the choices are {', '.join(map(str, choices))}"
    return [f"{label}: no {value!r}{hint}"]


def check(spec: dict, options: dict) -> list[str]:
    """Everything wrong with a spec, in words. `options` is render.humgen.options()."""
    if not isinstance(spec, dict):
        return ["a character is a JSON object"]
    problems = [f"{key}: missing" for key in REQUIRED if key not in spec]
    problems += [f"{key}: not a field of a character" for key in spec if key not in REQUIRED + OPTIONAL]
    if problems:
        return problems
    gender = spec["gender"]
    if gender not in ("male", "female"):
        return [f"gender: {gender!r} isn't male or female"]
    if not (isinstance(spec["name"], str) and spec["name"].strip()):
        problems.append("name: give them a name")
    problems += _named("preset", spec["preset"], _lookup(options["humans"][gender]))
    if not (_num(spec["age"]) and 20 <= spec["age"] <= 80):
        problems.append(f"age: {spec['age']!r} isn't between 20 and 80")
    if spec["hair"] is not False:
        problems += _named("hair", spec["hair"], _lookup(options["hair"][gender]))
    problems += _named("hair_color", spec["hair_color"], HAIR)
    problems += _named("eyes", spec["eyes"], EYES)
    problems += _named("outfit", spec["outfit"], _lookup(options["outfit"][gender]))
    problems += _named("footwear", spec["footwear"], _lookup(options["footwear"][gender]))
    if "face_hair" in spec and gender == "female":
        problems.append("face_hair: the add-on has no facial hair for women")
    elif "face_hair" in spec:
        problems += _named("face_hair", spec["face_hair"], _lookup(options["face_hair"]))
    if "brows" in spec:
        problems += _named("brows", spec["brows"], BROW_NAMES)
    if "lipstick" in spec and gender != "female":
        problems.append("lipstick: the add-on only has it for women")
    elif "lipstick" in spec and not (_num(spec["lipstick"]) and 0 <= spec["lipstick"] <= 1):
        problems.append(f"lipstick: {spec['lipstick']!r} isn't between 0 and 1")
    for part, rgb in (spec.get("clothes") or {}).items():
        if not (isinstance(rgb, list) and len(rgb) == 3 and all(_num(v) and 0 <= v <= 1 for v in rgb)):
            problems.append(f"clothes: {part} needs [r, g, b], each 0 to 1")
    for key, value in (spec.get("keys") or {}).items():
        problems += _named("keys", key, options["keys"])
        if not (_num(value) and -2 <= value <= 2):
            problems.append(f"keys: {key} is {value!r}, not between -2 and 2")
    return problems


def to_person(spec: dict, options: dict) -> dict:
    """What blender/humgen.py makes the person from: the same choices, as files in the add-on's content folder."""
    gender = spec["gender"]
    color = spec["hair_color"]
    person = {
        "preset": _lookup(options["humans"][gender])[spec["preset"]],
        "age": spec["age"],
        "hair": spec["hair"] and _lookup(options["hair"][gender])[spec["hair"]],
        "hair_color": {"salt_and_pepper": 0.0, **HAIR[color]},
        "brow_color": {"lightness": BROWS[color], "redness": HAIR[color]["redness"]},
        "brow_density": 2,
        "textures_8k": True,
        "eye_color": EYES[spec["eyes"]],
        "outfit": _lookup(options["outfit"][gender])[spec["outfit"]],
        "footwear": _lookup(options["footwear"][gender])[spec["footwear"]],
    }
    if gender == "male":
        person["face_hair"] = _lookup(options["face_hair"])[spec["face_hair"]] if spec.get("face_hair") else False
    faces = _lookup(options.get("expression") or [])
    person["expressions"] = [faces[name] for name in EXPRESSIONS if name in faces]
    if spec.get("lipstick"):
        person["makeup"] = {"lipstick_opacity": spec["lipstick"]}
    for key in ("brows", "clothes", "keys"):
        if spec.get(key):
            person[key] = spec[key]
    return person

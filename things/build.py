"""A thing's spec made into a saved model and a sheet to look at, in data/things/<id>/: `thing.blend`, `thing.json`,
`sheet.png`. A bad spec is refused with its reasons before anything's fetched, and a thing is only made again when its spec
changes.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from characters.build import sheet as tile
from render import blender_render
from things import get
from things import spec as thing_spec


MADE_BY = ("materials.py", "shapes.py", "kit.py", "things.py")     # what a built thing's look comes from, in blender/


def folder(config, tid: str) -> Path:
    return config.data_dir / "things" / tid


def _made_by(spec: dict) -> str:
    """For a built thing, what made it: its paint and shapes live in code, so a change there has to make it again."""
    if spec["source"].get("kind") != "built":
        return ""
    code = Path(__file__).resolve().parent.parent / "blender"
    return hashlib.sha256(b"".join((code / name).read_bytes() for name in MADE_BY)).hexdigest()[:16]


def made(config, tid: str) -> dict | None:
    path = folder(config, tid) / "thing.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def menu(config) -> dict:
    """What a scene can ask of each thing: id -> its moves and spots. A thing's clips are only known once it's been made."""
    out = {}
    for tid in thing_spec.all_ids():
        spec = thing_spec.load(thing_spec.path_for(tid))
        manifest = made(config, tid)
        moves = (manifest or {}).get("moves") or spec.get("moves") or {}
        lines = [part["id"] for part in spec["source"].get("parts") or [] if part.get("kind") in ("pipe", "spiral")]
        out[tid] = {"moves": sorted(moves), "spots": sorted(spec.get("spots") or {}), "lines": sorted(lines)}
    return out


def build(config, tid: str, spend: bool = False, say=print, spec: dict | None = None) -> dict:
    """Returns the thing's folder, its sheet and its thing.json. `spec` is for one still being tried, not yet on file."""
    spec = spec or thing_spec.load(thing_spec.path_for(tid))
    problems = thing_spec.check(spec)
    if problems:
        raise ValueError(f"{tid}: " + "; ".join(problems))
    where = folder(config, tid)
    have = made(config, tid)
    picture = where / "sheet" / "sheet.png"
    stamp = where / "made_by.txt"
    same_code = not _made_by(spec) or (stamp.exists() and stamp.read_text(encoding="utf-8") == _made_by(spec))
    if have and have.get("spec") == spec and picture.exists() and same_code:
        return {"id": tid, "folder": where, "sheet": picture, "manifest": have}
    say(f"{tid}: getting {spec['what']}")
    source = get.fetch(config, spec["source"], where / "source", spend, say)
    say(f"{tid}: into Blender")
    manifest = blender_render.make_thing(config, spec, source, where)
    say(f"{tid}: its sheet")
    result = blender_render.thing_sheet(config, where)
    picture = tile(result, where / "sheet", cell=(360, 480), columns=5)
    if _made_by(spec):
        stamp.write_text(_made_by(spec), encoding="utf-8")
    return {"id": tid, "folder": where, "sheet": picture, "manifest": manifest}

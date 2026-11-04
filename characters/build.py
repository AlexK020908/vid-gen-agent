"""A character spec made into a saved person and a portrait sheet to look at, in data/characters/<id>/. A bad spec is
refused with its reasons before Blender starts. A person is only made again when their spec changes."""
from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw

from characters import spec as character_spec
from render import blender_render, humgen


def folder(config, cid: str) -> Path:
    return config.data_dir / "characters" / cid


def sheet(result: dict, out: Path, cell=(360, 640), columns=4) -> Path:
    """The portraits as one picture: each labelled, in rows."""
    out = Path(out)
    shots = result["shots"]
    w, h = cell
    rows = (len(shots) + columns - 1) // columns
    picture = Image.new("RGB", (w * columns, h * rows), (24, 24, 26))
    draw = ImageDraw.Draw(picture)
    for i, shot in enumerate(shots):
        x, y = w * (i % columns), h * (i // columns)
        picture.paste(Image.open(out / shot["file"]).convert("RGB").resize((w, h)), (x, y))
        draw.text((x + 8, y + 8), shot["view"], fill=(255, 255, 255))
    path = out / "sheet.png"
    picture.save(path)
    return path


def build(config, cid: str, say=print) -> dict:
    """Returns the person's folder, the sheet and the person.json."""
    humgen.install(config, say)
    options = humgen.options(config)
    spec = character_spec.load(character_spec.path_for(cid))
    problems = character_spec.check(spec, options)
    if problems:
        raise ValueError(f"{cid}: " + "; ".join(problems))
    where = folder(config, cid)
    say(f"{cid}: making {spec['name']}")
    manifest = blender_render.make_person(config, character_spec.to_person(spec, options), where, say)
    say(f"{cid}: the portraits")
    result = blender_render.portraits(config, where)
    picture = sheet(result, where / "portraits")
    (where / "character.json").write_text(json.dumps(spec, indent=1), encoding="utf-8")
    return {"id": cid, "folder": where, "sheet": picture, "manifest": manifest}

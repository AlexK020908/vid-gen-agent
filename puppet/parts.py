"""Painted parts: a puppet's (head, scarf, hands, cane, brace) or a story's props (a plate, a drill), cut from
one sheet the image provider draws (prompts/parts.md, prompts/props.md), named by Claude (prompts/puppet.md,
`parts` turn), kept in a folder as PNGs with alpha and a puppet.json.

The sheet is drawn on a flat pure-green background, keyed out here. Each separate blob on it is a part;
Claude says which numbered blob is which (the model doesn't always keep the order it was asked for). A part is
cut along its own blob, so a long diagonal thing doesn't bring its neighbours along in its box.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from PIL import Image, ImageChops, ImageDraw, ImageFilter

from puppet import rig

KEY = (0, 255, 0)
SOFT = (40, 110)      # distance from the key color: fully clear below, fully solid above
MIN_AREA = 0.0015     # of the sheet; smaller blobs are speckles
MARGIN = 6
PIVOTS = {"head": (0.5, 1.0), "head_side": (0.5, 1.0), "scarf": (0.5, 0.0), "shirt": (0.5, 0.0), "hand": (0.5, 0.5),
          "cane": (0.5, 0.05), "brace": (0.5, 0.5)}
HEAD_SIDE = ("the same head alone once more, turned three-quarters to the right so the viewer sees more of its right "
             "side, the eyes looking the way it faces, cut off at the bottom of the chin, with no neck")
HERO_PARTS = {  # what the sheet asks for, by part; a channel's YAML `puppet:` overrides any (core/config.py)
    "head": "the head alone: the round white head with whatever it wears, its eyes, eyebrows and calm mouth, "
            "cut off at the bottom of the chin, with no neck and nothing around the neck",
    "head_side": HEAD_SIDE,
    "scarf": "what is worn around the neck alone (a scarf, a collar), as it sits when worn, with nothing inside it",
    "hand": "one hand alone, as the character's hands are drawn, with no arm",
    "cane": "the walking cane alone, upright, its handle at the top",
    "brace": "the knee brace alone, upright, with no leg inside it",
}


@dataclass
class Part:
    name: str
    image: Image.Image            # RGBA, as painted
    pivot: tuple[float, float]    # the point that sits on the joint, in part pixels
    height: float                 # how tall it draws, in H
    slot: str = ""                # where on the rig it goes (rig.SLOTS); "" for a prop
    faces: str = "right"          # the way it's painted facing: left, right, or front (symmetrical)


class Puppet:
    """A set of parts: a character's (with `scale`, their standing height against an adult's) or the props'."""

    def __init__(self, folder: Path, parts: dict[str, Part], scale: float = 1.0) -> None:
        self.folder, self.parts, self.scale = folder, parts, scale

    def __contains__(self, name: str) -> bool:
        return name in self.parts

    def __getitem__(self, name: str) -> Part:
        return self.parts[name]

    def in_slot(self, slot: str) -> Part | None:
        return next((p for p in self.parts.values() if p.slot == slot), None)

    @classmethod
    def load(cls, folder: Path) -> "Puppet":
        spec = json.loads((Path(folder) / "puppet.json").read_text(encoding="utf-8"))
        parts = {}
        for name, p in spec["parts"].items():
            with Image.open(Path(folder) / p["file"]) as img:
                parts[name] = Part(name, img.convert("RGBA"), tuple(p["pivot"]), float(p["height"]), p.get("slot", ""),
                                   p.get("faces", "right"))
        return cls(Path(folder), parts, float(spec.get("scale", 1.0)))


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40] or "x"


def items_text(parts: dict[str, str]) -> str:
    return "\n".join(f"{n}. {text}" for n, text in enumerate(parts.values(), 1))


def key_out(sheet: Image.Image, key: tuple = KEY, soft: tuple = SOFT) -> Image.Image:
    """The sheet with its flat key-colored background made transparent (RGBA), green spill taken off the edges."""
    r, g, b = sheet.convert("RGB").split()
    far = None
    for channel, k in zip((r, g, b), key):
        d = ImageChops.difference(channel, Image.new("L", channel.size, k))
        far = d if far is None else ImageChops.lighter(far, d)
    lo, hi = soft
    alpha = far.point(lambda v: 0 if v <= lo else 255 if v >= hi else round(255 * (v - lo) / (hi - lo)))
    if key == KEY:
        g = ImageChops.darker(g, ImageChops.lighter(r, b))  # no pixel greener than its other channels
    return Image.merge("RGBA", (r, g, b, alpha))


def blobs(alpha: Image.Image, min_area: float = MIN_AREA) -> list[tuple[tuple[int, int, int, int], Image.Image]]:
    """Each separate opaque blob as (its box (x0, y0, x1, y1), its mask (L, sheet size)), biggest first."""
    scale = 4
    full = alpha.point(lambda v: 255 if v > 48 else 0)
    small = full.resize((max(1, alpha.width // scale), max(1, alpha.height // scale)), Image.Resampling.BOX)
    small = small.point(lambda v: 255 if v > 48 else 0)
    least = min_area * small.width * small.height
    found = []
    label = 1
    for y in range(small.height):
        px = small.load()
        for x in range(small.width):
            if px[x, y] != 255:
                continue
            label += 1
            if label > 250:
                raise ValueError("the sheet is full of speckles; it needs a flat background")
            ImageDraw.floodfill(small, (x, y), label)
            px = small.load()
            box = small.point(lambda v, lb=label: 255 if v == lb else 0).getbbox()
            if not box or (box[2] - box[0]) * (box[3] - box[1]) < least:
                continue
            seed = _seed(full, x * scale, y * scale, scale)
            if seed is None:
                continue
            ImageDraw.floodfill(full, seed, label)
            mask = full.point(lambda v, lb=label: 255 if v == lb else 0)
            fb = mask.getbbox()
            found.append(((max(0, fb[0] - MARGIN), max(0, fb[1] - MARGIN), min(alpha.width, fb[2] + MARGIN),
                           min(alpha.height, fb[3] + MARGIN)), mask))
    return sorted(found, key=lambda b: -(b[0][2] - b[0][0]) * (b[0][3] - b[0][1]))


def _seed(full: Image.Image, x: int, y: int, scale: int) -> tuple[int, int] | None:
    px = full.load()
    for dy in range(scale):
        for dx in range(scale):
            if x + dx < full.width and y + dy < full.height and px[x + dx, y + dy] == 255:
                return (x + dx, y + dy)
    return None


def numbered(sheet: Image.Image, boxes: list[tuple], out: Path) -> Path:
    """The sheet with a red numbered box around each blob, for Claude to name them by."""
    img = sheet.convert("RGB")
    draw = ImageDraw.Draw(img)
    for n, (x0, y0, x1, y1) in enumerate(boxes, 1):
        draw.rectangle((x0, y0, x1, y1), outline=(230, 30, 30), width=4)
        draw.rectangle((x0, y0, x0 + 56, y0 + 40), fill=(230, 30, 30))
        draw.text((x0 + 10, y0 + 6), str(n), fill=(255, 255, 255), font_size=28)
    img.save(out, quality=90)
    return out


def build(sheet_path: Path, folder: Path, wanted: list[str], name_parts: Callable[[Path, list[str]], dict],
          heights: dict[str, float] = rig.HEIGHTS, pivots: dict[str, tuple] = PIVOTS, slots: dict[str, str] = rig.SLOTS,
          scale: float = 1.0) -> Puppet:
    """Cuts the sheet into the `wanted` parts and saves them in `folder`. `name_parts(numbered_sheet, wanted)`
    says which blob is which: {name: box number} or {name: {"box": n, "faces": "left" | "right" | "front"}},
    box 0 for one that isn't there."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    with Image.open(sheet_path) as img:
        sheet = img.convert("RGB")
    rgba = key_out(sheet)
    found = blobs(rgba.getchannel("A"))
    if not found:
        raise ValueError("no parts found on the sheet: nothing stands out from its background")
    which = name_parts(numbered(sheet, [box for box, _ in found], folder / "sheet.boxes.jpg"), wanted)
    spec, parts = {}, {}
    for name in wanted:
        answer = which.get(name) or 0
        n = int(answer["box"] if isinstance(answer, dict) else answer)
        faces = str(answer.get("faces") or "right").lower() if isinstance(answer, dict) else "right"
        if not 1 <= n <= len(found):
            continue
        (x0, y0, x1, y1), mask = found[n - 1]
        part = rgba.crop((x0, y0, x1, y1))
        own = mask.crop((x0, y0, x1, y1)).filter(ImageFilter.MaxFilter(5))  # a little room for the soft edge
        part.putalpha(ImageChops.multiply(part.getchannel("A"), own))
        part.save(folder / f"{name}.png")
        fx, fy = pivots.get(name, (0.5, 0.5))
        pivot = (part.width * fx, part.height * fy)
        slot = slots.get(name, "")
        spec[name] = {"file": f"{name}.png", "pivot": [round(pivot[0], 1), round(pivot[1], 1)],
                      "height": heights.get(name, 0.1), "slot": slot, "faces": faces, "box": [x0, y0, x1, y1]}
        parts[name] = Part(name, part, pivot, heights.get(name, 0.1), slot, faces)
    missing = [n for n in wanted if n not in parts]
    if missing:
        raise ValueError(f"the sheet has no usable {', '.join(missing)}; it needs drawing again")
    (folder / "puppet.json").write_text(json.dumps({"sheet": str(sheet_path), "scale": scale, "parts": spec},
                                                   indent=1), encoding="utf-8")
    return Puppet(folder, parts, scale)


def add(folder: Path, made: Puppet) -> Puppet:
    """Adds `made`'s parts (cut into another folder) to the puppet in `folder`, keeping what it has."""
    folder = Path(folder)
    spec = json.loads((folder / "puppet.json").read_text(encoding="utf-8"))
    for name, part in made.parts.items():
        part.image.save(folder / f"{name}.png")
        spec["parts"][name] = {"file": f"{name}.png", "pivot": [round(part.pivot[0], 1), round(part.pivot[1], 1)],
                               "height": part.height, "slot": part.slot, "faces": part.faces}
    (folder / "puppet.json").write_text(json.dumps(spec, indent=1), encoding="utf-8")
    return Puppet.load(folder)

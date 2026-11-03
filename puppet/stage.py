"""A place as a stage: its picture, where the floor runs and how tall a person stands along it, the named
spots people stand at, the things in the foreground a person can be behind, and where the light is. Claude
maps a picture once (prompts/puppet.md, `stage` turn) reading a labelled grid drawn over it; the map is kept
beside the picture as JSON.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw


@dataclass
class Stage:
    picture: Path
    size: tuple[int, int]
    floor: list[tuple[float, float, float]]   # (x, y, standing height) in pixels, along the main path
    spots: dict[str, tuple[float, float]]     # name -> where the feet go
    light: dict                               # {"x", "y", "warm"} in pixels
    occluders: list[dict] = field(default_factory=list)  # {"name", "polygon": [(x, y)], "base_y"}: in front of
                                                          # anything whose feet are above base_y

    def spot(self, name: str) -> tuple[float, float]:
        try:
            return self.spots[name]
        except KeyError:
            have = ", ".join(sorted(self.spots)) or "none"
            raise KeyError(f"the stage has no spot {name!r} (it has {have})") from None

    def height_at(self, x: float, y: float) -> float:
        """A standing adult's height at a point. Perspective makes it grow with how far down the picture the feet
        are, not how far across, so it's read along y between the nearest floor point above the spot and the
        nearest below it (a spot off to the side of the floor points takes the size of the depth it's at), or past
        the ends along the line through the nearest two. Nearest keeps a point on another level (a stair) to the
        spots beside it. Kept between half the smallest height and one and a half the largest."""
        def nearest(pts):
            return sorted(pts, key=lambda p: math.hypot(p[0] - x, p[1] - y))
        above, below = nearest([p for p in self.floor if p[1] < y]), nearest([p for p in self.floor if p[1] >= y])
        if above and below:
            a, b = above[0], below[0]
        else:
            ends = above or below
            a = ends[0]
            b = next((p for p in ends[1:] if p[1] != a[1]), None)
            if b is None:
                return a[2]
        height = a[2] + (b[2] - a[2]) * (y - a[1]) / (b[1] - a[1])
        heights = [p[2] for p in self.floor]
        return min(max(height, min(heights) / 2), max(heights) * 1.5)

    def save(self, path: Path) -> None:
        data = {"picture": str(self.picture), "size": list(self.size), "floor": [list(p) for p in self.floor],
                "spots": {k: list(v) for k, v in self.spots.items()}, "light": self.light,
                "occluders": [{**o, "polygon": [list(p) for p in o["polygon"]]} for o in self.occluders]}
        Path(path).write_text(json.dumps(data, indent=1), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "Stage":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(Path(data["picture"]), tuple(data["size"]), [tuple(p) for p in data["floor"]],
                   {k: tuple(v) for k, v in data["spots"].items()}, data["light"],
                   [{**o, "polygon": [tuple(p) for p in o["polygon"]]} for o in data.get("occluders", [])])

    @classmethod
    def from_percent(cls, picture: Path, data: dict) -> "Stage":
        """From Claude's answer: x, y and height as percentages of the picture."""
        with Image.open(picture) as img:
            w, h = img.size
        floor = [(p["x"] * w / 100, p["y"] * h / 100, p["height"] * h / 100) for p in data["floor"]]
        spots = {s["name"].strip().lower().replace(" ", "_"): (s["x"] * w / 100, s["y"] * h / 100)
                 for s in data["spots"]}
        light = {"x": data["light"]["x"] * w / 100, "y": data["light"]["y"] * h / 100,
                 "warm": bool(data["light"]["warm"])}
        occluders = [{"name": o["name"].strip().lower().replace(" ", "_"),
                      "polygon": [(p["x"] * w / 100, p["y"] * h / 100) for p in o["polygon"]],
                      "base_y": o["base_y"] * h / 100} for o in data.get("occluders") or []]
        return cls(Path(picture), (w, h), floor, spots, light, occluders)


def grid(picture: Path, out: Path, step: int = 10) -> Path:
    """The picture with a labelled grid every `step` percent, for Claude to read positions off."""
    with Image.open(picture) as img:
        img = img.convert("RGB")
    draw = ImageDraw.Draw(img)
    w, h = img.size
    for p in range(step, 100, step):
        x, y = round(w * p / 100), round(h * p / 100)
        draw.line((x, 0, x, h), fill=(255, 40, 40), width=2)
        draw.line((0, y, w, y), fill=(255, 40, 40), width=2)
        for xy in ((x + 4, 4), (x + 4, h - 34)):
            draw.text(xy, str(p), fill=(255, 40, 40), font_size=28, stroke_width=2, stroke_fill=(255, 255, 255))
        for xy in ((4, y + 4), (w - 44, y + 4)):
            draw.text(xy, str(p), fill=(255, 40, 40), font_size=28, stroke_width=2, stroke_fill=(255, 255, 255))
    img.save(out, quality=90)
    return out


def overlay(stage: Stage, out: Path) -> Path:
    """The stage with its map drawn on, to check it by eye: the floor line, a figure's height at each point,
    the spots, the occluders and the light."""
    with Image.open(stage.picture) as img:
        img = img.convert("RGB")
    draw = ImageDraw.Draw(img)
    for o in stage.occluders:
        draw.polygon([tuple(p) for p in o["polygon"]], outline=(255, 80, 255), width=4)
        draw.text((o["polygon"][0][0] + 8, o["polygon"][0][1] + 8), o["name"], fill=(255, 80, 255), font_size=26,
                  stroke_width=2, stroke_fill=(0, 0, 0))
    pts = [(x, y) for x, y, _ in stage.floor]
    if len(pts) > 1:
        draw.line(pts, fill=(40, 200, 255), width=4)
    for x, y, height in stage.floor:
        draw.line((x, y, x, y - height), fill=(40, 200, 255), width=3)
        draw.ellipse((x - 6, y - 6, x + 6, y + 6), fill=(40, 200, 255))
    for name, (x, y) in stage.spots.items():
        draw.ellipse((x - 8, y - 8, x + 8, y + 8), fill=(255, 200, 0), outline=(0, 0, 0))
        draw.text((x + 10, y - 30), name, fill=(255, 200, 0), font_size=26, stroke_width=2, stroke_fill=(0, 0, 0))
    lx, ly = stage.light["x"], stage.light["y"]
    draw.ellipse((lx - 14, ly - 14, lx + 14, ly + 14), outline=(255, 255, 0), width=4)
    img.save(out, quality=90)
    return out

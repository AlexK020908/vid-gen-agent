"""The story's props: painted once on a sheet (prompts/props.md), cut like a puppet's parts, then placed in a
place (puppet/state.py) or attached to a figure's joint (a drill in a hand, a towel on a knee).

Each prop has how tall it draws against a standing adult (H), and where its pivot is: the point that stands on
the floor when placed, or sits on the joint when held. The specs here are the ones the demo needs; the
stager will write a video's own list in the same shape.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from puppet import parts

SPECS = {
    "plate": {"draw": "a flat rectangular sheet of dull grey steel, upright and seen face on, as tall as a door, "
                      "with a row of drilled bolt holes down each side edge", "height": 1.12, "pivot": (0.5, 1.0)},
    "drill": {"draw": "a cordless power drill with its battery, seen from the side, its bit pointing to the right",
              "height": 0.17, "pivot": (0.35, 0.72)},
    "rifle": {"draw": "a rifle with a long suppressor on its barrel, seen from the side, pointing to the right",
              "height": 0.5, "pivot": (0.4, 0.62)},
    "towel": {"draw": "a folded white towel, a small neat rectangle", "height": 0.1, "pivot": (0.5, 0.5)},
    "wrench": {"draw": "a socket wrench, lying diagonally", "height": 0.18, "pivot": (0.5, 0.5)},
    "flashlight": {"draw": "a small black flashlight, seen from the side, pointing to the right", "height": 0.06,
                   "pivot": (0.5, 0.5)},
}


def items_text(names: list[str], specs: dict = SPECS) -> str:
    return parts.items_text({n: specs[n]["draw"] for n in names})


def build(sheet: Path, folder: Path, names: list[str], name_parts: Callable[[Path, list[str]], dict[str, int]],
          specs: dict = SPECS) -> parts.Puppet:
    return parts.build(sheet, folder, names, name_parts, heights={n: specs[n]["height"] for n in names},
                       pivots={n: tuple(specs[n]["pivot"]) for n in names}, slots={})


PIVOT_OF = {"bottom": (0.5, 1.0), "center": (0.5, 0.5), "grip": (0.4, 0.65)}  # where a prop stands or is held


def load(folder: Path) -> parts.Puppet:
    return parts.Puppet.load(folder)


def load_library(folder: Path) -> parts.Puppet:
    """The channel's props so far; empty when none have been painted."""
    folder = Path(folder)
    if (folder / "puppet.json").exists():
        return parts.Puppet.load(folder)
    return parts.Puppet(folder, {})


def add_to_library(folder: Path, made: parts.Puppet) -> parts.Puppet:
    """Copies newly cut props into the library folder and its puppet.json, keeping the ones already there."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    spec = {"parts": {}}
    if (folder / "puppet.json").exists():
        spec = json.loads((folder / "puppet.json").read_text(encoding="utf-8"))
    for name, part in made.parts.items():
        part.image.save(folder / f"{name}.png")
        spec["parts"][name] = {"file": f"{name}.png", "pivot": [round(part.pivot[0], 1), round(part.pivot[1], 1)],
                               "height": part.height, "slot": part.slot, "faces": part.faces}
    (folder / "puppet.json").write_text(json.dumps(spec, indent=1), encoding="utf-8")
    return parts.Puppet.load(folder)

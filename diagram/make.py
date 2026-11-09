"""A spec to a finished systems short: checked, simulated, its sound mixed, drawn by Remotion's `DiagramShort`."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Callable

from diagram import layout, sim, sound, verify
from diagram import spec as dspec

DRAWN = ("duration", "beat", "geometry", "title", "subtitles", "captions", "stats", "nodes", "edges", "dots",
         "flashes", "badges", "code", "end", "loop")


def check(spec) -> list[str]:
    """Everything wrong with a spec, from its fields to whether it fits on the frame with the queues its traffic
    builds. [] means it can be drawn."""
    found = dspec.problems(spec)
    if found:
        return found
    tl = sim.timeline(spec)
    phases = sim._timed(dspec.resolved(spec), tl["grid"])
    queues = {f["phase"] - 1: f["most_waiting"] for f in tl["facts"]}
    return layout.problems(spec, phases, queues) + _numbers(spec, tl)


def _numbers(spec: dict, tl: dict) -> list[str]:
    """A number the end card's claim or note gives in its stat's unit has to be one the pill really showed."""
    end, card = spec.get("end") or {}, tl.get("end")
    stat = next((s for s in spec.get("stats") or [] if s.get("name") == end.get("stat")), None)
    if not card or not stat or not stat.get("unit"):
        return []
    shown = {card["before"]["text"].split(" ")[0], card["after"]["text"].split(" ")[0]}
    out = []
    unit = re.escape(str(stat["unit"]))
    for field in ("claim", "note"):
        for n in re.findall(rf"(\d[\d,.]*)\s*{unit}\b", str(end.get(field) or "")):
            if n not in shown:
                out.append(f"the end card's {field} says {n} {stat['unit']}, but the {stat['name']} pill goes from "
                           f"{card['before']['text']} to {card['after']['text']}")
    return out


def props(timeline: dict, audio: str | None) -> dict:
    return {**{k: timeline[k] for k in DRAWN}, "audio": audio}


def render(spec: dict, out: Path, progress: Callable[[int, int], None] | None = None, music: bool = True) -> dict:
    """Renders `spec` to `out` (an MP4), with its timeline written beside it as <name>.timeline.json. Raises
    ValueError with the problems when the spec doesn't pass its checks."""
    from render import remotion_render
    found = check(spec)
    if found:
        raise ValueError("; ".join(found))
    out = Path(out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    tl = sim.timeline(spec)
    wav = sound.mix(tl, out.with_suffix(".sound.wav"), music=music)
    out.with_suffix(".timeline.json").write_text(json.dumps(tl, indent=1, ensure_ascii=False), encoding="utf-8")
    remotion_render.render_diagram(props(tl, "sound.wav"), {"sound.wav": str(wav)}, out, progress)
    # measured from the MP4 itself: every sound and every request landing is a code line running, on its frame
    off = verify.problems(out, wav, tl)
    if off:
        raise RuntimeError("the render is out of step with its timeline: " + "; ".join(off))
    return tl

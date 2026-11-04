"""Moving a machine short onto a new read: a warp from the times it was written to (another narrator's read) to the
new one's, applied to its segment timelines and its overlay props.

The picture follows the voice. Each line's start in the old read maps to where the new read reaches it, and between
line starts the picture is stretched evenly. It's never sped up: where the old read left a beat with no words (the
nail's taps), the new one keeps at least that long, so the picture only ever slows.
"""
from __future__ import annotations

import copy
import json


class Warp:
    """A piecewise straight map from old times to new, through `knots` [(old, new)] rising in both. Before the
    first knot and after the last, times move by that knot's shift."""

    def __init__(self, knots: list[tuple[float, float]]):
        self.knots = sorted(knots)
        for (a0, b0), (a1, b1) in zip(self.knots, self.knots[1:]):
            if a1 <= a0 or b1 < b0:
                raise ValueError(f"warp knots must rise: {(a0, b0)} then {(a1, b1)}")

    def __call__(self, t: float) -> float:
        k = self.knots
        if t <= k[0][0]:
            return t + k[0][1] - k[0][0]
        for (a0, b0), (a1, b1) in zip(k, k[1:]):
            if t <= a1:
                return b0 + (t - a0) * (b1 - b0) / (a1 - a0)
        return t + k[-1][1] - k[-1][0]

    def setpts(self) -> str:
        """The warp as an ffmpeg setpts expression, to slow a reference video to the new read (the side by side)."""
        k = self.knots
        expr = f"(T+{k[-1][1] - k[-1][0]:.4f})"
        for (a0, b0), (a1, b1) in reversed(list(zip(k, k[1:]))):
            expr = f"if(lt(T,{a1:.4f}),{b0:.4f}+(T-{a0:.4f})*{(b1 - b0) / (a1 - a0):.5f},{expr})"
        expr = f"if(lt(T,{k[0][0]:.4f}),T+{k[0][1] - k[0][0]:.4f},{expr})"
        return f"({expr})/TB"


def layout(old: list[dict], new: list[dict], pauses: list[float]) -> tuple[list[float], Warp]:
    """`old`: each line's {start, end} in the old read (end: its last word's end). `new`: each line's {duration} in
    the new read, one for one. `pauses`: the seconds after each new line. Returns (where each new line starts, the
    warp from old times to new). The first line starts where the old one did."""
    starts, knots = [], []
    t = old[0]["start"]
    for i, (was, now) in enumerate(zip(old, new)):
        starts.append(t)
        knots.append((was["start"], t))
        if i + 1 < len(old):
            t = max(t + now["duration"] + pauses[i], t + old[i + 1]["start"] - was["start"])
    last = len(old) - 1
    knots.append((old[last]["end"], max(starts[last] + new[last]["duration"] + pauses[last],
                                        starts[last] + old[last]["end"] - old[last]["start"])))
    return starts, Warp(knots)


def _keys(pairs, w: Warp):
    """[[t, value]] or [{t, ...}] with their times moved."""
    return [{**k, "t": round(w(k["t"]), 4)} if isinstance(k, dict) else [round(w(k[0]), 4), *k[1:]] for k in pairs]


def timeline(tl: dict, w: Warp) -> dict:
    """A segment's timeline (blender/shots.py) with every time moved: its span, keys, camera, cuts, events and its
    effects' times and keyed values. Durations (an effect's `life`) stay as they are."""
    tl = json.loads(json.dumps(tl))
    tl["from"], tl["to"] = round(w(tl["from"]), 4), round(w(tl["to"]), 4)
    for group in ("keys", "camera", "events"):
        tl[group] = _keys(tl.get(group) or [], w)
    for cut in tl.get("cuts") or []:
        cut["from"], cut["to"] = round(w(cut["from"]), 4), round(w(cut["to"]), 4)
    for e in tl.get("effects") or []:
        for field in ("from", "to", "t"):
            if field in e:
                e[field] = round(w(e[field]), 4)
        for field in ("keys", "colors"):
            if field in e:
                e[field] = _keys(e[field], w)
    return tl


def spans(items: list[dict], w: Warp) -> list[dict]:
    """Overlay items ({from, to, ...}: screens, labels, tags, sounds) with their times moved, and a tag's steps."""
    out = []
    for item in items:
        item = copy.deepcopy(item)
        for field in ("from", "to"):
            if field in item:
                item[field] = round(w(item[field]), 4)
        if "steps" in item:
            item["steps"] = [[round(w(t), 4), v] for t, v in item["steps"]]
        out.append(item)
    return out

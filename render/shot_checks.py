"""Checks on a machine short's shots: its labels against their anchor tracks, before Remotion draws them, and its
camera moves (SHORTS.md, "Shots").

A label points at a part the viewer must see. Remotion hides a label while its anchor is hidden behind another
part, so an anchor hidden for much of the label's time makes the label blink or vanish; one outside the safe area
puts the label's dot under the caption box or the platform's buttons. Phase 23 found the first kind: the AIR label
on a ball the ram's front edge covered for the shot's last half second. A hide shorter than BLINK frames, in the
picture, is ridden through (CalloutLabel in render/remotion/src/shorts/Overlays.tsx), so it isn't counted.
"""
from __future__ import annotations

import math

SAFE = {"top": 0.08, "right": 0.14, "bottom": 0.22, "left": 0.04}   # as render/remotion/src/shorts/types.ts
SEEN_ENOUGH = 0.9    # of a label's frames its anchor must be seen in
INSIDE_ENOUGH = 0.9  # of those its anchor must be inside the safe area in
BLINK = 18           # as Overlays.tsx: 0.6 s, since a picture that follows a slower voice hides things for longer


def showing(points: list, i: int) -> bool:
    """Whether a label on this track shows at index i: its anchor seen, or hidden only for a moment in the picture."""
    x, y, seen = points[i]
    if seen:
        return True
    if not (0 <= x <= 1 and 0 <= y <= 1):
        return False
    a = b = i
    while a > 0 and not points[a - 1][2] and i - a < BLINK:
        a -= 1
    while b < len(points) - 1 and not points[b + 1][2] and b - i < BLINK:
        b += 1
    return b - a + 1 < BLINK and a > 0 and b < len(points) - 1


def label_problems(labels: list[dict], tracks: dict, fps: int) -> list[str]:
    """`labels`: [{label, anchor, from, to}] in seconds. `tracks`: anchor -> {first, points: [[x, y, seen]]}, one
    point a frame from frame `first`. Returns each problem in words, or [] when every label can be seen."""
    problems = []
    for lab in labels:
        name = f'{lab["label"]} ({lab["from"]:.2f}-{lab["to"]:.2f} s)'
        track = tracks.get(lab["anchor"])
        if not track:
            problems.append(f'{name}: no track for its anchor {lab["anchor"]}')
            continue
        frames = range(round(lab["from"] * fps), round(lab["to"] * fps))
        index = [f - track["first"] for f in frames if 0 <= f - track["first"] < len(track["points"])]
        points = [[*track["points"][i], showing(track["points"], i)] for i in index]
        if len(points) < len(frames):
            problems.append(f"{name}: its anchor's track covers only {len(points)} of its {len(frames)} frames")
        if not points:
            continue
        seen = [(x, y) for x, y, _seen, shown in points if shown]
        if len(seen) < SEEN_ENOUGH * len(points):
            problems.append(f"{name}: its anchor is hidden in {len(points) - len(seen)} of {len(points)} frames")
        inside = [1 for x, y in seen
                  if SAFE["left"] <= x <= 1 - SAFE["right"] and SAFE["top"] <= y <= 1 - SAFE["bottom"]]
        if seen and len(inside) < INSIDE_ENOUGH * len(seen):
            problems.append(f"{name}: its anchor is outside the safe area in {len(seen) - len(inside)} of "
                            f"{len(seen)} frames")
    return problems


MAX_ZOOM = 2.5     # e-folds of framing a second (×12 a second): faster read as a jolt to the owner
MAX_TURN = 120     # degrees a second of the camera's swing about its target


def camera_problems(tl: dict) -> list[str]:
    """A segment's camera moves (blender/shots.py) that zoom or swing faster than a viewer follows. A move over in
    under three frames is a cut and is left alone, and so are keys placed by `at` and `aim`, and a move whose key
    says `fast` (a deliberate dive, into a flash or a port)."""
    keys = sorted(tl.get("camera") or [], key=lambda k: k["t"])
    problems = []
    for a, b in zip(keys, keys[1:]):
        dt = b["t"] - a["t"]
        if dt < 0.1 or "frame" not in a or "frame" not in b or b.get("fast"):
            continue
        zoom = abs(math.log(b["frame"] / a["frame"])) / dt
        turn = (abs(b.get("az", 0) - a.get("az", 0)) + abs(b.get("el", 5) - a.get("el", 5))) / dt
        if zoom > MAX_ZOOM:
            problems.append(f'{a["t"]:.2f}-{b["t"]:.2f} s: zooms ×{b["frame"] / a["frame"]:.2g} in {dt:.2f} s; '
                            f'give it {abs(math.log(b["frame"] / a["frame"])) / MAX_ZOOM:.2f} s or more')
        if turn > MAX_TURN:
            problems.append(f'{a["t"]:.2f}-{b["t"]:.2f} s: swings {turn * dt:.0f}° in {dt:.2f} s; give it '
                            f'{turn * dt / MAX_TURN:.2f} s or more')
    return problems

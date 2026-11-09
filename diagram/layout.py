"""Where everything goes on a systems short's 1080x1920 frame, and whether it fits.

Code places everything: the agent only picks the layout and the nodes' order (spec.LAYOUTS). Text is measured with the
same fonts Remotion draws with, so "it fits" here means it fits there.

The frame, top to bottom: the title, the subtitle and the stat pills, then the diagram, all across the full width less
4% a side, since the platforms' buttons only start a little past halfway down (BUTTONS_FROM: Reels' heart is at about
56% of the frame); then the caption and the code panel, kept out of the right 14% and the bottom 22%, which Reels' and
Shorts' own buttons and caption cover (render/remotion/src/shorts/types.ts SAFE).
"""
from __future__ import annotations

import math
from functools import lru_cache
from pathlib import Path

from PIL import ImageFont

from diagram import spec as dspec

W, H = 1080, 1920
LEFT, RIGHT = 43, 929              # the diagram, caption and code panel: in from the left 4%, out of the right 14%
HEAD_LEFT, HEAD_RIGHT = 43, 1037   # the title, subtitle and pills
TOP, BOTTOM = 154, 1498            # out of the top 8% and the bottom 22%
BUTTONS_FROM = 1037                # the platforms' buttons down the right side start below this (54%)
FONTS = Path(__file__).resolve().parent.parent / "render" / "remotion" / "src" / "shorts" / "fonts"

TITLE_TOP, TITLE_MOST, TITLE_LEAST = 172, 84, 52
SUBTITLE_SIZE = 30
PILL_H, PILL_TEXT, PILL_VALUE, PILL_PAD, PILL_GAP = 64, 22, 36, 26, 18
ICON = 108
RING = ICON * 0.82                 # the faint ring round a node that serves requests: a decoration, left out of footprints
LABEL = 32
COUNTER = 48
QUEUE_DOT, QUEUE_STEP, QUEUE_DOTS = 6, 14, 4   # waiting requests stack above a node, four dots then "+n" beside them
QUEUE_MORE = 30
BADGE, BADGE_PAD = 26, 14          # a node's badge (HIT, MISS, 180 ms, LOST): its letters, and the room round them
BADGE_H = round(BADGE * 1.25 + 2 * 5)
CAPTION_MOST, CAPTION_LEAST = 52, 40
CODE_SIZE, CODE_LINE, CODE_PAD = 33, 50, 22
CODE_BOTTOM = 1478
GAP = 8                            # the least room between two nodes' footprints
ROW_GAP_MOST, COL_GAP_MOST = 250, 330
END_BIG, END_CLAIM, END_NOTE = 92, 46, 28


@lru_cache(maxsize=64)
def _font(kind: str, size: int, weight: int) -> ImageFont.FreeTypeFont:
    if kind == "mono":
        f = ImageFont.truetype(str(FONTS / "JetBrainsMono.ttf"), size)
        f.set_variation_by_axes([min(800, weight)])
    else:
        f = ImageFont.truetype(str(FONTS / "Inter.ttf"), size)
        f.set_variation_by_axes([min(32, max(14, size)), weight])
    return f


def width(text: str, size: float, weight: int = 400, kind: str = "sans", spacing: float = 0.0) -> float:
    """How wide `text` is drawn, in px of the 1080-wide frame."""
    if not text:
        return 0.0
    f = _font(kind, int(round(size)), weight)
    return f.getlength(text) + spacing * max(0, len(text) - 1)


def lines(text: str, size: float, most: float, weight: int = 800) -> list[str] | None:
    """`text` on one line, or two balanced ones, each at most `most` wide; None if two won't do."""
    if width(text, size, weight) <= most:
        return [text]
    ws = text.split()
    best = None
    for i in range(1, len(ws)):
        a, b = " ".join(ws[:i]), " ".join(ws[i:])
        wide = max(width(a, size, weight), width(b, size, weight))
        if wide <= most and (best is None or wide < best[0]):
            best = (wide, [a, b])
    return best[1] if best else None


def fit(text: str, most: float, high: int, low: int, weight: int, kind: str = "sans", spacing: float = 0.0) -> int | None:
    """The biggest size from `high` down to `low` at which `text` fits in `most` px on one line."""
    for size in range(high, low - 1, -2):
        if width(text, size, weight, kind, spacing) <= most:
            return size
    return None


def caption_size(text: str) -> tuple[int, list[str]] | None:
    for size in range(CAPTION_MOST, CAPTION_LEAST - 1, -2):
        got = lines(text, size, RIGHT - LEFT)
        if got:
            return size, got
    return None


def frame(spec: dict, phases: list[dict]) -> dict:
    """The fixed parts of the frame: the title's size, where the pills, diagram box, caption and code panel go."""
    title = str(spec.get("title") or "")
    title_size = fit(title, HEAD_RIGHT - HEAD_LEFT, TITLE_MOST, TITLE_LEAST, 900) or TITLE_LEAST
    sub_top = TITLE_TOP + title_size * 1.15 + 12
    pills_top = sub_top + SUBTITLE_SIZE * 1.3 + 20
    stats = spec.get("stats") or []
    code_lines = max([len((p["code"] or {}).get("lines") or []) for p in phases] or [0])
    code_top = CODE_BOTTOM - (code_lines * CODE_LINE + 2 * CODE_PAD) if code_lines else None
    cap_h = int(CAPTION_MOST * 1.15 * 2)
    cap_top = (code_top - 28 - cap_h) if code_top else (BOTTOM - 40 - cap_h)
    box_top = pills_top + (PILL_H + 40 if stats else 0)
    box_bottom = cap_top - 24
    right = HEAD_RIGHT if box_bottom <= BUTTONS_FROM else RIGHT
    return {"title_size": title_size, "title_top": TITLE_TOP, "subtitle_top": round(sub_top),
            "pills_top": round(pills_top), "box": [HEAD_LEFT, round(box_top), right, round(box_bottom)],
            "caption_top": round(cap_top), "caption_h": cap_h, "code_top": round(code_top) if code_top else None,
            "code_lines": code_lines}


def counted(spec: dict) -> set[str]:
    """The nodes that show a counter: where requests end (a stream's `to`, or the cache a cache_hit route stops at),
    unless the node says count: false."""
    out = set()
    for p in spec.get("phases") or []:
        for s in (p or {}).get("traffic") or []:
            if not isinstance(s, dict):
                continue
            out |= set(dspec.stream_targets(s))
            if dspec.route_of(s) == "cache_hit" and s.get("via"):
                out.add(str(dspec._list(s["via"])[-1]))
    return {n["id"] for n in spec.get("nodes") or [] if n.get("id") in out and n.get("count", True) is not False}


def badged(spec: dict) -> set[str]:
    """The nodes that get a badge under their label (diagram/sim.py): a cache a cache_hit route asks, a node that ever
    fails or dies (LOST), and with `ms` on the nodes, where requests end and where answers come back to."""
    timed = any(n.get("ms") for n in spec.get("nodes") or [])
    out = set()
    for p in spec.get("phases") or []:
        p = p or {}
        for n, st in (p.get("state") or {}).items():
            if st in ("failing", "dead"):
                out.add(n)
        for s in p.get("traffic") or []:
            if not isinstance(s, dict):
                continue
            via = dspec._list(s.get("via"))
            if dspec.route_of(s) == "cache_hit" and via:
                out.add(str(via[-1]))
            if timed:
                out |= {t for t in dspec.stream_targets(s) if _ms(spec, t)}
                if s.get("back"):
                    out.add(str(s.get("from")))
    return out


def _ms(spec: dict, node: str) -> float:
    return float(next((n.get("ms") or 0 for n in spec.get("nodes") or [] if n.get("id") == node), 0))


def badge_sides(spec: dict, phase: dict) -> dict[str, str]:
    """Where each shown node's badge goes in this phase: under its label, or beside its icon (under its counter) when
    other nodes stand above or below it in its column, where there's no room under the label."""
    shown = [n["id"] for n in spec.get("nodes") or [] if n["id"] in phase["show"]]
    if spec.get("layout") not in ("pipeline", "fan_out", "fan_in"):
        return {n: "below" for n in shown}
    depth = _depths(shown, phase["edges"])
    return {n: "right" if sum(1 for m in shown if depth[m] == depth[n]) > 1 else "below" for n in shown}


def footprint(node: dict, counter: bool, queue: int = 0, badge: bool | str = False) -> tuple[float, float, float, float]:
    """How far a node's drawing reaches from its icon's centre: left, top, right, bottom (all positive). `queue` is the
    most requests ever seen waiting there in the phase, which stack above it; `badge`, where it gets one ("below" its
    label, or "right" of its icon), if it does."""
    label_w = width(str(node.get("label") or ""), LABEL, 700)
    half = ICON / 2
    left = max(half, label_w / 2)
    right = max(half, label_w / 2, half + 12 + (width("888", COUNTER, 800) if counter else 0))
    top = half + (12 + min(queue, QUEUE_DOTS) * QUEUE_STEP if queue else 0)
    if queue > QUEUE_DOTS:
        right = max(right, 14 + width(f"+{queue}", QUEUE_MORE, 800))
    bottom = half + 10 + LABEL * 1.25
    wide = width("1,000 ms", BADGE, 800, "mono") + 2 * BADGE_PAD
    if badge == "right":
        right = max(right, half + 12 + wide)
    elif badge:
        left, right = max(left, wide / 2), max(right, wide / 2)
        bottom += 8 + BADGE_H
    return left, top, right, bottom


def place(spec: dict, phase: dict, box: list[float], queues: dict[str, int] | None = None) -> dict[str, tuple[float, float]]:
    """Each shown node's icon centre in this phase. `queues`: the most requests seen waiting at each node in it."""
    nodes = {n["id"]: n for n in spec.get("nodes") or []}
    shown = [n["id"] for n in spec.get("nodes") or [] if n["id"] in phase["show"]]
    if not shown:
        return {}
    count, marked, sides = counted(spec), badged(spec), badge_sides(spec, phase)
    feet = {n: footprint(nodes[n], n in count, (queues or {}).get(n, 0), sides[n] if n in marked else False)
            for n in shown}
    x0, y0, x1, y1 = box
    layout = spec.get("layout")
    if layout in ("hub", "ring"):
        return _round(shown, feet, box, hub=layout == "hub")
    if layout == "grid":
        return _grid(shown, feet, box)
    depth = _depths(shown, phase["edges"])
    groups: dict[int, list[str]] = {}
    for n in shown:
        groups.setdefault(depth[n], []).append(n)
    tiers = [groups[d] for d in sorted(groups)]
    if layout == "layers":
        return _tiers(tiers, feet, box, across=False)
    return _tiers(tiers, feet, box, across=True)


def _depths(shown: list[str], edges: list) -> dict[str, int]:
    """How far each node is from where traffic starts, following the edges as written, a to b."""
    into = {n: [] for n in shown}
    for a, b in edges:
        if a in into and b in into:
            into[b].append(a)
    depth: dict[str, int] = {}

    def d(n: str, seen: frozenset) -> int:
        if n in depth:
            return depth[n]
        ups = [u for u in into[n] if u not in seen]
        depth[n] = 0 if not ups else 1 + max(d(u, seen | {n}) for u in ups)
        return depth[n]

    for n in shown:
        d(n, frozenset())
    return depth


def _spread(count: int, lo: float, hi: float, most_gap: float) -> list[float]:
    if count == 1:
        return [(lo + hi) / 2]
    gap = min(most_gap, (hi - lo) / (count - 1))
    mid = (lo + hi) / 2
    return [mid + (i - (count - 1) / 2) * gap for i in range(count)]


def _tiers(tiers: list[list[str]], feet: dict, box: list[float], across: bool) -> dict[str, tuple[float, float]]:
    x0, y0, x1, y1 = box
    top = max(f[1] for f in feet.values())
    bottom = max(f[3] for f in feet.values())
    left = max(f[0] for f in feet.values())
    right = max(f[2] for f in feet.values())
    out = {}
    if across:   # tiers are columns, left to right
        xs = _spread(len(tiers), x0 + max(feet[n][0] for n in tiers[0]), x1 - max(feet[n][2] for n in tiers[-1]),
                     COL_GAP_MOST * 2 if len(tiers) == 2 else 10_000)
        for x, tier in zip(xs, tiers):
            for n, y in zip(tier, _spread(len(tier), y0 + top, y1 - bottom, ROW_GAP_MOST)):
                out[n] = (x, y)
    else:        # tiers are rows, top to bottom
        ys = _spread(len(tiers), y0 + top, y1 - bottom, ROW_GAP_MOST)
        for y, tier in zip(ys, tiers):
            for n, x in zip(tier, _spread(len(tier), x0 + left, x1 - right, COL_GAP_MOST)):
                out[n] = (x, y)
    return {n: (round(x, 1), round(y, 1)) for n, (x, y) in out.items()}


def _round(shown: list[str], feet: dict, box: list[float], hub: bool) -> dict[str, tuple[float, float]]:
    x0, y0, x1, y1 = box
    top = max(f[1] for f in feet.values())
    bottom = max(f[3] for f in feet.values())
    side = max(max(f[0], f[2]) for f in feet.values())
    cx, cy = (x0 + x1) / 2, (y0 + top + y1 - bottom) / 2
    r = max(60.0, min((x1 - x0) / 2 - side, (y1 - bottom - (y0 + top)) / 2))
    around = shown[1:] if hub else shown
    out = {shown[0]: (cx, cy)} if hub else {}
    for i, n in enumerate(around):
        a = -math.pi / 2 + 2 * math.pi * i / max(1, len(around))
        out[n] = (cx + r * math.cos(a), cy + r * math.sin(a))
    return {n: (round(x, 1), round(y, 1)) for n, (x, y) in out.items()}


def _grid(shown: list[str], feet: dict, box: list[float]) -> dict[str, tuple[float, float]]:
    x0, y0, x1, y1 = box
    cols = min(3, math.ceil(math.sqrt(len(shown))))
    rows = math.ceil(len(shown) / cols)
    top = max(f[1] for f in feet.values())
    bottom = max(f[3] for f in feet.values())
    left = max(f[0] for f in feet.values())
    right = max(f[2] for f in feet.values())
    xs = _spread(cols, x0 + left, x1 - right, COL_GAP_MOST)
    ys = _spread(rows, y0 + top, y1 - bottom, ROW_GAP_MOST)
    return {n: (round(xs[i % cols], 1), round(ys[i // cols], 1)) for i, n in enumerate(shown)}


def problems(spec: dict, phases: list[dict] | None = None, queues: dict[int, dict[str, int]] | None = None) -> list[str]:
    """Whether everything fits on the frame and nothing overlaps, phase by phase. Run after spec.problems passes;
    `queues` (from the simulation) is the most requests waiting at each node in each phase, stacked above it."""
    phases = phases if phases is not None else dspec.resolved(spec)
    queues = queues or {}
    out = []
    title = str(spec.get("title") or "")
    if fit(title, HEAD_RIGHT - HEAD_LEFT, TITLE_MOST, TITLE_LEAST, 900) is None:
        out.append(f"the title doesn't fit across the frame even at {TITLE_LEAST}px; shorten it")
    fr = frame(spec, phases)
    for p in phases:
        sub = str(p["subtitle"] or "")
        if sub and fit(sub, HEAD_RIGHT - HEAD_LEFT, SUBTITLE_SIZE, 22, 400, "mono", 1.5) is None:
            out.append(f"phase {p['index'] + 1}: the subtitle doesn't fit across the frame; shorten it")
        text = str((p["caption"] or {}).get("text") or "")
        if text and caption_size(text) is None:
            out.append(f"phase {p['index'] + 1}: the caption doesn't fit in two lines; shorten it")
    pills = sum(pill_width(s) for s in spec.get("stats") or []) + PILL_GAP * max(0, len(spec.get("stats") or []) - 1)
    if pills > HEAD_RIGHT - HEAD_LEFT:
        out.append("the stat pills don't fit side by side; shorten their names or have fewer")
    end = spec.get("end") or {}
    claim = str(end.get("claim") or "")
    if claim and not lines(claim, END_CLAIM, RIGHT - LEFT):
        out.append("the end card's claim doesn't fit in two lines; shorten it")
    note = str(end.get("note") or "")
    if note and width(note, END_NOTE, 400, "mono", 1) > RIGHT - LEFT:
        out.append("the end card's note doesn't fit on one line; shorten it")
    box = fr["box"]
    if box[3] - box[1] < 260:
        out.append("there's no room left for the diagram: fewer code lines")
    nodes = {n["id"]: n for n in spec.get("nodes") or []}
    count, marked = counted(spec), badged(spec)
    for p in phases:
        where = f"phase {p['index'] + 1}"
        q = queues.get(p["index"], {})
        at = place(spec, p, box, q)
        sides = badge_sides(spec, p)
        boxes = {}
        for n, (x, y) in at.items():
            left, top, right, bottom = footprint(nodes[n], n in count, q.get(n, 0), sides[n] if n in marked else False)
            b = (x - left, y - top, x + right, y + bottom)
            boxes[n] = b
            if b[0] < box[0] - 0.5 or b[2] > box[2] + 0.5 or b[1] < box[1] - 0.5 or b[3] > box[3] + 0.5:
                out.append(f"{where}: {n} doesn't fit in the diagram's space; fewer nodes side by side, or a "
                           "layout that spreads them")
        names = list(boxes)
        for i, a in enumerate(names):
            for b in names[i + 1:]:
                if _overlap(boxes[a], boxes[b]):
                    out.append(f"{where}: {a} and {b} overlap; fewer nodes in one column or row, or another layout")
        for a, b in p["edges"]:
            if a not in at or b not in at:
                continue
            for c, (x, y) in at.items():
                if c in (a, b):
                    continue
                if _distance((x, y), at[a], at[b]) < ICON * 0.6:
                    out.append(f"{where}: the line {a}-{b} runs through {c}; reorder the nodes or change the layout")
    return list(dict.fromkeys(out))


def pill_width(stat: dict) -> float:
    name = str(stat.get("name") or "")
    return (PILL_PAD * 2 + width(name, PILL_TEXT, 500, "mono", 2.5) + 14 + width("888", PILL_VALUE, 800, "mono")
            + 6 + width(str(stat.get("unit") or ""), PILL_TEXT, 500, "mono"))


def _overlap(a, b) -> bool:
    return not (a[2] + GAP <= b[0] or b[2] + GAP <= a[0] or a[3] + GAP <= b[1] or b[3] + GAP <= a[1])


def _distance(p, a, b) -> float:
    (px, py), (ax, ay), (bx, by) = p, a, b
    dx, dy = bx - ax, by - ay
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / max(1e-9, dx * dx + dy * dy)))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))

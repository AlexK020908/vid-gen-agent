"""What must never pass through what, in a film written straight in Blender (a film.py that render/film_parts.py renders), measured on
every frame before any frame is rendered. The owner caught a wrist through a microwave's side on Nov 15, 2026: a hand keyed by eye
reached into the oven for the fork, nothing measured the arm against the oven, and a frame reviewer reading sheets of the cut missed it.

A film's FILM_CHECK run makes one `Crossings`, naming what moves (a hand and its sleeve) and what's solid (an oven's shell, its door, its
keys, a plate), calls `look(t)` at every frame once the scene is set there, and ends with `report()`. That prints a line starting with
CHECKED, which render/film_parts.py looks for: it won't render a film whose check doesn't print it, or finds something through something.

A film that draws small things inside a solid (electrons in a fork's steel, water in food) also makes a `Within`, looked at the same way
once the frame's drawn things are placed: each must stay inside its solid on every frame. And a `Lens`: the camera never inside anything
it films, nor right up against it.
"""
from __future__ import annotations

from mathutils import Vector

from blender.bounds import MOST_PAIRS, Solid

MOST = 0.0015       # how far one thing may go into another, in meters, before it shows: a fingertip on a key, a pad on a fork's handle
CHECKED = "CHECKED: what passes through what"


def _box(objs: list) -> tuple[Vector, Vector] | None:
    """Where some objects are, as a box in the world: from their bounding boxes, so a solid far from every mover is never built."""
    points = [o.matrix_world @ Vector(corner) for o in objs for corner in o.bound_box]
    if not points:
        return None
    return (Vector(tuple(min(p[i] for p in points) for i in range(3))), Vector(tuple(max(p[i] for p in points) for i in range(3))))


def _meet(a: tuple[Vector, Vector], low: Vector, high: Vector, margin: float) -> bool:
    return all(a[0][i] - margin <= high[i] and low[i] - margin <= a[1][i] for i in range(3))


def closed(solid: Solid) -> bool:
    """Whether a solid's surfaces close round an inside: every edge shared by two faces. An oven's five walls, open at the front, don't,
    so a point in the oven isn't inside them, though a ray from it crosses one wall and so seems to be."""
    count: dict[tuple[int, int], int] = {}
    for poly in solid.polys:
        for a, b in zip(poly, poly[1:] + poly[:1]):
            edge = (a, b) if a < b else (b, a)
            count[edge] = count.get(edge, 0) + 1
    return bool(count) and all(n == 2 for n in count.values())


def depth(mover: Solid, solid: Solid, shut: bool = True) -> float:
    """How deep a mover goes into a solid, in meters: where their faces cross, and, if the solid closes round an inside (`shut`), how
    far the mover's points are in it. Not the solid's points inside the mover, as Solid.crossing also counts: a hand cut off at the
    forearm is an open mesh, so counting the surfaces a ray crosses on its way out of it says nothing, and on the first check that put
    an oven wall 112 mm inside a hand."""
    if not mover.tree or not solid.tree or not mover.near(solid):
        return 0.0
    pairs = mover.tree.overlap(solid.tree)
    deepest = 0.0
    for a, b in pairs[:: max(1, len(pairs) // MOST_PAIRS)]:
        one, two = mover.polys[a], solid.polys[b]
        deepest = max(deepest, min(mover._across(one, solid, two), solid._across(two, mover, one)))
    return max(deepest, mover._inside(solid)) if shut else deepest


class Crossings:
    """Frame by frame, how deep each mover goes into each solid. `movers` and `solids` map a name a person would use ("the hand", "the
    oven's keypad side") to the mesh objects it's made of. `allow` gives a pair a deeper limit where touching is the point, as a pinch
    on a handle is: never more than a few millimeters."""

    def __init__(self, movers: dict[str, list], solids: dict[str, list], most: float = MOST, allow: dict | None = None):
        self.movers = {name: [o for o in objs if o is not None] for name, objs in movers.items()}
        self.solids = {name: [o for o in objs if o is not None] for name, objs in solids.items()}
        self.most = most
        self.allow = allow or {}
        self.found: list[tuple[float, str, str, float]] = []
        self.frames = 0
        self._shut: dict[str, bool] = {}       # whether each solid closes round an inside, measured once

    def look(self, t: float) -> list[tuple[str, str, float]]:
        """The scene as it stands now, at time t: every mover and solid that pass into each other deeper than they may."""
        self.frames += 1
        here = []
        movers = {name: Solid(objs) for name, objs in self.movers.items() if objs}
        for solid_name, objs in self.solids.items():
            box = _box(objs)
            near = [m for m in movers.values() if box and m.verts and _meet(box, m.low, m.high, 0.002)]
            if not near:
                continue
            solid = Solid(objs)
            if solid_name not in self._shut:
                self._shut[solid_name] = closed(solid)
            for mover_name, mover in movers.items():
                if mover not in near or set(self.movers[mover_name]) & set(objs):      # a thing is never measured against itself
                    continue
                deep = depth(mover, solid, self._shut[solid_name])
                if deep > self.allow.get((mover_name, solid_name), self.most):
                    here.append((mover_name, solid_name, deep))
                    self.found.append((t, mover_name, solid_name, deep))
        return here

    def problems(self) -> list[str]:
        """One line for each mover and solid that pass into each other: the deepest, and when, in words to fix it from."""
        spans: dict[tuple[str, str], list[tuple[float, float]]] = {}
        for t, mover, solid, depth in self.found:
            spans.setdefault((mover, solid), []).append((t, depth))
        out = []
        for (mover, solid), rows in spans.items():
            worst = max(rows, key=lambda r: r[1])
            out.append(f"{mover} goes {worst[1] * 1000:.1f} mm into {solid} at {worst[0]:.2f} s "
                       f"(through it from {rows[0][0]:.2f} s to {rows[-1][0]:.2f} s, {len(rows)} frames)")
        return out

    def report(self) -> list[str]:
        """Prints the CHECKED line render/film_parts.py looks for, then the problems, and returns them."""
        found = self.problems()
        print(f"{CHECKED}: {self.frames} frames, {len(self.movers)} moving, {len(self.solids)} solid, {len(found)} problem(s)", flush=True)
        for line in found:
            print("  THROUGH: " + line, flush=True)
        return found


STAYS = "CHECKED: what stays inside what"


def _radius(obj) -> float:
    """How far a small round thing reaches from its middle, in the world."""
    lo, hi = Vector(obj.bound_box[0]), Vector(obj.bound_box[6])
    return max(hi[i] - lo[i] for i in range(3)) / 2 * max(obj.matrix_world.to_scale())


class Within:
    """Small things drawn inside a solid, as electrons in a fork's steel or water in food, measured on every frame: each one's middle
    inside the solid, and none of it out past the solid's surface by more than `most`. The microwave short's cut 1 frame reviewer (Nov 15,
    2026) saw electrons below the fork's neck and between its prongs, which a sheet of small frames can't settle either way. `groups` maps
    a name a person would use ("the fork's electrons") to (the small things, the solid's mesh objects); only the shown ones are measured.
    The solid must close round an inside (every edge shared by two faces), as a solidified fork or a sphere does."""

    def __init__(self, groups: dict[str, tuple[list, list]], most: float = 0.0003):
        self.groups = {name: ([o for o in small if o is not None], [o for o in objs if o is not None]) for name, (small, objs) in groups.items()}
        self.most = most
        self.found: list[tuple[float, str, int, int, float]] = []
        self.frames = 0

    def look(self, t: float) -> list[tuple[str, int, float]]:
        """The drawn things as they stand now, at time t: for each group, how many poke out of their solid, and by how much at most."""
        self.frames += 1
        here = []
        for name, (small, objs) in self.groups.items():
            shown = [o for o in small if not o.hide_render]
            if not shown or not objs:
                continue
            solid = Solid(objs)
            if not solid.tree:
                continue
            out, worst = 0, 0.0
            for obj in shown:
                point, r = obj.matrix_world.translation.copy(), _radius(obj)
                found = solid.tree.find_nearest(point)
                d = found[3] if found[3] is not None else 0.0
                poke = r - d if solid._holds(point) else r + d
                if poke > self.most:
                    out += 1
                    worst = max(worst, poke)
            if out:
                here.append((name, out, worst))
                self.found.append((t, name, out, len(shown), worst))
        return here

    def problems(self) -> list[str]:
        spans: dict[str, list[tuple[float, int, int, float]]] = {}
        for t, name, out, shown, worst in self.found:
            spans.setdefault(name, []).append((t, out, shown, worst))
        lines = []
        for name, rows in spans.items():
            t, out, shown, worst = max(rows, key=lambda r: r[3])
            lines.append(f"{name}: {out} of {shown} out of it by up to {worst * 1000:.2f} mm at {t:.2f} s "
                         f"(from {rows[0][0]:.2f} s to {rows[-1][0]:.2f} s, {len(rows)} frames)")
        return lines

    def report(self) -> list[str]:
        """Prints the line saying this was measured, then the problems, and returns them."""
        found = self.problems()
        print(f"{STAYS}: {self.frames} frames, {len(self.groups)} kind(s) of drawn thing, {len(found)} problem(s)", flush=True)
        for line in found:
            print("  OUTSIDE: " + line, flush=True)
        return found


LENS = "CHECKED: what the lens comes up against"


class Lens:
    """The camera, measured on every frame against what it films: its lens never inside a solid, nor nearer to one than `most`. The
    microwave short's cut 2 frame reviewer (Nov 15, 2026) saw the view graze a mound of mash on its way to the fork, the water drawn in
    the mash swelling into blurred discs at the lens. Hidden things (a door left behind as the view goes in through it) aren't measured."""

    def __init__(self, cam, solids: dict[str, list], most: float = 0.006):
        self.cam = cam
        self.solids = {name: [o for o in objs if o is not None] for name, objs in solids.items()}
        self.most = most
        self.found: list[tuple[float, str, float, bool]] = []
        self.frames = 0
        self._shut: dict[str, bool] = {}
        self.nearest: dict[str, tuple[float, float]] = {}        # how near the lens came to each, and when: to see the check measured

    def look(self, t: float) -> list[tuple[str, float, bool]]:
        self.frames += 1
        here = []
        eye = self.cam.matrix_world.translation.copy()
        for name, objs in self.solids.items():
            shown = [o for o in objs if not o.hide_render]
            box = _box(shown)
            if not box or not _meet(box, eye, eye, self.most + 0.002):
                continue
            solid = Solid(shown)
            if not solid.tree:
                continue
            if name not in self._shut:
                self._shut[name] = closed(solid)
            found = solid.tree.find_nearest(eye)
            d = found[3] if found[3] is not None else 1.0
            if d < self.nearest.get(name, (1.0, 0.0))[0]:
                self.nearest[name] = (d, t)
            inside = self._shut[name] and solid._holds(eye)
            if inside or d < self.most:
                here.append((name, d, inside))
                self.found.append((t, name, d, inside))
        return here

    def problems(self) -> list[str]:
        spans: dict[str, list[tuple[float, float, bool]]] = {}
        for t, name, d, inside in self.found:
            spans.setdefault(name, []).append((t, d, inside))
        lines = []
        for name, rows in spans.items():
            worst = max(rows, key=lambda r: (r[2], -r[1]))
            how = "inside" if worst[2] else f"{worst[1] * 1000:.1f} mm from"
            lines.append(f"the lens is {how} {name} at {worst[0]:.2f} s (from {rows[0][0]:.2f} s to {rows[-1][0]:.2f} s, {len(rows)} frames)")
        return lines

    def report(self) -> list[str]:
        found = self.problems()
        print(f"{LENS}: {self.frames} frames, {len(self.solids)} solid, {len(found)} problem(s)", flush=True)
        near = sorted(self.nearest.items(), key=lambda kv: kv[1][0])[:5]
        if near:
            print("  nearest: " + "; ".join(f"{name} {d * 1000:.0f} mm at {t:.2f} s" for name, (d, t) in near), flush=True)
        for line in found:
            print("  LENS: " + line, flush=True)
        return found

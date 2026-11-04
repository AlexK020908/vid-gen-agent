"""What's solid in a scene, measured from the meshes as they stand at a frame: how things come to rest on each other, whether
they pass through each other, and whether anything's holding them up. A scene that breaks this is refused in words before a
frame is rendered, so nobody has to spot it by eye (blender/stage.py).
"""
from __future__ import annotations

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

MOST_PAIRS = 3000      # of the faces two things cross at, how many are measured: enough to find the deepest
MOST_INSIDE = 800      # of a thing's points and faces, how many are tested for being inside another
GRID = 32              # rays a side across where two things overlap, finding how far one can come down onto the other


def meshes_of(root) -> list:
    """The meshes that make up something, leaving out what's never drawn."""
    return [obj for obj in [root, *root.children_recursive]
            if obj.type == "MESH" and not obj.hide_viewport and obj.display_type != "WIRE" and not obj.get("light")]


class Solid:
    """Meshes as they stand right now, in the world."""

    def __init__(self, meshes: list):
        graph = bpy.context.evaluated_depsgraph_get()
        self.verts: list[Vector] = []
        self.polys: list[tuple] = []
        for obj in meshes:
            evaluated = obj.evaluated_get(graph)
            mesh = evaluated.to_mesh()
            place = evaluated.matrix_world.copy()
            start = len(self.verts)
            self.verts += [place @ v.co for v in mesh.vertices]
            self.polys += [tuple(start + i for i in p.vertices) for p in mesh.polygons]
            evaluated.to_mesh_clear()
        self.tree = BVHTree.FromPolygons(self.verts, self.polys, epsilon=0.0) if self.polys else None
        if self.verts:
            self.low = Vector(tuple(min(v[i] for v in self.verts) for i in range(3)))
            self.high = Vector(tuple(max(v[i] for v in self.verts) for i in range(3)))
        else:
            self.low = self.high = Vector()

    def near(self, other: "Solid", margin: float = 0.0) -> bool:
        return all(self.low[i] - margin <= other.high[i] and other.low[i] - margin <= self.high[i] for i in range(3))

    def _sample(self, most: int) -> list[Vector]:
        return self.verts[:: max(1, len(self.verts) // most)]

    def _plane(self, poly: tuple) -> tuple[Vector, Vector]:
        a, b, c = (self.verts[i] for i in poly[:3])
        return a, (b - a).cross(c - a).normalized()

    def _across(self, poly: tuple, other: "Solid", across: tuple) -> float:
        """How far a face reaches past another's plane, on the side it reaches least: how deep it goes, rather than how far
        it runs on beyond."""
        at, normal = other._plane(across)
        reach = [(self.verts[i] - at).dot(normal) for i in poly]
        return min(max(max(reach), 0.0), max(-min(reach), 0.0))

    def crossing(self, other: "Solid") -> float:
        """How deep this and another pass through each other, in meters. 0 if they don't."""
        if not self.tree or not other.tree or not self.near(other):
            return 0.0
        pairs = self.tree.overlap(other.tree)
        if not pairs:
            return 0.0
        deepest = 0.0
        for a, b in pairs[:: max(1, len(pairs) // MOST_PAIRS)]:
            one, two = self.polys[a], other.polys[b]
            deepest = max(deepest, min(self._across(one, other, two), other._across(two, self, one)))
        return max(deepest, self._inside(other), other._inside(self))

    def _holds(self, point: Vector) -> bool:
        """Whether a point is inside this, by how many surfaces a ray from it crosses on its way out."""
        crossed, at = 0, point
        way = Vector((0.0123, 0.0177, 1.0)).normalized()     # not along any face: straight up can run along a wall
        for _ in range(32):
            hit = self.tree.ray_cast(at, way)
            if hit[0] is None:
                break
            crossed += 1
            at = hit[0] + way * 1e-5
        return crossed % 2 == 1

    def _inside(self, other: "Solid") -> float:
        """How deep this is inside another: what the faces can't say when two shapes line up exactly, as one block sliding through
        another of the same size does."""
        centres = [sum((self.verts[i] for i in poly), Vector()) / len(poly) for poly in self.polys[:: max(1, len(self.polys) // MOST_INSIDE)]]
        deepest = 0.0
        for point in [*self._sample(MOST_INSIDE), *centres]:
            if all(other.low[i] <= point[i] <= other.high[i] for i in range(3)) and other._holds(point):
                found = other.tree.find_nearest(point)
                if found[3] is not None and found[3] > deepest:
                    deepest = found[3]
        return deepest

    def drop_onto(self, below: "Solid") -> float | None:
        """How far this can come straight down before it touches what's below it, by rays both ways, since a ring under a flat
        pan touches the middle of a face with no corner there, and down a grid across where they overlap, since two big faces
        turned against each other can overlap with no corner of either over the other. None if it isn't over it at all."""
        least = None
        x0, x1 = max(self.low.x, below.low.x), min(self.high.x, below.high.x)
        y0, y1 = max(self.low.y, below.low.y), min(self.high.y, below.high.y)
        if x0 < x1 and y0 < y1:
            for i in range(GRID):
                for j in range(GRID):
                    x, y = x0 + (x1 - x0) * (i + 0.5) / GRID, y0 + (y1 - y0) * (j + 0.5) / GRID
                    under = self.tree.ray_cast(Vector((x, y, below.low.z - 1.0)), Vector((0, 0, 1)))
                    over = below.tree.ray_cast(Vector((x, y, self.high.z + 1.0)), Vector((0, 0, -1)))
                    if under[0] is not None and over[0] is not None:
                        gap = under[0].z - over[0].z
                        if least is None or gap < least:
                            least = gap
        for point in self._sample(6000):
            hit = below.tree.ray_cast(point, Vector((0, 0, -1)))
            if hit[0] is not None and (least is None or hit[3] < least):
                least = hit[3]
        for point in below._sample(6000):
            hit = self.tree.ray_cast(point, Vector((0, 0, 1)))
            if hit[0] is not None and (least is None or hit[3] < least):
                least = hit[3]
        return least

    def gap_to(self, other: "Solid") -> float:
        """The nearest this comes to another, in meters: 0 if they meet, as a shaft running inside a motor does."""
        if not other.tree or not self.tree:
            return float("inf")
        if self.near(other) and self.tree.overlap(other.tree):
            return 0.0
        least = float("inf")
        for point in self._sample(800):
            found = other.tree.find_nearest(point)
            if found[3] is not None and found[3] < least:
                least = found[3]
        return least

    def ray(self, origin: Vector, direction: Vector) -> tuple:
        """The first thing a ray meets: (place, normal, distance), or None."""
        hit = self.tree.ray_cast(origin, direction) if self.tree else (None,)
        return (hit[0], hit[1], hit[3]) if hit[0] is not None else None

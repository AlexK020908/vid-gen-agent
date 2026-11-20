"""What fills things, what pours, and air drawn as moving balls: how the scene language's `level`, `fill`, `pour` and `air` are staged
(scenes/spec.py says how a scene asks for them, and blender/stage.py works out where and when).

  cut_at   a liquid part is cut off at a height in the world, frame by frame, so its top is flat and level whichever way what holds it is
           turned. Above it there's nothing. Seen from above, through that open top, its far inside wall is shaded as a flat surface facing
           up, which is what its top is
  stream   a pour, falling straight down from a spout under gravity and narrowing as it speeds up, since as much goes past every point each
           second. Its front falls from the spout when it starts, its tail falls away after it stops, and its foot is on what it lands on
  Air      balls going every way at once, as a gas's molecules do, at a spread of speeds, bouncing off everything solid and off the top of
           any liquid, which is the push you can't see. Some can be drawn off through a point, as a pump does, and thinning with height
           is gravity's, the same pull on every one, so the spread stays as it started
"""
from __future__ import annotations

import math
import random

import bmesh
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

from blender import bounds, look

GRAVITY = 9.81
UP = Vector((0, 0, 1))
OUT_WAYS = (Vector((0.0123, 0.0177, 1.0)).normalized(), Vector((0.81, -0.0211, 0.0173)).normalized(), Vector((-0.0307, 0.87, -0.0191)).normalized())
STREAM_RINGS = 40          # rings down a stream's length, closer together near the spout, where it narrows fastest
MOST_SUBSTEPS = 8          # how finely a ball's frame is cut up, so it can't step through a wall thinner than itself
MEAN_SPEED = 1.596         # a gas's mean speed, in steps of the spread of each part of its velocity (Maxwell's)
BALL_SEGMENTS = 2          # how finely a ball is made: an icosphere divided this many times
FULL_SHORT = 0.0003        # a full liquid is cut this far under its own top: a mesh's own top shades in a starburst where its sides' smoothing meets it


def _keyed(tree, keys) -> bpy.types.NodeSocket:
    """A value node that takes these values at these frames, in straight lines between them."""
    node = tree.nodes.new("ShaderNodeValue")
    for frame, value in keys:
        node.outputs[0].default_value = value
        node.outputs[0].keyframe_insert("default_value", frame=frame)
    data = tree.animation_data
    if data and data.action:
        for curve in look._fcurves(data.action):
            for point in curve.keyframe_points:
                point.interpolation = "LINEAR"
    return node.outputs[0]


def _own_materials(obj) -> list:
    """Its materials, each its own copy, so cutting this one doesn't cut anything else painted the same."""
    out = []
    for slot in obj.material_slots:
        if slot.material is None:
            continue
        slot.material = slot.material.copy()
        slot.material.use_nodes = True
        out.append(slot.material)
    return out


ROOM = 1.5            # how many radii from anything solid an air ball has to start
TOP_SHADE = 0.55      # a liquid's top, facing up, mirrors the bright studio over it, and pale as milk is how that reads: it's darker than its sides


def _top_facing_up(tree, geometry) -> None:
    """Its far inside wall, seen through its open top, shades as a surface facing up: that's the top of a liquid."""
    for bsdf in [n for n in tree.nodes if n.type == "BSDF_PRINCIPLED"]:
        normal = bsdf.inputs["Normal"]
        mix = tree.nodes.new("ShaderNodeMix")
        mix.data_type = "VECTOR"
        tree.links.new(geometry.outputs["Backfacing"], mix.inputs[0])
        tree.links.new(normal.links[0].from_socket if normal.links else geometry.outputs["Normal"], mix.inputs[4])
        mix.inputs[5].default_value = (0.0, 0.0, 1.0)
        tree.links.new(mix.outputs[1], normal)
        color = bsdf.inputs["Base Color"]
        shade = tree.nodes.new("ShaderNodeMix")
        shade.data_type = "RGBA"
        shade.blend_type = "MULTIPLY"
        tree.links.new(geometry.outputs["Backfacing"], shade.inputs[0])
        if color.links:
            tree.links.new(color.links[0].from_socket, shade.inputs[6])
        else:
            shade.inputs[6].default_value = color.default_value
        shade.inputs[7].default_value = (TOP_SHADE, TOP_SHADE, TOP_SHADE, 1.0)
        tree.links.new(shade.outputs[2], color)


def _clip(mat, low_keys=None, high_keys=None) -> None:
    """Only what's between two heights in the world shows, each keyed frame by frame: none below `low`, none above `high`."""
    tree = mat.node_tree
    output = next(n for n in tree.nodes if n.type == "OUTPUT_MATERIAL" and n.is_active_output)
    if not output.inputs["Surface"].links:
        return
    before = output.inputs["Surface"].links[0].from_socket
    geometry = tree.nodes.new("ShaderNodeNewGeometry")
    _top_facing_up(tree, geometry)
    z = tree.nodes.new("ShaderNodeSeparateXYZ")
    tree.links.new(geometry.outputs["Position"], z.inputs[0])
    shown = None
    for keys, test in ((high_keys, "LESS_THAN"), (low_keys, "GREATER_THAN")):
        if not keys:
            continue
        compare = tree.nodes.new("ShaderNodeMath")
        compare.operation = test
        tree.links.new(z.outputs["Z"], compare.inputs[0])
        tree.links.new(_keyed(tree, keys), compare.inputs[1])
        if shown is None:
            shown = compare.outputs[0]
        else:
            both = tree.nodes.new("ShaderNodeMath")
            both.operation = "MULTIPLY"
            tree.links.new(shown, both.inputs[0])
            tree.links.new(compare.outputs[0], both.inputs[1])
            shown = both.outputs[0]
    gone = tree.nodes.new("ShaderNodeBsdfTransparent")
    cut = tree.nodes.new("ShaderNodeMixShader")
    tree.links.new(shown, cut.inputs[0])
    tree.links.new(gone.outputs[0], cut.inputs[1])
    tree.links.new(before, cut.inputs[2])
    tree.links.new(cut.outputs[0], output.inputs["Surface"])
    mat.use_transparent_shadow = True        # what isn't there casts no shadow


def cut_at(obj, keys: list[tuple[int, float]]) -> None:
    """A liquid with its top at these world heights, frame by frame: (frame, z)."""
    for mat in _own_materials(obj):
        _clip(mat, high_keys=keys)


def lowest(obj) -> float:
    """The lowest point of a mesh in the world, as it stands."""
    graph = bpy.context.evaluated_depsgraph_get()
    evaluated = obj.evaluated_get(graph)
    mesh = evaluated.to_mesh()
    place = evaluated.matrix_world
    low = min((place @ v.co).z for v in mesh.vertices)
    evaluated.to_mesh_clear()
    return low


def highest(obj) -> float:
    graph = bpy.context.evaluated_depsgraph_get()
    evaluated = obj.evaluated_get(graph)
    mesh = evaluated.to_mesh()
    place = evaluated.matrix_world
    high = max((place @ v.co).z for v in mesh.vertices)
    evaluated.to_mesh_clear()
    return high


def tree_of(objs: list) -> BVHTree | None:
    """These meshes as they stand, as one tree to cast rays at."""
    graph = bpy.context.evaluated_depsgraph_get()
    verts, polys = [], []
    for obj in objs:
        evaluated = obj.evaluated_get(graph)
        mesh = evaluated.to_mesh()
        place = evaluated.matrix_world
        start = len(verts)
        verts += [place @ v.co for v in mesh.vertices]
        polys += [tuple(start + i for i in p.vertices) for p in mesh.polygons]
        evaluated.to_mesh_clear()
    return BVHTree.FromPolygons(verts, polys, epsilon=0.0) if polys else None


def holds(tree: BVHTree, point: Vector) -> bool:
    """Whether a point is inside a closed mesh: rays out of it cross an odd number of its surfaces, most of three ways."""
    votes = 0
    for way in OUT_WAYS:
        crossed, at = 0, point
        for _ in range(32):
            hit = tree.ray_cast(at, way)
            if hit[0] is None:
                break
            crossed += 1
            at = bounds.past(hit[0], way)
        votes += crossed % 2
    return votes >= 2


# --- a pour ------------------------------------------------------------------------------------------------------

def fallen(seconds: float, speed: float) -> float:
    """How far something leaving at `speed` straight down has fallen after this long."""
    return speed * seconds + GRAVITY * seconds * seconds / 2


def stream(name: str, mat, spout: dict[int, Vector], foot: dict[int, float], begin: int, end: int, last: int, fps: int, width: float, speed: float):
    """A stream falling straight down from where the spout is at each frame, onto `foot`, the height of what it lands on then. At `begin` its
    front leaves the spout and falls, and after `end` its tail does. It's `width` across at the spout, where it leaves at `speed`, and narrows
    as it falls faster: r = r0 (v0 / v) ** 0.5."""
    drop = max(spout[f].z - foot[f] for f in spout) + 0.01
    v0 = max(speed, 0.05)
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()
    rings, sides = [], 16
    for i in range(STREAM_RINGS + 1):
        h = drop * (i / STREAM_RINGS) ** 2
        r = width / 2 * math.sqrt(v0 / math.sqrt(v0 * v0 + 2 * GRAVITY * h))
        rings.append([bm.verts.new((r * math.cos(2 * math.pi * k / sides), r * math.sin(2 * math.pi * k / sides), -h)) for k in range(sides)])
    for a, b in zip(rings, rings[1:]):
        for k in range(sides):
            bm.faces.new((a[k], a[(k + 1) % sides], b[(k + 1) % sides], b[k]))
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])
    bm.to_mesh(mesh)
    bm.free()
    for poly in mesh.polygons:
        poly.use_smooth = True
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.data.materials.append(mat.copy())
    high, low = [], []
    for f in range(1, last + 1):
        obj.location = spout[f]
        obj.keyframe_insert("location", frame=f)
        tail = fallen(max(0.0, (f - end) / fps), v0) if f > end else -0.001
        front = fallen((f - begin) / fps, v0) if f >= begin else -0.002
        high.append((f, spout[f].z - tail))
        low.append((f, max(spout[f].z - front, foot[f] - 0.002)))
    _clip(obj.data.materials[0], low_keys=low, high_keys=high)
    obj["light"] = True          # not something solid
    return obj


# --- air ---------------------------------------------------------------------------------------------------------

class Air:
    """Balls in a box, going every way. `solids(frame)` gives the trees of what's solid then, and `liquids(frame)` (tree, top) pairs."""

    def __init__(self, name: str, box, count: int, radius: float, speed: float, mat, fps: int, solids, liquids, floor: float | None = None,
                 thins: float | None = None, walled: bool = False, seed: int = 11, within=None, parts=None):
        self.name, self.radius, self.fps, self.mat = name, radius, fps, mat
        self.low, self.high = Vector(box[0]), Vector(box[1])
        self.spread = speed / MEAN_SPEED
        self.solids, self.liquids, self.floor, self.walled = solids, liquids, floor, walled
        self.scale = thins / math.log(2) if thins else None          # thins is how much higher there's half as much: e^(-h / scale)
        self.pull = self.spread ** 2 / self.scale if thins else 0.0    # the pull down that keeps it that way, as gravity does the sky's: kT / m = g x scale
        self.rng = random.Random(seed)
        self.balls: list[dict] = []
        self.count, self.thins = count, thins
        self.plans: list[dict] = []        # what's drawn off when: {"frame", "share", "out", "over", "inside"}
        self.within = within               # where a ball may start, if not anywhere clear in the box: inside something's hollow
        self.parts = parts                 # each solid part by itself, (low, high, tree), to ask whether a point's inside one

    def _start_height(self) -> float:
        if not self.thins:
            return self.rng.uniform(self.low.z, self.high.z)
        span = self.high.z - self.low.z          # thinning as e^(-h / scale), cut off at the top of the box
        u = self.rng.random()
        return self.low.z - self.scale * math.log(1 - u * (1 - math.exp(-span / self.scale)))

    def _clear(self, at: Vector, trees, liquids) -> bool:
        """Somewhere a ball can be: not in anything solid, nor under the top of a liquid, nor touching either. Whether it's inside something is
        asked of each solid part by itself, as counting crossings through parts that overlap each other, a road under a pavement, says inside
        where it's out in the open."""
        for tree in trees:
            near = tree.find_nearest(at)
            if near[3] is not None and near[3] < self.radius * ROOM:
                return False
        if self.inside_solid(at, trees):
            return False
        for tree, top in liquids:
            if at.z < top + self.radius and holds(tree, Vector((at.x, at.y, min(at.z, top - 1e-4)))):
                return False
        return self.floor is None or at.z > self.floor + self.radius

    def inside_solid(self, at: Vector, trees) -> bool:
        if self.parts is None:
            return any(holds(tree, at) for tree in trees)
        return any(all(low[i] <= at[i] <= high[i] for i in range(3)) and holds(tree, at) for low, high, tree in self.parts)

    def fill(self, frame: int) -> None:
        trees, liquids = self.solids(frame), self.liquids(frame)
        tries = 0
        while len(self.balls) < self.count and tries < self.count * 40:
            tries += 1
            at = Vector((self.rng.uniform(self.low.x, self.high.x), self.rng.uniform(self.low.y, self.high.y), self._start_height()))
            if not self._clear(at, trees, liquids) or (self.within and not self.within(at)):
                continue
            way = Vector((self.rng.gauss(0, self.spread), self.rng.gauss(0, self.spread), self.rng.gauss(0, self.spread)))
            self.balls.append({"at": at, "v": way, "gone": None, "leaving": None, "track": {}})

    def leave(self, frame: int, share: float, out: Vector, over: float, inside=None) -> None:
        """A share of the balls in `inside` (a box), or all of them, drawn off toward `out` over `over` seconds, as a pump draws air."""
        here = [b for b in self.balls if b["gone"] is None and b["leaving"] is None and
                (inside is None or all(inside[0][i] <= b["at"][i] <= inside[1][i] for i in range(3)))]
        self.rng.shuffle(here)
        for b in here[:round(len(here) * share)]:
            b["leaving"] = {"from": frame, "out": Vector(out), "drift": max((Vector(out) - b["at"]).length / max(over, 0.05), self.spread)}

    def _wrap(self, b: dict, trees, liquids) -> bool:
        """Open air goes on past the box's sides, so what leaves one side comes in at the other, if there's room for it there; if not, it bounces
        back, which out of the picture nobody sees. Its top and bottom are unseen lids, since coming in at the bottom would be popping up out of
        what's there. Thinning air has no top, since what goes up comes down. Returns whether it's still in the box: what's being drawn off is
        gone once it leaves."""
        at, v = b["at"], b["v"]
        inside = all(self.low[i] <= at[i] <= self.high[i] for i in range(3))
        if b["leaving"]:
            return inside
        for i in range(3):
            lo, hi = self.low[i], self.high[i]
            if lo <= at[i] <= hi or (i == 2 and self.thins and at.z > hi):
                continue
            bounced = 2 * (lo if at[i] < lo else hi) - at[i]
            if i < 2 and not self.walled:
                there = at.copy()
                there[i] = lo + (at[i] - lo) % (hi - lo)
                if self._clear(there, trees, [(tree, top) for tree, top, _ in liquids]):
                    at[i] = there[i]
                    continue
            at[i] = bounced
            v[i] = abs(v[i]) if bounced <= (lo + hi) / 2 else -abs(v[i])
        return inside

    def _step(self, b: dict, h: float, trees, liquids) -> None:
        at, v = b["at"], b["v"]
        move = v * h
        if b["leaving"]:
            way = b["leaving"]["out"] - at
            if way.length > 1e-6:
                move = move + way.normalized() * (b["leaving"]["drift"] * h)
        if self.pull:
            v.z -= self.pull * h
        far = move.length
        if far < 1e-9:
            return
        way = move / far
        nearest = None
        for tree in trees:
            hit = tree.ray_cast(at, way, far + self.radius)
            if hit[0] is not None and (nearest is None or hit[3] < nearest[3]):
                nearest = hit
        if nearest is not None:
            normal = nearest[1] if nearest[1].dot(way) < 0 else -nearest[1]
            at += way * max(0.0, nearest[3] - self.radius)
            if v.dot(normal) < 0:
                v -= normal * (2 * v.dot(normal))
        else:
            at += move
        if self.floor is not None and at.z < self.floor + self.radius:
            at.z, v.z = 2 * (self.floor + self.radius) - at.z, abs(v.z)
        for tree, top, was in liquids:
            if at.z < top + self.radius and b["above"].get(id(tree), True) and holds(tree, Vector((at.x, at.y, top - 1e-4))):
                at.z, v.z = top + self.radius + (top + self.radius - at.z), abs(v.z)

    def run(self, begin: int, end: int, last: int) -> list:
        """Moves them all from `begin` to `end`, frame by frame, and keys the balls to it. Returns the balls' objects."""
        dt = 1.0 / self.fps
        fastest = max([b["v"].length for b in self.balls] + [self.spread * 3])
        steps = max(1, min(MOST_SUBSTEPS, math.ceil(fastest * dt / self.radius)))
        leaving_at: dict[int, list] = {}
        for plan in self.plans:
            leaving_at.setdefault(plan["frame"], []).append(plan)
        before: dict[int, float] = {}
        for f in range(begin, end + 1):
            for plan in leaving_at.get(f, []):
                self.leave(f, plan["share"], plan["out"], plan["over"], plan.get("inside"))
            trees = self.solids(f)
            now = self.liquids(f)
            tops = [(tree, top, None) for tree, top in now]
            for b in self.balls:
                if b["gone"] is not None:
                    continue
                b["track"][f] = b["at"].copy()
                b["above"] = {id(tree): b["at"].z >= before.get(k, top) - self.radius for k, (tree, top) in enumerate(now)}     # above the top as it was: if it's risen past, it pushes the ball up
                for _ in range(steps):
                    self._step(b, dt / steps, trees, tops)
                inside = self._wrap(b, trees, tops)
                if b["leaving"] and ((b["at"] - b["leaving"]["out"]).length < self.radius * 3 + b["leaving"]["drift"] * dt or not inside):
                    b["gone"] = f + 1
            before = {k: top for k, (_, top) in enumerate(now)}
        return self._key(begin, end, last)

    def _key(self, begin: int, end: int, last: int) -> list:
        mesh = bpy.data.meshes.new(f"{self.name}.ball")
        bm = bmesh.new()
        bmesh.ops.create_icosphere(bm, subdivisions=BALL_SEGMENTS, radius=self.radius)
        bm.to_mesh(mesh)
        bm.free()
        for poly in mesh.polygons:
            poly.use_smooth = True
        mesh.materials.append(self.mat)
        made = []
        for i, b in enumerate(self.balls):
            obj = bpy.data.objects.new(f"{self.name}.{i}", mesh)
            bpy.context.scene.collection.objects.link(obj)
            obj["light"] = True
            obj.visible_shadow = False        # a picture of air, not a thing: it casts no shadow
            obj["air"] = True                 # nor does it hide a label's dot behind it (blender/tracks.py)
            gone = b["gone"] or end + 1
            for f, at in b["track"].items():
                obj.location = at
                obj.keyframe_insert("location", frame=f)
            for f, size in ((1, 0.0), (begin, 1.0), (gone, 0.0)):
                if f <= last:
                    obj.scale = (size, size, size)
                    obj.keyframe_insert("scale", frame=f)
            if obj.animation_data and obj.animation_data.action:
                for curve in look._fcurves(obj.animation_data.action):
                    kind = "CONSTANT" if curve.data_path == "scale" else "LINEAR"
                    for point in curve.keyframe_points:
                        point.interpolation = kind
            made.append(obj)
        return made

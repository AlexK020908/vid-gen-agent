"""Builds a machine from its spec (machines/spec.py has the format and checks it before Blender starts).

Every part becomes one object, named by its id, at its place under its parent. A part with a joint moves only
through `Model.set()`: the joint's value turns or slides it in its parent's space, so whatever it carries moves
with it. Couplings are worked out from their drivers every time a joint is set: a crank's angle gives its
piston's height exactly.
"""
from __future__ import annotations

import math

import bpy
from mathutils import Euler, Quaternion, Vector
from mathutils.bvhtree import BVHTree

from blender import look, shapes

AXIS = {"x": Vector((1, 0, 0)), "y": Vector((0, 1, 0)), "z": Vector((0, 0, 1))}


def _make(part: dict, name: str):
    kind, mat = part["kind"], part.get("material")
    if kind == "group":
        obj = bpy.data.objects.new(name, None)
        bpy.context.scene.collection.objects.link(obj)
        return obj
    if kind == "box":
        return shapes.box(name, part["size"], mat, bevel=part.get("bevel", 0.0))
    if kind == "cylinder":
        return shapes.cylinder(name, part["r"], part["h"], mat, bevel=part.get("bevel", 0.0),
                               segments=part.get("segments", 64))
    if kind == "tube":
        return shapes.tube(name, part["r_out"], part["r_in"], part["h"], mat, segments=part.get("segments", 64))
    if kind == "cone":
        return shapes.lathe(name, [(0, 0), (part["r1"], 0), (part["r2"], part["h"]), (0, part["h"])], mat,
                            segments=part.get("segments", 64))
    if kind == "lathe":
        return shapes.lathe(name, [tuple(p) for p in part["points"]], mat, segments=part.get("segments", 64))
    if kind == "sphere":
        return shapes.sphere(name, part["r"], mat, segments=part.get("segments", 24))
    if kind == "torus":
        return shapes.torus(name, part["major"], part["minor"], mat, arc=part.get("arc", 360.0),
                            axis=part.get("axis", "Z").upper())
    if kind == "extrude":
        return shapes.extrude(name, [tuple(p) for p in part["outline"]], part["depth"], mat, bevel=part.get("bevel", 0.0))
    if kind == "pipe":
        return shapes.pipe(name, part["path"], part["r"], mat, bend=part.get("bend", 0.0))
    if kind == "rods":
        return shapes.rods(name, [(tuple(a), tuple(b)) for a, b in part["pairs"]], part["r"], mat)
    if kind == "truss":
        return shapes.truss(name, part["length"], part["width"], part["bays"], mat, chord=part.get("chord", 0.05),
                            lace=part.get("lace", 0.025))
    if kind == "spring":
        return shapes.spring(name, part["r"], part["wire"], part["turns"], part["h"], mat)
    if kind == "spiral":
        return shapes.spiral(name, part["r_in"], part["r_out"], part["turns"], part["wire"], mat)
    if kind == "text":
        return shapes.text(name, part["body"], part["height"], mat, depth=part.get("depth", 0.0))
    raise ValueError(f"unknown kind {kind}")


class Model:
    """`prefix` names its objects apart from another model's; `root` (an empty) carries the whole machine, so a
    shot can place, turn and scale it as one."""

    def __init__(self, spec: dict, prefix: str = "", root=None):
        self.spec = spec
        self.parts = {p["id"]: p for p in spec["parts"]}
        self.objects: dict[str, bpy.types.Object] = {}
        self.values: dict[str, float] = {}
        self.root = root
        for pid, part in self.parts.items():
            obj = _make(part, prefix + pid)
            if part.get("group"):
                obj["group"] = part["group"]
            self.objects[pid] = obj
        for pid, part in self.parts.items():
            if part.get("parent"):
                self.objects[pid].parent = self.objects[part["parent"]]
            elif root is not None:
                self.objects[pid].parent = root
        for pid, part in self.parts.items():
            if part.get("helper"):   # a shape only for cutting holes: never drawn
                self.objects[pid].hide_render = True
                self.objects[pid].display_type = "WIRE"
            for hole in part.get("subtract") or []:
                mod = self.objects[pid].modifiers.new(f"Hole {hole}", "BOOLEAN")
                mod.operation = "DIFFERENCE"
                mod.solver = "EXACT"
                mod.object = self.objects[hole]
        # holes never move against their part, so they're cut once here rather than on every frame
        holed = [pid for pid, part in self.parts.items() if part.get("subtract")]
        if holed:
            for pid in self.parts:
                self._place(pid)
            bpy.context.view_layer.update()
            for pid in holed:
                bake(self.objects[pid], prefix="Hole ")
        for pid, part in self.parts.items():
            joint = part.get("joint")
            self.values[pid] = float(joint.get("rest", joint.get("min", 0))) if joint else 0.0
            self._place(pid)
        self._couple()

    # --- joints -------------------------------------------------------------------------------------------------

    def _place(self, pid: str) -> None:
        part, obj = self.parts[pid], self.objects[pid]
        at = Vector(part.get("at", (0, 0, 0)))
        rot = Euler([math.radians(a) for a in part.get("rot", (0, 0, 0))]).to_quaternion()
        scale = part.get("scale", 1.0)
        scale = Vector(scale) if isinstance(scale, list) else Vector((scale, scale, scale))
        joint, v = part.get("joint"), self.values.get(pid, 0.0)
        if joint:
            axis = AXIS[joint["axis"]]
            if joint["type"] == "stretch":    # a cable or rod that lengthens along its axis: v is its length
                k = max(1e-4, v) / (part.get("h") or 1.0)
                scale = Vector([s * (k if a == joint["axis"] else 1.0) for s, a in zip(scale, "xyz")])
            elif joint["type"] == "slide":
                if part["kind"] == "spring" and joint["axis"] == "z":   # a spring squashes rather than moves
                    scale = Vector((scale.x, scale.y, scale.z * max(0.05, (part["h"] + v) / part["h"])))
                else:
                    at = at + axis * v
            else:
                rot = rot @ Quaternion(axis, math.radians(v))
        obj.rotation_mode = "XYZ"
        obj.location = at
        obj.rotation_euler = rot.to_euler("XYZ", obj.rotation_euler)   # nearest to the last, so a spin never flips
        obj.scale = scale

    def set(self, pid: str, value: float, frame: int | None = None) -> None:
        """Set a joint (a slide in meters, a hinge or spin in degrees), drive what it's coupled to, and keyframe
        the moved parts at `frame` if given."""
        joint = self.parts[pid].get("joint")
        if not joint:
            raise KeyError(f"part {pid} has no joint")
        if joint["type"] not in ("spin",):
            value = max(joint.get("min", value), min(joint.get("max", value), value))
        self.values[pid] = float(value)
        self._place(pid)
        moved = [pid] + self._couple()
        if frame is not None:
            for m in moved:
                obj = self.objects[m]
                look.key(obj, frame, location=obj.location.copy(), rotation_euler=obj.rotation_euler.copy(),
                         scale=obj.scale.copy())

    def _couple(self) -> list[str]:
        moved = []
        for c in self.spec.get("couple") or []:
            a = self.values[c["driver"]]
            if c["type"] == "crank":
                # a slider on a crank: throw r, rod l, at crank angle a (+ phase): s = r cos a + sqrt(l^2 - r^2 sin^2 a),
                # measured from the top of its stroke, so 0 is top dead centre and it goes down to -2r
                r, l = c["throw"], c["rod"]
                t = math.radians(a + c.get("phase", 0.0))
                s = r * math.cos(t) + math.sqrt(l * l - (r * math.sin(t)) ** 2) - (r + l)
                v = s * c.get("scale", 1.0)
            elif c["type"] == "rod":
                # a connecting rod hung from its piston's pin swings so its far end stays on the crank pin:
                # tilt = -asin(r sin a / l), in degrees, about the crank's axis
                r, l = c["throw"], c["rod"]
                v = -math.degrees(math.asin(max(-1.0, min(1.0, r * math.sin(math.radians(a + c.get("phase", 0.0)))
                                                         / l))))
            elif c["type"] == "gear":
                v = -a * c.get("ratio", 1.0)
            else:   # follow
                v = a * c.get("ratio", 1.0) + c.get("offset", 0.0)
            self.values[c["driven"]] = v
            self._place(c["driven"])
            moved.append(c["driven"])
        return moved

    # --- steps --------------------------------------------------------------------------------------------------

    def there(self, step: int) -> set[str]:
        out = set()
        for pid in self.parts:
            ok, cur = True, pid
            while cur is not None:
                rng = self.parts[cur].get("steps") or [1, None]
                if not (rng[0] <= step and (rng[1] is None or step <= rng[1])):
                    ok = False
                    break
                cur = self.parts[cur].get("parent")
            if ok:
                out.add(pid)
        return out

    def show_step(self, step: int, frame: int | None = None) -> None:
        """Show only the parts there at `step`; keyed at `frame` (constant until the next key) if given."""
        here = self.there(step)
        for pid, obj in self.objects.items():
            hidden = pid not in here or bool(self.parts[pid].get("helper"))
            obj.hide_render = hidden
            obj.hide_viewport = hidden
            if frame is not None:
                obj.keyframe_insert("hide_render", frame=frame)
                obj.keyframe_insert("hide_viewport", frame=frame)

    def anchor(self, name: str):
        pid, offset = self.spec["anchors"][name]
        return self.objects[pid], tuple(offset)

    def visible_objects(self):
        return [o for o in self.objects.values() if o.type == "MESH" and not o.hide_render]


def bake(obj, prefix: str = "") -> None:
    """Apply `obj`'s modifiers whose names start with `prefix` into its mesh, keeping the others."""
    keep = [m for m in obj.modifiers if not m.name.startswith(prefix)]
    for m in keep:
        m.show_viewport = False
    depsgraph = bpy.context.evaluated_depsgraph_get()
    mesh = bpy.data.meshes.new_from_object(obj.evaluated_get(depsgraph))
    for m in keep:
        m.show_viewport = True
    for m in [m for m in obj.modifiers if m.name.startswith(prefix)]:
        obj.modifiers.remove(m)
    old = obj.data
    obj.data = mesh
    if old.users == 0:
        bpy.data.meshes.remove(old)


def overlaps(model: Model, step: int) -> list[str]:
    """Parts there at `step` that pass through each other: with every joint at rest, then each joint at its min
    and its max, and each spinning driver a quarter turn at a time (a driven part moves only through its driver:
    a piston through its crank). Parent and child, and the spec's contacts, may touch."""
    allowed = {frozenset(p) for p in model.spec.get("contacts") or []}
    here = sorted(p for p in model.there(step) if not model.parts[p].get("helper"))
    for pid in here:
        parent = model.parts[pid].get("parent")
        if parent:
            allowed.add(frozenset((pid, parent)))
    driven = {c["driven"] for c in model.spec.get("couple") or []}
    drivers = {c["driver"] for c in model.spec.get("couple") or []}
    jointed = [p for p in here if model.parts[p].get("joint") and p not in driven]
    rest = {p: model.values[p] for p in jointed}
    states = [("rest", {})]
    for p in jointed:
        j = model.parts[p]["joint"]
        if j["type"] == "spin":
            if p in drivers:
                states += [(f"{p} at {a}", {p: rest[p] + a}) for a in (90, 180, 270)]
        else:
            lo, hi = j.get("check", [j.get("min", 0), j.get("max", 0)])
            states += [(f"{p} at {lo}", {p: lo}), (f"{p} at {hi}", {p: hi})]
    found: dict[frozenset, str] = {}
    meshes = [p for p in here if model.objects[p].type == "MESH"]
    for label, values in states:
        for p, v in values.items():
            model.set(p, v)
        bpy.context.view_layer.update()
        depsgraph = bpy.context.evaluated_depsgraph_get()
        trees = {}
        for p in meshes:
            obj = model.objects[p].evaluated_get(depsgraph)
            mesh = obj.to_mesh()
            verts = [obj.matrix_world @ v.co for v in mesh.vertices]
            polys = [tuple(f.vertices) for f in mesh.polygons]
            trees[p] = BVHTree.FromPolygons(verts, polys, epsilon=0.0) if polys else None
            obj.to_mesh_clear()
        for i, a in enumerate(meshes):
            for b in meshes[i + 1:]:
                key = frozenset((a, b))
                if key in allowed or key in found or not trees[a] or not trees[b]:
                    continue
                if trees[a].overlap(trees[b]):
                    found[key] = f"{a} and {b} pass through each other ({label})"
        for p in values:
            model.set(p, rest[p])
    return sorted(found.values())

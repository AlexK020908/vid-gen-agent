"""Ready-made models into a film (phase 64): a downloaded .blend (BlenderKit's, from render/assets.py) appended, its parts gathered
under one empty, measured, and fitted to where it goes; or kept as one collection that many copies instance (a town of houses).

The owner, Nov 19, 2026: everything beside a realistic person is as real as the person, found ready-made before anything is built."""
from __future__ import annotations

import math
from pathlib import Path

import bpy
from mathutils import Matrix, Vector


def append(path: str | Path, prefix: str, scene) -> tuple[bpy.types.Object, list[bpy.types.Object]]:
    """Every object in the .blend, renamed `<prefix>_<name>`, the ones with no parent put under a new empty named `prefix`. The
    file's cameras and lights are dropped (a model's file often brings its own studio). Returns the empty and the meshes."""
    with bpy.data.libraries.load(str(path), link=False) as (src, dst):
        dst.objects = list(src.objects)
    got = [o for o in dst.objects if o is not None]
    for o in [o for o in got if o.type in ("CAMERA", "LIGHT")]:
        got.remove(o)
        bpy.data.objects.remove(o)
    root = bpy.data.objects.new(prefix, None)
    scene.collection.objects.link(root)
    for o in got:
        scene.collection.objects.link(o)
        o.name = f"{prefix}_{o.name}"
    for o in got:
        if o.parent is None:
            o.parent = root
    bpy.context.view_layer.update()
    return root, [o for o in got if o.type == "MESH"]


def images_of(objs) -> set:
    """Every image the objects' materials use, in node groups too."""
    found, trees = set(), []

    def walk(tree):
        if tree in trees:
            return
        trees.append(tree)
        for n in tree.nodes:
            if n.type == "TEX_IMAGE" and n.image:
                found.add(n.image)
            elif n.type == "GROUP" and n.node_tree:
                walk(n.node_tree)

    for o in objs:
        if o.type == "MESH":
            for m in o.data.materials:
                if m and m.use_nodes:
                    walk(m.node_tree)
    return found


def shrink(objs, most: int) -> int:
    """Scales down every image the objects use whose longer side is over `most` pixels, to `most`: a model's maps sized for
    how near the camera comes, not for the close-up its maker rendered. The poop jet's town arrived with 8.5 GB of maps a
    process (an 8192 px roof seen from 30 m up), until each house's were held to 512 px (phase 64). Returns how many."""
    n = 0
    for img in images_of(objs):
        w, h = img.size[0], img.size[1]
        if max(w, h) > most:
            k = most / max(w, h)
            img.scale(max(1, round(w * k)), max(1, round(h * k)))
            n += 1
    return n


def strip_hair(objs) -> int:
    """Takes off the hair a model grows at render time (a geometry-nodes "hair system", particle hair), which no shot at
    our distances can see and which can cost gigabytes: the poop jet's towel rail grew fibres on its towel that took a
    render to 9 GB on their own (phase 64). Returns how many it took off."""
    n = 0
    for o in objs:
        for m in list(getattr(o, "modifiers", [])):
            hair = (m.type == "PARTICLE_SYSTEM" and m.particle_system.settings.type == "HAIR") or (
                m.type == "NODES" and m.node_group and "hair" in m.node_group.name.lower())
            if hair:
                o.modifiers.remove(m)
                n += 1
    return n


def box_of(meshes: list[bpy.types.Object]) -> tuple[Vector, Vector]:
    """The low and high corners round the meshes as they stand in the world."""
    pts = [o.matrix_world @ Vector(c) for o in meshes for c in o.bound_box]
    return (Vector([min(p[i] for p in pts) for i in range(3)]), Vector([max(p[i] for p in pts) for i in range(3)]))


def fit(root, meshes, at, turn: float = 0.0, height: float | None = None, size: tuple | None = None, scale: float | None = None):
    """Stands the model with the middle of its underside at `at`, turned `turn` radians about the vertical, at its own size, or scaled
    to a `height`, or to fit inside `size` (width, depth, height) whole. Returns the scale used."""
    root.matrix_world = Matrix.Identity(4)
    bpy.context.view_layer.update()
    lo, hi = box_of(meshes)
    dims = hi - lo
    s = scale or 1.0
    if height:
        s = height / dims.z
    elif size:
        s = min(size[i] / dims[i] for i in range(3) if size[i])
    base = Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z))
    root.matrix_world = (Matrix.Translation(Vector(at)) @ Matrix.Rotation(turn, 4, "Z") @ Matrix.Scale(s, 4) @ Matrix.Translation(-base))
    bpy.context.view_layer.update()
    return s


def as_collection(root, meshes, name: str, scene, stand: bool = True) -> tuple[bpy.types.Collection, Vector, Vector]:
    """The model moved into its own collection, kept out of the render where it stands (at the origin, underside down; or, with
    `stand` False, where its own file put it: a house whose cellar goes below its ground line keeps its ground at z = 0), for copies to
    instance. Returns the collection and the corners round it."""
    if stand:
        fit(root, meshes, (0, 0, 0))
    lo, hi = box_of(meshes)
    coll = bpy.data.collections.new(name)
    scene.collection.children.link(coll)
    for o in [root, *[c for c in root.children_recursive]]:
        for c in list(o.users_collection):
            c.objects.unlink(o)
        coll.objects.link(o)
    bpy.context.view_layer.layer_collection.children[coll.name].exclude = True
    return coll, lo, hi


def copy(coll, name: str, at, turn: float = 0.0, scale: float = 1.0, scene=None):
    """One more of a collection's model, standing at `at`."""
    e = bpy.data.objects.new(name, None)
    e.instance_type = "COLLECTION"
    e.instance_collection = coll
    e.location = at
    e.rotation_euler = (0.0, 0.0, turn)
    e.scale = (scale, scale, scale)
    (scene or bpy.context.scene).collection.objects.link(e)
    return e


def footprint(lo: Vector, hi: Vector, at, turn: float, scale: float = 1.0, pad: float = 0.0) -> list[Vector]:
    """The eight corners of a copy's box in the world (for the checks' stand-in), `pad` metres larger each way."""
    rot = Matrix.Rotation(turn, 3, "Z")
    out = []
    for x in (lo.x - pad, hi.x + pad):
        for y in (lo.y - pad, hi.y + pad):
            for z in (lo.z, hi.z + pad):
                out.append(Vector(at) + rot @ (Vector((x, y, z)) * scale))
    return out


def turned_to(direction: Vector) -> float:
    """The turn about the vertical that points a model's front (-Y) along `direction`."""
    return math.atan2(-direction.x, direction.y) + math.pi

"""A picture of every kept library piece that has none yet (blender/library.py), so the asset scout and the owner can see what
each is before bringing it in: data/library/<kind>/<name>/preview.png, 640 px square, written beside its .blend and listed in
index.json as "preview". Run in Blender, after a film's FILM_LIBRARY pass and not beside a render (it takes the GPU):

    blender -b --factory-startup -P blender/library_previews.py [-- name ...]

Props, effects and places are seen from a front corner, a little above, on a plain grey floor, lit by a sun and a soft sky.
A set (a room) is seen from inside, from a corner at eye height, as a person standing in it would see it. Materials are laid
on squares side by side, each 4 m across, seen from above at a slant. With names after `--`, only those are drawn, again if
they had a picture already.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from blender import library  # noqa: E402

SIZE = 640
SAMPLES = 48


def _empty_scene() -> bpy.types.Scene:
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for block in (bpy.data.meshes, bpy.data.materials, bpy.data.images, bpy.data.collections, bpy.data.cameras, bpy.data.lights):
        for item in list(block):
            if item.users == 0:
                block.remove(item)
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = SAMPLES
    scene.cycles.use_denoising = True
    scene.render.resolution_x = scene.render.resolution_y = SIZE
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = False
    scene.view_settings.view_transform = "AgX"
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        for kind in ("OPTIX", "CUDA", "HIP", "ONEAPI"):
            try:
                prefs.compute_device_type = kind
                prefs.get_devices()
                if any(d.type == kind for d in prefs.devices):
                    for d in prefs.devices:
                        d.use = True
                    scene.cycles.device = "GPU"
                    break
            except Exception:
                continue
    except Exception:
        pass
    world = bpy.data.worlds.get("preview_sky") or bpy.data.worlds.new("preview_sky")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.62, 0.68, 0.78, 1)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.8
    scene.world = world
    return scene


def _bounds(scene) -> tuple[Vector, Vector] | None:
    """The box round everything drawn, instanced collections (a town's houses) counted at their places."""
    dg = bpy.context.evaluated_depsgraph_get()
    pts = []
    for inst in dg.object_instances:
        ob = inst.object
        if ob.type in ("MESH", "CURVE", "VOLUME") and ob.name != "preview_floor":
            pts += [inst.matrix_world @ Vector(c) for c in ob.bound_box]
    if not pts:
        return None
    return Vector([min(p[i] for p in pts) for i in range(3)]), Vector([max(p[i] for p in pts) for i in range(3)])


def _camera(scene, at: Vector, look: Vector, lens: float) -> None:
    data = bpy.data.cameras.new("preview_cam")
    data.lens = lens
    data.clip_start, data.clip_end = 0.02, 20000
    cam = bpy.data.objects.new("preview_cam", data)
    scene.collection.objects.link(cam)
    cam.location = at
    cam.rotation_euler = (look - at).to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam


def _light(scene, energy: float = 3.5) -> None:
    sun = bpy.data.objects.new("preview_sun", bpy.data.lights.new("preview_sun", "SUN"))
    sun.data.energy = energy
    sun.data.angle = math.radians(3)
    sun.rotation_euler = (math.radians(50), 0, math.radians(35))
    scene.collection.objects.link(sun)


def _floor(scene, lo: Vector, hi: Vector) -> None:
    span = max((hi - lo).length, 1.0) * 3
    mesh = bpy.data.meshes.new("preview_floor")
    c = Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z - 0.001))
    mesh.from_pydata([c + Vector((sx * span, sy * span, 0)) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))], [], [(0, 1, 2, 3)])
    mat = bpy.data.materials.new("preview_floor")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.42, 0.42, 0.42, 1)
    bsdf.inputs["Roughness"].default_value = 0.8
    mesh.materials.append(mat)
    floor = bpy.data.objects.new("preview_floor", mesh)
    scene.collection.objects.link(floor)


def _materials_scene(scene, entry: dict) -> bool:
    """Each of the entry's kept materials on its own 4 m square, side by side."""
    with bpy.data.libraries.load(entry["where"], link=False) as (src, dst):
        dst.materials = list(src.materials)
    mats = [m for m in dst.materials if m is not None]
    if not mats:
        return False
    for i, mat in enumerate(mats):
        mesh = bpy.data.meshes.new(f"square_{i}")
        x0 = i * 4.4
        mesh.from_pydata([Vector((x0 + dx, dy, 0)) for dx, dy in ((0, 0), (4, 0), (4, 4), (0, 4))], [], [(0, 1, 2, 3)])
        mesh.materials.append(mat)
        scene.collection.objects.link(bpy.data.objects.new(f"square_{i}", mesh))
    mid = Vector(((len(mats) * 4.4 - 0.4) / 2, 2, 0))
    _camera(scene, mid + Vector((0, -len(mats) * 3.2 - 3, len(mats) * 2.4 + 3)), mid, 35)
    _light(scene)
    return True


def draw(name: str, entry: dict) -> Path | None:
    scene = _empty_scene()
    folder = Path(entry["where"]).parent
    if entry["kind"] == "materials":
        if not _materials_scene(scene, entry):
            return None
    else:
        library.bring(name, scene)
        box = _bounds(scene)
        if box is None:
            return None
        lo, hi = box
        mid = (lo + hi) / 2
        size = hi - lo
        if entry["kind"] == "sets":           # from a corner inside the room, at eye height, across to the far corner
            at = Vector((hi.x - 0.25, lo.y + 0.25, lo.z + 1.6))
            _camera(scene, at, Vector((lo.x + 0.4, hi.y - 0.4, lo.z + 0.9)), 14)
            _light(scene, 1.5)
        else:
            radius = max(size.length / 2, 0.05)
            lens = 50
            dist = radius / math.tan(math.atan(18 / lens)) * 1.15
            view = Vector((0.75, -1.0, 0.55)).normalized()
            _camera(scene, mid + view * dist, mid, lens)
            _floor(scene, lo, hi)
            _light(scene)
    path = folder / "preview.png"
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    return path


def main() -> None:
    asked = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    index = library._index()
    for name, entry in index.items():
        if entry.get("kind") == "download" or not str(entry.get("where", "")).endswith(".blend"):
            continue
        if asked and name not in asked:
            continue
        if not asked and (Path(entry["where"]).parent / "preview.png").exists():
            continue
        path = draw(name, entry)
        print(f"PREVIEW {name}: {path or 'nothing to draw'}", flush=True)
        if path:
            fresh = library._index()
            fresh[name]["preview"] = str(path)
            library._write_index(fresh)
            info = Path(entry["where"]).parent / "info.json"
            if info.exists():
                data = json.loads(info.read_text(encoding="utf-8"))
                data["preview"] = str(path)
                info.write_text(json.dumps(data, indent=1), encoding="utf-8")
    print("PREVIEWS DONE", flush=True)


main()

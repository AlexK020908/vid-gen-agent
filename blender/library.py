"""Everything a film makes or brings in, kept on disk for the next one (phase 64). The owner, Nov 19, 2026: "from now on for
everytuhg we redner, keep it in blender or somewhere or on disk so we can reuse, so more thiongs we render in blender, more
things we can reuse".

data/library/<kind>/<name>/ holds what a film made: <name>.blend (the parts standing at the origin, their parents, keys and
the character they rode on left behind), info.json (what it is, its size, where it was made, where it came from, its license
and any credit owed) and, once render_previews has run, preview.png. data/library/index.json lists every entry, the
ready-made downloads too (those stay where they were fetched, under data/assets/, and the entry points there). The asset
scout searches this index before the web.

    from blender import library
    library.keep("small_plane_wing", "props", [wing, stripe, *bits], "A small plane's wing, 11 m...", made_for="poop_jet")
    root, parts = library.bring("small_plane_wing", scene)
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

LIB = Path(__file__).resolve().parents[1] / "data" / "library"
INDEX = LIB / "index.json"


def _index() -> dict:
    return json.loads(INDEX.read_text(encoding="utf-8")) if INDEX.exists() else {}


def _write_index(entries: dict) -> None:
    LIB.mkdir(parents=True, exist_ok=True)
    INDEX.write_text(json.dumps(dict(sorted(entries.items())), indent=1), encoding="utf-8")


def note(name: str, kind: str, about: str, where: str, **facts) -> None:
    """Lists something kept elsewhere on disk (a download under data/assets/) in the library's index."""
    entries = _index()
    entries[name] = {"kind": kind, "about": about, "where": where, **facts, "noted": time.strftime("%Y-%m-%d")}
    _write_index(entries)


def keep(name: str, kind: str, objs, about: str, made_for: str, frame: int | None = None, source: str = "made here",
         license: str = "ours", credit: str = "", materials=()) -> Path:
    """Writes copies of `objs` (as they stand at `frame`, or now), parent-free and unkeyed, gathered about the middle of
    their underside at the origin, to data/library/<kind>/<name>/<name>.blend, with their meshes, materials and images
    (packed images stay packed; files on disk are pointed at by full path). `materials` adds loose materials (an effect's
    shaders). Returns the .blend's path."""
    scene = bpy.context.scene
    if frame is not None:
        scene.frame_set(frame)
    bpy.context.view_layer.update()
    objs = [o for o in objs if o is not None]
    pts = [o.matrix_world @ Vector(c) for o in objs if o.type in ("MESH", "CURVE") for c in o.bound_box]
    if pts:
        lo = Vector([min(p[i] for p in pts) for i in range(3)])
        hi = Vector([max(p[i] for p in pts) for i in range(3)])
        base = Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z))
    else:
        lo = hi = base = Vector()
    copies = []
    for o in objs:
        c = o.copy()
        if c.data is not None and o.type in ("MESH", "CURVE"):
            c.data = o.data.copy() if o.type == "CURVE" else o.data
        c.animation_data_clear()
        c.parent = None
        c.matrix_world = Matrix.Translation(-base) @ o.matrix_world
        c.hide_render = False
        c.name = f"{name}:{o.name}"
        copies.append(c)
    folder = LIB / kind / name
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{name}.blend"
    blocks = set(copies) | {m for m in materials if m}
    bpy.data.libraries.write(str(path), blocks, path_remap="ABSOLUTE", fake_user=True, compress=True)
    for c in copies:
        bpy.data.objects.remove(c)
    dims = [round(v, 3) for v in (hi - lo)]
    faces = sum(len(o.data.polygons) for o in objs if o.type == "MESH")
    info = {"kind": kind, "about": about, "where": str(path), "made_for": made_for, "source": source, "license": license,
            "credit": credit, "size_m": dims, "faces": faces, "parts": [o.name for o in objs],
            "materials": sorted({m.name for o in objs if o.type == "MESH" for m in o.data.materials if m} | {m.name for m in materials if m}),
            "kept": time.strftime("%Y-%m-%d")}
    (folder / "info.json").write_text(json.dumps(info, indent=1), encoding="utf-8")
    entries = _index()
    entries[name] = {k: info[k] for k in ("kind", "about", "where", "made_for", "source", "license", "credit", "size_m", "faces", "kept")}
    _write_index(entries)
    return path


def bring(name: str, scene=None) -> tuple[bpy.types.Object, list[bpy.types.Object]]:
    """A kept entry's parts appended into this scene under one empty named after it, standing at the origin as kept. Only the
    kept parts (named "<name>:<part>") are put in the scene: the models a part instances (a town's houses) come along inside
    their own collections, where the instances find them, and aren't stood at the origin themselves."""
    entry = _index()[name]
    scene = scene or bpy.context.scene
    with bpy.data.libraries.load(entry["where"], link=False) as (src, dst):
        dst.objects = [n for n in src.objects if n.startswith(f"{name}:")]
    root = bpy.data.objects.new(name, None)
    scene.collection.objects.link(root)
    got = [o for o in dst.objects if o is not None]
    for o in got:
        scene.collection.objects.link(o)
        if o.parent is None:
            o.parent = root
    return root, got

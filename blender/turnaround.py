"""A machine's turnaround sheet: every step from four sides (front, three-quarter left, side, three-quarter right)
and, when any part is cut by cutaways, a cut-open front view. Also the overlap check at every step.

Writes <out>/step<N>_<view>.png and <out>/turnaround.json: the steps, the views and the problems found.
"""
from __future__ import annotations

import json
from pathlib import Path

import bpy

from blender import envs, framing, kit, look, materials, shapes

VIEWS = {"front": (0, -1, 0.3), "left": (-0.75, -0.75, 0.35), "side": (1, 0, 0.3), "right": (0.75, -0.75, 0.35)}


def run(job: dict, out: Path, scene) -> dict:
    spec = job["spec"]
    envs.studio()
    model = kit.Model(spec)
    cut_parts = [model.objects[p] for p, part in model.parts.items() if part.get("cut")]
    cam, aim = look.camera(scene, at=(0, -5, 1), look_at=(0, 0, 0), lens=50, fstop=0)
    steps = len(spec.get("steps") or []) or 1
    problems, shots = [], []
    for step in range(1, steps + 1):
        model.show_step(step)
        bpy.context.view_layer.update()
        problems += [f"step {step}: {p}" for p in kit.overlaps(model, step)]
        skip = {model.objects[p] for p in job.get("unframed") or [] if p in model.objects}   # e.g. 30 m of pile
        objs = [o for o in model.visible_objects() if o not in skip]
        if not objs:
            problems.append(f"step {step}: nothing is there")
            continue
        views = dict(VIEWS)
        cutter = None
        if any(not o.hide_render for o in cut_parts):
            lo, hi = framing.bounds(objs)
            cutter = shapes.cut_away([o for o in cut_parts if not o.hide_render], keep_y_above=(lo.y + hi.y) / 2,
                                     name=f"Cut{step}", material=materials.hatch_for(max(hi - lo)))
            cutter.hide_viewport = True
            views = {"cut": VIEWS["front"], **views}
        for view, direction in views.items():
            for obj in cut_parts:
                mod = obj.modifiers.get("Cutaway")
                if mod:
                    mod.show_render = mod.show_viewport = view == "cut"
            bpy.context.view_layer.update()
            framing.fit(cam, aim, objs, direction=direction, fill=0.85)
            scene.render.filepath = str(out / f"step{step}_{view}.png")
            bpy.ops.render.render(write_still=True)
            shots.append({"step": step, "view": view, "file": f"step{step}_{view}.png"})
            print(f"FRAME {len(shots)}/?", flush=True)
        for obj in cut_parts:
            for mod in list(obj.modifiers):
                if mod.name == "Cutaway":
                    obj.modifiers.remove(mod)
        if cutter is not None:
            bpy.data.objects.remove(cutter, do_unlink=True)
    result = {"name": spec["name"], "steps": spec.get("steps") or [], "shots": shots, "problems": problems}
    (out / "turnaround.json").write_text(json.dumps(result, indent=1), encoding="utf-8")
    return result

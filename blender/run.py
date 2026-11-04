"""Blender's entry point: `blender -b --factory-startup --python-exit-code 1 -P blender/run.py -- <job.json>`.

The job (written by render/blender_render.py):
  kind      "turnaround" (a machine's sheet, blender/turnaround.py, with `spec`), "pose" (a `spec` with joints
            `set`, writing pose.json: where every part is), "segment" (a timeline, blender/shots.py, with
            `timeline` and `specs`, and `people` for any in it; frames are numbered for the whole short), "person"
            (makes and saves a person, blender/humgen.py), "portraits" (a saved person's sheet, blender/portraits.py),
            "stage" (a scene, blender/stage.py, with `scene`, `folders` and `catalog`, and `things`: each thing's folder),
            "thing" (makes and saves a thing, blender/things.py, with `spec` and `source`), "thing_sheet" (a saved thing's
            sheet, with `thing`: its folder), or a look-test shot (the default)
  shot      which look-test shot to build (looktest.SHOTS, charactertest.SHOTS)
  person    for a character shot or portraits, the folder of the saved person
  people    for a segment, each person's name in its timeline -> the folder of the saved person
  out       the folder for the frames (f_0001.png ...) and tracks.json
  size, fps, samples
  engine    optional, "cycles" in place of EEVEE
  frames    optional list of frame numbers to render instead of the whole shot (a quick look)
  textures  Poly Haven texture id -> {diff, rough, nor_gl} paths
  hdris     Poly Haven HDRI id -> path

It prints "FRAME i/n" after each frame for the progress line. tracks.json holds the anchors' screen positions for
every frame, the shot's events, and how long each frame took to render.
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import bpy  # noqa: E402

from blender import (charactertest, envs, humgen, kit, look, looktest, materials, portraits, shots, stage,  # noqa: E402
                     things, tracks, turnaround)


def _empty_scene():
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for block in (bpy.data.meshes, bpy.data.lights, bpy.data.cameras, bpy.data.materials):
        for item in list(block):
            block.remove(item)


def main() -> None:
    job = json.loads(Path(sys.argv[sys.argv.index("--") + 1]).read_text(encoding="utf-8"))
    out = Path(job["out"])
    out.mkdir(parents=True, exist_ok=True)
    materials.ASSETS.update(job.get("textures") or {})
    envs.HDRIS.update(job.get("hdris") or {})
    _empty_scene()
    if job.get("kind") == "person":
        humgen.build(job, out)
        return
    if job.get("kind") == "thing":
        things.make(job, out)
        return
    scene = bpy.context.scene
    fps = int(job.get("fps", 30))
    look.setup(scene, size=tuple(job.get("size", (1080, 1920))), fps=fps, samples=int(job.get("samples", 32)),
               **({"look": job["look"]} if job.get("look") else {}),
               **({"engine": job["engine"]} if job.get("engine") else {}))
    charactertest.PERSON = job.get("person") or ""
    if job.get("kind") == "portraits":
        portraits.run(job, out, scene)
        return
    if job.get("kind") == "thing_sheet":
        things.sheet(job, out, scene)
        return
    if job.get("kind") == "turnaround":
        turnaround.run(job, out, scene)
        return
    if job.get("kind") == "pose":   # set joints, say where every part ends up (for checks and tests)
        model = kit.Model(job["spec"])
        for pid, value in (job.get("set") or {}).items():
            model.set(pid, value)
        bpy.context.view_layer.update()
        (out / "pose.json").write_text(json.dumps({
            "values": model.values,
            "at": {pid: [round(c, 5) for c in obj.matrix_world.translation] for pid, obj in model.objects.items()},
        }), encoding="utf-8")
        return
    if job.get("kind") == "stage":
        shot = stage.run(job, fps)
        first, last = 1, shot["frames"]
        scene.frame_start, scene.frame_end = first, last
        track, events = {}, shot["events"]
    elif job.get("kind") == "segment":
        seg = shots.run(job, out, scene)
        first, last = seg["f0"], seg["f1"]
        track, events = seg["anchors"], seg["events"]
    else:
        shot = {**looktest.SHOTS, **charactertest.SHOTS}[job["shot"]](fps)
        first, last = 1, shot["frames"]
        scene.frame_start, scene.frame_end = first, last
        track, events = tracks.export(scene, shot["anchors"], first, last), shot["events"]
    frames = last - first + 1
    wanted = job.get("frames") or list(range(first, last + 1))
    times: list[float] = []
    started = [0.0]
    bpy.app.handlers.render_pre.append(lambda *_: started.__setitem__(0, time.perf_counter()))

    def done(*_):
        times.append(round(time.perf_counter() - started[0], 3))
        print(f"FRAME {len(times)}/{len(wanted)}", flush=True)

    bpy.app.handlers.render_post.append(done)
    scene.render.filepath = str(out / "f_")
    if job.get("render", True):
        if wanted == list(range(first, last + 1)):
            bpy.ops.render.render(animation=True)
        else:
            for f in wanted:
                scene.frame_start = scene.frame_end = f
                bpy.ops.render.render(animation=True)
        scene.frame_start, scene.frame_end = first, last

    (out / "tracks.json").write_text(json.dumps({
        "fps": fps, "first": first, "frames": frames, "size": [scene.render.resolution_x, scene.render.resolution_y],
        "anchors": track, "events": events, "rendered": wanted if job.get("render", True) else [],
        "render_s": times,
    }), encoding="utf-8")


main()

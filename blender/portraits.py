"""A person's portrait sheet, to judge them before any shot: the face from three sides, the full body, and a few
expressions. Runs with the add-on off, as every render does, so it also proves the saved person works alone.

Writes <out>/<view>.png and <out>/portraits.json.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import bpy
from mathutils import Vector

from blender import envs, look, people

# name, how much of them is in the picture, the camera's angle round them in degrees, the expression
VIEWS = (("front", "face", 0, None), ("three quarter left", "face", -38, None), ("three quarter right", "face", 38, None),
         ("full body", "body", 0, None), *((name, "face", 0, name) for name in (
             "happy", "surprised", "angry", "sad", "shocked", "scared", "disgusted", "thinking")))
LENS = 85.0


def run(job: dict, out: Path, scene) -> dict:
    envs.sky_set()
    scene.render.use_motion_blur = False
    person = people.Person(job["person"])
    eyes = person.middle(person.eyes)
    envs.portrait_lights(eyes)
    cam, aim = look.camera(scene, (eyes.x, eyes.y - 3, eyes.z), eyes, lens=LENS, fstop=0)
    shots = []
    for i, (view, frame_on, angle, expression) in enumerate(VIEWS, start=1):
        person.expression(i, expression)
        scene.frame_set(i)
        if frame_on == "face":
            target, height = eyes - Vector((0, 0, 0.04)), 0.42
        else:                              # the top of the head is about 15 cm above the eyes; the picture is narrow, and
            target = Vector((eyes.x, eyes.y, (eyes.z + 0.15) / 2))   # it has to fit the arms held out from the sides
            height = (eyes.z + 0.15) * 1.6
        distance = height * LENS / 24
        turn = math.radians(angle)
        aim.location = target
        cam.location = target + Vector((math.sin(turn) * distance, -math.cos(turn) * distance, 0))
        cam.data.clip_start = distance / 100
        bpy.context.view_layer.update()
        name = f"{i:02d}_{view.replace(' ', '_')}.png"
        scene.render.filepath = str(out / name)
        bpy.ops.render.render(write_still=True)
        shots.append({"view": view, "file": name})
        print(f"FRAME {i}/{len(VIEWS)}", flush=True)
    result = {"shots": shots}
    (out / "portraits.json").write_text(json.dumps(result, indent=1), encoding="utf-8")
    return result

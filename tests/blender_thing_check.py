"""Run inside Blender: a thing staged by the same code every scene uses, on a stand-in person, and checked by where things end
up: it flies nose first, banks into its turn, lands on the top of their head, and its wings really flap.
Writes what it found to <folder>/out.json.
"""
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from blender import look, stage  # noqa: E402

job = json.loads(Path(sys.argv[sys.argv.index("--") + 1]).read_text(encoding="utf-8"))
folder = Path(job["out"])
rock = job["scene"].pop("rock")      # a second copy of the thing, on the floor, tipping about its underside
job["scene"]["cast"]["other"] = {"type": "prop", "prop": "flyer", "at": [-3, 0, 0], "facing": 0}
job["scene"]["happens"].append(rock)
for default in list(bpy.data.objects):
    bpy.data.objects.remove(default, do_unlink=True)
scene = bpy.context.scene
look.setup(scene, size=(108, 192), fps=30, samples=1)
s = stage.Stage(job["scene"], job["folders"], job["catalog"], 30, job["things"])
s.run()

bird = s.props["bird"]
root, thing = bird["root"], bird["thing"]
go = next(e for e in job["scene"]["happens"] if e["do"] == "go")
arrive = s.frame(go["t"]) + round(go["over"] * 30)


def wing_at(f):
    scene.frame_set(f)
    bpy.context.view_layer.update()
    rig = thing.saved["WingRig"]
    return (rig.matrix_world @ rig.pose.bones["wing.L"].tail).copy()


def where(f):
    scene.frame_set(f)
    bpy.context.view_layer.update()
    return root.matrix_world.translation.copy(), (root.matrix_world.to_3x3() @ Vector((0, -1, 0))).normalized()


# flying: the nose points where it's going, and it leans into the turn
middle = s.frame(go["t"]) + round(go["over"] * 15)
a, nose = where(middle)
b, _ = where(middle + 1)
scene.frame_set(middle)
bpy.context.view_layer.update()
banked = (root.matrix_world.to_3x3() @ Vector((0, 0, 1))).normalized()
wing_a, wing_b = wing_at(middle), wing_at(middle + 5)
scene.frame_set(arrive)
bpy.context.view_layer.update()
top = s._top_of_head(s.people["walt"], s._on_person("walt", "eyes") - s._directions("walt")[0] * 0.03)
landed, _ = where(arrive)
half = thing.size.z / 2
ride = root.constraints[0]
riding = []
for f in (arrive - 1, arrive):
    scene.frame_set(f)
    riding.append(ride.influence)

other = s.props["other"]["root"]


def other_at(f):
    scene.frame_set(f)
    bpy.context.view_layer.update()
    return other.matrix_world.translation.copy(), other.matrix_world.to_quaternion()


rest_place, rest_turn = other_at(1)
first_snap = 1 + round(0.9 * 30 / 3)
_, drawn = other_at(1 + round(0.9 * 30 / 3 * 0.72))
home_place, home_turn = other_at(first_snap)
rock_found = {"back_deg": math.degrees(rest_turn.rotation_difference(drawn).angle),
              "home_gap": (home_place - rest_place).length + rest_turn.rotation_difference(home_turn).angle}

(folder / "out.json").write_text(json.dumps({
    "rock": rock_found,
    "size": list(thing.size),
    "along_line": (b - a).normalized().dot(nose),
    "bank": (Vector((0, 0, 1)) - banked).length,
    "wing_moved": (wing_a - wing_b).length,
    "gap_above_head": (landed.z - half) - top.z,
    "gap_across": (Vector((landed.x, landed.y)) - Vector((top.x, top.y))).length,
    "rides_on": ride.target.parent_bone,
    "riding": riding,
}), encoding="utf-8")

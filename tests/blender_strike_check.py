"""Run inside Blender: a person swinging a held tool at the side of a thing, staged by the same code every scene uses, and checked
by where things end up: its working end lands on the surface, flat, the hand holding it has closed, and someone standing too
far away is refused. Writes what it found to <folder>/out.json.
"""
import json
import sys
from pathlib import Path

import bpy
from mathutils import Quaternion, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from blender import look, stage  # noqa: E402

job = json.loads(Path(sys.argv[sys.argv.index("--") + 1]).read_text(encoding="utf-8"))
folder = Path(job["out"])
for default in list(bpy.data.objects):
    bpy.data.objects.remove(default, do_unlink=True)
scene = bpy.context.scene
look.setup(scene, size=(108, 192), fps=30, samples=1)
s = stage.Stage(job["scene"], job["folders"], job["catalog"], 30, job["things"])
try:
    s.run()
except ValueError as e:
    (folder / "out.json").write_text(json.dumps({"refused": str(e)}), encoding="utf-8")
    sys.exit(0)

strike = next(e for e in job["scene"]["happens"] if e["do"] == "strike")
hit = s.frame(strike["t"])
scene.frame_set(hit)
bpy.context.view_layer.update()
tool = s.props["tool"]
root, thing = tool["root"], tool["thing"]
turn = root.matrix_world.to_quaternion()
reach = thing.spot("end") - thing.spot("grip")
end = root.matrix_world.translation + turn @ reach
person = s.people["walt"]
shoulder = person.rig.matrix_world @ person.bone("upper_arm.R").head
side = s._side_facing("trunk", float(strike["along"]), shoulder)
front = turn @ Vector((reach.x, reach.y, 0)).normalized()      # the way its working end sticks out from the handle is what lands
toward_target = (side - shoulder)
toward_target.z = 0
wrist_gap = ((person.rig.matrix_world @ person.bone("hand.R").head) - person.holds["R"].matrix_world.translation).length
scene.frame_set(1)
bpy.context.view_layer.update()
right = person.rig.pose.bones[person.bones["thumb.01.R"]].rotation_quaternion
left = person.rig.pose.bones[person.bones["thumb.01.L"]].rotation_quaternion
mirrored = Quaternion((left.w, left.x, -left.y, -left.z))
(folder / "out.json").write_text(json.dumps({
    "gap": (end - side).length,
    "faces_target": front.dot(toward_target.normalized()),
    "handle_up": (turn @ Vector((0, 0, 1))).z,
    "thumb_closed_deg": right.rotation_difference(mirrored).angle * 57.2958,
    "wrist_gap": wrist_gap,
    "drew_back": len([leg for leg in tool["path"] if not leg.get("blow")]) == 1,
}), encoding="utf-8")

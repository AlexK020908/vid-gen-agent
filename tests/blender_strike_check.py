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
end = root.matrix_world.translation + turn @ (thing.spot("end") - thing.spot("grip"))
shoulder = s._in_their_terms("walt", (stage.SHOULDER[0], stage.SHOULDER[1], stage.SHOULDER[2]))
side = s._side_facing("trunk", float(strike["along"]), shoulder)
front = turn @ Vector((0, -1, 0))
toward_target = (side - shoulder)
toward_target.z = 0
person = s.people["walt"]
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
}), encoding="utf-8")

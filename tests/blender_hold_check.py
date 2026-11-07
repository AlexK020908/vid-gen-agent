"""Run inside Blender: a saved person's hand locked on a sword, and a glow on the skin, checked by where things end up. The
sword is moved between two places within reach, and the hand has to go with it, palm on the grip, fingers the sword's way.
Writes what it found to <folder>/out.json.
"""
import json
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Quaternion, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from blender import people  # noqa: E402

folder = Path(sys.argv[sys.argv.index("--") + 1])
for default in list(bpy.data.objects):
    bpy.data.objects.remove(default, do_unlink=True)
person = people.Person(str(folder))
sword = bpy.data.objects.new("Sword", None)
bpy.context.scene.collection.objects.link(sword)
wrist = person.hold("R", sword, radius=0.014)


def place(palm, blade, fingers):
    z = Vector(blade).normalized()
    y = (Vector(fingers) - z * Vector(fingers).dot(z)).normalized()
    sword.matrix_world = Matrix.Translation(palm) @ Matrix((y.cross(z), y, z)).transposed().to_4x4()
    bpy.context.view_layer.update()
    hand = person.bone("hand.R")
    head = person.rig.matrix_world @ hand.head
    turned = (person.rig.matrix_world @ hand.matrix).to_quaternion().rotation_difference(sword.matrix_world.to_quaternion())
    return {"gap": (head - sword.matrix_world @ wrist).length, "turned": list(turned), "wrist_behind": (head - Vector(palm)).dot(y)}


found = {"near": place((-0.25, -0.30, 0.95), (0.8, -0.3, 0.5), (-0.1, -1, -0.5)),
         "far": place((-0.38, -0.28, 1.15), (0.2, 0.3, 0.9), (0, -1, -0.3))}
socket = person.glow(Vector((0, -0.05, 1.55)), 0.08, (0, 1, 0))
socket.default_value = 1.0
socket.keyframe_insert("default_value", frame=3)
tree = person.body.data.materials[0].node_tree
surface = next(n for n in tree.nodes if n.type == "OUTPUT_MATERIAL").inputs["Surface"].links[0].from_node
found["glow_node"] = surface.type
found["fist_thin"] = person.fist("R", 0.008)
found["fist_thick"] = person.fist("R", 0.03)
along, grip, palm, lies = person._hand_axes("R")
found["handle_clear"] = {name: min(((p - (lies + palm * 0.014)) - grip * (p - (lies + palm * 0.014)).dot(grip)).length for p in person._finger_line(name, "R", bends)) for name, bends in person.fist("R", 0.014).items()}
flipped = person.hold("L", sword, spin=Quaternion((0, 0, 1), 3.14159265), radius=0.014)
plain = person.hold("L", sword, radius=0.014)
found["flipped_wrist"] = [list(flipped), list(plain)]
(folder / "out.json").write_text(json.dumps(found), encoding="utf-8")

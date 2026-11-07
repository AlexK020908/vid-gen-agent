"""Run inside Blender: a stand-in person, saved as blender/humgen.py saves a real one, so the render side can be tested
without the paid add-on. A ball for a head with two eyes, teeth, a rig with the bones the shots use, and face keys, one
of them driven by a bone as the add-on's are.

Used two ways: `blender -b -P blender_fake_person.py -- <folder>` writes the files, and the stub add-on in
tests/stub_humgen/ imports build() to play Human.from_preset().
"""
import json
import sys
from pathlib import Path

import bmesh
import bpy


def _ball(name, r, at, color):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=16, radius=r)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = at
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1)
    mat.use_nodes = True
    mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (*color, 1)
    mesh.materials.append(mat)
    return obj


def _key(obj, name, move):
    if not obj.data.shape_keys:
        obj.shape_key_add(name="Basis")
    block = obj.shape_key_add(name=name)
    for point, vert in zip(block.data, obj.data.vertices):
        point.co = vert.co + move(vert.co)
    block.value = 0.0         # a face at rest, as a real person's is: left on, these keys shrink the head to a tiny ball
    return block


def build():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()
    arm = bpy.data.armatures.new("Fake")
    rig = bpy.data.objects.new("FakeRig", arm)
    bpy.context.scene.collection.objects.link(rig)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")
    for name, head, tail in (("head", (0, 0, 1.5), (0, 0, 1.75)), ("eyeball_lookat_master", (0, -0.16, 1.65), (0, -0.2, 1.65)),
                             ("jaw_open_lt_rt_frwd", (0, 0, 1.3), (0, 0, 1.35))):
        bone = arm.edit_bones.new(name)
        bone.head, bone.tail = head, tail
    for name, head, tail in (("spine", (0, 0, 0.8), (0, 0, 0.95)), ("spine.001", (0, 0, 0.95), (0, 0, 1.05)),
                             ("spine.002", (0, 0, 1.05), (0, 0, 1.15)), ("spine.003", (0, 0, 1.15), (0, 0, 1.3)),
                             ("neck", (0, 0, 1.3), (0, 0, 1.45)), ("thigh.L", (0.1, 0, 0.85), (0.1, 0, 0.45)),
                             ("thigh.R", (-0.1, 0, 0.85), (-0.1, 0, 0.45))):
        bone = arm.edit_bones.new(name)
        bone.head, bone.tail = head, tail
    for side, x in (("L", 1), ("R", -1)):                 # arms in an A-pose, bent a little, so they can reach
        before = None
        for name, head, tail in ((f"upper_arm.{side}", (0.17 * x, 0.05, 1.25), (0.32 * x, 0.03, 1.07)),
                                 (f"forearm.{side}", (0.32 * x, 0.03, 1.07), (0.46 * x, -0.1, 0.95)),
                                 (f"hand.{side}", (0.46 * x, -0.1, 0.95), (0.505 * x, -0.145, 0.905)),
                                 (f"thumb.01.{side}", (0.47 * x, -0.13, 0.95), (0.49 * x, -0.2, 0.93))):
            bone = arm.edit_bones.new(name)
            bone.head, bone.tail = head, tail
            if name.startswith("thumb"):
                bone.parent = arm.edit_bones[f"hand.{side}"]
            elif before is not None:
                bone.parent = before
            before = bone
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.mode_set(mode="EDIT")
    for side, x in (("L", 1), ("R", -1)):                 # fingers, joint by joint, so a hand can close on what it holds
        shin = arm.edit_bones.new(f"shin.{side}")
        shin.head, shin.tail, shin.parent = (0.1 * x, 0, 0.45), (0.1 * x, 0, 0.1), arm.edit_bones[f"thigh.{side}"]
        foot = arm.edit_bones.new(f"foot.{side}")
        foot.head, foot.tail, foot.parent = (0.1 * x, 0, 0.1), (0.1 * x, -0.12, 0.02), shin
        for name, spread in (("f_index", 0.03), ("f_middle", 0.01), ("f_ring", -0.01), ("f_pinky", -0.03)):
            at = (0.505 * x, -0.145 + spread * 0.7, 0.905 - spread * 0.7)    # the knuckles lie across the hand
            parent = arm.edit_bones[f"hand.{side}"]
            for joint in (1, 2, 3):
                bone = arm.edit_bones.new(f"{name}.0{joint}.{side}")
                tail = (at[0] + 0.02 * x, at[1] - 0.02, at[2] - 0.02)
                bone.head, bone.tail, bone.parent = at, tail, parent
                at, parent = tail, bone
        parent = arm.edit_bones[f"thumb.01.{side}"]
        at = parent.tail.copy()
        for joint in (2, 3):
            bone = arm.edit_bones.new(f"thumb.0{joint}.{side}")
            tail = (at[0] + 0.005 * x, at[1] - 0.025, at[2] - 0.005)
            bone.head, bone.tail, bone.parent = at, tail, parent
            at, parent = tail, bone
    bpy.ops.object.mode_set(mode="OBJECT")
    for bone in rig.pose.bones:
        bone["original_name"] = bone.name

    body = _ball("FakeBody", 0.12, (0, 0, 1.6), (0.7, 0.5, 0.4))
    eyes = _ball("FakeEyes", 0.03, (0, -0.1, 1.65), (0.9, 0.9, 0.9))
    upper = _ball("FakeUpper", 0.02, (0, -0.1, 1.55), (0.9, 0.9, 0.85))
    lower = _ball("FakeLower", 0.02, (0, -0.1, 1.52), (0.9, 0.9, 0.85))
    for obj in (body, eyes, upper, lower):
        obj.parent = rig
    for name in ("eyeBlink_L", "eyeBlink_R", "eyeWide_L", "eyeWide_R"):
        _key(body, name, lambda co: co * -0.3)
    jaw = _key(body, "jawOpen", lambda co: co * 0.5)
    _key(lower, "jawOpen", lambda co: co * 0 + type(co)((0, 0, -0.03)))
    driver = jaw.driver_add("value").driver   # held at nothing by a bone that never moves: a key has to beat it
    var = driver.variables.new()
    var.type = "TRANSFORMS"
    var.targets[0].id = rig
    var.targets[0].bone_target = "jaw_open_lt_rt_frwd"
    var.targets[0].transform_type = "LOC_Z"
    var.targets[0].transform_space = "LOCAL_SPACE"
    driver.expression = "var"
    return rig, body, eyes, upper, lower


def save(out: Path) -> None:
    rig, body, eyes, upper, lower = build()
    manifest = {
        "spec": {"fake": True}, "rig": rig.name, "body": body.name, "eyes": eyes.name, "upper_teeth": upper.name,
        "lower_teeth": lower.name, "bones": {b.name: b.name for b in rig.pose.bones},
        "face_keys": [k.name for k in body.data.shape_keys.key_blocks if k.name != "Basis"],
    }
    out.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(out / "person.blend"))
    (out / "person.json").write_text(json.dumps(manifest), encoding="utf-8")


if __name__ == "__main__" and "--" in sys.argv:
    save(Path(sys.argv[sys.argv.index("--") + 1]))

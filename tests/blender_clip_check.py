"""Run inside Blender: a body clip retargeted from one skeleton to another, checked by where the bones end up. The clip's
skeleton stands in a T-pose and lowers its left arm straight down, dropping its hips. Ours stands in an A-pose, with
other bone names, shorter legs, and a palm bone the clip doesn't have. Writes what it found to <out>.json.
"""
import json
import math
import sys
from pathlib import Path
from types import SimpleNamespace

import bpy
from mathutils import Quaternion, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from blender import clips  # noqa: E402

folder = Path(sys.argv[sys.argv.index("--") + 1])
for default in list(bpy.data.objects):      # the factory scene's cube, camera and light
    bpy.data.objects.remove(default, do_unlink=True)


def armature(name, bones):
    data = bpy.data.armatures.new(name)
    rig = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(rig)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode="EDIT")
    made = {}
    for bone, head, tail, parent in bones:
        edit = data.edit_bones.new(bone)
        edit.head, edit.tail = head, tail
        if parent:
            edit.parent = made[parent]
        made[bone] = edit
    bpy.ops.object.mode_set(mode="OBJECT")
    return rig


def export(rig, path, animated):
    bpy.ops.object.select_all(action="DESELECT")
    rig.select_set(True)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.export_scene.fbx(filepath=str(path), use_selection=True, object_types={"ARMATURE"}, add_leaf_bones=False,
                             bake_anim=animated, bake_anim_use_nla_strips=False, bake_anim_use_all_actions=False,
                             primary_bone_axis="Y", secondary_bone_axis="X")


theirs = armature("Theirs", [("pelvis", (0, 0, 1.0), (0, 0, 1.2), None), ("thigh_l", (0.1, 0, 1.0), (0.1, 0, 0.5), "pelvis"),
                             ("upperarm_l", (0.2, 0, 1.5), (0.5, 0, 1.5), "pelvis"),
                             ("hand_l", (0.5, 0, 1.5), (0.7, 0, 1.5), "upperarm_l")])
reference = folder / "reference.fbx"
export(theirs, reference, False)
arm, hips = theirs.pose.bones["upperarm_l"], theirs.pose.bones["pelvis"]
arm.rotation_mode = "QUATERNION"
turn = (arm.bone.matrix_local.to_3x3().inverted() @ Vector((0, 1, 0))).normalized()   # about the world's y: +x to -z
for f, angle, drop in ((1, 0.0, 0.0), (10, 90.0, 0.2)):
    arm.rotation_quaternion = Quaternion(turn, math.radians(angle))
    arm.keyframe_insert("rotation_quaternion", frame=f)
    hips.location = hips.bone.matrix_local.to_3x3().inverted() @ Vector((0, 0, -drop))
    hips.keyframe_insert("location", frame=f)
bpy.context.scene.frame_start, bpy.context.scene.frame_end = 1, 10
clip_file = folder / "clip.fbx"
export(theirs, clip_file, True)
bpy.data.objects.remove(theirs, do_unlink=True)

ours = armature("Ours", [("spine", (0, 0, 0.8), (0, 0, 1.0), None), ("thigh.L", (0.1, 0, 0.8), (0.1, 0, 0.4), "spine"),
                         ("upper_arm.L", (0.2, 0, 1.3), (0.4, 0, 1.1), "spine"),
                         ("hand.L", (0.4, 0, 1.1), (0.5, 0, 1.0), "upper_arm.L"),
                         ("palm.L", (0.5, 0, 1.0), (0.55, 0, 0.95), "hand.L")])
person = SimpleNamespace(rig=ours, bones={b.name: b.name for b in ours.pose.bones},
                         bone=lambda name: ours.pose.bones[name])
scene = bpy.context.scene
scene.render.fps = 30
clip = clips.read({"file": str(clip_file), "action": None, "reference": {"file": str(reference), "action": None}})
left = [o.name for o in bpy.data.objects]
solver = clips.Solver(person)
after = solver.play(clip, 1, blend=0)
scene.frame_set(after - 1)
bpy.context.view_layer.update()


def direction(name):
    bone = ours.pose.bones[name]
    return list((bone.tail - bone.head).normalized())


(folder / "out.json").write_text(json.dumps({
    "frames": clip["frames"], "objects_left": left, "after": after, "fps": scene.render.fps,
    "upper_arm": direction("upper_arm.L"), "hand": direction("hand.L"), "palm": direction("palm.L"),
    "spine_z": ours.pose.bones["spine"].head.z,
}), encoding="utf-8")

"""Run inside Blender: a stand-in winged thing, written out as a GLB, as a file from anywhere comes. A box for a body and two
boxes for wings on bones, far bigger than real and lying on its side's axis, with one clip that flaps the wings.

`blender -b -P blender_fake_thing.py -- <out.glb>`
"""
import sys

import bmesh
import bpy
from mathutils import Euler

out = sys.argv[sys.argv.index("--") + 1]
for default in list(bpy.data.objects):
    bpy.data.objects.remove(default, do_unlink=True)
arm = bpy.data.armatures.new("Wings")
rig = bpy.data.objects.new("WingRig", arm)
bpy.context.scene.collection.objects.link(rig)
bpy.context.view_layer.objects.active = rig
bpy.ops.object.mode_set(mode="EDIT")
for name, head, tail in (("body", (0, 0, 0), (0, 0, 2)), ("wing.L", (1, 0, 1), (10, 0, 1)), ("wing.R", (-1, 0, 1), (-10, 0, 1))):
    bone = arm.edit_bones.new(name)
    bone.head, bone.tail = head, tail
arm.edit_bones["wing.L"].parent = arm.edit_bones["body"]
arm.edit_bones["wing.R"].parent = arm.edit_bones["body"]
bpy.ops.object.mode_set(mode="OBJECT")

bm = bmesh.new()
groups = {"body": ((0, 0, 1), (2, 2, 2)), "wing.L": ((5.5, 0, 1), (9, 2, 0.2)), "wing.R": ((-5.5, 0, 1), (9, 2, 0.2))}
for at, size in groups.values():
    made = bmesh.ops.create_cube(bm, size=1.0)["verts"]
    for vert in made:
        vert.co = (vert.co.x * size[0] + at[0], vert.co.y * size[1] + at[1], vert.co.z * size[2] + at[2])
mesh = bpy.data.meshes.new("Flyer")
bm.to_mesh(mesh)
bm.free()
obj = bpy.data.objects.new("Flyer", mesh)
bpy.context.scene.collection.objects.link(obj)
obj.parent = rig
obj.modifiers.new("Rig", "ARMATURE").object = rig
for name in groups:
    obj.vertex_groups.new(name=name)
for vert in mesh.vertices:
    x = vert.co.x
    name = "wing.L" if x > 1.01 else "wing.R" if x < -1.01 else "body"
    obj.vertex_groups[name].add([vert.index], 1.0, "REPLACE")
mat = bpy.data.materials.new("Feathers")
mat.use_nodes = True
mesh.materials.append(mat)

rig.animation_data_create()
action = bpy.data.actions.new("Flap")
rig.animation_data.action = action
for frame, angle in ((1, -0.6), (11, 0.6), (21, -0.6)):
    for name, sign in (("wing.L", 1), ("wing.R", -1)):
        bone = rig.pose.bones[name]
        bone.rotation_mode = "XYZ"
        bone.rotation_euler = Euler((0, 0, angle * sign))
        bone.keyframe_insert("rotation_euler", frame=frame)
bpy.ops.export_scene.gltf(filepath=out, export_format="GLB", export_animations=True, export_force_sampling=True)

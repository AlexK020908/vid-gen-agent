"""Where each anchor (a point on a part, for a callout's dot) is on screen in every frame, and whether it's seen.

A point is seen when it's in front of the camera, inside the picture, and nothing rendered stands between it and
the camera (a ray from the camera that hits another part first hides it; the cutaway's hidden cutter doesn't, nor
does a part of the same `group`, a custom property: the air balls are one group).
Positions are fractions of the picture, x from the left and y from the top, as the overlay draws them.
"""
from __future__ import annotations

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector


def _seen(scene, depsgraph, cam_pos: Vector, point: Vector, owner) -> bool:
    direction = point - cam_pos
    dist = direction.length
    direction.normalize()
    origin = cam_pos.copy()
    travelled = 0.0
    while travelled < dist - 1e-3:
        hit, loc, _normal, _index, obj, _matrix = scene.ray_cast(depsgraph, origin, direction,
                                                                 distance=dist - travelled)
        if not hit:
            return True
        if obj is not None and (obj.original is owner or obj.original.parent is owner):
            return True
        group = owner.get("group")
        if obj is not None and group and obj.original.get("group") == group:
            return True   # one air ball in front of another is still the air the label points at
        if obj is not None and not obj.original.hide_render:
            return False
        step = (loc - origin).length + 1e-3   # hidden helper (the cutter): look past it
        travelled += step
        origin = loc + direction * 1e-3
    return True


def export(scene, anchors: dict[str, tuple], first: int, last: int) -> dict:
    """`anchors`: name -> (object, local offset). Returns {name: [[x, y, seen], ...]} for frames first..last."""
    cam = scene.camera
    out = {name: [] for name in anchors}
    for frame in range(first, last + 1):
        scene.frame_set(frame)
        depsgraph = bpy.context.evaluated_depsgraph_get()
        cam_pos = cam.matrix_world.translation.copy()
        for name, (obj, offset) in anchors.items():
            point = obj.matrix_world @ Vector(offset)
            co = world_to_camera_view(scene, cam, point)
            inside = co.z > 0 and 0 <= co.x <= 1 and 0 <= co.y <= 1
            seen = inside and _seen(scene, depsgraph, cam_pos, point, obj)
            out[name].append([round(co.x, 4), round(1 - co.y, 4), bool(seen)])
    return out

"""Aim and place a camera so given objects fill the picture, seen from a direction."""
from __future__ import annotations

import math

from mathutils import Vector


def bounds(objs):
    """The world-space box around `objs` (their evaluated shapes, cutaways included): (min, max) corners."""
    lo = Vector((math.inf,) * 3)
    hi = Vector((-math.inf,) * 3)
    for obj in objs:
        for corner in obj.bound_box:
            p = obj.matrix_world @ Vector(corner)
            lo = Vector(map(min, lo, p))
            hi = Vector(map(max, hi, p))
    return lo, hi


def corners(lo, hi):
    return [Vector((x, y, z)) for x in (lo.x, hi.x) for y in (lo.y, hi.y) for z in (lo.z, hi.z)]


def fit(cam, aim, objs, direction=(0, -1, 0.35), fill=0.8, target=None) -> float:
    """Put `cam` along `direction` from the middle of `objs` (or `target`), just far enough that every corner of
    their box is inside `fill` of the picture, and aim it there through `aim` (the empty it tracks). The picture
    is 9:16 with the sensor fitted vertically. Returns the distance."""
    lo, hi = bounds(objs)
    middle = Vector(target) if target is not None else (lo + hi) / 2
    back = Vector(direction).normalized()          # from the middle toward the camera
    forward = -back
    up = Vector((0, 0, 1)) if abs(forward.z) < 0.99 else Vector((0, 1, 0))
    right = forward.cross(up).normalized()
    up = right.cross(forward).normalized()
    data = cam.data
    tan_v = data.sensor_height / 2 / data.lens * fill
    tan_h = data.sensor_height * 9 / 16 / 2 / data.lens * fill
    dist = 1e-3
    for p in corners(lo, hi):
        v = p - middle
        x, y, z = v.dot(right), v.dot(up), v.dot(forward)   # z > 0: farther than the middle
        dist = max(dist, abs(x) / tan_h - z, abs(y) / tan_v - z)
    closest = max((p - middle).dot(back) for p in corners(lo, hi))   # the corner nearest the camera's side
    dist = max(dist, closest * 1.05 + 1e-3, 0.05)
    cam.location = middle + back * dist
    aim.location = middle
    data.clip_start = max(0.001, dist / 1000)
    data.clip_end = dist * 50 + 100
    return dist

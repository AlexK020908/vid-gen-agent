"""Phase 23's look test: three shots from reference A's opening, built by hand to judge whether Blender reaches
A's look before the parts kit and shot sheets are built (SHORTS.md).

Each shot builds its scene and returns its anchors (name -> (object, local offset)), its length in frames and
its events (frame, kind), which the overlay and sound use.
"""
from __future__ import annotations

import math
import random

import bpy

from blender import envs, look, shapes


def _ease(obj, frame: int, kind: str, easing: str = "AUTO") -> None:
    """How `obj` moves from its key at `frame` to the next: QUAD with EASE_IN speeds up (a hammer swinging into
    a nail), EASE_OUT slows down (lifting off it), LINEAR is even."""
    for curve in look._fcurves(obj.animation_data.action):
        for point in curve.keyframe_points:
            if round(point.co.x) == frame:
                point.interpolation = kind
                point.easing = easing


def nail(fps: int) -> dict:
    """'give it a few light taps ... and it goes right into the wood': a long nail in a pale block, tapped three
    times by a claw hammer swinging in from the right. As in A, a notch is cut out of the block's front through
    the nail's own plane, so the nail is seen going into the wood."""
    x, y, length = 0.0, -0.04, 0.10
    block = envs.workbench(block=(0.5, 0.20, 0.12), target=(x, y, 0.12))
    top = block.dimensions[2]
    profile = [(0, 0), (0.0012, 0.008), (0.0012, 0.0986), (0.0036, 0.0989), (0.0036, 0.1), (0, 0.1)]
    nail = shapes.lathe("Nail", profile, "bright_steel", segments=48)
    # the notch's left wall stays out of the picture; the block left of it throws A's dark wedge across the cut
    shapes.cut_away([block], keep_y_above=y, material="wood_cut", x_range=(x - 0.07, x + 0.05))

    frames = 100                     # A from 1.4 s, so its taps at 2.0, 2.6 and 3.2 s are frames 18, 36, 54
    taps = [18, 36, 54]
    # how much of the nail stands above the wood before each tap and after: A's nail starts with just its point in
    # and ends with less than half out
    out = [0.097, 0.080, 0.062, 0.045]
    base = [top - (length - o) for o in out]
    look.key(nail, 1, location=(x, y, base[0]))
    for i, f in enumerate(taps):
        look.key(nail, f, location=(x, y, base[i]))
        look.key(nail, f + 2, location=(x, y, base[i + 1]))
    look.ease(nail, "LINEAR")

    # the hammer swings about a pivot at the end of its handle, off to the right; its face meets the nail's head.
    # It's built full size and shrunk to A's, whose head is about a third as tall as the nail is long
    size, face_full = 0.5, 0.055   # face_full: from the head's middle to its striking face, before the shrink
    reach, face = 0.27 * size, face_full * size
    pivot = bpy.data.objects.new("Hammer.pivot", None)
    bpy.context.scene.collection.objects.link(pivot)
    head = bpy.data.objects.new("Hammer", None)
    bpy.context.scene.collection.objects.link(head)
    head.parent = pivot
    head.location = (-reach, 0, 0)
    head.scale = (size, size, size)
    shapes.lathe("HammerFace", [(0, -face_full), (0.0105, -face_full), (0.0125, -face_full + 0.002), (0.0125, -0.03),
                                (0.0105, -0.02), (0, -0.02)], "steel", segments=40, parent=head)   # polished face
    shapes.box("HammerEye", (0.032, 0.022, 0.045), "black_steel", at=(0, 0, 0.003), bevel=0.003, parent=head)
    claw = shapes.torus("HammerClaw", 0.045, 0.0075, "black_steel", at=(0.045, 0, 0.025), arc=75, axis="Y",
                        segments=24, ring=12, parent=head)
    claw.rotation_euler = (0, math.radians(-105), 0)   # from the head's top, curving up toward the handle
    handle = shapes.lathe("HammerHandle", [(0, 0), (0.0105, 0), (0.0105, 0.02), (0.0125, 0.18), (0.0145, 0.26),
                                           (0.0145, 0.282), (0.010, 0.288), (0, 0.288)], "wood", segments=32,
                          at=(0.012, 0, 0), parent=head)
    handle.rotation_euler = (0, math.radians(90), 0)
    handle.scale = (1.0, 0.75, 1.0)

    def height(i):
        return top + out[i] + face

    # light taps: A's hammer comes in from the top right, then lifts only a little between taps, staying in view
    up = math.radians
    swings = [(1, up(50), height(0)), (10, up(22), height(0))]
    for i, f in enumerate(taps):
        swings += [(f, 0.0, height(i)), (f + 2, 0.0, height(i + 1)), (f + 8, up(17), height(i + 1))]
    swings += [(taps[-1] + 16, up(40), height(3)), (taps[-1] + 26, up(75), height(3))]
    for f, angle, z in swings:
        look.key(pivot, f, location=(x + reach, y, z), rotation_euler=(0, angle, 0))
    look.ease(pivot, "LINEAR")
    for i, f in enumerate(taps):
        _ease(pivot, taps[i - 1] + 8 if i else 10, "QUAD", "EASE_IN")   # gathering speed into the nail
        _ease(pivot, f + 2, "QUAD", "EASE_OUT")               # slowing as it lifts off
    _ease(pivot, taps[-1] + 8, "QUAD", "EASE_IN")

    focus = bpy.data.objects.new("Nail.focus", None)   # the middle of the nail, so head and point are both sharp
    bpy.context.scene.collection.objects.link(focus)
    focus.parent = nail
    focus.location = (0, 0, 0.05)
    # A's camera starts close on the standing nail, pulls back as the hammer comes in so there's room above it,
    # holds through the taps, and pushes in again as the nail goes into the wood
    moves = ((1, (0.012, -0.34, 0.33), (0.0, y, 0.165)), (18, (0.018, -0.50, 0.43), (0.0, y, 0.235)),
             (54, (0.016, -0.47, 0.41), (0.0, y, 0.225)), (78, (0.012, -0.34, 0.29), (0.0, y, 0.135)),
             (frames, (0.01, -0.32, 0.28), (0.0, y, 0.13)))
    cam, aim = look.camera(bpy.context.scene, at=moves[0][1], look_at=moves[0][2], lens=50, fstop=4.5, focus=focus)
    for f, at, target in moves:
        look.key(cam, f, location=at)
        look.key(aim, f, location=target)
    return {"anchors": {"nail": (nail, (0.0036, 0, 0.099))}, "frames": frames,
            "events": [{"frame": f, "kind": "impact"} for f in taps]}


def crane(fps: int) -> dict:
    """'Hoisting it with a crane every time is far too slow': the iron block on the hook, crawling up above the pile."""
    envs.desert_lot()
    shapes.cylinder("Pile", 0.3, 10.0, "dark_steel", bevel=0.02, segments=48)
    for i in range(1, 10):
        shapes.tube(f"Band{i}", 0.304, 0.29, 0.07, "white_paint", at=(0, 0, i * 1.0), segments=48)
    shapes.tube("RedBand", 0.304, 0.29, 0.12, "red_paint", at=(0, 0, 9.55), segments=48)

    rig = bpy.data.objects.new("Hoist", None)
    bpy.context.scene.collection.objects.link(rig)
    block = shapes.cylinder("IronBlock", 0.45, 1.1, "steel", bevel=0.035, parent=rig)
    shapes.torus("Eye", 0.075, 0.022, "steel", at=(0, 0, 1.15), axis="X", parent=rig)
    shapes.torus("Hook", 0.11, 0.038, "hazard_stripes", at=(0, 0, 1.30), axis="Y", arc=290, parent=rig)
    shapes.box("HookBlock", (0.34, 0.22, 0.52), "hazard_stripes", at=(0, 0, 1.75), bevel=0.02, parent=rig)
    shapes.rods("Cable", [((0, 0, 2.0), (0, 0, 40.0))], 0.012, "rubber", parent=rig)

    frames = int(3.2 * fps)
    look.key(rig, 1, location=(0, 0, 10.55))
    look.key(rig, frames, location=(0, 0, 11.25))
    look.ease(rig, "LINEAR")

    boom = shapes.truss("Boom", 46.0, 1.4, 22, "white_paint", at=(6, 30, 0.5), chord=0.07, lace=0.035)
    boom.rotation_euler = (math.radians(-20), math.radians(-14), 0)
    shapes.box("CraneBase", (5, 7, 2.6), "white_paint", at=(6, 30, 1.3), bevel=0.1)

    cam, aim = look.camera(bpy.context.scene, at=(1.6, -8.0, 11.0), look_at=(0, 0, 10.9), lens=35, fstop=4.0,
                           focus=block)
    look.key(aim, 1, location=(0, 0, 10.9))
    look.key(aim, frames, location=(0, 0, 11.15))
    return {"anchors": {"iron_block": (block, (-0.42, -0.12, 0.55))}, "frames": frames, "events": []}


def air(fps: int, balls=60, seed=3) -> dict:
    """'it compresses the air inside the cylinder': the lower cylinder cut open, the ram coming down in slow
    motion, the air balls crowding into the shrinking space."""
    envs.desert_lot()
    z0 = 3.0
    shapes.cylinder("Pile", 0.3, z0, "dark_steel", bevel=0.02, segments=48)
    # the anvil and lower cylinder as one turned part: base flange, wall, top lip, and the dish the ram lands in
    # the bowl: 0.38 up at the wall, 0.26 at the middle
    dish = [(0.50 * math.cos(t), 0.38 - 0.12 * math.sin(t)) for t in
            (math.radians(a) for a in range(0, 91, 10))]
    housing_profile = ([(0, 0), (0.95, 0), (0.95, 0.09), (0.62, 0.09), (0.62, 1.02), (0.74, 1.02), (0.74, 1.12),
                        (0.505, 1.12)] + [(r, z) for r, z in dish if r > 1e-4] + [(0, 0.26)])
    housing = shapes.lathe("Housing", housing_profile, "safety_yellow", at=(0, 0, z0), segments=96)
    shapes.cut_away([housing])

    ram = shapes.cylinder("Ram", 0.48, 1.3, "steel", bevel=0.03, segments=96)
    shapes.tube("Collar", 0.66, 0.479, 0.16, "safety_yellow", at=(0, 0, 1.14), segments=96, parent=ram)
    for side in (-1, 1):
        shapes.box(f"Lug{side}", (0.36, 0.16, 0.12), "safety_yellow", at=(side * 0.78, 0, 1.22), bevel=0.01,
                   parent=ram)
        shapes.tube(f"Sleeve{side}", 0.07, 0.04, 0.2, "safety_yellow", at=(side * 0.9, 0, 1.12), segments=32,
                    parent=ram)
        shapes.cylinder(f"Rod{side}", 0.035, 4.6, "chrome", at=(side * 0.9, 0, z0 + 0.09), segments=24)
    shapes.torus("RamEye", 0.07, 0.02, "steel", at=(0, 0, 1.36), axis="X", parent=ram)

    frames = int(3.5 * fps)
    high, low = z0 + 1.02, z0 + 0.62
    floor = z0 + 0.36   # the dish's rim; balls sit between here and the ram's face
    for f in (1, frames):
        look.key(ram, f, location=(0, 0, high if f == 1 else low))
    look.ease(ram, "LINEAR")

    rng = random.Random(seed)
    specs = []
    for i in range(balls):
        r = 0.44 * math.sqrt(rng.random())
        ang = rng.uniform(0.15, math.pi - 0.15)       # the back half only: the front half is cut away
        specs.append((r, ang, rng.random(), rng.uniform(0, 6.3), rng.uniform(1.5, 3.0)))
    objs = [shapes.sphere(f"Air{i}", 0.031, "air", segments=16) for i in range(balls)]
    for obj in objs:
        obj["group"] = "air"
    for f in range(1, frames + 1, 2):
        t = (f - 1) / max(1, frames - 1)
        top = high + (low - high) * t - 0.03
        for obj, (r, ang, u, phase, speed) in zip(objs, specs):
            wob = 0.04 * math.sin(phase + f * speed / fps * 2 * math.pi)
            a = ang + 0.05 * math.sin(phase * 1.7 + f / fps * speed)
            h = floor + 0.03 + min(max(u + wob, 0.0), 1.0) * max(top - floor - 0.06, 0.0)
            look.key(obj, f, location=(r * math.cos(a), r * math.sin(a) + 0.02, h))
    for obj in objs:
        look.ease(obj, "LINEAR")

    cam, aim = look.camera(bpy.context.scene, at=(0.12, -3.7, z0 + 1.7), look_at=(0, 0, z0 + 0.72), lens=30,
                           fstop=5.6, focus=housing)
    look.key(cam, 1, location=(0.12, -3.7, z0 + 1.7))
    look.key(cam, frames, location=(0.08, -3.35, z0 + 1.6))
    # the label points at a ball low and near the cut: the camera looks down a little, so as the ram comes down its
    # uncut front edge covers the chamber's back and top
    near = min(range(balls), key=lambda i: specs[i][0] * math.sin(specs[i][1]) + 0.3 * specs[i][2])
    return {"anchors": {"air": (objs[near], (0, 0, 0))}, "frames": frames, "events": []}


SHOTS = {"nail": nail, "crane": crane, "air": air}

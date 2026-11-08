"""Run inside Blender: scenes staged by the same code every short uses, measured from the meshes rather than looked at. Writes what
it found to <folder>/out.json: where things came to rest, how a spin turned, how a slide ended, how a hat sits, and what got refused.
"""
import json
import math
import sys
import traceback
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from blender import bounds, glow, look, materials, people, stage  # noqa: E402

job = json.loads(Path(sys.argv[sys.argv.index("--") + 1]).read_text(encoding="utf-8"))
materials.ASSETS.update(job["textures"])
folder = Path(job["out"])
out = {}


def fresh():
    for block in (bpy.data.objects, bpy.data.meshes, bpy.data.materials, bpy.data.lights, bpy.data.cameras, bpy.data.curves):
        for item in list(block):
            block.remove(item)
    materials._made.clear()
    look.setup(bpy.context.scene, size=(108, 192), fps=30, samples=1)


def staged(scene):
    fresh()
    s = stage.Stage(scene, job["folders"], job["catalog"], 30, job["things"])
    s.run()
    return s


def refused(scene):
    try:
        staged(scene)
    except stage.Refused as e:
        return e.problems
    return []


STAND = {"type": "prop", "prop": "block", "on": "set", "at": [0, 0], "facing": 0}
SHOT = [{"t": 0, "on": "stand:", "frame": 0.6, "angle": [0, 20], "lens": 26, "square": True}]

# a thing on a thing on a set: each comes down until it touches, and no further
s = staged({"length": 0.2, "set": "sky_counter", "cast": {"stand": STAND, "top": {"type": "prop", "prop": "block", "on": "stand", "by": "under", "onto": "over", "facing": 30}}, "shots": SHOT})
bpy.context.view_layer.update()
stand = bounds.Solid(bounds.meshes_of(s.props["stand"]["root"]))
top = bounds.Solid(bounds.meshes_of(s.props["top"]["root"]))
surface = bounds.Solid(s.solids)
out["rest"] = {"on_set": stand.low.z - surface.high.z, "on_stand": top.low.z - stand.high.z,
               "across": (Vector(s.props["top"]["root"].matrix_world.translation.xy) - Vector(s.props["stand"]["root"].matrix_world.translation.xy)).length}

# fixed to another at a point, from the side: the two spots meet, and they're let overlap
s = staged({"length": 0.2, "set": "sky_counter", "cast": {"stand": STAND, "top": {"type": "prop", "prop": "block", "to": "stand:off_middle", "by": "under", "facing": 0}}, "shots": SHOT})
bpy.context.view_layer.update()
there = s.props["stand"]["root"].matrix_world @ s.props["stand"]["thing"].spot("off_middle")
here = s.props["top"]["root"].matrix_world @ s.props["top"]["thing"].spot("under")
out["fixed"] = (there - here).length

# a spin: the axis stays put to the micron, and it turns at the rate it was told
s = staged({"length": 1.0, "set": "sky_counter", "cast": {"stand": STAND, "wheel": {"type": "prop", "prop": "block", "at": [0, 0, 0.5], "floats": True, "facing": 0}},
            "happens": [{"do": "spin", "t": 0, "prop": "wheel", "axis": "x", "about": "off_middle", "rate": 1.0}],
            "shots": [{"t": 0, "on": "stand:", "frame": 1.2, "angle": [0, 10], "lens": 26, "square": True}]})
root = s.props["wheel"]["root"]
spot = s.props["wheel"]["thing"].spot("off_middle")
wandered, up = 0.0, []
start = None
for f in range(1, 31):
    bpy.context.scene.frame_set(f)
    bpy.context.view_layer.update()
    place = root.matrix_world @ spot
    start = start or place.copy()
    wandered = max(wandered, (place - start).length)
    up.append(list(root.matrix_world.to_3x3() @ Vector((0, 0, 1))))
quarter = up[7]     # 7 frames into 30 a turn is 84 degrees
out["spin"] = {"wandered": wandered, "up_after_84": quarter}

# a slide: straight, level, and exactly where it rests at the end
s = staged({"length": 1.0, "set": "sky_counter", "cast": {"stand": STAND, "top": {"type": "prop", "prop": "block", "on": "stand", "facing": 0}},
            "happens": [{"do": "slide", "t": 0.2, "prop": "top", "from": [0, 0, 0.4], "over": 0.5}], "shots": SHOT})
root = s.props["top"]["root"]
tilts, heights = [], []
for f in range(1, 31):
    bpy.context.scene.frame_set(f)
    bpy.context.view_layer.update()
    tilts.append((root.matrix_world.to_3x3() @ Vector((0, 0, 1))).angle(Vector((0, 0, 1))))
    heights.append(root.matrix_world.translation.z)
bpy.context.scene.frame_set(30)
bpy.context.view_layer.update()
stand = bounds.Solid(bounds.meshes_of(s.props["stand"]["root"]))
top = bounds.Solid(bounds.meshes_of(root))
out["slide"] = {"most_tilt": max(tilts), "start_above_end": heights[0] - heights[-1], "gap_at_end": top.low.z - stand.high.z, "crossing": top.crossing(stand)}

# a hat: seated by measuring, riding on the head
s = staged({"length": 0.5, "set": "sky_set", "cast": {"walt": {"type": "person", "character": "walt", "at": [0, 0], "stance": "Idle_relaxed"},
                                                      "hat": {"type": "prop", "prop": "hat", "at": [0, 0, 1], "facing": 0}},
            "happens": [{"do": "wear", "who": "walt", "prop": "hat"}], "shots": [{"t": 0, "on": "walt:eyes", "frame": 0.8, "lens": 26}]})
bpy.context.scene.frame_set(1)
bpy.context.view_layer.update()
person = s.people["walt"]
body = bounds.Solid([person.body])
hat = bounds.Solid(bounds.meshes_of(s.props["hat"]["root"]))
middle = (hat.low + hat.high) / 2
out["hat"] = {"head_top": body.high.z, "hat_top": hat.high.z, "rim": hat.low.z, "eyes": person.middle(person.eyes).z,
              "off_centre": abs(middle.x - (body.low.x + body.high.x) / 2)}

# what's refused
out["through"] = refused({"length": 0.2, "set": "sky_counter", "cast": {"stand": STAND, "other": {"type": "prop", "prop": "block", "at": [0.02, 0, 0.01], "facing": 0, "floats": True}}, "shots": SHOT})
out["hanging"] = refused({"length": 0.2, "set": "sky_counter", "cast": {"stand": STAND, "other": {"type": "prop", "prop": "block", "at": [0.5, 0, 0.3], "facing": 0}}, "shots": SHOT})
out["said_to_float"] = refused({"length": 0.2, "set": "sky_counter", "cast": {"stand": STAND, "other": {"type": "prop", "prop": "block", "at": [0.5, 0, 0.3], "facing": 0, "floats": True}}, "shots": SHOT})
out["said_to_touch"] = refused({"length": 0.2, "set": "sky_counter", "cast": {"stand": STAND, "other": {"type": "prop", "prop": "block", "at": [0.02, 0, 0.01], "facing": 0, "floats": True}},
                                "touching": [["stand", "other"]], "shots": SHOT})
out["in_the_way"] = refused({"length": 0.2, "set": "sky_counter", "cast": {"stand": STAND, "other": {"type": "prop", "prop": "block", "on": "set", "at": [0, -0.25], "facing": 0}},
                             "shots": [{"t": 0, "on": "stand:", "frame": 0.6, "angle": [0, 3], "lens": 26, "square": True}]})
out["lens_under"] = refused({"length": 0.2, "set": "sky_counter", "cast": {"stand": STAND},
                             "shots": [{"t": 0, "on": "stand:", "frame": 0.6, "angle": [0, -40], "lens": 26, "square": True}]})
# a wall behind what a shot is on isn't in its way, with the lens inside the wall's bounding box; a wall between them is.
# A thing's `at` is its middle, and this one's wall is 0.89 behind that
SHOT_LOW = [{"t": 0, "on": "stand:", "frame": 0.6, "angle": [0, 3], "lens": 26, "square": True}]
out["wall_behind"] = refused({"length": 0.2, "set": "sky_counter", "cast": {"stand": STAND, "corner": {"type": "prop", "prop": "corner", "on": "set", "at": [0, -0.59], "facing": 0}}, "shots": SHOT_LOW})
out["wall_between"] = refused({"length": 0.2, "set": "sky_counter", "cast": {"stand": STAND, "corner": {"type": "prop", "prop": "corner", "on": "set", "at": [0, -1.04], "facing": 0}}, "shots": SHOT_LOW})
# how many chips a hit throws
staged({"length": 0.2, "set": "sky_counter", "cast": {"stand": STAND}, "happens": [{"do": "sparks", "t": 0.05, "on": "stand:", "kind": "chips", "count": 6}], "shots": SHOT})
out["chips"] = sum(obj.name.startswith("Spark") for obj in bpy.data.objects)
out["slide_through"] = refused({"length": 0.6, "set": "sky_counter", "cast": {"stand": STAND, "other": {"type": "prop", "prop": "block", "at": [0, 0, 0.5], "facing": 0, "floats": True}},
                                "happens": [{"do": "slide", "t": 0.1, "prop": "other", "by": [0, 0, -0.5], "over": 0.4}], "shots": SHOT})

# a glow can't leave its thing: a flow's circles stop at its edge, and every point stays on its surface
s = staged({"length": 0.3, "set": "sky_counter", "cast": {"stand": STAND},
            "happens": [{"do": "flow", "t": 0, "on": "stand:over", "color": "green", "radii": [0.02, 0.5]},
                        {"do": "lit", "t": 0, "on": "stand:over", "color": "red", "radius": 0.03},
                        {"do": "rings", "t": 0, "on": "stand:over", "color": "white", "reach": 0.1},
                        {"do": "tint", "t": 0, "to": 0.2, "prop": "stand", "color": [0.4, 0.2, 0.1]}], "shots": SHOT})
lights = s.props["stand"].get("lights") or []
bpy.context.scene.frame_set(1)
bpy.context.view_layer.update()
box = bounds.Solid(bounds.meshes_of(s.props["stand"]["root"]))
tube_points = [obj.matrix_world @ v.co for obj in lights for v in obj.data.vertices]
out["flow"] = {"lines": len(lights), "furthest_past_edge": max((max(p.x - box.high.x, box.low.x - p.x) for p in tube_points), default=9.0)}
out["balls"] = [o.name for o in bpy.data.objects if "aura" in o.name.lower()]

# how people move: a wall to run into, from far enough off to get up to speed
RUNNER = {"type": "person", "character": "walt", "at": [0, -6.5], "facing": 180, "stance": "Idle_relaxed"}
WALL = {"type": "prop", "prop": "wall", "on": "set", "at": [0, 0], "facing": 0}
ON_RUNNER = [{"t": 0, "on": "walt:chest", "frame": 3.0, "angle": [90, 4], "lens": 26, "follow": True}]
scene = bpy.context.scene

s = staged({"length": 2.3, "set": "sky_set", "cast": {"walt": RUNNER, "wall": WALL},
            "happens": [{"do": "walk", "t": 0, "who": "walt", "to": [0, -0.5], "over": 1.5, "clip": "Run_jog_forwards", "hits": "wall", "with": "forehead", "slow": [0.3, 0.2]}], "shots": ON_RUNNER})
arrive = 1 + round(1.5 * 30)
turn = arrive - round(0.3 * 30)
rig = s.people["walt"].rig
ys = {}
for f in (2, 12, turn + 1, turn + 6, arrive, arrive + 2, arrive + 11, arrive + 14, arrive + 18):
    scene.frame_set(f)
    bpy.context.view_layer.update()
    ys[f] = rig.location.y
scene.frame_set(arrive)
bpy.context.view_layer.update()
wall, body = s._solid_of("wall"), s._solid_of("walt")
way = Vector((0, 1, 0))
out["hit"] = {"reach_at_arrival": body.reach_to(wall, way), "crossing_at_arrival": body.crossing(wall),
              "speed_running": (ys[12] - ys[2]) / 10, "speed_in_slow_motion": (ys[turn + 6] - ys[turn + 1]) / 5, "moved_back": ys[arrive] - ys[arrive + 18]}
scene.frame_set(arrive + 18)
bpy.context.view_layer.update()
out["hit"]["reach_after"] = s._solid_of("walt").reach_to(s._solid_of("wall"), way)

s = staged({"length": 2.0, "set": "sky_set", "cast": {"walt": {**RUNNER, "at": [0, -2.0]}},
            "happens": [{"do": "walk", "t": 0.1, "who": "walt", "to": [0, -0.5], "over": 1.5, "clip": "Walk_forwards"}], "shots": ON_RUNNER})
person = s.people["walt"]
hips_from_rig, jumps, last = 0.0, 0.0, None
for f in range(10, 45):
    scene.frame_set(f)
    bpy.context.view_layer.update()
    hips = person.rig.matrix_world @ person.bone("spine").head
    hips_from_rig = max(hips_from_rig, Vector((hips.x - person.rig.location.x, hips.y - person.rig.location.y)).length)
    if last is not None:
        jumps = max(jumps, (hips - last).length)
    last = hips
scene.frame_set(60)
bpy.context.view_layer.update()
out["walk"] = {"ends_at": person.rig.location.y, "told": -0.5, "hips_from_rig": hips_from_rig, "biggest_jump": jumps}

out["too_fast"] = refused({"length": 1.0, "set": "sky_set", "cast": {"walt": RUNNER},
                           "happens": [{"do": "walk", "t": 0, "who": "walt", "to": [0, 2], "over": 0.5, "clip": "Walk_forwards"}], "shots": ON_RUNNER})
out["ran_through"] = refused({"length": 1.5, "set": "sky_set", "cast": {"walt": {**RUNNER, "at": [0, -3.0]}, "wall": WALL},
                              "happens": [{"do": "walk", "t": 0, "who": "walt", "to": [0, 1.0], "over": 1.0, "clip": "Run_jog_forwards"}], "shots": ON_RUNNER})

# a shot following a runner goes with them, without bouncing with their steps
s = staged({"length": 1.6, "set": "sky_set", "cast": {"walt": RUNNER},
            "happens": [{"do": "walk", "t": 0, "who": "walt", "to": [0, 0.7], "over": 1.6, "clip": "Run_jog_forwards"}], "shots": ON_RUNNER})
person = s.people["walt"]
aim = s.cuts[0]["aim"]
aims, hips_up, apart = [], [], 0.0
for f in range(10, 40):
    scene.frame_set(f)
    bpy.context.view_layer.update()
    aims.append(aim.matrix_world.translation.z)
    hips_up.append((person.rig.matrix_world @ person.bone("spine").head).z)
    apart = max(apart, abs(aim.matrix_world.translation.y - (person.rig.matrix_world @ person.bone("spine.003").tail).y))
out["follow"] = {"aim_bounce": max(aims) - min(aims), "hips_bounce": max(hips_up) - min(hips_up), "stays_with_them": apart}
# and the lights on them go too
key = bpy.data.objects["Key"]
scene.frame_set(1)
bpy.context.view_layer.update()
first = key.matrix_world.translation.y
scene.frame_set(48)
bpy.context.view_layer.update()
out["lights"] = {"key_moved": key.matrix_world.translation.y - first, "walked": person.rig.location.y - (-6.5)}

# someone falls, and stays down
s = staged({"length": 3.2, "set": "sky_set", "cast": {"walt": {**RUNNER, "at": [0, 0]}},
            "happens": [{"do": "act", "t": 0.1, "who": "walt", "clip": "Death_fall_backwards", "stays": True}], "shots": [{"t": 0, "on": "walt:chest", "frame": 3.0, "angle": [90, 4], "lens": 26}]})
person, shadow = s.people["walt"], s.shadows["walt"]
hips_at = lambda: person.rig.matrix_world @ person.bone("spine").head
scene.frame_set(1)
bpy.context.view_layer.update()
standing = hips_at().z
scene.frame_set(80)
bpy.context.view_layer.update()
done = hips_at().z
scene.frame_set(96)
bpy.context.view_layer.update()
hips = hips_at()
out["fall"] = {"hips_standing": standing, "hips_when_done": done, "hips_later": hips.z,
               "shadow_under_hips": Vector((shadow.matrix_world.translation.x - hips.x, shadow.matrix_world.translation.y - hips.y)).length}
floor = bpy.data.objects["hidden_floor"]
out["floor"] = {"height": floor.matrix_world.translation.z, "casts_no_shadow": not floor.visible_shadow}

# a squash presses along its axis, stays on what it's on, and comes back
s = staged({"length": 1.0, "set": "sky_counter", "cast": {"stand": STAND},
            "happens": [{"do": "squash", "t": 0.1, "prop": "stand", "amount": 0.2, "axis": "z", "over": 0.6}], "shots": SHOT})
squasher = s.props["stand"]["squasher"]
meshes = bounds.meshes_of(s.props["stand"]["root"])
scene.frame_set(1)
bpy.context.view_layer.update()
rest = bounds.Solid(meshes).low.z
pressed, wider, moved = 1.0, 1.0, 0.0
for f in range(4, 12):
    scene.frame_set(f)
    bpy.context.view_layer.update()
    pressed, wider = min(pressed, squasher.scale.z), max(wider, squasher.scale.x)
    moved = max(moved, abs(bounds.Solid(meshes).low.z - rest))
scene.frame_set(30)
bpy.context.view_layer.update()
out["squash"] = {"pressed": pressed, "wider": wider, "underside_moved": moved, "after": squasher.scale.z}

# a rock with a part: what's near that spot moves, and what's far from it doesn't
ROD = {"type": "prop", "prop": "rod", "at": [0, 0, 0.5], "facing": 0, "floats": True}
s = staged({"length": 1.0, "set": "sky_counter", "cast": {"rod": ROD},
            "happens": [{"do": "rock", "t": 0.1, "prop": "rod", "over": 0.6, "times": 1, "degrees": 20, "about": "neck", "part": {"near": "tip", "radius": 0.2}}],
            "shots": [{"t": 0, "on": "rod:", "frame": 0.8, "angle": [0, 10], "lens": 26, "square": True}]})
root = s.props["rod"]["root"]
meshes = bounds.meshes_of(root)
scene.frame_set(1)
bpy.context.view_layer.update()
before = bounds.Solid(meshes).verts
root_before = root.matrix_world.translation.copy()
tip = root.matrix_world @ s.props["rod"]["thing"].spot("tip")
scene.frame_set(18)
bpy.context.view_layer.update()
after = bounds.Solid(meshes).verts
near = [(a - b).length for a, b in zip(after, before) if (b - tip).length < 0.03]
far = [(a - b).length for a, b in zip(after, before) if (b - tip).length > 0.21]
out["bend"] = {"near_moved": max(near or [0]), "far_moved": max(far or [0]), "root_moved": (root.matrix_world.translation - root_before).length}

# a glide: from where it says to where it says, with no jump on the way
s = staged({"length": 1.0, "set": "sky_counter", "cast": {"stand": STAND},
            "shots": [{"t": 0, "on": "stand:", "frame": 1.2, "angle": [0, 20], "lens": 24, "square": True, "shift": [-0.1, -0.2], "to": {"frame": 0.6, "angle": [60, 30], "shift": [0, 0]}}]})
cam, aim = s.cuts[0]["camera"], s.cuts[0]["aim"]
places = []
for f in range(1, 31):
    scene.frame_set(f)
    bpy.context.view_layer.update()
    places.append((cam.matrix_world.translation.copy(), aim.matrix_world.translation.copy()))
out["glide"] = {"start_distance": (places[0][0] - places[0][1]).length, "told_start": 1.2, "end_distance": (places[-1][0] - places[-1][1]).length, "told_end": 0.6,
                "biggest_step": max((a[0] - b[0]).length for a, b in zip(places, places[1:]))}
scene.frame_set(1)
bpy.context.view_layer.update()
shift = {"x": cam.data.shift_x, "y": cam.data.shift_y}
scene.frame_set(30)
bpy.context.view_layer.update()
out["shift"] = {**shift, "end_y": cam.data.shift_y}

# what a body's moves sound like
s = staged({"length": 3.0, "set": "sky_set", "cast": {"walt": RUNNER},
            "happens": [{"do": "walk", "t": 0, "who": "walt", "to": [0, 5.0], "over": 2.4, "clip": "Run_jog_forwards", "slow": [0.6, 0.2]}], "shots": ON_RUNNER})
steps = [c["frame"] for c in s._sound_cues() if c["kind"] == "step"]
slow_from = s.frame(0) + round(1.8 * 30)
s = staged({"length": 3.2, "set": "sky_set", "cast": {"walt": {**RUNNER, "at": [0, 0]}}, "happens": [{"do": "act", "t": 0.1, "who": "walt", "clip": "Death_fall_backwards", "stays": True}],
            "shots": [{"t": 0, "on": "walt:chest", "frame": 3.0, "angle": [90, 4], "lens": 26}]})
heights = [h.z for h in s._clip("Death_fall_backwards")["hips"]]
drop = heights[0] - min(heights)
expected = s.frame(0.1) + next(i for i, z in enumerate(heights) if heights[0] - z >= 0.9 * drop)
lands = [c["frame"] for c in s._sound_cues() if c["kind"] == "land"]
s = staged({"length": 1.0, "set": "sky_set", "cast": {"walt": {**RUNNER, "at": [0, 0]}}, "happens": [{"do": "act", "t": 0.1, "who": "walt", "clip": "Hit_to_the_head"}],
            "shots": [{"t": 0, "on": "walt:chest", "frame": 3.0, "angle": [90, 4], "lens": 26}]})
out["sounds"] = {"steps": steps, "slow_from": slow_from, "lands": lands, "expected_land": expected, "stands_silent": [c for c in s._sound_cues() if c["kind"] == "land"]}

# set against something crooked: a wall that leans, and a rod with its base and tip both on it
LEANING = {"type": "prop", "prop": "wall", "at": [0, 0.5, -0.5], "points": [0, 0.2, 1], "up": [0, 1, -0.2], "floats": True}
s = staged({"length": 0.5, "set": "sky_set", "cast": {"wall": LEANING, "rod": {"type": "prop", "prop": "rod", "against": "wall", "at": [0, -3], "height": 1.0, "points": [0, 0, 1], "up": [0, 1, 0], "way": [0, 1], "by": ["base", "tip"]}},
            "shots": [{"t": 0, "on": "rod:", "frame": 1.5, "angle": [90, 4], "lens": 26}]})
scene.frame_set(1)
bpy.context.view_layer.update()
wall = s._solid_of("wall")
root, thing = s.props["rod"]["root"], s.props["rod"]["thing"]
gap = lambda spot: wall.ray(root.matrix_world @ thing.spot(spot) - Vector((0, 1, 0)), Vector((0, 1, 0)))[2] - 1
out["against"] = {"first_gap": abs(gap("base")), "second_gap": abs(gap("tip")), "tipped": math.degrees((root.rotation_quaternion @ Vector((0, 0, 1))).angle(Vector((0, 0, 1)))), "through": []}
out["nail_in"] = None
s = staged({"length": 0.5, "set": "sky_set", "cast": {"wall": WALL, "rod": {"type": "prop", "prop": "rod", "against": "wall", "at": [0, -3], "height": 1.0, "points": [0, -1, 0], "up": [0, 0, 1], "way": [0, 1], "by": ["base"], "into": 0.03}},
            "shots": [{"t": 0, "on": "rod:", "frame": 1.5, "angle": [90, 4], "lens": 26}]})
scene.frame_set(1)
bpy.context.view_layer.update()
root, thing = s.props["rod"]["root"], s.props["rod"]["thing"]
tip = root.matrix_world @ thing.spot("base")
out["nail_in"] = tip.y - s._solid_of("wall").low.y

# glass on part of a thing: marked on its points, and through the window its far side isn't drawn
s = staged({"length": 0.5, "set": "sky_set", "cast": {"rod": {**ROD, "at": [0, 0, 1]}},
            "happens": [{"do": "ghost", "t": 0, "prop": "rod", "near": "tip", "radius": 0.1}], "shots": [{"t": 0, "on": "rod:", "frame": 0.8, "angle": [90, 4], "lens": 26}]})
root = s.props["rod"]["root"]
mesh = bounds.meshes_of(root)[0]
tip = root.matrix_world @ s.props["rod"]["thing"].spot("tip")
marked = list(mesh.data.attributes["ghost_part"].data)
shares = [(mark.value, (mesh.matrix_world @ v.co - tip).length) for mark, v in zip(marked, mesh.data.vertices)]
out["part"] = {"near_spot": max(share for share, far in shares if far < 0.05), "far_from_it": max(share for share, far in shares if far > 0.11),
               "culled": any(slot.material.use_backface_culling for slot in mesh.material_slots),
               "seen_from_inside": any(n.type == "NEW_GEOMETRY" for slot in mesh.material_slots for n in slot.material.node_tree.nodes)}
s = staged({"length": 0.5, "set": "sky_set", "cast": {"rod": {**ROD, "at": [0, 0, 1]}},
            "happens": [{"do": "ghost", "t": 0, "prop": "rod"}], "shots": [{"t": 0, "on": "rod:", "frame": 0.8, "angle": [90, 4], "lens": 26}]})
out["whole_seen_from_inside"] = any(n.type == "NEW_GEOMETRY" for slot in bounds.meshes_of(s.props["rod"]["root"])[0].material_slots for n in slot.material.node_tree.nodes)

# a shell with a hole in it: a point outside isn't inside because one ray left through the hole
fresh()
bm = bmesh.new()
bmesh.ops.create_cube(bm, size=2.0)
bm.faces.ensure_lookup_table()
bmesh.ops.delete(bm, geom=[next(f for f in bm.faces if f.normal.z > 0.9)], context="FACES_ONLY")
mesh = bpy.data.meshes.new("open")
bm.to_mesh(mesh)
bm.free()
shell = bpy.data.objects.new("open", mesh)
bpy.context.scene.collection.objects.link(shell)
bpy.context.view_layer.update()
solid = bounds.Solid([shell])
out["open_shell"] = {"inside": solid._holds(Vector((0.2, 0.3, -0.5))), "beside": solid._holds(Vector((1.5, 0.2, -0.5))), "under": solid._holds(Vector((0.2, 0.3, -1.5)))}

# what's inside a thing goes where it goes, and isn't part of it
INNER = {"type": "prop", "prop": "orb", "inside": "outer", "room": 0.5}
BOX = {"type": "prop", "prop": "shell", "at": [0, 0, 0.5], "floats": True}
s = staged({"length": 1.0, "set": "sky_set", "cast": {"outer": BOX, "inner": INNER},
            "happens": [{"do": "slide", "t": 0, "prop": "outer", "over": 0.5, "by": [0.4, 0, 0], "ease": "linear"}],
            "shots": [{"t": 0, "on": "outer:", "frame": 1.5, "angle": [0, 4], "lens": 26}]})
scene.frame_set(1)
bpy.context.view_layer.update()
before = s.props["inner"]["root"].matrix_world.translation.copy()
scene.frame_set(25)
bpy.context.view_layer.update()
out["carried"] = {"moved": (s.props["inner"]["root"].matrix_world.translation - before).x, "outer_moved": s.props["outer"]["root"].matrix_world.translation.x,
                  "part_of_it": any(obj in bounds.meshes_of(s.props["outer"]["root"]) for obj in bounds.meshes_of(s.props["inner"]["root"]))}

# inside something, a slide until what it's inside stops at the wall ahead of it, and a press takes the shape of that wall
s = staged({"length": 2.0, "set": "sky_set", "cast": {"outer": BOX, "inner": INNER},
            "happens": [{"do": "slide", "t": 0.1, "prop": "inner", "over": 0.5, "until": "outer", "way": [0, 1, 0], "ease": "linear"},
                        {"do": "press", "t": 0.6, "prop": "inner", "amount": 0.3, "way": [0, 1, 0], "in": 0.2, "over": 0.5, "stays": 1.0}],
            "shots": [{"t": 0, "on": "outer:", "frame": 1.5, "angle": [0, 4], "lens": 26}]})
scene.frame_set(s.frame(0.6))
bpy.context.view_layer.update()
inner, shell = s._solid_of("inner"), s._solid_of("outer")
middle_of = (inner.low + inner.high) / 2
ahead = shell.ray(middle_of, Vector((0, 1, 0)))[0].y
touched = {"front": inner.high.y, "wall": ahead, "back": inner.low.y}
scene.frame_set(s.frame(1.5))
bpy.context.view_layer.update()
pressed = s._solid_of("inner")
out["press"] = {**touched, "front_after": pressed.high.y, "back_after": pressed.low.y, "pokes": shell.pokes_by(pressed._sample(300)), "wide_before": inner.high.x - inner.low.x, "wide_after": pressed.high.x - pressed.low.x,
                "on_the_wall_before": sum(v.y > inner.high.y - 0.002 for v in inner.verts), "on_the_wall_after": sum(v.y > pressed.high.y - 0.002 for v in pressed.verts)}

# a part bends until its spot touches what it's against
s = staged({"length": 0.5, "set": "sky_set", "cast": {"wall": WALL, "rod": {"type": "prop", "prop": "rod", "against": "wall", "at": [0, -3], "height": 1.0, "points": [0, -0.5, 1], "up": [0, 1, 0], "way": [0, 1], "by": ["neck"],
                                                                         "bends": [{"spot": "tip", "about": "neck", "near": "tip", "radius": 0.18}]}},
            "shots": [{"t": 0, "on": "rod:neck", "frame": 1.5, "angle": [90, 4], "lens": 26}]})
scene.frame_set(1)
bpy.context.view_layer.update()
root, thing = s.props["rod"]["root"], s.props["rod"]["thing"]
hook = next(iter(s.props["rod"]["hooks"].values()))
tip = root.matrix_world @ (thing.spot("neck") + hook.rotation_quaternion @ (thing.spot("tip") - thing.spot("neck")))
out["bent"] = {"bent_by": math.degrees(hook.rotation_quaternion.angle), "gap": abs(s._solid_of("wall").ray(tip - Vector((0, 1, 0)), Vector((0, 1, 0)))[2] - 1)}

# someone's head: the mark covers it, what's in it rides on it, and their hair and eyes go
HEADED = {"type": "person", "character": "walt", "at": [0, -2.0], "facing": 180, "stance": "Idle_relaxed"}
checks = stage.Stage.check_physics
stage.Stage.check_physics = lambda self: None       # the stand-in's head is a ball that doesn't bend with its neck, as a real body's does
s = staged({"length": 2.0, "set": "sky_set", "cast": {"walt": HEADED, "in_head": {"type": "prop", "prop": "orb", "inside": "walt", "room": 0.5, "facing": 180}},
            "happens": [{"do": "walk", "t": 0.1, "who": "walt", "to": [0, -0.5], "over": 1.5, "clip": "Walk_forwards"}, {"do": "ghost", "t": 0, "who": "walt"}],
            "shots": [{"t": 0, "on": "walt:eyes", "frame": 2.0, "angle": [90, 4], "lens": 26, "follow": True}]})
stage.Stage.check_physics = checks
person, carried = s.people["walt"], s.props["in_head"]["root"]
distances = []
for f in (1, 20, 40):
    scene.frame_set(f)
    bpy.context.view_layer.update()
    distances.append((carried.matrix_world.translation - s._on_person("walt", "eyes")).length)
middle = person.head_middle()
points = person.rest_points()
marks = [m.value for m in person.body.data.attributes["ghost_part"].data]
out["in_head"] = {"rides": max(distances) - min(distances), "marked_at_top": max(mark for mark, p in zip(marks, points) if p[2] > middle.z + 0.02), "not_at_the_hips": max([mark for mark, p in zip(marks, points) if p[2] < 1.0] or [0.0]),
                  "travelled": carried.matrix_world.translation.y - (-2.0),
                  "eyes_go": any(n.type == "BSDF_TRANSPARENT" for m in person.eyes.data.materials for n in m.node_tree.nodes)}

# whoever goes down lands, goes slack and still breathes
s = staged({"length": 3.2, "set": "sky_set", "cast": {"walt": {**RUNNER, "at": [0, 0]}}, "happens": [{"do": "act", "t": 0.1, "who": "walt", "clip": "Death_fall_backwards", "stays": True}, {"do": "expression", "t": 0.5, "who": "walt", "name": "out_cold"}],
            "shots": [{"t": 0, "on": "walt:chest", "frame": 3.0, "angle": [90, 4], "lens": 26}]})
person = s.people["walt"]
chest = []
for f in (s.total - 40, s.total - 20, s.total):
    scene.frame_set(f)
    bpy.context.view_layer.update()
    chest.append(tuple(person.rig.pose.bones[person.bones["spine.003"]].rotation_quaternion))
out["down"] = {"thumped": bool(s.knocks["walt"]), "still_moving": chest[0] != chest[1] or chest[1] != chest[2]}

# a running body's shoulders don't twist further than a body's do
s = staged({"length": 1.0, "set": "sky_set", "cast": {"walt": RUNNER}, "happens": [{"do": "walk", "t": 0, "who": "walt", "to": [0, -2.5], "over": 0.9, "clip": "Run_jog_forwards"}], "shots": ON_RUNNER})
person, solver = s.people["walt"], s.solvers["walt"]
out["run"] = {"kept": s._calmed(s._clip("Run_jog_forwards"), solver, person)}

# what's inside something can't show outside its outline from the lens, even if it's surrounded
s = staged({"length": 0.5, "set": "sky_set", "cast": {"outer": BOX, "inner": {**INNER, "room": 0.5}}, "shots": [{"t": 0, "on": "outer:", "frame": 1.5, "angle": [0, 4], "lens": 26}]})
out["outline_within"] = s._outside_outline()
scene.frame_set(1)
inner = s.props["inner"]["root"]
inner.location.z += 0.6                 # up and out of the box, in sight of the lens
bpy.context.view_layer.update()
out["outline_past"] = s._outside_outline()
inner.location.z -= 0.6

# what's on something that moves goes with it, and a thing that's been told to start short does
s = staged({"length": 1.0, "set": "sky_set", "cast": {"under": {"type": "prop", "prop": "block", "on": "set", "at": [0, 0]}, "on_it": {"type": "prop", "prop": "orb", "on": "under", "at": [0, 0]}},
            "happens": [{"do": "slide", "t": 0, "prop": "under", "over": 0.5, "by": [0.4, 0, 0], "ease": "linear"}],
            "shots": [{"t": 0, "on": "under:", "frame": 1.5, "angle": [0, 4], "lens": 26}]})
scene.frame_set(1)
bpy.context.view_layer.update()
before = s.props["on_it"]["root"].matrix_world.translation.copy()
scene.frame_set(25)
bpy.context.view_layer.update()
out["rides_on"] = (s.props["on_it"]["root"].matrix_world.translation - before).x

# part of something pressed, and turned to other stuff: the rest stays as it is
s = staged({"length": 1.0, "set": "sky_set", "cast": {"rod": ROD},
            "happens": [{"do": "turns", "t": 0.1, "prop": "rod", "near": "tip", "radius": 0.1, "into": {"color": [0.9, 0.7, 0.1], "pores": 0.004}, "fade": 0.1},
                        {"do": "press", "t": 0.2, "prop": "rod", "near": "tip", "radius": 0.15, "amount": 0.3, "way": [0, 0, 1], "in": 0.1, "over": 0.3, "stays": 0.0, "soft": 0.5}],
            "shots": [{"t": 0, "on": "rod:", "frame": 0.8, "angle": [90, 4], "lens": 26}]})
meshes = bounds.meshes_of(s.props["rod"]["root"])
scene.frame_set(1)
bpy.context.view_layer.update()
rest = bounds.Solid(meshes).verts
scene.frame_set(s.frame(0.3))
bpy.context.view_layer.update()
pressed = bounds.Solid(meshes).verts
tip = s.props["rod"]["root"].matrix_world @ s.props["rod"]["thing"].spot("tip")
scene.frame_set(s.frame(0.95))
bpy.context.view_layer.update()
back_again = bounds.Solid(meshes).verts
marked = list(meshes[0].data.attributes["turned_part"].data)
out["part_pressed"] = {"near_moved": max((a - b).length for a, b in zip(pressed, rest) if (b - tip).length < 0.2),
                       "far_moved": max((a - b).length for a, b in zip(pressed, rest) if (b - tip).length > 0.3),
                       "came_back": max((a - b).length for a, b in zip(back_again, rest)),
                       "turned_near": max(m.value for m, v in zip(marked, rest) if (v - tip).length < 0.05), "turned_far": max(m.value for m, v in zip(marked, rest) if (v - tip).length > 0.11)}

# a head stays where it stopped, while the rest of them comes on under it
bends, checks = stage.Stage._bends, stage.Stage.check_physics
stage.Stage._bends = staticmethod(lambda person: True)      # the stand-in's a ball that doesn't bend, so where its head goes isn't what's measured here
stage.Stage.check_physics = lambda self: None
s = staged({"length": 1.8, "set": "sky_set", "cast": {"walt": RUNNER, "wall": WALL},
            "happens": [{"do": "walk", "t": 0, "who": "walt", "to": [0, -0.3], "over": 1.0, "clip": "Run_jog_forwards", "hits": "wall", "with": "forehead"}],
            "shots": [{"t": 0, "on": "walt:chest", "frame": 2.5, "angle": [90, 4], "lens": 24, "follow": True}]})
stage.Stage._bends, stage.Stage.check_physics = staticmethod(bends), checks
walk = next(e for e in s.events if e["do"] == "walk")
arrive = s.frame(0) + 30
place = []
for f in (arrive, arrive + 3, arrive + 6, arrive + 20):
    scene.frame_set(f)
    bpy.context.view_layer.update()
    place.append(s.people["walt"].rig.location.y)
leaning = s.people["walt"].rig.pose.bones[s.people["walt"].bones["spine.002"]].rotation_quaternion.copy()
out["keeps_coming"] = {"carry": walk["carry"], "rig_on": place[1] - place[0], "rig_back": place[0] - place[3], "touch_near_wall": abs(s.touches["walt"].y - s._solid_of("wall").low.y)}

# where a hit lands is the part that's touching, which isn't always what's furthest on
s = staged({"length": 1.5, "set": "sky_set", "cast": {"walt": RUNNER, "wall": {**WALL, "facing": 35}},
            "happens": [{"do": "walk", "t": 0, "who": "walt", "to": [0, -0.3], "over": 1.0, "clip": "Run_jog_forwards", "hits": "wall", "with": "forehead"}],
            "shots": [{"t": 0, "on": "walt:chest", "frame": 2.5, "angle": [90, 4], "lens": 24, "follow": True}]})
scene.frame_set(s.frame(0) + 30)
bpy.context.view_layer.update()
_slant = s._solid_of("wall")
_furthest = max(s._solid_of("walt").verts, key=lambda v: v.y)
out["touch_slanted"] = {"touch_to_wall": _slant.tree.ray_cast(s.touches["walt"], (0, 1, 0))[3], "furthest_to_wall": _slant.tree.ray_cast(_furthest, (0, 1, 0))[3]}

# time slowing down smoothly into slow motion, rather than all at once
s = staged({"length": 2.0, "set": "sky_set", "cast": {"walt": {**RUNNER, "at": [0, -3]}, "wall": WALL},
            "happens": [{"do": "walk", "t": 0, "who": "walt", "to": [0, -0.3], "over": 1.5, "clip": "Run_jog_forwards", "hits": "wall", "with": "forehead", "slow": [1.49, 0.01], "ramp": 0.2, "covers": 0.95}],
            "shots": [{"t": 0, "on": "wall:", "frame": 2.5, "angle": [90, 4], "lens": 24}]})
places = []
for f in range(1, 47):
    scene.frame_set(f)
    bpy.context.view_layer.update()
    places.append(s.people["walt"].rig.location.y)
steps = [b - a for a, b in zip(places, places[1:])]
out["ramp"] = {"first": steps[1], "middle": steps[12], "last": steps[-2], "evenly": max(abs(b - a) for a, b in zip(steps[1:], steps[2:])), "covered": places[-1] - places[0]}

# a peck goes the way the beak points, however the head's turned
class _Spots:
    spot = staticmethod(lambda name: {"neck": Vector((0, 0, 0)), "beak": Vector((0.1, -0.1, 0.02)), "straight_up": Vector((0, 0, 0.1))}[name])


out["toward"] = {"along": list(stage.Stage._rock_axis({"toward": "beak", "about": "neck"}, _Spots)), "straight_up": list(stage.Stage._rock_axis({"toward": "straight_up", "about": "neck"}, _Spots))}

# a part bent at rest takes its spots with it
ROD_ON_WALL = {"type": "prop", "prop": "rod", "against": "wall", "at": [0, -3], "height": 1.0, "points": [0, -0.5, 1], "up": [0, 1, 0], "way": [0, 1], "by": ["neck"],
               "bends": [{"spot": "tip", "about": "neck", "near": "tip", "radius": 0.18, "yaw": 30}]}
s = staged({"length": 0.5, "set": "sky_set", "cast": {"wall": WALL, "rod": ROD_ON_WALL}, "shots": [{"t": 0, "on": "rod:neck", "frame": 1.5, "angle": [90, 4], "lens": 26}]})
scene.frame_set(1)
bpy.context.view_layer.update()
wall_solid = s._solid_of("wall")
tip_at = s.aim("rod:tip", 1)
out["bent_spot"] = {"tip_on_wall": abs(wall_solid.ray(tip_at - Vector((0, 1, 0)), Vector((0, 1, 0)))[2] - 1), "moved": (s.props["rod"]["thing"].spot("tip") - s._bent_spot(s.props["rod"], "tip")).length}

# something smoothed where it's marked, no smaller for it, and with its holes no bigger
fresh()
bm = bmesh.new()
bmesh.ops.create_icosphere(bm, subdivisions=4, radius=0.1)
for i, vert in enumerate(bm.verts):
    vert.co *= 1 + 0.03 * math.sin(i * 12.9898)
bm.faces.ensure_lookup_table()
top = [f for f in bm.faces if f.calc_center_median().z > 0.095]
rim_before = set()
bmesh.ops.delete(bm, geom=top, context="FACES_ONLY")
mesh = bpy.data.meshes.new("bumpy")
bm.to_mesh(mesh)
bm.free()
bumpy = bpy.data.objects.new("bumpy", mesh)
bpy.context.scene.collection.objects.link(bumpy)
bpy.context.view_layer.update()
polys_per_edge = {}
for poly in mesh.polygons:
    for key in poly.edge_keys:
        polys_per_edge[key] = polys_per_edge.get(key, 0) + 1
rim = {i for key, used in polys_per_edge.items() if used == 1 for i in key}
before = [v.co.copy() for v in mesh.vertices]
glow.mark_part([bumpy], (0, 0, 0), 1.0)
glow.smooth_part([bumpy], 5)
block = mesh.shape_keys.key_blocks[-1]
after = [point.co.copy() for point in block.data]
radius = lambda points: sum(p.length for p in points) / len(points)
bumps = lambda points: sum(abs(p.length - radius(points)) for p in points) / len(points)
out["smoothed"] = {"radius_before": radius(before), "radius_after": radius(after), "bumps_before": bumps(before), "bumps_after": bumps(after), "rim_moved": max((after[i] - before[i]).length for i in rim), "had_a_rim": len(rim)}

# being surrounded: lines through a point meet a thing on both sides, whatever holes it has
fresh()
bm = bmesh.new()
bmesh.ops.create_cube(bm, size=2.0)
bm.faces.ensure_lookup_table()
bmesh.ops.delete(bm, geom=[next(f for f in bm.faces if f.normal.z > 0.9)], context="FACES_ONLY")
mesh = bpy.data.meshes.new("open")
bm.to_mesh(mesh)
bm.free()
shell = bpy.data.objects.new("open", mesh)
bpy.context.scene.collection.objects.link(shell)
bpy.context.view_layer.update()
solid = bounds.Solid([shell])
out["surrounded"] = {"inside": solid.encloses(Vector((0.2, 0.3, -0.5))), "just_outside": solid.encloses(Vector((1.1, 0.2, -0.2))), "beside": solid.encloses(Vector((1.5, 0.2, -0.5)))}

# whoever goes down stays on the ground all the way down, and doesn't blink once they're out cold
blinks = []
blink = people.Person.blink
people.Person.blink = lambda self, frame, *a, **k: blinks.append(frame)
s = staged({"length": 3.2, "set": "sky_set", "cast": {"walt": {**RUNNER, "at": [0, 0]}}, "happens": [{"do": "act", "t": 0.1, "who": "walt", "clip": "Death_fall_backwards", "stays": True, "skip": 0.1}, {"do": "expression", "t": 1.0, "who": "walt", "name": "out_cold"}],
            "shots": [{"t": 0, "on": "walt:chest", "frame": 3.0, "angle": [90, 4], "lens": 26}]})
people.Person.blink = blink
meshes = bounds.meshes_of(s.people["walt"].rig)
lows = []
for f in range(s.frame(0.1), s.total, 6):
    scene.frame_set(f)
    bpy.context.view_layer.update()
    lows.append(s._lowest(meshes))
out["stays_down"] = {"lowest": min(lows), "highest": max(lows), "last_blink": max(blinks or [0]), "out_cold_at": s.frame(1.0)}

# something soft sinks into what it's on, rather than balancing on what sticks out of its underside
ON_WALL = {"type": "prop", "prop": "rod", "on": "wall", "points": [0, 0, 1], "up": [0, 1, 0]}
s = staged({"length": 0.5, "set": "sky_set", "touching": [["rod", "wall"]], "cast": {"wall": WALL, "rod": ON_WALL}, "shots": [{"t": 0, "on": "wall:", "frame": 2.5, "angle": [90, 4], "lens": 24}]})
sits_at = s.props["rod"]["root"].location.z
s = staged({"length": 0.5, "set": "sky_set", "touching": [["rod", "wall"]], "cast": {"wall": WALL, "rod": {**ON_WALL, "sinks": 0.03}}, "shots": [{"t": 0, "on": "wall:", "frame": 2.5, "angle": [90, 4], "lens": 24}]})
out["sinks"] = sits_at - s.props["rod"]["root"].location.z

# a peck drawn back slowly, with a long way to snap home
slow_back = {"back": 0.45}
steps = [stage._rock_share(i, 100, 1, slow_back) for i in range(101)]
out["rock_back"] = {"furthest_at": steps.index(max(steps)), "plain_furthest_at": max(range(101), key=lambda i: stage._rock_share(i, 100, 1, {}))}

# a thing can be smoothed as it's cast, and glass can keep some of what it was
s = staged({"length": 0.5, "set": "sky_set", "cast": {"wall": {**WALL, "smooth": 3}}, "shots": [{"t": 0, "on": "wall:", "frame": 2.5, "angle": [90, 4], "lens": 24}]})
out["smoothed_as_cast"] = any(mesh.data.shape_keys for mesh in bounds.meshes_of(s.props["wall"]["root"]))
kept = bpy.data.materials.new("kept")
kept.use_nodes = True
glow.ghost_materials([kept], "ice", 1, 10, 3, 20, fill=0.25)
out["glass_keeps"] = [round(node.inputs[1].default_value, 3) for node in kept.node_tree.nodes if node.type == "MATH" and node.operation == "MULTIPLY" and not node.inputs[1].links]

# what's frozen by slow motion stays frozen, rather than getting up
s = staged({"length": 2.0, "set": "sky_set", "cast": {"walt": {**RUNNER, "at": [0, 0]}}, "happens": [{"do": "walk", "t": 0, "who": "walt", "to": [0, 0.5], "over": 1.0, "clip": "Run_jog_forwards", "slow": [0.9, 0.01], "covers": 0.5}],
            "shots": [{"t": 0, "on": "walt:chest", "frame": 3.0, "angle": [90, 4], "lens": 26}]})
heights = []
for f in (31, 45, 60):
    scene.frame_set(f)
    bpy.context.view_layer.update()
    heights.append(s._on_person("walt", "eyes").z)
out["frozen"] = max(heights) - min(heights)

# lights come from in front of someone, whichever way they face
s = staged({"length": 0.5, "set": "sky_set", "cast": {"walt": {**RUNNER, "at": [0, 0], "facing": 180}}, "shots": [{"t": 0, "on": "walt:eyes", "frame": 1.0, "angle": [0, 4], "lens": 26}]})
key = bpy.data.objects["Key"]
person = s.people["walt"]
out["light"] = {"key_in_front": (key.matrix_world.translation - person.middle(person.eyes)).dot(s._directions("walt")[0])}

# a liquid's top: flat, level, where the scene says, counted from another's top; a pour lands on it; air never ends up in anything
from blender import liquid  # noqa: E402

DISH = {"type": "prop", "prop": "dish", "on": "set", "at": [0, 0], "level": 0.01}
TUBE = {"type": "prop", "prop": "tube", "on": "dish", "above": "dish", "level": 0.45}
s = staged({"length": 2.0, "set": "sky_counter", "cast": {"dish": DISH, "tube": TUBE, "jug": {"type": "prop", "prop": "jug", "at": [0.04, 0.0, 0.2], "floats": True}},
            "happens": [{"do": "fill", "prop": "tube", "t": 0.2, "over": 1.0, "level": 0.3, "ease": "linear"},
                        {"do": "pour", "from": "jug:spout", "into": "dish", "t": 0.1, "to": 1.5},
                        {"do": "fill", "prop": "dish", "t": 0.2, "over": 1.2, "level": 0.02, "ease": "linear"},
                        {"do": "air", "t": 0, "box": [[-0.12, -0.12, 0.0], [0.12, 0.12, 0.3]], "count": 120, "radius": 0.004, "speed": 0.3,
                         "leave": [{"t": 1.0, "through": [0, 0, 0.6], "share": 0.5, "over": 0.5}]}],
            "shots": [{"t": 0, "on": "dish:middle", "frame": 0.4, "angle": [0, 20], "fstop": 16, "square": True}]})
scene = bpy.context.scene
dish_bottom = liquid.lowest(s._liquid_of("dish"))
stream = next(o for o in bpy.data.objects if o.name.startswith("jug.pour"))
balls = [o for o in bpy.data.objects if o.name.startswith("Air")]
solid = bounds.Solid([obj for cid in ("dish", "tube", "jug") for obj in bounds.meshes_of(s.props[cid]["root"])] + list(s.solids))
inside, under = 0, 0
for f in range(1, s.total + 1, 4):
    scene.frame_set(f)
    bpy.context.view_layer.update()
    wet = liquid.tree_of([s._liquid_of("dish")])
    for ball in balls:
        if ball.scale[0] < 0.5:
            continue
        at = ball.matrix_world.translation
        inside += solid._holds(at)
        under += at.z < s.tops["dish"][f] - 0.001 and liquid.holds(wet, at)
scene.frame_set(45)
bpy.context.view_layer.update()
out["liquid"] = {"dish_from_bottom": [round(s.tops["dish"][f] - dish_bottom, 4) for f in (1, 7, 43)],
                 "tube_above_dish": [round(s.tops["tube"][f] - s.tops["dish"][f], 4) for f in (1, 7, 37, 60)],
                 "spout_moved": (stream.matrix_world.translation - s.aim("jug:spout", 45)).length,
                 "balls_inside_solids": inside, "balls_under_a_top": under,
                 "balls_left": sum(1 for b in balls if b.scale[0] > 0.5), "balls": len(balls),
                 "solid_has_no_liquid": all(not obj.get("liquid") for obj in bounds.meshes_of(s.props["tube"]["root"])),
                 "glass_seen_through": s._see_through("dish"), "steel_seen_through": s._see_through("jug")}
out["liquid_refused"] = {
    "misses": refused({"length": 1.0, "set": "sky_counter", "cast": {"dish": DISH, "jug": {"type": "prop", "prop": "jug", "at": [0.3, 0.0, 0.2], "floats": True}},
                       "happens": [{"do": "pour", "from": "jug:spout", "into": "dish", "t": 0.1, "to": 0.8}, {"do": "fill", "prop": "dish", "t": 0.2, "over": 0.5, "level": 0.02}],
                       "shots": [{"t": 0, "on": "dish:middle", "frame": 0.6, "angle": [0, 20], "fstop": 16, "square": True}]}),
    "into_empty": refused({"length": 1.0, "set": "sky_counter", "cast": {"dish": {**DISH, "level": 0.0}, "jug": {"type": "prop", "prop": "jug", "at": [0.04, 0.0, 0.2], "floats": True}},
                           "happens": [{"do": "pour", "from": "jug:spout", "into": "dish", "t": 0.1, "to": 0.8}, {"do": "fill", "prop": "dish", "t": 0.2, "over": 0.5, "level": 0.02}],
                           "shots": [{"t": 0, "on": "dish:middle", "frame": 0.6, "angle": [0, 20], "fstop": 16, "square": True}]}),
    "dipped": refused({"length": 0.5, "set": "sky_counter", "cast": {"dish": {**DISH, "level": 0.03}, "tube": {**TUBE, "level": 0.2}},
                       "shots": [{"t": 0, "on": "dish:middle", "frame": 0.4, "angle": [0, 20], "fstop": 16, "square": True}]}),
    "no_room": refused({"length": 0.5, "set": "sky_counter", "cast": {"dish": DISH, "tube": {**TUBE, "level": 0.1}},
                        "happens": [{"do": "air", "t": 0, "box": [[-0.01, -0.01, 0.2], [0.01, 0.01, 0.45]], "inside": "tube", "count": 20, "radius": 0.004}],
                        "shots": [{"t": 0, "on": "dish:middle", "frame": 0.4, "angle": [0, 20], "fstop": 16, "square": True}]})}

# a label's thing tracked on screen: in the middle of a shot that's on it, and seen through its own glass, a tube's glass and liquids
from blender import tracks  # noqa: E402

fresh()
s = stage.Stage({"length": 1.0, "set": "sky_counter", "cast": {"dish": DISH, "tube": TUBE, "jug": {"type": "prop", "prop": "jug", "at": [0.04, 0.0, 0.2], "floats": True}},
                 "anchors": ["dish:middle", "jug:spout"],
                 "shots": [{"t": 0, "on": "dish:middle", "frame": 0.8, "angle": [0, 20], "fstop": 16, "square": True}]}, job["folders"], job["catalog"], 30, job["things"])
shot = s.run()
track = tracks.export(bpy.context.scene, shot["anchors"], 1, s.total)
out["anchors_first"] = {name: points[0] for name, points in track.items()}
out["anchors"] = {"names": sorted(shot["anchors"]), "frames": len(track["dish:middle"]), "total": s.total,
                  "dish_from_middle": max(math.hypot(x - 0.5, y - 0.5) for x, y, _ in track["dish:middle"]),
                  "dish_seen": all(seen for _, _, seen in track["dish:middle"]), "spout_seen": all(seen for _, _, seen in track["jug:spout"]),
                  "spout_above_dish": all(sp[1] < d[1] for sp, d in zip(track["jug:spout"], track["dish:middle"]))}

(folder / "out.json").write_text(json.dumps(out, indent=1), encoding="utf-8")

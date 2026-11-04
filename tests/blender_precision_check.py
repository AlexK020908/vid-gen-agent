"""Run inside Blender: scenes staged by the same code every short uses, measured from the meshes rather than looked at. Writes what
it found to <folder>/out.json: where things came to rest, how a spin turned, how a slide ended, how a hat sits, and what got refused.
"""
import json
import sys
import traceback
from pathlib import Path

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from blender import bounds, look, materials, stage  # noqa: E402

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

(folder / "out.json").write_text(json.dumps(out, indent=1), encoding="utf-8")

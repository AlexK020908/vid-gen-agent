"""Stages a scene: the fixed code that runs what the agent writes in the scene language (scenes/spec.py has the format and
checks it before Blender starts). A new topic needs no new code here.

Things stay physically true by how they're built:
  - a held prop leads and the hand is locked on it (Person.hold), so a hand can't slip off a grip
  - a strike's arc ends exactly on the target's surface, found by casting a ray at it, so nothing passes through
  - a blow makes whoever holds the target ring down as a damped spring, about the teeth or hand, in proportion to how far
    out it landed: that's a lever. Sparks fall under gravity
  - people hold a stance from a body clip played very slowly, so they breathe and shift, and never freeze
  - a thing that goes under its own power (a bird) leans into its turns as far as its speed needs, flares to land, and
    rides on whoever it lands on
  - a thing put `on` another is lowered until the two meshes touch, found by rays, so it can't float or sink
  - a thing that's worn is seated by measuring the head and the inside of the hat, and rides on the head
  - a turning thing turns about one exact axis, with no wander
  - a glow is on a thing's own surface or in a line along it (blender/glow.py)
  - when it's all staged, the meshes are checked against each other frame by frame (blender/bounds.py): anything that passes
    through something, hangs in the air unsaid, or stands in front of the lens gets the scene refused, in words

One scene runs throughout, and the shots are cameras it cuts between, so everything stays where it was between cuts.
"""
from __future__ import annotations

import json
import math
import random
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Quaternion, Vector

from blender import bounds, clips, envs, glow, liquid, look, materials, people, shapes, things

UP = Vector((0, 0, 1))
COLORS = glow.COLORS
# where a hand holds a prop, in the person's own directions: (to their right, forward, up), for the right hand. The left
# mirrors it. palm, the way the prop points, the way the fingers point. A grip can differ by hand to keep crossed props apart
GRIPS = {
    "low_cross": {"R": ((0.235, 0.30, 0.90), (-0.80, 0.30, 0.48), (0.1, 1, -0.5)),
                  "L": ((0.235, 0.36, 0.90), (-0.80, 0.30, 0.48), (0.1, 1, -0.5))},
    "ready": ((0.20, 0.34, 1.02), (-0.10, 0.25, 1.0), (0.4, 1, -0.1)),
    "raised": ((0.24, 0.26, 1.42), (-0.25, 0.30, 0.90), (0.1, 1, -0.3)),
    "overhead": ((0.16, 0.14, 1.58), (-0.15, -0.35, 0.9), (0.0, 1, 0.2)),
    "at_side": ((0.34, 0.10, 0.84), (0.1, 0.8, -0.5), (0.0, 0.2, -1)),
    "forward": ((0.16, 0.44, 1.16), (-0.05, 1.0, 0.12), (0.0, 0.1, -1)),
}
SLOW = 0.3                          # how slowly a strike's aftermath runs, of real time
MOST_TWIST = 14.0                   # degrees either way a moving body's shoulders turn against its hips, whatever a clip does: a run from a pack can twist like a towel
RELAXED = {"f_index": (18, 22, 12), "f_middle": (20, 24, 12), "f_ring": (22, 26, 14), "f_pinky": (24, 28, 14), "thumb": (6, 8, 8)}    # a hand with nothing in it, gone slack
LANDS_HARD = 9.0                    # degrees a head rings by, hitting the ground
BREATHS = 0.24                      # breaths a second, of someone lying where they fell
WIND_UP = 0.5                       # seconds someone takes to draw back for a blow
WIND_TURN, WIND_LEAN = 22.0, -6.0   # how far their shoulders turn away, and they lean, drawing back for it, in degrees
BLOW_TURN, BLOW_LEAN = -14.0, 10.0  # and going through it, when it lands
BLOW_EASE = 24                      # frames they take to come back from it
HAND_SLIPS = 0.012                  # how far a wrist can be from where it's meant to be before a hand's visibly off what it holds (m)
HELD_CLEAR = 0.12                   # what's held further than this from the hand can't pass through whoever's holding it (m)
GIVE_IN, GIVE_STAYS, GIVE_BACK = 4, 2, 10    # frames something soft takes to give in where it's hit, stays in, and takes to come back
SOFT_EDGE = 5.0                     # a soft thing's mesh is cut up until its edges are this many times shorter than the dent it takes
MOST_SOFT_FACES = 60000             # and no further than this
MOVE_BLEND = 7                      # frames a body move fades in from what came before it, or back to the stance
BEND_FIRM = 0.7                     # the share of a bend's radius that moves whole; beyond it, it fades out to nothing
BRACED = {"eyeBlink_L": 0.75, "eyeBlink_R": 0.75, "browDown_L": 0.9, "browDown_R": 0.9, "noseSneer_L": 0.6,
          "noseSneer_R": 0.6}
BITING = {"mouthLowerDown_L": 0.7, "mouthLowerDown_R": 0.7, "mouthUpperUp_L": 0.42, "mouthUpperUp_R": 0.42,
          "mouthFunnel": 0.15, "jawOpen": 0.98}


def ring_down(frame: int, start: int, size: float, hertz: float = 1.1, damping: float = 0.32) -> float:
    """A damped spring knocked at `start`: 0 before, then swinging out to about `size` and settling."""
    if frame < start:
        return 0.0
    t = (frame - start) / 30.0
    return size * math.exp(-damping * 2 * math.pi * hertz * t) * math.sin(2 * math.pi * hertz * t) * 1.5


def _wrapped_grip(parent, base, length, radius=0.0105, wrap=0.0028, step=0.0048, seed=3):
    """A cord-wound grip along z: wound turn against turn, a little uneven as hand-wound cord is, dark in the gaps."""
    rng = random.Random(seed)
    shapes.cylinder(f"{parent.name}.grip", radius, length, "rubber", at=(0, 0, base), segments=24, parent=parent)
    for i in range(int(length / step)):
        turn = shapes.torus(f"{parent.name}.wrap{i}", radius + 0.0003, wrap, "cord", at=(0, 0, base + i * step), axis="Z",
                            segments=16, ring=6, parent=parent)
        turn.rotation_euler = (rng.uniform(-0.09, 0.09), rng.uniform(-0.09, 0.09), 0)


def _katana(root):
    """About 26 cm of grip around the hand, a guard, and a long narrow blade, along z."""
    _wrapped_grip(root, -0.11, 0.27)
    shapes.cylinder(f"{root.name}.collar", 0.0135, 0.014, "bright_steel", at=(0, 0, 0.16), segments=24, parent=root)
    shapes.cylinder(f"{root.name}.guard", 0.034, 0.004, "black_steel", at=(0, 0, 0.174), bevel=0.001, parent=root)
    shapes.torus(f"{root.name}.rim", 0.034, 0.0028, "copper", at=(0, 0, 0.176), axis="Z", parent=root)
    shapes.box(f"{root.name}.blade", (0.009, 0.026, 0.72), "chrome", at=(0, 0, 0.54), bevel=0.0015, parent=root)


def _long_sword(root):
    """A sword held in the teeth at the grip's middle: a long grip running out one way, a guard, then the blade."""
    _wrapped_grip(root, -0.75, 0.85)
    shapes.cylinder(f"{root.name}.collar", 0.0135, 0.016, "bright_steel", at=(0, 0, 0.095), segments=32, parent=root)
    shapes.cylinder(f"{root.name}.guard", 0.029, 0.004, "black_steel", at=(0, 0, 0.111), bevel=0.001, parent=root)
    shapes.torus(f"{root.name}.rim", 0.029, 0.0028, "copper", at=(0, 0, 0.113), axis="Z", parent=root)
    shapes.box(f"{root.name}.blade", (0.016, 0.004, 0.6), "bright_steel", at=(0, 0, 0.415), bevel=0.001, parent=root)


def _stick(root):
    shapes.cylinder(f"{root.name}.stick", 0.018, 0.9, "wood", at=(0, 0, -0.12), segments=20, parent=root)


def _ball(root):
    shapes.sphere(f"{root.name}.ball", 0.11, "orange_paint", segments=32, parent=root)


# how to build each prop; how far along it a strike lands; how far its striking surface is from its axis
PROPS = {"katana": (_katana, 0.62, 0.013), "long_sword": (_long_sword, 0.5, 0.008), "stick": (_stick, 0.6, 0.018),
         "ball": (_ball, 0.0, 0.11)}


# which bone carries what lands on each place on a person
RIDES = {"crown": "head", "forehead": "head", "shoulder_r": "upper_arm.R", "shoulder_l": "upper_arm.L", "hand_r": "hand.R",
         "hand_l": "hand.L", "chest": "spine.003", "stomach": "spine.001", "hips": "spine"}
ROCK_AXES = {"pitch": Vector((1, 0, 0)), "roll": Vector((0, 1, 0)), "yaw": Vector((0, 0, 1))}   # in the thing's own axes
ROCK_BACK = 0.72                  # the share of a rock spent drawing back, the rest being the snap
OWN_AXES = {"x": Vector((1, 0, 0)), "y": Vector((0, 1, 0)), "z": Vector((0, 0, 1))}
REST_GAP = 0.0004                 # how far above what it rests on a thing is left, so the two faces don't fight (m)
TOO_DEEP = 0.003                  # how far two things can pass through each other before it shows (m)
TOUCHING = 0.005                  # how near something has to be to be holding a thing up (m)
FLOORED = ("sky_set", "gym", "desert_lot", "studio", "place")     # sets whose floor is at z 0, with no mesh to measure
MOST_AIR_SHORT = 0.5      # air that finds room for less than this share of its balls is refused: drawn, it would be nothing (found on the barometer's straw)
CHECK_EVERY = 2                   # frames apart that moving things are checked
PERSON_EVERY = 10                 # and people: a body is many faces, and it moves slowly
PERSON_ACTING = 4                 # unless they're doing something
PERSON_WALKING = 2                # or going somewhere: a runner covers 15 cm in a frame
WALK_SPEEDS = (0.6, 1.5)          # how far a walking move can be slowed or sped up from its own pace before it looks wrong
PICTURE_SHAPE = 9 / 16            # a short's width against its height
SMOOTHED = "smoothed_all"
SCAN_SMOOTHS = 5                  # how many times a scan's surface is smoothed where it goes to glass, or the bright line round its edge is as wavy as every little bump in it
DEEP_COUNTER = 6.0                # how far a counter goes back in a real room, so its back edge is far off rather than just behind what's on it (m)
PLACE_LIGHT = 0.35                # how strong the lights added to a real place are, of what a bright set has: a place mostly lights itself
FALLS = 0.3                       # how far their hips drop in a move, against the length of a leg, for it to count as going down
POKES_OUT = 0.0015                # how far something inside another can reach out of it before it shows (m)
FIT_LEAST, FIT_MOST = 0.02, 2.5   # what a thing's sized by, at the least and most, to fit inside another
FIT_POINTS, CHECK_POINTS = 500, 150   # how many of its points are measured, to fit it, and each time it's checked
FIT_FEWER = 5                     # one in this many of them is enough to look for where it fits best
FIT_STEP, FIT_WANDERS = 0.02, 0.15    # how far it's moved at a time, looking for where it fits best, and how far it can go from where it was asked for, of the size of what it's in
ROOM = 0.85                       # how much of the room inside something a thing fills, fitted inside it
RESTS_ON = 0.003                  # how near a surface a point has to be to be bearing on it (m)
LIES_DOWN = 8                     # frames someone takes to settle on the ground, at the end of a fall
REBOUND = 0.14                    # how far someone bounces back from what they run into (m)
CARRIES_ON, CARRY_FRAMES = 0.07, 6    # how far their body keeps coming when their head's stopped (m), and how long that takes, before they're thrown back
CARRY_ROOM, HEAD_SIZE = 0.012, 0.22   # how far short of what they hit the rest of them stays, doing that, and how far from where they touched counts as the rest of them (m)
HEAD_HELD_BACK = 0.27             # how far a head goes back for each radian the back and neck lean by, shared out as they are, with a little to spare, so it stays where it stopped (m)
OUTLINE_EVERY, OUTLINE_POINTS = 6, 300    # frames apart that what's inside something is checked against its outline, and how many of its points
OUTLINE_SHARE = 0.005             # how far past the outline it can be before it shows, as a share of the picture's height, and how big a hole in a scan is taken for a hole
MOVERS = ("slide", "go", "fly", "rock", "spin")    # what makes something go somewhere, taking along what's on it
FROZEN = 0.1                      # the share of real speed below which what they were doing simply stays as it is, for as long as a scene lasts
PRESS_SOFT = 0.35                 # how far back from its front something pressed is squeezed, of its length
PRESS_FLAT = 0.55                 # how much of how far it shortens goes into flattening its front
PRESS_SPREADS = 0.8               # how much it spreads sideways, where it's squeezed most, for how much it shortens: what's squeezed goes somewhere
REBOUND_FRAMES = 10               # and how long that takes
FOLLOW_EVERY = 2                  # frames apart that a followed person is measured
FOLLOW_SMOOTH = 8                 # frames either side a following camera averages over: about one step, so it doesn't bounce with them
LENS_ROWS = (-1, 0, 1)            # the rays through what a shot is on, to see whether something's in front of it
NEAR_LENS = 0.6                   # how much of the way from the lens something in front has to be to count as blocking it
BEHIND_SUBJECT = 0.02   # a wall behind what a shot is on isn't in its way, even with the lens inside the wall's bounding box (m)
MOST_TIP = 50                     # how many degrees a thing set against another will tip, to touch it with two spots
HAT_ROOM = 1.06                   # a hat that's made to fit is this much wider than the head under it
HAIR_ROOM = 0.012                 # room left between the top of the head and the inside of a hat (m)
LEAN_LIMIT = math.radians(50)     # the steepest a flyer banks
CLIMB_LIMIT = math.radians(30)    # and climbs or dives, nose first
FLARE = math.radians(35)          # how far the nose comes up to land


def _spline(points: list[Vector], per_span: int = 48) -> list[Vector]:
    """A smooth line through points (Catmull-Rom), sampled finely."""
    if len(points) == 2:
        return [points[0].lerp(points[1], i / per_span) for i in range(per_span + 1)]
    ends = [points[0] * 2 - points[1], *points, points[-1] * 2 - points[-2]]
    out = []
    for i in range(1, len(ends) - 2):
        a, b, c, d = ends[i - 1:i + 3]
        for n in range(per_span):
            t = n / per_span
            out.append(((b * 2) + (c - a) * t + (a * 2 - b * 5 + c * 4 - d) * t * t + (b * 3 - a - c * 3 + d) * t * t * t) * 0.5)
    out.append(points[-1].copy())
    return out


def _along_line(line: list[Vector], share: float) -> Vector:
    """The point `share` of the way along a sampled line, by distance."""
    lengths = [0.0]
    for a, b in zip(line, line[1:]):
        lengths.append(lengths[-1] + (b - a).length)
    wanted = share * lengths[-1]
    for i in range(1, len(line)):
        if lengths[i] >= wanted:
            span = lengths[i] - lengths[i - 1]
            return line[i - 1].lerp(line[i], (wanted - lengths[i - 1]) / span if span else 0.0)
    return line[-1].copy()


def _pace(t: float, ease_in: float, ease_out: float) -> float:
    """How far along by time t, each 0 to 1, with steady speed but for easing up over the first `ease_in` of the time, and
    down over the last `ease_out`."""
    whole = 1 - ease_in / 2 - ease_out / 2
    if ease_in and t < ease_in:
        done = t * t / (2 * ease_in)
    elif ease_out and t > 1 - ease_out:
        left = 1 - t
        done = whole - left * left / (2 * ease_out)
    else:
        done = t - ease_in / 2
    return done / whole


def _axes(points: Vector, fingers: Vector) -> Quaternion:
    z = points.normalized()
    y = (fingers - z * fingers.dot(z)).normalized()
    return Matrix((y.cross(z), y, z)).transposed().to_quaternion()


def _splinter(name: str, rng, at: Vector):
    """A chip of wood: a thin uneven sliver, torn to a point at both ends, each one different."""
    length, width = rng.uniform(0.012, 0.04), rng.uniform(0.0025, 0.007)
    rows = ((0.0, 0.25), (0.3, 1.0), (0.7, 0.8), (1.0, 0.15))
    verts = []
    for along, wide in rows:
        for k in range(4):
            turn = k * math.tau / 4 + rng.uniform(-0.4, 0.4)
            verts.append(((math.cos(turn) * width * wide * rng.uniform(0.7, 1.3)), (math.sin(turn) * width * wide * 0.3), (along - 0.5) * length * rng.uniform(0.92, 1.08)))
    faces = [[j * 4 + k, j * 4 + (k + 1) % 4, (j + 1) * 4 + (k + 1) % 4, (j + 1) * 4 + k] for j in range(3) for k in range(4)] + [[3, 2, 1, 0], [12, 13, 14, 15]]
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = at
    materials.assign(obj, "wood")
    return obj


def _rock_share(i: int, count: int, times: int, e: dict) -> float:
    """How far back something rocking is at this step of it, 0 to 1. It draws back, and snaps home, faster the nearer it gets. `wobble`: something soft set going, swinging both ways and
    dying away. `gentle`: it comes home slowing down, as if something's taking it up."""
    if e.get("wobble"):
        return math.sin(i / count * times * math.tau) * math.exp(-3.0 * i / count) * (1 - (i / count) ** 8)
    if i == count:
        return 0.0
    x = (i / count * times) % 1.0
    back = float(e.get("back", 0.5 if e.get("gentle") else ROCK_BACK))
    if x < back:
        return math.sin(x / back * math.pi / 2)
    y = (x - back) / (1 - back)
    return (1 - y) ** 2 if e.get("gentle") else 1 - y * y


def _pressed(since: float) -> float:
    """How far in something soft is, 0 to 1, these frames after it's hit: it gives, it stays in while the blow's going on, and it comes back."""
    if since <= 0:
        return 0.0
    if since <= GIVE_IN:
        return 1 - (1 - since / GIVE_IN) ** 2
    if since <= GIVE_IN + GIVE_STAYS:
        return 1.0
    x = min(1.0, (since - GIVE_IN - GIVE_STAYS) / GIVE_BACK)
    return 1 - x * x * (3 - 2 * x)


def _made_fine(obj, longest: float) -> None:
    """A mesh cut up until none of its edges is longer than this in the world, so it can bend smoothly anywhere."""
    scale = max(obj.matrix_world.to_scale())
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    for _ in range(6):
        long = [edge for edge in bm.edges if edge.calc_length() * scale > longest]
        if not long or len(bm.faces) > MOST_SOFT_FACES:
            break
        bmesh.ops.subdivide_edges(bm, edges=long, cuts=1, use_grid_fill=True)
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    obj.data.shade_smooth()


def _only_during(root, ranges: list[tuple[int, int]], last_frame: int) -> None:
    """Show an object and what's under it only in these frame ranges, cutting exactly: a near-lens sword is cleared from a
    shot this way, and people who aren't in it don't slow its render."""
    switches: dict[int, bool] = {1: True}
    for a, b in sorted(ranges):
        switches[a] = False
        if b < last_frame:
            switches[b + 1] = True
    for obj in [root, *root.children_recursive]:
        for f, hidden in sorted(switches.items()):
            obj.hide_render = hidden
            obj.keyframe_insert("hide_render", frame=f)
        for curve in look._fcurves(obj.animation_data.action):
            if curve.data_path == "hide_render":
                for point in curve.keyframe_points:
                    point.interpolation = "CONSTANT"


def _inside_outline(point, flat) -> bool:
    """Whether a point on a surface is inside the outline of these points on it."""
    ordered = sorted({(round(float(x), 5), round(float(y), 5)) for x, y in flat})
    if len(ordered) < 3:
        return False
    cross = lambda o, a, b: (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    def half(rows):
        kept = []
        for row in rows:
            while len(kept) >= 2 and cross(kept[-2], kept[-1], row) <= 0:
                kept.pop()
            kept.append(row)
        return kept[:-1]
    hull = half(ordered) + half(ordered[::-1])
    return len(hull) >= 3 and all(cross(a, b, point) > 0 for a, b in zip(hull, hull[1:] + hull[:1]))


class Refused(ValueError):
    """A scene that isn't physically right, with what's wrong, in words."""

    def __init__(self, problems: list[str]):
        super().__init__("; ".join(problems))
        self.problems = problems


class Stage:
    def __init__(self, scene_spec: dict, folders: dict, catalog: dict, fps: int, thing_folders: dict | None = None):
        self.spec, self.folders, self.catalog, self.fps = scene_spec, folders, catalog, fps
        self.thing_folders = thing_folders or {}
        self.total = round(scene_spec["length"] * fps)
        self.bl = bpy.context.scene
        self.people: dict[str, people.Person] = {}
        self.solvers: dict[str, clips.Solver] = {}
        self.props: dict[str, dict] = {}
        self.knocks: dict[str, list] = {}
        self.events = sorted(scene_spec.get("happens") or [], key=lambda e: e.get("t", -1))
        self._clips: dict[str, dict] = {}
        self.waiting_rings: list[tuple] = []
        self.solids: list = []           # what the set itself is made of
        self.spans: dict[str, list] = {}  # the frames each of the cast is in the picture
        self.cuts: list[dict] = []
        self.shadows: dict = {}
        self.swings: dict[str, list] = {}  # the blows each person puts their body into
        self.touches: dict[str, Vector] = {}  # where someone first touched what they ran into

    def frame(self, t: float) -> int:
        return max(1, min(self.total, round(t * self.fps) + 1))

    # --- where things are ------------------------------------------------------------------------------------------

    def _facing(self, cid: str) -> float:
        c = self.spec["cast"][cid]
        facing = c.get("facing", 0)
        if isinstance(facing, (int, float)):
            return float(facing)
        here, there = c.get("at", (0, 0)), self.spec["cast"][facing].get("at", (0, 0))
        return math.degrees(math.atan2(there[0] - here[0], -(there[1] - here[1])))

    def _directions(self, who: str) -> tuple[Vector, Vector]:
        """A person's forward and right in the world."""
        turn = math.radians(self._facing(who))
        forward = Vector((math.sin(turn), -math.cos(turn), 0))
        return forward, Vector((forward.y, -forward.x, 0))

    def _in_their_terms(self, who: str, point, is_position=True) -> Vector:
        forward, right = self._directions(who)
        v = right * point[0] + forward * point[1] + UP * point[2]
        if is_position:
            at = self.spec["cast"][who].get("at", (0, 0))
            v += Vector((at[0], at[1], 0))
        return v

    def _grip(self, who: str, hand: str, name: str):
        """A named grip in the world: palm, the way the prop points, the way the fingers point."""
        g = GRIPS[name]
        palm, points, fingers = g[hand] if hand in g else g if isinstance(g, tuple) else g["R"]
        if hand == "L":
            palm, points, fingers = [(-v[0], v[1], v[2]) for v in (palm, points, fingers)]
        return (self._in_their_terms(who, palm), self._in_their_terms(who, points, False).normalized(),
                self._in_their_terms(who, fingers, False).normalized())

    def aim(self, name: str, frame: int | None = None) -> Vector:
        """A place in the world: on a person, as they stand now or as they are at `frame`, or on a prop, where it is at `frame` if it travels."""
        who, _, part = name.partition(":")
        if who in self.people:
            keep = self.bl.frame_current
            if frame is None or frame == keep:
                return self._on_person(who, part)
            self.bl.frame_set(max(1, min(self.total, frame)))
            here = self._on_person(who, part)
            self.bl.frame_set(keep)
            return here
        p = self.props[who]
        spots = p["thing"].spots if p.get("thing") else {}
        if p.get("carried"):            # it goes where what it's in goes, so it's only known by looking
            keep = self.bl.frame_current
            self.bl.frame_set(max(1, min(self.total, frame or keep)))
            bpy.context.view_layer.update()
            place = p["root"].matrix_world
            here = place @ p["thing"].spot(part) if part in spots else place.translation.copy()
            self.bl.frame_set(keep)
            return here
        if p.get("track") and frame is not None:
            here, turn = self._place(who, frame)
            if part in spots:           # a held thing's origin is where the hand closes on it
                grip = p["thing"].spot("grip") if p.get("holder") and "grip" in spots else Vector()
                return here + turn @ (self._bent_spot(p, part) - grip)
            return here + turn @ UP * float(part or 0)
        if part in spots:
            grip = p["thing"].spot("grip") if p.get("holder") and "grip" in spots else Vector()
            return p["palm"] + self._turn_of(p, p["points"], p["fingers"]) @ (self._bent_spot(p, part) - grip)
        return self._along(who, float(part or 0))

    @staticmethod
    def _turn_of(p: dict, points: Vector, fingers: Vector) -> Quaternion:
        """How something's turned, from the way it points and the way the fingers point that hold it. A tool's working end sticks out from its handle one way, whichever way it was
        modelled, and it's held with that leading the hand, the way you hold a hammer."""
        return _axes(points, fingers) @ p["spin"] if p.get("spin") else _axes(points, fingers)

    @staticmethod
    def _bent_spot(p: dict, name: str) -> Vector:
        """A spot on a thing, in its own axes, wherever any part that's been bent at rest has taken it."""
        thing = p["thing"]
        at = thing.spot(name)
        for (about, near, radius), hook in p.get("hooks", {}).items():
            rest = p.get("hook_rest", {}).get(hook.name)
            if rest is not None and (at - thing.spot(near)).length < radius:
                return thing.spot(about) + rest @ (at - thing.spot(about))
        return at

    def _hook_over(self, p: dict, at: Vector):
        """The part bent at rest that a place on a thing is in, if it's in one."""
        for (_, near, radius), hook in p.get("hooks", {}).items():
            if hook.name in p.get("hook_rest", {}) and (at - p["thing"].spot(near)).length < radius * BEND_FIRM:
                return hook
        return None

    def _place(self, cid: str, frame: int) -> tuple[Vector, Quaternion]:
        """Where a travelling prop is and how it's turned, at a frame: the last it was given, or where it began."""
        p = self.props[cid]
        known = [f for f in p.get("track", {}) if f <= frame]
        return p["track"][max(known)] if known else (p["palm"], _axes(p["points"], p["fingers"]))

    def _heading(self, cid: str, frame: int) -> float:
        """Which way a thing's facing at a frame, in the same degrees as a person's facing."""
        _, turn = self._place(cid, frame)
        forward = turn @ Vector((0, -1, 0))
        return math.degrees(math.atan2(forward.x, -forward.y))

    def _size_of(self, p: dict) -> tuple[float, float]:
        """How far along a prop a strike lands, and how far its surface is from its axis. A thing with a `grip` and an `end`
        spot is exact: that's a tool's working end, from where it's held."""
        if p.get("thing"):
            thing = p["thing"]
            if "grip" in thing.spots and "end" in thing.spots:
                return (thing.spot("end") - thing.spot("grip")).length, min(thing.size) / 2
            return max(thing.size) * 0.6, min(thing.size) / 2
        return PROPS[p["kind"]][1], PROPS[p["kind"]][2]

    def _walk_clock(self, e: dict):
        """How many frames' worth of a walk have gone by each of its frames: all of them, but for its slow motion at the end."""
        count = max(1, round(float(e["over"]) * self.fps))
        slow = e.get("slow")
        if not slow:
            return lambda n: n
        turn, share = count - round(float(slow[0]) * self.fps), float(slow[1])
        ramp = float(e.get("ramp", 0.0)) * self.fps
        if ramp:                      # time slowing down smoothly into it, rather than all at once
            return lambda n: n if n <= turn else turn + (n - turn) * share + (1 - share) * ramp * (1 - math.exp(-(n - turn) / ramp))
        return lambda n: n if n <= turn else turn + (n - turn) * share

    def _walked(self, who: str, frame: int) -> Vector:
        """How far someone's walked from where they stood by a frame, each walk going on from where the last one ended. Running into
        something, they bounce back from it a little."""
        start = Vector((*self.spec["cast"][who].get("at", (0, 0))[:2], 0))
        here = start.copy()
        for e in self.events:                  # in the order they happen
            if e["do"] == "walk" and e["who"] == who:
                begin, count = self.frame(e["t"]), max(1, round(float(e["over"]) * self.fps))
                to = Vector((*e["to"][:2], 0))
                way = to - here
                clock = self._walk_clock(e)
                here = here + way * (clock(max(0, min(count, frame - begin))) / clock(count))
                if e.get("hits") and way.length and frame > begin + count:
                    since = (frame - begin - count) * self._slowed_to(e)
                    u = min(1.0, max(0.0, since - CARRY_FRAMES) / REBOUND_FRAMES)
                    here = here + way.normalized() * (self._carried_on(since, e.get("carry", CARRIES_ON)) - REBOUND * (1 - (1 - u) ** 2))
        return here - start

    @staticmethod
    def _carried_on(since: float, amount: float) -> float:
        """How far past where their head stopped someone's body has come, this long after: a body doesn't stop because its head has."""
        return amount * math.sin(math.pi * since / CARRY_FRAMES) if 0 <= since < CARRY_FRAMES else 0.0

    @staticmethod
    def _slowed_to(e: dict) -> float:
        """How slowly what comes straight after a walk happens: at full speed, unless the walk ended so slowly that it's as good as frozen, when that's just as slow."""
        return float(e["slow"][1]) if e.get("slow") and float(e["slow"][1]) < FROZEN else 1.0

    def _land_people(self) -> None:
        """Whoever stays down lies on the ground, neither in it nor above it, measured from their body as the move leaves it."""
        if self.spec["set"] not in FLOORED:
            return
        for e in self.events:
            if e["do"] != "act" or not e.get("stays"):
                continue
            person = self.people[e["who"]]
            begin = self.frame(e["t"])
            end = min(self.total, begin + int((self._clip(e["clip"])["frames"] - float(e.get("skip", 0.0)) * self.fps) / float(e.get("speed", 1.0))))
            meshes = bounds.meshes_of(person.rig)
            kept = None
            for f in sorted({*range(begin, end, 2), end}):      # whatever a move has them doing, the lowest of them is on the ground, all the way down: nobody hops as they fall
                self.bl.frame_set(f)
                bpy.context.view_layer.update()
                kept = person.rig.location.z - self._lowest(meshes)
                person.rig.location.z = kept
                person.rig.keyframe_insert("location", index=2, frame=f)
            if end < self.total and kept is not None:
                person.rig.location.z = kept
                person.rig.keyframe_insert("location", index=2, frame=self.total)
            self._shadow_lies_down(e["who"], person, begin, end)
        self.bl.frame_set(1)

    @staticmethod
    def _lowest(meshes: list) -> float:
        """How high the lowest point of these meshes is, as they stand now."""
        graph = bpy.context.evaluated_depsgraph_get()
        low = float("inf")
        for obj in meshes:
            evaluated = obj.evaluated_get(graph)
            mesh = evaluated.to_mesh()
            co = np.zeros(len(mesh.vertices) * 3)
            mesh.vertices.foreach_get("co", co)
            place = np.array(evaluated.matrix_world)
            if len(co):
                low = min(low, float((co.reshape(-1, 3) @ place[2, :3] + place[2, 3]).min()))
            evaluated.to_mesh_clear()
        return low if low != float("inf") else 0.0

    def _shadow_lies_down(self, who: str, person, begin: int, end: int) -> None:
        """Someone's patch of shadow on the ground, going from under where they stand to all along where they lie."""
        shadow = self.shadows.get(who)
        if shadow is None:
            return
        self.bl.frame_set(end)
        bpy.context.view_layer.update()
        world = person.rig.matrix_world
        feet = (world @ person.bone("foot.L").head + world @ person.bone("foot.R").head) / 2
        along = world @ person.bone("head").tail - feet
        length = math.hypot(along.x, along.y)
        if length < 0.5:
            return
        shadow.rotation_euler.z = math.atan2(-along.x, along.y)
        shadow.keyframe_insert("rotation_euler", index=2, frame=begin)
        for f, y in ((begin, 1.0), (end, length / (2 * envs.SHADOW_RADIUS) * 1.15)):
            shadow.scale.y = y
            shadow.keyframe_insert("scale", index=1, frame=f)

    @staticmethod
    def _bends(person) -> bool:
        """Whether a body bends with its bones: if not, it can't leave its head behind."""
        return any(m.type == "ARMATURE" for m in person.body.modifiers)

    def _start_short(self) -> None:
        """Someone who starts a set distance short of where they'll stop, for a move too slow to be started from a rough place: at 1 cm a second, a guess at where they stop would have them flying."""
        for e in self.events:
            if e["do"] == "walk" and "covers" in e:
                c = self.spec["cast"][e["who"]]
                to, here = Vector((*e["to"][:2], 0)), Vector((*c.get("at", (0, 0))[:2], 0))
                c["at"] = list((to - (to - here).normalized() * float(e["covers"]))[:2])

    def _solve_hits(self) -> None:
        """Someone running into something: which of their steps they do it on, so that what they lead with gets there first, and exactly where
        they stop, measured from their body as it is at that moment and the thing itself. Nothing's guessed, and nothing goes through."""
        for e in self.events:
            if e["do"] != "walk" or not e.get("hits"):
                continue
            who, begin, count = e["who"], self.frame(e["t"]), max(1, round(float(e["over"]) * self.fps))
            arrive = min(self.total, begin + count)
            start = Vector((*self.spec["cast"][who].get("at", (0, 0))[:2], 0)) + self._walked(who, begin)
            to = Vector((*e["to"][:2], 0))
            way = (to - start).normalized()
            clip, solver = self._clip(e["clip"]), self.solvers[who]
            if e.get("with"):
                speed, clock = self._walk_speed(who, e, clip, solver), self._walk_clock(e)
                period = max(1, clip["frames"] - 1)
                least = None
                for back in range(0, min(count, round(period / speed))):
                    self.bl.frame_set(arrive - 1 - back)
                    lead = max(v.dot(way) for v in self._solid_of(who).verts) - self._on_person(who, e["with"]).dot(way)
                    if least is None or lead < least:
                        least, e["last_step"] = lead, (clock(count - 1 - back) * speed) % period
            for _ in range(2):            # its pace changes with where it stops, and with last_step that leaves how it lands alone
                self._key_people()
                self.bl.frame_set(arrive)
                gap = self._solid_of(who).reach_to(self._solid_of(e["hits"]), way)
                if gap is None:
                    raise Refused([f"{who} runs towards {e['hits']} and would miss it. Start them in line with it"])
                to = to + way * gap
                e["to"] = list(to[:2])
                if "covers" in e:         # it starts that far short of wherever that turns out to be
                    self.spec["cast"][who]["at"] = list((to - way * float(e["covers"]))[:2])
            self._key_people()
            self.bl.frame_set(arrive)
            bpy.context.view_layer.update()
            body, other = self._solid_of(who), self._solid_of(e["hits"])
            ahead = [(hit[3], v) for v, hit in ((v, other.tree.ray_cast(v, way)) for v in body.verts) if hit[0] is not None]
            # what's touching is what's nearest it, which isn't always what's furthest on: a swinging hand can be out past the side of what they ran into
            front = min(ahead, key=lambda a: a[0])[1] if ahead else max(body.verts, key=lambda v: v.dot(way))
            self.touches[who] = front.copy()
            room = [hit[3] for hit in (other.tree.ray_cast(v, way) for v in body.verts[::5] if (v - front).length > HEAD_SIZE) if hit[0] is not None]      # the rest of them comes on only as far as there's room
            e["carry"] = max(0.0, min(CARRIES_ON, min(room, default=CARRIES_ON) - CARRY_ROOM)) if self._bends(self.people[who]) else 0.0
            self._key_people()
        self.bl.frame_set(1)

    def _walk_speed(self, cid: str, e: dict, clip: dict, solver) -> float:
        """How fast a walking move plays so that their feet don't slide: the pace this walk needs, against the pace of the move's own steps."""
        begin, count = self.frame(e["t"]), max(1, round(float(e["over"]) * self.fps))
        start = Vector((*self.spec["cast"][cid].get("at", (0, 0))[:2], 0)) + self._walked(cid, begin)
        needs, own = (Vector((*e["to"][:2], 0)) - start).length / self._walk_clock(e)(count), solver.pace(clip)
        if own < 1e-4:
            raise Refused([f"{e['clip']} stays on the spot, so {cid} would slide along the ground. Use a move that travels"])
        speed = needs / own
        if not WALK_SPEEDS[0] <= speed <= WALK_SPEEDS[1]:
            way = own * self.fps
            raise Refused([f"{cid} goes {needs * self.fps:.1f} m/s, and {e['clip']}'s own steps go {way:.1f} m/s, so it would look wrong. At {way * WALK_SPEEDS[0]:.1f} "
                           f"to {way * WALK_SPEEDS[1]:.1f} m/s it looks right: change where they start or how long they take"])
        return speed

    def _followed(self, name: str, begin: int, end: int) -> dict[int, Vector]:
        """Where a shot that follows something aims, frame by frame. A person's steps are smoothed out of it, so the camera stays with
        them without bouncing along, and the picture doesn't wobble."""
        who, _, part = name.partition(":")
        if who not in self.people:
            return {f: self.aim(name, f) for f in range(begin, end + 1)}
        low, high = max(1, begin - FOLLOW_SMOOTH), min(self.total, end + FOLLOW_SMOOTH)
        marks = sorted({*range(low, high, FOLLOW_EVERY), high})
        keep = self.bl.frame_current
        placed = []
        for f in marks:
            self.bl.frame_set(f)
            placed.append(self._on_person(who, part))
        self.bl.frame_set(keep)
        raw = {marks[0]: placed[0]}
        for a, b, here, there in zip(marks, marks[1:], placed, placed[1:]):
            for f in range(a + 1, b + 1):
                raw[f] = here.lerp(there, (f - a) / (b - a))
        out = {}
        for f in range(begin, end + 1):
            now = max(low, min(high, f))
            reach = min(FOLLOW_SMOOTH, now - low, high - now)         # as far either side as there's a body to measure, so it stays centred
            near = [raw[g] for g in range(now - reach, now + reach + 1)]
            out[f] = sum(near, Vector()) / len(near)
        return out

    def _on_person(self, who: str, part: str) -> Vector:
        """A named place on someone, in the world, as they stand now."""
        person = self.people[who]
        forward, _ = self._directions(who)
        world = person.rig.matrix_world
        eyes = person.middle(person.eyes)
        return {"eyes": lambda: eyes, "mouth": person.mouth, "forehead": lambda: eyes + UP * 0.07 + forward * 0.015,
                "jaw": lambda: person.mouth() - forward * 0.045 - UP * 0.015,
                "neck": lambda: world @ person.bone("neck").head,
                "chest": lambda: world @ person.bone("spine.003").tail + forward * 0.08,
                "stomach": lambda: world @ person.bone("spine.001").head + forward * 0.1,
                "hips": lambda: world @ person.bone("spine").head,
                "body": lambda: (eyes + Vector((person.rig.location.x, person.rig.location.y, 0))) / 2,
                "touch": lambda: self.touches.get(who, eyes + UP * 0.07 + forward * 0.015),
                "crown": lambda: self._top_of_head(person, eyes - forward * 0.03),
                "shoulder_r": lambda: world @ person.bone("upper_arm.R").head + UP * 0.05,
                "shoulder_l": lambda: world @ person.bone("upper_arm.L").head + UP * 0.05,
                "hand_r": lambda: world @ person.bone("hand.R").tail + UP * 0.04,
                "hand_l": lambda: world @ person.bone("hand.L").tail + UP * 0.04}[part]()

    def _top_of_head(self, person, over: Vector) -> Vector:
        """The top of someone's head above a point, by casting a ray down at the body as it's posed, and a little for hair."""
        bpy.context.view_layer.update()
        evaluated = person.body.evaluated_get(bpy.context.evaluated_depsgraph_get())
        inverse = person.body.matrix_world.inverted()
        origin = inverse @ (over + UP * 0.6)
        hit, where, _, _ = evaluated.ray_cast(origin, (inverse.to_3x3() @ -UP).normalized())
        top = person.body.matrix_world @ where if hit else over + UP * 0.12
        return top + UP * 0.02

    def _point(self, value) -> Vector:
        return Vector(value) if isinstance(value, (list, tuple)) else self.aim(value)

    def _along(self, prop: str, meters: float) -> Vector:
        p = self.props[prop]
        if p.get("bitten"):
            return p["bite"] + p["along"] * meters
        return p["palm"] + p["points"] * meters

    # --- the cast --------------------------------------------------------------------------------------------------

    def _clip(self, name: str) -> dict:
        if name not in self._clips:
            self._clips[name] = clips.read(self.catalog[name])
        return self._clips[name]

    def build_people(self) -> None:
        for cid, c in self.spec["cast"].items():
            if c["type"] != "person":
                continue
            at = c.get("at", (0, 0))
            person = people.Person(self.folders[c["character"]], at=(at[0], at[1], 0), rot=self._facing(cid))
            self.people[cid] = person
            self.knocks[cid] = []
            self.solvers[cid] = clips.Solver(person)
            if self.spec["set"] in ("sky_set", "place"):      # a floor that's only a picture can't catch a real shadow, and in a place the sky's too soft to make one
                shadow = envs.floor_shadow(f"{cid}.shadow", at)
                under = shadow.constraints.new("COPY_LOCATION")     # it stays under their hips, as they walk or fall
                under.target, under.subtarget, under.use_z = person.rig, person.bones["spine"], False
                self.shadows[cid] = shadow
        for e in self.events:             # who gets hit has to be known before their body's keyed
            if e["do"] == "knock":
                axis = Vector(e.get("axis", (0, 1, 0))).normalized()
                self.knocks[e["who"]].append((self.frame(e["t"]), axis, float(e["size"])))
            elif e["do"] == "act" and e.get("stays"):      # whoever goes down hits the ground, and their head rings with it
                for cue in self._landing(e):
                    self.knocks[e["who"]].append((cue["frame"], self._directions(e["who"])[1], LANDS_HARD))

    def _key_people(self) -> None:
        for offset, (cid, solver) in enumerate(self.solvers.items()):
            c = self.spec["cast"][cid]
            person = self.people[cid]
            inverse = person.rig.matrix_world.to_quaternion().inverted()

            holding = {e["hand"]: person.fist(e["hand"], self._handle_radius(self.props[e["prop"]])) for e in self.events if e["do"] == "hold" and e["who"] == cid}

            downs = [self.frame(e["t"]) for e in self.events if e["do"] == "act" and e.get("stays") and e["who"] == cid]
            stops = [(self.frame(e["t"]) + max(1, round(float(e["over"]) * self.fps)), self._slowed_to(e), e.get("carry", CARRIES_ON)) for e in self.events if e["do"] == "walk" and e.get("hits") and e["who"] == cid]

            def adjust(frame, pose, solver=solver, cid=cid, person=person, inverse=inverse, holding=holding, downs=downs, stops=stops):
                solver.mirror_fingers(pose)
                for side, closed in holding.items():
                    self._close_hand(person, pose, side, closed)
                for arrive, slowed, amount in stops:
                    carried = self._carried_on((frame - arrive) * slowed, amount)
                    if carried:              # their head stays where it stopped, and the rest of them comes on under it
                        lean = carried / HEAD_HELD_BACK
                        for name, share in (("spine.001", 0.2), ("spine.002", 0.3), ("spine.003", 0.3), ("neck", 0.2)):
                            bone = person.bones[name]
                            pose[bone] = pose[bone] @ Quaternion(solver.rest[bone].inverted() @ (inverse @ self._directions(cid)[1]), lean * share)
                for start in downs:
                    if frame >= start:
                        self._gone_slack(person, pose, min(1.0, (frame - start) / 18), (frame - start) / self.fps, solver, inverse, self._directions(cid)[1])
                for swing in self.swings.get(cid, ()):
                    self._into_blow(frame, pose, swing, person, solver, inverse)
                for start, axis, size in self.knocks[cid]:
                    for name, share in (("head", 1.0), ("neck", 0.4), ("spine.003", 0.18), ("spine.002", 0.09)):
                        angle = math.radians(ring_down(frame, start, size * share))
                        if angle:
                            bone = person.bones[name]
                            local = solver.rest[bone].inverted() @ (inverse @ axis)
                            pose[bone] = pose[bone] @ Quaternion(local, angle)

            stance, life, at = self._clip(c["stance"]), c.get("life", 0.22), 1
            moves = sorted((e for e in self.events if e["do"] in ("act", "walk") and e["who"] == cid), key=lambda e: e["t"])
            for n, e in enumerate(moves):
                start = self.frame(e["t"])
                if start > at:
                    solver.play(stance, at, frames=start - at, blend=0 if at == 1 else MOVE_BLEND, speed=life, offset=offset * 9, adjust=adjust)
                clip = self._clip(e["clip"])
                walks = e["do"] == "walk"
                speed = self._walk_speed(cid, e, clip, solver) if walks else float(e.get("speed", 1.0))
                skip = float(e.get("skip", 0.0)) * self.fps
                length = round(float(e["over"]) * self.fps) if "over" in e else int((clip["frames"] - skip) / speed)
                length = min(length, self.total - start + 1)
                clock = self._walk_clock(e) if walks else None
                step = e["last_step"] - clock(length - 1) * speed if "last_step" in e else skip      # counted back from the step they arrive on
                calm = self._calmed(clip, solver, person) if walks else 1.0

                def doing(frame, pose, adjust=adjust, calm=calm, person=person):
                    if calm < 1.0:
                        self._twist_by(pose, person, calm)
                    adjust(frame, pose)

                solver.play(clip, start, frames=length, blend=0 if start == 1 else MOVE_BLEND, speed=speed, offset=step, adjust=doing, on_the_spot=walks, clock=clock)
                at = start + length
                if walks and n + 1 == len(moves) and self._slowed_to(e) < FROZEN and at <= self.total:      # in slow motion this slow, they've no time to do anything else
                    solver.play(clip, at, frames=self.total - at + 1, blend=0, speed=0.0, offset=clock(length) * speed + step, adjust=doing, on_the_spot=True)
                    at = self.total + 1
                elif walks and e.get("hits") and at <= self.total:      # they're still in their stride while their body comes on, before anything else can happen to it
                    until = min(at + CARRY_FRAMES, self.frame(moves[n + 1]["t"]) if n + 1 < len(moves) else self.total + 1, self.total + 1)
                    if until > at:
                        solver.play(clip, at, frames=until - at, blend=0, speed=0.0, offset=clock(length) * speed + step, adjust=doing, on_the_spot=True)
                        at = until
                if e.get("stays") and at <= self.total:        # they stay as it left them, until the next move or the end
                    until = self.frame(moves[n + 1]["t"]) if n + 1 < len(moves) else self.total + 1
                    if until > at:
                        solver.play(clip, at, frames=until - at, blend=0, speed=0.0, offset=clip["frames"] - 1, adjust=adjust)
                        at = until
            if at <= self.total:
                solver.play(stance, at, frames=self.total - at + 1, blend=0 if at == 1 else MOVE_BLEND, speed=life, offset=offset * 9, adjust=adjust)
            self._key_walks(cid, person)
        self.bl.frame_set(1)
        bpy.context.view_layer.update()

    def _key_walks(self, cid: str, person) -> None:
        """Someone going from one place to another, at a steady speed."""
        walks = [e for e in self.events if e["do"] == "walk" and e["who"] == cid]
        if not walks:
            return
        start = Vector((*self.spec["cast"][cid].get("at", (0, 0))[:2], 0))
        for f in self._walk_marks(cid):
            look.key(person.rig, f, location=start + self._walked(cid, f))
        look.ease(person.rig, "LINEAR")

    def _walk_marks(self, cid: str) -> list[int]:
        """The frames a person's way along the ground changes at, with a straight line between them."""
        marks = {1, self.total}
        for e in self.events:
            if e["do"] == "walk" and e["who"] == cid:
                begin, count = self.frame(e["t"]), max(1, round(float(e["over"]) * self.fps))
                marks |= {begin, begin + count}
                if e.get("slow"):
                    marks.add(begin + count - round(float(e["slow"][0]) * self.fps))
                if e.get("ramp"):
                    marks |= set(range(begin, begin + count + 1))
                if e.get("hits"):
                    marks |= set(range(begin + count, begin + count + round((REBOUND_FRAMES + CARRY_FRAMES) / self._slowed_to(e)) + 1, max(1, round(1 / max(self._slowed_to(e), 0.05)))))
        return sorted(f for f in marks if f <= self.total)

    def _lights_on(self, cid: str, lights: list) -> None:
        """Lights on someone who goes somewhere go with them, or they'd run out of the light."""
        if not any(e["do"] == "walk" and e["who"] == cid for e in self.events):
            return
        keep = self._walked(cid, self.bl.frame_current)
        for obj in lights:
            base = obj.location.copy() - keep
            for f in self._walk_marks(cid):
                look.key(obj, f, location=base + self._walked(cid, f))
            look.ease(obj, "LINEAR")

    @staticmethod
    def _twist_of(q: Quaternion) -> float:
        """How far a bone's turned about its own length, in radians."""
        return 2 * math.atan2(q.y, q.w)

    @staticmethod
    def _twist_by(pose: dict, person, k: float) -> None:
        """A body's shoulders turning against its hips only this share of what a clip has them doing, with the rest of what it does left as it is."""
        for name in ("spine.001", "spine.002", "spine.003"):
            bone = person.bones[name]
            q = pose.get(bone)
            if q is not None:
                twist = Quaternion((q.w, 0, q.y, 0)).normalized()
                pose[bone] = q @ twist.inverted() @ Quaternion((0, 1, 0), Stage._twist_of(twist) * k)

    def _calmed(self, clip: dict, solver, person) -> float:
        """The share of a moving clip's twist that's kept, so a body's shoulders don't turn further than a real body's do."""
        totals = []
        for i in range(0, max(1, clip["frames"] - 1), 2):
            pose = solver._frame(clip, i)
            totals.append(sum(self._twist_of(Quaternion((q.w, 0, q.y, 0)).normalized()) for q in (pose.get(person.bones[name]) for name in ("spine.001", "spine.002", "spine.003")) if q is not None))
        half = math.degrees(max(totals) - min(totals)) / 2 if totals else 0.0
        return min(1.0, MOST_TWIST / half) if half else 1.0

    @staticmethod
    def _gone_slack(person, pose: dict, k: float, since: float, solver, inverse, right: Vector) -> None:
        """Someone who's gone down: their hands going slack, whatever a clip had them doing, and their chest still rising and falling."""
        for side in "LR":
            for finger, bends in RELAXED.items():
                for joint, bend in enumerate(bends, 1):
                    bone = person.bones.get(f"{finger}.0{joint}.{side}")
                    if bone is not None:
                        pose[bone] = pose.get(bone, Quaternion()).slerp(Quaternion((1, 0, 0), math.radians(bend)), k)
        breath = math.radians(1.1) * k * math.sin(since * BREATHS * math.tau)
        for name in ("spine.002", "spine.003"):
            bone = person.bones[name]
            pose[bone] = pose[bone] @ Quaternion(solver.rest[bone].inverted() @ (inverse @ right), breath)

    @staticmethod
    def _close_hand(person, pose: dict, side: str, closed: dict) -> None:
        """A hand holding something closes on it, as far as each finger goes before it would enter it, whatever its stance has the fingers doing."""
        for finger, bends in closed.items():
            for joint, bend in enumerate(bends, 1):
                bone = person.bones.get(f"{finger}.0{joint}.{side}")
                if bone is not None:
                    pose[bone] = Quaternion((1, 0, 0), math.radians(bend))

    @staticmethod
    def _into_blow(frame: int, pose: dict, swing: tuple, person, solver, inverse) -> None:
        """Someone putting their body into a blow: their shoulders turning away and leaning back as they draw back, then through it and over it as it lands, and easing back."""
        wind, drive, hit, sign, right, look_turn, look_up = swing
        if frame <= wind:
            return
        if frame <= drive:
            k = (frame - wind) / max(1, drive - wind)
            k = k * k * (3 - 2 * k)
            turn, lean = WIND_TURN * k, WIND_LEAN * k
        elif frame <= hit:
            k = ((frame - drive) / max(1, hit - drive)) ** 2
            turn, lean = WIND_TURN + (BLOW_TURN - WIND_TURN) * k, WIND_LEAN + (BLOW_LEAN - WIND_LEAN) * k
        else:
            k = max(0.0, 1 - (frame - hit) / BLOW_EASE)
            k = k * k * (3 - 2 * k)
            turn, lean = BLOW_TURN * k, BLOW_LEAN * k
        for name, share in (("spine.001", 0.25), ("spine.002", 0.35), ("spine.003", 0.4)):
            bone = person.bones[name]
            rest = solver.rest[bone].inverted()
            pose[bone] = pose[bone] @ Quaternion(rest @ (inverse @ UP), math.radians(turn * sign * share)) @ Quaternion(rest @ (inverse @ right), math.radians(-lean * share))
        # and their head stays on what they're hitting, whatever the rest of them does
        if frame <= drive:
            k = (frame - wind) / max(1, drive - wind)
            k = k * k * (3 - 2 * k)
        elif frame > hit:
            k = max(0.0, 1 - (frame - hit) / (BLOW_EASE * 2))
        else:
            k = 1.0
        for name, share in (("neck", 0.4), ("head", 0.6)):
            bone = person.bones[name]
            rest = solver.rest[bone].inverted()
            pose[bone] = pose[bone] @ Quaternion(rest @ (inverse @ UP), math.radians((look_turn - turn * sign) * k * share)) @ Quaternion(rest @ (inverse @ right), math.radians((look_up + lean) * k * share))

    def _handle_radius(self, p: dict) -> float:
        """How thick what's held is where the hand closes on it, measured from its mesh, before it's moved to be held."""
        if "radius" not in p:
            bpy.context.view_layer.update()
            thing, place = p.get("thing"), p["root"].matrix_world
            middle = place @ thing.spot("grip") if thing and "grip" in thing.spots else place.translation.copy()
            turn = place.to_3x3().normalized()
            solid = bounds.Solid(bounds.meshes_of(p["root"]))
            found = sorted(1.0 - hit[2] for hit in (solid.ray(middle + way, -way) for way in (turn @ Vector((math.cos(k * math.tau / 8), math.sin(k * math.tau / 8), 0)) for k in range(8))) if hit)
            p["radius"] = max(found[len(found) // 2], 0.004) if found else 0.014
        return p["radius"]

    def build_props(self) -> None:
        for cid, c in self.spec["cast"].items():
            if c["type"] != "prop":
                continue
            if c["prop"] not in PROPS:
                self._build_thing(cid, c)
                continue
            root = bpy.data.objects.new(cid, None)
            self.bl.collection.objects.link(root)
            root.rotation_mode = "QUATERNION"
            PROPS[c["prop"]][0](root)
            palm = Vector(c.get("at", (0, 0, 1)))
            points = Vector(c.get("points", (0, 0, 1))).normalized()
            fingers = Vector(c.get("up", (0, 1, 0)))
            root.location, root.rotation_quaternion = palm, _axes(points, fingers)
            self.props[cid] = {"root": root, "kind": c["prop"], "palm": palm, "points": points, "fingers": fingers,
                               "holder": None}

    def _build_thing(self, cid: str, c: dict) -> None:
        """A thing from the library: `at` is where its underside sits, and it faces the way a person would."""
        thing = things.Thing(self.thing_folders[c["prop"]], size=float(c.get("size", 1.0)))
        root = thing.root
        root.name = cid
        if c.get("smooth"):                # the folds smoothed out of a brain, to make it a bird's
            bpy.context.view_layer.update()
            glow.mark_part(bounds.meshes_of(root), (0, 0, 0), 1e6, name=SMOOTHED)
            glow.smooth_part(bounds.meshes_of(root), int(c["smooth"]), name=SMOOTHED)
        at = c.get("at", (0, 0, 0))
        palm = Vector((at[0], at[1], at[2] if len(at) > 2 else 0.0)) + UP * (thing.size.z / 2)   # one that's `on` something finds its height later
        if "points" in c:
            turn = _axes(Vector(c["points"]), Vector(c.get("up", (0, 1, 0))))
        else:
            turn = Quaternion(UP, math.radians(self._facing(cid)))
        root.location, root.rotation_quaternion = palm, turn
        self.props[cid] = {"root": root, "kind": c["prop"], "thing": thing, "palm": palm, "points": turn @ UP,
                           "fingers": turn @ Vector((0, 1, 0)), "holder": None, "liquids": bounds.liquids_of(root)}

    def _under(self, under: str) -> bounds.Solid | None:
        if under == "set":
            return bounds.Solid(self.solids) if self.solids else None
        return bounds.Solid(bounds.meshes_of(self.props[under]["root"]))

    @staticmethod
    def _balanced(root) -> Quaternion:
        """How far a thing turns as it comes to rest on something flat: it tips over the point it's on, a degree at a time, until its middle is over what's bearing on the
        surface, or nearly over its one point, if it's round."""
        bpy.context.view_layer.update()
        points = np.array([tuple(v) for v in bounds.Solid(bounds.meshes_of(root))._sample(4000)])
        middle, turned = points.mean(axis=0), Quaternion()
        size = float(np.linalg.norm(points.max(axis=0) - points.min(axis=0)))
        for _ in range(180):
            feet = points[points[:, 2] < points[:, 2].min() + RESTS_ON]
            flat = feet[:, :2]
            over = middle[:2]
            nearest = feet[int(np.argmin(np.linalg.norm(flat - over, axis=1)))]
            apart = over - nearest[:2]
            far = float(np.linalg.norm(apart))
            if far < size * 0.015 or _inside_outline(over, flat):
                break
            q = Quaternion(Vector((-apart[1] / far, apart[0] / far, 0)), math.radians(1))
            matrix = np.array(q.to_matrix())
            points = (points - nearest) @ matrix.T + nearest
            middle = (middle - nearest) @ matrix.T + nearest
            turned = q @ turned
        return turned

    def _rest_on(self, cid: str, under: str) -> None:
        """Lowered onto what's under it until the two touch, measured from the meshes. It goes where `at` says across the set, or
        over what it's on: its `by` spot, or its middle, over the other's `onto` spot, or its middle."""
        c = self.spec["cast"][cid]
        p = self.props[cid]
        root, thing = p["root"], p["thing"]
        if under == "set":                 # a flat surface: it comes to rest the way it would, not balanced on a point
            root.rotation_quaternion = self._balanced(root) @ root.rotation_quaternion
            p.update(points=root.rotation_quaternion @ UP, fingers=root.rotation_quaternion @ Vector((0, 1, 0)))
        turn = root.rotation_quaternion.copy()
        at = c.get("at")
        if at:
            x, y = at[0], at[1]
        else:
            if under == "set":
                over = Vector()
            else:
                q = self.props[under]
                over = q["root"].matrix_world @ q["thing"].spot(c["onto"]) if c.get("onto") else q["root"].matrix_world.translation
            own = turn @ thing.spot(c["by"]) if c.get("by") else Vector()
            x, y = over.x - own.x, over.y - own.y
        below = self._under(under)
        top = below.high.z if below else 0.0
        root.location = (x, y, top + thing.size.z + 0.3)
        bpy.context.view_layer.update()
        mine = bounds.Solid(bounds.meshes_of(root))
        if below is None:
            root.location.z -= mine.low.z - REST_GAP
        else:
            drop = mine.drop_onto(below)
            if drop is None:
                raise Refused([f"{cid} is on {under}, but it isn't over {under}: nothing's under it to rest on"])
            root.location.z -= drop - REST_GAP + float(c.get("sinks", 0.0))
        p["palm"] = root.location.copy()
        bpy.context.view_layer.update()
        if under != "set" and any(e.get("prop") == under and e["do"] in MOVERS for e in self.events):
            self._carry(cid, self.props[under]["root"])

    def _rest_against(self, cid: str) -> None:
        """Brought up to another thing from the side, at a height, until it touches, measured from the meshes: the way a bird comes to a
        tree, or a nail to a wall. Its first `by` spot, or its whole self, meets it first. With a second spot, it tips forward or back until
        that one touches too, and with `into` it goes that much further in."""
        c, p = self.spec["cast"][cid], self.props[cid]
        root, thing = p["root"], p["thing"]
        other = self._solid_of(c["against"])
        turn = root.rotation_quaternion.copy()
        forward = turn @ Vector((0, -1, 0))
        way = Vector((*c["way"], 0)).normalized() if c.get("way") else Vector((forward.x, forward.y, 0)).normalized()
        turn = Quaternion(way.cross(UP).normalized(), math.radians(float(c.get("tip", 0.0)))) @ turn
        start = Vector((c["at"][0], c["at"][1], float(c["height"])))
        by = c.get("by") or []
        if by:
            met = other.ray(start, way)
            if met is None:
                raise Refused([f"{cid} comes up to {c['against']} from {list(c['at'])} at a height of {c['height']} m, and misses it. Start it in line with it"])
            if len(by) == 2:
                turn = self._tip_to_touch(cid, c["against"], other, met[0], turn, way, thing.spot(by[1]) - thing.spot(by[0]))
            root.rotation_quaternion = turn
            root.location = met[0] - way * REST_GAP - turn @ thing.spot(by[0])
        else:
            root.location = start
            bpy.context.view_layer.update()
            reach = self._solid_of(cid).reach_to(other, way)
            if reach is None:
                raise Refused([f"{cid} comes up to {c['against']} from {list(c['at'])} at a height of {c['height']} m, and misses it. Start it in line with it"])
            root.location = start + way * (reach - REST_GAP)
        root.location = root.location + way * float(c.get("into", 0.0))
        p.update(palm=root.location.copy(), points=turn @ UP, fingers=turn @ Vector((0, 1, 0)))
        bpy.context.view_layer.update()
        for bend in c.get("bends") or []:
            self._bend_to_touch(cid, c["against"], other, way, bend)

    def _bend_to_touch(self, cid: str, name: str, other: bounds.Solid, way: Vector, bend: dict) -> None:
        """A part of it bending at a spot, as little as it can, until another of its spots touches what it's against: a bird's tail braced on the bark. It stays bent there."""
        p = self.props[cid]
        root, thing = p["root"], p["thing"]
        hook = self._bend_hook(cid, bend["about"], bend["near"], float(bend["radius"]))
        axis = self._rock_axis(bend, thing)
        about, spot = thing.spot(bend["about"]), thing.spot(bend["spot"])
        turned = Quaternion((0, 0, 1), math.radians(float(bend.get("yaw", 0.0))))     # a scan's head can be looking off to one side: it's turned to what it's against first

        def gap(degrees: float) -> float | None:
            hit = other.ray(root.matrix_world @ (about + (Quaternion(axis, math.radians(degrees)) @ turned) @ (spot - about)) - way, way)
            return hit[2] - 1.0 if hit else None

        for step in range(MOST_TIP):
            for sign in (1, -1):
                low, high = sign * step, sign * (step + 1)
                near, far = gap(low), gap(high)
                if near is None or far is None or near * far > 0:
                    continue
                for _ in range(24):
                    middle = (low + high) / 2
                    here = gap(middle)
                    if here is None or here * near > 0:
                        low, near = middle, here if here is not None else near
                    else:
                        high = middle
                rest = Quaternion(axis, math.radians((low + high) / 2)) @ turned
                hook.rotation_quaternion = rest
                p.setdefault("hook_rest", {})[hook.name] = rest
                bpy.context.view_layer.update()
                return
        raise Refused([f"{cid}'s {bend['spot']} can't reach {name}, however far it bends at {bend['about']}. Bring it nearer"])

    @staticmethod
    def _roomiest(shell: bounds.Solid, at: Vector) -> Vector:
        """The roomiest place near a place inside something: it keeps stepping away from the nearest surface until there's nowhere roomier."""
        here, step = at.copy(), 0.002
        for _ in range(80):
            near = shell.tree.find_nearest(here)
            if near[0] is None or (here - near[0]).length < 1e-7:
                break
            here = here + (here - near[0]).normalized() * step
            step *= 0.97
        return here

    def _fit_inside(self, cid: str) -> None:
        """Inside another thing, such as a brain in a head: it goes in the roomiest place near a spot, or exactly on that spot if it's told to `stay`, and it's sized to
        fit, all of it, measured from the meshes. If it's been given a size, that's checked instead. What it's inside may be a shell with holes in it."""
        c, p = self.spec["cast"][cid], self.props[cid]
        root, thing = p["root"], p["thing"]
        other = c["inside"]
        bpy.context.view_layer.update()
        shell = self._solid_of(other)
        if other in self.people:           # someone's head, as they stand at rest, before they're moved
            person = self.people[other]
            at, outer_turn = person.rig.matrix_world @ person.head_middle(), person.rig.matrix_world.to_quaternion()
        else:
            q = self.props[other]
            at, outer_turn = q["root"].matrix_world @ self._bent_spot(q, c["near"]) if c.get("near") else (shell.low + shell.high) / 2, q["root"].rotation_quaternion
            bent = self._hook_over(q, q["thing"].spot(c["near"])) if c.get("near") else None
            if bent is not None:          # what's inside a part that's bent is turned with it
                outer_turn = bent.matrix_world.to_quaternion()
        centre = at if c.get("stay") else self._roomiest(shell, at)
        if "points" in c:                  # its turn is counted in the axes of what it's in, however that's turned
            root.rotation_quaternion = outer_turn @ root.rotation_quaternion
            p.update(points=root.rotation_quaternion @ UP, fingers=root.rotation_quaternion @ Vector((0, 1, 0)))
        by = thing.spot(c["by"]) if c.get("by") else Vector()     # what goes on that place is this spot of it, or its middle
        root.location = centre - root.rotation_quaternion @ by
        bpy.context.view_layer.update()
        reaches = [point - centre for point in self._solid_of(cid)._sample(FIT_POINTS)]

        def largest(at: Vector, rows: list) -> float:
            """The largest it can be, with all of it inside, with that place here."""
            pokes = lambda k: shell.pokes_by([at + reach * k for reach in rows])
            if pokes(FIT_LEAST) > POKES_OUT:
                return 0.0
            fits, too_big = FIT_LEAST, FIT_MOST
            for _ in range(9):
                middle = math.sqrt(fits * too_big)
                if pokes(middle) > POKES_OUT:
                    too_big = middle
                else:
                    fits = middle
            return fits

        few = reaches[:: FIT_FEWER]
        fits = largest(centre, few)
        if not c.get("stay"):         # it goes where it fits best: a skull's jaw says where it can be in a head as much as its dome does
            size = (shell.high - shell.low).length
            for step in (size * FIT_STEP, size * FIT_STEP / 2, size * FIT_STEP / 4):
                moved = True
                while moved:
                    moved = False
                    for way in (Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1)), Vector((-1, 0, 0)), Vector((0, -1, 0)), Vector((0, 0, -1))):
                        tried = largest(centre + way * step, few)
                        if tried > fits * 1.002 and (centre + way * step - at).length < size * FIT_WANDERS:
                            fits, centre, moved = tried, centre + way * step, True
        fits = largest(centre, reaches)
        if fits <= 0.0:
            raise Refused([f"{cid} is inside {other}, but {other} isn't all round it there. Put it nearer a spot in the middle of {other}"])
        room = float(c.get("room", ROOM))
        if "size" in c:
            if fits < room:
                raise Refused([f"{cid} is too big to go inside {other}: at most {round(float(c['size']) * fits / room, 3)} of its size fits, or leave its size out and it's worked out"])
        else:
            thing.resize(fits * room)
            root.location = centre - root.rotation_quaternion @ (thing.spot(c["by"]) if c.get("by") else Vector())
        p.update(palm=root.location.copy(), inside_of=other)
        bpy.context.view_layer.update()
        if other in self.people:
            self._carry(cid, self.people[other].attach("head", root.location.copy(), f"{cid}.in_head"))
        else:
            self._carry(cid, (self._hook_over(self.props[other], self.props[other]["thing"].spot(c["near"])) if c.get("near") else None) or self.props[other]["root"])

    def _carry(self, cid: str, parent) -> None:
        """Something goes along with what it's inside, from where it is now: where it's put after this is counted as if that hadn't moved."""
        p = self.props[cid]
        bpy.context.view_layer.update()
        p["root"].parent = parent
        p["root"].matrix_parent_inverse = parent.matrix_world.inverted()
        p["root"][bounds.CARRIED] = True
        p["carried"] = True
        bpy.context.view_layer.update()

    def _inside_chain(self, cid: str) -> list[str]:
        """All that something's inside, nearest first."""
        chain, c = [], self.spec["cast"][cid]
        while c.get("inside"):
            chain.append(c["inside"])
            c = self.spec["cast"][c["inside"]]
        return chain

    def _poking_out(self) -> list[str]:
        """Anything that's said to be inside something and reaches outside it, at any moment of the scene."""
        out = []
        solids: dict[tuple, bounds.Solid] = {}

        def solid(name: str, f: int) -> bounds.Solid:
            if (name, f) not in solids:
                solids[(name, f)] = self._solid_of(name)
            return solids[(name, f)]

        for cid, p in self.props.items():
            if not p.get("inside_of"):
                continue
            other = p["inside_of"]
            moves = {e["do"] for e in self.events if e.get("prop") in (cid, other)} & {"slide", "squash", "press", "go", "fly", "rock", "spin"}
            frames = sorted({*range(1, self.total + 1, 3), self.total}) if moves or other in self.people else [1]
            worst, when = 0.0, 0
            for f in frames:
                self.bl.frame_set(f)
                bpy.context.view_layer.update()
                here = solid(other, f).pokes_by(solid(cid, f)._sample(CHECK_POINTS))
                if here > worst:
                    worst, when = here, f
            if worst > POKES_OUT:
                out.append(f"{cid} pokes out of {other} by {worst * 100:.1f} cm, at {(when - 1) / self.fps:.2f} s of this scene. Leave its size to be worked out, or keep what moves it inside")
        return out

    def _outside_outline(self) -> list[str]:
        """Anything inside something that shows outside its outline, from where each shot's looking at it. Being surrounded isn't enough: something in a hollow of a scan's neck has it on nearly every side and
        can still sit outside its outline in the picture. What the viewer sees is what counts: a line from the lens through each of its points has to meet what it's inside."""
        inner = [cid for cid, p in self.props.items() if p.get("inside_of")]
        if not inner:
            return []
        solids: dict[tuple, bounds.Solid] = {}
        worst: dict[tuple, tuple] = {}

        def solid(name: str, f: int) -> bounds.Solid:
            if (name, f) not in solids:
                solids[(name, f)] = self._solid_of(name)
            return solids[(name, f)]

        for cut in self.cuts:
            allow = max(float(cut["frame"]) * OUTLINE_SHARE, 0.0004)
            for f in sorted({*range(cut["begin"], cut["end"], OUTLINE_EVERY), cut["end"]}):
                self.bl.frame_set(f)
                bpy.context.view_layer.update()
                lens = cut["camera"].matrix_world.translation.copy()
                for cid in inner:
                    if not self._shown(cid, f):
                        continue
                    for other in self._inside_chain(cid):
                        if not self._shown(other, f):
                            continue
                        shell = solid(other, f)
                        for point in solid(cid, f)._sample(OUTLINE_POINTS):
                            away = self._past_outline(shell, lens, point, allow)
                            if away > worst.get((cid, other), (0.0,))[0]:
                                worst[(cid, other)] = (away, cut["t"], (f - 1) / self.fps)
            solids.clear()
        return [f"{cid} shows outside the outline of {other} by {away * 100:.1f} cm, in the shot at {t} s, at {when:.2f} s of this scene. Make it smaller with room, or put it nearer the middle of {other}, or look from another side"
                for (cid, other), (away, t, when) in worst.items()]

    @staticmethod
    def _past_outline(shell: bounds.Solid, lens: Vector, point: Vector, allow: float) -> float:
        """How far a point is from something, if it's outside that thing's outline from a lens, and 0 if it's within it. A line through a tiny hole in a scan isn't past its outline, so the lines just beside it are tried too."""
        way = point - lens
        if shell.tree.ray_cast(lens, way.normalized())[0] is not None:
            return 0.0
        side = way.cross(UP).normalized()
        over = side.cross(way).normalized()
        for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            if shell.tree.ray_cast(lens, (point + side * (a * allow) + over * (b * allow) - lens).normalized())[0] is not None:
                return 0.0
        found = shell.tree.find_nearest(point)
        return found[3] if found[3] is not None else 0.0

    def _tip_to_touch(self, cid: str, name: str, other: bounds.Solid, met: Vector, turn: Quaternion, way: Vector, along: Vector) -> Quaternion:
        """Turned about its side, as little as it can be, until a second spot `along` from where it's touching touches too."""
        side = way.cross(UP).normalized()

        def gap(degrees: float) -> float | None:
            hit = other.ray(met + (Quaternion(side, math.radians(degrees)) @ turn) @ along - way, way)
            return hit[2] - 1.0 if hit else None

        for step in range(MOST_TIP):
            for sign in (1, -1):
                low, high = sign * step, sign * (step + 1)
                near, far = gap(low), gap(high)
                if near is None or far is None or near * far > 0:
                    continue
                for _ in range(24):
                    middle = (low + high) / 2
                    here = gap(middle)
                    if here is None or here * near > 0:
                        low, near = middle, here if here is not None else near
                    else:
                        high = middle
                return Quaternion(side, math.radians((low + high) / 2)) @ turn
        raise Refused([f"{cid} can't touch {name} with both its spots, however far it tips. Bring it to a flatter place on it"])

    def _fix_to(self, cid: str) -> None:
        """Fixed to another thing at a point, from any side: its `by` spot, or its middle, exactly on the other's spot."""
        c = self.spec["cast"][cid]
        p = self.props[cid]
        other, _, spot = c["to"].partition(":")
        q = self.props[other]
        there = q["root"].matrix_world @ q["thing"].spot(spot)
        own = p["root"].rotation_quaternion @ p["thing"].spot(c["by"]) if c.get("by") else Vector()
        p["root"].location = there - own
        p["palm"] = p["root"].location.copy()
        bpy.context.view_layer.update()

    def settle(self) -> None:
        """Everything that's on something or fixed to something, from the bottom of each stack up."""
        cast = self.spec["cast"]
        below = {cid: c.get("on") or c.get("against") or c.get("inside") or c["to"].partition(":")[0] for cid, c in cast.items() if c.get("on") or c.get("to") or c.get("against") or c.get("inside")}
        waiting = list(below)
        for _ in range(len(waiting) + 1):
            for cid in list(waiting):
                if below[cid] not in waiting:
                    if cast[cid].get("on"):
                        self._rest_on(cid, below[cid])
                    elif cast[cid].get("against"):
                        self._rest_against(cid)
                    elif cast[cid].get("inside"):
                        self._fit_inside(cid)
                    else:
                        self._fix_to(cid)
                    waiting.remove(cid)
        if waiting:
            raise Refused([f"{', '.join(waiting)} are each resting on the other"])

    def _wear(self, e: dict) -> None:
        """On a person's head: the head and the inside of the hat are measured, the hat's made to fit unless its size was said, and
        it comes down until its inside meets the top of the head or its rim reaches the brow. It rides on the head from there, and
        the hair it covers doesn't come through."""
        who, p = e["who"], self.props[e["prop"]]
        person, root, thing = self.people[who], p["root"], p["thing"]
        self.bl.frame_set(1)
        bpy.context.view_layer.update()
        place = person.rig.matrix_world
        bone = person.bone("head")
        up = (place @ bone.tail - place @ bone.head).normalized()
        if up.dot(UP) < 0.7:          # a head tipped this far isn't what a hat is level with
            up = UP.copy()
        forward, _ = self._directions(who)
        forward = (forward - up * forward.dot(up)).normalized()
        side = forward.cross(up).normalized()
        body = bounds.Solid([person.body])
        eyes = person.middle(person.eyes)
        brow = eyes + up * 0.035 - forward * 0.05

        def span(way: Vector) -> tuple[Vector, Vector]:
            near, far = body.ray(brow + way * 0.4, -way), body.ray(brow - way * 0.4, way)
            if near is None or far is None:
                raise Refused([f"{who}'s head can't be measured at the brow, to fit {e['prop']}"])
            return near[0], far[0]

        front, back = span(forward)
        left, right = span(side)
        depth, width = (front - back).dot(forward), (left - right).dot(side)
        middle = eyes - forward * (eyes - (front + back) / 2).dot(forward) - side * (eyes - (left + right) / 2).dot(side)
        crown = body.ray(middle + up * 0.5, -up)
        if crown is None:
            raise Refused([f"{who}'s head can't be measured from above, to fit {e['prop']}"])
        top = crown[0]
        # the hat, on its own, upright at the world's middle
        root.location, root.rotation_quaternion = (0, 0, 0), Quaternion()
        bpy.context.view_layer.update()
        hat = bounds.Solid(bounds.meshes_of(root))
        rim = hat.low.z
        mouth = Vector((0, 0, rim + (hat.high.z - rim) * 0.3))
        walls = {}
        for name, way in (("front", Vector((0, -1, 0))), ("back", Vector((0, 1, 0))), ("left", Vector((-1, 0, 0))), ("right", Vector((1, 0, 0)))):
            hit = hat.ray(mouth, way)
            walls[name] = hit[0] if hit else mouth + way * thing.size.x / 2
        inner_x, inner_y = walls["right"].x - walls["left"].x, walls["back"].y - walls["front"].y
        centre = Vector(((walls["right"].x + walls["left"].x) / 2, (walls["back"].y + walls["front"].y) / 2, rim))
        ceiling = hat.ray(centre + Vector((0, 0, 0.002)), Vector((0, 0, 1)))
        inside = (ceiling[0].z - rim) if ceiling and ceiling[0].z - rim > 0.03 else (hat.high.z - rim) * 0.75
        k = float(e["size"]) if e.get("size") else max(width * HAT_ROOM / inner_x, depth * HAT_ROOM / inner_y)
        thing.resize(k)
        # how far up the head its rim sits: its inside on the top of the head, or its rim on the brow if it's deeper than that
        high = (top - brow).dot(up) + HAIR_ROOM - inside * k
        seat = brow + forward * (middle - brow).dot(forward) + side * (middle - brow).dot(side) + up * max(high, 0.0)
        turn = _axes(up, -forward)
        origin = seat - turn @ (centre * k)
        holder = person.attach("head", origin, f"{e['prop']}.worn")
        holder.matrix_world = Matrix.Translation(origin) @ turn.to_matrix().to_4x4()
        root.parent = holder
        root.location, root.rotation_quaternion = (0, 0, 0), Quaternion()
        p.update(palm=origin, points=turn @ UP, fingers=turn @ Vector((0, 1, 0)), holder=who, worn=True)
        person.hide_hair_above(seat + up * 0.004, turn)
        bpy.context.view_layer.update()
        print(f"WORN {e['prop']} on {who}: head {width:.3f} x {depth:.3f}, made {k:.2f} times its size, rim {max(high, 0.0) * 100:.1f} cm above the brow, "
              f"inside {inside * k * 100:.1f} cm deep", flush=True)

    def _spin(self, e: dict) -> None:
        """Turning steadily about one axis of its own, through a spot on it or its middle, with no wander: `rate` turns a second,
        coming up to speed over `ease` seconds if it's said."""
        cid = e["prop"]
        p = self.props[cid]
        root, thing = p["root"], p["thing"]
        begin = self.frame(e["t"])
        end = min(self.total, self.frame(e["to"]) if "to" in e else self.total)
        here, turn = self._place(cid, begin)
        about = thing.spot(e["about"]) if e.get("about") else Vector()
        hinge = here + turn @ about
        axis = (turn @ OWN_AXES[e.get("axis", "z")]).normalized()
        rate = float(e.get("rate", 1.0)) * math.tau / self.fps
        ease = max(1, round(float(e.get("ease", 0.0)) * self.fps))
        angle = math.radians(float(e.get("start", 0.0)))
        track = p.setdefault("track", {})
        for f in range(begin, end + 1):
            tip = Quaternion(axis, angle)
            place, turned = hinge + tip @ (here - hinge), tip @ turn
            root.location, root.rotation_quaternion = place, turned
            root.keyframe_insert("location", frame=f)
            root.keyframe_insert("rotation_quaternion", frame=f)
            track[f] = (place.copy(), turned.copy())
            angle += rate * min(1.0, (f - begin + 1) / ease)
        look.ease(root, "LINEAR")

    def _slide(self, e: dict) -> None:
        """Straight along a line, level, keeping its turn, as something set down does. `from` is how far off where it rests it
        starts, and it's there until `t`; `by` is how far it goes from where it is."""
        cid = e["prop"]
        p = self.props[cid]
        root = p["root"]
        begin = self.frame(e["t"])
        count = max(1, round(float(e["over"]) * self.fps))
        rest, turn = self._place(cid, begin)
        start = rest + Vector(e["from"]) if "from" in e else rest
        if e.get("until"):                 # it goes until it touches: how far that is, is measured
            way = Vector(e["way"]).normalized()
            self.bl.frame_set(begin)
            root.location = rest
            bpy.context.view_layer.update()
            inside = e["until"] in self._inside_chain(cid)       # from inside something, it's the near wall ahead of it that it meets
            gap = self._solid_of(cid).reach_to(self._solid_of(e["until"]), way, back=1e-4 if inside else 1.0)
            if gap is None:
                raise Refused([f"{cid} slides towards {e['until']} and would miss it"])
            carried = root.matrix_world.to_quaternion() @ turn.inverted()     # however what it's in has turned since it went in, it goes the way that's said in the world
            finish = rest + carried.inverted() @ (way * max(0.0, gap - REST_GAP))
            self.bl.frame_set(1)
        else:
            finish = rest if "from" in e else rest + Vector(e["by"])
        kind = e.get("ease", "inout")
        track = p.setdefault("track", {})
        for f in range(1, self.total + 1):
            if f in track and f < begin:
                continue
            x = max(0.0, min(1.0, (f - begin) / count))
            x = x if kind == "linear" else x * x if kind == "in" else 1 - (1 - x) ** 2 if kind == "out" else x * x * (3 - 2 * x)
            here = start.lerp(finish, x)
            root.location, root.rotation_quaternion = here, turn
            root.keyframe_insert("location", frame=f)
            root.keyframe_insert("rotation_quaternion", frame=f)
            track[f] = (here.copy(), turn.copy())

    def _press(self, e: dict) -> None:
        """The front of something stopping against what it's hit, while the rest of it keeps coming: the part nearest what it hit gets squeezed most and spreads, the back comes on by as much as it's shortened, and the very front
        stays where it is. It springs part of the way back, and stays pressed by `stays` of it, as something still being pushed does."""
        p = self.props[e["prop"]]
        root = p["root"]
        begin = self.frame(e["t"])
        self.bl.frame_set(begin)
        bpy.context.view_layer.update()
        to_root = root.matrix_world.inverted()
        way = (to_root.to_3x3() @ Vector(e["way"])).normalized()
        if e.get("near"):              # a part that's been bent at rest is pressed as it was modelled, before it's bent
            for (_, near, reach), hook in p.get("hooks", {}).items():
                if hook.name in p.get("hook_rest", {}) and (p["thing"].spot(e["near"]) - p["thing"].spot(near)).length < reach:
                    way = p["hook_rest"][hook.name].inverted() @ way
        w = np.array(way)
        meshes = bounds.meshes_of(root)
        rows = []
        for obj in meshes:
            co = np.zeros(len(obj.data.vertices) * 3)
            obj.data.vertices.foreach_get("co", co)
            co = co.reshape(-1, 3)
            place = np.array(to_root @ obj.matrix_world)
            rows.append((obj, co, co @ place[:3, :3].T + place[:3, 3], place))
        here = np.vstack([row[2] for row in rows])
        part = None
        if e.get("near"):              # only what's near a spot, as a head that's gone soft crumples and the body behind it doesn't
            thing = p["thing"]
            centre = np.array(thing.spot(e["near"]) - (thing.spot("grip") if p.get("holder") and "grip" in thing.spots else Vector()))
            reach = float(e["radius"])
            part = lambda points: np.clip((reach - np.linalg.norm(points - centre, axis=1)) / (reach * 0.35), 0.0, 1.0)
        chosen = here if part is None else here[part(here) > 0.5]
        along = chosen @ w
        front, size = along.max(), float(along.max() - along.min())
        middle = chosen.mean(axis=0)
        amount = float(e["amount"])
        spread, firm = float(e.get("soft", PRESS_SOFT)), np.exp(-1 / float(e.get("soft", PRESS_SOFT)))
        blocks = []
        shell = self._solid_of(p["inside_of"]) if p.get("inside_of") else None
        world = root.matrix_world
        for obj, co, points, place in rows:
            behind = front - points @ w
            flat = amount * size * PRESS_FLAT    # the front goes flat on what's stopped it, as far back as this, and what's behind that comes on after it
            forward = np.minimum(behind, flat) + (amount * size - flat) * (1 - np.exp(-np.maximum(behind - flat, 0.0) / (spread * size))) / (1 - firm)
            flat = (points - middle) - np.outer((points - middle) @ w, w)
            moved = np.outer(forward, w) + flat * (amount * PRESS_SPREADS * np.exp(-behind / (0.3 * size)))[:, None]
            if part is not None:
                share = part(points)
                moved = moved * (share * share * (3 - 2 * share))[:, None]
            if shell is not None:          # what it's inside stops it, wherever it reaches that: it takes the shape of the wall, as a brain does in a skull
                moved = self._stopped_by(shell, world, points, moved)
            local = co + moved @ np.linalg.inv(place[:3, :3]).T
            if not obj.data.shape_keys:
                obj.shape_key_add(name="Basis", from_mix=False)
            block = obj.shape_key_add(name="pressed", from_mix=False)
            block.slider_min = -1.0
            block.data.foreach_set("co", local.reshape(-1))
            obj.data.update()
            blocks.append(block)
        rising = max(2, round(float(e.get("in", 0.12)) * self.fps))
        ringing = max(2, round(float(e.get("over", 0.8)) * self.fps))
        stays = float(e.get("stays", 0.4))
        for i in range(-1, rising + ringing + 1):
            if i < 0:
                value = 0.0
            elif i < rising:
                x = (i + 1) / rising
                value = 1 - (1 - x) ** 2
            else:
                u = (i - rising) / ringing
                value = stays + (1 - stays) * math.exp(-3.4 * u) * math.cos(u * math.tau * 1.6)
            for block in blocks:
                block.value = value
                block.keyframe_insert("value", frame=begin + i)
        p["pressed"] = True

    @staticmethod
    def _stopped_by(shell: bounds.Solid, world, points, moved) -> np.ndarray:
        """How far each point can go of how far it's going, with something in the way of some of them."""
        out = moved.copy()
        turn = world.to_3x3()
        for i in range(len(points)):
            far = float(np.linalg.norm(moved[i]))
            if far < 1e-5:
                continue
            way = (turn @ Vector(moved[i] / far)).normalized()
            hit = shell.tree.ray_cast(world @ Vector(points[i]), way, far + REST_GAP)
            if hit[0] is not None:
                out[i] = moved[i] * max(0.0, (hit[3] - REST_GAP)) / far
        return out

    def stage_holds(self) -> None:
        for e in self.events:
            if e["do"] == "wear":
                self._wear(e)
        for e in self.events:
            if e["do"] == "bite":
                self._bite(e)
        for e in self.events:
            if e["do"] == "hold":
                p = self.props[e["prop"]]
                radius, thing = self._handle_radius(p), p.get("thing")
                if thing:
                    thing.hold_by_grip()
                    reach = thing.spot("end") - thing.spot("grip") if "grip" in thing.spots and "end" in thing.spots else Vector()
                    if math.hypot(reach.x, reach.y) > 1e-4:     # about the handle, so that way's the way the fingers point
                        p["spin"] = Quaternion(UP, math.pi / 2 - math.atan2(reach.y, reach.x))
                p["palm"], p["points"], p["fingers"] = self._grip(e["who"], e["hand"], e["grip"])
                p["root"].location, p["root"].rotation_quaternion = p["palm"], self._turn_of(p, p["points"], p["fingers"])
                p["holder"], p["hand"] = e["who"], e["hand"]
                p["wrist"] = self.people[e["who"]].hold(e["hand"], p["root"], spin=p.get("spin"), radius=radius)

    def _bite(self, e: dict) -> None:
        person, p = self.people[e["who"]], self.props[e["prop"]]
        forward, right = self._directions(e["who"])
        bite = person.mouth() - UP * 0.027
        holder = person.attach("head", bite, f"{e['prop']}.bite")
        holder.matrix_world = Matrix.Translation(bite) @ Quaternion(UP, math.radians(self._facing(e["who"]))).to_matrix().to_4x4()
        pivot = bpy.data.objects.new(f"{e['prop']}.pivot", None)
        self.bl.collection.objects.link(pivot)
        pivot.parent = holder
        root = p["root"]
        root.parent = pivot
        root.rotation_mode = "XYZ"
        root.location = (0, 0, 0)
        yaw = math.radians(e.get("yaw", 14))
        root.rotation_euler = (0, math.radians(90), yaw)
        p.update(bitten=True, bite=bite, along=(-right * math.cos(yaw) + (-forward) * math.sin(yaw)).normalized(), pivot=pivot,
                 holder=e["who"])
        face = dict(BITING)
        person.face(1, strict=False, **face)
        p["biting"] = face
        self.people[e["who"]].biters = True

    # --- what happens ----------------------------------------------------------------------------------------------

    def _surface(self, prop: str, along: float) -> Vector:
        """Where a blow lands on a prop: the top of it, `along` meters out, by casting a ray down at its meshes."""
        point = self._along(prop, along)
        best = None
        bpy.context.view_layer.update()
        graph = bpy.context.evaluated_depsgraph_get()
        for obj in self.props[prop]["root"].children_recursive:
            if obj.type != "MESH":
                continue
            inverse = obj.matrix_world.inverted()
            origin = inverse @ (point + UP * 0.5)
            direction = (inverse.to_3x3() @ -UP).normalized()
            hit, where, _, _ = obj.evaluated_get(graph).ray_cast(origin, direction)
            if hit:
                world = obj.matrix_world @ where
                if best is None or world.z > best.z:
                    best = world
        return best if best is not None else point

    def _working_end(self, p: dict, reach: float) -> Vector:
        """Where a held thing's working end is from the hand, in its own axes."""
        thing = p.get("thing")
        if thing and "grip" in thing.spots and "end" in thing.spots:
            return thing.spot("end") - thing.spot("grip")
        return Vector((0, 0, reach))

    def _side_facing(self, prop: str, along: float, toward: Vector) -> Vector:
        """Where a blow from `toward` lands on a thing, `along` meters up it: the nearest of its surface, by casting a ray."""
        point = self._along(prop, along)
        origin = Vector((toward.x, toward.y, point.z))
        direction = (point - origin).normalized()
        best, nearest = None, float("inf")
        bpy.context.view_layer.update()
        graph = bpy.context.evaluated_depsgraph_get()
        for obj in self.props[prop]["root"].children_recursive:
            if obj.type != "MESH":
                continue
            inverse = obj.matrix_world.inverted()
            hit, where, _, _ = obj.evaluated_get(graph).ray_cast(inverse @ origin, (inverse.to_3x3() @ direction).normalized())
            if hit:
                world = obj.matrix_world @ where
                gap = (world - origin).length
                if gap < nearest:
                    best, nearest = world, gap
        return best if best is not None else point

    def _strike(self, e: dict) -> None:
        """The arc, the bounce, and what it does to whoever has the target."""
        who, p = e["who"], self.props[e["prop"]]
        hit = self.frame(e["t"])
        over = max(1, round(e.get("over", 0.85) * self.fps))
        along = float(e.get("along", 0))
        reach, edge = self._size_of(p)
        struck_cid, _, spot = e["target"].partition(":")
        on_person = struck_cid not in self.props
        side, person = p.get("hand"), self.people[who]
        self.bl.frame_set(hit)
        bpy.context.view_layer.update()
        shoulder = person.rig.matrix_world @ person.bone(f"upper_arm.{side}").head
        swing = not on_person and bool(self.props[struck_cid].get("thing"))     # a tree, a wall: it lands on the side facing them
        forward, right = self._directions(who)
        outward = right if side == "R" else -right
        away = -forward
        if swing:
            touch = self.aim(e["target"], hit) if spot else self._side_facing(struck_cid, along, shoulder)
            away = Vector((shoulder.x - touch.x, shoulder.y - touch.y, 0)).normalized()
            # upright at the moment it lands, the way a hammer meets a wall: the fist behind it and its face flat on the surface
            points, fingers = (UP - away * 0.15).normalized(), -away
            palm_end = touch - self._turn_of(p, points, fingers) @ self._working_end(p, reach)
        else:
            fingers = Vector((0, 0, -1))
            touch = (self.aim(e["target"]) if on_person else self._surface(e["target"], along)) + UP * edge
            points = (touch - shoulder).normalized()
            palm_end = touch - points * reach
        wrist = palm_end + self._turn_of(p, points, fingers) @ p.get("wrist", Vector())
        arm = person.bone(f"upper_arm.{side}").bone.length + person.bone(f"forearm.{side}").bone.length
        if (wrist - shoulder).length > arm + HAND_SLIPS:
            raise ValueError(f"strike: {who} stands too far from {e['target']} to reach it: the wrist would have to be "
                             f"{(wrist - shoulder).length:.2f} m from the shoulder, and their arm's {arm:.2f} m. Stand closer")
        if swing:                    # drawn back beside the head, the arm bent, as far as a blow's drawn back
            high_palm = shoulder + UP * 0.2 + forward * 0.03 + outward * 0.2
            high = (UP + away * 1.0 + outward * 0.2).normalized()
        else:
            high_palm = palm_end.lerp(shoulder + UP * 0.34, 0.65)
            high = (points + UP * 1.8).normalized()
        drive = hit - over
        wind = drive - round(WIND_UP * self.fps)
        path = p.setdefault("path", [])
        if wind >= 1:
            path.append({"from": wind, "to": drive, "palm1": high_palm, "points1": high, "fingers": fingers})
        else:                        # no time to draw back: they're already there
            p["start"] = (high_palm, high, fingers)
            wind = drive
        give, slow = float(e.get("gives", 0.0)), float(e.get("slow", 1.0))
        path.append({"from": drive, "to": hit, "palm1": palm_end, "points1": points, "fingers": fingers, "blow": True, "away": away, "give": give, "slow": slow})
        eyes = self._on_person(who, "eyes")
        to_it = touch - eyes
        flat = Vector((to_it.x, to_it.y, 0))
        head = person.bone("head")       # however far the way they're standing already has their head turned or bowed
        place = person.rig.matrix_world
        facing = (place @ head.matrix @ head.bone.matrix_local.inverted() @ place.inverted()).to_quaternion() @ forward
        facing_flat = Vector((facing.x, facing.y, 0))
        look_turn = math.degrees(math.atan2(facing_flat.cross(flat).z, facing_flat.dot(flat)))
        look_up = math.degrees(math.atan2(to_it.z, max(flat.length, 1e-6))) - math.degrees(math.atan2(facing.z, max(facing_flat.length, 1e-6)))
        self.swings.setdefault(who, []).append((wind, drive, hit, 1.0 if side == "L" else -1.0, right, look_turn, look_up))
        if give:
            self._gives(p, hit, give, float(e.get("radius", 0.04)), slow)
        if on_person:
            struck = e["target"].partition(":")[0]
            self.knocks[struck].append((hit, UP.cross(points).normalized(), float(e.get("size", 10.0))))
            self._reel(struck, hit, {})
        target = self.props.get(e["target"]) or {}
        holder = target.get("holder")
        if holder:
            d = target["along"] if target.get("bitten") else target["points"]
            axis = d.cross(-UP).normalized()
            size = min(14.0, 26.0 * along + 4.0)
            if target.get("pivot"):
                pivot = target["pivot"]
                for f in range(1, self.total + 1, 2):
                    pivot.rotation_euler = (0, 0, 0)
                    pivot.rotation_quaternion = (1, 0, 0, 0)
                    pivot.rotation_mode = "QUATERNION"
                    local = pivot.parent.matrix_world.to_quaternion().inverted() @ axis
                    pivot.rotation_quaternion = Quaternion(local, math.radians(ring_down(f, hit, size * 0.6)))
                    pivot.keyframe_insert("rotation_quaternion", frame=f)
            self.knocks[holder].append((hit, axis, size))
            self._reel(holder, hit, dict(target.get("biting") or {}))
        if e.get("sparks", True):
            self._sparks(touch + UP * 0.004, hit, kind=e["sparks"] if isinstance(e.get("sparks"), str) else "sparks")
        if e.get("rings", True):    # once the shots can be worked out, in _act
            self.waiting_rings.append((touch, hit, e.get("ring_color", "red"), e["t"]))

    def _gives(self, p: dict, hit: int, depth: float, radius: float, slow: float = 1.0) -> None:
        """A soft tool giving in where it lands, as a sponge does round a nail's head, and springing back, wobbling, when it lets go, at this share of the speed it really would."""
        thing = p["thing"]
        at = thing.spot("end") - thing.spot("grip")
        blocks = self._dent(p, at, depth, radius)
        for f in range(max(1, hit - 1), min(self.total, hit + round((GIVE_IN + GIVE_STAYS + GIVE_BACK + 26) / slow)) + 1):
            since = (f - hit) * slow
            after = since - GIVE_IN - GIVE_STAYS - GIVE_BACK
            value = _pressed(since) if after <= 0 else -0.16 * math.exp(-after / 8) * math.sin(after / 2.4)
            for block in blocks:
                block.value = value
                block.keyframe_insert("value", frame=f)

    def _dent(self, p: dict, at: Vector, depth: float, radius: float) -> list:
        """The shape of something pressed in `depth` meters at a place on its surface, in its own axes: it goes in most in the middle, fading out to nothing at `radius` and less the further
        in from the surface, and bulges a little round the rim, as what was there goes somewhere. Returns the shape keys that say how far it's gone in."""
        root = p["root"]
        bpy.context.view_layer.update()
        to_root = root.matrix_world.inverted()
        meshes = bounds.meshes_of(root)
        def part_centre(obj):
            corners = [to_root @ obj.matrix_world @ Vector(c) for c in obj.bound_box]
            return sum(corners, Vector()) / 8
        def off(obj):
            corners = [to_root @ obj.matrix_world @ Vector(c) for c in obj.bound_box]
            return sum(max(min(c[i] for c in corners) - at[i], at[i] - max(c[i] for c in corners), 0.0) ** 2 for i in range(3))
        near = min(meshes, key=off)
        way = (part_centre(near) - at).normalized()
        blocks = []
        for obj in meshes:
            if off(obj) > (radius * 2) ** 2:
                continue
            _made_fine(obj, radius / SOFT_EDGE)
            place = to_root @ obj.matrix_world
            back = place.inverted().to_3x3()
            co = np.zeros(len(obj.data.vertices) * 3)
            obj.data.vertices.foreach_get("co", co)
            co = co.reshape(-1, 3)
            m = np.array(place)
            here = co @ m[:3, :3].T + m[:3, 3]
            d = here - np.array(at)
            w = np.array(way)
            inward = d @ w
            flat = d - np.outer(inward, w)
            r = np.linalg.norm(flat, axis=1)
            u = np.clip(r / radius, 0.0, 1.0)
            fades = np.exp(-np.maximum(inward, 0.0) / (radius * 1.6))
            pushed = (1 - u * u) ** 2 * fades
            rim = np.exp(-((r - radius * 1.25) / (radius * 0.55)) ** 2) * np.exp(-(np.maximum(inward, 0.0) / (radius * 1.2)) ** 2)
            outward = flat / np.maximum(r, 1e-6)[:, None]
            moved = np.outer(pushed * depth, w) + outward * (rim * depth * 0.32)[:, None] - np.outer(rim * depth * 0.14, w)
            m_back = np.array(back)
            local = co + moved @ m_back.T
            if not obj.data.shape_keys:
                obj.shape_key_add(name="Basis", from_mix=False)
            block = obj.shape_key_add(name="dent", from_mix=False)
            block.slider_min = -1.0
            block.data.foreach_set("co", local.reshape(-1))
            obj.data.update()
            blocks.append(block)
        return blocks

    def _reel(self, who: str, hit: int, base: dict) -> None:
        """Eyes shut and brow down from a blow, then easing. `base` is what the face was doing, such as biting."""
        person = self.people[who]
        clench = {**base, "jawOpen": base["jawOpen"] - 0.1} if base else {}
        rest = {name: 0.0 for name in BRACED}
        person.face(hit, strict=False, **base, **rest)
        person.face(hit + 5, strict=False, **clench, **BRACED)
        person.face(hit + 62, strict=False, **clench, **BRACED)
        person.face(hit + 78, strict=False, **base, **rest)

    def _fly(self, e: dict) -> None:
        """A thrown thing: gravity's arc from one place to another, tumbling, and if it hits someone, they reel and it
        bounces off and falls to the floor, bouncing until it stops. Before it's thrown it's nowhere to be seen."""
        p = self.props[e["prop"]]
        root = p["root"]
        start, end = self._point(e["from"]), self._point(e["to"])
        begin, over = self.frame(e["t"]), max(1, round(e["over"] * self.fps))
        arrive = begin + over
        slow = float(e.get("slow", 1.0))
        flight = e["over"] * slow                    # the real seconds it's in the air
        velocity = (end - start) / flight + UP * (0.5 * 9.81 * flight)
        turn = Vector((0.7, 0.2, 0.5)).normalized()
        root.scale = (0, 0, 0)
        root.keyframe_insert("scale", frame=max(1, begin - 1))
        root.scale = (1, 1, 1)
        root.keyframe_insert("scale", frame=begin)
        radius = self._size_of(p)[1]
        here = end.copy()
        if e.get("hits"):
            travel = (end - start).normalized()
            self.knocks[e["hits"]].append((arrive, UP.cross(travel).normalized(), float(e.get("size", 10.0))))
            self._reel(e["hits"], arrive, {})
        away = (start - end).normalized() * 1.6 + UP * 1.5
        step = slow / self.fps
        for f in range(begin, self.total + 1):
            if f <= arrive:
                t = (f - begin) * step
                here = start + velocity * t + Vector((0, 0, -9.81)) * (0.5 * t * t)
            else:
                away.z -= 9.81 * step
                here = here + away * step
                if here.z < radius:          # the floor: it loses half its speed each bounce, and drags
                    here.z = radius
                    away = Vector((away.x * 0.7, away.y * 0.7, -away.z * 0.5))
            root.location = here
            root.rotation_quaternion = Quaternion(turn, 9.0 * (f - begin) * step)
            root.keyframe_insert("location", frame=f)
            root.keyframe_insert("rotation_quaternion", frame=f)
            p.setdefault("track", {})[f] = (here.copy(), root.rotation_quaternion.copy())

    def _glide(self, s: dict, cam, target, begin: int, end: int, on: Vector, lens: float) -> None:
        """A shot that travels: the camera goes from where the shot starts to its `to`, swinging round rather than cutting across, and
        easing in and out, with the aim moving with it. Keyed frame by frame, so it stays on what it's following."""
        to = s["to"]
        ahead = round(float(to.get("ahead", 0)) * self.fps)
        last = max(begin + 1, end - 1)
        start_way, start_turn = self._way_to_lens(s, begin)
        end_shot = {**s, "on": to.get("on", s["on"]), "angle": to.get("angle", s.get("angle", (0, 0)))}
        _, end_turn = self._way_to_lens(end_shot, last)
        swing = math.atan2(math.sin(end_turn - start_turn), math.cos(end_turn - start_turn))
        up0, up1 = (math.radians(a) for a in (s.get("angle", (0, 0))[1], end_shot["angle"][1]))
        near0, near1 = float(s["frame"]) * lens / 24, float(to.get("frame", s["frame"])) * lens / 24
        kind = to.get("ease", "inout")
        follows = s.get("follow")
        leaving = self._followed(s["on"], begin, end) if follows else None
        going = self._followed(end_shot["on"], begin + ahead, end + ahead) if follows else None
        fixed = None if follows else self.aim(end_shot["on"], last + ahead)
        for f in range(begin, end + 1):
            u = min(1.0, (f - begin) / max(1, last - begin))
            k = {"linear": u, "in": u * u, "out": 1 - (1 - u) ** 2}.get(kind, u * u * (3 - 2 * u))
            frm = leaving[f] if follows else on
            there = going[f + ahead] if follows else fixed
            aim_now = frm.lerp(there, k)
            turn, up = start_turn + swing * k, up0 + (up1 - up0) * k
            way = Vector((math.sin(turn) * math.cos(up), -math.cos(turn) * math.cos(up), math.sin(up)))
            look.key(target, f, location=aim_now)
            look.key(cam, f, location=aim_now + way * (near0 * (near1 / near0) ** k))
            if "shift" in to:
                self._shift_lens(cam, [a + (b - a) * k for a, b in zip(s.get("shift", (0, 0)), to["shift"])], f)
        look.ease(target, "LINEAR")
        cam.data.clip_start = max(0.005, min(near0, near1) / 100)

    def _shift_lens(self, cam, shift, frame: int | None = None) -> None:
        """What a shot's on, placed away from the middle of the picture, by these shares of its width and height, sliding the lens rather
        than turning the camera, so nothing else about the shot changes. A portrait picture's shift is counted in its height."""
        cam.data.shift_x, cam.data.shift_y = -shift[0] * PICTURE_SHAPE, -shift[1]
        if frame is not None:
            cam.data.keyframe_insert("shift_x", frame=frame)
            cam.data.keyframe_insert("shift_y", frame=frame)

    def _way_to_lens(self, s: dict, begin: int) -> tuple[Vector, float]:
        """The direction from a shot's subject to its camera, and the degrees of that around the subject."""
        who = s["on"].partition(":")[0]
        when = begin + round(float(s.get("ahead", 0)) * self.fps)
        if s.get("square"):            # counted from the set, so its straight lines stay level whichever way a thing faces
            base = 0.0
        elif who in self.people:
            base = math.radians(self._facing(who))
        else:
            base = math.radians(self._heading(who, when)) if self.props[who].get("thing") else 0.0
        around, up = (math.radians(v) for v in s.get("angle", (0, 0)))
        turn = base + around
        return Vector((math.sin(turn) * math.cos(up), -math.cos(turn) * math.cos(up), math.sin(up))), turn

    def _facing_shot(self, t: float) -> Vector:
        """The way to the lens of whichever shot is on at a time: what spreads flat, such as rings, faces it."""
        shots = self.spec["shots"]
        s = [x for x in shots if x["t"] <= t + 1e-6][-1]
        return self._way_to_lens(s, self.frame(s["t"]))[0]

    def _go(self, e: dict) -> None:
        """Under its own power, nose first along a smooth line, banking as far as a turn at that speed needs. It lands, or
        it hits someone and falls, or it flies on."""
        cid = e["prop"]
        p = self.props[cid]
        root, thing = p["root"], p.get("thing")
        begin = self.frame(e["t"])
        arrive = min(self.total, begin + max(1, round(e["over"] * self.fps)))
        start, _ = self._place(cid, begin)
        lands, hits = e.get("lands", False), e.get("hits")
        half = thing.size.z / 2 if thing else 0.0
        self.bl.frame_set(arrive)             # someone it's aiming at is where they'll be when it gets there
        bpy.context.view_layer.update()
        stops = [Vector(stop) if isinstance(stop, list) else self.aim(stop, arrive) for stop in e["through"]]
        if lands:
            stops[-1] = stops[-1] + UP * half
        ride = self._ride_on(stops[-1], e["through"][-1], cid) if lands and isinstance(e["through"][-1], str) else None
        self.bl.frame_set(1)
        line = _spline([start, *stops])
        moving = begin - 1 in p.get("track", {}) and not p.get("landed")
        count = arrive - begin + 1
        places = [_along_line(line, _pace(i / max(1, count - 1), 0.0 if moving else 0.2, 0.35 if lands else 0.0))
                  for i in range(count)]
        turns = self._nose_first(places, lands, e, cid)
        track = p.setdefault("track", {})
        for i, (here, turn) in enumerate(zip(places, turns)):
            root.location, root.rotation_quaternion = here, turn
            root.keyframe_insert("location", frame=begin + i)
            root.keyframe_insert("rotation_quaternion", frame=begin + i)
            track[begin + i] = (here.copy(), turn.copy())
        p["landed"] = lands
        after = (places[-1] - places[-2]) * self.fps if len(places) > 1 else Vector()
        if hits:
            self.knocks[hits].append((arrive, UP.cross(after.normalized()).normalized(), float(e.get("size", 10.0))))
            self._reel(hits, arrive, {})
            self._falls(cid, places[-1], after * -0.25 + UP * 1.2, arrive, float(e.get("slow", 1.0)))
        elif not lands:
            for f in range(arrive + 1, self.total + 1):
                here = places[-1] + after * ((f - arrive) / self.fps)
                root.location = here
                root.keyframe_insert("location", frame=f)
                track[f] = (here.copy(), turns[-1].copy())
        if ride is not None:
            constraint = root.constraints.new("COPY_LOCATION")
            constraint.target = ride
            for f, value in ((arrive - 1, 0.0), (arrive, 1.0)):
                constraint.influence = value
                constraint.keyframe_insert("influence", frame=f)
            for curve in look._fcurves(root.animation_data.action):
                if "influence" in curve.data_path:
                    for point in curve.keyframe_points:
                        point.interpolation = "CONSTANT"
        if thing:
            speed = float(e.get("speed", 1.0))
            if "move" in e:
                thing.play(begin, arrive if lands or hits else self.total + 1, e["move"], speed)
            if "then" in e and arrive < self.total:
                thing.play(arrive, self.total + 1, e["then"], speed)

    def _bend_hook(self, cid: str, about: str, near: str, radius: float):
        """What part of a thing turns about: all of it near a spot moves, and it fades out to nothing `radius` meters away, so a scan with no
        bones bends there, as a bird's neck does."""
        p = self.props[cid]
        hooks = p.setdefault("hooks", {})
        key = (about, near, radius)
        if key in hooks:
            return hooks[key]
        root, thing = p["root"], p["thing"]
        hook = bpy.data.objects.new(f"{cid}.bend{len(hooks)}", None)
        self.bl.collection.objects.link(hook)
        hook.parent = root
        hook.location = thing.spot(about)
        hook.rotation_mode = "QUATERNION"
        bpy.context.view_layer.update()
        centre = np.array(root.matrix_world @ thing.spot(near))
        firm = radius * BEND_FIRM
        for obj in bounds.meshes_of(root):
            place = np.array(obj.matrix_world)
            co = np.zeros(len(obj.data.vertices) * 3)
            obj.data.vertices.foreach_get("co", co)
            world = co.reshape(-1, 3) @ place[:3, :3].T + place[:3, 3]
            share = np.clip((radius - np.linalg.norm(world - centre, axis=1)) / max(radius - firm, 1e-6), 0.0, 1.0)
            weights = share * share * (3 - 2 * share)
            group = obj.vertex_groups.new(name=hook.name)
            for i in np.nonzero(weights)[0]:
                group.add([int(i)], float(weights[i]), "REPLACE")
            bend = obj.modifiers.new(hook.name, "HOOK")
            bend.object = hook
            bend.vertex_group = group.name
            bend.falloff_type = "NONE"
            bend.matrix_inverse = hook.matrix_world.inverted() @ obj.matrix_world
        hooks[key] = hook
        for other, c in self.spec["cast"].items():        # what's inside the part that bends goes with it
            if c.get("inside") == cid and (self.props[other]["root"].matrix_world.translation - Vector(tuple(centre))).length < firm:
                self._carry(other, hook)
        return hook

    def _squash(self, e: dict) -> None:
        """Pressed flat along one of its own axes and springing back, wider the way it isn't pressed, keeping its volume, with one of its spots staying
        where it is: a hit you can feel. It starts at `amount` and rings out over `over` seconds."""
        p = self.props[e["prop"]]
        thing = p["thing"]
        if "squasher" not in p:
            p["squasher"] = bpy.data.objects.new(f"{p['root'].name}.squash", None)
            self.bl.collection.objects.link(p["squasher"])
            p["squasher"].parent = p["root"]
            thing.holder.parent = p["squasher"]
        squasher = p["squasher"]
        grip = thing.spot("grip") if p.get("holder") and "grip" in thing.spots else Vector()
        spot = (thing.spot(e["about"]) - grip) if e.get("about") else Vector()
        if self.spec["cast"][e["prop"]].get("on"):       # it spreads sideways and up, and doesn't go down through what it's on
            spot.z = -thing.size.z / 2
        axis = "xyz".index(e.get("axis", "y"))
        begin, count = self.frame(e["t"]), max(2, round(float(e.get("over", 0.6)) * self.fps))
        amount = float(e["amount"])
        for i in range(-1, count + 1):
            if i < 0 or i == count:
                press = 0.0
            else:
                u = i / count
                press = amount * math.exp(-3.4 * u) * math.cos(u * math.tau * 1.6) * min(1.0, (i + 1) / 2)
            scale = [1 + press / 2 if e.get("spreads", True) else 1.0] * 3
            scale[axis] = 1 - press
            f = begin + i
            squasher.scale = scale
            squasher.location = Vector(spot[k] * (1 - scale[k]) for k in range(3))
            squasher.keyframe_insert("scale", frame=f)
            squasher.keyframe_insert("location", frame=f)

    def _rock(self, e: dict) -> None:
        """A whole thing drawing back and snapping to where it stood, about a place on it: speeding up into each snap, as a
        peck or a hammer does. It ends where it started. With `part`, only what's near a spot moves, and the rest stays put."""
        cid = e["prop"]
        p = self.props[cid]
        root, thing = p["root"], p["thing"]
        begin = self.frame(e["t"])
        count = max(1, round(e["over"] * self.fps))
        times, back = int(e.get("times", 1)), math.radians(float(e.get("degrees", 20)))
        if e.get("part"):
            hook = self._bend_hook(cid, e["about"], e["part"]["near"], float(e["part"]["radius"]))
            axis = self._rock_axis(e, thing)
            for i in range(count + 1):
                f = begin + i
                if f > self.total:
                    break
                share = _rock_share(i, count, times, e)
                hook.rotation_quaternion = p.get("hook_rest", {}).get(hook.name, Quaternion()) @ Quaternion(axis, -back * share)
                hook.keyframe_insert("rotation_quaternion", frame=f)
            return
        here, turn = self._place(cid, begin)
        pivot = thing.spot(e["about"]) if e.get("about") else Vector((0, 0, -thing.size.z / 2))
        hinge = here + turn @ pivot
        axis = turn @ self._rock_axis(e, thing)
        track = p.setdefault("track", {})
        for i in range(count + 1):
            f = begin + i
            if f > self.total:
                break
            tip = Quaternion(axis, -back * _rock_share(i, count, times, e))
            place, turned = hinge + tip @ (here - hinge), tip @ turn
            root.location, root.rotation_quaternion = place, turned
            root.keyframe_insert("location", frame=f)
            root.keyframe_insert("rotation_quaternion", frame=f)
            track[f] = (place.copy(), turned.copy())

    @staticmethod
    def _rock_axis(e: dict, thing) -> Vector:
        """What something rocks about, in its own axes: one of them, or, with `toward`, whatever draws that spot back up and away along its own line, so a peck goes the way the beak points, however the head's turned."""
        if e.get("toward"):
            line = thing.spot(e["toward"]) - (thing.spot(e["about"]) if e.get("about") else Vector())
            across = Vector((0, 0, 1)).cross(line)
            if across.length > 1e-6:     # straight up its own z, there's no way that's back
                return across.normalized()
        return ROCK_AXES[e.get("axis", "pitch")]

    def _ride_on(self, place: Vector, aim: str, cid: str):
        """What a thing that's landed on a person follows from then on. Nothing, if it landed on anything else."""
        who, _, part = aim.partition(":")
        if who not in self.people or part not in RIDES:
            return None
        return self.people[who].attach(RIDES[part], place, f"{cid}.ride")

    def _nose_first(self, places: list[Vector], lands: bool, e: dict, cid: str) -> list[Quaternion]:
        """Its turn at each frame: facing along the line, as steep as it climbs or dives within reason, banked by physics:
        tan(bank) = speed x turn rate / g. Landing, the nose comes up to brake and it ends level, facing `ends_facing`."""
        count = len(places)
        heads, climbs = [], []
        for i in range(count):
            d = places[min(count - 1, i + 2)] - places[max(0, i - 2)]
            flat = math.hypot(d.x, d.y)
            heads.append(math.atan2(d.x, -d.y) if flat > 1e-5 else (heads[-1] if heads else math.radians(self._heading(cid, 1))))
            climbs.append(max(-CLIMB_LIMIT, min(CLIMB_LIMIT, math.atan2(d.z, flat))) if flat > 1e-5 else 0.0)
        for i in range(1, count):            # no jump across the half turn
            heads[i] = heads[i - 1] + (heads[i] - heads[i - 1] + math.pi) % (2 * math.pi) - math.pi
        ends = e.get("ends_facing")
        if ends is not None:
            ends = math.radians(ends) if isinstance(ends, (int, float)) else self._toward(ends, places[-1])
        turns = []
        for i in range(count):
            a, b = max(0, i - 3), min(count - 1, i + 3)
            rate = (heads[b] - heads[a]) * self.fps / max(1, b - a)
            speed = (places[min(count - 1, i + 1)] - places[max(0, i - 1)]).length * self.fps / 2
            bank = max(-LEAN_LIMIT, min(LEAN_LIMIT, math.atan(speed * rate / 9.81)))
            head, climb = heads[i], climbs[i]
            if lands and i >= count * 0.7:
                x = min(1.0, (i - count * 0.7) / max(1.0, count * 0.3 - 1))     # reaching 1 on the last frame: it ends level
                climb = climb * (1 - x) + FLARE * math.sin(math.pi * x)
                bank *= 1 - x
                if ends is not None:
                    head += ((ends - head + math.pi) % (2 * math.pi) - math.pi) * x
            forward = Vector((math.sin(head) * math.cos(climb), -math.cos(head) * math.cos(climb), math.sin(climb)))
            up = Quaternion(forward, -bank) @ (UP - forward * UP.dot(forward)).normalized()
            turns.append(_axes(up, -forward))
        return turns

    def _toward(self, other: str, here: Vector) -> float:
        there = self.props[other]["palm"] if other in self.props else self.spec["cast"][other].get("at", (0, 0))
        return math.atan2(there[0] - here.x, -(there[1] - here.y))

    def _falls(self, cid: str, here: Vector, away: Vector, start: int, slow: float = 1.0) -> None:
        """Dropping under gravity from a hit, tumbling, bouncing on the floor until it stops."""
        p = self.props[cid]
        root = p["root"]
        radius = self._size_of(p)[1]
        step = slow / self.fps
        spin = Vector((0.5, 0.8, 0.2)).normalized()
        _, turn = self._place(cid, start)
        here = here.copy()
        for f in range(start + 1, self.total + 1):
            away.z -= 9.81 * step
            here = here + away * step
            if here.z < radius:
                here.z = radius
                away = Vector((away.x * 0.6, away.y * 0.6, -away.z * 0.4))
            tumble = Quaternion(spin, 5.0 * (f - start) * step) @ turn
            root.location, root.rotation_quaternion = here, tumble
            root.keyframe_insert("location", frame=f)
            root.keyframe_insert("rotation_quaternion", frame=f)
            p["track"][f] = (here.copy(), tumble.copy())

    def _sparks(self, at: Vector, frame: int, count: int = 26, kind: str = "sparks", slow: float = SLOW, away=None) -> None:
        """Bright chips thrown from a hit, or chips of what was hit, each falling under gravity on its own arc, at this share of real speed: slow motion, by default."""
        rng = random.Random(frame)
        wood = kind == "chips"
        for i in range(count):
            chip = _splinter(f"Spark{frame}.{i}", rng, at) if wood else shapes.box(f"Spark{frame}.{i}", (0.003, 0.003, rng.uniform(0.01, 0.03)), "spark", at=at)
            velocity = Vector((rng.uniform(-1, 1), rng.uniform(-1, 0.1), rng.uniform(0.15, 1.1))).normalized() * rng.uniform(0.8, 2.6)
            if away:                  # they fly off the surface they came from, whichever way that faces
                velocity = Vector((0, -1, 0)).rotation_difference(Vector(away).normalized()) @ velocity
            chip.rotation_mode = "QUATERNION"
            chip.rotation_quaternion = UP.rotation_difference(velocity)
            chip.scale = (0, 0, 0)
            chip.keyframe_insert("scale", frame=frame - 1)
            chip.keyframe_insert("location", frame=frame - 1)
            life = rng.randint(45, 70)
            for f in range(frame, frame + life + 1, 2):
                t = (f - frame) / 30.0 * slow
                chip.location = at + velocity * t + Vector((0, 0, -9.81)) * (0.5 * t * t)
                s = max(0.0, min(1.0, (1.0 - (f - frame) / life) / 0.2))      # by the time they go, they've left the picture
                chip.scale = (s, s, s)
                chip.keyframe_insert("location", frame=f)
                chip.keyframe_insert("scale", frame=f)

    def _glow(self, e: dict) -> None:
        person = self.people[e["who"]]
        place = self._on_person(e["who"], e["on"])
        socket = person.glow(place, float(e.get("radius", 0.078)), COLORS[e["color"]])
        begin, end = self.frame(e["t"]), self.frame(e["to"])
        strength = float(e.get("strength", 1.0))
        for f, value in ((max(1, begin - 1), 0.0), (begin + 18, 0.75 * strength), (end, strength)):
            socket.default_value = value
            socket.keyframe_insert("default_value", frame=f)

    def _lit(self, e: dict) -> None:
        """A thing's own surface lights up: all of it, or a patch of it around a spot. It can't leave the thing's edges."""
        cid, _, part = e["on"].partition(":")
        p = self.props[cid]
        thing = p.get("thing")
        begin = self.frame(e["t"])
        end = self.frame(e["to"]) if "to" in e else self.total
        meshes = bounds.meshes_of(p["root"])
        if e.get("only"):
            meshes = [obj for obj in meshes if any(obj.name == name or obj.name.startswith(f"{name}.") for name in e["only"])]
        centre = None
        if part and thing and e.get("radius"):
            centre = bpy.data.objects.new(f"{cid}.glow{begin}", None)
            self.bl.collection.objects.link(centre)
            centre.parent = p["root"]
            centre.location = thing.spot(part)
        glow.surface(meshes, e["color"], begin, end, round(float(e.get("fade", 0.15)) * self.fps), self.total,
                     strength=float(e.get("strength", 1.0)), cover=float(e.get("cover", 0.92)), centre=centre,
                     radius=e.get("radius"), edge=float(e.get("edge", 0.55)), rim=float(e.get("rim", 0.0 if e.get("radius") else 0.45)), soft=float(e.get("soft", 0.75)))

    def _tint(self, e: dict) -> None:
        p = self.props[e["prop"]]
        end = self.frame(e["to"]) if "to" in e else self.total
        glow.tint(bounds.meshes_of(p["root"]), e["color"], self.frame(e["t"]), end, float(e.get("amount", 1.0)))

    def _ghost(self, e: dict) -> None:
        begin, end = self.frame(e["t"]), self.frame(e["to"]) if "to" in e else self.total
        fade = round(float(e.get("fade", 0.15)) * self.fps)
        if e.get("who"):                  # someone's head: their skin goes to glass there, and their hair, eyes and teeth aren't there for as long as it does
            person = self.people[e["who"]]
            bone = person.bone("head")
            middle = person.head_middle()
            radius = float(e.get("radius", 0.17))
            glow.mark_part([person.body], tuple(middle), radius, points=person.rest_points())
            bpy.context.view_layer.update()
            centre = person.attach("head", person.rig.matrix_world @ bone.matrix @ bone.bone.matrix_local.inverted() @ middle, f"{person.rig.name}.xray")
            skin = person.body.data.materials[0]
            glow.ghost_materials([skin], e.get("color", "ice"), begin, end, fade, self.total, float(e.get("edge", 2.2)), float(e.get("strength", 1.4)), window=(centre, radius))
            others = [m for m in person.body.data.materials if m is not None and m != skin]
            for obj in (person.eyes, person.upper_teeth, person.lower_teeth):
                others += [m for m in obj.data.materials if m is not None]
            glow.fade_out(others, begin, end, fade, self.total)
            return
        p = self.props[e["prop"]]
        meshes = bounds.meshes_of(p["root"])
        window = None
        if e.get("near"):
            bpy.context.view_layer.update()
            at = p["root"].matrix_world @ p["thing"].spot(e["near"])
            glow.mark_part(meshes, tuple(at), float(e["radius"]))       # marked on the mesh as it was modelled, before any part of it bent
            glow.smooth_part(meshes, SCAN_SMOOTHS)
            centre = bpy.data.objects.new(f"{p['root'].name}.xray", None)
            self.bl.collection.objects.link(centre)
            hook = next((h for (_, near, radius), h in p.get("hooks", {}).items() if (at - p["root"].matrix_world @ p["thing"].spot(near)).length < radius * BEND_FIRM), None)
            centre.parent = hook or p["root"]
            bpy.context.view_layer.update()
            centre.matrix_parent_inverse = centre.parent.matrix_world.inverted()
            centre.location = p["root"].matrix_world @ self._bent_spot(p, e["near"])
            window = (centre, float(e["radius"]))
        glow.ghost(meshes, e.get("color", "ice"), begin, end, fade, self.total, float(e.get("edge", 2.2)), float(e.get("strength", 1.4)), window=window, fill=float(e.get("fill", 0.0)))

    def _turns(self, e: dict) -> None:
        """Part of something turning into other stuff, near a spot: a bird's head going to sponge, to show what that would be like."""
        p = self.props[e["prop"]]
        meshes = bounds.meshes_of(p["root"])
        bpy.context.view_layer.update()
        glow.mark_part(meshes, tuple(p["root"].matrix_world @ p["thing"].spot(e["near"])), float(e["radius"]), name=glow.TURNED)
        glow.turn_part(meshes, e["into"], self.frame(e["t"]), self.frame(e["to"]) if "to" in e else self.total, round(float(e.get("fade", 0.4)) * self.fps), self.total)

    def _pit(self, e: dict) -> None:
        """A mark on a surface where it's being hit, growing, so what's hitting it shows on what's hit."""
        begin = self.frame(e["t"])
        keep = self.bl.frame_current
        at = self.aim(e["at"], begin)
        self.bl.frame_set(keep)
        glow.pit(bounds.meshes_of(self.props[e["on"]]["root"]), tuple(at), float(e.get("from_radius", float(e["radius"]) * 0.6)), float(e["radius"]), begin, begin + max(1, round(float(e.get("over", 1.0)) * self.fps)), self.total)

    def _dim(self, e: dict) -> None:
        """The place around everything going dark, or coming back: it's what lets what's lit stand out against it, as an x-ray does."""
        bg = next(n for n in self.bl.world.node_tree.nodes if n.type == "BACKGROUND")
        socket = bg.inputs["Strength"]
        begin, count = self.frame(e["t"]), max(1, round(float(e.get("over", 0.3)) * self.fps))
        was = socket.default_value
        socket.keyframe_insert("default_value", frame=max(1, begin - 1)) if begin > 1 else None
        socket.default_value = was * float(e["level"])
        socket.keyframe_insert("default_value", frame=begin + count)

    def _flow_paths(self, e: dict, p: dict, solid: bounds.Solid) -> list[tuple]:
        """Where a flow's lines run, in the world as things stand: a part's own line, or circles around a spot, each laid on the
        thing's surface by rays, so they follow its shape. A point with no surface under it is left out, so a line stops at the
        thing's edge. Returns (points, closed)."""
        thing, root = p["thing"], p["root"]
        place = root.matrix_world
        if e.get("along"):
            lift = Vector((0, 0, float(e.get("lift", 0.0))))
            return [([place @ (q + lift) for q in thing.line(e["along"])], False)]
        _, _, part = e["on"].partition(":")
        turn = place.to_3x3().normalized()
        x, y, z = turn.col[0], turn.col[1], turn.col[2]
        middle = place @ (thing.spot(part) if part else Vector())
        way = z if e.get("side") == "under" else -z         # the way a ray goes to reach the surface
        lift = float(e.get("width", 0.0012)) * 0.8
        paths = []
        for radius in e.get("radii") or [thing.size.x / 3]:
            arcs = int(e.get("arcs", 1))
            arc = math.radians(float(e.get("arc", 360.0))) if arcs > 1 or "arc" in e else math.tau
            steps = max(24, int(arc * radius / 0.004))
            for k in range(arcs):
                start = math.tau * k / arcs + float(e.get("turn", 0.0))
                run, kept = [], []
                for i in range(steps + 1):
                    angle = start + arc * i / steps
                    over = middle + (x * math.cos(angle) + y * math.sin(angle)) * radius
                    hit = solid.ray(over - way * 0.5, way)
                    if hit is None:
                        if len(run) > 1:
                            kept.append(run)
                        run = []
                        continue
                    run.append(hit[0] + hit[1] * (lift if hit[1].dot(way) < 0 else -lift))
                if len(run) > 1:
                    kept.append(run)
                paths += [(line, False) for line in kept]
        return paths

    def _flow(self, e: dict) -> None:
        """Thin light on a thing's surface, or along one of its parts, running."""
        cid = e["on"].partition(":")[0]
        p = self.props[cid]
        begin = self.frame(e["t"])
        end = self.frame(e["to"]) if "to" in e else self.total
        self.bl.frame_set(begin)
        bpy.context.view_layer.update()
        place = p["root"].matrix_world.copy()
        paths = self._flow_paths(e, p, bounds.Solid(bounds.meshes_of(p["root"])))
        if not paths:
            raise Refused([f"the flow at {e['t']} s on {e['on']} has no surface to run on: its circles miss {cid} altogether"])
        fade = round(float(e.get("fade", 0.15)) * self.fps)
        width = float(e.get("width", 0.0012))
        pulses, speed, steady = float(e.get("pulses", 3.0)), float(e.get("speed", 1.0)), float(e.get("steady", 7.0))
        line_paint = glow.line_material(f"{cid}.flow{begin}", e["color"], begin, end, fade, self.total, self.fps, steady=steady,
                                        peak=float(e.get("peak", 46.0)), pulses=pulses, speed=speed, reverse=float(e.get("reverse", 0.0)))
        bead_paint = None
        if e.get("beads"):
            bead_paint = glow.line_material(f"{cid}.beads{begin}", e.get("bead_color", e["color"]), begin, end, fade, self.total, self.fps,
                                            steady=0.0, peak=float(e.get("bead_peak", 9.0)), pulses=float(e["beads"]), speed=speed,
                                            duty=0.32, reverse=float(e.get("reverse", 0.0)))
        for i, (points, closed) in enumerate(paths):
            for suffix, paint, radius in (("line", line_paint, width / 2), ("beads", bead_paint, width * 1.6)):
                if paint is None:
                    continue
                obj = glow.tube(f"{cid}.{suffix}{begin}.{i}", points, radius, closed)
                obj["light"] = True
                obj.data.materials.append(paint)
                obj.parent = p["root"]
                obj.matrix_parent_inverse = place.inverted()
                p.setdefault("lights", []).append(obj)

    def _clean_rings(self, e: dict, f: int, at: Vector, way: Vector) -> None:
        """Thin true circles spreading from a point, one after another, facing the lens."""
        reach = float(e.get("reach", 0.2))
        life = max(4, round(float(e.get("over", 0.9)) * self.fps))
        width = float(e.get("width", 0.0009 + reach * 0.004))
        for i in range(int(e.get("count", 3))):
            glow.ring(f"Ring{f}.{i}", at + way * 0.002, way, f + i * max(2, life // 5), life, reach * (1 - 0.14 * i), width,
                      e.get("color", "white"), float(e.get("strength", 22.0)))

    def _act(self) -> None:
        for at, frame, color, t in self.waiting_rings:
            way = self._facing_shot(t)
            self._clean_rings({"color": color, "reach": 0.22, "count": 4, "width": 0.002}, frame, at + way * 0.03, way)
        for e in self.events:
            kind, f = e["do"], self.frame(e.get("t", 0))
            if kind == "expression":
                self.people[e["who"]].expression(f, e["name"], e.get("amount", 1.0))
            elif kind == "face":
                self.people[e["who"]].face(f, strict=False, **e["keys"])
            elif kind == "gaze":
                self.people[e["who"]].gaze(f, e.get("x", 0.0), e.get("y", 0.0))
            elif kind == "glow":
                self._glow(e)
            elif kind in ("lit", "aura"):
                self._lit(e)
            elif kind == "tint":
                self._tint(e)
            elif kind == "ghost":
                self._ghost(e)
            elif kind == "dim":
                self._dim(e)
            elif kind == "turns":
                self._turns(e)
            elif kind == "pit":
                self._pit(e)
            elif kind == "flow":
                self._flow(e)
            elif kind == "rings":
                self._clean_rings(e, f, self.aim(e["on"], f), self._facing_shot(e["t"]))
            elif kind == "sparks":
                self._sparks(self.aim(e["on"], f), f, kind=e.get("kind", "sparks"), count=int(e.get("count", 26)), slow=float(e.get("slow", SLOW)), away=e.get("away"))
            elif kind == "pour":
                self._pour(e)
            elif kind == "air":
                self._air(e)
            elif kind == "play":
                end = self.frame(e["to"]) if "to" in e else self.total + 1
                self.props[e["prop"]]["thing"].play(f, end, e["move"], float(e.get("speed", 1.0)))
            elif kind == "move":
                p = self.props[e["prop"]]
                palm, points, fingers = self._grip(p["holder"], p["hand"], e["grip"])
                over = max(1, round(e["over"] * self.fps))
                p.setdefault("path", []).append({"from": f, "to": f + over, "palm1": palm, "points1": points, "fingers": fingers})

    def _key_props(self) -> None:
        """Each moving prop, frame by frame: it speeds up into a blow, and bounces off, or gives in if it's soft."""
        for p in self.props.values():
            if p.get("bitten") or not p.get("path"):
                continue
            root = p["root"]
            legs = sorted(p["path"], key=lambda leg: leg["from"])
            first = p.get("start") or (p["palm"], p["points"], p["fingers"])
            for f in range(1, self.total + 1):
                palm, turn = first[0], self._turn_of(p, first[1], first[2])
                for leg in legs:
                    if f >= leg["to"]:
                        palm, turn = self._after_blow(p, leg, f) if leg.get("blow") else (leg["palm1"], self._turn_of(p, leg["points1"], leg["fingers"]))
                    elif f > leg["from"]:
                        t = (f - leg["from"]) / (leg["to"] - leg["from"])
                        t = t * t if leg.get("blow") else t * t * (3 - 2 * t)
                        palm, turn = palm.lerp(leg["palm1"], t), turn.slerp(self._turn_of(p, leg["points1"], leg["fingers"]), t)
                        break
                    else:
                        break
                root.location, root.rotation_quaternion = palm, turn
                root.keyframe_insert("location", frame=f)
                root.keyframe_insert("rotation_quaternion", frame=f)
                p.setdefault("track", {})[f] = (palm.copy(), turn.copy())

    def _after_blow(self, p: dict, leg: dict, f: int) -> tuple[Vector, Quaternion]:
        """Where something is after it's landed: it comes back up off what it hit, and if it's soft it goes on in by as far as it gives, before it does."""
        since = (f - leg["to"]) * leg.get("slow", 1.0)
        lift = 1 - math.exp(-since / 16.0)
        palm = leg["palm1"] + UP * (0.05 * lift)
        if leg.get("give"):
            palm = palm - leg["away"] * (leg["give"] * _pressed(since)) + leg["away"] * (0.09 * lift)
        return palm, self._turn_of(p, (leg["points1"] + UP * (0.16 * lift)).normalized(), leg["fingers"])

    def _blinks(self) -> None:
        rng = random.Random(4)
        for cid, person in self.people.items():
            until = min([self.frame(e["t"]) for e in self.events if e["do"] == "expression" and e.get("who") == cid and e.get("name") in people.OWN_FACES] or [self.total - 8])      # someone knocked out doesn't blink
            f = rng.randint(12, 40)
            while f < until - 8:
                person.blink(f)
                f += rng.randint(70, 130)

    # --- what fills things, what pours, and air ----------------------------------------------------------------------

    def _liquid_of(self, cid: str, part: str | None = None):
        found = self.props[cid].get("liquids") or {}
        return found[part] if part else next(iter(found.values()))

    def _moves(self, cid: str) -> bool:
        p = self.props.get(cid) or {}
        return bool(p.get("track") or p.get("carried") or p.get("pressed")) or any(e.get("prop") == cid and e["do"] in MOVERS for e in self.events)

    def _liquids(self) -> None:
        """Each liquid's top, in the world, frame by frame: where the scene says it starts (`level`, meters above the bottom of the liquid, or above
        the top of another's with `above`), then each `fill`. A liquid nobody gives a level is full. Then each is cut off there, so its top is flat
        and level, whichever way what holds it is turned."""
        cast = self.spec["cast"]
        self.tops: dict[str, dict[int, float]] = {}
        waiting = [cid for cid, p in self.props.items() if p.get("liquids")]
        keep = self.bl.frame_current
        frames = range(1, self.total + 1)
        for _ in range(len(waiting) + 1):
            for cid in list(waiting):
                c = cast[cid]
                if c.get("above") and c["above"] in waiting:
                    continue
                waiting.remove(cid)
                obj = self._liquid_of(cid, c.get("part"))
                self.props[cid]["liquid_paint"] = [slot.material.copy() for slot in obj.material_slots if slot.material]     # what it's made of, for a pour of it
                self.bl.frame_set(1)
                bpy.context.view_layer.update()
                bottom, full = liquid.lowest(obj), liquid.highest(obj) - liquid.lowest(obj)
                base = {f: bottom for f in frames}
                if self._moves(cid):
                    for f in frames:
                        self.bl.frame_set(f)
                        bpy.context.view_layer.update()
                        base[f] = liquid.lowest(obj)
                fills = sorted((e for e in self.events if e["do"] == "fill" and e["prop"] == cid), key=lambda e: e["t"])
                if "level" not in c and not fills:      # full: cut a hair under its own top all the same, as the cut's top is the clean one
                    self.tops[cid] = {f: base[f] + full - liquid.FULL_SHORT for f in frames}
                    liquid.cut_at(obj, [(f, self.tops[cid][f]) for f in frames])
                    continue
                under = self.tops[c["above"]] if c.get("above") else base
                height = {f: float(c.get("level", full)) for f in frames}
                for e in fills:
                    begin, count = self.frame(e["t"]), max(1, round(float(e["over"]) * self.fps))
                    was, kind = height[begin], e.get("ease", "inout")
                    for f in frames:
                        if f < begin:
                            continue
                        x = min(1.0, (f - begin) / count)
                        x = x if kind == "linear" else x * x if kind == "in" else 1 - (1 - x) ** 2 if kind == "out" else x * x * (3 - 2 * x)
                        height[f] = was + (float(e["level"]) - was) * x
                self.tops[cid] = {f: under[f] + height[f] for f in frames}
                liquid.cut_at(obj, [(f, self.tops[cid][f]) for f in frames])
        self.bl.frame_set(keep)
        bpy.context.view_layer.update()

    def _spot_at(self, aim: str, frame: int) -> Vector:
        self.bl.frame_set(frame)
        bpy.context.view_layer.update()
        return self.aim(aim, frame).copy()

    def _pour(self, e: dict) -> None:
        """A stream from a spout straight down into what's being filled. If it isn't over it, or something solid's in the way, the scene's refused
        in words."""
        who = e["from"].partition(":")[0]
        into = e["into"]
        begin, end = self.frame(e["t"]), self.frame(e["to"])
        keep = self.bl.frame_current
        if self._moves(who):
            spout = {f: self._spot_at(e["from"], f) for f in range(1, self.total + 1)}
        else:
            at = self._spot_at(e["from"], begin)
            spout = {f: at for f in range(1, self.total + 1)}
        foot = self.tops[into]
        self.bl.frame_set(begin)
        bpy.context.view_layer.update()
        here = spout[begin]
        if here.z <= foot[begin]:
            raise Refused([f"the pour from {e['from']} at {e['t']} s starts below the top of what's in {into}"])
        filled = self._liquid_of(into, e.get("part"))
        inside = liquid.tree_of([filled])
        under = max(foot[begin] - 0.001, liquid.lowest(filled) + 0.001)       # inside what it'll fill, even if that's still empty
        if inside is None or not liquid.holds(inside, Vector((here.x, here.y, under))):
            raise Refused([f"the pour from {e['from']} at {e['t']} s isn't over what's in {into}: falling straight down, it would miss it"])
        for cid in [*self.props, *(["the set"] if self.solids else [])]:
            if cid == who:
                continue
            hit = self._solid_of(cid).ray(here - UP * 0.0005, -UP)
            if hit and hit[0].z > foot[begin] + 0.001:
                where = "the counter" if cid == "the set" else cid
                raise Refused([f"the pour from {e['from']} at {e['t']} s lands on {where}, {(hit[0].z - foot[begin]) * 100:.1f} cm above what's in {into}"])
        paint = self.props[into]["liquid_paint"][0]
        liquid.stream(f"{who}.pour{begin}", paint, spout, foot, begin, end, self.total, self.fps, float(e.get("width", 0.006)), float(e.get("speed", 0.3)))
        self.bl.frame_set(keep)

    def _air(self, e: dict) -> None:
        """Air as balls in a box, every way at once, bouncing off everything solid and off the top of every liquid, some drawn off where it says."""
        begin = self.frame(e["t"])
        end = self.frame(e["to"]) if "to" in e else self.total
        keep = self.bl.frame_current
        bodies = [obj for p in self.props.values() for obj in bounds.meshes_of(p["root"])] + [person.body for person in self.people.values()] + list(self.solids)
        moving = any(self._moves(cid) for cid in self.props) or any(other["do"] in ("walk", "act", "strike") for other in self.events)
        solid_trees: dict[int, list] = {}
        wet = [(cid, self._liquid_of(cid, self.spec["cast"][cid].get("part"))) for cid in self.tops]
        wet_trees: dict[int, list] = {}

        def solids(f):
            key = f if moving else 0
            if key not in solid_trees:
                self.bl.frame_set(f)
                bpy.context.view_layer.update()
                solid_trees.clear()
                made = liquid.tree_of(bodies)
                solid_trees[key] = [made] if made else []
            return solid_trees[key]

        def liquids(f):
            key = f if moving else 0
            if key not in wet_trees:
                self.bl.frame_set(f)
                bpy.context.view_layer.update()
                wet_trees.clear()
                wet_trees[key] = [liquid.tree_of([obj]) for _, obj in wet]
            return [(tree, self.tops[cid][f]) for tree, (cid, _) in zip(wet_trees[key], wet) if tree]

        box = e["box"]
        has_floor = self.spec["set"] in FLOORED and (self.spec["set"] != "place" or self.spec["place"].get("ground"))     # a place with no ground has nothing at 0
        floor = 0.0 if has_floor and box[0][2] <= 0.05 <= box[1][2] else None
        name = e.get("color", "ice")
        paint = materials.custom(f"air.{begin}.{name}.{e.get('glow', 0.35)}", color=glow.color_of(name), rough=0.35, glow=float(e.get("glow", 0.35)))
        self.bl.frame_set(begin)
        bpy.context.view_layer.update()
        parts = []                         # each solid part by itself, as it stands when the air starts, to ask whether a ball would start inside it
        for obj in bodies:
            tree = liquid.tree_of([obj])
            if tree is not None:
                corners = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
                parts.append((Vector([min(c[i] for c in corners) for i in range(3)]), Vector([max(c[i] for c in corners) for i in range(3)]), tree))
        within = None
        if e.get("inside"):                # only in the hollow of something: a tube, a bottle, a column
            self.bl.frame_set(begin)
            bpy.context.view_layer.update()
            shell = self._solid_of(e["inside"])
            within = lambda at: shell.encloses(at)
        air = liquid.Air(f"Air{begin}", box, int(e["count"]), float(e.get("radius", 0.01)), float(e.get("speed", 0.4)), paint, self.fps, solids, liquids,
                         floor=floor, thins=e.get("thins"), walled=bool(e.get("walled", False)), seed=begin * 7 + self.events.index(e), within=within, parts=parts)
        air.fill(begin)
        if len(air.balls) < int(e["count"]) * MOST_AIR_SHORT:
            where = f"inside {e['inside']}" if e.get("inside") else "in its box"
            raise Refused([f"the air at {e['t']} s found room for {len(air.balls)} of its {e['count']} balls {where}: a ball only starts "
                           f"{liquid.ROOM} times its radius from anything solid, so make the balls smaller or the box bigger"])
        for g in e.get("leave") or []:
            out = Vector(g["through"]) if isinstance(g["through"], list) else self._spot_at(g["through"], self.frame(g["t"]))
            air.plans.append({"frame": self.frame(g["t"]), "share": float(g.get("share", 1.0)), "out": out, "over": float(g.get("over", 1.0)), "inside": g.get("from")})
        air.run(begin, end, self.total)
        self.bl.frame_set(keep)
        bpy.context.view_layer.update()

    # --- the shots -------------------------------------------------------------------------------------------------

    def _shots(self) -> None:
        shots = self.spec["shots"]
        ends = [self.frame(s["t"]) for s in shots[1:]] + [self.total + 1]
        ranges: dict[str, list] = {cid: [] for cid in self.spec["cast"]}
        for s, end in zip(shots, ends):
            begin = self.frame(s["t"])
            on = self.aim(s["on"], begin + round(float(s.get("ahead", 0)) * self.fps))
            lens = float(s.get("lens", 28))
            distance = float(s["frame"]) * lens / 24
            at = on + self._way_to_lens(s, begin)[0] * distance
            cam, target = look.camera(self.bl, at, on, lens=lens, fstop=float(s.get("fstop", 3.0)), name=f"Shot{begin}")
            cam.data.clip_start = max(0.005, distance / 100)
            if s.get("shift"):
                self._shift_lens(cam, s["shift"])
            final = on + (at - on) * (1 - float(s.get("push", 0.0))) + Vector(s.get("drift", (0, 0, 0)))
            look.key(cam, begin, location=at)
            look.key(cam, end, location=final)
            if s.get("to"):
                self._glide(s, cam, target, begin, end, on, lens)
            elif s.get("follow"):          # it travels with what it's on, so that stays put in the picture
                path = self._followed(s["on"], begin, end)
                for f in range(begin, end + 1):
                    here = path[f]
                    look.key(target, f, location=here)
                    look.key(cam, f, location=here + (at - on) + (final - at) * ((f - begin) / max(1, end - begin)))
            look.ease(cam, "LINEAR")
            self.bl.timeline_markers.new(f"Shot{begin}", frame=begin).camera = cam
            self.cuts.append({"t": s["t"], "begin": begin, "end": end - 1, "camera": cam, "aim": target, "frame": s["frame"],
                              "on": s["on"].partition(":")[0], "glides": bool(s.get("to"))})
            for cid in self.spec["cast"]:
                if s.get("shows") is None or cid in s["shows"]:
                    ranges[cid].append((begin, end - 1))
        self.spans = ranges
        for cid in self.spec["cast"]:
            spans = ranges[cid]
            if len(spans) == len(shots):
                continue             # in every shot: nothing to switch
            root = self.people[cid].rig if cid in self.people else self.props[cid]["root"]
            _only_during(root, spans, self.total)

    def _pairs_allowed(self) -> set:
        """Who's meant to touch: what's said in the scene, and what its events have touch."""
        allowed = {frozenset(pair) for pair in self.spec.get("touching") or []}
        allowed |= {frozenset((cid, c["to"].partition(":")[0])) for cid, c in self.spec["cast"].items() if c.get("to")}
        allowed |= {frozenset((cid, c[way])) for cid, c in self.spec["cast"].items() for way in ("against", "inside") if c.get(way)}
        for cid, c in self.spec["cast"].items():       # what's inside something is inside whatever that's inside
            outer = c.get("inside")
            while outer and self.spec["cast"][outer].get("inside"):
                outer = self.spec["cast"][outer]["inside"]
                allowed.add(frozenset((cid, outer)))
        for e in self.events:
            if e["do"] in ("hold", "bite", "wear", "strike"):
                allowed.add(frozenset((e["who"], e["prop"])))
            if e["do"] == "strike":
                allowed.add(frozenset((e["prop"], e["target"].partition(":")[0])))
            if e["do"] in ("fly", "go") and e.get("hits"):
                allowed.add(frozenset((e["prop"], e["hits"])))
            if e["do"] == "go" and e.get("lands") and isinstance(e["through"][-1], str):
                allowed.add(frozenset((e["prop"], e["through"][-1].partition(":")[0])))
        return allowed

    def _shown(self, cid: str, frame: int) -> bool:
        return any(a <= frame <= b for a, b in self.spans.get(cid, []))

    def _solid_of(self, cid: str) -> bounds.Solid:
        if cid == "the set":
            return bounds.Solid(self.solids)
        if cid in self.people:
            return bounds.Solid([self.people[cid].body])
        return bounds.Solid(bounds.meshes_of(self.props[cid]["root"]))

    def _crossings(self) -> list[str]:
        """Anything that passes through anything else while they're both in the picture."""
        allowed = self._pairs_allowed()
        moving = {cid for cid, p in self.props.items() if p.get("track") or p.get("pressed") or p.get("carried")}
        names = list(self.props) + list(self.people) + (["the set"] if self.solids else [])
        names = [cid for cid in names if any(other != cid and frozenset((cid, other)) not in allowed for other in names)]     # nothing to measure, if all it can meet is meant to touch it
        kept: dict[str, bounds.Solid] = {}
        deepest: dict[frozenset, tuple] = {}
        doing = {e["do"] for e in self.events}
        person_every = PERSON_WALKING if "walk" in doing else PERSON_ACTING if "act" in doing else PERSON_EVERY
        frames = sorted({*range(1, self.total + 1, CHECK_EVERY if moving else person_every if doing & {"walk", "act"} else max(self.total, 1)), self.total})
        for f in frames:
            self.bl.frame_set(f)
            bpy.context.view_layer.update()
            people_now = (f - 1) % person_every == 0 or f == self.total
            solids = {}
            for cid in names:
                if cid != "the set" and not self._shown(cid, f):
                    continue
                if cid in self.people:
                    if people_now:
                        solids[cid] = self._solid_of(cid)
                    continue
                p = self.props.get(cid)
                if p is not None and p["root"].scale.length < 1e-6:       # not thrown yet
                    continue
                if cid in moving or cid not in kept:
                    kept[cid] = self._solid_of(cid)
                solids[cid] = kept[cid]
            ids = list(solids)
            for i, a in enumerate(ids):
                for b in ids[i + 1:]:
                    key = frozenset((a, b))
                    if key in allowed or (f > 1 and a not in moving and b not in moving and a not in self.people and b not in self.people):
                        continue
                    depth = solids[a].crossing(solids[b])
                    if depth > TOO_DEEP and depth > deepest.get(key, (0,))[0]:
                        deepest[key] = (depth, (f - 1) / self.fps, a, b)
        return [f"{a} and {b} pass through each other by {depth * 100:.1f} cm, at {t:.2f} s of this scene. Move one, or if they're "
                f"meant to touch, say so in touching" for depth, t, a, b in deepest.values()]

    def _hanging(self) -> list[str]:
        """Anything left in the air, with nothing holding it up, that nobody said was meant to hang there."""
        out = []
        self.bl.frame_set(self.total)
        bpy.context.view_layer.update()
        others = {cid: self._solid_of(cid) for cid in self.props}
        if self.solids:
            others["the set"] = self._solid_of("the set")
        for cid, p in self.props.items():
            c = self.spec["cast"][cid]
            travels = any(e["do"] in ("go", "fly") and e.get("prop") == cid for e in self.events)
            if c.get("floats") or c.get("on") or c.get("to") or c.get("against") or c.get("inside") or p.get("holder") or travels or self.spec["set"] not in (*FLOORED, "sky_counter"):
                continue
            mine = others[cid]
            if self.spec["set"] in FLOORED and mine.low.z < TOUCHING:     # on the floor, or planted in it
                continue
            gap = min((mine.gap_to(s) for other, s in others.items() if other != cid), default=float("inf"))
            if self.spec["set"] in FLOORED:
                gap = min(gap, abs(mine.low.z))
            if gap > TOUCHING:
                out.append(f"{cid} hangs in the air, {gap * 100:.1f} cm from anything. Say what it's on, or floats: true if it's a marker")
        return out

    def _blocked(self) -> list[str]:
        """A shot whose lens is inside something, or with something right in front of it, covering what it's on."""
        out = []
        for cut in self.cuts:
            middle = (cut["begin"] + cut["end"]) // 2
            for f in ((cut["begin"], middle, cut["end"]) if cut["glides"] else (middle,)):    # a glide can run into something on the way
                self.bl.frame_set(f)
                bpy.context.view_layer.update()
                found = self._blocked_at(cut, f)
                if found:
                    out += found
                    break
        return out

    def _blocked_at(self, cut: dict, f: int) -> list[str]:
        out = []
        lens, aim = cut["camera"].matrix_world.translation.copy(), cut["aim"].matrix_world.translation.copy()
        if self.solids and lens.z < self._solid_of("the set").high.z:
            out.append(f"the shot at {cut['t']} s has its lens under the counter")
        way = aim - lens
        right = way.cross(UP).normalized()
        over = right.cross(way).normalized()
        reach = float(cut["frame"]) * 0.08
        subject = cut["on"]
        around = self._inside_chain(subject) if subject in self.props else []       # what a shot looks through, to what's inside it, isn't in its way
        for cid in [*self.props, *self.people]:
            if cid == subject or cid in around or not self._shown(cid, f) or (self.props.get(cid) or {}).get("worn") or self._see_through(cid):
                continue
            solid = self._solid_of(cid)
            if solid.tree is None:
                continue
            ahead = solid.ray(lens, way.normalized())
            if all(solid.low[i] <= lens[i] <= solid.high[i] for i in range(3)) and ahead and ahead[2] < way.length - BEHIND_SUBJECT:
                out.append(f"the shot at {cut['t']} s has its lens inside {cid}. Leave {cid} out of its shows, or move the lens")
                continue
            blocked = 0
            for a in LENS_ROWS:
                for b in LENS_ROWS:
                    to = (aim + right * (a * reach) + over * (b * reach)) - lens
                    hit = solid.ray(lens, to.normalized())
                    if hit and hit[2] < to.length * NEAR_LENS:
                        blocked += 1
            if blocked >= 5:
                out.append(f"{cid} is right in front of the lens in the shot at {cut['t']} s, covering {subject}. Leave it out of its shows, or move the lens")
        return out

    def _see_through(self, cid: str) -> bool:
        """A thing that's all glass: a shot looks through it, so it isn't in the way."""
        p = self.props.get(cid)
        meshes = bounds.meshes_of(p["root"]) if p else []
        return bool(meshes) and all(obj.get("clear") for obj in meshes)

    def _hands_off(self) -> list[str]:
        """A hand that can't get to what it's holding, and what's held going through whoever's holding it. Hands and handles touch, so what's further along is what's measured."""
        out = []
        for e in self.events:
            if e["do"] != "hold":
                continue
            person, p = self.people[e["who"]], self.props[e["prop"]]
            target = person.holds[e["hand"]]
            frames = sorted({*range(1, self.total + 1, 3), self.total})
            worst, when, through = 0.0, 0, None
            for f in frames:
                self.bl.frame_set(f)
                bpy.context.view_layer.update()
                gap = ((person.rig.matrix_world @ person.bone(f"hand.{e['hand']}").head) - target.matrix_world.translation).length
                if gap > worst:
                    worst, when = gap, f
                if through is None and p.get("path"):
                    held = bounds.Solid(bounds.meshes_of(p["root"]))
                    palm = p["root"].matrix_world.translation
                    far = [v for v in held._sample(120) if (v - palm).length > HELD_CLEAR]
                    body = bounds.Solid([person.body])
                    if any(all(body.low[i] <= v[i] <= body.high[i] for i in range(3)) and body.encloses(v) for v in far):
                        through = f
            if worst > HAND_SLIPS:
                out.append(f"{e['who']}'s hand can't reach {e['prop']}: it's {worst * 100:.0f} cm off it at {(when - 1) / self.fps:.2f} s of this scene. Stand nearer, or use a nearer grip")
            if through is not None:
                out.append(f"{e['prop']} goes through {e['who']} at {(through - 1) / self.fps:.2f} s of this scene. Stand them further off, or strike from the other side")
        return out

    def check_physics(self) -> None:
        problems = self._crossings() + self._hanging() + self._blocked() + self._poking_out() + self._outside_outline() + self._hands_off()
        self.bl.frame_set(1)
        if problems:
            raise Refused(problems)

    def run(self) -> dict:
        if self.spec["set"] == "place":
            self.solids = envs.place(**{k: v for k, v in self.spec["place"].items() if k != "light"}) or []
        else:
            self.solids = getattr(envs, self.spec["set"])(**({"depth": DEEP_COUNTER} if self.spec["set"] == "sky_counter" and self.spec.get("place") else {})) or []
        if self.spec.get("place") and self.spec["set"] != "place":
            envs.room_behind(**self.spec["place"])
        self._start_short()
        self.build_people()
        self.build_props()
        self.settle()
        # stand everyone first, so what's placed on their body is placed where it ends up. A blow's knock is added after,
        # when the strike is worked out; playing the stance again with it replaces those keys
        self._key_people()
        self._solve_hits()
        self.stage_holds()
        for e in self.events:
            if e["do"] == "strike":
                self._strike(e)
            elif e["do"] == "fly":
                self._fly(e)
            elif e["do"] == "go":
                self._go(e)
            elif e["do"] == "rock":
                self._rock(e)
            elif e["do"] == "spin":
                self._spin(e)
            elif e["do"] == "slide":
                self._slide(e)
            elif e["do"] == "squash":
                self._squash(e)
            elif e["do"] == "press":
                self._press(e)
        if any(self.knocks.values()) or self.swings:
            self._key_people()
        self._land_people()
        self._key_props()
        self._liquids()
        self._act()
        self._blinks()
        strength = float(self.spec["place"].get("light", PLACE_LIGHT)) if self.spec["set"] == "place" else 1.0
        if self.people:
            first, lead = next(iter(self.people.items()))
            self._lights_on(first, envs.portrait_lights(lead.middle(lead.eyes), key=130.0 * strength, fill=60.0 * strength, rim=70.0 * strength, facing=self._facing(first)))
        elif self.props and not self.solids:
            opening = self.spec["shots"][0]
            lens_way = self._way_to_lens(opening, self.frame(opening["t"]))[0]        # lit from the side it's seen from
            envs.portrait_lights(self.aim(opening["on"], self.frame(opening["t"])), key=130.0 * strength, fill=60.0 * strength, rim=70.0 * strength, facing=math.degrees(math.atan2(lens_way.x, -lens_way.y)))
        for p in self.props.values():
            if p.get("thing"):
                p["thing"].finish()
        spinning = any(e["do"] == "spin" for e in self.events)
        self.bl.render.motion_blur_shutter = 0.5 if spinning else 0.25
        self.bl.eevee.motion_blur_steps = 4 if spinning else 1      # a turn's blur follows the arc, in that many straight steps
        if any(e["do"] in ("flow", "rings", "strike", "lit", "aura", "ghost") for e in self.events):
            look.halo(self.bl, threshold=1.7, strength=0.5, size=0.6)
        self._shots()
        self.check_physics()
        return {"frames": self.total, "anchors": self._anchors(), "events": self._sound_cues()}

    def _anchors(self) -> dict:
        """What the short's labels name, each as an empty keyed to its aim every frame, so its place on screen can be tracked
        (blender/tracks.py). It carries the name of what it's on: that thing's own surface doesn't hide it, as the label's on it."""
        out = {}
        for name in self.spec.get("anchors") or []:
            mark = bpy.data.objects.new(f"anchor.{name}", None)
            self.bl.collection.objects.link(mark)
            who, _, part = name.partition(":")
            owner = self.people[who].rig if who in self.people else (self.props[who].get("root") if who in self.props else None)
            if owner is not None:
                mark["of"] = owner.name
            p = self.props.get(who) or {}
            if p.get("thing") and part in p["thing"].spots:
                # a spot on a thing rides on the thing, so it's wherever the thing is drawn, however it's moved: keyed from where it was
                # worked out to be, a slid arrow's label ran off ahead of it (found on the straw short's pump)
                grip = p["thing"].spot("grip") if p.get("holder") and "grip" in p["thing"].spots else Vector()
                mark.parent = p["root"]
                mark.location = self._bent_spot(p, part) - grip
            else:
                for f in range(1, self.total + 1):
                    mark.location = self.aim(name, f)
                    mark.keyframe_insert("location", frame=f)
            out[name] = (mark, (0.0, 0.0, 0.0))
        return out

    def _footsteps(self, e: dict) -> list[dict]:
        """A step each time their hips come down in a walking move, worked out from the move, so they keep time with it however it's paced."""
        clip, solver = self._clip(e["clip"]), self.solvers[e["who"]]
        heights = [h.z for h in clip["hips"]]
        period = max(1, clip["frames"] - 1)
        lows = [i for i in range(period) if heights[i] <= heights[(i - 1) % period] and heights[i] < heights[(i + 1) % period]]
        if not lows:
            return []
        speed, clock = self._walk_speed(e["who"], e, clip, solver), self._walk_clock(e)
        begin, count = self.frame(e["t"]), max(1, round(float(e["over"]) * self.fps))
        step = e["last_step"] - clock(count - 1) * speed if "last_step" in e else 0
        cues = []
        for n in range(count):
            here, then = (clock(n) * speed + step) % period, (clock(n + 1) * speed + step) % period
            passed = [i for i in lows if (here <= i < then if here <= then else i >= here or i < then)]
            if passed:
                cues.append({"frame": begin + n, "kind": "step"})
        return cues

    def _landing(self, e: dict) -> list[dict]:
        """A move that takes someone down to the ground ends in a thud, as they land."""
        clip = self._clip(e["clip"])
        heights = [h.z for h in clip["hips"]]
        drop = heights[0] - min(heights)
        if drop < FALLS * clip["leg"]:
            return []
        land = next(i for i, z in enumerate(heights) if heights[0] - z >= 0.9 * drop)
        return [{"frame": self.frame(e["t"]) + round(max(0.0, land - float(e.get("skip", 0.0)) * self.fps) / float(e.get("speed", 1.0))), "kind": "land"}]

    def _sound_cues(self) -> list[dict]:
        """When something lands or sets off, for the short's sound."""
        cues = []
        for e in self.events:
            if e["do"] == "strike":
                cues.append({"frame": self.frame(e["t"]), "kind": "hit"})
            elif e["do"] in ("fly", "go"):
                cues.append({"frame": self.frame(e["t"]), "kind": e["do"]})
                if e.get("hits"):
                    cues.append({"frame": self.frame(e["t"] + e["over"]), "kind": "hit"})
            elif e["do"] == "rock":
                times = int(e.get("times", 1))
                cues += [{"frame": self.frame(e["t"] + e["over"] * k / times), "kind": "rock"} for k in range(1, times + 1)]
            elif e["do"] == "spin":
                cues.append({"frame": self.frame(e["t"]), "kind": "go"})
            elif e["do"] == "slide" and "from" in e:     # set down
                cues.append({"frame": self.frame(e["t"] + e["over"]), "kind": "rock"})
            elif e["do"] == "knock" and float(e["size"]) >= 6:
                cues.append({"frame": self.frame(e["t"]), "kind": "hit"})
            elif e["do"] in ("squash", "press"):
                cues.append({"frame": self.frame(e["t"]), "kind": "hit"})
            elif e["do"] == "walk":
                cues += self._footsteps(e)
            elif e["do"] == "act":
                cues += self._landing(e)
        for s in self.spec["shots"]:            # a big move of the camera gets a soft rush of air
            to = s.get("to")
            if to and (float(to.get("frame", s["frame"])) / float(s["frame"]) > 1.8 or float(s["frame"]) / float(to.get("frame", s["frame"])) > 1.8):
                cues.append({"frame": self.frame(s["t"]), "kind": "go"})
        return cues


def run(job: dict, fps: int) -> dict:
    """A scene staged, or refused: what's wrong goes in refused.json beside its frames, so whoever's filming can read it in full."""
    try:
        return Stage(job["scene"], job["folders"], job["catalog"], fps, job.get("things")).run()
    except Refused as e:
        (Path(job["out"]) / "refused.json").write_text(json.dumps(e.problems, indent=1), encoding="utf-8")
        raise

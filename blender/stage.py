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

import bpy
from mathutils import Matrix, Quaternion, Vector

from blender import bounds, clips, envs, glow, look, materials, people, shapes, things

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
UPPER_ARM, FOREARM = 0.235, 0.23    # our rig's arm, shoulder to wrist, for what a hand can reach
SHOULDER = (0.17, 0.0, 1.20)        # the shoulder of someone in a stance, in their own directions
SLOW = 0.3                          # how slowly a strike's aftermath runs, of real time
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
# how far each joint of a finger bends to close on a grip, in degrees, whatever the stance's hand is doing
FIST = {"f_index": (50, 75, 50), "f_middle": (50, 75, 50), "f_ring": (50, 75, 50), "f_pinky": (50, 75, 50), "thumb": (15, 25, 30)}
OWN_AXES = {"x": Vector((1, 0, 0)), "y": Vector((0, 1, 0)), "z": Vector((0, 0, 1))}
REST_GAP = 0.0004                 # how far above what it rests on a thing is left, so the two faces don't fight (m)
TOO_DEEP = 0.003                  # how far two things can pass through each other before it shows (m)
TOUCHING = 0.005                  # how near something has to be to be holding a thing up (m)
FLOORED = ("sky_set", "gym", "desert_lot", "studio")     # sets whose floor is at z 0, with no mesh to measure
CHECK_EVERY = 2                   # frames apart that moving things are checked
PERSON_EVERY = 10                 # and people: a body is many faces, and it moves slowly
LENS_ROWS = (-1, 0, 1)            # the rays through what a shot is on, to see whether something's in front of it
NEAR_LENS = 0.6                   # how much of the way from the lens something in front has to be to count as blocking it
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
        """A place in the world: on a person as they stand now, or on a prop, where it is at `frame` if it travels."""
        who, _, part = name.partition(":")
        if who in self.people:
            return self._on_person(who, part)
        p = self.props[who]
        spots = p["thing"].spots if p.get("thing") else {}
        if p.get("track") and frame is not None:
            here, turn = self._place(who, frame)
            if part in spots:           # a held thing's origin is where the hand closes on it
                grip = p["thing"].spot("grip") if p.get("holder") and "grip" in spots else Vector()
                return here + turn @ (p["thing"].spot(part) - grip)
            return here + turn @ UP * float(part or 0)
        if part in spots:
            return p["palm"] + _axes(p["points"], p["fingers"]) @ p["thing"].spot(part)
        return self._along(who, float(part or 0))

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
            if self.spec["set"] == "sky_set":      # its floor is only a picture, so it can't catch a real shadow
                envs.floor_shadow(f"{cid}.shadow", at)
        for e in self.events:             # who gets hit has to be known before their body's keyed
            if e["do"] == "knock":
                axis = Vector(e.get("axis", (0, 1, 0))).normalized()
                self.knocks[e["who"]].append((self.frame(e["t"]), axis, float(e["size"])))

    def _key_people(self) -> None:
        for offset, (cid, solver) in enumerate(self.solvers.items()):
            c = self.spec["cast"][cid]
            person = self.people[cid]
            inverse = person.rig.matrix_world.to_quaternion().inverted()

            holding = [e["hand"] for e in self.events if e["do"] == "hold" and e["who"] == cid]

            def adjust(frame, pose, solver=solver, cid=cid, person=person, inverse=inverse, holding=holding):
                solver.mirror_fingers(pose)
                for side in holding:
                    self._close_hand(person, pose, side)
                for start, axis, size in self.knocks[cid]:
                    for name, share in (("head", 1.0), ("neck", 0.4), ("spine.003", 0.18), ("spine.002", 0.09)):
                        angle = math.radians(ring_down(frame, start, size * share))
                        if angle:
                            bone = person.bones[name]
                            local = solver.rest[bone].inverted() @ (inverse @ axis)
                            pose[bone] = pose[bone] @ Quaternion(local, angle)

            solver.play(self._clip(c["stance"]), 1, frames=self.total, blend=0, speed=c.get("life", 0.22),
                        offset=offset * 9, adjust=adjust)
        self.bl.frame_set(1)
        bpy.context.view_layer.update()

    @staticmethod
    def _close_hand(person, pose: dict, side: str) -> None:
        """A hand holding something closes on it, on top of whatever its stance has the fingers doing."""
        for finger, bends in FIST.items():
            for joint, bend in enumerate(bends, 1):
                bone = person.bones.get(f"{finger}.0{joint}.{side}")
                if bone is not None:
                    pose[bone] = pose.get(bone, Quaternion()) @ Quaternion((1, 0, 0), math.radians(bend))

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
        at = c.get("at", (0, 0, 0))
        palm = Vector((at[0], at[1], at[2] if len(at) > 2 else 0.0)) + UP * (thing.size.z / 2)   # one that's `on` something finds its height later
        if "points" in c:
            turn = _axes(Vector(c["points"]), Vector(c.get("up", (0, 1, 0))))
        else:
            turn = Quaternion(UP, math.radians(self._facing(cid)))
        root.location, root.rotation_quaternion = palm, turn
        self.props[cid] = {"root": root, "kind": c["prop"], "thing": thing, "palm": palm, "points": turn @ UP,
                           "fingers": turn @ Vector((0, 1, 0)), "holder": None}

    def _under(self, under: str) -> bounds.Solid | None:
        if under == "set":
            return bounds.Solid(self.solids) if self.solids else None
        return bounds.Solid(bounds.meshes_of(self.props[under]["root"]))

    def _rest_on(self, cid: str, under: str) -> None:
        """Lowered onto what's under it until the two touch, measured from the meshes. It goes where `at` says across the set, or
        over what it's on: its `by` spot, or its middle, over the other's `onto` spot, or its middle."""
        c = self.spec["cast"][cid]
        p = self.props[cid]
        root, thing = p["root"], p["thing"]
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
            root.location.z -= drop - REST_GAP
        p["palm"] = root.location.copy()
        bpy.context.view_layer.update()

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
        below = {cid: c["on"] if c.get("on") else c["to"].partition(":")[0] for cid, c in cast.items() if c.get("on") or c.get("to")}
        waiting = list(below)
        for _ in range(len(waiting) + 1):
            for cid in list(waiting):
                if below[cid] not in waiting:
                    if cast[cid].get("on"):
                        self._rest_on(cid, below[cid])
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
        finish = rest if "from" in e else rest + Vector(e["by"])
        kind = e.get("ease", "inout")
        track = p.setdefault("track", {})
        for f in range(1, self.total + 1):
            if f in track and f < begin:
                continue
            x = max(0.0, min(1.0, (f - begin) / count))
            x = x * x if kind == "in" else 1 - (1 - x) ** 2 if kind == "out" else x * x * (3 - 2 * x)
            here = start.lerp(finish, x)
            root.location, root.rotation_quaternion = here, turn
            root.keyframe_insert("location", frame=f)
            root.keyframe_insert("rotation_quaternion", frame=f)
            track[f] = (here.copy(), turn.copy())

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
                if p.get("thing"):
                    p["thing"].hold_by_grip()
                p["palm"], p["points"], p["fingers"] = self._grip(e["who"], e["hand"], e["grip"])
                p["root"].location, p["root"].rotation_quaternion = p["palm"], _axes(p["points"], p["fingers"])
                p["holder"], p["hand"] = e["who"], e["hand"]
                self.people[e["who"]].hold(e["hand"], p["root"])

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
        on_person = e["target"] not in self.props
        shoulder = self._in_their_terms(who, (SHOULDER[0] if p.get("hand") == "R" else -SHOULDER[0], SHOULDER[1], SHOULDER[2]))
        swing = not on_person and bool(self.props[e["target"]].get("thing"))     # a tree, a wall: it lands on the side facing them
        fingers = Vector((0, 0, -1))
        if swing:
            touch = self._side_facing(e["target"], along, shoulder)
            toward = Vector((shoulder.x - touch.x, shoulder.y - touch.y, 0)).normalized()
            # upright at the moment it lands, the way a hammer meets a wall: its front (-y) flat on the surface
            points, fingers = (UP + -toward * 0.15).normalized(), toward
            offset = _axes(points, fingers) @ self._working_end(p, reach)
            palm_end = touch - offset
        else:
            touch = (self.aim(e["target"]) if on_person else self._surface(e["target"], along)) + UP * edge
            points = (touch - shoulder).normalized()
            palm_end = touch - points * reach
        if (palm_end - shoulder).length > UPPER_ARM + FOREARM + 0.08:
            raise ValueError(f"strike: {who} stands too far from {e['target']} to reach it: the hand would have to be "
                             f"{(palm_end - shoulder).length:.2f} m from the shoulder. Stand closer")
        if swing:                    # cocked back from the wrist: any further and the handle goes through them
            high_palm = palm_end + toward * 0.02 + UP * 0.1
            high = (UP + toward * 0.4).normalized()
        else:
            high_palm = palm_end.lerp(shoulder + UP * 0.34, 0.65)
            high = (points + UP * 1.8).normalized()
        p.setdefault("path", []).append({"from": hit - over, "to": hit, "palm0": high_palm, "points0": high,
                                         "palm1": palm_end, "points1": points, "fingers": fingers})
        p["start"] = (high_palm, high, fingers)
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

    def _rock(self, e: dict) -> None:
        """A whole thing drawing back and snapping to where it stood, about a place on it: speeding up into each snap, as a
        peck or a hammer does. It ends where it started."""
        cid = e["prop"]
        p = self.props[cid]
        root, thing = p["root"], p["thing"]
        begin = self.frame(e["t"])
        count = max(1, round(e["over"] * self.fps))
        times, back = int(e.get("times", 1)), math.radians(float(e.get("degrees", 20)))
        here, turn = self._place(cid, begin)
        pivot = thing.spot(e["about"]) if e.get("about") else Vector((0, 0, -thing.size.z / 2))
        hinge = here + turn @ pivot
        axis = turn @ ROCK_AXES[e.get("axis", "pitch")]
        track = p.setdefault("track", {})
        for i in range(count + 1):
            f = begin + i
            if f > self.total:
                break
            x = (i / count * times) % 1.0
            if i == count:
                share = 0.0
            elif x < ROCK_BACK:          # easing back
                share = math.sin(x / ROCK_BACK * math.pi / 2)
            else:                        # and snapping home, faster the nearer it gets
                y = (x - ROCK_BACK) / (1 - ROCK_BACK)
                share = 1 - y * y
            tip = Quaternion(axis, -back * share)
            place, turned = hinge + tip @ (here - hinge), tip @ turn
            root.location, root.rotation_quaternion = place, turned
            root.keyframe_insert("location", frame=f)
            root.keyframe_insert("rotation_quaternion", frame=f)
            track[f] = (place.copy(), turned.copy())

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

    def _sparks(self, at: Vector, frame: int, count: int = 26, kind: str = "sparks") -> None:
        """Bright chips thrown from a hit, or chips of what was hit, each falling under gravity on its own arc, in slow motion."""
        rng = random.Random(frame)
        wood = kind == "chips"
        for i in range(count):
            size = (rng.uniform(0.004, 0.014), 0.002, rng.uniform(0.008, 0.03)) if wood else (0.003, 0.003, rng.uniform(0.01, 0.03))
            chip = shapes.box(f"Spark{frame}.{i}", size, "wood" if wood else "spark", at=at)
            velocity = Vector((rng.uniform(-1, 1), rng.uniform(-1, 0.1), rng.uniform(0.15, 1.1))).normalized() * rng.uniform(0.8, 2.6)
            chip.rotation_mode = "QUATERNION"
            chip.rotation_quaternion = UP.rotation_difference(velocity)
            chip.scale = (0, 0, 0)
            chip.keyframe_insert("scale", frame=frame - 1)
            chip.keyframe_insert("location", frame=frame - 1)
            life = rng.randint(22, 40)
            for f in range(frame, frame + life + 1, 2):
                t = (f - frame) / 30.0 * SLOW
                chip.location = at + velocity * t + Vector((0, 0, -9.81)) * (0.5 * t * t)
                s = max(0.0, 1.0 - (f - frame) / life)
                chip.scale = (s, s, s)
                chip.keyframe_insert("location", frame=f)
                chip.keyframe_insert("scale", frame=f)

    def _glow(self, e: dict) -> None:
        person = self.people[e["who"]]
        place = self._on_person(e["who"], e["on"])
        socket = person.glow(place, float(e.get("radius", 0.078)), COLORS[e["color"]])
        begin, end = self.frame(e["t"]), self.frame(e["to"])
        for f, value in ((max(1, begin - 1), 0.0), (begin + 18, 0.75), (end, 1.0)):
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
            elif kind == "flow":
                self._flow(e)
            elif kind == "rings":
                self._clean_rings(e, f, self.aim(e["on"], f), self._facing_shot(e["t"]))
            elif kind == "sparks":
                self._sparks(self.aim(e["on"], f), f, kind=e.get("kind", "sparks"))
            elif kind == "play":
                end = self.frame(e["to"]) if "to" in e else self.total + 1
                self.props[e["prop"]]["thing"].play(f, end, e["move"], float(e.get("speed", 1.0)))
            elif kind == "move":
                p = self.props[e["prop"]]
                palm, points, fingers = self._grip(p["holder"], p["hand"], e["grip"])
                over = max(1, round(e["over"] * self.fps))
                p.setdefault("path", []).append({"from": f, "to": f + over, "palm1": palm, "points1": points, "fingers": fingers})

    def _key_props(self) -> None:
        """Each moving prop, frame by frame: it speeds up into a strike, and bounces off it, slowly."""
        for p in self.props.values():
            if p.get("bitten") or not p.get("path"):
                continue
            root = p["root"]
            palm, points, fingers = p.get("start") or (p["palm"], p["points"], p["fingers"])
            for f in range(1, self.total + 1):
                now_palm, now_points = palm, points
                for leg in p["path"]:
                    if f >= leg["to"]:
                        palm, points, fingers = leg["palm1"], leg["points1"], leg.get("fingers", fingers)
                        now_palm, now_points = palm, points
                        if "palm0" in leg:
                            lift = 1 - math.exp(-(f - leg["to"]) / 16.0)
                            now_palm = palm + UP * (0.05 * lift)
                            now_points = (points + UP * (0.16 * lift)).normalized()
                    elif f > leg["from"]:
                        t = (f - leg["from"]) / (leg["to"] - leg["from"])
                        start_palm, start_points = leg.get("palm0", palm), leg.get("points0", points)
                        t = t * t * t if "palm0" in leg else t * t * (3 - 2 * t)
                        now_palm, now_points = start_palm.lerp(leg["palm1"], t), start_points.slerp(leg["points1"], t).normalized()
                        break
                root.location = now_palm
                root.rotation_quaternion = _axes(now_points, fingers)
                root.keyframe_insert("location", frame=f)
                root.keyframe_insert("rotation_quaternion", frame=f)
                p.setdefault("track", {})[f] = (now_palm.copy(), root.rotation_quaternion.copy())

    def _blinks(self) -> None:
        rng = random.Random(4)
        for person in self.people.values():
            f = rng.randint(12, 40)
            while f < self.total - 8:
                person.blink(f)
                f += rng.randint(70, 130)

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
            final = on + (at - on) * (1 - float(s.get("push", 0.0))) + Vector(s.get("drift", (0, 0, 0)))
            look.key(cam, begin, location=at)
            look.key(cam, end, location=final)
            if s.get("follow"):            # it travels with what it's on, so that stays put in the picture
                for f in range(begin, end + 1):
                    here = self.aim(s["on"], f)
                    look.key(target, f, location=here)
                    look.key(cam, f, location=here + (at - on) + (final - at) * ((f - begin) / max(1, end - begin)))
            look.ease(cam, "LINEAR")
            self.bl.timeline_markers.new(f"Shot{begin}", frame=begin).camera = cam
            self.cuts.append({"t": s["t"], "begin": begin, "end": end - 1, "camera": cam, "aim": target, "frame": s["frame"],
                              "on": s["on"].partition(":")[0]})
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
        moving = {cid for cid, p in self.props.items() if p.get("track")}
        names = list(self.props) + list(self.people) + (["the set"] if self.solids else [])
        kept: dict[str, bounds.Solid] = {}
        deepest: dict[frozenset, tuple] = {}
        frames = sorted({*range(1, self.total + 1, CHECK_EVERY if moving else max(self.total, 1)), self.total})
        for f in frames:
            self.bl.frame_set(f)
            bpy.context.view_layer.update()
            people_now = (f - 1) % PERSON_EVERY == 0 or f == self.total
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
            if c.get("floats") or c.get("on") or c.get("to") or p.get("holder") or travels or self.spec["set"] not in (*FLOORED, "sky_counter"):
                continue
            mine = others[cid]
            if self.spec["set"] in FLOORED and abs(mine.low.z) < TOUCHING:
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
            f = (cut["begin"] + cut["end"]) // 2
            self.bl.frame_set(f)
            bpy.context.view_layer.update()
            lens, aim = cut["camera"].matrix_world.translation.copy(), cut["aim"].matrix_world.translation.copy()
            if self.solids and lens.z < self._solid_of("the set").high.z:
                out.append(f"the shot at {cut['t']} s has its lens under the counter")
            way = aim - lens
            right = way.cross(UP).normalized()
            over = right.cross(way).normalized()
            reach = float(cut["frame"]) * 0.08
            subject = cut["on"]
            for cid in [*self.props, *self.people]:
                if cid == subject or not self._shown(cid, f) or (self.props.get(cid) or {}).get("worn"):
                    continue
                solid = self._solid_of(cid)
                if solid.tree is None:
                    continue
                if all(solid.low[i] <= lens[i] <= solid.high[i] for i in range(3)) and solid.ray(lens, way.normalized()):
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

    def check_physics(self) -> None:
        problems = self._crossings() + self._hanging() + self._blocked()
        self.bl.frame_set(1)
        if problems:
            raise Refused(problems)

    def run(self) -> dict:
        self.solids = getattr(envs, self.spec["set"])() or []
        self.build_people()
        self.build_props()
        self.settle()
        # stand everyone first, so what's placed on their body is placed where it ends up. A blow's knock is added after,
        # when the strike is worked out; playing the stance again with it replaces those keys
        self._key_people()
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
        if any(self.knocks.values()):
            self._key_people()
        self._key_props()
        self._act()
        self._blinks()
        if self.people:
            lead = next(iter(self.people.values()))
            envs.portrait_lights(lead.middle(lead.eyes), key=130.0, fill=60.0, rim=70.0)
        elif self.props and not self.solids:
            envs.portrait_lights(next(iter(self.props.values()))["palm"], key=130.0, fill=60.0, rim=70.0)
        for p in self.props.values():
            if p.get("thing"):
                p["thing"].finish()
        spinning = any(e["do"] == "spin" for e in self.events)
        self.bl.render.motion_blur_shutter = 0.5 if spinning else 0.25
        self.bl.eevee.motion_blur_steps = 4 if spinning else 1      # a turn's blur follows the arc, in that many straight steps
        if any(e["do"] in ("flow", "rings", "strike", "lit", "aura") for e in self.events):
            look.halo(self.bl, threshold=1.7, strength=0.5, size=0.6)
        self._shots()
        self.check_physics()
        return {"frames": self.total, "anchors": {}, "events": self._sound_cues()}

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
        return cues


def run(job: dict, fps: int) -> dict:
    """A scene staged, or refused: what's wrong goes in refused.json beside its frames, so whoever's filming can read it in full."""
    try:
        return Stage(job["scene"], job["folders"], job["catalog"], fps, job.get("things")).run()
    except Refused as e:
        (Path(job["out"]) / "refused.json").write_text(json.dumps(e.problems, indent=1), encoding="utf-8")
        raise

"""The stick-figure skeleton: proportions, poses, movement cycles, and where every joint is.

A figure hangs from its hip (the root): a torso stroke up to the neck, the painted head on the neck, arms
from the shoulder, legs from the hip, in the style of the channel's character reference (thick black sticks,
mitten hands, no feet). Every length is a fraction of H, the figure's standing height in pixels, so one pose
draws at any depth of a stage. Angles are degrees: limbs from straight down and the torso from straight up,
positive toward the way the figure faces, so a pose is written once for a figure facing right and mirrored
for one facing left.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, fields, replace

TORSO, SHOULDER_DROP = 0.38, 0.08          # hip to neck; neck to where the arms start
UPPER_ARM = FOREARM = 0.14
THIGH = SHIN = 0.17
STROKE = 0.022                             # the sticks' width
HEIGHTS = {"head": 0.27, "head_side": 0.27, "scarf": 0.18, "shirt": 0.42, "hand": 0.085, "cane": 0.40,
           "brace": 0.15}  # painted parts
SLOTS = {"head": "head", "head_side": "head_side", "scarf": "neck", "shirt": "neck", "hand": "hand", "cane": "cane",
         "brace": "r_knee"}
STRIDE = 0.46                              # ground one walk cycle (two steps) covers, in H
LIMBS = ("l_upper", "l_fore", "r_upper", "r_fore", "l_thigh", "l_shin", "r_thigh", "r_shin")


@dataclass(frozen=True)
class Pose:
    torso: float = 0.0          # lean from upright
    head: float = 0.0           # tilt on top of the torso's lean
    l_upper: float = -8.0
    l_fore: float = -10.0
    r_upper: float = 8.0
    r_fore: float = 6.0
    l_thigh: float = -9.0
    l_shin: float = -9.0
    r_thigh: float = 9.0
    r_shin: float = 9.0
    cane: float | None = None   # the cane's angle from straight down, held in the right hand; None = not held
    bob: float = 0.0            # the whole figure lifted (+) or dipped (-), in H


NUMBERS = tuple(f.name for f in fields(Pose) if f.name != "cane")


def smooth(t: float) -> float:
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)


def blend(a: Pose, b: Pose, t: float) -> Pose:
    """`a` at t=0, `b` at t=1, straight in between (ease with smooth() first)."""
    t = min(1.0, max(0.0, t))
    values = {name: getattr(a, name) + (getattr(b, name) - getattr(a, name)) * t for name in NUMBERS}
    if a.cane is None or b.cane is None:
        values["cane"] = a.cane if t < 0.5 else b.cane
    else:
        values["cane"] = a.cane + (b.cane - a.cane) * t
    return Pose(**values)


def cycle(keys: list[tuple[float, Pose]], phase: float) -> Pose:
    """The pose at `phase` (0 to 1, wrapping) of a movement cycle given as (phase, pose) keyframes."""
    phase %= 1.0
    keys = sorted(keys)
    for i, (at, pose) in enumerate(keys):
        nxt_at, nxt = keys[(i + 1) % len(keys)]
        span = (nxt_at - at) % 1.0 or 1.0
        if (phase - at) % 1.0 < span:
            return blend(pose, nxt, smooth(((phase - at) % 1.0) / span))
    return keys[0][1]


def _dir(angle: float, facing: int, up: bool = False) -> tuple[float, float]:
    a = math.radians(angle)
    return (math.sin(a) * facing, -math.cos(a) if up else math.cos(a))


def joints(pose: Pose, H: float, root: tuple[float, float], facing: int = 1) -> dict:
    """Pixel positions of every joint for a figure of height H whose hip is at `root`, facing right (1) or
    left (-1). Also `rot`: the on-screen rotation (PIL degrees) each slot's painted part is drawn with."""
    rx, ry = root
    ry -= pose.bob * H

    def at(start, angle, length, up=False):
        dx, dy = _dir(angle, facing, up)
        return (start[0] + dx * length * H, start[1] + dy * length * H)

    hip = (rx, ry)
    neck = at(hip, pose.torso, TORSO, up=True)
    shoulder = at(hip, pose.torso, TORSO - SHOULDER_DROP, up=True)
    j = {"hip": hip, "neck": neck, "shoulder": shoulder}
    for side in ("l", "r"):
        elbow = at(shoulder, getattr(pose, f"{side}_upper"), UPPER_ARM)
        j[f"{side}_elbow"], j[f"{side}_hand"] = elbow, at(elbow, getattr(pose, f"{side}_fore"), FOREARM)
        knee = at(hip, getattr(pose, f"{side}_thigh"), THIGH)
        j[f"{side}_knee"], j[f"{side}_foot"] = knee, at(knee, getattr(pose, f"{side}_shin"), SHIN)
    if pose.cane is not None:
        j["cane_top"] = j["r_hand"]
        j["cane_tip"] = at(j["r_hand"], pose.cane, HEIGHTS["cane"])
    j["rot"] = {"head": -(pose.torso + pose.head) * facing, "neck": -pose.torso * facing,
                "l_hand": pose.l_fore * facing, "r_hand": pose.r_fore * facing,
                "l_knee": pose.l_shin * facing, "r_knee": pose.r_shin * facing,
                "cane": (pose.cane or 0.0) * facing}
    return j


def ground(pose: Pose, H: float) -> float:
    """How far the lowest point of the legs is below the hip, so the figure can be stood on a floor line."""
    j = joints(replace(pose, bob=0.0), H, (0.0, 0.0), 1)
    return max(j[k][1] for k in ("l_foot", "r_foot", "l_knee", "r_knee"))


# --- poses: written for a figure facing right; the cane, when held, is in the right hand ----------

STAND = Pose(torso=2, l_upper=-6, l_fore=-10, r_upper=22, r_fore=-4, l_thigh=-8, l_shin=-8, r_thigh=6, r_shin=6,
             cane=3)
STAND_FREE = replace(STAND, r_upper=8, r_fore=6, cane=None)
LOOK_DOWN = replace(STAND, torso=12, head=16, r_upper=30, r_fore=-6, cane=6)
REACH = Pose(torso=6, head=2, l_upper=70, l_fore=62, r_upper=78, r_fore=70, l_thigh=-8, l_shin=-8, r_thigh=8,
             r_shin=8)                                                     # both hands out in front, chest high
KNEEL = Pose(torso=18, head=12, l_upper=24, l_fore=66, r_upper=36, r_fore=14, l_thigh=-6, l_shin=-98,
             r_thigh=60, r_shin=60, cane=18)                               # on the left knee, the braced leg out
KNEEL_WORK = replace(KNEEL, head=22, l_upper=60, l_fore=58, r_upper=72, r_fore=64, cane=None)  # both hands at work ahead
KNEEL_PRESS = replace(KNEEL, torso=26, head=18, l_upper=48, l_fore=88, r_upper=56, r_fore=92, cane=None)  # leaning on them
SIT = Pose(torso=6, head=8, l_upper=28, l_fore=48, r_upper=34, r_fore=44, l_thigh=76, l_shin=88, r_thigh=68,
           r_shin=80, cane=None)                                           # on the floor, legs out in front
SIT_KNEE_UP = replace(SIT, torso=10, head=14, r_thigh=112, r_shin=4, r_upper=42, r_fore=30, l_upper=20,
                      l_fore=40)                                            # the braced knee drawn up, foot flat
POSES = {"stand": STAND, "stand_free": STAND_FREE, "look_down": LOOK_DOWN, "reach": REACH, "kneel": KNEEL,
         "kneel_work": KNEEL_WORK, "kneel_press": KNEEL_PRESS, "sit": SIT, "sit_knee_up": SIT_KNEE_UP}
LIMP = [  # the braced right leg stays straight and takes a short step; the body dips when it lands; the cane plants with it
    (0.00, Pose(torso=6, head=3, r_thigh=18, r_shin=18, l_thigh=-22, l_shin=-40, r_upper=28, r_fore=10, cane=2,
                l_upper=-18, l_fore=-30, bob=-0.01)),
    (0.25, Pose(torso=10, head=4, r_thigh=2, r_shin=2, l_thigh=-2, l_shin=-55, r_upper=8, r_fore=0, cane=-4,
                l_upper=0, l_fore=-25, bob=-0.035)),
    (0.50, Pose(torso=4, head=0, l_thigh=26, l_shin=24, r_thigh=-18, r_shin=-22, l_upper=20, l_fore=10,
                r_upper=-10, r_fore=-15, cane=25, bob=0.0)),
    (0.75, Pose(torso=5, head=2, l_thigh=4, l_shin=2, r_thigh=-4, r_shin=-12, l_upper=4, l_fore=0,
                r_upper=12, r_fore=5, cane=15, bob=0.015)),
]
WALK = [  # an even walk, no cane
    (0.00, Pose(torso=3, r_thigh=24, r_shin=22, l_thigh=-22, l_shin=-42, r_upper=-18, r_fore=-24, l_upper=22,
                l_fore=14, bob=0.0)),
    (0.25, Pose(torso=4, r_thigh=4, r_shin=2, l_thigh=-4, l_shin=-56, r_upper=-2, r_fore=-14, l_upper=4,
                l_fore=4, bob=0.012)),
    (0.50, Pose(torso=3, l_thigh=24, l_shin=22, r_thigh=-22, r_shin=-42, l_upper=-18, l_fore=-24, r_upper=22,
                r_fore=14, bob=0.0)),
    (0.75, Pose(torso=4, l_thigh=4, l_shin=2, r_thigh=-4, r_shin=-56, l_upper=-2, l_fore=-14, r_upper=4,
                r_fore=4, bob=0.012)),
]
CYCLES = {"limp": LIMP, "walk": WALK}

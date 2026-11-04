"""Phase 32's look test (CHARACTERS.md): one person in a close-up, built by hand to judge the face, skin and hair
before anything is built on them. A blink and a glance, then a prop rises to the mouth, the jaw opens and bites it, and
the eyes go wide.

A shot returns its anchors and events as blender/looktest.py's do.
"""
from __future__ import annotations

import math
import random

import bpy
from mathutils import Vector

from blender import envs, look, people, shapes

PERSON: str = ""   # the folder of the saved person, set by run.py


def _handle(holder):
    """A long corded grip running out of the picture one way, then a guard and a blade the other, built along the
    holder's z with its origin at the bite."""
    rng = random.Random(3)
    shapes.cylinder("Grip", 0.0105, 0.85, "rubber", at=(0, 0, -0.75), segments=24, parent=holder)   # dark in the gaps
    turns = int(0.85 / 0.0048)
    for i in range(turns):                 # cord wound turn against turn, a little uneven as hand-wound cord is
        wrap = shapes.torus(f"Wrap{i}", 0.0108, 0.0028, "cord", at=(0, 0, -0.75 + i * 0.0048), axis="Z", segments=20,
                            ring=6, parent=holder)
        wrap.rotation_euler = (rng.uniform(-0.09, 0.09), rng.uniform(-0.09, 0.09), 0)
    shapes.cylinder("Collar", 0.0135, 0.016, "bright_steel", at=(0, 0, 0.095), segments=32, parent=holder)
    shapes.cylinder("Guard", 0.029, 0.004, "black_steel", at=(0, 0, 0.111), bevel=0.001, parent=holder)
    shapes.torus("GuardRim", 0.029, 0.0028, "copper", at=(0, 0, 0.113), axis="Z", parent=holder)
    shapes.box("Blade", (0.016, 0.004, 0.6), "bright_steel", at=(0, 0, 0.415), bevel=0.001, parent=holder)


def portrait(fps: int) -> dict:
    envs.sky_set()
    scene = bpy.context.scene
    person = people.Person(PERSON)
    eyes = person.middle(person.eyes)
    envs.portrait_lights(eyes)
    # the reference's framing: the eyes a little above the middle, the shoulders along the bottom. About 0.6 m of
    # picture at the lens's 24 mm sensor height, pushed in slowly
    lens = 85.0
    near, far = 0.62 * lens / 24, 0.67 * lens / 24
    aim = eyes - Vector((0, 0, 0.035))
    cam, target = look.camera(scene, (eyes.x, eyes.y - far, eyes.z), aim, lens=lens, fstop=2.8)
    look.key(cam, 1, location=cam.location.copy())
    look.key(cam, 120, location=Vector((eyes.x, eyes.y - near, eyes.z)))
    look.ease(cam, "LINEAR")

    # a touch of open-eyed interest from the start: at rest the add-on's faces read as a slight frown
    rest = {"eyeWide_L": 0.15, "eyeWide_R": 0.15, "browOuterUp_L": 0.3, "browOuterUp_R": 0.3, "browInnerUp": 0.2}
    person.face(1, strict=False, jawOpen=0.0, mouthLowerDown_L=0.0, mouthLowerDown_R=0.0, mouthUpperUp_L=0.0,
                mouthUpperUp_R=0.0, **rest)
    person.gaze(1)
    person.blink(18)
    person.gaze(30)                      # a glance aside and back
    person.gaze(36, x=0.8, y=0.15)
    person.gaze(48, x=0.8, y=0.15)
    person.gaze(54)
    person.face(58, strict=False, jawOpen=0.0, mouthLowerDown_L=0.0, mouthLowerDown_R=0.0, mouthUpperUp_L=0.0,
                mouthUpperUp_R=0.0, **rest)
    # stunned, not snarling: a dropped jaw with relaxed lips. Pulling the upper lip up bares the teeth like a growl
    wide = {"mouthLowerDown_L": 0.7, "mouthLowerDown_R": 0.7, "mouthUpperUp_L": 0.25, "mouthUpperUp_R": 0.25,
            "mouthFunnel": 0.15}
    person.face(58, strict=False, mouthFunnel=0.0)
    person.face(70, strict=False, jawOpen=1.0, browInnerUp=0.7, **wide)
    person.face(84, strict=False, jawOpen=1.0, **wide)
    person.face(92, strict=False, jawOpen=0.85, **wide)   # the bite
    person.face(90, strict=False, eyeWide_L=0.15, eyeWide_R=0.15, browOuterUp_L=0.3, browOuterUp_R=0.3)
    person.face(97, strict=False, eyeWide_L=0.6, eyeWide_R=0.6, browOuterUp_L=0.8, browOuterUp_R=0.8, browInnerUp=0.9)
    person.gaze(90)
    person.gaze(97, x=-0.25, y=0.7)      # looking up and aside, as if asking how this happened
    person.blink(112)

    bite = person.mouth() - Vector((0, 0, 0.019))    # the jaw swings down, so an open mouth sits below a shut one
    holder = person.attach("head", bite, "Mouth")
    prop = bpy.data.objects.new("Prop", None)
    scene.collection.objects.link(prop)
    prop.parent = holder
    # along the picture's width, turned a little so the guard's face shows and the blade end goes away from the camera
    prop.rotation_euler = (0, math.radians(90), math.radians(14))
    _handle(prop)
    below = Vector((0, -0.16, -0.5))                 # out of the picture, nearer the camera: it rises past the chin
    look.key(prop, 1, location=below)
    look.key(prop, 62, location=below)
    look.key(prop, 86, location=Vector((0, -0.02, 0)))
    look.key(prop, 92, location=Vector((0, -0.002, 0)))
    look.ease(prop, "BEZIER")
    return {"frames": 120, "anchors": {"mouth": (holder, (0, 0, 0))}, "events": [{"frame": 92, "kind": "bite"}]}


SHOTS = {"portrait": portrait}

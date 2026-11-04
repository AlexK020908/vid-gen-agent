"""One segment of a machine short, from its timeline: the set, the machines placed in it, keys at given seconds
(steps, joints, visibility, scale, place), the camera's keys, the cutaways' times and the effects. Rendered frame
by frame, with the anchors' screen tracks for the overlays.

A timeline (JSON, written by hand for A's rebuild, by Claude later):
  from, to       seconds of the whole short this segment covers; frames are numbered for the whole short
  env            a set from blender/envs.py, with env_args
  models         id -> {spec, at, rot (degrees about z, or [x, y, z]), scale, step, parent ("model.part" it
                 hangs from, placed in that part's space), hide (parts hidden from the start)}
  people         id -> {person (a character's id), at, rot (degrees about z)}. "id:eyes", "id:mouth" and "id:head" are
                 points a camera or an anchor can follow
  keys           [{t, ease, step: {model: n}, joints: {"model.part": value}, show: {"model.part" or "model": bool},
                  scale: {model: s}, place: {model: {at, rot}}}]
  camera         [{t, ease, target: [x, y, z] or "model:anchor" or "model.part", offset, az, el, frame, x, y, lens,
                  roll, fstop, fast}] or with at and aim given directly; `fast` marks a deliberate quick move (a dive
                  into a flash) that render/shot_checks.py's camera check lets pass
  cuts           [{model, from, to, y, hatch, material, x_range, parts}]: x_range cuts a notch that wide
  effects        [{kind, ...}] (blender/effects.py)
  anchors        names "model:anchor" whose screen positions go to tracks.json
  events         [{t, kind}] for the sound

ease says how a move arrives at its key: inout (the default: smooth), linear, in (speeding up into it, a fall),
out (slowing into it, a rise or a stop), const (holding, then a jump at the key).
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import bpy
from mathutils import Euler, Vector

from blender import effects, envs, kit, look, materials, people, shapes, tracks

EASE = {"linear": ("LINEAR", "AUTO"), "in": ("QUAD", "EASE_IN"), "out": ("QUAD", "EASE_OUT"),
        "inout": ("BEZIER", "AUTO"), "const": ("CONSTANT", "AUTO"), "fall": ("QUAD", "EASE_IN"),
        "rise": ("QUAD", "EASE_OUT"), "whip": ("SINE", "EASE_IN_OUT")}


class Segment:
    def __init__(self, timeline: dict, specs: dict, fps: int, people_folders: dict | None = None):
        self.tl, self.fps = timeline, fps
        self.people_folders = people_folders or {}
        self.cast: dict[str, people.Person] = {}
        self.f0 = self.frame(timeline["from"])
        self.f1 = self.frame(timeline["to"]) - 1
        self.models: dict[str, kit.Model] = {}
        self.roots: dict[str, bpy.types.Object] = {}
        self.eases: list[tuple[bpy.types.Object, int, int, str]] = []   # (object, from frame, to frame, ease)
        self.specs = specs
        self.fx_anchors: dict[str, tuple] = {}   # "fx:name" anchors on effects (an air ball, the gas column)

    def frame(self, t: float) -> int:
        return round(t * self.fps)

    # --- the set and the machines -------------------------------------------------------------------------------

    def build(self):
        env = getattr(envs, self.tl.get("env", "studio"))
        env(**(self.tl.get("env_args") or {}))
        for pid, p in (self.tl.get("people") or {}).items():
            self.cast[pid] = people.Person(self.people_folders[p["person"]], at=p.get("at", (0, 0, 0)), rot=p.get("rot", 0))
        for mid, m in (self.tl.get("models") or {}).items():
            root = bpy.data.objects.new(f"{mid}.root", None)
            bpy.context.scene.collection.objects.link(root)
            if m.get("parent"):           # hung from another machine's part, built before it
                root.parent = self.resolve(m["parent"])[0]
            _place(root, m)
            model = kit.Model(self.specs[m["spec"]], prefix=f"{mid}.", root=root)
            model.show_step(int(m.get("step", 1)), frame=self.f0)
            for pid in m.get("hide") or []:
                _key_hidden(model.objects[pid], True, self.f0)
            self.models[mid], self.roots[mid] = model, root
            look.key(root, self.f0, location=root.location.copy(), rotation_euler=root.rotation_euler.copy(),
                     scale=root.scale.copy())

    def resolve(self, name: str):
        """'model:anchor' -> (object, offset); 'model.part' -> (object, (0, 0, 0)); 'model' -> its root;
        'fx:name' -> an effect's anchor."""
        if name.startswith("fx:"):
            return self.fx_anchors[name[3:]]
        if name.startswith("at:"):        # a fixed point in the world, "at:x,y,z" (where a pile's tip was)
            if name not in self.fx_anchors:
                point = bpy.data.objects.new(name, None)
                bpy.context.scene.collection.objects.link(point)
                point.location = Vector([float(v) for v in name[3:].split(",")])
                self.fx_anchors[name] = (point, (0, 0, 0))
            return self.fx_anchors[name]
        if ":" in name:
            mid, anchor = name.split(":", 1)
            if mid in self.cast:
                return self.cast[mid].anchor(anchor)
            return self.models[mid].anchor(anchor)
        if "." in name:
            mid, pid = name.split(".", 1)
            return self.models[mid].objects[pid], (0, 0, 0)
        return self.roots[name], (0, 0, 0)

    def point(self, target, offset=(0, 0, 0)) -> Vector:
        if isinstance(target, str):
            obj, off = self.resolve(target)
            p = obj.matrix_world @ Vector(off)
        else:
            p = Vector(target)
        return p + Vector(offset)

    # --- keys -------------------------------------------------------------------------------------------------

    def keys(self):
        prev: dict[str, int] = {}          # channel -> its last key's frame, so a key's ease shapes the move into it
        for key in sorted(self.tl.get("keys") or [], key=lambda k: k["t"]):
            f, ease = self.frame(key["t"]), key.get("ease", "inout")
            for mid, step in (key.get("step") or {}).items():
                self.models[mid].show_step(int(step), frame=f)
            for name, value in (key.get("joints") or {}).items():
                mid, pid = name.split(".", 1)
                model = self.models[mid]
                model.set(pid, float(value), frame=f)
                for moved in [pid] + [c["driven"] for c in model.spec.get("couple") or [] if c["driver"] == pid]:
                    self._eased(model.objects[moved], prev, f"{mid}.{moved}", f, ease)
            for name, shown in (key.get("show") or {}).items():
                if name in self.models:   # a whole machine, its helpers always hidden
                    model = self.models[name]
                    objs = [o for p, o in model.objects.items() if not model.parts[p].get("helper")]
                else:
                    objs = [self.resolve(name)[0]]
                for obj in objs:
                    _key_hidden(obj, not shown, f)
            for mid, s in (key.get("scale") or {}).items():
                root = self.roots[mid]
                look.key(root, f, scale=Vector((s, s, s)) if not isinstance(s, list) else Vector(s))
                self._eased(root, prev, f"{mid}.root", f, ease)
            for mid, place in (key.get("place") or {}).items():
                root = self.roots[mid]
                _place(root, place)
                look.key(root, f, location=root.location.copy(), rotation_euler=root.rotation_euler.copy())
                self._eased(root, prev, f"{mid}.root", f, ease)

    def _eased(self, obj, prev, channel, f, ease):
        if channel in prev and prev[channel] < f:
            self.eases.append((obj, prev[channel], f, ease))
        prev[channel] = f

    def apply_eases(self):
        """Interpolation lives on a move's first key: set each one by the ease of the key it moves to."""
        for obj, a, b, ease in self.eases:
            kind, easing = EASE.get(ease, EASE["inout"])
            anim = obj.animation_data
            if not anim or not anim.action:
                continue
            for curve in look._fcurves(anim.action):
                if curve.data_path.startswith("hide"):
                    continue
                for point in curve.keyframe_points:
                    if round(point.co.x) == a:
                        point.interpolation = kind
                        point.easing = easing

    # --- the camera -----------------------------------------------------------------------------------------------

    def camera(self, scene):
        rig = bpy.data.objects.new("CameraRig", None)
        scene.collection.objects.link(rig)
        aim = bpy.data.objects.new("CameraAim", None)
        scene.collection.objects.link(aim)
        track = rig.constraints.new("TRACK_TO")
        track.target, track.track_axis, track.up_axis = aim, "TRACK_NEGATIVE_Z", "UP_Y"
        data = bpy.data.cameras.new("Camera")
        data.sensor_fit, data.sensor_height = "VERTICAL", 24.0
        data.clip_start, data.clip_end = 0.01, 3000.0
        data.dof.use_dof = True
        cam = bpy.data.objects.new("Camera", data)
        scene.collection.objects.link(cam)
        cam.parent = rig                           # the camera rolls about its own view axis on the rig
        scene.camera = cam
        prev = None
        for key in sorted(self.tl.get("camera") or [], key=lambda k: k["t"]):
            f = self.frame(key["t"])
            scene.frame_set(max(self.f0, min(self.f1, f)))
            lens = float(key.get("lens", 35))
            if "at" in key:
                at, target = Vector(key["at"]), Vector(key["aim"])
                dist = (target - at).length
            else:
                target = self.point(key["target"], key.get("offset", (0, 0, 0)))
                az, el = math.radians(key.get("az", 0)), math.radians(key.get("el", 5))
                back = Vector((math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el)))
                frame_h = float(key.get("frame", 3.0))
                dist = frame_h / (2 * (12 / lens))
                at = target + back * dist
                forward = -back
                up = Vector((0, 0, 1)) if abs(forward.z) < 0.99 else Vector((0, 1, 0))
                right = forward.cross(up).normalized()
                up = right.cross(forward).normalized()
                # put the target at (x, y) of the picture by aiming beside it
                target = (target + up * (float(key.get("y", 0.5)) - 0.5) * frame_h
                          + right * (0.5 - float(key.get("x", 0.5))) * frame_h * 9 / 16)
            look.key(rig, f, location=at)
            look.key(aim, f, location=target)
            cam.rotation_euler = (0, 0, math.radians(key.get("roll", 0)))
            cam.keyframe_insert("rotation_euler", frame=f)
            data.lens = lens
            data.keyframe_insert("lens", frame=f)
            # the nearest clip the shot allows: 0.01 m in a wide desert shot left the depth too coarse far off, and
            # surfaces close together flickered as they swapped (nothing in a shot comes within 1/300 of its distance)
            data.clip_start = min(0.5, max(0.005, dist / 300))
            data.keyframe_insert("clip_start", frame=f)
            data.dof.focus_distance = float(key.get("focus", dist))
            data.dof.aperture_fstop = float(key.get("fstop", 8))
            data.dof.keyframe_insert("focus_distance", frame=f)
            data.dof.keyframe_insert("aperture_fstop", frame=f)
            if prev is not None:
                for obj in (rig, aim, cam):
                    self.eases.append((obj, prev, f, key.get("ease", "inout")))
                self._ease_data(data, prev, key.get("ease", "inout"))
            prev = f
        return cam

    def _ease_data(self, data, a, ease):
        kind, easing = EASE.get(ease, EASE["inout"])
        for owner in (data,):
            anim = owner.animation_data
            if anim and anim.action:
                for curve in look._fcurves(anim.action):
                    for point in curve.keyframe_points:
                        if round(point.co.x) == a:
                            point.interpolation, point.easing = kind, easing

    # --- cutaways -------------------------------------------------------------------------------------------------

    def cuts(self):
        for i, cut in enumerate(self.tl.get("cuts") or []):
            model, root = self.models[cut["model"]], self.roots[cut["model"]]
            parts = cut.get("parts") or [p for p, part in model.parts.items() if part.get("cut")]
            objs = [model.objects[p] for p in parts]
            cutter = shapes.cut_away(objs, keep_y_above=0.0, name=f"Cut{i}", x_range=cut.get("x_range"),
                                     material=cut.get("material") or f"cut:{cut.get('hatch', 0.07)}")
            cutter.parent = root
            middle = 0.0 if not cut.get("x_range") else sum(cut["x_range"]) / 2
            cutter.location = (middle, cut.get("y", 0.0) - 20.0, 0)
            cutter.hide_viewport = True
            on, off = self.frame(cut["from"]), self.frame(cut["to"])
            if on <= self.f0 and off > self.f1:   # on throughout: cut once, not on every frame
                bpy.context.view_layer.update()
                for obj in objs:
                    kit.bake(obj, prefix="Cutaway")
                continue
            for obj in objs:
                mod = obj.modifiers.get("Cutaway")
                if mod is None:
                    continue
                mod.name = f"Cutaway{i}"
                for f, shown in ((self.f0, False), (on, True), (off, False)):
                    mod.show_render = mod.show_viewport = shown and on <= f < off
                    mod.keyframe_insert("show_render", frame=f)
                    mod.keyframe_insert("show_viewport", frame=f)


def _place(root, m: dict) -> None:
    root.location = Vector(m.get("at", (0, 0, 0)))
    rot = m.get("rot", 0)
    root.rotation_euler = Euler([math.radians(a) for a in rot]) if isinstance(rot, list) else Euler(
        (0, 0, math.radians(rot)))
    s = m.get("scale", 1.0)
    root.scale = Vector(s) if isinstance(s, list) else Vector((s, s, s))


def _key_hidden(obj, hidden: bool, f: int) -> None:
    obj.hide_render = hidden
    obj.hide_viewport = hidden
    obj.keyframe_insert("hide_render", frame=f)
    obj.keyframe_insert("hide_viewport", frame=f)


def run(job: dict, out: Path, scene) -> dict:
    fps = int(job.get("fps", 30))
    seg = Segment(job["timeline"], job["specs"], fps, job.get("people"))
    seg.build()
    seg.keys()
    seg.cuts()
    fx = effects.Effects(seg)
    for e in seg.tl.get("effects") or []:
        fx.add(e)
    seg.camera(scene)
    seg.apply_eases()
    scene.frame_start, scene.frame_end = seg.f0, seg.f1
    anchors = {name: seg.resolve(name) for name in seg.tl.get("anchors") or []}
    track = tracks.export(scene, anchors, seg.f0, seg.f1) if anchors else {}
    return {"f0": seg.f0, "f1": seg.f1, "anchors": track,
            "events": [{"frame": seg.frame(e["t"]), "kind": e["kind"]} for e in seg.tl.get("events") or []]}

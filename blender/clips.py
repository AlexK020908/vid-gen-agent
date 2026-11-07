"""Body clips (CC0 packs in data/motion, render/clips.py) played on a person. A clip's skeleton isn't our rig's: it has
other names, proportions and a T-pose where ours stands in an A-pose. So a clip is read as how far each bone turned from
that T-pose, in the world's axes, and each of our bones turns the same way from our rig's own T-pose. Only the hips'
travel is scaled, by leg length, so feet land where they should on any person.

Their bones are in the file's own axes, so a clip is compared only with a reference from the same file: the pack's T-pose
clip, or the mannequin's rest pose. Our rig is at rest here, before any keys, when `Solver` is made.
"""
from __future__ import annotations

import math

import bpy
from mathutils import Quaternion, Vector

# their bone -> ours
BONES = {"pelvis": "spine", "spine_01": "spine.001", "spine_02": "spine.002", "spine_03": "spine.003", "neck_01": "neck",
         "Head": "head"}
for _theirs, _ours in (("l", "L"), ("r", "R")):
    BONES.update({f"clavicle_{_theirs}": f"shoulder.{_ours}", f"upperarm_{_theirs}": f"upper_arm.{_ours}",
                  f"lowerarm_{_theirs}": f"forearm.{_ours}", f"hand_{_theirs}": f"hand.{_ours}",
                  f"thigh_{_theirs}": f"thigh.{_ours}", f"calf_{_theirs}": f"shin.{_ours}",
                  f"foot_{_theirs}": f"foot.{_ours}", f"ball_{_theirs}": f"toe.{_ours}"})
    for _finger, _named in (("index", "f_index"), ("middle", "f_middle"), ("ring", "f_ring"), ("pinky", "f_pinky"),
                            ("thumb", "thumb")):
        for _i in (1, 2, 3):
            BONES[f"{_finger}_0{_i}_{_theirs}"] = f"{_named}.0{_i}.{_ours}"
HIPS, LEG = "pelvis", "thigh_l"


def _import(path: str):
    """A pack's file into the scene. An importer can set the scene's frame rate, so it's put back. Returns its armature
    and everything it brought."""
    scene = bpy.context.scene
    fps, frame = scene.render.fps, scene.frame_current
    before = set(bpy.data.objects)
    if path.lower().endswith(".fbx"):
        bpy.ops.import_scene.fbx(filepath=path, automatic_bone_orientation=False, ignore_leaf_bones=False)
    else:
        bpy.ops.import_scene.gltf(filepath=path)
    scene.render.fps = fps
    scene.frame_set(frame)
    brought = [obj for obj in bpy.data.objects if obj not in before]
    return next(obj for obj in brought if obj.type == "ARMATURE"), brought


def _sample(arm) -> dict:
    """Each mapped bone's rotation and head in the world, as the armature stands now."""
    bpy.context.view_layer.update()
    world = arm.matrix_world
    turn = world.to_quaternion()
    out = {}
    for name in BONES:
        bone = arm.pose.bones.get(name)
        if bone is not None:
            out[name] = (turn @ bone.matrix.to_quaternion(), world @ bone.head, world @ bone.tail)
    return out


def _use_action(arm, action) -> None:
    ad = arm.animation_data or arm.animation_data_create()
    ad.use_nla = False
    ad.action = action
    if getattr(action, "slots", None) and len(action.slots):
        ad.action_slot = action.slots[0]


def _action(name: str | None):
    if name is None:
        return None
    found = [a for a in bpy.data.actions if a.name == name or a.name.endswith(f"|{name}")]
    if not found:
        raise KeyError(f"no clip {name}; the file has {sorted(a.name for a in bpy.data.actions)}")
    return found[0]


def _remove(brought: list) -> None:
    for obj in brought:
        bpy.data.objects.remove(obj, do_unlink=True)


def _reference(arm, action_name: str | None) -> dict:
    """The T-pose to compare a clip with: a clip of it, or the armature's rest pose with its animation out of the way."""
    if action_name:
        action = _action(action_name)
        _use_action(arm, action)
        bpy.context.scene.frame_set(int(action.frame_range[0]))
    else:
        arm.animation_data_clear()
        for bone in arm.pose.bones:
            bone.matrix_basis.identity()
    return _sample(arm)


def read(entry: dict) -> dict:
    """A clip from a catalog entry (render/clips.py): {file, action, reference: {file, action}}. Its frames, each bone's
    rotation away from the reference in the world's axes, the reference's bone directions, and the hips' travel. What
    the file brought into the scene leaves again."""
    scene = bpy.context.scene
    keep = scene.frame_current
    had = set(bpy.data.actions)
    arm, brought = _import(entry["file"])
    action = _action(entry["action"]) if entry.get("action") else arm.animation_data.action
    ref = entry["reference"]
    if ref["file"] == entry["file"]:
        base = _reference(arm, ref.get("action"))
    else:
        ref_arm, ref_brought = _import(ref["file"])
        base = _reference(ref_arm, ref.get("action"))
        brought += ref_brought
    _use_action(arm, action)
    first, last = (int(round(v)) for v in action.frame_range)
    turns: dict[str, list] = {name: [] for name in base}
    hips = []
    for f in range(first, last + 1):
        scene.frame_set(f)
        now = _sample(arm)
        for name, (q, _, _) in now.items():
            if name in turns:
                turns[name].append(q @ base[name][0].inverted())
        hips.append(now[HIPS][1] - base[HIPS][1])
    scene.frame_set(keep)
    _remove(brought)
    for leftover in set(bpy.data.actions) - had:
        bpy.data.actions.remove(leftover)
    return {"frames": last - first + 1, "turns": turns, "hips": hips, "leg": base[LEG][1].z,
            "directions": {name: (tail - head).normalized() for name, (_, head, tail) in base.items()}}


class Solver:
    """Our rig's T-pose, worked out once from its rest pose. It turns a clip's frames into the local rotations to key."""

    def __init__(self, person):
        self.person = person
        self.rig = person.rig
        self.rest: dict[str, Quaternion] = {}
        self.order = []                         # parents before children
        for bone in self.rig.pose.bones:
            self.rest[bone.name] = bone.bone.matrix_local.to_quaternion()
            self.order.append(bone)
        self.order.sort(key=lambda b: len(b.parent_recursive))
        self.ours = {theirs: person.bones[name] for theirs, name in BONES.items() if name in person.bones}
        self.root = person.bone("spine")
        self.leg = person.bone("thigh.L").bone.head_local.z
        self.last: dict[str, Quaternion] = {}   # the pose the last clip ended on, for the next one to fade from
        self.last_root = Vector()

    def _frame(self, clip: dict, at: float) -> dict[str, Quaternion]:
        """Each of our bones' local rotation at `at`, in the clip's frames, between two of them when it's slowed down.
        A bone with no match keeps its place on its parent."""
        i, between = int(at), at - int(at)
        after = min(i + 1, clip["frames"] - 1)
        posed: dict[str, Quaternion] = {}
        theirs_by_ours = {name: theirs for theirs, name in self.ours.items()}
        local: dict[str, Quaternion] = {}
        for bone in self.order:
            name = bone.name
            parent = bone.parent.name if bone.parent else None
            rest_here = self.rest[name]
            rest_on_parent = (self.rest[parent].inverted() @ rest_here) if parent else rest_here
            theirs = theirs_by_ours.get(name)
            if theirs and theirs in clip["turns"] and clip["turns"][theirs]:
                ours_dir = (bone.bone.tail_local - bone.bone.head_local).normalized()
                to_t_pose = ours_dir.rotation_difference(clip["directions"][theirs])
                turns = clip["turns"][theirs]
                wanted = turns[i].slerp(turns[after], between) @ to_t_pose @ rest_here
                above = posed[parent] if parent else Quaternion()
                local[name] = rest_on_parent.inverted() @ above.inverted() @ wanted
                posed[name] = wanted
            else:
                above = posed[parent] if parent else Quaternion()
                posed[name] = above @ rest_on_parent
        return local

    def mirror_fingers(self, pose: dict, closed: str = "R", other: str = "L") -> None:
        """One hand's fingers copied to the other: bones on either side mirror across x, so a local turn mirrors by
        flipping its y and z. The sword clips only close the sword hand."""
        for name, bone in self.person.bones.items():
            if name.endswith(f".{closed}") and name.split(".")[0] in ("f_index", "f_middle", "f_ring", "f_pinky", "thumb"):
                if bone in pose:
                    q = pose[bone]
                    pose[self.person.bones[f"{name[:-1]}{other}"]] = Quaternion((q.w, q.x, -q.y, -q.z))

    def pace(self, clip: dict) -> float:
        """How far a clip's own steps carry this person along the ground in one of its frames: nothing, if it stays on the spot."""
        travel = clip["hips"][-1] - clip["hips"][0]
        return math.hypot(travel.x, travel.y) * self.leg / clip["leg"] / max(1, clip["frames"] - 1)

    def play(self, clip: dict, start: int, frames: int | None = None, blend: int = 6, speed: float = 1.0,
             offset: float = 0, adjust=None, on_the_spot: bool = False, clock=None) -> int:
        """Key `clip` from frame `start`, crossfading from what came before over `blend` frames. `frames` is how long to
        play, looping if it's longer than the clip; `speed` below 1 is slow motion. `adjust(frame, pose)` can change each
        frame's local rotations before they're keyed (a head knocked by a blow). `on_the_spot` takes the clip's travel along
        the ground out of it, keeping the bounce and sway of its steps, for whoever moves the rig to carry them along it, and
        loops it as the cycle it is, whose last frame is its first. `clock(n)` is how many frames' worth of it have gone by n
        frames in, for slow motion partway. Returns the frame after the last."""
        length = frames if frames is not None else int(clip["frames"] / speed)
        scale = self.leg / clip["leg"]
        to_local = self.root.bone.matrix_local.to_quaternion().inverted()
        ended: dict[str, Quaternion] = {}
        period = max(1, clip["frames"] - 1) if on_the_spot else clip["frames"]
        travel = clip["hips"][-1] - clip["hips"][0]
        drift = Vector((travel.x, travel.y, 0)) if on_the_spot else Vector()
        for n in range(length):
            at = ((clock(n) if clock else n) * speed + offset) % period
            i, between = int(at), at - int(at)
            hips = clip["hips"][i].lerp(clip["hips"][min(i + 1, clip["frames"] - 1)], between) - drift * (at / period)
            root = to_local @ (hips * scale)
            mix = 1.0
            if self.last and n < blend:
                t = (n + 1) / (blend + 1)
                mix = t * t * (3 - 2 * t)
            pose = self._frame(clip, at)
            if adjust:
                adjust(start + n, pose)
            for name, q in pose.items():
                if mix < 1.0 and name in self.last:
                    q = self.last[name].slerp(q, mix)
                bone = self.rig.pose.bones[name]
                bone.rotation_mode = "QUATERNION"
                bone.rotation_quaternion = q
                bone.keyframe_insert("rotation_quaternion", frame=start + n)
                ended[name] = q
            if mix < 1.0:
                root = self.last_root.lerp(root, mix)
            self.root.location = root
            self.root.keyframe_insert("location", frame=start + n)
            self.last_root = root.copy()
        self.last = ended
        return start + length

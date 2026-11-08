"""Things, from whatever file they came in (things/get.py): made the right size, stood upright, saved, and placed in a scene
by what they are, so the stage doesn't care where one came from. Each sits under two empties: `root`, which a scene moves
and whose origin is the thing's middle, and `holder`, which sizes and turns what the file brought.

Clips play through the NLA, so a clip can loop, slow down and ease into the next one, on whatever in the file it moves.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Euler, Vector

from blender import envs, kit, look, materials, shapes

EASE_FRAMES = 6     # how long one move takes to ease into the next
LIQUID = "liquid"        # marks a part that is what fills something: blender/bounds.py leaves it out of what's solid
CLEAR = "clear"          # marks a part you see through, such as glass: it isn't in the way of a shot
CLEAR_ENOUGH = 0.8       # how see-through a part's own paint has to be to count
MOST_FACES = 200_000     # a museum scan comes with up to a million: its texture carries the detail, and every check reads every face
VIEWS = (("front", 0, 4), ("three quarter", -38, 10), ("side", 90, 4), ("back", 180, 4), ("from above", 20, 55))
LENS = 60.0


def _import(path: str) -> None:
    low = path.lower()
    if low.endswith(".fbx"):
        bpy.ops.import_scene.fbx(filepath=path, automatic_bone_orientation=False, ignore_leaf_bones=False)
    elif low.endswith((".glb", ".gltf")):
        bpy.ops.import_scene.gltf(filepath=path)
    elif low.endswith(".obj"):
        bpy.ops.wm.obj_import(filepath=path)
    else:
        raise ValueError(f"can't read {path}: only glb, gltf, fbx and obj")


def _brought(before: set) -> list:
    """What the file brought, less its cameras, its lights and the shapes the importer draws bones with."""
    leftovers = bpy.data.collections.get("glTF_not_exported")
    shapes = set(leftovers.objects) if leftovers else set()
    for obj in list(bpy.data.objects):
        if obj not in before and (obj.type in ("CAMERA", "LIGHT") or obj in shapes):
            bpy.data.objects.remove(obj, do_unlink=True)
    return [obj for obj in bpy.data.objects if obj not in before]


def _bounds(meshes: list) -> tuple[Vector, Vector]:
    """The corners of the box around everything as it stands now, posed by its rig."""
    bpy.context.view_layer.update()
    graph = bpy.context.evaluated_depsgraph_get()
    points = []
    for obj in meshes:
        evaluated = obj.evaluated_get(graph)
        points += [evaluated.matrix_world @ Vector(c) for c in evaluated.bound_box]
    return (Vector(tuple(min(p[i] for p in points) for i in range(3))),
            Vector(tuple(max(p[i] for p in points) for i in range(3))))


def _smooth(meshes: list) -> None:
    """Weld a faceted model's split corners, and shade it smooth."""
    done = set()
    for obj in meshes:
        if obj.data in done:
            continue
        done.add(obj.data)
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
        bm.to_mesh(obj.data)
        bm.free()
        obj.data.shade_smooth()


def _fewer_faces(meshes: list) -> None:
    """A heavy scan brought down to MOST_FACES, keeping its shape and how its texture sits on it. Not one with a rig: its bones need
    every face where it is."""
    total = sum(len(obj.data.polygons) for obj in meshes)
    if total <= MOST_FACES or any(m.type == "ARMATURE" for obj in meshes for m in obj.modifiers):
        return
    for obj in meshes:
        bm = bmesh.new()         # a scan can be all loose triangles, which won't simplify until their corners are joined
        bm.from_mesh(obj.data)
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
        bm.to_mesh(obj.data)
        bm.free()
        trim = obj.modifiers.new("fewer", "DECIMATE")
        trim.ratio = MOST_FACES / total
    bpy.context.view_layer.update()
    graph = bpy.context.evaluated_depsgraph_get()
    for obj in meshes:
        made = bpy.data.meshes.new_from_object(obj.evaluated_get(graph))
        obj.modifiers.clear()
        obj.data = made


def _trim(meshes: list, boxes: list) -> None:
    """What's inside each box taken off, such as the stand a museum mounted it on. A box gives a range on any of x, y and z, as shares
    of what it measured to begin with: {"y": [0, 0.5], "z": [0, 0.3]} is the nearer half of the lowest part, all the way across."""
    low, high = _bounds(meshes)
    for box in boxes:
        ranges = [(i, low[i] + (high[i] - low[i]) * box["xyz"[i]][0], low[i] + (high[i] - low[i]) * box["xyz"[i]][1]) for i in range(3) if "xyz"[i] in box]
        for obj in meshes:
            place = obj.matrix_world.copy()
            bm = bmesh.new()
            bm.from_mesh(obj.data)
            doomed = []
            for vert in bm.verts:
                at = place @ vert.co
                if all(a <= at[i] <= b for i, a, b in ranges):
                    doomed.append(vert)
            bmesh.ops.delete(bm, geom=doomed, context="VERTS")
            bm.to_mesh(obj.data)
            bm.free()
            obj.data.update()


def _trim_pale(meshes: list, rules: list) -> None:
    """Faces paler than a brightness taken off, near a place: what's left of a white mount on a bird's toes, which a box would take the toes
    with. Each is {"near": [x, y, z], "radius": meters, "above": 0 to 1}, in meters from its middle, as a spot is. A face's brightness is
    what its picture shows at its corners and middle, and it goes if all of them are paler."""
    bpy.context.view_layer.update()
    for rule in rules:
        near, reach, above = Vector(rule["near"]), float(rule["radius"]), float(rule["above"])
        for obj in meshes:
            layer = obj.data.uv_layers.active
            if layer is None:
                continue
            place = obj.matrix_world
            pixels = {}
            for slot, mat in enumerate(obj.data.materials):
                node = None
                if mat is not None and mat.use_nodes:
                    bsdf = next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
                    if bsdf is not None and bsdf.inputs["Base Color"].links:
                        node = bsdf.inputs["Base Color"].links[0].from_node
                if node is not None and node.type == "TEX_IMAGE" and node.image and node.image.size[0]:
                    w, h = node.image.size
                    pixels[slot] = (np.array(node.image.pixels[:], dtype=np.float32).reshape(h, w, -1), w, h)
            doomed = []
            for poly in obj.data.polygons:
                if poly.material_index not in pixels or (place @ poly.center - near).length > reach:
                    continue
                image, w, h = pixels[poly.material_index]
                uvs = [layer.data[i].uv for i in poly.loop_indices]
                uvs.append(sum(uvs, Vector((0, 0))) / len(uvs))
                pale = True
                for uv in uvs:
                    r, g, b = image[int(uv.y % 1 * (h - 1)), int(uv.x % 1 * (w - 1))][:3]
                    if min(r, g, b) < above:
                        pale = False
                        break
                if pale:
                    doomed.append(poly.index)
            if doomed:
                bm = bmesh.new()
                bm.from_mesh(obj.data)
                bm.faces.ensure_lookup_table()
                bmesh.ops.delete(bm, geom=[bm.faces[i] for i in doomed], context="FACES_ONLY")
                bm.to_mesh(obj.data)
                bm.free()
                obj.data.update()


def _image_size(obj, slot: int) -> tuple[int, int] | None:
    """The size of the picture on a material's color, or None if it isn't from a picture."""
    mats = obj.data.materials
    mat = mats[slot] if slot < len(mats) else None
    if mat is None or not mat.use_nodes:
        return None
    bsdf = next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if bsdf is None or not bsdf.inputs["Base Color"].links:
        return None
    node = bsdf.inputs["Base Color"].links[0].from_node
    return tuple(node.image.size) if node.type == "TEX_IMAGE" and node.image and node.image.size[0] else None


def _texels_per_meter(meshes: list) -> float | None:
    """How many of its texture's pixels lie on a meter of its surface, typically. None if its color doesn't come from a picture."""
    bpy.context.view_layer.update()
    found = []
    for obj in meshes:
        layer = obj.data.uv_layers.active
        if layer is None:
            continue
        place, verts = obj.matrix_world, obj.data.vertices
        polys = obj.data.polygons
        for k in range(0, len(polys), max(1, len(polys) // 3000)):
            poly = polys[k]
            size = _image_size(obj, poly.material_index)
            if not size or len(poly.vertices) != 3:
                continue
            a, b, c = (place @ verts[i].co for i in poly.vertices)
            area = (b - a).cross(c - a).length / 2
            p, q, r = (layer.data[i].uv for i in poly.loop_indices)
            flat = abs((q.x - p.x) * (r.y - p.y) - (r.x - p.x) * (q.y - p.y)) / 2
            if area > 1e-12 and flat > 0:
                found.append(math.sqrt(flat * size[0] * size[1] / area))
    if not found:
        return None
    return round(sorted(found)[len(found) // 2], 1)


def _color(meshes: list, colors: dict) -> list[str]:
    """Paint materials by name, for a model that came grey. Returns every material it has; a name that matches none fails."""
    found = {m.name: m for obj in meshes for m in obj.data.materials if m is not None}
    for name, color in colors.items():
        if name not in found:
            raise ValueError(f"no material called {name}: it has {', '.join(sorted(found))}")
        bsdf = next((n for n in found[name].node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if bsdf is not None:
            for link in list(bsdf.inputs["Base Color"].links):   # a scan's picture would win over the color
                found[name].node_tree.links.remove(link)
            bsdf.inputs["Base Color"].default_value = (*color, 1)
            bsdf.inputs["Roughness"].default_value = 0.7
    return sorted(found)


def _slots(action, objects: list) -> list[list[str]]:
    """What each of an action's slots animates: [slot, object's name, "object" or "keys"]. An importer names a slot for its
    object, or else just "OBSlot" for the file's armature."""
    by_name = {obj.name: obj for obj in objects}
    keys = {obj.data.shape_keys.name: obj for obj in objects if obj.type == "MESH" and obj.data.shape_keys}
    rig = next((obj for obj in objects if obj.type == "ARMATURE"), None)
    out = []
    for slot in action.slots:
        name = slot.identifier[2:]
        if slot.target_id_type == "KEY" and name in keys:
            out.append([slot.identifier, keys[name].name, "keys"])
        elif slot.target_id_type == "OBJECT" and name in by_name:
            out.append([slot.identifier, name, "object"])
        elif slot.target_id_type == "OBJECT" and rig is not None:
            out.append([slot.identifier, rig.name, "object"])
    return out


def _clear_animation(objects: list) -> None:
    for obj in objects:
        for holder in (obj, obj.data.shape_keys if obj.type == "MESH" else None):
            if holder is None or not holder.animation_data:
                continue
            for track in list(holder.animation_data.nla_tracks):
                holder.animation_data.nla_tracks.remove(track)
            holder.animation_data.action = None
        if obj.type == "ARMATURE":
            for bone in obj.pose.bones:
                bone.matrix_basis.identity()


def _show(action, slots: list, by_name: dict) -> None:
    for identifier, name, kind in slots:
        obj = by_name[name]
        holder = obj.data.shape_keys if kind == "keys" else obj
        ad = holder.animation_data or holder.animation_data_create()
        ad.action = action
        ad.action_slot = next(s for s in action.slots if s.identifier == identifier)


def _built(spec: dict) -> dict:
    """A thing made from its parts by the machine kit. A part's own paint becomes a material by that part's name."""
    parts = []
    for part in spec["source"]["parts"]:
        material = part.get("material")
        if isinstance(material, dict):
            name = f"own.{part['id']}"
            materials.custom(name, **material)
            part = {**part, "material": name}
        parts.append(part)
    return kit.Model({"parts": parts}).objects


def _line_of(part: dict) -> list | None:
    """The line a part runs along, in its own space, for what's drawn along it."""
    if part.get("kind") == "pipe":
        return [tuple(p) for p in part["path"]]
    if part.get("kind") == "spiral":
        return shapes.spiral_path(part["r_in"], part["r_out"], part["turns"])
    return None


def make(job: dict, out: Path) -> dict:
    """The file into thing.blend and thing.json: the right size, the right way up, with its clips listed."""
    spec, scene = job["spec"], bpy.context.scene
    fps = scene.render.fps
    before = set(bpy.data.objects)
    built = spec["source"]["kind"] == "built"
    parts = _built(spec) if built else None
    liquids = [part["id"] for part in spec["source"].get("parts") or [] if part.get("liquid")] if built else []
    for pid in liquids:             # what's in it: never solid, and cut off at a level the scene gives (blender/liquid.py)
        parts[pid][LIQUID] = pid
    for part in (spec["source"].get("parts") or []) if built else []:      # what you see through: it doesn't stand in a lens's way
        paint = part.get("material")
        if not part.get("liquid") and (paint == "clear_glass" or (isinstance(paint, dict) and paint.get("clear", 0) >= CLEAR_ENOUGH)):
            parts[part["id"]][CLEAR] = True
    if not built:
        _import(job["source"]["file"])
    scene.render.fps = fps
    objects = _brought(before)
    meshes = [obj for obj in objects if obj.type == "MESH"]
    if not meshes:
        raise ValueError(f"{job['source']['file']} has no mesh in it")
    if not built:
        _fewer_faces(meshes)
    if spec.get("smooth"):
        _smooth(meshes)
    paints = _color(meshes, spec.get("colors") or {})
    clips = {}
    for action in bpy.data.actions:
        action.use_fake_user = True
        first, last = action.frame_range
        short = action.name.rsplit("|", 1)[-1]
        clips[short] = {"action": action.name, "from": round(first, 2), "to": round(last, 2), "slots": _slots(action, objects)}
    _clear_animation(objects)
    moves = {name: {"clip": move["clip"], "from": move.get("from", clips[move["clip"]]["from"]),
                    "to": move.get("to", clips[move["clip"]]["to"])}
             for name, move in (spec.get("moves") or {}).items()} or {
        name: {"clip": name, "from": clip["from"], "to": clip["to"]} for name, clip in clips.items()}

    root = bpy.data.objects.new("thing", None)
    holder = bpy.data.objects.new("thing.holder", None)
    for obj in (root, holder):
        scene.collection.objects.link(obj)
    holder.parent = root
    for obj in objects:
        if obj.parent is None:
            obj.parent = holder
    tilt = spec.get("tilt", (0, 0))
    holder.rotation_euler = Euler((math.radians(tilt[0]), math.radians(tilt[1]), math.radians(spec.get("turn", 0))), "XYZ")
    rest = moves.get(spec.get("rest"))
    by_name = {obj.name: obj for obj in objects}
    if rest:
        _show(bpy.data.actions[clips[rest["clip"]]["action"]], clips[rest["clip"]]["slots"], by_name)
        scene.frame_set(int(rest["from"]))
    if spec.get("trim"):
        _trim(meshes, spec["trim"])
    low, high = _bounds(meshes)
    longest = max(high - low)
    if longest <= 0:
        raise ValueError(f"{job['source']['file']} has no size")
    scale = spec["meters"] / longest if spec.get("meters") else 1.0
    holder.scale = (scale, scale, scale)
    low, high = _bounds(meshes)
    holder.location = -(low + high) / 2
    bpy.context.view_layer.update()
    if spec.get("trim_pale"):
        _trim_pale(meshes, spec["trim_pale"])
    low, high = _bounds(meshes)
    _clear_animation(objects)
    scene.frame_set(1)

    manifest = {"spec": spec, "root": root.name, "holder": holder.name, "objects": sorted(o.name for o in [root, holder, *objects]),
                "size": [round(v, 5) for v in high - low], "materials": paints, "clips": clips, "moves": moves, "license": job["source"]["license"],
                "texels_per_meter": None if built else _texels_per_meter(meshes),
                "credit": job["source"].get("credit", ""), "page": job["source"].get("page", ""), "liquids": liquids,
                "glass": built and any(part.get("material") == "clear_glass" or (isinstance(part.get("material"), dict) and part["material"].get("clear", 0) > 0)
                                       for part in spec["source"]["parts"])}
    if built:      # its spots and lines were written in its parts' meters: from here on they count from its middle, like any thing's
        bpy.context.view_layer.update()
        manifest["spots"] = {name: [round(v, 5) for v in holder.matrix_basis @ Vector(at)] for name, at in (spec.get("spots") or {}).items()}
        manifest["lines"] = {}
        for part in spec["source"]["parts"]:
            line = _line_of(part)
            if line:
                placed = parts[part["id"]].matrix_world
                manifest["lines"][part["id"]] = [[round(v, 5) for v in placed @ Vector(p)] for p in line]
    out.mkdir(parents=True, exist_ok=True)
    try:
        bpy.ops.file.pack_all()
    except RuntimeError as e:          # a texture the file names but didn't include: the model comes in without it
        print(f"not all textures were found: {e}", flush=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(out / "thing.blend"))
    (out / "thing.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    return manifest


class Thing:
    """A saved thing in the scene. Move `root`. `size` is its box in meters. Say what it plays, then call `finish`."""

    def __init__(self, folder: str, size: float = 1.0):
        folder = Path(folder)
        self.manifest = m = json.loads((folder / "thing.json").read_text(encoding="utf-8"))
        with bpy.data.libraries.load(str(folder / "thing.blend"), link=False) as (source, target):
            names, actions = list(source.objects), list(source.actions)
            target.objects = list(names)       # Blender swaps these lists' names for the blocks when it's done
            target.actions = list(actions)
        # a second copy's objects arrive under new names, so they're found by what they were saved as
        self.saved = dict(zip(names, target.objects))
        self.actions = dict(zip(actions, target.actions))
        for obj in target.objects:
            bpy.context.scene.collection.objects.link(obj)
        self.root = self.saved[m["root"]]
        self.holder = self.saved[m["holder"]]
        self.root.rotation_mode = "QUATERNION"
        self.holder.scale = tuple(v * size for v in self.holder.scale)
        self.holder.location = tuple(v * size for v in self.holder.location)
        self.factor = size
        self.size = Vector(m["size"]) * size
        self.moves = m["moves"]
        self.playing: list[tuple] = []
        self.spots = m.get("spots") or m["spec"].get("spots") or {}
        self.lines = m.get("lines") or {}

    def resize(self, k: float) -> None:
        """Bigger or smaller by `k` from here on, to fit what it goes on."""
        self.holder.scale = tuple(v * k for v in self.holder.scale)
        self.holder.location = tuple(v * k for v in self.holder.location)
        self.factor *= k
        self.size = self.size * k

    def spot(self, name: str) -> Vector:
        return Vector(self.spots[name]) * self.factor

    def line(self, name: str) -> list[Vector]:
        """A part's line, from the thing's middle, as it's sized here."""
        return [Vector(p) * self.factor for p in self.lines[name]]

    def hold_by_grip(self) -> None:
        """A held thing's origin moves to where the hand closes on it."""
        if "grip" in self.spots:
            self.holder.location = Vector(self.holder.location) - self.spot("grip")

    def play(self, start: int, end: int, move: str, speed: float = 1.0) -> None:
        self.playing.append((int(start), int(end), move, float(speed)))

    def _holders(self, clip: dict) -> list[tuple]:
        action = self.actions[clip["action"]]
        out = []
        for identifier, name, kind in clip["slots"]:
            obj = self.saved[name]
            holder = obj.data.shape_keys if kind == "keys" else obj
            out.append((holder, action, next(s for s in action.slots if s.identifier == identifier)))
        return out

    def _strip(self, holder, action, slot, start, end, move, speed, first) -> None:
        ad = holder.animation_data or holder.animation_data_create()
        ad.use_nla = True
        track = ad.nla_tracks.new()
        strip = track.strips.new(move["clip"], start, action)
        strip.action_slot = slot
        strip.action_frame_start, strip.action_frame_end = move["from"], move["to"]
        strip.scale = 1.0 / speed
        length = (move["to"] - move["from"]) / speed
        strip.repeat = max(1.0, (end - start) / max(length, 1e-3))
        strip.extrapolation = "HOLD" if first else "HOLD_FORWARD"
        if not first:
            strip.blend_in = min(EASE_FRAMES, (end - start) / 2)

    def finish(self) -> None:
        """Into the NLA: one track for each thing it plays, in order, each easing in over the one before and holding its
        last pose until the next. Before anything plays, it stands in its `rest`."""
        rest = self.manifest["spec"].get("rest")
        segments = sorted(self.playing)
        if rest and (not segments or segments[0][0] > 1):
            segments.insert(0, (1, 2, rest, None))
        for i, (start, end, name, speed) in enumerate(segments):
            move = self.moves[name]
            clip = self.manifest["clips"][move["clip"]]
            if speed is None:                  # one pose, held
                move, speed = {**move, "to": move["from"] + 1}, 1.0
            for holder, action, slot in self._holders(clip):
                self._strip(holder, action, slot, start, end, move, speed, i == 0)


def sheet(job: dict, out: Path, scene) -> dict:
    """A thing from each side and its moves, to judge it before it's used: is it right, is its front the front, how big."""
    envs.sky_set()
    scene.render.use_motion_blur = False
    thing = Thing(job["thing"])
    middle = Vector((0, 0, thing.size.z / 2))      # standing on the floor: the set's floor hides whatever's under it, which was half of every thing
    thing.root.location = middle
    envs.portrait_lights(middle, reach=max(max(thing.size) / 1.2, 0.6))
    cam, aim = look.camera(scene, (0, -3, 0), middle, lens=LENS, fstop=0)
    height = max(thing.size) * 1.35
    distance = height * LENS / 24
    cam.data.clip_start, cam.data.clip_end = distance / 100, distance * 100
    views = [(view, around, up, None, 0) for view, around, up in VIEWS]
    for name, move in list(thing.moves.items())[:4]:
        span = move["to"] - move["from"]
        views += [(f"{name}, frame {round(move['from'] + span * i / 4)}", 30, 8, name, move["from"] + span * i / 4) for i in range(4)]
    shots = []
    for i, (view, around, up, name, at) in enumerate(views, start=1):
        if name:
            clip = thing.manifest["clips"][thing.moves[name]["clip"]]
            _show(thing.actions[clip["action"]], clip["slots"], thing.saved)
            scene.frame_set(int(round(at)))
        turn, lift = math.radians(around), math.radians(up)
        cam.location = middle + Vector((math.sin(turn) * math.cos(lift), -math.cos(turn) * math.cos(lift), math.sin(lift))) * distance
        bpy.context.view_layer.update()
        file = f"{i:02d}.png"
        scene.render.filepath = str(out / file)
        bpy.ops.render.render(write_still=True)
        shots.append({"view": view, "file": file})
        print(f"FRAME {i}/{len(views)}", flush=True)
    size = [round(v, 3) for v in thing.size]
    result = {"shots": shots, "size": size}
    (out / "sheet.json").write_text(json.dumps(result, indent=1), encoding="utf-8")
    return result

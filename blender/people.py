"""A saved person (blender/humgen.py) brought into a scene and made to perform. It's plain Blender from here: objects,
bones and shape keys, so a render doesn't need the add-on, only the textures in its content folder.

The face is keyed on its shape keys, not through the rig's control bones. Each key's driver is removed the first time
it's keyed, as the add-on's own motion capture does, or the driver would overwrite the key.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import bpy
from mathutils import Matrix, Vector


# what a shot or a portrait asks for by name: the add-on's artist-made faces, saved on the person as "e_<file>" keys
EXPRESSIONS = {
    "happy": "e_happy_smile", "smile": "e_Smile", "surprised": "e_big_surprise", "shocked": "e_flabbergasted",
    "scared": "e_unpleasant_surprise", "angry": "e_Angry", "yelling": "e_angry_yell", "sad": "e_Sad",
    "disgusted": "e_Disgust", "thinking": "e_concentrated", "curious": "e_intrigued",
}


class Person:
    def __init__(self, folder: str, at=(0, 0, 0), rot: float = 0.0):
        folder = Path(folder)
        self.manifest = json.loads((folder / "person.json").read_text(encoding="utf-8"))
        with bpy.data.libraries.load(str(folder / "person.blend"), link=False) as (source, target):
            names = list(source.objects)
            target.objects = list(names)       # Blender swaps this list's names for the objects when it's done
        # a second person's objects arrive under new names, "HG_Body.001", so they're found by what they were saved as
        saved = dict(zip(names, target.objects))
        for obj in target.objects:
            bpy.context.scene.collection.objects.link(obj)
        m = self.manifest
        self.rig = saved[m["rig"]]
        self.body = saved[m["body"]]
        self.eyes = saved[m["eyes"]]
        self.upper_teeth = saved[m["upper_teeth"]]
        self.lower_teeth = saved[m["lower_teeth"]]
        self.bones = m["bones"]
        self.rig.location = at
        self.rig.rotation_euler = (0, 0, math.radians(rot))
        bpy.context.scene.render.hair_type = "STRIP"   # strands as flat ribbons facing the camera: smooth in EEVEE
        self._freed: set[str] = set()
        self._anchors: dict[str, tuple] = {}
        self._soften_gloss()
        bpy.context.view_layer.update()

    def _soften_gloss(self) -> None:
        """The add-on's teeth, tongue and eye lenses are mirror-gloss, which EEVEE turns to white speckle: inside a
        dark mouth, and as a noisy block where an eye reflects a light. A soft sheen looks wet instead. EEVEE also lets
        the sky's light into a closed space, so the tongue glows; darkening it where it's enclosed makes the mouth the
        dark hollow it is in Cycles."""
        done = set()
        for obj in (self.upper_teeth, self.lower_teeth):
            for mat in obj.data.materials:
                bsdf = next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
                if bsdf is None or mat.name in done:
                    continue
                done.add(mat.name)
                tree = mat.node_tree
                rough = bsdf.inputs["Roughness"]
                for link in list(rough.links):
                    tree.links.remove(link)
                rough.default_value = 0.5
                bsdf.inputs["Specular IOR Level"].default_value = 0.3
                base = bsdf.inputs["Base Color"]
                if base.links:
                    source = base.links[0].from_socket
                    enclosed = tree.nodes.new("ShaderNodeAmbientOcclusion")
                    enclosed.inputs["Distance"].default_value = 0.06
                    darken = tree.nodes.new("ShaderNodeVectorMath")
                    darken.operation = "MULTIPLY"
                    tree.links.new(source, darken.inputs[0])
                    tree.links.new(enclosed.outputs["AO"], darken.inputs[1])
                    tree.links.new(darken.outputs["Vector"], base)
        for mat in self.eyes.data.materials:
            lens = False
            for node in mat.node_tree.nodes:
                if node.type in ("BSDF_GLOSSY", "BSDF_GLASS"):
                    node.inputs["Roughness"].default_value = max(node.inputs["Roughness"].default_value, 0.04)
                    lens = True
            if lens:    # dithered see-through speckles over the iris, so the lens blends instead
                mat.surface_render_method = "BLENDED"

    def bone(self, name: str):
        """A pose bone by its name in the add-on's rig, whatever it's called on this person."""
        return self.rig.pose.bones[self.bones[name]]

    def _corners(self, obj) -> list[Vector]:
        evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
        return [evaluated.matrix_world @ Vector(c) for c in evaluated.bound_box]

    def middle(self, obj) -> Vector:
        """The middle of an object as it stands now, deformed by the rig, in the world."""
        corners = self._corners(obj)
        return sum(corners, Vector()) / len(corners)

    def mouth(self) -> Vector:
        """The front of the teeth, halfway up the mouth, for a person facing the camera along +y. The middle of the
        teeth is deep inside the head: they run back as far as the molars."""
        middle = (self.middle(self.upper_teeth) + self.middle(self.lower_teeth)) / 2
        middle.y = min(c.y for c in self._corners(self.upper_teeth))
        return middle

    def _blocks(self, name: str) -> list:
        """A face key's blocks: the jaw has one on the body and one on the lower teeth, which open together."""
        found = []
        for obj in (self.body, self.lower_teeth, self.upper_teeth):
            keys = obj.data.shape_keys
            block = keys.key_blocks.get(name) if keys else None
            if block is not None:
                found.append(block)
        return found

    def face(self, frame: int, strict: bool = True, **keys) -> None:
        """Key face shapes at `frame`, e.g. face(40, jawOpen=0.4). An unknown name is refused, with the real ones,
        unless not `strict` (a hand-built test trying names)."""
        for name, value in keys.items():
            blocks = self._blocks(name)
            if not blocks:
                if strict:
                    raise KeyError(f"no face key {name}; this person has {self.manifest['face_keys']}")
            for block in blocks:
                id_key = f"{block.id_data.name}/{name}"
                if id_key not in self._freed:
                    block.driver_remove("value")
                    self._freed.add(id_key)
                block.value = value
                block.keyframe_insert("value", frame=frame)

    def expression(self, frame: int, name: str | None, amount: float = 1.0) -> None:
        """Key a named expression at `frame`, every other one back to rest. None is the resting face."""
        shapes = {key: 0.0 for key in EXPRESSIONS.values()}
        if name:
            shapes[EXPRESSIONS[name]] = amount
        self.face(frame, strict=False, **shapes)

    def anchor(self, name: str) -> tuple:
        """A point on the head that a camera or a label can follow, as (object, offset): "eyes", "mouth" or "head"."""
        if name not in self._anchors:
            points = {"eyes": lambda: self.middle(self.eyes), "mouth": self.mouth,
                      "head": lambda: self.rig.matrix_world @ self.bone("head").head}
            if name not in points:
                raise KeyError(f"no anchor {name} on a person; there's {', '.join(points)}")
            self._anchors[name] = (self.attach("head", points[name](), f"{self.rig.name}.{name}"), (0, 0, 0))
        return self._anchors[name]

    def hold(self, side: str, sword) -> None:
        """Lock a hand onto a sword's grip, so the sword leads and the arm follows. `sword` is an object in the world
        with its origin in the palm: its z runs along the blade, its y the way the fingers point. The hand can't slip,
        whatever the sword does, as long as the arm reaches. The grip lies across the palm, with the thumb on the blade
        side, as a held sword does. Works out the hand's turn from its rest pose, so call it before keying anything
        that would change the rest."""
        hand = self.bone(f"hand.{side}")
        rest = hand.bone.matrix_local.to_3x3()
        along = (hand.bone.tail_local - hand.bone.head_local).normalized()
        thumb = self.bone(f"thumb.01.{side}").bone.tail_local - hand.bone.head_local
        grip = (thumb - along * thumb.dot(along)).normalized()
        axes = Matrix((along.cross(grip).normalized(), along, grip)).transposed()
        target = bpy.data.objects.new(f"{self.rig.name}.hold.{side}", None)
        bpy.context.scene.collection.objects.link(target)
        target.parent = sword
        target.matrix_parent_inverse = Matrix.Identity(4)
        target.rotation_mode = "QUATERNION"
        target.rotation_quaternion = (axes.inverted() @ rest).to_quaternion()
        target.location = (0, -0.075, 0)                       # the hand's root, behind the palm
        ik = self.bone(f"forearm.{side}").constraints.new("IK")
        ik.target, ik.chain_count, ik.use_tail, ik.use_rotation = target, 2, True, False
        turn = hand.constraints.new("COPY_ROTATION")
        turn.target, turn.target_space, turn.owner_space = target, "WORLD", "WORLD"

    def glow(self, at: Vector, radius: float, color) -> "bpy.types.NodeSocket":
        """A patch of the skin that glows, fading out `radius` meters from the world point `at`, riding on the head, with
        a mottled edge: force travelling through a jaw. Returns the socket to key how much of it shows, 0 to 1."""
        centre = self.attach("head", at, f"{self.rig.name}.glow")
        mat = self.body.data.materials[0]
        tree = mat.node_tree
        output = next(n for n in tree.nodes if n.type == "OUTPUT_MATERIAL" and n.is_active_output)
        coords = tree.nodes.new("ShaderNodeTexCoord")
        coords.object = centre
        squash = tree.nodes.new("ShaderNodeMapping")   # wider than it's tall, so it stays on the jaw, off the neck
        squash.inputs["Scale"].default_value = (0.8, 0.8, 1.7)
        tree.links.new(coords.outputs["Object"], squash.inputs["Vector"])
        distance = tree.nodes.new("ShaderNodeVectorMath")
        distance.operation = "LENGTH"
        tree.links.new(squash.outputs["Vector"], distance.inputs[0])
        mottled = tree.nodes.new("ShaderNodeTexNoise")
        mottled.inputs["Scale"].default_value = 55.0
        mottled.inputs["Detail"].default_value = 3.0
        tree.links.new(coords.outputs["Object"], mottled.inputs["Vector"])
        edge = tree.nodes.new("ShaderNodeMath")
        edge.operation = "ADD"
        tree.links.new(distance.outputs["Value"], edge.inputs[0])
        scaled = tree.nodes.new("ShaderNodeMath")
        scaled.operation = "MULTIPLY"
        scaled.inputs[1].default_value = radius * 0.5
        tree.links.new(mottled.outputs["Fac"], scaled.inputs[0])
        tree.links.new(scaled.outputs["Value"], edge.inputs[1])
        falloff = tree.nodes.new("ShaderNodeMapRange")
        falloff.interpolation_type = "SMOOTHSTEP"
        falloff.inputs["From Min"].default_value = radius * 0.8
        falloff.inputs["From Max"].default_value = radius * 1.25
        falloff.inputs["To Min"].default_value = 1.0
        falloff.inputs["To Max"].default_value = 0.0
        tree.links.new(edge.outputs["Value"], falloff.inputs["Value"])
        strength = tree.nodes.new("ShaderNodeValue")
        strength.outputs[0].default_value = 0.0
        amount = tree.nodes.new("ShaderNodeMath")
        amount.operation = "MULTIPLY"
        tree.links.new(falloff.outputs["Result"], amount.inputs[0])
        tree.links.new(strength.outputs[0], amount.inputs[1])
        light = tree.nodes.new("ShaderNodeEmission")
        light.inputs["Color"].default_value = (*color, 1)
        light.inputs["Strength"].default_value = 0.85
        both = tree.nodes.new("ShaderNodeMixShader")   # in place of the skin, not on top of it: added, it washes out
        tree.links.new(amount.outputs["Value"], both.inputs[0])
        tree.links.new(output.inputs["Surface"].links[0].from_socket, both.inputs[1])
        tree.links.new(light.outputs["Emission"], both.inputs[2])
        tree.links.new(both.outputs["Shader"], output.inputs["Surface"])
        return strength.outputs[0]

    def hide_hair_above(self, at: Vector, turn) -> None:
        """No hair above a plane through the world point `at`, turned by `turn` and riding on the head: what a hat is covering.
        It's cut in the hair's own shader, so it holds whatever the head does, and the strands below it stay as they were."""
        plane = self.attach("head", at, f"{self.rig.name}.hat_line")
        bpy.context.view_layer.update()
        plane.matrix_world = Matrix.Translation(at) @ turn.to_matrix().to_4x4()
        done = set()
        for system in self.body.particle_systems:
            name = system.name.lower()
            if "brow" in name or "lash" in name or not 0 < system.settings.material <= len(self.body.material_slots):
                continue
            mat = self.body.material_slots[system.settings.material - 1].material
            if mat is None or mat in done:
                continue
            done.add(mat)
            tree = mat.node_tree
            mat.surface_render_method = "DITHERED"
            output = next(n for n in tree.nodes if n.type == "OUTPUT_MATERIAL" and n.is_active_output)
            coords = tree.nodes.new("ShaderNodeTexCoord")
            coords.object = plane
            height = tree.nodes.new("ShaderNodeSeparateXYZ")
            tree.links.new(coords.outputs["Object"], height.inputs[0])
            above = tree.nodes.new("ShaderNodeMath")
            above.operation = "GREATER_THAN"
            above.inputs[1].default_value = 0.0
            tree.links.new(height.outputs["Z"], above.inputs[0])
            mix = tree.nodes.new("ShaderNodeMixShader")
            tree.links.new(above.outputs[0], mix.inputs[0])
            tree.links.new(output.inputs["Surface"].links[0].from_socket, mix.inputs[1])
            tree.links.new(tree.nodes.new("ShaderNodeBsdfTransparent").outputs[0], mix.inputs[2])
            tree.links.new(mix.outputs[0], output.inputs["Surface"])

    def blink(self, frame: int, closed: int = 2, open_again: int = 4) -> None:
        """A blink starting at `frame`: quick down, slower up."""
        for f, value in ((frame, 0.0), (frame + closed, 1.0), (frame + closed + open_again, 0.0)):
            self.face(f, strict=False, eyeBlink_L=value, eyeBlink_R=value)

    def gaze(self, frame: int, x: float = 0.0, y: float = 0.0, degrees: float = 16.0) -> None:
        """Turn both eyes at `frame`: x from -1 (the person's right) to 1 (their left), y from -1 (down) to 1 (up).
        The eyes track a target bone about 16 cm in front of the face, so turning them directly does nothing: the
        target moves, and the lids follow by their own keys."""
        bone = self.bone("eyeball_lookat_master")
        reach = math.tan(math.radians(degrees)) * 0.16
        bone.location = bone.bone.matrix_local.to_3x3().inverted() @ Vector((x * reach, 0, y * reach))
        bone.keyframe_insert("location", frame=frame)
        up, down = max(y, 0.0), max(-y, 0.0)
        self.face(frame, strict=False, eyeLookUpLeft=up, eyeLookUpRight=up, eyeLookDownLeft=down, eyeLookDownRight=down)

    def attach(self, bone: str, at: Vector, name: str = "Held"):
        """An empty at the world point `at`, riding on a bone: what's parented to it moves with that bone, and is
        placed by keys in the world's directions from there (a prop in the mouth)."""
        holder = bpy.data.objects.new(name, None)
        bpy.context.scene.collection.objects.link(holder)
        holder.parent = self.rig
        holder.parent_type = "BONE"
        holder.parent_bone = self.bones[bone]
        bpy.context.view_layer.update()
        holder.matrix_world = Matrix.Translation(at)
        return holder

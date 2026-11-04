"""Makes a person with Human Generator and saves them (CHARACTERS.md). This is the only file that touches the add-on:
everything else uses the saved person, through blender/people.py.

A job of kind "person":
  humgen    {addon, content}: the folders render/humgen.py unpacked
  person    what characters/spec.py's to_person() writes: preset (a path from Human.get_preset_options), and optionally
            age, hair (a path, or false for bald), brows (a name from person.json's "brows"), brow_density, hair_color and brow_color {lightness, redness, salt_and_pepper, ...}, textures_8k,
            skin {tone, redness, saturation, freckles, ...}, makeup {lipstick_opacity, ...}, expressions (paths in the
            content folder, each saved as a shape key "e_<name>"), face_hair (a path, or false for none; it takes
            hair_color too), eye_color [r, g, b],
            outfit, footwear (paths in the content folder), clothes {part of a garment's name: [r, g, b]} and keys
            {shape key name: value}, such as "Stylized" or "Eye Scale"

It writes person.blend and person.json to `out`: which objects and bones are which, and every face key there is.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import addon_utils
import bpy


def enable(addon_dir: str, content_dir: str) -> None:
    """Enable the add-on for this run. Every run is --factory-startup, so nothing of it is remembered. default_set
    puts it in the preferences' list of add-ons, where it looks up its own settings."""
    sys.path.insert(0, addon_dir)
    if not addon_utils.enable("HumGen3D", default_set=True):
        raise RuntimeError(f"Human Generator wouldn't enable from {addon_dir}")
    prefs = bpy.context.preferences.addons["HumGen3D"].preferences
    prefs.skip_url_request = True                     # no update checks: the version is pinned
    prefs.filepath_ = os.path.join(content_dir, "")   # it joins paths to this with no separator between
    import HumGen3D

    HumGen3D.HG_start(None)   # its own setup when Blender opens a file, which has already happened by now


def _path(p: str) -> str:
    """This system's slashes: the add-on finds a preset's gender by splitting on them."""
    return os.path.normpath(p)


def _garments() -> list[str]:
    return [obj.name for obj in bpy.data.objects if obj.get("cloth") or obj.get("shoe")]


def _color_clothes(colors: dict) -> None:
    """A garment's main color, on its material's control node. A garment is named for what it is ("HG_Sweater_2")."""
    for part, rgb in colors.items():
        matching = [name for name in _garments() if part.lower() in name.lower()]
        if not matching:
            raise ValueError(f"clothes: no garment like {part!r} in this outfit: {_garments()}")
        for name in matching:
            for mat in bpy.data.objects[name].data.materials:
                control = mat.node_tree.nodes.get("HG_Control")
                for socket in control.inputs if control else ():
                    if socket.name.startswith("Main Color"):
                        socket.default_value = (*rgb, 1.0)


def build(job: dict, out: Path) -> dict:
    enable(job["humgen"]["addon"], job["humgen"]["content"])
    from HumGen3D import Human

    context = bpy.context
    spec = job["person"]
    # our own look.setup() decides the render settings, so the add-on leaves them alone
    human = Human.from_preset(_path(spec["preset"]), context=context, prettify_eevee=False)
    if spec.get("age"):
        human.age.set(int(spec["age"]))
    if spec.get("hair") is False:
        human.hair.regular_hair.remove_all()
    elif spec.get("hair"):
        human.hair.regular_hair.set(_path(spec["hair"]), context=context)
    for name, value in (spec.get("hair_color") or {}).items():
        getattr(human.hair.regular_hair, name).value = value
    if spec.get("brows"):
        human.hair.eyebrows.set(spec["brows"])
    for name, value in (spec.get("brow_color") or {}).items():
        getattr(human.hair.eyebrows, name).value = value
    if spec.get("brow_density"):     # the add-on's are 8 strands per guide, sparse in a close-up
        for mod in human.objects.body.modifiers:   # only the brows in use: changing a hidden set crashes EEVEE's blur
            if mod.type == "PARTICLE_SYSTEM" and mod.show_render and mod.particle_system.name.startswith("Eyebrows"):
                settings = mod.particle_system.settings
                settings.rendered_child_count = int(settings.rendered_child_count * spec["brow_density"])
                settings.root_radius *= 1.5
    if spec.get("textures_8k"):
        human.skin.texture.set(human.as_dict()["skin"]["texture.set"].replace("Default 4K", "Default 8K"))
    for name, value in (spec.get("skin") or {}).items():
        getattr(human.skin, name).value = value
    for name, value in (spec.get("makeup") or {}).items():
        getattr(human.skin.gender_specific, name).value = value
    if spec.get("face_hair") is False:
        human.hair.face_hair.remove_all()
    elif spec.get("face_hair"):
        human.hair.face_hair.set(_path(spec["face_hair"]), context=context)
        for name, value in (spec.get("hair_color") or {}).items():
            getattr(human.hair.face_hair, name).value = value
    if spec.get("eye_color"):
        human.eyes.iris_color.value = (*spec["eye_color"], 1.0)
    if spec.get("outfit"):
        human.clothing.outfit.set(_path(spec["outfit"]), context=context)
    if spec.get("footwear"):
        human.clothing.footwear.set(_path(spec["footwear"]), context=context)
    _color_clothes(spec.get("clothes") or {})
    for name, value in (spec.get("keys") or {}).items():
        human.keys[name].value = value
    human.hair.update_hair_shader_type("accurate")    # the one EEVEE can draw; "fast" is Cycles only
    for preset in spec.get("expressions") or []:      # the add-on's artist-made faces, as keys a shot can blend
        human.expression.set(_path(preset))
    human.expression.load_facial_rig(context=context)
    for key in human.expression.keys:
        key.value = 0

    objects = human.objects
    body = objects.body
    manifest = {
        "spec": spec,
        "rig": objects.rig.name,
        "body": body.name,
        "eyes": objects.eyes.name,
        "upper_teeth": objects.upper_teeth.name,
        "lower_teeth": objects.lower_teeth.name,
        "bones": {b.get("original_name", b.name): b.name for b in objects.rig.pose.bones},
        "face_keys": [k.name for k in body.data.shape_keys.key_blocks if k.name not in ("Basis", "Male")
                      and not k.name.startswith(("cor_", "LIVE_KEY"))],
        "brows": [s.name for s in human.hair.particle_systems if s.name.startswith("Eyebrows_")],
        "garments": _garments(),
        "settings": human.as_dict(),
    }
    bpy.ops.wm.save_as_mainfile(filepath=str(out / "person.blend"), compress=True, relative_remap=False)
    (out / "person.json").write_text(json.dumps(manifest, indent=1, default=str), encoding="utf-8")
    return manifest

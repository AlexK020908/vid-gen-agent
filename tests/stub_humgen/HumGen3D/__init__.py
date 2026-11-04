"""A stand-in for the paid add-on, with only what blender/humgen.py calls, signatures as in its source (v4.0.38). It
tests our side of the join: enabling under --factory-startup, the preferences, the paths and the saved files. It says
nothing about how the real add-on behaves."""
import importlib.util
import os
from pathlib import Path
from types import SimpleNamespace

import bpy

bl_info = {"name": "Stub Human Generator", "blender": (4, 0, 0), "category": "Add Mesh"}
CALLS = []
STARTED = []


def HG_start(dummy):
    """The real one fills the lists from_preset needs, and asks the web for updates unless told not to."""
    prefs = bpy.context.preferences.addons["HumGen3D"].preferences
    assert prefs.skip_url_request and prefs.filepath_
    STARTED.append(True)


class Prefs(bpy.types.AddonPreferences):
    bl_idname = __package__ or "HumGen3D"
    filepath_: bpy.props.StringProperty(default="")
    skip_url_request: bpy.props.BoolProperty(default=False)


def _fake_person():
    path = Path(os.environ["FAKE_PERSON_SCRIPT"])
    spec = importlib.util.spec_from_file_location("blender_fake_person", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.build()


class _Set:
    def __init__(self, name):
        self.name = name
        self.lightness = SimpleNamespace(value=0.0)

    def set(self, preset, context=None):
        prefs = bpy.context.preferences.addons["HumGen3D"].preferences
        CALLS.append((self.name, preset))
        assert os.path.exists(prefs.filepath_ + preset), prefs.filepath_ + preset   # joined with no separator


class Human:
    def __init__(self):
        rig, body, eyes, upper, lower = _fake_person()
        self.objects = SimpleNamespace(rig=rig, body=body, eyes=eyes, upper_teeth=upper, lower_teeth=lower)
        self.hair = SimpleNamespace(regular_hair=_Set("hair"), update_hair_shader_type=self._shader, particle_systems=[])
        self.clothing = SimpleNamespace(outfit=_Set("outfit"), footwear=_Set("footwear"))
        self.expression = SimpleNamespace(load_facial_rig=lambda context=None: None, keys=[])
        self.keys = {}

    def _shader(self, kind):
        assert kind == "accurate"

    def as_dict(self):
        return {"calls": CALLS}

    @classmethod
    def from_preset(cls, preset, context=None, prettify_eevee=True, from_batch_generator=False):
        assert preset.split(os.sep)[1] in ("male", "female"), preset   # how the add-on finds the gender
        assert prettify_eevee is False
        assert STARTED, "from_preset before the add-on's startup"
        return cls()


def register():
    bpy.utils.register_class(Prefs)


def unregister():
    bpy.utils.unregister_class(Prefs)

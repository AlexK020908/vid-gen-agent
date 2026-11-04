"""Phase 32 (CHARACTERS.md): unpacking the add-on, listing what it offers, and the render side with a stand-in person.
The paid add-on isn't needed: a stub plays it, so these check our side of the join and not how it really behaves. The
Blender tests skip without Blender.
"""
import json
import os
import shutil
import subprocess
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from characters import build
from characters import spec as character_spec
from core import config
from render import blender_render, clips, humgen
from scenes import spec as scene_spec

CFG = config.load()
PEOPLE, STANCES = ["hero", "foe"], ["Idle_relaxed", "Idle_with_a_sword"]
SCENE = {
    "length": 2.0, "set": "gym",
    "cast": {"a": {"type": "person", "character": "hero", "at": [0, 0], "stance": "Idle_relaxed"},
             "b": {"type": "person", "character": "foe", "at": [0.85, -0.9], "facing": "a", "stance": "Idle_with_a_sword"},
             "bitten": {"type": "prop", "prop": "long_sword"}, "held": {"type": "prop", "prop": "katana"},
             "thrown": {"type": "prop", "prop": "ball"}},
    "happens": [{"do": "bite", "who": "a", "prop": "bitten"},
                {"do": "hold", "who": "b", "prop": "held", "hand": "R", "grip": "raised"},
                {"do": "strike", "t": 1.0, "who": "b", "prop": "held", "target": "bitten", "along": 0.42},
                {"do": "fly", "t": 0.2, "prop": "thrown", "from": [2, -2, 1.2], "to": "a:forehead", "over": 0.6, "hits": "a"},
                {"do": "glow", "t": 0.9, "who": "a", "on": "jaw", "color": "green", "to": 2.0},
                {"do": "expression", "t": 0.5, "who": "a", "name": "shocked"}],
    "shots": [{"t": 0, "on": "a:mouth", "frame": 0.9, "angle": [0, -5], "lens": 24, "push": 0.05},
              {"t": 1.0, "on": "bitten:0.2", "frame": 0.4, "lens": 20, "shows": ["a", "bitten", "held"]}],
    "captions": [{"t": 0, "to": 2, "text": "Words"}]}
TESTS = Path(__file__).resolve().parent
needs_blender = pytest.mark.skipif(blender_render.missing(CFG) is not None, reason="Blender isn't installed")


def _cfg(tmp_path):
    return SimpleNamespace(blender={"humgen": str(tmp_path)}, data_dir=tmp_path / "data")


def _zip(path: Path, files: dict) -> Path:
    with zipfile.ZipFile(path, "w") as z:
        for name, body in files.items():
            z.writestr(name, body)
    return path


def _downloads(tmp_path):
    _zip(tmp_path / "HumGen3D_V4_0.zip", {"HumGen3D/__init__.py": "bl_info = {}"})
    _zip(tmp_path / "Base_Humans.hgpack", {
        "content_packs/Base_Humans.json": "{}", "models/male/Asian 3.json": "{}", "models/female/Black 1.json": "{}",
        "models/HG_HUMAN.blend": "", "models/face_rig.json": "{}"})
    _zip(tmp_path / "Base_Hair.hgpack", {"hair/head/male/Short.json": "{}", "hair/head/male/Short.jpg": "",
                                         "hair/face_hair/Beard.json": "{}", "outfits/male/Tee.blend": ""})


def test_it_says_what_is_missing(tmp_path):
    assert "HumGen3D" in humgen.missing(_cfg(tmp_path))
    _zip(tmp_path / "HumGen3D_V4_0.zip", {"HumGen3D/__init__.py": ""})
    assert ".hgpack" in humgen.missing(_cfg(tmp_path))
    with pytest.raises(RuntimeError, match="hgpack"):
        humgen.install(_cfg(tmp_path))


def test_install_unpacks_once_and_lists_the_options(tmp_path):
    _downloads(tmp_path)
    cfg = _cfg(tmp_path)
    assert humgen.missing(cfg) is None
    said = []
    paths = humgen.install(cfg, said.append)
    assert len(said) == 3
    assert (Path(paths["addon"]) / "HumGen3D" / "__init__.py").exists()
    assert (Path(paths["content"]) / "models" / "HG_HUMAN.blend").exists()
    said.clear()
    humgen.install(cfg, said.append)
    assert not said                                # already unpacked: several gigabytes aren't unpacked twice

    found = humgen.options(cfg)
    assert found["humans"] == {"male": [os.path.join("models", "male", "Asian 3.json")],
                               "female": [os.path.join("models", "female", "Black 1.json")]}
    assert found["hair"]["male"] == [os.path.join("hair", "head", "male", "Short.json")]   # not its thumbnail
    assert found["face_hair"] == [os.path.join("hair", "face_hair", "Beard.json")]
    assert found["outfit"]["male"] == [os.path.join("outfits", "male", "Tee.blend")]
    assert found["pose"] == []


def test_a_pack_cannot_write_outside_its_folder(tmp_path):
    _downloads(tmp_path)
    _zip(tmp_path / "Evil.hgpack", {"../../escaped.txt": "x"})
    with pytest.raises(ValueError, match="outside"):
        humgen.install(_cfg(tmp_path))
    assert not (tmp_path.parent / "escaped.txt").exists()


OPTIONS = {
    "humans": {"male": ["models\\male\\Caucasian\\David.json"], "female": ["models\\female\\Black\\Maya.json"]},
    "hair": {"male": ["hair\\head\\male\\Short\\Short Combed.json"], "female": ["hair\\head\\female\\Long\\Bob Short.json"]},
    "outfit": {"male": ["outfits\\male\\Extra\\Relaxed Fit.blend"], "female": ["outfits\\female\\Casual\\Dress.blend"]},
    "footwear": {"male": ["footwear\\male\\Sneakers.blend"], "female": ["footwear\\female\\Sneakers.blend"]},
    "face_hair": ["hair\\face_hair\\Beard\\Goatee.json"],
    "keys": ["Stylized", "Eye Scale"],
}
SAM = {"name": "Sam", "gender": "male", "preset": "David", "age": 40, "hair": "Short Combed", "hair_color": "brown",
       "eyes": "blue", "outfit": "Relaxed Fit", "footwear": "Sneakers", "keys": {"Stylized": 0.4}}


def test_a_good_character_passes_and_becomes_files():
    assert character_spec.check(SAM, OPTIONS) == []
    person = character_spec.to_person(SAM, OPTIONS)
    assert person["preset"] == OPTIONS["humans"]["male"][0]
    assert person["hair"] == OPTIONS["hair"]["male"][0]
    assert person["hair_color"]["lightness"] == character_spec.HAIR["brown"]["lightness"]
    assert person["brow_color"]["lightness"] == character_spec.BROWS["brown"]
    assert person["face_hair"] is False                # clean-shaven unless asked: presets bring their own beards
    assert character_spec.to_person({**SAM, "face_hair": "Goatee"}, OPTIONS)["face_hair"].endswith("Goatee.json")
    assert character_spec.to_person({**SAM, "hair": False}, OPTIONS)["hair"] is False


@pytest.mark.parametrize("change, says", [
    ({"preset": "Davd"}, "did you mean David"),
    ({"preset": "Maya"}, "preset"),                     # a woman's preset on a man
    ({"age": 12}, "between 20 and 80"),
    ({"hair": "Short Comb"}, "did you mean Short Combed"),
    ({"hair_color": "purple"}, "hair_color"),
    ({"eyes": "gold"}, "eyes"),
    ({"outfit": "Tuxedo"}, "outfit"),
    ({"footwear": "Clogs"}, "footwear"),
    ({"face_hair": "Soul Patch"}, "face_hair"),
    ({"brows": "Eyebrows_500"}, "brows"),
    ({"lipstick": 0.5}, "lipstick"),                    # Sam's a man: the add-on's skin has none for men
    ({"clothes": {"Sweater": [2, 0, 0]}}, "clothes"),
    ({"keys": {"Nope": 0.5}}, "keys"),
    ({"keys": {"Stylized": 9}}, "between -2 and 2"),
    ({"gender": "robot"}, "gender"),
    ({"favourite_food": "soup"}, "not a field"),
])
def test_a_bad_character_is_refused_with_the_reason(change, says):
    problems = character_spec.check({**SAM, **change}, OPTIONS)
    assert problems and says in " ".join(problems)


def test_women_have_no_facial_hair_in_the_add_on():
    nia = {**SAM, "gender": "female", "preset": "Maya", "hair": "Bob Short", "outfit": "Dress"}
    assert character_spec.check(nia, OPTIONS) == []
    assert "face_hair" not in character_spec.to_person(nia, OPTIONS)   # asking to remove it raises in the add-on
    assert "no facial hair" in character_spec.check({**nia, "face_hair": "Goatee"}, OPTIONS)[0]


def test_a_missing_field_is_named():
    spec = dict(SAM)
    del spec["outfit"]
    assert character_spec.check(spec, OPTIONS) == ["outfit: missing"]


def test_every_character_in_the_repo_has_its_fields():
    for cid in character_spec.all_ids():
        spec = character_spec.load(character_spec.path_for(cid))
        assert not [key for key in character_spec.REQUIRED if key not in spec], cid


def test_a_bad_spec_never_reaches_blender(tmp_path, monkeypatch):
    _downloads(tmp_path)
    cfg = _cfg(tmp_path)
    (tmp_path / "bad.json").write_text(json.dumps({**SAM, "preset": "Nobody"}), encoding="utf-8")
    monkeypatch.setattr(character_spec, "SPECS", tmp_path)
    monkeypatch.setattr(blender_render, "run_job", lambda *a, **k: pytest.fail("Blender started"))
    with pytest.raises(ValueError, match="preset"):
        build.build(cfg, "bad", lambda _: None)


def _fake_person(tmp_path) -> Path:
    folder = tmp_path / "person"
    subprocess.run([str(blender_render.exe(CFG)), "-b", "--factory-startup", "--python-exit-code", "1", "-P",
                    str(TESTS / "blender_fake_person.py"), "--", str(folder)], check=True, capture_output=True)
    return folder


@needs_blender
def test_a_saved_person_performs_with_the_add_on_off(tmp_path):
    """The blink and the jaw show in the picture: the jaw's key beats its driver, and nothing of the add-on is loaded."""
    tracks = blender_render.render_shot(CFG, "portrait", tmp_path / "f", size=(216, 384), samples=2, frames=[1, 20, 74],
                                        person=_fake_person(tmp_path))
    assert tracks["rendered"] == [1, 20, 74]
    assert "mouth" in tracks["anchors"]
    closed, blink, jaw = [(tmp_path / "f" / f"f_{i:04d}.png").read_bytes() for i in (1, 20, 74)]
    assert closed != blink and closed != jaw and blink != jaw


@needs_blender
def test_a_portrait_sheet_shows_every_view(tmp_path):
    person = _fake_person(tmp_path)
    result = blender_render.portraits(CFG, person, size=(108, 192), samples=1)
    assert [s["view"] for s in result["shots"]] == ["front", "three quarter left", "three quarter right", "full body",
                                                    "happy", "surprised", "angry", "sad", "shocked", "scared",
                                                    "disgusted", "thinking"]
    picture = build.sheet(result, person / "portraits", cell=(54, 96))
    assert Image.open(picture).size == (54 * 4, 96 * 3)
    pictures = {(person / "portraits" / s["file"]).read_bytes() for s in result["shots"][:4]}
    assert len(pictures) == 4                            # the camera really moved


@needs_blender
def test_two_people_share_a_segment(tmp_path):
    """The second person's objects arrive renamed. Each is found, placed, and followed by the camera, with no add-on."""
    person = _fake_person(tmp_path)
    cfg = SimpleNamespace(blender=CFG.blender, data_dir=tmp_path / "data")
    (cfg.data_dir / "characters").mkdir(parents=True)
    shutil.copytree(person, cfg.data_dir / "characters" / "sam")
    timeline = {"from": 0, "to": 1, "env": "studio",
                "people": {"a": {"person": "sam", "at": [-0.5, 0, 0]}, "b": {"person": "sam", "at": [0.5, 0, 0], "rot": 20}},
                "camera": [{"t": 0, "target": "a:eyes", "frame": 1.0, "lens": 50, "fstop": 0}],
                "anchors": ["a:eyes", "b:eyes", "b:mouth"]}
    tracks = blender_render.render_segment(cfg, timeline, tmp_path / "f", size=(108, 192), samples=1, frames=[1])
    assert tracks["rendered"] == [1]
    a, b = tracks["anchors"]["a:eyes"][0], tracks["anchors"]["b:eyes"][0]
    assert abs(a[0] - 0.5) < 0.05                         # the camera is on the first person
    assert b[0] > a[0] + 0.2                              # the second stands to the side


def test_a_good_scene_passes():
    assert scene_spec.check(SCENE, PEOPLE, STANCES) == []


@pytest.mark.parametrize("change, says", [
    ({"set": "moon"}, "set"),
    ({"length": 900}, "length"),
    ({"cast": {**SCENE["cast"], "a": {**SCENE["cast"]["a"], "character": "nobody"}}}, "character"),
    ({"cast": {**SCENE["cast"], "a": {**SCENE["cast"]["a"], "stance": "Dance"}}}, "stance"),
    ({"cast": {**SCENE["cast"], "held": {"type": "prop", "prop": "banana"}}}, "prop"),
    ({"happens": [{"do": "dance", "t": 0}]}, "do"),
    ({"happens": [{"do": "strike", "t": 1, "who": "b", "prop": "held", "target": "bitten", "along": 0.2}]}, "has to hold"),
    ({"happens": [{"do": "strike", "t": 1, "who": "b", "prop": "held", "target": "bitten"}]}, "how far along"),
    ({"happens": [{"do": "expression", "t": 99, "who": "a", "name": "happy"}]}, "outside the scene"),
    ({"happens": [{"do": "expression", "t": 0, "who": "a", "name": "bored"}]}, "name"),
    ({"happens": [{"do": "glow", "t": 1, "who": "a", "on": "elbow", "color": "green", "to": 2}]}, "on"),
    ({"happens": [{"do": "fly", "t": 0, "prop": "thrown", "from": "nowhere:eyes", "to": "a:eyes", "over": 1}]}, "nowhere"),
    ({"shots": [{"t": 1, "on": "a:eyes", "frame": 1}]}, "first has to start at 0"),
    ({"shots": [{"t": 0, "on": "a:knee", "frame": 1}]}, "on"),
    ({"shots": [{"t": 0, "on": "a:eyes"}]}, "frame"),
    ({"length": 10, "shots": [{"t": 0, "on": "a:eyes", "frame": 1}]}, "too long"),
    ({"shots": [{"t": 0, "on": "a:eyes", "frame": 1, "shows": ["ghost"]}]}, "ghost"),
])
def test_a_bad_scene_is_refused_with_the_reason(change, says):
    problems = scene_spec.check({**SCENE, **change}, PEOPLE, STANCES)
    assert problems and says in " ".join(problems)


def test_the_example_scene_passes_its_checks():
    scene = scene_spec.load(TESTS.parent / "scenes" / "examples" / "ball_to_the_head.json")
    assert scene_spec.check(scene, character_spec.all_ids(), ["Idle_relaxed", "Idle_arms_folded_waiting"]) == []


@needs_blender
@pytest.mark.skipif(clips.missing(CFG) is not None, reason="the free body clips aren't in data/motion")
def test_a_scene_is_staged_from_its_file_alone(tmp_path):
    """Biting, holding, a strike, a thrown ball, a glow and two shots, all run from the scene's JSON on stand-in people, by
    the same code every topic uses."""
    folder = _fake_person(tmp_path)
    found = clips.catalog(CFG)
    tracks = blender_render.render_stage(CFG, SCENE, {"hero": folder, "foe": folder}, found, tmp_path / "f",
                                         size=(108, 192), samples=1, frames=[5, 40])
    assert tracks["frames"] == 60 and tracks["rendered"] == [5, 40]
    assert (tmp_path / "f" / "f_0005.png").read_bytes() != (tmp_path / "f" / "f_0040.png").read_bytes()


@needs_blender
def test_a_clip_moves_our_bones_the_way_it_moves_its_own(tmp_path):
    """Their arm starts straight out and drops straight down. Ours starts in an A-pose and has to end pointing down too,
    and the hips drop by the leg-length ratio. What the clip's file brought into the scene is gone again."""
    subprocess.run([str(blender_render.exe(CFG)), "-b", "--factory-startup", "--python-exit-code", "1", "-P",
                    str(TESTS / "blender_clip_check.py"), "--", str(tmp_path)], check=True, capture_output=True)
    out = json.loads((tmp_path / "out.json").read_text(encoding="utf-8"))
    assert out["objects_left"] == ["Ours"]
    assert out["fps"] == 30                                  # an importer can change this
    assert out["frames"] == 10 and out["after"] == 11
    assert out["upper_arm"] == pytest.approx([0, 0, -1], abs=0.03)
    assert out["hand"] == pytest.approx([0, 0, -1], abs=0.03)   # it follows its parent, as theirs did
    assert out["palm"][2] < -0.9                             # a bone the clip doesn't have stays on its parent
    assert out["spine_z"] == pytest.approx(0.8 - 0.2 * 0.8, abs=0.02)   # 0.2 m at 1.0 m of leg is 0.16 m at 0.8 m


@needs_blender
def test_a_hand_stays_on_its_sword_wherever_the_sword_goes(tmp_path):
    """A sword leads and the arm follows, so a palm can't slip off a grip. The glow goes in place of the skin."""
    folder = _fake_person(tmp_path)
    subprocess.run([str(blender_render.exe(CFG)), "-b", "--factory-startup", "--python-exit-code", "1", "-P",
                    str(TESTS / "blender_hold_check.py"), "--", str(folder)], check=True, capture_output=True)
    out = json.loads((folder / "out.json").read_text(encoding="utf-8"))
    for place in ("near", "far"):
        assert out[place]["gap"] < 0.005, place              # within 5 mm of the grip
        assert out[place]["fingers_off"] < 0.05, place       # the hand turned with it
    assert out["glow_node"] == "MIX_SHADER"


def test_clips_are_listed_from_both_packs(tmp_path):
    where = tmp_path / "motion"
    where.mkdir()
    cfg = SimpleNamespace(data_dir=tmp_path)
    assert "KinemIQ" in clips.missing(cfg)
    _zip(where / clips.KINEMIQ, {"KinemIQ_Mannequin.fbx": "", "FBX/Sword_slash.fbx": "", "README.txt": ""})
    assert "Quaternius" in clips.missing(cfg)
    _zip(where / clips.QUATERNIUS, {"Universal Animation Library 2[Standard]/Unreal-Godot/UAL2_Standard.glb": "x"})
    found = clips.catalog(cfg)
    assert found["Sword_slash"]["reference"]["file"].endswith("KinemIQ_Mannequin.fbx")
    sword = found["Sword_Regular_A"]
    assert "[" not in sword["file"]                          # Blender's glTF importer refuses a path with brackets
    assert sword["reference"] == {"file": sword["file"], "action": "A_TPose"}
    assert (where / "quaternius" / "UAL2_Standard.glb").read_text() == "x"


def test_a_person_who_has_not_been_made_is_refused(tmp_path):
    cfg = SimpleNamespace(blender=CFG.blender, data_dir=tmp_path)
    with pytest.raises(ValueError, match="hasn't been made"):
        blender_render.render_segment(cfg, {"from": 0, "to": 1, "people": {"a": {"person": "nobody"}}}, tmp_path / "f")


@needs_blender
def test_cycles_renders_the_same_shot(tmp_path):
    tracks = blender_render.render_shot(CFG, "portrait", tmp_path / "f", size=(108, 192), samples=2, frames=[1],
                                        person=_fake_person(tmp_path), engine="cycles")
    assert tracks["rendered"] == [1]
    assert (tmp_path / "f" / "f_0001.png").stat().st_size > 0


@needs_blender
def test_a_person_is_made_through_the_add_on_and_saved(tmp_path, monkeypatch):
    """With the stub standing in: enabled under --factory-startup, handed the content folder and this system's paths,
    saved, and made again only when the spec changes."""
    _downloads(tmp_path)
    (tmp_path / "addon" / "HumGen3D").mkdir(parents=True)
    stub = TESTS / "stub_humgen" / "HumGen3D" / "__init__.py"
    cfg = SimpleNamespace(blender={**CFG.blender, "humgen": str(tmp_path)}, data_dir=CFG.data_dir)
    monkeypatch.setenv("FAKE_PERSON_SCRIPT", str(TESTS / "blender_fake_person.py"))
    humgen.install(cfg, lambda _: None)
    (tmp_path / "addon" / "HumGen3D" / "__init__.py").write_text(stub.read_text(encoding="utf-8"), encoding="utf-8")

    spec = {"preset": os.path.join("models", "male", "Asian 3.json"),
            "hair": os.path.join("hair", "head", "male", "Short.json"),
            "outfit": os.path.join("outfits", "male", "Tee.blend"), "hair_color": {"lightness": 0.3}}
    made = blender_render.make_person(cfg, spec, tmp_path / "made", lambda _: None)
    assert made["spec"] == spec and made["rig"] == "FakeRig"
    assert "jawOpen" in made["face_keys"]
    assert made["settings"]["calls"] == [["hair", spec["hair"]], ["outfit", spec["outfit"]]]
    saved = tmp_path / "made" / "person.blend"
    stamp = saved.stat().st_mtime_ns
    blender_render.make_person(cfg, spec, tmp_path / "made", lambda _: None)
    assert saved.stat().st_mtime_ns == stamp
    assert json.loads((tmp_path / "made" / "person.json").read_text(encoding="utf-8"))["spec"] == spec

    tracks = blender_render.render_shot(CFG, "portrait", tmp_path / "f", size=(108, 192), samples=1, frames=[1],
                                        person=tmp_path / "made")
    assert tracks["rendered"] == [1]

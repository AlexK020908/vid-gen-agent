"""The owner's standard, as checks (Nov 4, 2026): "every subsequent video should be made with precision and respects physical
boundaries and remove bad glows and placements". Scenes are stopped from wobbling before Blender starts, and staged scenes are
measured from their meshes: what rests on what, how a spin turns, how a hat sits, and what gets refused."""
import json
import math
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from core import config
from render import assets, blender_render, clips
from scenes import direction as short
from scenes import spec as scene_spec
from things import build, get
from things import spec as thing_spec

CFG = config.load()
TESTS = Path(__file__).resolve().parent
needs_blender = pytest.mark.skipif(blender_render.missing(CFG) is not None, reason="Blender isn't installed")
MENU = {"pan": {"moves": [], "spots": ["base", "floor"], "lines": ["handle"]}, "stand": {"moves": [], "spots": ["top"], "lines": []}}
BASE = {"length": 3.0, "set": "sky_counter",
        "cast": {"stand": {"type": "prop", "prop": "stand", "on": "set", "at": [0, 0]},
                 "pan": {"type": "prop", "prop": "pan", "on": "stand", "by": "base", "onto": "top"}},
        "happens": [], "shots": [{"t": 0, "on": "pan:floor", "frame": 0.4, "angle": [0, 60], "square": True}]}


def _problems(**change):
    return scene_spec.check({**BASE, **change}, [], [], MENU)


def _shots(*shots):
    return _problems(shots=[{"on": "pan:floor", "square": True, **s} for s in shots])


def test_a_good_scene_passes():
    assert _problems() == []


def test_a_small_swing_between_two_shots_of_one_size_is_refused_as_wobble():
    wobble = _shots({"t": 0, "frame": 0.4, "angle": [4, 60]}, {"t": 1, "frame": 0.42, "angle": [-4, 62]})
    assert "wobbling" in wobble[0]
    assert _shots({"t": 0, "frame": 0.4, "angle": [0, 60]}, {"t": 1, "frame": 0.8, "angle": [0, 60]}) == []      # clearly another size
    assert _shots({"t": 0, "frame": 0.4, "angle": [0, 10]}, {"t": 1, "frame": 0.4, "angle": [0, 60]}) == []      # clearly another angle
    assert _shots({"t": 0, "frame": 0.4, "angle": [0, 60]}, {"t": 1, "frame": 0.4, "angle": [0, 60]}) == []      # the same shot


def test_a_glide_goes_somewhere_and_nobody_can_lose_it():
    assert _shots({"t": 0, "frame": 0.4, "angle": [0, 60], "to": {"frame": 0.2, "angle": [40, 30], "ease": "out"}}) == []
    assert _shots({"t": 0, "frame": 0.4, "angle": [0, 60], "to": {"on": "stand:top", "frame": 0.8}}) == []
    assert "too fast to follow" in " ".join(_shots({"t": 0, "frame": 8.0, "angle": [0, 60], "to": {"frame": 0.1}}))
    assert "too fast to follow" in " ".join(_shots({"t": 0, "frame": 0.4, "angle": [0, 60], "to": {"angle": [170, 60]}}, {"t": 0.5, "frame": 2.0, "angle": [0, 60]}))
    assert "to on" in " ".join(_shots({"t": 0, "frame": 0.4, "to": {"on": "nobody:top"}}))


def test_a_shot_can_place_its_subject_anywhere_in_the_picture():
    assert _shots({"t": 0, "frame": 0.4, "shift": [0, -0.2], "to": {"shift": [0.1, 0]}}) == []
    assert "shift" in " ".join(_shots({"t": 0, "frame": 0.4, "shift": [0, -0.7]}))
    assert "shift" in " ".join(_shots({"t": 0, "frame": 0.4, "to": {"shift": "low"}}))


RUNNER = {"walt": {"type": "person", "character": "walt", "at": [0, -5], "facing": 180, "stance": "Idle_relaxed"}, **BASE["cast"]}


def _walk(**event):
    walk = {"do": "walk", "t": 0, "who": "walt", "to": [0, -1], "over": 1.0, "clip": "Run", **event}
    return scene_spec.check({**BASE, "cast": RUNNER, "happens": [walk]}, ["walt"], ["Idle_relaxed", "Run"], MENU)


def test_someone_goes_the_way_theyre_facing_and_what_they_hit_has_to_be_there():
    assert _walk() == []
    assert _walk(hits="stand", **{"with": "forehead"}, slow=[0.3, 0.2]) == []
    assert "isn't the way they're facing" in " ".join(_walk(to=[4, -5]))
    assert "isn't the way they're facing" in " ".join(_walk(to=[0, -9]))
    assert "isn't in the cast" in " ".join(_walk(hits="nobody"))
    assert "with" in " ".join(_walk(**{"with": "elbow"}))
    assert "slow" in " ".join(_walk(slow=[2.0, 0.2]))           # longer than the walk
    assert "slow" in " ".join(_walk(slow=[0.3, 1.5]))           # faster, not slower
    assert "clip" in " ".join(_walk(clip="Moonwalk"))


def test_a_walk_goes_on_from_where_the_last_one_ended():
    """Facing +y, it's the second walk that turns back: measured from where the first ended, not from where they started."""
    there = {"do": "walk", "t": 0, "who": "walt", "to": [0, -1], "over": 0.5, "clip": "Run"}
    on = {"do": "walk", "t": 0.5, "who": "walt", "to": [0, 0], "over": 0.5, "clip": "Run"}
    back = {"do": "walk", "t": 0.5, "who": "walt", "to": [0, -3], "over": 0.5, "clip": "Run"}
    check = lambda *walks: scene_spec.check({**BASE, "cast": RUNNER, "happens": list(walks)}, ["walt"], ["Idle_relaxed", "Run"], MENU)
    assert check(there, on) == []
    assert "isn't the way they're facing" in " ".join(check(there, back))


def test_a_push_fast_enough_to_throb_is_refused():
    assert "throbs" in _shots({"t": 0, "frame": 0.4, "angle": [0, 60], "push": 0.2}, {"t": 1, "frame": 0.8, "angle": [0, 60]})[0]
    assert _shots({"t": 0, "frame": 0.4, "angle": [0, 60], "push": 0.04}, {"t": 1, "frame": 0.8, "angle": [0, 60]}) == []


@pytest.mark.parametrize("cast, says", [
    ({"stand": {"type": "prop", "prop": "stand", "on": "nothing"}}, "isn't in the cast"),
    ({"stand": {"type": "prop", "prop": "stand", "on": "stand"}}, "on itself"),
    ({"stand": {"type": "prop", "prop": "stand", "on": "set", "at": [0, 0, 1]}}, "just [x, y]"),
    ({"stand": {"type": "prop", "prop": "stand", "on": "set"}, "pan": {"type": "prop", "prop": "pan", "on": "stand", "by": "nowhere"}}, "by 'nowhere'"),
    ({"stand": {"type": "prop", "prop": "stand", "on": "set"}, "pan": {"type": "prop", "prop": "pan", "on": "stand", "onto": "nowhere"}}, "onto 'nowhere'"),
    ({"ball": {"type": "prop", "prop": "ball", "on": "set"}}, "only a thing"),
    ({"stand": {"type": "prop", "prop": "stand", "on": "set"}, "pan": {"type": "prop", "prop": "pan", "to": "stand"}}, "needs a spot"),
    ({"stand": {"type": "prop", "prop": "stand", "on": "set"}, "pan": {"type": "prop", "prop": "pan", "to": "stand:nowhere"}}, "needs a spot"),
    ({"stand": {"type": "prop", "prop": "stand", "on": "set"}, "pan": {"type": "prop", "prop": "pan", "to": "nobody:top"}}, "isn't a thing"),
    ({"stand": {"type": "prop", "prop": "stand", "on": "set"}, "pan": {"type": "prop", "prop": "pan", "to": "stand:top", "by": "nowhere"}}, "by 'nowhere'"),
    ({"stand": {"type": "prop", "prop": "stand", "on": "set"}, "pan": {"type": "prop", "prop": "pan", "to": "stand:top", "on": "set"}}, "not both"),
])
def test_a_bad_resting_place_is_refused_with_the_reason(cast, says):
    problems = _problems(cast=cast, shots=[{"t": 0, "on": f"{next(iter(cast))}:", "frame": 1}])
    assert any(says in p for p in problems), problems


@pytest.mark.parametrize("event, says", [
    ({"do": "spin", "t": 0, "prop": "pan", "axis": "w"}, "axis"),
    ({"do": "spin", "t": 0, "prop": "pan", "about": "nowhere"}, "about 'nowhere'"),
    ({"do": "slide", "t": 0, "prop": "pan", "over": 1}, "from or by"),
    ({"do": "slide", "t": 0, "prop": "pan", "over": 1, "from": [0, 0, 1], "by": [0, 0, 1]}, "from or by"),
    ({"do": "slide", "t": 0, "prop": "pan", "over": 1, "from": [0, 1]}, "[x, y, z]"),
    ({"do": "lit", "t": 0, "on": "pan:nowhere", "color": "red"}, "isn't a spot"),
    ({"do": "lit", "t": 0, "on": "pan", "color": "red", "radius": 0.1}, "needs a spot"),
    ({"do": "lit", "t": 0, "on": "pan", "color": "pink"}, "color"),
    ({"do": "flow", "t": 0, "on": "pan:floor", "color": "green"}, "needs radii"),
    ({"do": "flow", "t": 0, "on": "pan", "color": "green", "along": "nowhere"}, "isn't a line"),
    ({"do": "flow", "t": 0, "on": "pan", "color": "green", "radii": [0.1], "side": "left"}, "side"),
    ({"do": "tint", "t": 0, "prop": "pan", "color": "pink"}, "color is one of"),
])
def test_a_bad_use_of_light_or_motion_is_refused_with_the_reason(event, says):
    problems = _problems(happens=[event])
    assert any(says in p for p in problems), problems


def test_what_may_touch_has_to_be_in_the_cast():
    assert "pair of cast ids" in _problems(touching=[["pan", "nobody"]])[0]


def test_a_mark_is_checked_and_drawn():
    assert short.mark_problems([{"kind": "count", "from": 1, "to": 2, "start": 0, "end": 9, "text": "A SECOND"}], 5) == []
    assert "from and to" in short.mark_problems([{"kind": "count", "from": 3, "to": 9, "start": 0, "end": 9, "text": "A"}], 5)[0]
    assert "text" in short.mark_problems([{"kind": "count", "from": 1, "to": 2, "start": 0, "end": 9}], 5)[0]
    assert "kind" in short.mark_problems([{"kind": "ball"}], 5)[0]
    assert short.tags([{"kind": "count", "from": 1, "to": 2}])[0]["at"] == [0.5, 0.36]


PARTS = [{"id": "base", "kind": "cylinder", "r": 0.1, "h": 0.02, "material": "steel"},
         {"id": "wire", "kind": "spiral", "r_in": 0.01, "r_out": 0.09, "turns": 3, "wire": 0.004, "at": [0, 0, 0.02], "material": {"color": [0.6, 0.2, 0.0], "metal": 0.8}}]


def test_a_built_thing_needs_no_size_and_its_parts_are_checked():
    assert thing_spec.check({"what": "a coil", "source": {"kind": "built", "parts": PARTS}}) == []
    assert "meters: missing" in thing_spec.check({"what": "a pan", "source": {"kind": "polyhaven", "asset": "x"}})
    bad = [{**PARTS[0], "material": "gold"}, {**PARTS[1], "material": {"color": [2, 0, 0]}}, {**PARTS[1], "id": "w2", "r_in": 0.2, "material": {"color": [1, 0, 0], "shine": 1}}]
    problems = thing_spec.check({"what": "a coil", "source": {"kind": "built", "parts": bad}})
    assert any("palette" in p for p in problems)
    assert any("color has to be" in p for p in problems)
    assert any("has no shine" in p for p in problems)
    assert any("r_in" in p for p in problems)


def test_a_built_thing_fetches_nothing_and_costs_nothing(tmp_path):
    got = get.fetch(CFG, {"kind": "built", "parts": PARTS}, tmp_path / "s", say=lambda _: None)
    assert got["usd"] == 0 and got["license"] == "own" and not (tmp_path / "s").exists()


def test_a_shot_too_close_for_a_things_texture_is_refused_and_says_how_near_it_can_go():
    from things.build import sharp_from
    assert sharp_from({"texels_per_meter": 1920}) == 0.5                  # a texel to two screen pixels at 0.5 m of picture
    assert sharp_from({"texels_per_meter": None}) == 0 and sharp_from(None) == 0
    things = {"bird": {"moves": [], "spots": ["head"], "lines": [], "sharp_from": 0.5}}
    def scene(frame, size=1.0):
        return {"length": 1.0, "set": "sky_set", "cast": {"it": {"type": "prop", "prop": "bird", "at": [0, 0, 0], "size": size}},
                "shots": [{"t": 0, "on": "it:head", "frame": frame, "angle": [0, 0], "lens": 26}]}
    assert not any("blurry" in p for p in scene_spec.check(scene(0.6), [], [], things))
    assert any("only sharp from 0.5 m" in p for p in scene_spec.check(scene(0.2), [], [], things))
    assert not any("blurry" in p for p in scene_spec.check(scene(0.2, size=0.3), [], [], things))       # made smaller, it can be nearer


def test_a_scene_can_turn_a_thing_to_glass_to_show_whats_inside():
    things = {"skull": {"moves": [], "spots": [], "lines": [], "sharp_from": 0}}
    base = {"length": 1.0, "set": "sky_set", "cast": {"it": {"type": "prop", "prop": "skull", "at": [0, 0, 0]}},
            "shots": [{"t": 0, "on": "it:", "frame": 0.5, "angle": [0, 0], "lens": 26}]}
    good = {**base, "happens": [{"do": "ghost", "t": 0, "prop": "it", "color": "ice"}]}
    assert not any("ghost" in p or "happens" in p for p in scene_spec.check(good, [], [], things))
    assert any("color" in p for p in scene_spec.check({**base, "happens": [{"do": "ghost", "t": 0, "prop": "it", "color": "plaid"}]}, [], [], things))


def test_every_example_scene_keeps_to_the_standard():
    menu = build.menu(CFG)
    from characters import spec as character_spec
    for path in (TESTS.parent / "scenes" / "examples").glob("*.json"):
        scene = scene_spec.load(path)
        stances = sorted({c["stance"] for c in scene["cast"].values() if c["type"] == "person"})
        assert scene_spec.check(scene, character_spec.all_ids(), stances, menu) == [], path.name


@pytest.fixture(scope="module")
def measured(tmp_path_factory):
    from tests.test_characters import _fake_person
    if blender_render.missing(CFG) or clips.missing(CFG):
        pytest.skip("needs Blender and the free body clips")
    tmp = tmp_path_factory.mktemp("precision")
    block = {"what": "a block", "source": {"kind": "built", "parts": [{"id": "body", "kind": "box", "size": [0.2, 0.2, 0.1], "bevel": 0.002, "at": [0, 0, 0.05], "material": "steel"}]},
             "spots": {"under": [0, 0, 0], "over": [0, 0, 0.1], "off_middle": [0.05, 0, 0.05]}}
    dome = {"what": "a hat", "source": {"kind": "built", "parts": [{"id": "dome", "kind": "lathe", "segments": 48,
            "points": [[0.11, 0.0], [0.09, 0.07], [0.0, 0.12], [0.0, 0.115], [0.086, 0.066], [0.106, 0.0]], "material": "steel"}]}}
    corner = {"what": "a wall with a wing that reaches forward, so its bounding box holds a lens in front of the wall", "source": {"kind": "built", "parts": [
              {"id": "wall", "kind": "box", "size": [2.4, 0.05, 1.0], "bevel": 0.002, "at": [0, 0.5, 0.5], "material": "steel"},
              {"id": "wing", "kind": "box", "size": [0.05, 1.8, 1.0], "bevel": 0.002, "at": [1.2, -0.4, 0.5], "material": "steel"}]}}
    wall = {"what": "a wall", "source": {"kind": "built", "parts": [{"id": "wall", "kind": "box", "size": [3.0, 0.1, 3.0], "bevel": 0.002, "at": [0, 0, 1.5], "material": "steel"}]}}
    rod = {"what": "a rod with many rings to it, so a bend shows", "source": {"kind": "built", "parts": [
           {"id": "rod", "kind": "lathe", "points": [[0.0, 0.0], *[[0.02, i * 0.02] for i in range(21)], [0.0, 0.4]], "segments": 16, "material": "steel"}]},
           "spots": {"base": [0, 0, 0], "neck": [0, 0, 0.2], "tip": [0, 0, 0.4]}}
    # a closed hollow box, and a round thing to go inside it
    shell = {"what": "a hollow box", "source": {"kind": "built", "parts": [
             {"id": "floor", "kind": "box", "size": [0.5, 0.5, 0.01], "at": [0, 0, 0.005], "material": "steel"}, {"id": "roof", "kind": "box", "size": [0.5, 0.5, 0.01], "at": [0, 0, 0.495], "material": "steel"},
             {"id": "left", "kind": "box", "size": [0.01, 0.5, 0.5], "at": [-0.245, 0, 0.25], "material": "steel"}, {"id": "right", "kind": "box", "size": [0.01, 0.5, 0.5], "at": [0.245, 0, 0.25], "material": "steel"},
             {"id": "near", "kind": "box", "size": [0.5, 0.01, 0.5], "at": [0, -0.245, 0.25], "material": "steel"}, {"id": "far", "kind": "box", "size": [0.5, 0.01, 0.5], "at": [0, 0.245, 0.25], "material": "steel"}]}}
    round_side = [[round(0.1 * math.sin(i * math.pi / 12), 5), round(0.1 - 0.1 * math.cos(i * math.pi / 12), 5)] for i in range(1, 12)]
    orb = {"what": "a ball", "source": {"kind": "built", "parts": [{"id": "ball", "kind": "lathe", "segments": 32, "points": [[0.0, 0.0], *round_side, [0.0, 0.2]], "material": "steel"}]}}
    for name, spec in (("block", block), ("hat", dome), ("corner", corner), ("wall", wall), ("rod", rod), ("shell", shell), ("orb", orb)):
        blender_render.make_thing(CFG, spec, {"file": "", "license": "own", "credit": ""}, tmp / name)
    found = clips.catalog(CFG)
    job = {"folders": {"walt": str(_fake_person(tmp))}, "catalog": {name: found[name] for name in ("Idle_relaxed", "Walk_forwards", "Run_jog_forwards", "Hit_to_the_head", "Death_fall_backwards")},
           "things": {name: str(tmp / name) for name in ("block", "hat", "corner", "wall", "rod", "shell", "orb")}, "out": str(tmp),
           "textures": {t: assets.texture(CFG.data_dir, t) for t in blender_render.TEXTURES}}
    (tmp / "job.json").write_text(json.dumps(job), encoding="utf-8")
    done = subprocess.run([str(blender_render.exe(CFG)), "-b", "--factory-startup", "--python-exit-code", "1", "-P",
                           str(TESTS / "blender_precision_check.py"), "--", str(tmp / "job.json")], capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert done.returncode == 0, (done.stdout + done.stderr)[-3000:]
    return json.loads((tmp / "out.json").read_text(encoding="utf-8"))


@needs_blender
def test_a_thing_rests_exactly_on_what_its_on(measured):
    rest = measured["rest"]
    assert 0 < rest["on_set"] < 0.002 and 0 < rest["on_stand"] < 0.002     # touching, by less than 2 mm, and not sunk in
    assert rest["across"] < 0.001


@needs_blender
def test_a_thing_fixed_to_another_meets_it_exactly_and_isnt_refused_for_overlapping(measured):
    assert measured["fixed"] < 0.00001


@needs_blender
def test_a_spin_turns_about_one_exact_axis_at_its_rate(measured):
    assert measured["spin"]["wandered"] < 0.0001                            # the axle doesn't move
    x, y, z = measured["spin"]["up_after_84"]
    assert abs(x) < 0.001 and y < -0.9 and abs(z) < 0.3                     # about 84 degrees round x


@needs_blender
def test_a_slide_stays_level_and_ends_exactly_where_it_rests(measured):
    slide = measured["slide"]
    assert slide["most_tilt"] < 0.001                                       # it never pitches like a bird landing
    assert slide["start_above_end"] == pytest.approx(0.4, abs=0.001)
    assert 0 < slide["gap_at_end"] < 0.002 and slide["crossing"] == 0


@needs_blender
def test_a_hat_sits_on_the_head_it_was_fitted_to(measured):
    hat = measured["hat"]
    assert hat["hat_top"] > hat["head_top"]                                 # the head's inside it, not through it
    assert hat["hat_top"] - hat["head_top"] < 0.06                          # and it's on the head, not hovering above
    assert hat["rim"] < hat["head_top"] - 0.025                             # its rim comes down round the head
    assert hat["rim"] > hat["eyes"]                                         # and stops above the eyes
    assert hat["off_centre"] < 0.01


@needs_blender
def test_what_isnt_physically_right_is_refused_in_words(measured):
    assert any("pass through each other" in p for p in measured["through"])
    assert any("hangs in the air" in p for p in measured["hanging"])
    assert any("in front of the lens" in p for p in measured["in_the_way"])
    assert any("under the counter" in p for p in measured["lens_under"])
    assert any("pass through each other" in p for p in measured["slide_through"])    # moving, not just as it starts


@needs_blender
def test_a_wall_behind_the_subject_isnt_in_the_way_but_one_between_them_is(measured):
    """Found on a woodpecker against a wide trunk: a lens inside its bounding box was refused for a trunk behind the bird."""
    assert not any("lens" in p for p in measured["wall_behind"])
    assert any("lens" in p for p in measured["wall_between"])


@needs_blender
def test_a_hit_throws_as_many_chips_as_it_says(measured):
    assert measured["chips"] == 6


@needs_blender
def test_what_was_said_to_float_or_touch_is_let_be(measured):
    assert measured["said_to_float"] == []
    assert measured["said_to_touch"] == []


@needs_blender
def test_a_glow_stays_on_its_thing(measured):
    flow = measured["flow"]
    assert flow["lines"] > 0
    assert flow["furthest_past_edge"] < 0.005      # a circle half a meter wide on a 20 cm block stops at the block's edge
    assert measured["balls"] == []                 # and nothing's a ball of light


def test_a_refusal_says_every_reason_from_a_stage(tmp_path, monkeypatch):
    from scenes import render as filming
    (tmp_path / "frames").mkdir()

    def refuses(*args, **kwargs):
        (tmp_path / "frames" / "refused.json").write_text(json.dumps(["a and b pass through each other", "c hangs in the air"]), encoding="utf-8")
        raise RuntimeError("blender failed on stage")

    monkeypatch.setattr(filming.blender_render, "render_stage", refuses)
    real = {"length": 1.0, "set": "sky_counter", "cast": {"stand": {"type": "prop", "prop": "ring_stand", "on": "set", "at": [0, 0]}},
            "shots": [{"t": 0, "on": "stand:top", "frame": 0.6, "square": True}]}
    with pytest.raises(scene_spec.Refused) as caught:
        filming.film(CFG, real, tmp_path, frames=[1], say=lambda _: None)
    assert caught.value.problems == ["a and b pass through each other", "c hangs in the air"]


class _Built:
    """What a stage needs around a thing being built: its reply from the look, and a note book, with nothing started."""

    def __init__(self, monkeypatch, tmp_path, right, notes=()):
        from stages import direct
        self.direct = direct
        self.written, self.told, self.notes = [], [], list(notes)
        monkeypatch.setattr(direct.thing_spec, "path_for", lambda tid: tmp_path / f"{tid}.json")
        monkeypatch.setattr(direct.thing_build, "build", lambda config, tid, say=None, spec=None: {
            "manifest": {"size": [0.2, 0.2, 0.1], "clips": {}}, "sheet": "sheet.png"})
        monkeypatch.setattr(direct.db, "notes", lambda conn, vid, stage: list(self.notes))
        monkeypatch.setattr(direct.db, "add_feedback", lambda conn, vid, stage, note: self.notes.append(note))

        class _Tx:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        monkeypatch.setattr(direct.db, "tx", lambda conn: _Tx())
        looked = {"seen": "a coil", "right_thing": right, "problems": ["its wire floats"]}
        self.ctx = SimpleNamespace(config=CFG, llm=SimpleNamespace(check_thing=lambda *a: looked),
                                   events=SimpleNamespace(emit=lambda kind, vid, text: self.told.append(text)))

    def build(self, tmp_path):
        return self.direct._get_thing(self.ctx, None, {"id": 1}, None, {"id": "coil_thing", "what": "a coil", "parts": PARTS, "spots": {"middle": [0, 0, 0]}},
                                      lambda what: None)


def test_a_built_thing_that_looks_right_goes_in_the_library(tmp_path, monkeypatch):
    built = _Built(monkeypatch, tmp_path, right=True)
    assert built.build(tmp_path) == "coil_thing"
    spec = json.loads((tmp_path / "coil_thing.json").read_text(encoding="utf-8"))
    assert spec["source"]["kind"] == "built" and thing_spec.check(spec) == [] and spec["spots"] == {"middle": [0, 0, 0]}


def test_a_built_thing_that_looks_wrong_goes_back_to_be_written_again(tmp_path, monkeypatch):
    built = _Built(monkeypatch, tmp_path, right=False)
    assert built.build(tmp_path) is None
    assert built.notes[0].startswith(built.direct.BUILT_NOTE) and "its wire floats" in built.notes[0]
    assert not (tmp_path / "coil_thing.json").exists() and built.told == []


def test_a_built_thing_that_keeps_looking_wrong_is_left_out_and_the_owner_told(tmp_path, monkeypatch):
    from stages import direct
    built = _Built(monkeypatch, tmp_path, right=False, notes=[f"{direct.BUILT_NOTE}{i}" for i in range(direct.MOST_REBUILDS)])
    assert built.build(tmp_path) is None
    assert len(built.notes) == direct.MOST_REBUILDS and "still doesn't look right" in built.told[0]


def test_what_a_short_asks_to_build_is_checked_as_it_comes_in():
    from stages import direct
    check = direct._check_cast(SimpleNamespace(config=SimpleNamespace(mode="stub")))
    person = {"id": "walt", "plays": "a man", "spec": {}}
    good = {"id": "a_new_coil", "what": "a coil", "search": "", "meters": 0, "moves": False, "parts": PARTS}
    assert check({"people": [person], "things": [good]}) == []
    assert any("thing a_new_coil" in p and "palette" in p for p in check({"people": [person], "things": [{**good, "parts": [{**PARTS[0], "material": "gold"}]}]}))
    assert any("says search" in p for p in check({"people": [person], "things": [{"id": "x", "what": "a bird", "search": "", "meters": 1, "moves": False, "parts": []}]}))


def test_the_brief_describes_a_built_thing_that_hasnt_been_made_yet(tmp_path, monkeypatch):
    """It has no meters, and the director's brief used to fall over on that."""
    from stages import direct
    (tmp_path / "coil_thing.json").write_text(json.dumps({"what": "a coil", "source": {"kind": "built", "parts": PARTS}, "spots": {"middle": [0, 0, 0]}}), encoding="utf-8")
    monkeypatch.setattr(direct.thing_spec, "path_for", lambda tid: tmp_path / f"{tid}.json")
    monkeypatch.setattr(direct.thing_build, "made", lambda config, tid: None)
    text = direct._things_text(CFG, ["coil_thing"])
    assert "a coil" in text and "Spots: middle" in text and "Parts: base, wire" in text and "Lines: wire" in text


def test_a_refused_scene_goes_back_to_the_director_a_few_times_then_stops(tmp_path, monkeypatch):
    """Whenever a scene's refused, after the look too, the director hears why. If it never comes right, the owner does."""
    from core.errors import FinalError
    from stages import film

    def refuses(*a):
        raise scene_spec.Refused(["a and b pass through each other"])

    monkeypatch.setattr(film, "_film_all", refuses)
    monkeypatch.setattr(film, "timeline", lambda ctx, conn, video: {"lines": [], "total": 1.0})
    monkeypatch.setattr(film, "_stub", lambda ctx: False)
    notes, told, updates = [], [], []
    monkeypatch.setattr(film.db, "add_feedback", lambda conn, vid, stage, note: notes.append(note))
    monkeypatch.setattr(film.db, "update_video", lambda conn, vid, **values: updates.append(values))

    class _Tx:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(film.db, "tx", lambda conn: _Tx())
    ctx = SimpleNamespace(channel=lambda cid: None, events=SimpleNamespace(emit=lambda kind, vid, text: told.append(text)))
    video = {"id": 1, "channel_id": "shorts", "direction_json": json.dumps({"scenes": [], "look": 1}), "direction_draft_json": json.dumps({"scenes": [], "refused": 1})}
    film._work(ctx, None, video)
    assert notes == [f"{film.direct.LOOK_NOTE}a and b pass through each other"] and "isn't physically right" in told[0]
    assert updates[0]["direction_json"] is None and json.loads(updates[0]["direction_draft_json"])["refused"] == 2
    video["direction_draft_json"] = json.dumps({"scenes": [], "refused": film.MOST_REFUSALS})
    with pytest.raises(FinalError, match="still isn't physically right"):
        film._work(ctx, None, video)


@needs_blender
def test_someone_running_into_something_stops_exactly_where_their_body_meets_it(measured):
    hit = measured["hit"]
    assert abs(hit["reach_at_arrival"]) < 0.002                 # touching, to 2 mm, with what's measured off the meshes
    assert hit["crossing_at_arrival"] < 0.003
    assert hit["reach_after"] > 0.05                            # and they bounce back off it
    assert hit["moved_back"] == pytest.approx(0.14, abs=0.001)  # by what the rig was told, from where it stopped
    assert hit["speed_in_slow_motion"] < hit["speed_running"] * 0.25


@needs_blender
def test_a_walking_moves_own_travel_isnt_added_to_the_walk(measured):
    """The clip carries the hips 1.4 m by itself. Left in, a man goes twice as far and jumps back at every loop of it."""
    assert measured["walk"]["ends_at"] == pytest.approx(measured["walk"]["told"], abs=0.001)
    assert measured["walk"]["hips_from_rig"] < 0.15             # the hips stay over the rig
    assert measured["walk"]["biggest_jump"] < 0.08              # a hip never moves more than a step's worth in a frame


@needs_blender
def test_a_walk_at_a_speed_its_steps_cant_do_is_refused_with_what_they_can(measured):
    assert any("own steps go" in p and "m/s" in p for p in measured["too_fast"])


@needs_blender
def test_someone_running_through_something_is_caught_between_the_old_checks(measured):
    """The old check looked at people once in ten frames, or only at the ends of a scene: a runner goes through a tree between them."""
    assert any("pass through each other" in p for p in measured["ran_through"])


@needs_blender
def test_a_shot_following_someone_doesnt_bounce_with_their_steps(measured):
    assert measured["follow"]["aim_bounce"] < 0.012             # against the steps it follows, in meters
    assert measured["follow"]["hips_bounce"] > 0.02             # which do bounce
    assert measured["follow"]["stays_with_them"] < 0.25


@needs_blender
def test_lights_go_with_who_theyre_on(measured):
    assert measured["lights"]["key_moved"] == pytest.approx(measured["lights"]["walked"], abs=0.001)


@needs_blender
def test_who_falls_can_stay_down(measured):
    stayed = measured["fall"]
    assert stayed["hips_when_done"] < stayed["hips_standing"] - 0.3    # on the ground: the stand-in's bones fall, and its head's fixed to the rig
    assert stayed["hips_later"] == pytest.approx(stayed["hips_when_done"], abs=0.005)    # and it stays there
    assert stayed["shadow_under_hips"] < 0.001


@needs_blender
def test_whats_planted_below_the_set_is_hidden_by_a_floor_nobody_can_see(measured):
    assert measured["floor"]["height"] == 0
    assert measured["floor"]["casts_no_shadow"]


@needs_blender
def test_a_squash_presses_along_its_axis_keeps_its_volume_and_comes_back(measured):
    squash = measured["squash"]
    assert 0.8 < squash["pressed"] < 0.9                        # about what it was told, along its axis, a frame or two in
    assert squash["wider"] > 1.05                               # wider the other ways
    assert squash["underside_moved"] < 0.0005                   # and on the counter, it stays on the counter, rather than spreading down through it
    assert squash["after"] == pytest.approx(1.0, abs=0.001)     # and it ends as it was


@needs_blender
def test_a_rock_with_a_part_bends_only_that_part(measured):
    bend = measured["bend"]
    assert bend["near_moved"] > 0.01
    assert bend["far_moved"] < 0.00001
    assert bend["root_moved"] < 0.00001


@needs_blender
def test_a_glide_starts_and_ends_where_it_says(measured):
    glide = measured["glide"]
    assert glide["start_distance"] == pytest.approx(glide["told_start"], abs=0.002)
    assert glide["end_distance"] == pytest.approx(glide["told_end"], abs=0.01)
    assert glide["biggest_step"] < 0.2                          # with no jump on the way


@needs_blender
def test_a_shift_moves_the_subject_in_the_picture_and_nothing_else(measured):
    assert measured["shift"]["x"] == pytest.approx(0.1 * 9 / 16, abs=1e-6)       # [-0.1, -0.2] puts it left and low in the picture, so the lens slides right and up
    assert measured["shift"]["y"] == pytest.approx(0.2, abs=1e-6)
    assert measured["shift"]["end_y"] == pytest.approx(0.0, abs=1e-6)


@needs_blender
def test_a_thing_against_a_crooked_surface_touches_it_with_both_its_spots(measured):
    against = measured["against"]
    assert against["first_gap"] < 0.002 and against["second_gap"] < 0.002
    assert abs(against["tipped"]) > 5                           # it had to tip to do it, on a surface that leans
    assert against["through"] == []                             # and it's let be


@needs_blender
def test_a_nail_goes_into_what_it_comes_up_against_by_as_much_as_it_says(measured):
    assert measured["nail_in"] == pytest.approx(0.03, abs=0.002)


@needs_blender
def test_glass_on_part_of_a_thing_leaves_the_rest_as_it_was(measured):
    part = measured["part"]
    assert part["near_spot"] > 0.99 and part["far_from_it"] == 0     # marked on the points, so it stays on them as they bend
    assert not part["culled"]                                        # a scan's full of tiny gaps: with its far side gone everywhere, each shows the sky
    assert part["seen_from_inside"]                                  # it goes when it's seen from inside, through the window
    assert not measured["whole_seen_from_inside"]                    # an x-ray of the whole thing keeps its far side: that's what you're looking at


@needs_blender
def test_a_hole_in_a_scan_doesnt_fool_what_says_whats_inside_it(measured):
    """A scan isn't sealed: one ray through a hole said a point well outside a tree was 7 cm inside it."""
    shell = measured["open_shell"]
    assert shell["inside"] is True             # though the ray straight up goes out through the hole
    assert shell["beside"] is False
    assert shell["under"] is False             # though the ray straight up goes in through its floor and out through the hole


@needs_blender
def test_someone_running_keeps_time_with_their_steps_and_lands_with_a_thud(measured):
    steps = measured["sounds"]["steps"]
    assert len(steps) >= 4                                      # a running man's feet
    gaps = [b - a for a, b in zip(steps, steps[1:])]
    assert max(gaps) - min(gaps) <= 3                           # evenly
    assert steps[-1] <= measured["sounds"]["slow_from"] + 3     # and his slow motion is too slow for another step
    assert measured["sounds"]["lands"] == [measured["sounds"]["expected_land"]]
    assert measured["sounds"]["stands_silent"] == []            # a flinch on their feet doesn't thud


@needs_blender
def test_whats_inside_a_thing_goes_where_it_goes_and_isnt_part_of_it(measured):
    """Found by the frame reviewer: a skull and the brain in it each had to be moved on their own, and could come apart. And once one rode in the other, turning the outer one to glass took the inner one with it."""
    carried = measured["carried"]
    assert carried["outer_moved"] == pytest.approx(0.4, abs=0.02) and carried["moved"] == pytest.approx(carried["outer_moved"], abs=0.005)
    assert not carried["part_of_it"]


@needs_blender
def test_something_inside_stops_at_the_wall_ahead_of_it_and_takes_its_shape(measured):
    """Found by the frame reviewer: a brain never reached the forehead it was said to slam into, because rays started outside the skull and met its back wall first."""
    press = measured["press"]
    assert press["wall"] - 0.004 < press["front"] <= press["wall"] + 0.0005                  # it goes right up to the near side of the wall ahead
    assert press["back_after"] > press["back"] + 0.02                                        # the front's stopped, and the rest keeps coming
    assert press["front_after"] == pytest.approx(press["front"], abs=0.002)
    assert press["wide_after"] > press["wide_before"]                                        # what's squeezed goes somewhere
    assert press["on_the_wall_after"] > press["on_the_wall_before"] * 2                      # and its front goes flat on what stopped it
    assert press["pokes"] == 0                                                               # and none of it goes through the wall


@needs_blender
def test_a_part_bends_until_it_touches_what_its_against(measured):
    bent = measured["bent"]
    assert bent["bent_by"] > 3 and bent["gap"] < 0.01


@needs_blender
def test_whats_in_someones_head_rides_on_it_and_their_head_goes_to_glass(measured):
    """Found by rendering it: a person's proportions come from shape keys, so marking their head from the mesh's own numbers marked their chin."""
    head = measured["in_head"]
    assert head["rides"] < 0.02 and head["travelled"] > 0.5
    assert head["marked_at_top"] > 0.9 and head["not_at_the_hips"] == 0
    assert head["eyes_go"]


@needs_blender
def test_whoever_goes_down_lands_goes_slack_and_breathes(measured):
    """Found by the frame reviewer: a body hit the ground stiff and frozen, staring, with its fists clenched."""
    down = measured["down"]
    assert down["thumped"] and down["still_moving"]


@needs_blender
def test_a_running_body_doesnt_twist_like_a_towel(measured):
    """Found by the frame reviewer: the pack's jog swings the shoulders 41 degrees each way while the hips stay still."""
    assert measured["run"]["kept"] < 1.0


@needs_blender
def test_what_slow_motion_has_frozen_stays_frozen(measured):
    """Found by rendering it: a man in very slow motion stood up the moment his run ended."""
    assert measured["frozen"] < 0.02


@needs_blender
def test_lights_come_from_in_front_of_someone_whichever_way_they_face(measured):
    """Found by the frame reviewer: facing the tree, a man was lit from behind, and his face went blotched and red."""
    assert measured["light"]["key_in_front"] > 1.0


def test_a_scene_can_press_dim_and_x_ray_a_head_and_is_told_when_it_cant():
    things = {"brain": {"moves": [], "spots": ["front"], "lines": [], "sharp_from": 0}, "tool": {"moves": [], "spots": ["grip", "end"], "lines": [], "sharp_from": 0}}
    from characters import spec as character_spec
    who = character_spec.all_ids()[0]
    cast = {"man": {"type": "person", "character": who, "at": [0, 0], "stance": "Idle_relaxed"}, "skull": {"type": "prop", "prop": "brain", "inside": "man", "by": "front"}, "brain": {"type": "prop", "prop": "brain", "inside": "skull"}}
    base = {"length": 1.0, "set": "place", "place": {"sky": "woods", "light": 0.2}, "cast": cast, "shots": [{"t": 0, "on": "man:eyes", "frame": 0.5, "angle": [0, 0], "lens": 26, "fstop": 8}]}
    check = lambda **more: scene_spec.check({**base, **more}, character_spec.all_ids(), ["Idle_relaxed"], things)
    assert check(happens=[{"do": "ghost", "t": 0, "who": "man"}, {"do": "dim", "t": 0, "level": 0.3}, {"do": "press", "t": 0.1, "prop": "brain", "amount": 0.2, "way": [0, 1, 0]}]) == []
    assert any("prop, or who" in p for p in check(happens=[{"do": "ghost", "t": 0}]))
    assert any("only a place" in p for p in scene_spec.check({k: v for k, v in {**base, "set": "sky_set", "happens": [{"do": "dim", "t": 0, "level": 0.3}]}.items() if k != "place"}, character_spec.all_ids(), ["Idle_relaxed"], things))
    assert any("amount" in p for p in check(happens=[{"do": "press", "t": 0.1, "prop": "brain", "amount": 0.9, "way": [0, 1, 0]}]))
    assert any("way" in p for p in check(happens=[{"do": "press", "t": 0.1, "prop": "brain", "amount": 0.2, "way": [0, 0, 0]}]))
    assert any("light" in p for p in scene_spec.check({**base, "place": {"sky": "woods", "light": 0}}, character_spec.all_ids(), ["Idle_relaxed"], things))
    assert any("by" in p for p in scene_spec.check({**base, "cast": {**cast, "skull": {"type": "prop", "prop": "brain", "inside": "man", "by": "nowhere"}}}, character_spec.all_ids(), ["Idle_relaxed"], things))
    assert "out_cold" in scene_spec.EXPRESSIONS


@needs_blender
def test_whats_inside_something_cant_show_outside_its_outline_from_the_lens(measured):
    """The owner, twice: "the brain is outside the sillouhote". Being surrounded isn't enough: what counts is what the lens sees."""
    assert measured["outline_within"] == []
    assert any("shows outside the outline of outer" in problem for problem in measured["outline_past"])


@needs_blender
def test_whats_on_something_that_moves_goes_with_it(measured):
    """Found by the frame reviewer: brains glided across a table with nothing moving them. On a sled, they go where it goes."""
    assert measured["rides_on"] == pytest.approx(0.4, abs=0.02)


@needs_blender
def test_part_of_a_thing_can_be_pressed_and_turned_to_other_stuff(measured):
    """A woodpecker's head gone to sponge, so a viewer sees why a sponge has come into it."""
    part = measured["part_pressed"]
    assert part["near_moved"] > 0.01 and part["far_moved"] < 0.001
    assert part["came_back"] < 0.001                 # with nothing left of it, as stays is 0
    assert part["turned_near"] > 0.99 and part["turned_far"] == 0


@needs_blender
def test_a_body_keeps_coming_when_its_head_has_stopped(measured):
    """Found by the frame reviewer: the whole man reversed at once, with no momentum carrying his body on."""
    keeps = measured["keeps_coming"]
    assert keeps["carry"] > 0
    assert keeps["rig_on"] > keeps["carry"] * 0.5        # his body comes on
    assert keeps["rig_back"] == pytest.approx(0.14, abs=0.002)      # and then he's thrown back
    assert keeps["touch_near_wall"] < 0.01               # and what a ring's aimed at is on what he hit


@needs_blender
def test_a_hit_lands_on_what_touched_rather_than_on_what_is_furthest_on(measured):
    """Measured after two reviews saw no ring when a head stopped: the rings and chips were round his swinging hand, out of the shot, as that was the furthest point of him."""
    slanted = measured["touch_slanted"]
    assert slanted["touch_to_wall"] < 0.01
    assert slanted["furthest_to_wall"] is None or slanted["furthest_to_wall"] > slanted["touch_to_wall"] + 0.01


def test_a_scene_says_what_a_part_turns_into_and_where_a_pit_is():
    things = {"bird": {"moves": [], "spots": ["head", "beak"], "lines": [], "sharp_from": 0}, "tree": {"moves": [], "spots": [], "lines": [], "sharp_from": 0}}
    base = {"length": 1.0, "set": "sky_set", "cast": {"it": {"type": "prop", "prop": "bird", "at": [0, 0, 0]}, "tree": {"type": "prop", "prop": "tree", "at": [1, 0, 0]}},
            "shots": [{"t": 0, "on": "it:head", "frame": 0.5, "angle": [0, 0], "lens": 26}]}
    check = lambda *events: scene_spec.check({**base, "happens": list(events)}, [], [], things)
    good = {"do": "turns", "t": 0, "prop": "it", "near": "head", "radius": 0.1, "into": {"color": [1, 1, 0], "pores": 0.003}}
    assert check(good) == []
    assert any("near" in p for p in check({**good, "near": "nowhere"}))
    assert any("color" in p for p in check({**good, "into": {"pores": 0.003}}))
    assert check({"do": "pit", "t": 0, "on": "tree", "at": "it:beak", "radius": 0.01}) == []
    assert any("thing from the library" in p for p in check({"do": "pit", "t": 0, "on": "nobody", "at": "it:beak", "radius": 0.01}))
    assert check({"do": "press", "t": 0, "prop": "it", "amount": 0.2, "way": [0, 1, 0], "near": "beak", "radius": 0.1}) == []
    assert any("near" in p for p in check({"do": "press", "t": 0, "prop": "it", "amount": 0.2, "way": [0, 1, 0], "near": "beak"}))


def test_the_brief_and_the_reviewer_ask_why_something_is_there():
    """The owner: "u need to explain why sponge was introcued here, need to connect between scenes"."""
    root = TESTS.parent / "prompts" / "character"
    assert "Each picture comes from the one before" in (root / "direct.md").read_text(encoding="utf-8")
    assert "Why is that there?" in (root / "frames.md").read_text(encoding="utf-8")
    assert "A comparison comes after what it's standing in for" in (root / "script.md").read_text(encoding="utf-8")


def test_the_words_say_what_a_comparison_stands_in_for():
    """The owner: "the transition to sponge isn't good still, it shouldt say 'therefore there is no cusion since sponge wouldnt work'". A picture's link can't make up for words with none."""
    root = TESTS.parent / "prompts" / "character"
    script, critic = (root / "script.md").read_text(encoding="utf-8"), (root / "critic.md").read_text(encoding="utf-8")
    assert "the words tie them together" in script
    assert "Each line follows from the one before" in script
    assert "Does each line follow from the one before?" in critic
    assert "can a viewer say what it's standing in for" in critic


def test_the_brief_keeps_the_picture_with_the_words_and_the_reviewer_knows_what_it_cant_see():
    """The seventh review: true speeds put a stop 2 s behind the word for it, a pad looked like a cushion just after "no real cushion", a shot opened on empty rails, and a peck between sampled frames read as no peck."""
    root = TESTS.parent / "prompts" / "character"
    direct, frames = (root / "direct.md").read_text(encoding="utf-8"), (root / "frames.md").read_text(encoding="utf-8")
    assert "The picture happens when the words say it" in direct
    assert "starts with it in the picture" in direct
    assert "Nothing in a picture contradicts what's just been said" in direct
    assert "can fall between them" in frames


@needs_blender
def test_time_slows_down_smoothly_into_slow_motion(measured):
    """Found by the frame reviewer: a hit shown twice read as the picture jumping back, so it's one unbroken beat, slowing down into it."""
    ramp = measured["ramp"]
    assert ramp["first"] > ramp["middle"] > ramp["last"] > 0
    assert ramp["evenly"] < ramp["first"] * 0.25         # no sudden change of speed
    assert ramp["covered"] == pytest.approx(0.95, abs=0.02)      # and it starts as far short as it was told


@needs_blender
def test_a_peck_goes_the_way_the_beak_points(measured):
    """Found by looking: a head turned to one side rocked about its body's axis, so its beak went sideways."""
    along, straight_up = measured["toward"]["along"], measured["toward"]["straight_up"]
    assert along[0] * 0.1 + along[1] * -0.1 == pytest.approx(0, abs=1e-6)       # square to the beak's line
    assert abs(sum(v * v for v in along) - 1) < 1e-6
    assert abs(sum(v * v for v in straight_up) - 1) < 1e-6                      # and it doesn't fall over if that's straight up


@needs_blender
def test_a_part_bent_at_rest_takes_its_spots_with_it(measured):
    bent = measured["bent_spot"]
    assert bent["moved"] > 0.01 and bent["tip_on_wall"] < 0.01


@needs_blender
def test_smoothing_a_scan_doesnt_shrink_it_or_open_its_holes(measured):
    """Found by the checks: plain smoothing shrank a bird's head by 2 cm, and then its holes opened up."""
    smoothed = measured["smoothed"]
    assert smoothed["bumps_after"] < smoothed["bumps_before"] * 0.6
    assert smoothed["radius_after"] == pytest.approx(smoothed["radius_before"], rel=0.02)
    assert smoothed["had_a_rim"] > 0 and smoothed["rim_moved"] == 0


@needs_blender
def test_being_surrounded_is_lines_through_a_point_meeting_something_on_both_sides(measured):
    surrounded = measured["surrounded"]
    assert surrounded["inside"] is True and surrounded["just_outside"] is False and surrounded["beside"] is False


@needs_blender
def test_someone_going_down_stays_on_the_ground_and_doesnt_blink_once_out_cold(measured):
    """Found by the frame reviewer: he tucked his knees and left the ground, as if hopping backward, and then opened his eyes."""
    down = measured["stays_down"]
    assert abs(down["lowest"]) < 0.02 and abs(down["highest"]) < 0.02
    assert down["last_blink"] < down["out_cold_at"]


@needs_blender
def test_a_peck_can_draw_back_slowly(measured):
    """Found by the frame reviewer: "slow motion" with a strike over in a fifth of a second isn't slow."""
    rock = measured["rock_back"]
    assert rock["furthest_at"] == 45 and rock["plain_furthest_at"] != 45


@needs_blender
def test_a_thing_can_be_smoothed_as_its_cast(measured):
    """Found by the frame reviewer: a tiny bird's brain with a person's folds on it reads as the wrong thing."""
    assert measured["smoothed_as_cast"] is True


@needs_blender
def test_glass_can_keep_some_of_what_it_was(measured):
    """Found by the frame reviewer: thin lines over a busy forest don't read as a solid head."""
    assert 0.75 in measured["glass_keeps"]


@needs_blender
def test_something_soft_sinks_into_what_its_on(measured):
    """Found by the frame reviewer: a brain balanced on the tip of its stem, with its weight overhanging, though it sat on something soft."""
    assert measured["sinks"] == pytest.approx(0.03, abs=0.001)


def test_sinking_needs_something_to_sink_into():
    things = {"brain": {"moves": [], "spots": [], "lines": [], "sharp_from": 0}, "pad": {"moves": [], "spots": [], "lines": [], "sharp_from": 0}}
    from characters import spec as character_spec
    base = {"length": 1.0, "set": "sky_set", "shots": [{"t": 0, "on": "pad", "frame": 1.0, "angle": [0, 0], "lens": 26}]}
    check = lambda cast: scene_spec.check({**base, "cast": cast}, character_spec.all_ids(), ["Idle_relaxed"], things)
    pad = {"type": "prop", "prop": "pad", "on": "set"}
    assert not [p for p in check({"pad": pad, "brain": {"type": "prop", "prop": "brain", "on": "pad", "sinks": 0.02}}) if "sinks" in p]
    assert [p for p in check({"pad": pad, "brain": {"type": "prop", "prop": "brain", "sinks": 0.02}}) if "sinks" in p]
    assert [p for p in check({"pad": pad, "brain": {"type": "prop", "prop": "brain", "on": "pad", "sinks": -1}}) if "sinks" in p]

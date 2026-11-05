"""The owner's standard, as checks (Nov 4, 2026): "every subsequent video should be made with precision and respects physical
boundaries and remove bad glows and placements". Scenes are stopped from wobbling before Blender starts, and staged scenes are
measured from their meshes: what rests on what, how a spin turns, how a hat sits, and what gets refused."""
import json
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
    for name, spec in (("block", block), ("hat", dome), ("corner", corner)):
        blender_render.make_thing(CFG, spec, {"file": "", "license": "own", "credit": ""}, tmp / name)
    found = clips.catalog(CFG)
    job = {"folders": {"walt": str(_fake_person(tmp))}, "catalog": {"Idle_relaxed": found["Idle_relaxed"]},
           "things": {"block": str(tmp / "block"), "hat": str(tmp / "hat"), "corner": str(tmp / "corner")}, "out": str(tmp),
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

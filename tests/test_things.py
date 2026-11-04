"""Phase 35 (CHARACTERS.md): getting anything a scene needs. The specs and their checks, the license rules and the spending
gate need no network: the sources are faked. The Blender tests use a stand-in winged model, written out as a GLB."""
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from characters import build as character_build
from core import config
from render import blender_render, clips
from scenes import spec as scene_spec
from things import build, get
from things import spec as thing_spec

CFG = config.load()
TESTS = Path(__file__).resolve().parent
needs_blender = pytest.mark.skipif(blender_render.missing(CFG) is not None, reason="Blender isn't installed")
GOOD = {"what": "a bird", "source": {"kind": "polyhaven", "asset": "food_apple_01"}, "meters": 0.3}
MENU = {"gull": {"moves": ["Fly", "Sit"], "spots": ["head"]}}
SCENE = {
    "length": 3.0, "set": "sky_set",
    "cast": {"walt": {"type": "person", "character": "walt", "at": [0, 0], "stance": "Idle_relaxed"},
             "bird": {"type": "prop", "prop": "gull", "at": [4, 4, 3], "facing": "walt", "size": 1.2}},
    "happens": [{"do": "go", "t": 0.2, "prop": "bird", "through": [[1, 1, 2.2], "walt:crown"], "over": 1.5, "move": "Fly",
                 "then": "Sit", "lands": True, "ends_facing": 0},
                {"do": "play", "t": 2.5, "prop": "bird", "move": "Fly", "to": 3.0, "speed": 0.5},
                {"do": "rock", "t": 1.8, "prop": "bird", "over": 0.6, "times": 3, "degrees": 25, "about": "head"},
                {"do": "aura", "t": 0.5, "on": "bird:head", "color": "green", "to": 1.5, "radius": 0.04},
                {"do": "sparks", "t": 1.0, "on": "bird:head", "kind": "chips"}],
    "shots": [{"t": 0, "on": "bird:head", "frame": 1, "follow": True}, {"t": 2, "on": "walt:crown", "frame": 1}]}


def test_a_good_thing_passes():
    assert thing_spec.check(GOOD) == []


@pytest.mark.parametrize("change, says", [
    ({"meters": 0}, "meters"),
    ({"meters": 900}, "meters"),
    ({"source": {"kind": "shop"}}, "kind"),
    ({"source": {"kind": "sketchfab"}}, "uid"),
    ({"source": {"kind": "url", "url": "u", "license": "CC-BY-NC", "page": "p"}}, "license"),
    ({"source": {"kind": "url", "url": "u", "license": "CC-BY", "page": "p"}}, "credit"),
    ({"tilt": [1]}, "tilt"),
    ({"colors": {"Wing": [2, 0, 0]}}, "color Wing"),
    ({"moves": {"fly": {"from": 1, "to": 2}}}, "move fly"),
    ({"moves": {"fly": {"clip": "a", "from": 5, "to": 2}}}, "before"),
    ({"spots": {"head": [0, 0]}}, "spot head"),
    ({"wings": 2}, "wings"),
])
def test_a_bad_thing_is_refused_with_the_reason(change, says):
    problems = thing_spec.check({**GOOD, **change})
    assert problems and says in " ".join(problems)


def test_every_thing_on_file_passes():
    for tid in thing_spec.all_ids():
        assert thing_spec.check(thing_spec.load(thing_spec.path_for(tid))) == [], tid


def _info(slug="by", tags=(), downloadable=True):
    return {"name": "Gull", "user": {"displayName": "Maker"}, "viewerUrl": "https://sketchfab.com/m", "isDownloadable": downloadable,
            "license": {"slug": slug, "label": slug, "url": "https://creativecommons.org/licenses/by/4.0/"},
            "tags": [{"name": t} for t in tags]}


@pytest.mark.parametrize("info, name", [(_info("cc0"), "CC0"), (_info("by"), "CC-BY"), (_info("by-nc"), None),
                                        (_info("by-sa"), None), (_info("by", ["NoAI"]), None),
                                        (_info("cc0", downloadable=False), None)])
def test_only_open_licenses_come_through(info, name):
    assert get._sketchfab_open(info)[0] == name


def test_a_credit_is_kept_for_cc_by(tmp_path, monkeypatch):
    monkeypatch.setenv("SKETCHFAB_TOKEN", "t")
    calls = []

    def fake_json(url, headers=None):
        calls.append((url, headers))
        return {"glb": {"url": "https://files/model.glb"}} if url.endswith("/download") else _info("by")

    monkeypatch.setattr(get, "_json", fake_json)
    monkeypatch.setattr(get.assets, "_get", lambda url: b"glb")
    got = get.fetch(CFG, {"kind": "sketchfab", "uid": "abc"}, tmp_path, say=lambda _: None)
    assert '"Gull" by Maker' in got["credit"] and "CC BY 4.0" in got["credit"]
    assert calls[1][1] == {"Authorization": "Token t"}       # the token goes only where it's asked for
    assert Path(got["file"]).read_bytes() == b"glb"
    assert get.fetch(CFG, {"kind": "sketchfab", "uid": "abc"}, tmp_path, say=lambda _: None)["credit"] == got["credit"]
    assert len(calls) == 2                                   # fetched once, then kept


def test_the_next_model_tried_isnt_mistaken_for_the_last(tmp_path, monkeypatch):
    monkeypatch.setenv("SKETCHFAB_TOKEN", "t")
    monkeypatch.setattr(get, "_json", lambda url, headers=None: (
        {"glb": {"url": f"https://files/{url.split('/')[-2]}.glb"}} if url.endswith("/download") else _info("cc0")))
    monkeypatch.setattr(get.assets, "_get", lambda url: url.encode())
    first = get.fetch(CFG, {"kind": "sketchfab", "uid": "aaa"}, tmp_path / "s", say=lambda _: None)
    assert b"aaa" in Path(first["file"]).read_bytes()
    second = get.fetch(CFG, {"kind": "sketchfab", "uid": "bbb"}, tmp_path / "s", say=lambda _: None)
    assert b"bbb" in Path(second["file"]).read_bytes()       # both are model.glb


def test_a_download_without_a_token_says_how_to_get_one(tmp_path, monkeypatch):
    monkeypatch.delenv("SKETCHFAB_TOKEN", raising=False)
    with pytest.raises(RuntimeError, match="SKETCHFAB_TOKEN"):
        get.fetch(CFG, {"kind": "sketchfab", "uid": "abc"}, tmp_path, say=lambda _: None)


def test_generating_costs_money_so_it_needs_a_yes(tmp_path, monkeypatch):
    called = []
    client = SimpleNamespace(subscribe=lambda model, arguments: called.append(arguments) or {"model_glb": {"url": "https://x/m.glb"}})
    monkeypatch.setattr(get.assets, "_get", lambda url: b"glb")
    source = {"kind": "generate", "prompt": "a gull"}
    with pytest.raises(RuntimeError, match="needs the owner's yes"):
        get.fetch(CFG, source, tmp_path, say=lambda _: None, client=client)
    assert called == []
    got = get.fetch(CFG, source, tmp_path, spend=True, say=lambda _: None, client=client)
    assert called == [{"prompt": "a gull"}] and got["usd"] == get.GENERATE["usd"]


def test_looking_for_something_finds_it_and_shows_pictures(tmp_path, monkeypatch):
    cfg = SimpleNamespace(data_dir=tmp_path)
    monkeypatch.setattr(get, "_polyhaven_list", lambda c: {
        "food_apple_01": {"name": "Apple", "tags": ["fruit"], "categories": ["food"], "authors": {"A": "All"}},
        "chair_01": {"name": "Chair", "tags": [], "categories": ["furniture"], "authors": {}}})
    pages = {"cc0": [{"uid": "1", "name": "Scan", "tags": []}, {"uid": "2", "name": "Skip", "tags": [{"name": "noai"}]}],
             "by": [{"uid": "3", "name": "Rigged", "animationCount": 2, "tags": []}, {"uid": "1", "name": "Scan", "tags": []}]}
    monkeypatch.setattr(get, "_json", lambda url, headers=None: {"results": pages["cc0" if "license=cc0" in url else "by"]})
    found = get.search(cfg, "apple")
    assert [h["title"] for h in found["hits"]] == ["Apple", "Scan", "Rigged"]   # free first, noai and repeats left out
    assert found["hits"][2]["license"] == "CC-BY" and found["hits"][2]["moves"] == 2
    assert Image.open(found["sheet"]).width > 0


def test_a_scene_can_use_any_thing_in_the_library():
    assert scene_spec.check(SCENE, ["walt"], ["Idle_relaxed"], MENU) == []


@pytest.mark.parametrize("change, says", [
    ({"cast": {**SCENE["cast"], "bird": {"type": "prop", "prop": "owl"}}}, "owl"),
    ({"cast": {**SCENE["cast"], "bird": {**SCENE["cast"]["bird"], "size": 0}}}, "size"),
    ({"cast": {**SCENE["cast"], "bird": {**SCENE["cast"]["bird"], "facing": "nobody"}}}, "facing"),
    ({"happens": [{"do": "go", "t": 0, "prop": "bird", "through": [], "over": 1}]}, "through"),
    ({"happens": [{"do": "go", "t": 0, "prop": "bird", "through": ["ghost:eyes"], "over": 1}]}, "ghost"),
    ({"happens": [{"do": "go", "t": 0, "prop": "bird", "through": ["walt:crown"], "over": 0}]}, "over"),
    ({"happens": [{"do": "go", "t": 0, "prop": "bird", "through": ["walt:crown"], "over": 1, "move": "Swim"}]}, "Swim"),
    ({"happens": [{"do": "go", "t": 0, "prop": "bird", "through": ["walt:crown"], "over": 1, "hits": "bird"}]}, "hits"),
    ({"happens": [{"do": "play", "t": 0, "prop": "bird", "move": "Swim"}]}, "Swim"),
    ({"happens": [{"do": "play", "t": 0, "prop": "bird", "move": "Fly", "speed": 0}]}, "speed"),
    ({"shots": [{"t": 0, "on": "bird:tail", "frame": 1}]}, "spot on it: head"),
    ({"happens": [{"do": "rock", "t": 0, "prop": "bird", "over": 1, "about": "tail"}]}, "spot on it"),
    ({"happens": [{"do": "aura", "t": 0, "on": "bird:tail", "color": "green", "to": 1}]}, "isn't a spot"),
    ({"happens": [{"do": "aura", "t": 0, "on": "walt:eyes", "color": "green", "to": 1}]}, "`glow`"),
    ({"happens": [{"do": "aura", "t": 0, "on": "bird:head", "color": "pink", "to": 1}]}, "color"),
    ({"happens": [{"do": "sparks", "t": 0, "on": "bird:head", "kind": "glitter"}]}, "kind"),
    ({"happens": [{"do": "rock", "t": 0, "prop": "bird", "over": 1, "axis": "sideways"}]}, "axis"),
    ({"happens": [{"do": "rock", "t": 0, "prop": "bird", "over": 0}]}, "over"),
    ({"happens": [{"do": "rock", "t": 0, "prop": "bird", "over": 1, "times": 0}]}, "times"),
    ({"happens": [{"do": "rock", "t": 0, "prop": "bird", "over": 1, "degrees": 500}]}, "degrees"),
])
def test_a_bad_use_of_a_thing_is_refused_with_the_reason(change, says):
    problems = scene_spec.check({**SCENE, **change}, ["walt"], ["Idle_relaxed"], MENU)
    assert problems and says in " ".join(problems)


def test_a_things_clips_are_known_once_its_made(tmp_path):
    cfg = SimpleNamespace(data_dir=tmp_path)
    assert build.menu(cfg)["apple"]["moves"] == []
    (tmp_path / "things" / "apple").mkdir(parents=True)
    (tmp_path / "things" / "apple" / "thing.json").write_text(json.dumps({"moves": {"Roll": {}, "Bounce": {}}}), encoding="utf-8")
    assert build.menu(cfg)["apple"]["moves"] == ["Bounce", "Roll"]


def _fake_model(tmp_path) -> Path:
    glb = tmp_path / "flyer.glb"
    subprocess.run([str(blender_render.exe(CFG)), "-b", "--factory-startup", "--python-exit-code", "1", "-P",
                    str(TESTS / "blender_fake_thing.py"), "--", str(glb)], check=True, capture_output=True)
    return glb


@needs_blender
def test_any_file_comes_in_at_its_real_size_with_its_clips(tmp_path):
    spec = {"what": "a flyer", "source": {"kind": "url", "url": "u", "license": "CC0", "page": "p"}, "meters": 0.5, "turn": 90}
    made = blender_render.make_thing(CFG, spec, {"file": str(_fake_model(tmp_path)), "license": "CC0", "credit": ""}, tmp_path / "t")
    assert max(made["size"]) == pytest.approx(0.5, abs=0.001)
    assert made["size"][1] == pytest.approx(0.5, abs=0.001)    # turned a quarter, the long way is now along y
    assert made["moves"] and all(m["to"] > m["from"] for m in made["moves"].values())
    result = blender_render.thing_sheet(CFG, tmp_path / "t", size=(54, 72), samples=1)
    assert [s["view"] for s in result["shots"]][:5] == ["front", "three quarter", "side", "back", "from above"]
    assert len(result["shots"]) == 9                           # four frames of its one clip
    picture = character_build.sheet(result, tmp_path / "t" / "sheet", cell=(27, 36), columns=5)
    assert Image.open(picture).size == (27 * 5, 36 * 2)


@needs_blender
def test_a_wrong_material_name_says_what_there_is(tmp_path):
    spec = {"what": "a flyer", "source": {"kind": "url", "url": "u", "license": "CC0", "page": "p"}, "meters": 0.5,
            "colors": {"Wing": [1, 0, 0]}}
    with pytest.raises(RuntimeError, match="Feathers"):
        blender_render.make_thing(CFG, spec, {"file": str(_fake_model(tmp_path)), "license": "CC0", "credit": ""}, tmp_path / "t")


@needs_blender
@pytest.mark.skipif(clips.missing(CFG) is not None, reason="the free body clips aren't in data/motion")
def test_a_thing_flies_lands_on_someone_and_rides_there(tmp_path):
    """No code for this bird: it's what any scene with any winged thing gets."""
    from tests.test_characters import _fake_person  # the stand-in person
    spec = {"what": "a flyer", "source": {"kind": "url", "url": "u", "license": "CC0", "page": "p"}, "meters": 0.4}
    blender_render.make_thing(CFG, spec, {"file": str(_fake_model(tmp_path)), "license": "CC0", "credit": ""}, tmp_path / "t")
    person = _fake_person(tmp_path)
    scene = {"length": 3.0, "set": "sky_set",
             "cast": {"walt": {"type": "person", "character": "walt", "at": [0, 0], "stance": "Idle_relaxed"},
                      "bird": {"type": "prop", "prop": "flyer", "at": [3, 3, 2.5], "facing": 180}},
             "happens": [{"do": "go", "t": 0.2, "prop": "bird", "through": [[2, -1, 2.2], [-1, -1, 2.0], "walt:crown"], "over": 2.0,
                          "move": "Flap", "lands": True, "ends_facing": 0}],
             "rock": {"do": "rock", "t": 0.0, "prop": "other", "over": 0.9, "times": 3, "degrees": 25},
             "shots": [{"t": 0, "on": "bird:", "frame": 1, "follow": True}]}
    found = clips.catalog(CFG)
    job = {"scene": scene, "folders": {"walt": str(person)}, "catalog": {"Idle_relaxed": found["Idle_relaxed"]},
           "things": {"flyer": str(tmp_path / "t")}, "out": str(tmp_path)}
    (tmp_path / "job.json").write_text(json.dumps(job), encoding="utf-8")
    subprocess.run([str(blender_render.exe(CFG)), "-b", "--factory-startup", "--python-exit-code", "1", "-P",
                    str(TESTS / "blender_thing_check.py"), "--", str(tmp_path / "job.json")], check=True, capture_output=True)
    out = json.loads((tmp_path / "out.json").read_text(encoding="utf-8"))
    assert out["rock"]["back_deg"] > 15 and out["rock"]["home_gap"] < 0.001     # drawn back, and home exactly on each snap
    assert out["along_line"] > 0.8                             # nose first, within the limit on climbing
    assert out["bank"] > 0.05                                  # it leans into its turn
    assert out["wing_moved"] > 0.02                            # the clip plays, through the NLA
    assert abs(out["gap_above_head"]) < 0.02                   # its underside is on their head
    assert out["gap_across"] < 0.03
    assert out["rides_on"] == "head" and out["riding"] == [0.0, 1.0]   # and it stays there once it's landed


def _strike_job(tmp_path, stands_at):
    from tests.test_characters import _fake_person
    glb = _fake_model(tmp_path)
    file = {"file": str(glb), "license": "CC0", "credit": ""}
    source = {"kind": "url", "url": "u", "license": "CC0", "page": "p"}
    blender_render.make_thing(CFG, {"what": "a tool", "source": source, "meters": 0.35, "turn": 90,
                                    "spots": {"grip": [0, 0, -0.03], "end": [0.17, 0, 0]}}, file, tmp_path / "tool")
    blender_render.make_thing(CFG, {"what": "a trunk", "source": source, "meters": 3.0}, file, tmp_path / "trunk")
    person = _fake_person(tmp_path)
    scene = {"length": 2.0, "set": "sky_set",
             "cast": {"walt": {"type": "person", "character": "walt", "at": [0, stands_at], "facing": 180, "stance": "Idle_relaxed"},
                      "tool": {"type": "prop", "prop": "toolkind"},
                      "trunk": {"type": "prop", "prop": "trunkkind", "at": [0, 0, 1.1], "facing": 0, "floats": True}},
             "happens": [{"do": "hold", "who": "walt", "prop": "tool", "hand": "R", "grip": "ready"},
                         {"do": "strike", "t": 1.5, "who": "walt", "prop": "tool", "target": "trunk", "along": 0.0, "over": 0.8, "sparks": False}],
             "shots": [{"t": 0, "on": "walt:chest", "frame": 1.2, "shows": ["walt", "tool"]}]}     # the trunk's between them and the lens
    found = clips.catalog(CFG)
    job = {"scene": scene, "folders": {"walt": str(person)}, "catalog": {"Idle_relaxed": found["Idle_relaxed"]},
           "things": {"toolkind": str(tmp_path / "tool"), "trunkkind": str(tmp_path / "trunk")}, "out": str(tmp_path)}
    (tmp_path / "job.json").write_text(json.dumps(job), encoding="utf-8")
    subprocess.run([str(blender_render.exe(CFG)), "-b", "--factory-startup", "--python-exit-code", "1", "-P",
                    str(TESTS / "blender_strike_check.py"), "--", str(tmp_path / "job.json")], check=True, capture_output=True)
    return json.loads((tmp_path / "out.json").read_text(encoding="utf-8"))


@needs_blender
@pytest.mark.skipif(clips.missing(CFG) is not None, reason="the free body clips aren't in data/motion")
def test_a_tool_swung_at_the_side_of_a_thing_lands_flat_on_it_in_a_closed_hand(tmp_path):
    """Found on the first real short: a strike only knew how to come down from above, and a hand holding a tool stayed open."""
    out = _strike_job(tmp_path, -0.62)
    assert out["gap"] < 0.01                                   # its working end is on the surface
    assert out["faces_target"] > 0.9                           # its front is what lands, not its side
    assert out["handle_up"] > 0.9                              # upright, as a hammer meets a wall, not poked end on
    assert out["thumb_closed_deg"] > 10                        # the hand holding it has closed; the other hasn't


@needs_blender
@pytest.mark.skipif(clips.missing(CFG) is not None, reason="the free body clips aren't in data/motion")
def test_someone_too_far_away_to_swing_is_refused(tmp_path):
    out = _strike_job(tmp_path, -2.5)
    assert "stands too far" in out["refused"]

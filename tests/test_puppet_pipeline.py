"""The puppet pictures in the pipeline: scene sheets checked against the stage, and a stub video staged and
animated end to end (render.pictures: puppet)."""
import json
from pathlib import Path

import pytest
from PIL import Image

from core import actions, db
from core.context import make_ctx
from core.engine import Engine
from providers.llm import STUB_PLACES
from puppet import sheet as sheets, state
from puppet.stage import Stage

PEOPLE = ["the stick figure", "Eli"]
PROPS = ["plate", "drill"]


def _stage(tmp_path: Path) -> Stage:
    picture = tmp_path / "place.png"
    Image.new("RGB", (1920, 1080), (200, 200, 190)).save(picture)
    return Stage(picture, (1920, 1080), [(300, 1000, 600), (1500, 1000, 600)],
                 {"door": (300, 1000), "stairs_top": (1500, 1000)}, {"x": 960, "y": 100, "warm": True})


def _sheet() -> dict:
    return {"figures": [{"who": "the stick figure", "attached": [{"joint": "r_hand", "prop": "drill", "angle": 0}],
                         "actions": [{"from_ms": 0, "to_ms": 3000, "do": "limp", "start": "door", "end": "stairs_top"},
                                     {"from_ms": 3000, "to_ms": 5000, "do": "kneel_work", "facing": "right"}]},
                        {"who": "Eli", "attached": [],
                         "actions": [{"from_ms": 1000, "to_ms": 5000, "do": "reach", "at": "stairs_top", "side": "right",
                                      "facing": "left"}]}],
            "set": [{"place": "plate", "at": "stairs_top", "angle": 0}],
            "camera": [{"at_ms": 0, "center": "door", "zoom": 1.4}, {"at_ms": 3000, "center": "the stick figure", "zoom": 1.7}],
            "light": {"time": "night", "lamp": "lamp"}}


def test_a_good_sheet_passes_and_each_mistake_is_named(tmp_path):
    stage = _stage(tmp_path)
    assert sheets.check(_sheet(), stage, PEOPLE, PROPS, 5000) == []
    bad = _sheet()
    bad["figures"][0]["actions"][0]["end"] = "roof"
    assert any("roof" in p for p in sheets.check(bad, stage, PEOPLE, PROPS, 5000))
    bad = _sheet()
    bad["figures"][0]["actions"][1]["do"] = "backflip"
    assert any("backflip" in p for p in sheets.check(bad, stage, PEOPLE, PROPS, 5000))
    bad = _sheet()
    bad["figures"][0]["actions"][1]["from_ms"] = 2000                                 # overlaps the walk
    assert any("overlap" in p for p in sheets.check(bad, stage, PEOPLE, PROPS, 5000))
    bad = _sheet()
    bad["figures"][0]["actions"][1]["to_ms"] = 9000                                   # past the end of the line
    assert any("9000" in p for p in sheets.check(bad, stage, PEOPLE, PROPS, 5000))
    bad = _sheet()
    bad["figures"][0]["attached"][0]["prop"] = "chainsaw"
    assert any("chainsaw" in p for p in sheets.check(bad, stage, PEOPLE, PROPS, 5000))
    bad = _sheet()
    bad["figures"].append({"who": "Dale", "actions": [{"from_ms": 0, "to_ms": 5000, "do": "stand", "at": "door"}]})
    assert any("Dale" in p for p in sheets.check(bad, stage, PEOPLE, PROPS, 5000))
    bad = _sheet()
    bad["figures"][1]["actions"][0]["side"] = ""                                     # Eli on the very spot where
    assert any("both stand at stairs_top" in p for p in sheets.check(bad, stage, PEOPLE, PROPS, 5000))  # the hero kneels
    bad["figures"][1]["actions"][0]["side"] = "left"
    assert sheets.check(bad, stage, PEOPLE, PROPS, 5000) == []                       # a side apart is fine
    bad = _sheet()
    bad["camera"] = []
    assert any("camera" in p for p in sheets.check(bad, stage, PEOPLE, PROPS, 5000))
    bad = _sheet()
    bad["figures"].pop()                                                             # Eli is in the scene but
    bad["camera"][1]["center"] = "Eli"                                               # not on the sheet
    assert any("'Eli' is neither a spot nor a person on this sheet" in p for p in sheets.check(bad, stage, PEOPLE, PROPS, 5000))
    bad = _sheet()
    bad["light"]["time"] = "noon"
    assert any("light.time" in p for p in sheets.check(bad, stage, PEOPLE, PROPS, 5000))


def test_a_sheet_resolves_to_puppets_placements_light_and_a_following_camera(tmp_path):
    stage = _stage(tmp_path)
    puppets = {"hero": object(), "eli": object()}
    after = sheets.after(_sheet(), {}, "stairwell")
    assert state.placements(after, "stairwell") == {"plate": {"at": "stairs_top", "angle": 0}}
    out = sheets.resolve(_sheet(), stage, puppets, {"plate": 1, "drill": 2}, state.placements(after, "stairwell"),
                         5000, 10)
    assert [f["who"] for f in out["figures"]] == ["hero", "eli"]
    assert out["figures"][0]["attached"] == {"r_hand": {"prop": "drill", "angle": 0.0}}
    assert out["set"] == {"plate": {"at": "stairs_top", "angle": 0}}
    assert out["light"]["level"] < 1 and out["light"]["glow"]["at"] == "lamp"
    assert out["camera"][1]["center"] == "hero"                 # the camera follows the person, by puppet key
    assert out["camera"][0]["center"] == "door"
    assert sheets.light_for({"time": "day", "lamp": ""}) is None
    summary = sheets.summary(_sheet(), state.placements(after, "stairwell"))
    assert "the stick figure: ended at stairs_top, kneel_work, holding drill in r_hand" in summary
    assert "plate at stairs_top" in summary and "Light last time: night, lit by lamp." in summary
    with pytest.raises(ValueError, match="no puppet"):
        sheets.resolve(_sheet(), stage, {"hero": object()}, {}, {}, 5000, 10)


def test_a_side_stands_a_figure_a_step_from_the_spot(tmp_path):
    from puppet import animate
    stage = _stage(tmp_path)

    class Puppet:
        scale = 1.0

    at = animate.figure_at(stage, Puppet(), [{"from_ms": 0, "to_ms": 1000, "do": "stand", "at": "door"}], 500)
    right = animate.figure_at(stage, Puppet(), [{"from_ms": 0, "to_ms": 1000, "do": "stand", "at": "door", "side": "right"}], 500)
    assert right.feet[0] - at.feet[0] == pytest.approx(animate.SIDE * stage.height_at(*stage.spot("door")))
    assert right.feet[1] == at.feet[1]


def test_the_words_and_the_stage_are_told_to_the_stager(tmp_path):
    assert sheets.words_text([{"word": "Day", "start_ms": 0}, {"word": "14.", "start_ms": 420}]) == "Day(0.0) 14.(0.4)"
    text = sheets.stage_text(_stage(tmp_path))
    assert "door at x 16%, y 93%" in text and "56% of the picture tall" in text
    assert sheets.who_key("The Stick Figure") == "hero" and sheets.who_key("Mrs. Okafor") == "mrs-okafor"


def test_a_stub_video_is_staged_and_animated_end_to_end(tmp_path):
    ctx = make_ctx(data_dir=tmp_path, overrides={
        "mode": "stub", "stub": {"scenes": 4}, "engine": {"retry_backoff_s": 0}, "topics": {"competitors": "off"},
        "render": {"engine": "ffmpeg", "pictures": "puppet", "puppet_fps": 4}})
    vid = actions.new_video(ctx, "zombie", "Day 1 to Day 30 in a flooded subway")
    Engine(ctx).run_until_idle()
    actions.approve(ctx, vid, "outline")
    Engine(ctx).run_until_idle()
    actions.approve(ctx, vid, "script")
    Engine(ctx).run_until_idle()
    with ctx.connect() as conn:
        video = db.get_video(conn, vid)
        scenes = db.scenes_for(conn, vid)
        costs = conn.execute("SELECT stage, COUNT(*) AS n FROM costs WHERE video_id = ? GROUP BY stage", (vid,)).fetchall()
    assert video["state"] == "assembled", video["error"]
    assets = json.loads(video["assets_json"])
    assert set(assets["stages"]) == {p["id"] for p in STUB_PLACES}
    for path in assets["stages"].values():
        assert Path(path).exists()
    assert "hero" in assets["puppets"] and (Path(assets["puppets"]["hero"]) / "puppet.json").exists()
    assert str(tmp_path) in assets["puppets"]["hero"]                       # under data, never in the repo
    assert (Path(assets["props"]) / "cot.png").exists()                      # the stub script's cot, painted once
    for s in scenes:
        assert s["state"] == "ok" and s["sheet_json"] and s["motion"] == "clip", s["idx"]
        assert ctx.abs(s["clip_path"]).exists() and ctx.abs(s["still_path"]).exists()
    first = scenes[0]
    placed = json.loads(first["set_json"])
    assert placed[first["place"]]["cot"]["at"]                               # the cot pushed against the door...
    later = next(s for s in scenes[1:] if s["place"] == first["place"])
    assert json.loads(later["set_json"])[first["place"]]["cot"] == placed[first["place"]]["cot"]  # ...is still there
    by_stage = {c["stage"]: c["n"] for c in costs}
    assert by_stage.get("assets", 0) >= 3 and by_stage.get("sheets", 0) == 4
    assert "stills" not in by_stage and "clips" not in by_stage               # the generative stages stood aside
    assert ctx.abs(video["video_path"]).exists()

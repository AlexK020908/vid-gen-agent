"""The machine kit (SHORTS.md phase 25): specs checked in code before Blender starts, then built, posed and
turned around in Blender. The Blender tests skip without Blender (tests/test_shorts.py says how)."""
import copy
import json

import pytest

from core import config
from machines import sheet, spec
from render import blender_render

CFG = config.load()
needs_blender = pytest.mark.skipif(blender_render.missing(CFG) is not None, reason="Blender isn't installed")

# one cylinder of an engine: a piston in a cut-open liner, driven by a crank from step 2
ENGINE = {
    "name": "one cylinder of an engine",
    "steps": ["the piston in its cylinder", "with the crank"],
    "parts": [
        {"id": "block", "kind": "tube", "r_out": 0.07, "r_in": 0.05, "h": 0.22, "material": "safety_yellow",
         "at": [0, 0, 0.12], "cut": True},
        {"id": "piston", "kind": "cylinder", "r": 0.049, "h": 0.06, "material": "steel", "at": [0, 0, 0.27],
         "joint": {"type": "slide", "axis": "z", "min": -0.08, "max": 0, "rest": 0}},
        {"id": "pin", "kind": "cylinder", "r": 0.008, "h": 0.07, "material": "chrome", "at": [0.035, 0, 0.02],
         "rot": [0, -90, 0], "parent": "piston"},
        {"id": "crank", "kind": "group", "at": [0, 0, 0.04], "steps": [2, None],
         "joint": {"type": "spin", "axis": "y"}},
        {"id": "web", "kind": "box", "size": [0.03, 0.02, 0.07], "material": "dark_steel", "at": [0, -0.02, 0.02],
         "parent": "crank"},
        {"id": "shaft", "kind": "cylinder", "r": 0.012, "h": 0.12, "material": "chrome", "at": [0, 0.06, 0],
         "rot": [90, 0, 0], "parent": "crank"},
    ],
    "couple": [{"type": "crank", "driver": "crank", "driven": "piston", "throw": 0.04, "rod": 0.13}],
    "contacts": [["piston", "block"], ["pin", "block"], ["shaft", "web"], ["pin", "piston"]],
    "anchors": {"piston": ["piston", [0.049, 0, 0.03]]},
}


def test_a_good_spec_has_no_problems():
    assert spec.check(ENGINE) == []


@pytest.mark.parametrize("change, problem", [
    (lambda s: s["parts"][0].update(material="gold"), "material must be one of the palette"),
    (lambda s: s["parts"][0].update(r_in=0.08), "r_in (0.08) must be less than its r_out"),
    (lambda s: s["parts"][2].update(parent="rotor"), "its parent 'rotor' isn't a part"),
    (lambda s: s["parts"][3].update(steps=[2, 5]), "outside the machine's 2 steps"),
    (lambda s: s["parts"][1]["joint"].update(min=0.1), "min must be at most its max"),
    (lambda s: s["couple"][0].update(throw=0.2), "throw (the crank's radius) less than rod"),
    (lambda s: s["parts"][4].update(kind="blob"), "kind must be one of"),
    (lambda s: s["parts"][5].pop("h"), "a cylinder needs h"),
    (lambda s: s["parts"][0].update(h=900), "more than the 500 m"),
    (lambda s: s["anchors"].update(top=["lid", [0, 0, 0]]), "anchor top"),
    (lambda s: (s["parts"][3].update(parent="web")), "go round in a circle"),
])
def test_a_bad_spec_says_what_to_fix(change, problem):
    bad = copy.deepcopy(ENGINE)
    change(bad)
    problems = spec.check(bad)
    assert any(problem in p for p in problems), problems


SPECS = sorted((config.ROOT / "machines" / "specs").glob("*.json"))


@pytest.mark.parametrize("path", SPECS, ids=[p.stem for p in SPECS])
def test_every_machine_we_keep_passes_its_checks(path):
    assert spec.check(spec.load(path)) == []


@needs_blender
@pytest.mark.parametrize("path", SPECS, ids=[p.stem for p in SPECS])
def test_no_machine_we_keep_passes_through_itself(tmp_path, path):
    """At every step, at rest and at every joint's ends. The checks caught real mistakes in each first draft: the
    pile hammer's ram and eye bolt hitting the crossbar at full lift, its lugs, fuel pipe and spark wire through the
    guide rods, its collar inside the cylinder; the engine's bores leaving a skin where they met the crankcase, a
    one-piece main shaft under the rods, valves through the plugs; the crane's boom through its cab."""
    machine = spec.load(path)
    result = blender_render.turnaround(CFG, machine, tmp_path, size=(54, 96), samples=1)
    assert result["problems"] == []
    assert len({s["step"] for s in result["shots"]}) == len(machine["steps"])


def test_parts_come_and_go_with_the_steps():
    assert "crank" not in spec.at_step(ENGINE, 1) and "web" not in spec.at_step(ENGINE, 1)   # a child goes too
    assert {"crank", "web", "shaft", "piston"} <= set(spec.at_step(ENGINE, 2))


@needs_blender
def test_a_turnaround_shows_every_step_from_every_side(tmp_path):
    result = blender_render.turnaround(CFG, ENGINE, tmp_path, size=(108, 192), samples=1)
    assert result["problems"] == []
    views = {(s["step"], s["view"]) for s in result["shots"]}
    assert views == {(step, view) for step in (1, 2) for view in ("cut", "front", "left", "side", "right")}
    assert all((tmp_path / s["file"]).exists() for s in result["shots"])
    assert sheet.make(result, tmp_path).exists()


@needs_blender
def test_parts_passing_through_each_other_are_found(tmp_path):
    """At rest, mounted parts not declared as contacts; and at a joint's far end, a slider driven into a wall."""
    bad = copy.deepcopy(ENGINE)
    bad["contacts"] = [c for c in bad["contacts"] if c != ["shaft", "web"]]
    bad["parts"] += [
        {"id": "wall", "kind": "box", "size": [0.02, 0.2, 0.2], "material": "white_paint", "at": [0.4, 0, 0.1]},
        {"id": "door", "kind": "box", "size": [0.1, 0.1, 0.1], "material": "steel", "at": [0.25, 0, 0.05],
         "joint": {"type": "slide", "axis": "x", "min": 0, "max": 0.15, "rest": 0}},
    ]
    result = blender_render.turnaround(CFG, bad, tmp_path, size=(108, 192), samples=1)
    assert "step 2: shaft and web pass through each other (rest)" in result["problems"]
    assert "step 1: door and wall pass through each other (door at 0.15)" in result["problems"]
    assert not any("rest" in p and "door" in p for p in result["problems"])   # clear of it at rest


@needs_blender
def test_a_crank_drives_its_piston_exactly(tmp_path):
    """At 180 degrees the piston is at the bottom of its stroke: down twice the crank's throw."""
    blender_render.run_job(CFG, {"kind": "pose", "spec": ENGINE, "set": {"crank": 180}}, tmp_path)
    pose = json.loads((tmp_path / "pose.json").read_text(encoding="utf-8"))
    assert pose["values"]["piston"] == pytest.approx(-0.08, abs=1e-6)
    assert pose["at"]["piston"][2] == pytest.approx(0.27 - 0.08, abs=1e-4)
    assert pose["at"]["pin"][2] == pytest.approx(0.27 - 0.08 + 0.02, abs=1e-4)   # the pin rides with it

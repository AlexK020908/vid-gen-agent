"""Writes the machine specs in this folder: `uv run python -m machines.specs.generate`.

The JSON files are what the kit reads and the tests check; this is how they're made, so a change is made here and
the files written again. Sizes follow reference A's storyboard (data/benchmarks/pile_hammer/storyboard.json), which
gives every part in multiples of the pile's diameter (0.6 m here).
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


class Spec:
    def __init__(self, name: str, steps: list[str]):
        self.data = {"name": name, "steps": steps, "parts": [], "anchors": {}, "couple": [], "contacts": []}

    def part(self, **kw):
        self.data["parts"].append(kw)
        return kw

    def touch(self, *pairs):
        self.data["contacts"] += [list(p) for p in pairs]

    def save(self, file: str):
        (HERE / file).write_text(json.dumps(self.data, indent=1), encoding="utf-8")
        return self.data


def pile_hammer():
    """The diesel pile hammer, built up in A's order. The pile is 30 m long (50 diameters) with its top at the
    hammer's z 0; the hammer rides on it, so it sinks with each blow."""
    D = 0.6                                         # the pile's diameter: A sizes everything by it
    s = Spec("diesel pile hammer", [
        "an iron block", "split into a ram and an anvil", "the anvil's flange", "a cylinder between them",
        "explosives inside", "guide rods", "explosives through the port", "a fuel injector, gasoline and a spark plug",
        "diesel"])
    p = s.part
    p(id="pile", kind="tube", r_out=D / 2, r_in=D / 2 - 0.04, h=30.0, material="pile_paint", at=[0, 0, -30],
      segments=48, joint={"type": "slide", "axis": "z", "min": -20, "max": 0, "rest": 0})
    p(id="pile_plug", kind="cylinder", r=D / 2 - 0.04, h=0.5, material="dark_steel", at=[0, 0, 29.3], parent="pile")
    p(id="hammer", kind="group", parent="pile", at=[0, 0, 30])

    R, H = 0.65, 1.75                               # the block: 2.2 pile diameters wide, splitting 30% of the way up
    split = 0.3 * H
    p(id="block", kind="cylinder", r=R, h=H, material="steel", bevel=0.04, segments=72, parent="hammer", steps=[1, 1],
      joint={"type": "slide", "axis": "z", "min": 0, "max": 30, "rest": 0})
    p(id="block_eye", kind="torus", major=0.11, minor=0.03, material="steel", at=[0, 0, H + 0.07], axis="X",
      parent="block")
    p(id="split_line", kind="tube", r_out=R + 0.006, r_in=R - 0.02, h=0.03, material="safety_yellow", at=[0, 0, split],
      segments=72, parent="block")

    # the anvil: first the block's lower 30%, then a boss with a dished top on a wide flange with four sockets
    p(id="anvil", kind="lathe", material="steel", parent="hammer", steps=[2, None], cut=True, segments=72,
      points=[[0, 0], [R, 0], [R, split - 0.02], [R - 0.02, split], [0.5, split], [0.35, split - 0.05],
              [0.15, split - 0.08], [0, split - 0.085]])
    ram_h = H - split
    p(id="ram", kind="cylinder", r=R, h=ram_h, material="steel", bevel=0.04, segments=72, at=[0, 0, split],
      parent="hammer", steps=[2, None],
      joint={"type": "slide", "axis": "z", "min": 0, "max": 30, "rest": 0, "check": [0, 3.1]})
    p(id="ram_eye", kind="torus", major=0.1, minor=0.028, material="steel", at=[0, 0, ram_h + 0.06], axis="X",
      parent="ram")
    p(id="flange", kind="cylinder", r=2.5 * D, h=0.12, material="dark_steel", bevel=0.015, segments=128,
      parent="hammer", steps=[3, None], cut=True)
    for i, (x, y) in enumerate([(-1.3, 0), (1.3, 0), (0, -1.3), (0, 1.3)], 1):
        p(id=f"socket{i}", kind="cylinder", r=0.11, h=0.12, material="safety_yellow", bevel=0.01, segments=32,
          at=[x, y, 0.12], parent="hammer", steps=[3, None], cut=True)

    # the cylinder: 1.2 rams wide, standing on the flange round the anvil's boss and reaching just under the ram's
    # collar when the ram is down (1.1 rams tall in all), lipped at both ends, a port each side into the chamber
    collar_h = 0.25 * ram_h
    cyl_r, bore = 1.2 * R, R + 0.025
    cyl_z, cyl_h = 0.12, split + ram_h - collar_h - 0.03 - 0.12
    port_z = split + 0.25
    p(id="cyl_slide", kind="group", parent="hammer", steps=[4, None],
      joint={"type": "slide", "axis": "x", "min": -8, "max": 0, "rest": 0})
    p(id="cyl_drop", kind="group", parent="cyl_slide", joint={"type": "slide", "axis": "z", "min": 0, "max": 3, "rest": 0})
    for side, x in (("l", -1), ("r", 1)):
        p(id=f"port_hole_{side}", kind="cylinder", r=0.075, h=0.4, at=[x * (cyl_r - 0.2), 0, port_z], rot=[0, 90, 0],
          helper=True, segments=32, parent="cyl_drop")
    p(id="cylinder", kind="tube", r_out=cyl_r, r_in=bore, h=cyl_h, material="safety_yellow", segments=96,
      at=[0, 0, cyl_z], parent="cyl_drop", cut=True, subtract=["port_hole_l", "port_hole_r"])
    for name, z in (("lip_low", cyl_z), ("lip_high", cyl_z + cyl_h - 0.1)):
        p(id=name, kind="tube", r_out=cyl_r + 0.07, r_in=cyl_r - 0.02, h=0.1, material="safety_yellow", segments=96,
          at=[0, 0, z], parent="cyl_drop", cut=True)
    for side, x in (("l", -1), ("r", 1)):
        p(id=f"port_ring_{side}", kind="tube", r_out=0.13, r_in=0.075, h=0.08, material="safety_yellow", segments=32,
          at=[x * (cyl_r - 0.01), 0, port_z], rot=[0, 90 * x, 0], parent="cyl_drop")

    # explosives: a striped drum with a red cap, dropped onto the boss
    p(id="explosive", kind="cylinder", r=0.45 * bore, h=0.25, material="hazard_stripes", bevel=0.015,
      at=[0, 0, split - 0.05], parent="hammer", steps=[5, 5],
      joint={"type": "slide", "axis": "z", "min": 0, "max": 4, "rest": 0})
    p(id="explosive_cap", kind="cylinder", r=0.07, h=0.06, material="red_paint", at=[0, 0, 0.25], parent="explosive")

    # guide rods from two sockets up to the crossbar; the collar's ears ride on them
    top = split + 4.5 * ram_h + 0.3
    for side, x in (("l", -1.3), ("r", 1.3)):
        p(id=f"rod_{side}", kind="cylinder", r=0.25 * D / 2, h=top - 0.24, material="glass_rod", segments=32,
          at=[x, 0, 0.24], parent="hammer", steps=[6, None],
          joint={"type": "stretch", "axis": "z", "min": 0.05, "max": top - 0.24, "rest": top - 0.24})
        p(id=f"ear_{side}", kind="box", size=[0.26, 0.26, 0.24], material="safety_yellow", bevel=0.02,
          at=[x * 0.79, 0, ram_h - 0.15], parent="ram", steps=[6, None])
        p(id=f"sleeve_{side}", kind="tube", r_out=0.15, r_in=0.25 * D / 2 + 0.012, h=0.26, material="safety_yellow",
          segments=32, at=[x, 0, ram_h - 0.28], parent="ram", steps=[6, None])
    p(id="collar", kind="tube", r_out=1.3 * R, r_in=R, h=collar_h, material="safety_yellow", segments=96,
      at=[0, 0, ram_h - collar_h], parent="ram", steps=[6, None])
    p(id="crossbar", kind="box", size=[2.5 * 2 * R * 1.05, 0.4, 0.3], material="safety_yellow", bevel=0.02,
      at=[0, 0, top + 0.15], parent="hammer", steps=[6, None])
    p(id="pulley", kind="sphere", r=0.22, material="dark_steel", at=[0, 0, 0.36], parent="crossbar")
    # the start-up hook goes down no further than the ram's eye with the ram on the anvil, where it hooks it
    lowest = round(split + ram_h + 0.06 + 0.1 + 0.028 + 0.22 - top, 4)
    p(id="startup_cable", kind="cylinder", r=0.015, h=1.0, material="rubber", at=[0, 0, -0.15], rot=[180, 0, 0],
      segments=12, parent="crossbar", joint={"type": "stretch", "axis": "z", "min": 0.05, "max": -lowest, "rest": 0.5})
    p(id="startup", kind="group", at=[0, 0, -0.15], parent="crossbar",
      joint={"type": "slide", "axis": "z", "min": lowest, "max": -0.05, "rest": -0.5})
    p(id="startup_hook", kind="box", size=[0.16, 0.12, 0.22], material="hazard_stripes", bevel=0.01,
      at=[0, 0, -0.11], parent="startup")

    # loading explosives through the port: a red drum on its side between the cylinder and the left rod, pushed in
    # from the front (the rod stands in the way of anything coming along x)
    p(id="canister", kind="cylinder", r=0.4 * cyl_r, h=0.34, material="red_paint", bevel=0.02, segments=48,
      at=[-cyl_r - 0.37, 0, port_z], rot=[0, 90, 0], parent="hammer", steps=[7, 7],
      joint={"type": "slide", "axis": "y", "min": -1.2, "max": 0, "rest": 0})
    p(id="canister_cap", kind="cylinder", r=0.4 * cyl_r - 0.03, h=0.04, material="red_paint", at=[0, 0, -0.04],
      parent="canister")

    # gasoline: a chrome injector in the left port, a jerry can piped to it; a spark plug in the right port wired
    # to a coil and a battery
    p(id="injector", kind="cylinder", r=0.06, h=0.22, material="chrome", segments=24, at=[-cyl_r - 0.17, 0, port_z],
      rot=[0, 90, 0], parent="hammer", steps=[8, None])
    p(id="can", kind="box", size=[0.42, 0.26, 0.73], material="red_paint", bevel=0.03, at=[-1.95, 0, 0.12 + 0.365],
      parent="hammer", steps=[8, None])
    p(id="can_cap", kind="cylinder", r=0.05, h=0.07, material="black_steel", at=[0.1, 0, 0.365], parent="can")
    p(id="can_label", kind="box", size=[0.34, 0.01, 0.16], material="black_steel", at=[0, -0.133, 0.05], parent="can")
    p(id="can_word", kind="text", body="GASOLINE", height=0.06, depth=0.004, material="safety_yellow",
      at=[0, -0.14, 0.05], parent="can", steps=[8, 8])
    p(id="can_word_diesel", kind="text", body="DIESEL", height=0.07, depth=0.004, material="white_paint",
      at=[0, -0.14, 0.05], parent="can", steps=[9, None])
    p(id="fuel_pipe", kind="pipe", r=0.025, bend=0.08, material="safety_yellow", parent="hammer", steps=[8, None],
      path=[[-1.74, 0, 0.75], [-1.45, -0.2, 0.95], [-1.2, -0.2, port_z], [-cyl_r - 0.17, 0, port_z]])
    p(id="spark_plug", kind="lathe", material="white_paint", segments=24, at=[cyl_r + 0.05, 0, port_z],
      rot=[0, 90, 0], parent="hammer", steps=[8, 8],
      points=[[0, 0], [0.05, 0], [0.05, 0.06], [0.035, 0.08], [0.035, 0.2], [0.015, 0.22], [0, 0.22]])
    p(id="coil", kind="box", size=[0.16, 0.16, 0.3], material="black_steel", bevel=0.01, at=[1.95, 0.3, 0.27],
      parent="hammer", steps=[8, 8])
    p(id="battery", kind="box", size=[0.3, 0.2, 0.22], material="black_steel", bevel=0.01, at=[2.0, -0.35, 0.23],
      parent="hammer", steps=[8, 8])
    p(id="spark_wire", kind="pipe", r=0.012, bend=0.1, material="red_paint", parent="hammer", steps=[8, 8],
      path=[[cyl_r + 0.27, 0, port_z], [1.45, -0.2, port_z + 0.1], [1.75, -0.1, 0.5], [1.95, 0.3, 0.42]])
    p(id="battery_cable", kind="pipe", r=0.012, bend=0.06, material="black_steel", parent="hammer", steps=[8, 8],
      path=[[1.95, 0.22, 0.2], [1.98, 0, 0.2], [2.0, -0.25, 0.34]])

    s.touch(["block", "pile"], ["anvil", "pile"], ["flange", "pile"], ["flange", "anvil"], ["ram", "anvil"], ["cylinder", "flange"],
            ["cylinder", "anvil"], ["lip_low", "anvil"], ["lip_low", "cylinder"], ["lip_high", "cylinder"],
            ["lip_low", "flange"], ["port_ring_l", "cylinder"], ["port_ring_r", "cylinder"],
            ["explosive", "anvil"], ["explosive", "ram"], ["pile_plug", "anvil"], ["pile_plug", "flange"],
            ["rod_l", "socket1"], ["rod_r", "socket2"], ["crossbar", "rod_l"], ["crossbar", "rod_r"],
            ["ear_l", "sleeve_l"], ["ear_r", "sleeve_r"], ["ear_l", "collar"], ["ear_r", "collar"],
            ["sleeve_l", "collar"], ["sleeve_r", "collar"], ["pulley", "crossbar"], ["startup_cable", "crossbar"],
            ["startup_hook", "crossbar"], ["startup_cable", "pulley"],
            ["startup_cable", "startup_hook"], ["canister", "port_ring_l"], ["canister", "cylinder"],
            ["canister", "lip_low"], ["injector", "port_ring_l"], ["injector", "cylinder"], ["can", "flange"],
            ["fuel_pipe", "can"], ["fuel_pipe", "injector"], ["fuel_pipe", "port_ring_l"], ["fuel_pipe", "lip_low"],
            ["spark_plug", "port_ring_r"], ["spark_plug", "cylinder"], ["coil", "flange"], ["battery", "flange"],
            ["spark_wire", "spark_plug"], ["spark_wire", "coil"], ["battery_cable", "coil"],
            ["battery_cable", "battery"], ["can_label", "can"], ["can_word", "can_label"], ["can_word_diesel", "can_label"],
            ["can_word", "can"], ["can_word_diesel", "can"], ["canister_cap", "canister"], ["startup_hook", "ram_eye"],
            *[[f"socket{i}", "flange"] for i in range(1, 5)])
    s.data["couple"] = [{"type": "follow", "driver": "startup", "driven": "startup_cable", "ratio": -1.0}]
    # an anchor is on a part's face to the camera (-y) where another part could cover its middle: the injector's
    # middle is inside its port ring, and pile_low is where the pile is in the picture while it's called heavy
    s.data["anchors"] = {
        "block": ["block", [R, 0, 0.6 * H]], "ram": ["ram", [R, 0, 0.5 * ram_h]], "anvil": ["anvil", [R, 0, 0.2]],
        "cylinder": ["cylinder", [-cyl_r, 0, 0.75 * cyl_h]], "pile_top": ["pile", [D / 2, 0, 29.6]],
        "pile_low": ["pile", [0.2, -0.22, 3.5]],
        "tip": ["pile", [0, -D / 2, 0.05]], "rod_r": ["rod_r", [-0.075, 0, 2.0]], "coil": ["coil", [0, -0.08, 0.1]],
        "port_r": ["port_ring_r", [0, 0, 0.08]], "port_l": ["port_ring_l", [0, 0, 0.08]],
        "rod": ["rod_l", [0.075, 0, 2.0]], "collar": ["collar", [1.3 * R, 0, 0.15]],
        "injector": ["injector", [0, -0.055, 0.02]], "spark_plug": ["spark_plug", [0, 0, 0.2]],
        "can": ["can", [0, -0.13, 0.05]], "explosive": ["explosive", [0.3, 0, 0.12]],
        "canister": ["canister", [0, -0.26, 0.3]], "chamber": ["anvil", [0, 0.2, split + 0.15]]}
    return s.save("diesel_pile_hammer.json")


def iron_block():
    """The pile hammer's iron block on its own (2.2 pile diameters wide, 1.75 m tall, an eye on top), to hang from a
    crane's hook; its origin is the middle of its bottom."""
    s = Spec("iron block", ["the block"])
    s.part(id="block", kind="cylinder", r=0.65, h=1.75, material="steel", bevel=0.04, segments=72)
    s.part(id="eye", kind="torus", major=0.11, minor=0.03, material="steel", at=[0, 0, 1.82], axis="X", parent="block")
    s.data["anchors"] = {"block": ["block", [0.65, 0, 1.05]]}
    return s.save("iron_block.json")


def car_engine():
    """An inline four, about half a metre long, cut open through its cylinders' axes. The crankshaft turns about x
    at z 0.10; each piston rides its crank (throw 3 cm, rod 13 cm), phases 0, 180, 180, 0."""
    s = Spec("four-cylinder car engine", ["the engine"])
    p = s.part
    X, PHASE = [-0.195, -0.065, 0.065, 0.195], [0, 180, 180, 0]
    THROW, ROD, AXIS_Z = 0.03, 0.13, 0.10
    pin_tdc = AXIS_Z + THROW + ROD
    for i, x in enumerate(X, 1):
        p(id=f"bore{i}", kind="cylinder", r=0.041, h=0.19, at=[x, 0, 0.17], helper=True, segments=48)
        p(id=f"dome{i}", kind="sphere", r=0.041, at=[x, 0, 0.36], helper=True, segments=32)
        p(id=f"liner{i}", kind="tube", r_out=0.0412, r_in=0.0395, h=0.17, material="bright_steel", segments=48,
          at=[x, 0, 0.19], cut=True)
    p(id="crankcase", kind="box", size=[0.54, 0.17, 0.17], at=[0, 0, 0.105], helper=True)
    p(id="block", kind="box", size=[0.58, 0.2, 0.42], material="dark_steel", at=[0, 0, 0.21], cut=True, bevel=0.004,
      subtract=[f"bore{i}" for i in range(1, 5)] + [f"dome{i}" for i in range(1, 5)] + ["crankcase"])
    p(id="crank", kind="group", at=[0, 0, AXIS_Z], joint={"type": "spin", "axis": "x"})
    edges = [-0.31] + [v for x in X for v in (x - 0.027, x + 0.027)] + [0.31]
    for k in range(0, len(edges), 2):
        p(id=f"journal{k // 2 + 1}", kind="cylinder", r=0.014, h=round(edges[k + 1] - edges[k], 4),
          material="black_steel", at=[edges[k], 0, 0], rot=[0, 90, 0], segments=32, parent="crank")
    for i, (x, ph) in enumerate(zip(X, PHASE), 1):
        z = THROW if ph == 0 else -THROW
        p(id=f"crankpin{i}", kind="cylinder", r=0.012, h=0.028, material="black_steel", at=[x - 0.014, 0, z],
          rot=[0, 90, 0], segments=24, parent="crank")
        for side, dx in (("a", -0.021), ("b", 0.021)):
            p(id=f"web{i}{side}", kind="box", size=[0.012, 0.05, 0.075], material="black_steel", bevel=0.004,
              at=[x + dx, 0, z / 2], parent="crank")
        p(id=f"piston{i}", kind="lathe", material="bright_steel", segments=48, at=[x, 0, pin_tdc - 0.015],
          points=[[0, 0], [0.0385, 0], [0.0385, 0.046], [0.036, 0.05], [0, 0.05]],
          joint={"type": "slide", "axis": "z", "min": -2 * THROW, "max": 0, "rest": 0})
        p(id=f"rod{i}", kind="group", parent=f"piston{i}", at=[0, 0, 0.015],
          joint={"type": "hinge", "axis": "x", "min": -30, "max": 30, "rest": 0})
        p(id=f"rodbar{i}", kind="box", size=[0.014, 0.016, ROD], material="bright_steel", bevel=0.003,
          at=[0, 0, -ROD / 2], parent=f"rod{i}")
        for side, dx in (("in", -0.022), ("ex", 0.022)):
            p(id=f"valve{i}{side}", kind="lathe", material="bright_steel", segments=24, at=[x + dx, 0.0, 0.356],
              points=[[0, 0], [0.012, 0], [0.010, 0.004], [0.0035, 0.012], [0.0035, 0.11], [0, 0.11]])
        p(id=f"plug{i}", kind="lathe", material="white_paint", segments=24, at=[x, 0, 0.395],
          points=[[0, 0], [0.008, 0], [0.008, 0.03], [0.013, 0.03], [0.013, 0.05], [0.009, 0.05],
                  [0.009, 0.085], [0.004, 0.09], [0, 0.09]])
        s.data["couple"] += [
            {"type": "crank", "driver": "crank", "driven": f"piston{i}", "throw": THROW, "rod": ROD, "phase": ph},
            {"type": "rod", "driver": "crank", "driven": f"rod{i}", "throw": THROW, "rod": ROD, "phase": ph}]
        s.touch([f"piston{i}", "block"], [f"piston{i}", f"liner{i}"], [f"liner{i}", "block"],
                [f"valve{i}in", "block"], [f"valve{i}ex", "block"], [f"plug{i}", "block"],
                [f"rodbar{i}", f"crankpin{i}"], [f"rodbar{i}", f"piston{i}"], [f"web{i}a", f"journal{i}"],
                [f"web{i}b", f"journal{i + 1}"], [f"web{i}a", f"crankpin{i}"], [f"web{i}b", f"crankpin{i}"])
    s.touch(*[[f"journal{k}", "block"] for k in range(1, 6)])
    s.data["anchors"] = {"piston": ["piston2", [0.0385, 0, 0.03]], "plug": ["plug3", [0.013, 0, 0.06]],
                         "chamber": ["piston2", [0, 0, 0.08]], "crank": ["journal3", [0.014, 0, 0.05]]}
    return s.save("car_engine.json")


def crawler_crane():
    """Tracks, a turning cab, a lattice boom that tilts, and a hook hanging straight down from the boom's tip on a
    cable as long as the hook is low."""
    s = Spec("crawler crane", ["the crane"])
    p = s.part
    p(id="crane", kind="group", joint={"type": "spin", "axis": "z"})
    for side, x in (("l", -1.7), ("r", 1.7)):
        p(id=f"track_{side}", kind="box", size=[1.0, 7.2, 1.1], material="rubber", bevel=0.25, at=[x, 0, 0.55])
    p(id="turntable", kind="cylinder", r=1.5, h=0.4, material="dark_steel", at=[0, 0, 1.1], parent="crane")
    p(id="cab", kind="box", size=[3.2, 4.4, 2.4], material="white_paint", bevel=0.08, at=[0.2, 0.7, 2.7],
      parent="crane")
    p(id="cab_panel", kind="box", size=[3.22, 1.4, 1.0], material="blue_paint", at=[0.2, -0.6, 2.4], parent="crane")
    p(id="cab_window", kind="box", size=[1.2, 0.1, 0.9], material="black_steel", at=[-0.7, -1.52, 3.1],
      parent="crane")
    p(id="counterweight", kind="box", size=[3.0, 1.2, 1.7], material="dark_steel", bevel=0.05, at=[0.2, 3.4, 2.4],
      parent="crane")
    p(id="boom_pivot", kind="group", at=[0, -2.4, 2.3], parent="crane",
      joint={"type": "hinge", "axis": "x", "min": 0, "max": 80, "rest": 20})
    p(id="boom", kind="truss", length=46.0, width=1.4, bays=22, material="white_paint", chord=0.08, lace=0.04,
      parent="boom_pivot")
    p(id="tip", kind="group", at=[0, -1.0, 46.0], parent="boom",
      joint={"type": "hinge", "axis": "x", "min": -80, "max": 0, "rest": -20})
    p(id="sheave", kind="cylinder", r=0.45, h=0.3, material="steel", at=[-0.15, 0, 0], rot=[0, 90, 0], parent="tip")
    p(id="cable", kind="cylinder", r=0.03, h=1.0, material="rubber", rot=[180, 0, 0], segments=12, parent="tip",
      joint={"type": "stretch", "axis": "z", "min": 0.5, "max": 60, "rest": 10})
    p(id="hook", kind="group", parent="tip", joint={"type": "slide", "axis": "z", "min": -60, "max": -2.0, "rest": -10})
    p(id="hook_block", kind="box", size=[0.7, 0.45, 1.0], material="hazard_stripes", bevel=0.04, at=[0, 0, -0.5],
      parent="hook")
    p(id="hook_claw", kind="torus", major=0.22, minor=0.08, arc=290, axis="Y", material="hazard_stripes",
      at=[0, 0, -1.3], parent="hook")
    s.data["couple"] = [{"type": "follow", "driver": "boom_pivot", "driven": "tip", "ratio": -1.0},
                        {"type": "follow", "driver": "hook", "driven": "cable", "ratio": -1.0}]
    s.touch(["track_l", "turntable"], ["track_r", "turntable"], ["cab", "turntable"], ["cab_panel", "cab"],
            ["cab_window", "cab"], ["cab_window", "cab_panel"], ["counterweight", "cab"], ["counterweight", "turntable"],
            ["boom", "turntable"], ["boom", "sheave"], ["cable", "sheave"], ["cable", "hook_block"],
            ["hook_block", "hook_claw"], ["cab_panel", "turntable"], ["boom", "cable"])
    s.data["anchors"] = {"hook": ["hook_block", [0.35, 0, 0.0]], "boom": ["boom", [0.7, 0, 25]],
                         "cab": ["cab", [1.6, -1.0, 0]]}
    return s.save("crawler_crane.json")


def claw_hammer():
    """Its pivot at the end of the handle and the head at -0.27 m along x; a shot shrinks or grows it (the nail's
    taps at half size, the giant one at a hundred times)."""
    s = Spec("claw hammer", ["the hammer"])
    p = s.part
    p(id="grip", kind="group")
    p(id="head", kind="group", at=[-0.27, 0, 0], parent="grip")
    p(id="face", kind="lathe", material="steel", segments=40, parent="head",
      points=[[0, -0.055], [0.0105, -0.055], [0.0125, -0.053], [0.0125, -0.03], [0.0105, -0.02], [0, -0.02]])
    p(id="eye", kind="box", size=[0.032, 0.022, 0.045], material="black_steel", bevel=0.003, at=[0, 0, 0.003],
      parent="head")
    p(id="claw", kind="torus", major=0.045, minor=0.0075, arc=75, axis="Y", material="black_steel", segments=24,
      at=[0.045, 0, 0.025], rot=[0, -105, 0], parent="head")
    p(id="handle", kind="lathe", material="wood", segments=32, at=[0.012, 0, 0], rot=[0, 90, 0],
      scale=[1.0, 0.75, 1.0], parent="head",
      points=[[0, 0], [0.0105, 0], [0.0105, 0.02], [0.0125, 0.18], [0.0145, 0.26], [0.0145, 0.282], [0.010, 0.288],
              [0, 0.288]])
    s.touch(["face", "eye"], ["claw", "eye"], ["handle", "eye"], ["handle", "face"])
    s.data["anchors"] = {"head": ["eye", [0.016, 0, 0]], "handle": ["handle", [0.015, 0, 0.15]]}
    return s.save("claw_hammer.json")


def ground_section():
    """The ground in section, as A shows it: a thin dark topsoil, then orange clay, tan sand, blue-grey clay, tan,
    blue-grey, each two to four pile diameters thick, cut open where a pile goes in; a striped barrier round the
    pit and a few cones. The ground's top is z 0, but the layers start 3 cm under it: the desert's sand is the top
    seen from above, and two faces at one height flicker as they fight for the same pixels (the floor in A's rebuild
    did, from high up). From the front the 3 cm reads as part of the topsoil."""
    s = Spec("the ground in section", ["the ground"])
    p = s.part
    layers = [("soil_mid", 0.3), ("soil_top", 2.2), ("soil_low", 1.6), ("soil_deep", 2.0), ("soil_low", 1.4),
              ("soil_deep", 6.0)]
    z = -0.03
    for i, (mat, depth) in enumerate(layers, 1):
        p(id=f"layer{i}", kind="box", size=[80.0, 14.0, depth], material=mat, at=[0, 0, z - depth / 2], cut=True)
        z -= depth
    for i, (x, y, w, d) in enumerate([(0, -3.5, 7.2, 0.15), (-3.5, 0, 0.15, 7.2), (3.5, 0, 0.15, 7.2)], 1):
        p(id=f"barrier{i}", kind="box", size=[w, d, 0.5], material="barrier_stripes", at=[x, y, 0.55])
        for j, t in enumerate((-0.45, 0.45)):
            px, py = (x + t * w, y) if w > d else (x, y + t * d)
            p(id=f"post{i}{j}", kind="cylinder", r=0.05, h=0.8, material="white_paint", at=[px, py, 0])
            s.touch([f"post{i}{j}", f"barrier{i}"], [f"post{i}{j}", "layer1"])
    for i, (x, y) in enumerate([(-4.6, -1.0), (4.2, 2.5), (-2.0, 5.0)], 1):
        p(id=f"cone{i}", kind="cone", r1=0.18, r2=0.03, h=0.7, material="orange_paint", at=[x, y, 0])
        p(id=f"cone{i}_band", kind="cone", r1=0.12, r2=0.09, h=0.12, material="white_paint", at=[0, 0, 0.32],
          parent=f"cone{i}")
        s.touch([f"cone{i}", "layer1"])
    s.touch(*[[f"layer{i}", f"layer{i + 1}"] for i in range(1, len(layers))],
            ["barrier1", "barrier2"], ["barrier1", "barrier3"], ["post10", "barrier2"], ["post11", "barrier3"],
            ["post20", "barrier1"], ["post30", "barrier1"])
    s.data["anchors"] = {"layers": ["layer3", [0, -7, 0]]}
    return s.save("ground_section.json")


def nail():
    """A 10 cm round wire nail: a thin shank, a short point, a thin flat head. Its origin is its point."""
    s = Spec("nail", ["the nail"])
    s.part(id="nail", kind="lathe", material="bright_steel", segments=48,
           points=[[0, 0], [0.0012, 0.008], [0.0012, 0.0986], [0.0036, 0.0989], [0.0036, 0.1], [0, 0.1]])
    s.data["anchors"] = {"head": ["nail", [0.0036, 0, 0.099]], "point": ["nail", [0, 0, 0.002]]}
    return s.save("nail.json")


def wood_block():
    """A's block of pale wood the nail goes into, 50 cm by 20 by 12, standing on z 0; cut open where a nail goes in."""
    s = Spec("wood block", ["the block"])
    s.part(id="block", kind="box", size=[0.5, 0.2, 0.12], material="pale_wood", at=[0, 0, 0.06], bevel=0.002, cut=True)
    return s.save("wood_block.json")


ALL = [wood_block, pile_hammer, iron_block, car_engine, crawler_crane, claw_hammer, ground_section, nail]

if __name__ == "__main__":
    from machines import spec
    for make in ALL:
        data = make()
        print(f"{data['name']}: {len(data['parts'])} parts; {spec.check(data) or 'no problems'}")

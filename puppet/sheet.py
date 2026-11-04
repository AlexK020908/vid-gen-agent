"""A scene sheet: what Claude writes for one scene (prompts/sheet.md), checked against the stage and turned into
what puppet/animate.py draws.

The sheet Claude writes:
    {"figures": [{"who": "the stick figure" | a cast name,
                  "actions": [{"from_ms", "to_ms", "do": a pose, a cycle or "inside", "start"?, "end"?, "at"?,
                               "facing"?}],
                  "attached": [{"joint": "r_hand", "prop": "drill", "angle": 0}]}],
     "crowds": [{"who": "the dead", "count": 6, "do": "reach", "at": "outside_gate", "from_ms", "to_ms",
                 "facing": "right"}],                   # extras (channel `extras`), drawn as a group about a spot
     "set": [{"place": "plate", "at": "stairs_top", "angle": 0, "lift": 0} | {"remove": "plate"}],
     "camera": [{"at_ms": 0, "center": a spot or a figure's name, "zoom": 1.4}],
     "light": {"time": "day" | "dusk" | "night" | "dawn", "lamp": a spot name or "lamp" or ""}}

Names are the story's (the main character is "the stick figure", as in the visual prompts); `who_key` maps them
to puppet keys ("hero", a cast slug). Times are ms from the start of the scene's narration. "inside" puts a
person in a vehicle or a building at a spot, not drawn; `lift` raises a placed prop off the ground by that many
adult heights (a helicopter hovering), its shadow left on the ground.
"""
from __future__ import annotations

import re

from providers import checks
from puppet import rig, state
from puppet.parts import Puppet
from puppet.stage import Stage

JOINTS = ("l_hand", "r_hand", "l_knee", "r_knee")
TIMES = ("day", "dusk", "night", "dawn")
LIGHTS = {  # what each time of day does to the painted place (drawn by day), and the lamp's glow
    "day": {"level": 1.0, "color": (1.0, 1.0, 1.0), "glow": None},
    "dawn": {"level": 0.82, "color": (0.92, 0.93, 1.0), "glow": None},
    "dusk": {"level": 0.72, "color": (1.0, 0.88, 0.78), "glow": {"radius": 0.5, "color": (255, 220, 160), "strength": 0.8}},
    "night": {"level": 0.52, "color": (0.76, 0.8, 1.0), "glow": {"radius": 0.6, "color": (255, 226, 170), "strength": 0.9}},
}
ZOOM = (1.0, 2.5)
CROWD_MAX = 12
LIFT_MAX = 4.0


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40] or "x"


def who_key(name: str) -> str:
    """The puppet key for a figure's name: the main character is "hero", everyone else their slug."""
    return "hero" if name.strip().lower() == checks.HERO else slug(name)


def check(sheet: dict, stage: Stage, people: list[str], props: list[str], duration_ms: int,
          crowds: list[str] = ()) -> list[str]:
    """What's wrong with a sheet, each as an instruction; [] when it can be drawn. `crowds` are the kinds of
    extras the channel has."""
    problems = []
    spots, names = set(stage.spots), {p.lower() for p in people}
    moves = set(rig.POSES) | set(rig.CYCLES) | {rig.INSIDE}

    def spot_ok(where, what: str) -> None:
        if isinstance(where, str) and where not in spots:
            problems.append(f"{what} names the spot {where!r}, which the place doesn't have (it has: "
                            f"{', '.join(sorted(spots))})")

    figures = sheet.get("figures") or []
    if not figures:
        problems.append("figures is empty: every scene shows at least one person")
    seen = set()
    for f in figures:
        who = str(f.get("who", "")).strip()
        if who.lower() not in names:
            problems.append(f"{who!r} isn't in this scene (the people in it: {', '.join(people)})")
        if who.lower() in seen:
            problems.append(f"{who} is listed twice; give one figure all their actions")
        seen.add(who.lower())
        actions = sorted(f.get("actions") or [], key=lambda a: a.get("from_ms", 0))
        if not actions:
            problems.append(f"{who} has no actions")
        last_end = None
        for a in actions:
            do = a.get("do", "")
            if do not in moves:
                problems.append(f"{who}: {do!r} isn't a pose or a movement (poses: {', '.join(rig.POSES)}; "
                                f"movements: {', '.join(rig.CYCLES)})")
            start, end = a.get("from_ms", 0), a.get("to_ms", 0)
            if not 0 <= start < end <= duration_ms + 1:
                problems.append(f"{who}: an action runs {start} to {end} ms, but the scene is 0 to {duration_ms} ms "
                                "and an action ends after it starts")
            if last_end is not None and start < last_end:
                problems.append(f"{who}: actions overlap at {start} ms; one action at a time, each starting when "
                                "the last one ends")
            last_end = end
            if do in rig.CYCLES and not (a.get("start") and a.get("end")):
                problems.append(f"{who}: a {do} needs `start` and `end` spots")
            if do == rig.INSIDE and not a.get("at"):
                problems.append(f"{who}: `inside` needs `at`: the spot of the vehicle or building they're in")
            for key in ("start", "end", "at"):
                if a.get(key):
                    spot_ok(a[key], f"{who}'s {do}")
        if actions and actions[0].get("from_ms", 0) != 0 and "at" not in actions[0] and "start" not in actions[0]:
            problems.append(f"{who}'s first action doesn't say where they are (`at` or `start`)")
        for att in f.get("attached") or []:
            if att.get("joint") not in JOINTS:
                problems.append(f"{who}: things attach to {', '.join(JOINTS)}, not {att.get('joint')!r}")
            if att.get("prop") not in props:
                problems.append(f"{who} holds {att.get('prop')!r}, which isn't among the props "
                                f"({', '.join(props) or 'none'})")
    problems += _shared_spots(figures)
    kinds = {k.lower() for k in crowds}
    for c in sheet.get("crowds") or []:
        who, do = str(c.get("who", "")).strip(), c.get("do", "")
        if who.lower() not in kinds:
            problems.append(f"crowds come as {', '.join(sorted(kinds)) or 'nothing (this channel has none)'}, "
                            f"not {who!r}")
        if not 1 <= int(c.get("count") or 0) <= CROWD_MAX:
            problems.append(f"a crowd of {who} has {c.get('count')}; give 1 to {CROWD_MAX}")
        if do not in set(rig.POSES) | set(rig.CYCLES):
            problems.append(f"a crowd of {who}: {do!r} isn't a pose or a movement")
        if not 0 <= c.get("from_ms", 0) < c.get("to_ms", 0) <= duration_ms + 1:
            problems.append(f"a crowd of {who} runs {c.get('from_ms')} to {c.get('to_ms')} ms, but the scene is 0 to "
                            f"{duration_ms} ms")
        if do in rig.CYCLES and not (c.get("start") and c.get("end")):
            problems.append(f"a crowd of {who}: a {do} needs `start` and `end` spots")
        if do not in rig.CYCLES and not c.get("at"):
            problems.append(f"a crowd of {who} needs `at`: the spot they're gathered at")
        for key in ("start", "end", "at"):
            if c.get(key):
                spot_ok(c[key], f"a crowd of {who}")
    for change in sheet.get("set") or []:
        if "remove" in change:
            if change["remove"] not in props:
                problems.append(f"set removes {change['remove']!r}, which isn't a prop")
        else:
            if change.get("place") not in props:
                problems.append(f"set places {change.get('place')!r}, which isn't a prop ({', '.join(props) or 'none'})")
            spot_ok(change.get("at"), f"placing {change.get('place')}")
            if not change.get("at"):
                problems.append(f"placing {change.get('place')} needs `at`: a spot")
            if not 0 <= float(change.get("lift") or 0) <= LIFT_MAX:
                problems.append(f"{change.get('place')}'s lift of {change.get('lift')} is outside 0 to {LIFT_MAX} "
                                "adult heights")
    for key in sheet.get("camera") or []:
        center = key.get("center")
        if isinstance(center, str) and center not in spots and center.lower() not in seen:
            problems.append(f"the camera's center {center!r} is neither a spot nor a person on this sheet's figures")
        if not ZOOM[0] <= float(key.get("zoom", 1.0)) <= ZOOM[1]:
            problems.append(f"camera zoom {key.get('zoom')} is outside {ZOOM[0]} to {ZOOM[1]}")
    if not sheet.get("camera"):
        problems.append("camera is empty: give at least the opening framing")
    light = sheet.get("light") or {}
    if light.get("time") not in TIMES:
        problems.append(f"light.time must be one of {', '.join(TIMES)}")
    if light.get("lamp") and light["lamp"] != "lamp":
        spot_ok(light["lamp"], "the lamp")
    return problems


def _shared_spots(figures: list[dict]) -> list[str]:
    """Two people standing on the same spot and side while their actions overlap in time."""
    stands = []  # (who, from, to, spot, side)
    for f in figures:
        where, side = None, None
        for a in sorted(f.get("actions") or [], key=lambda a: a.get("from_ms", 0)):
            if a.get("at") or a.get("start"):
                where, side = a.get("at") or a.get("start"), a.get("side")
            if a.get("end"):
                where, side = a["end"], a.get("side")
            if where and a.get("do") not in rig.CYCLES and a.get("do") != rig.INSIDE:   # two can ride in one car
                stands.append((f.get("who"), a.get("from_ms", 0), a.get("to_ms", 0), where, side or ""))
    problems = []
    for i, (who, f0, t0, spot, side) in enumerate(stands):
        for other, f1, t1, spot2, side2 in stands[i + 1:]:
            if other != who and spot == spot2 and side == side2 and f0 < t1 and f1 < t0:
                problems.append(f"{who} and {other} both stand at {spot} at the same time; give each a different "
                                "`side` (left or right of the spot) or a different spot")
    return sorted(set(problems))


def resolve(sheet: dict, stage: Stage, puppets: dict, props, placements: dict, duration_ms: int, fps: int) -> dict:
    """The sheet as puppet/animate.py draws it: figures by puppet key, props standing (`placements`, from the
    set state after this scene's changes), the light, the camera."""
    figures, puppets = [], dict(puppets)
    for f in sheet.get("figures") or []:
        key = who_key(f["who"])
        if key not in puppets:
            raise ValueError(f"no puppet for {f['who']!r}")
        attached = {a["joint"]: {"prop": a["prop"], "angle": float(a.get("angle", 0.0))} for a in f.get("attached") or []}
        figures.append({"who": key, "actions": [dict(a) for a in f.get("actions") or []], "attached": attached})
    for n, crowd in enumerate(sheet.get("crowds") or []):
        figures += _crowd(crowd, n, stage, puppets)
    camera = [{**k, "center": (who_key(k["center"]) if isinstance(k.get("center"), str)
                               and k["center"] not in stage.spots else k.get("center"))}
              for k in sheet.get("camera") or []]
    return {"stage": stage, "puppets": puppets, "props": props, "set": placements, "duration_ms": duration_ms,
            "fps": fps, "light": light_for(sheet.get("light") or {}), "figures": figures, "camera": camera}


def _crowd(crowd: dict, n: int, stage: Stage, puppets: dict) -> list[dict]:
    """A crowd as one figure per member: gathered about its spot (or walking from one to another) a step apart, a
    little nearer or farther, each a touch taller or shorter and out of step with the rest. Their puppets go into
    `puppets` under keys of their own ("the-dead#0.3")."""
    key = who_key(crowd["who"])
    if key not in puppets:
        raise ValueError(f"no puppet for the crowd {crowd['who']!r}")
    base, members = puppets[key], []
    for i in range(int(crowd["count"])):
        ring, side = (i + 1) // 2, (1 if i % 2 else -1)
        dx, dy = side * 0.42 * ring, ((ring % 3) - 1) * 0.07          # in the height of an adult at the spot

        def moved(where):
            x, y = stage.spot(where)
            H = stage.height_at(x, y)
            return [x + dx * H, y + dy * H]

        action = {k: crowd[k] for k in ("from_ms", "to_ms", "do", "facing") if crowd.get(k) not in ("", None)}
        action.update({k: moved(crowd[k]) for k in ("at", "start", "end") if crowd.get(k)})
        action["phase"] = (i * 0.37) % 1.0
        alias = f"{key}#{n}.{i}"
        puppets[alias] = Puppet(base.folder, base.parts, base.scale * (0.94 + 0.04 * (i % 4)))
        members.append({"who": alias, "actions": [action], "attached": {}})
    return members


def light_for(spec: dict) -> dict | None:
    base = LIGHTS.get(spec.get("time") or "day", LIGHTS["day"])
    glow = base["glow"]
    lamp = spec.get("lamp")
    if glow and lamp:
        glow = {**glow, "at": lamp}
    elif glow and not lamp:
        glow = None
    if base["level"] >= 0.999 and not glow:
        return None
    return {"level": base["level"], "color": list(base["color"]), "glow": glow}


def after(sheet: dict, before: dict, place: str) -> dict:
    """The set state after this scene's changes."""
    return state.apply(before, place, sheet.get("set") or [])


def summary(sheet: dict, place_state: dict) -> str:
    """Where everyone ended and what stands in the place, for the next scene's sheet."""
    parts = []
    for f in sheet.get("figures") or []:
        actions = sorted(f.get("actions") or [], key=lambda a: a.get("from_ms", 0))
        if not actions:
            continue
        last, where = actions[-1], "where they were"
        for a in actions:  # a pose without `at` stays where the action before it ended
            where = a.get("end") or a.get("at") or a.get("start") or where
        held = ", ".join(f"{a['prop']} in {a['joint']}" for a in f.get("attached") or [])
        parts.append(f"{f['who']}: ended at {where}, {last.get('do')}" + (f", holding {held}" if held else ""))
    for c in sheet.get("crowds") or []:
        parts.append(f"a crowd of {c.get('count')} {c.get('who')}: ended at {c.get('end') or c.get('at')}, {c.get('do')}")
    standing = "; ".join(f"{prop} at {p.get('at')}" + (f" lifted {p['lift']}" if p.get("lift") else "")
                         for prop, p in place_state.items()) or "nothing placed"
    light = sheet.get("light") or {}
    when = light.get("time") or "day"
    lit = f"Light last time: {when}" + (f", lit by {light['lamp']}" if light.get("lamp") else "") + "."
    return "; ".join(parts) + f". Standing in the place: {standing}. {lit}"


def words_text(words: list[dict]) -> str:
    """The narration with each word's start, in seconds, for timing actions: Day(0.0) 14.(0.4) Midnight.(2.0)"""
    return " ".join(f"{w['word']}({w['start_ms'] / 1000:.1f})" for w in words)


def stage_text(stage: Stage) -> str:
    """The spots as the sheet may name them, with where they are in the picture."""
    w, h = stage.size
    lines = []
    for name, (x, y) in stage.spots.items():
        line = (f"- {name} at x {x / w * 100:.0f}%, y {y / h * 100:.0f}% of the picture, a standing adult "
                f"{stage.height_at(x, y) / h * 100:.0f}% of the picture tall")
        beyond = stage.behind(x, y)
        if beyond:
            line += f", on the far side of the {beyond['name']}" + (", seen through it" if beyond.get("see_through") else "")
        lines.append(line)
    if stage.occluders:
        lines.append("In front: " + ", ".join(o["name"] + (" (bars: people behind show through the gaps)"
                                                          if o.get("see_through") else "") for o in stage.occluders)
                     + " (people behind them are partly hidden)")
    return "\n".join(lines) or "(no spots mapped)"

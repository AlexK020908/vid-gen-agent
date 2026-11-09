"""Claude's work: the writing (outline, script, regen tweaks, titles, topic ideas, reviews) and the looking (picture
checks, stage maps, part names, the props list, scene sheets), and directing a 3D short.

Each method returns its value. `meter` (core.context.Meter) names the call and carries Stop; the stub reports what
the call would have cost through it (`check(usd)` before, `spend(usd)` after), as simulated costs. Claude's own
provider is providers/claude.py, done by the Claude Code session (providers/session.py).
"""
from __future__ import annotations

from typing import Callable, Protocol

LABELS = ["Day 1", "Day 2", "Day 3", "Day 5", "Day 7", "Day 10", "Day 14", "Day 21", "Day 30", "Day 45",
          "Day 60", "Day 75", "Day 90", "Day 120", "Day 150", "Day 180", "Day 210", "Day 240", "Day 270",
          "Day 300", "Day 330", "Day 350", "Day 360", "Day 365"]
BEAT_TITLES = ["The first night", "Finding water", "A real shelter", "The first encounter", "Running low",
               "A risky supply run", "The storm", "Building defenses", "An unexpected ally", "Losing everything",
               "Starting over", "The long winter"]
SKILLS = ["finding and purifying water", "building a shelter that holds heat", "rationing food",
          "starting a fire without matches", "treating a deep cut", "signalling for rescue",
          "navigating without a phone", "preserving meat", "staying warm overnight", "setting a snare",
          "repairing broken tools", "reading the weather"]
FILLER = ("He checks his gear twice, counts what is left, and makes a plan for the next few hours, because "
          "one mistake out here costs more than a day and nobody is coming to fix it for him").split()
STUB_CAST = {"name": "Rosa", "look": "a stick-figure girl in a yellow raincoat", "role": "a lost kid",
             "thread": "He finds her in beat 2 and walks her to her mother's door in beat 3."}
STUB_TRACKER = [{"item": "Water", "unit": "L", "start": 20}, {"item": "Food", "unit": "days", "start": 14}]
STUB_PLACES = [
    {"id": "shelter", "name": "the shelter", "look": "A one-room concrete shelter: a cot on the left, a shelf of "
     "supplies on the right, a steel door at the back, one bare bulb."},
    {"id": "outside", "name": "the street outside", "look": "A wet, empty street of shuttered shops, a burned-out "
     "car on the left, the shelter's steel door on the right."},
]


class Meter(Protocol):
    """`stopped` says the person pressed Stop (stop_writing) on this video's writing (core.context.Meter)."""
    stopped: bool
    def check(self, usd: float) -> None: ...
    def spend(self, usd: float, detail: dict | None = None) -> None: ...


class NoMeter:
    """For calls outside a video (bench-render): nothing is guarded or logged."""

    stopped = False

    def check(self, usd: float) -> None:
        pass

    def spend(self, usd: float, detail: dict | None = None) -> None:
        pass


class LLM(Protocol):
    """`previous` is the draft being revised (None writes a fresh one); `notes` are every note so far.
    `progress(n)` is called with the number of scenes written while the script streams."""

    def outline(self, channel, topic: str, notes: list[str], previous: dict | None, meter: Meter,
                sequel: dict | None = None) -> dict:
        """`sequel` is {part, story} for a next part: its number and the story so far (core/series.py)."""
    def script(self, channel, outline: dict, notes: list[str], previous: dict | None, meter: Meter,
               progress: Callable[[int], None] | None = None, earlier_places: str = "") -> dict:
        """{"places": [{id, name, look}], "scenes": [{idx, beat_idx, label, place, cast, narration, move, tracker,
        set_change, looks, shot, visual_prompt, motion}]}; `previous` has the same shape."""
    def revise_visual(self, channel, scene: dict, note: str, meter: Meter) -> str: ...
    def rewrite_line(self, channel, scene: dict, note: str, meter: Meter) -> str: ...
    def titles(self, channel, outline: dict, meter: Meter) -> dict:
        """{"titles": 3 title options, "thumb_texts": the 2 to 4 words drawn on thumbnail n, one per title,
        "description": the viewer-facing blurb for the YouTube page}"""
    def topics(self, channel, hits: list[dict], taken: list[str], count: int, meter: Meter, families=(), held=(),
               winner: dict | None = None) -> list[dict]:
        """`count` ideas [{title, why, family, based_on: hit numbers from 1}] built on competitors' `hits` (title,
        channel, views, per_day, age_days), none in `taken` or in a `held` family; `families` are the tags in use.
        With `winner` (the channel's own 48-hour winner, as the only hit) they're its follow-ups."""
    def check_picture(self, channel, turn: str, values: dict, pictures: list, meter: Meter) -> list[str]:
        """Looks at `pictures` (paths; the last one is the picture to judge, any before it are what it follows
        from) with prompts/picture.md's `turn` filled with `values`, and returns what a viewer would see is
        wrong, each as an instruction for drawing it again; [] when it's right."""
    def map_stage(self, channel, name: str, picture, meter: Meter) -> dict:
        """Where people stand in a place's picture (sent with a labelled grid; puppet/stage.py): {seen, floor:
        [{x, y, height}], spots: [{name, x, y, what}], light: {x, y, warm}}, positions as percentages."""
    def name_parts(self, channel, picture, names: list[str], meter: Meter) -> dict[str, dict]:
        """Which numbered box on a parts sheet holds each of `names` (puppet/parts.py) and which way it faces:
        {name: {"box": n (0 for one that isn't there), "faces": "left" | "right" | "front"}}."""
    def critique(self, channel, kind: str, values: dict, meter: Meter) -> dict:
        """The reviewer's pass (prompts/critic.md, `kind` outline or script, `values` its text):
        {"verdict": "fine" | "revise", "problems": [{where, what, fix}]} (core/review.py)."""
    def scene_sheet(self, channel, values: dict, context: dict, check: Callable[[dict], list[str]], meter: Meter) -> dict:
        """One scene staged (puppet/sheet.py) from prompts/sheet.md filled with `values`; `context` is the same
        in data (spots, people, props, duration_ms, set_change, narration) for a stub; `check` says what's wrong
        with a draft so it's written again."""
    def inventory(self, channel, cast: str, script: str, have: list[str], meter: Meter) -> dict:
        """{"props": [{name, draw, height, stands}], "people": [{name, scale}]} for a script (prompts/inventory.md);
        `have` are prop names already painted, to reuse."""
    def cast_short(self, channel, values: dict, check: Callable[[dict], list[str]], meter: Meter) -> dict:
        """Who and what a character short needs (prompts/character/cast.md): {"people": [{id, plays, spec}], "things":
        [{id, what, search, meters, moves}]}. `check` says what's wrong with a draft."""
    def pick_thing(self, channel, want: dict, hits: list[dict], sheet, rejected: list[str], meter: Meter) -> dict:
        """{"seen", "choice": which of `hits`, numbered from 1 as on the picture `sheet`, or 0 for none, "why"}."""
    def check_thing(self, channel, want: dict, manifest: dict, sheet, round_n: int, meter: Meter) -> dict:
        """What a thing's sheet shows, and how to set it up (prompts/character/thing.md)."""
    def direct(self, channel, values: dict, check: Callable[[dict], list[str]], meter: Meter) -> dict:
        """{"scenes": [...]}: the whole short in the scene language (prompts/character/direct.md, scenes/direction.py)."""
    def check_frames(self, channel, said: str, planned: str, sheets: list[dict], every: int, meter: Meter) -> list[dict]:
        raise NotImplementedError

    def check_film(self, channel, shots: str, sheet, meter: Meter) -> list[dict]:
        """What a viewer would see is wrong on a sheet of frames: [{shot, what, fix}]."""
    def check_joins(self, channel, turn: str, values: dict, meter: Meter) -> dict:
        """The joins between lines and between shots (prompts/transitions.md, `turn` script or film):
        {"seen", "problems": [{at, in: words | picture, what, fix, serious}]} (core/transitions.py)."""
    def diagram(self, channel, topic: str, notes: list[str], previous: dict | None, meter: Meter) -> dict:
        """A systems short's spec (diagram/spec.py, prompts/diagram/spec.md), passing diagram/make.py's checks."""
    def look_diagram(self, channel, phases: str, sheet, meter: Meter) -> list[dict]:
        """What a viewer would see is wrong on a sheet of a systems short's frames: [{phase, what, fix}]."""


def _cost(meter: Meter, usd: float) -> None:
    meter.check(usd)
    meter.spend(usd)


def _spread(items: list[str], n: int) -> list[str]:
    if n <= 1:
        return items[:1]
    if n > len(items):
        return items + [f"Day {365 + 10 * i}" for i in range(1, n - len(items) + 1)]
    return [items[round(i * (len(items) - 1) / (n - 1))] for i in range(n)]


class StubLLM:
    """Deterministic placeholder text so the pipeline runs end to end for $0."""

    def __init__(self, n_scenes: int = 12) -> None:
        self.n_scenes = n_scenes
        self.judge: Callable[[dict], list[str]] | None = None  # tests: what check_picture finds, from its values
        self.critic_problems: list[dict] = []  # tests: what the reviewer finds next (used once, then it passes)
        self.join_problems: list[dict] = []    # tests: what the check of the joins finds next (used once, then it passes)
        self.look_problems: list[dict] = []    # tests: what the look at a systems short finds next (used once)

    def check_picture(self, channel, turn: str, values: dict, pictures: list, meter: Meter) -> list[str]:
        _cost(meter, 0.01)
        return list(self.judge(values)) if self.judge else []

    def critique(self, channel, kind: str, values: dict, meter: Meter) -> dict:
        _cost(meter, 0.02)
        problems, self.critic_problems = list(self.critic_problems), []
        return {"verdict": "revise" if problems else "fine", "problems": problems}

    def map_stage(self, channel, name: str, picture, meter: Meter) -> dict:
        _cost(meter, 0.01)
        return {"seen": f"placeholder map of {name}",
                "floor": [{"x": 12, "y": 94, "height": 62}, {"x": 50, "y": 90, "height": 56},
                          {"x": 88, "y": 94, "height": 62}],
                "spots": [{"name": "door_left", "x": 18, "y": 94, "what": "a door"},
                          {"name": "middle", "x": 50, "y": 90, "what": "the middle of the floor"},
                          {"name": "stairs_top", "x": 80, "y": 93, "what": "the top of the stairs"}],
                "occluders": [{"name": "table", "base_y": 97, "polygon": [
                    {"x": 60, "y": 80}, {"x": 75, "y": 80}, {"x": 75, "y": 97}, {"x": 60, "y": 97}]}],
                "light": {"x": 50, "y": 10, "warm": True}}

    def name_parts(self, channel, picture, names: list[str], meter: Meter) -> dict[str, dict]:
        _cost(meter, 0.01)
        # the stub sheet draws them biggest first, in the order asked
        return {n: {"box": i, "faces": "front" if n == "head" else "right"} for i, n in enumerate(names, 1)}

    def scene_sheet(self, channel, values: dict, context: dict, check: Callable[[dict], list[str]], meter: Meter) -> dict:
        """The main character walks from the first spot to the second over the first half, then kneels; each cast
        member stands at the next spot; a set change stands the first prop at the second spot; night when the
        line says so."""
        _cost(meter, 0.02)
        spots, people, props = context["spots"], context["people"], context["props"]
        total = int(context["duration_ms"])
        half = max(1, total // 2)
        figures = []
        for i, who in enumerate(people):
            if i == 0:
                actions = [{"from_ms": 0, "to_ms": half, "do": "limp", "start": spots[0], "end": spots[min(1, len(spots) - 1)]},
                           {"from_ms": half, "to_ms": total, "do": "kneel"}]
            else:
                actions = [{"from_ms": 0, "to_ms": total, "do": "stand_free", "at": spots[min(i + 1, len(spots) - 1)],
                            "facing": "left"}]
            figures.append({"who": who, "actions": actions, "attached": []})
        changes = ([{"place": props[0], "at": spots[min(1, len(spots) - 1)], "angle": 0.0}]
                   if context.get("set_change") and props else [])
        night = any(w in context.get("narration", "").lower() for w in ("night", "midnight", "dark"))
        sheet = {"figures": figures, "set": changes,
                 "camera": [{"at_ms": 0, "center": people[0], "zoom": 1.4}, {"at_ms": total, "center": people[0], "zoom": 1.6}],
                 "light": {"time": "night" if night else "day", "lamp": "lamp" if night else ""}}
        problems = check(sheet)
        if problems:
            raise ValueError("the stub sheet failed its own check: " + "; ".join(problems))
        return sheet

    def inventory(self, channel, cast: str, script: str, have: list[str], meter: Meter) -> dict:
        _cost(meter, 0.02)
        props = []
        if "cot" in script.lower() and "cot" not in have:
            props.append({"name": "cot", "draw": "a folding camp cot, seen from the side", "height": 0.45, "stands": "bottom"})
        people = [{"name": line.split(":")[0].strip("- ").strip(), "scale": 1.0}
                  for line in cast.splitlines() if line.startswith("- ")]
        return {"props": props, "people": people}

    def cast_short(self, channel, values: dict, check: Callable[[dict], list[str]], meter: Meter) -> dict:
        _cost(meter, 0.02)
        first = values["people"].splitlines()[0].split(":")[0].strip("- ")
        return {"people": [{"id": first, "plays": "the person it happens to", "spec": {}}], "things": []}

    def pick_thing(self, channel, want: dict, hits: list[dict], sheet, rejected: list[str], meter: Meter) -> dict:
        _cost(meter, 0.01)
        return {"seen": "a sheet of models", "choice": min(len(rejected) + 1, len(hits)), "why": "the first one left"}

    def check_thing(self, channel, want: dict, manifest: dict, sheet, round_n: int, meter: Meter) -> dict:
        _cost(meter, 0.01)
        return {"seen": "the model", "right_thing": True, "turn": 0, "tilt": [0, 0], "meters": want["meters"], "rest": "",
                "moves": {}, "spots": {}, "problems": []}

    def direct(self, channel, values: dict, check: Callable[[dict], list[str]], meter: Meter) -> dict:
        """One scene on the first person, cutting every 3 seconds to a new picture, with a blow to give them something to do."""
        _cost(meter, 0.05)
        total, who = values["total"], values["cast_ids"][0]
        starts = [float(t) for t in range(0, max(1, int(total)), 3)]
        scene = {"from": 0, "to": total, "set": "sky_set",
                 "cast": {who: {"type": "person", "character": who, "at": [0, 0], "stance": values["stances"].split(", ")[0]}},
                 "happens": [{"do": "knock", "t": 0.5, "who": who, "size": 3, "axis": [1, 0, 0]}],
                 "shots": [{"t": t, "on": f"{who}:eyes", "frame": round(0.3 * 1.4 ** (i % 8), 3), "angle": [-60 + 40 * (i // 8), 0], "lens": 26,
                            "to": {"frame": round(0.36 * 1.4 ** (i % 8), 3)}} for i, t in enumerate(starts)]}
        direction = {"scenes": [scene]}
        problems = check(direction)
        if problems:
            raise ValueError("the stub direction failed its own check: " + "; ".join(problems))
        return direction

    def check_film(self, channel, shots: str, sheet, meter: Meter) -> list[dict]:
        _cost(meter, 0.01)
        return []

    def check_frames(self, channel, said: str, planned: str, sheets: list[dict], every: int, meter: Meter) -> list[dict]:
        _cost(meter, 0.01)
        return []

    def check_joins(self, channel, turn: str, values: dict, meter: Meter) -> dict:
        _cost(meter, 0.01)
        problems, self.join_problems = list(self.join_problems), []
        return {"seen": f"the joins of the {turn}", "problems": problems}

    def diagram(self, channel, topic: str, notes: list[str], previous: dict | None, meter: Meter) -> dict:
        """The worked example (diagram/examples/cache.json), so a systems short runs end to end for $0."""
        import json
        from pathlib import Path
        _cost(meter, 0.05)
        return json.loads((Path(__file__).resolve().parent.parent / "diagram" / "examples" / "cache.json")
                          .read_text(encoding="utf-8"))

    def look_diagram(self, channel, phases: str, sheet, meter: Meter) -> list[dict]:
        _cost(meter, 0.01)
        problems, self.look_problems = list(self.look_problems), []
        return problems

    def outline(self, channel, topic: str, notes: list[str], previous: dict | None, meter: Meter,
                sequel: dict | None = None) -> dict:
        _cost(meter, 0.05)
        n_beats = max(4, round(self.n_scenes / 5))
        labels = _spread(LABELS, n_beats)
        beats = [
            {"label": labels[i], "title": BEAT_TITLES[i % len(BEAT_TITLES)],
             "summary": f"Placeholder beat {i + 1} for '{topic}'.", "skill": SKILLS[i % len(SKILLS)],
             "hero": i % 4 == 0}
            for i in range(n_beats)
        ]
        for i, beat in enumerate(beats):
            beat["cast"] = [STUB_CAST["name"]] if i in (1, 2) else []
        hook = f"Placeholder hook: one ordinary guy, {channel.scenario_family}: {topic}."
        if sequel:
            hook = f"Part {sequel['part']}. Previously: {sequel['story'][:60]}. {hook}"
        if notes:
            hook += f" (revision {len(notes)}, last note: {notes[-1]})"
        return {"topic": topic, "hook": hook, "backstory": "Placeholder backstory: it started on the news, then it "
                "reached his street.", "cast": [dict(STUB_CAST)], "tracker": [dict(t) for t in STUB_TRACKER],
                "beats": beats, "ending": "Placeholder ending: he makes it, changed."}

    def script(self, channel, outline: dict, notes: list[str], previous: dict | None, meter: Meter,
               progress: Callable[[int], None] | None = None, earlier_places: str = "") -> dict:
        """Beats alternate between the two places (each move told in the line), the tracker drops a little each
        beat, the shelter is barricaded in beat 1, and the outline's cast are in the beats that list them."""
        _cost(meter, round(0.6 * self.n_scenes / 120, 4))
        beats = outline["beats"]
        per_beat = [self.n_scenes // len(beats) + (1 if i < self.n_scenes % len(beats) else 0)
                    for i in range(len(beats))]
        tracker = outline.get("tracker") or []
        scenes, clips = [], 0
        for b, (beat, count) in enumerate(zip(beats, per_beat)):
            place = STUB_PLACES[b % 2]["id"]
            for k in range(count):
                idx = len(scenes) + 1
                lead = f"{beat['label']}. {beat['title']}, part {k + 1}."
                move = ""
                if scenes and scenes[-1]["place"] != place:
                    move = "He steps outside" if place == "outside" else "Back in the shelter"
                    lead += f" {move}."
                lead += "".join(f" {name} is with him." for name in beat.get("cast") or [])
                if notes and idx == 1:
                    lead += f" Revised per note: {notes[-1]}."
                narration = " ".join((lead.split() + FILLER)[:34]) + "."
                motion = "kenburns"
                if k == 0 and beat.get("hero") and clips < channel.clips_per_video:
                    motion, clips = "clip", clips + 1
                scenes.append({
                    "idx": idx, "beat_idx": b, "label": beat["label"], "place": place,
                    "cast": list(beat.get("cast") or []), "narration": narration, "move": move,
                    "tracker": [{"item": t["item"], "amount": max(0, t["start"] - b)} for t in tracker] if k == 0 else [],
                    "set_change": "a cot is pushed against the steel door" if b == 0 and k == 0 else "",
                    "looks": [{"who": "the stick figure", "now": "a red backpack"}] if b == 0 and k == 0 else [],
                    "shot": "close-up" if k == 1 else "wide",
                    "visual_prompt": f"the stick figure, {beat['title'].lower()}, shot {k + 1}", "motion": motion,
                })
        if progress:
            progress(len(scenes))
        return {"places": [dict(p) for p in STUB_PLACES], "scenes": scenes}

    def revise_visual(self, channel, scene: dict, note: str, meter: Meter) -> str:
        _cost(meter, 0.01)
        return f"{scene['visual_prompt']} [regen {scene['regen_count'] + 1}: {note}]"

    def rewrite_line(self, channel, scene: dict, note: str, meter: Meter) -> str:
        _cost(meter, 0.01)
        first = scene["narration"].split(".")[0]
        return f"{first}. (Rewritten per note: {note})"

    def titles(self, channel, outline: dict, meter: Meter) -> dict:
        _cost(meter, 0.02)
        topic = outline["topic"]
        part = f" (Part {outline['part']})" if outline.get("part", 1) > 1 else ""
        return {"titles": [t[:90] + part for t in (f"I Survived 365 Days: {topic}", f"{topic} (Day 1 to Day 365)",
                                                   f"What It Really Takes: {topic}")],
                "thumb_texts": ["365 DAYS ALONE", "THE WORST NIGHT", "HOW DID I LAST?"],
                "description": f"Placeholder description for viewers: one ordinary guy, {topic}, told day by day from "
                               "Day 1, with the water running out and nobody coming. A stick-figure survival story."}

    def topics(self, channel, hits: list[dict], taken: list[str], count: int, meter: Meter, families=(), held=(),
               winner: dict | None = None) -> list[dict]:
        _cost(meter, 0.03)
        if winner:
            return _stub_follow_ups(winner, taken, count, held)
        return _stub_topics(hits, taken, count, held)


STUB_TOPICS = [("stranded on an oil rig", "ocean"), ("in a flooded subway", "underground"),
               ("trapped in a shopping mall", "city"), ("on a drifting cargo ship", "ocean"),
               ("alone in a mountain cabin", "wilderness"), ("in an abandoned hospital", "city"),
               ("on a frozen lake", "frozen north"), ("in a desert bunker", "underground")]


def _stub_topics(hits: list[dict], taken: list[str], count: int, held=()) -> list[dict]:
    have = {t.lower() for t in taken}
    fresh = [(f"Day 1 to Day 365 {s}", f) for s, f in STUB_TOPICS
             if f"day 1 to day 365 {s}" not in have and f not in held]
    out = []
    for i, (title, family) in enumerate(fresh[:count]):
        n = i % len(hits)
        hit = hits[n]
        out.append({"title": title, "family": family, "based_on": [n + 1],
                    "why": f"Same hook as \"{hit['title']}\" ({hit['per_day']:,.0f} views a day), in a setting this "
                           "channel hasn't done."})
    return out


def _stub_follow_ups(winner: dict, taken: list[str], count: int, held=()) -> list[dict]:
    have = {t.lower() for t in taken}
    ideas = [(f"{winner['title']}: the second year", winner["family"] or "sequel"),
             *((f"Day 1 to Day 365 {s}", f) for s, f in STUB_TOPICS)]
    fresh = [(t, f) for t, f in ideas if t.lower() not in have and f not in held][:count]
    return [{"title": t, "family": f, "based_on": [1],
             "why": f"Follows \"{winner['title']}\", which beat this channel's medians at 48 hours."} for t, f in fresh]

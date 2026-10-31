"""Text generation: outline, script, regen tweaks, titles, topic ideas.

Each method returns its value and reports spend through `meter` (core.context.Meter): `check(usd)`
before a call, `spend(usd)` after it. One Claude method can make two API calls, and a failed call
still costs money, so a single returned number wouldn't do. The Claude provider is providers/claude.py.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Callable, Iterator, Protocol

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
    """`stopped` and `writing(close)` let the Stop button cut a streaming call off (core.context.Meter)."""
    stopped: bool
    def check(self, usd: float) -> None: ...
    def spend(self, usd: float, detail: dict | None = None) -> None: ...
    def writing(self, close: Callable[[], None]): ...


class NoMeter:
    """For calls outside a video (bench-render): nothing is guarded or logged."""

    stopped = False

    def check(self, usd: float) -> None:
        pass

    def spend(self, usd: float, detail: dict | None = None) -> None:
        pass

    @contextmanager
    def writing(self, close: Callable[[], None]) -> Iterator[None]:
        yield


class LLM(Protocol):
    """`previous` is the draft being revised (None writes a fresh one); `notes` are every note so far.
    `progress(n)` is called with the number of scenes written while the script streams."""

    def outline(self, channel, topic: str, notes: list[str], previous: dict | None, meter: Meter) -> dict: ...
    def script(self, channel, outline: dict, notes: list[str], previous: dict | None, meter: Meter,
               progress: Callable[[int], None] | None = None) -> dict:
        """{"places": [{id, name, look}], "scenes": [{idx, beat_idx, label, place, cast, narration, move, tracker,
        set_change, shot, visual_prompt, motion}]}; `previous` has the same shape."""
    def revise_visual(self, channel, scene: dict, note: str, meter: Meter) -> str: ...
    def rewrite_line(self, channel, scene: dict, note: str, meter: Meter) -> str: ...
    def titles(self, channel, outline: dict, meter: Meter) -> dict:
        """{"titles": 3 title options, "thumb_texts": the 2 to 4 words drawn on thumbnail n, one per title}"""
    def topics(self, channel, hits: list[dict], taken: list[str], count: int, meter: Meter, families=(), held=(),
               winner: dict | None = None) -> list[dict]:
        """`count` ideas [{title, why, family, based_on: hit numbers from 1}] built on competitors' `hits` (title,
        channel, views, per_day, age_days), none in `taken` or in a `held` family; `families` are the tags in use.
        With `winner` (the channel's own 48-hour winner, as the only hit) they're its follow-ups."""


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

    def outline(self, channel, topic: str, notes: list[str], previous: dict | None, meter: Meter) -> dict:
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
        if notes:
            hook += f" (revision {len(notes)}, last note: {notes[-1]})"
        return {"topic": topic, "hook": hook, "backstory": "Placeholder backstory: it started on the news, then it "
                "reached his street.", "cast": [dict(STUB_CAST)], "tracker": [dict(t) for t in STUB_TRACKER],
                "beats": beats, "ending": "Placeholder ending: he makes it, changed."}

    def script(self, channel, outline: dict, notes: list[str], previous: dict | None, meter: Meter,
               progress: Callable[[int], None] | None = None) -> dict:
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
                    "shot": "close-up" if k == 1 else "wide",
                    "visual_prompt": f"stick figure, {beat['title'].lower()}, shot {k + 1}", "motion": motion,
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
        return {"titles": [t[:100] for t in (f"I Survived 365 Days: {topic}", f"{topic} (Day 1 to Day 365)",
                                             f"What It Really Takes: {topic}")],
                "thumb_texts": ["365 DAYS ALONE", "THE WORST NIGHT", "HOW DID I LAST?"]}

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

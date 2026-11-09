"""What Claude is asked to do and how its reply is read: the outline, the script, scene fixes, titles with their
thumbnail text, topic ideas from competitors' recent hits, the reviewer's reads, and the looking: each drawn
picture checked against its scene, a place mapped into a stage, a parts sheet's parts named, a script's props
listed, and each scene staged.

Every call fills a prompt file (providers/prompts.py: the system part with the channel's facts, then the turn with
the idea, outline, notes and the rest) and asks for JSON in a schema, which is checked in code
(providers/checks.py). The request goes to the Claude Code session as a job (providers/session.py, core/jobs.py),
where the answer is checked as it comes in. A reply that still fails its checks when the stage reads it (after a
restart, when no check was registered) gets one more try with the problems listed; after that the stage fails
with them on the error card (FinalError).

Pictures go with a request as image blocks naming the file and its contents' hash, so a picture drawn again is a
new request; take_job sends them to the session as JPEGs (server/claude_code.py).
"""
from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Callable

from core import formats
from core.errors import FinalError
from providers import checks, prompts
from providers.llm import Meter

log = logging.getLogger("stickfleet.claude")

WHAT = {"outline": "outline", "script": "script", "regen": "scene fix", "titles": "titles", "topic": "topic ideas",
        "critic": "review", "picture": "picture check", "map": "stage map", "parts": "part names",
        "inventory": "props list", "sheet": "scene sheet", "cast": "list of what the short needs",
        "source": "choice of a model", "thing": "check of a model", "direct": "direction", "film": "look at the shots", "frames": "review of the frames",
        "transitions": "check of the joins"}
PICTURE_VALUES = ("idx", "label", "shot", "before", "narration", "visual_prompt", "people", "what", "images")  # picture.md
SHOWN = 25           # problems listed in a retry turn
FIX = ("That reply has problems the pipeline checks for:\n{problems}\n\n"
       "Fix them and send the whole reply again. Keep everything these problems don't touch as it was.")


def _obj(props: dict) -> dict:
    return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}


STR = {"type": "string"}
NUM = {"type": "number"}
NAMES = {"type": "array", "items": STR}
# Fields come back in the order they're listed, so each is written knowing the ones before it: the cast and the
# tracker before the beats, the places before the scenes, and a scene's place, cast and line before its picture.
OUTLINE = _obj({
    "hook": STR, "backstory": STR,
    "cast": {"type": "array", "items": _obj({"name": STR, "look": STR, "role": STR, "thread": STR})},
    "tracker": {"type": "array", "items": _obj({"item": STR, "unit": STR, "start": NUM})},
    "beats": {"type": "array", "items": _obj(
        {"label": STR, "title": STR, "summary": STR, "skill": STR, "hero": {"type": "boolean"}, "cast": NAMES})},
    "ending": STR})
SCRIPT = _obj({
    "places": {"type": "array", "items": _obj({"id": STR, "name": STR, "look": STR})},
    "scenes": {"type": "array", "items": _obj(
        {"beat": {"type": "integer"}, "label": STR, "place": STR, "cast": NAMES, "narration": STR, "move": STR,
         "tracker": {"type": "array", "items": _obj({"item": STR, "amount": NUM})}, "set_change": STR,
         "looks": {"type": "array", "items": _obj({"who": STR, "now": STR})},
         "shot": {"type": "string", "enum": list(checks.SHOTS)}, "visual_prompt": STR,
         "motion": {"type": "string", "enum": list(checks.MOTIONS)}})}})
VISUAL = _obj({"visual_prompt": STR})
LINE = _obj({"narration": STR})
PICTURE = _obj({"seen": STR, "noticed": {"type": "array", "items": STR},  # what it shows, everything off, then
                "problems": {"type": "array", "items": STR}})               # the few things worth a redraw
TITLES = _obj({"titles": {"type": "array", "items": STR}, "thumb_texts": {"type": "array", "items": STR},
               "description": STR})
TOPICS = _obj({"topics": {"type": "array", "items": _obj(
    {"title": STR, "why": STR, "family": STR, "based_on": {"type": "array", "items": {"type": "integer"}}})}})
STAGE = _obj({"seen": STR,  # puppet/stage.py: where people stand in a place and how tall, as percentages
              "floor": {"type": "array", "items": _obj({"x": NUM, "y": NUM, "height": NUM})},
              "spots": {"type": "array", "items": _obj({"name": STR, "x": NUM, "y": NUM, "what": STR})},
              "occluders": {"type": "array", "items": _obj(
                  {"name": STR, "polygon": {"type": "array", "items": _obj({"x": NUM, "y": NUM})}, "base_y": NUM,
                   "see_through": {"type": "boolean"}})},
              "light": _obj({"x": NUM, "y": NUM, "warm": {"type": "boolean"}})})
PARTS = _obj({"seen": STR, "parts": {"type": "array", "items": _obj(
    {"name": STR, "box": {"type": "integer"}, "faces": {"type": "string", "enum": ["left", "right", "front"]}})}})
PUPPET_VALUES = ("name", "names")  # puppet.md's turns
_ACTION = _obj({"from_ms": {"type": "integer"}, "to_ms": {"type": "integer"}, "do": STR, "start": STR, "end": STR,
                "at": STR, "side": STR, "facing": STR, "look": STR})  # "" for a key that doesn't apply
SHEET = _obj({  # puppet/sheet.py: one scene staged
    "figures": {"type": "array", "items": _obj(
        {"who": STR, "actions": {"type": "array", "items": _ACTION},
         "attached": {"type": "array", "items": _obj({"joint": STR, "prop": STR, "angle": NUM})}})},
    "crowds": {"type": "array", "items": _obj(
        {"who": STR, "count": {"type": "integer"}, "from_ms": {"type": "integer"}, "to_ms": {"type": "integer"},
         "do": STR, "start": STR, "end": STR, "at": STR, "facing": STR})},
    "set": {"type": "array", "items": _obj({"place": STR, "at": STR, "angle": NUM, "lift": NUM, "remove": STR})},
    "camera": {"type": "array", "items": _obj({"at_ms": {"type": "integer"}, "center": STR, "zoom": NUM})},
    "light": _obj({"time": STR, "lamp": STR})})
INVENTORY = _obj({  # prompts/inventory.md: the props a script uses and how big each cast member is
    "props": {"type": "array", "items": _obj({"name": STR, "draw": STR, "height": NUM, "stands": STR})},
    "people": {"type": "array", "items": _obj({"name": STR, "scale": NUM})}})
SHEET_VALUES = ("idx", "label", "shot", "duration_ms", "place_name", "words", "visual_prompt", "set_change", "looks",
                "people", "crowds", "stage", "props", "poses", "cycles", "previous", "state")
SHORT_OUTLINE = _obj({"shape": {"type": "string", "enum": list(checks.SHORT_SHAPES)}, "hook": STR, "fact": STR, "turn": STR,  # prompts/character/: a character short (core/formats.py)
                      "beats": {"type": "array", "items": _obj({"title": STR, "summary": STR})}, "ending": STR})
SHORT_SCRIPT = _obj({"scenes": {"type": "array", "items": _obj({"beat": {"type": "integer"}, "narration": STR, "shows": STR})}})
SHORT_TITLES = _obj({"titles": {"type": "array", "items": STR}, "description": STR})
ANY = {"type": "object"}
SHORT_CAST = _obj({
    "people": {"type": "array", "items": _obj({"id": STR, "plays": STR, "spec": ANY})},
    "things": {"type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["id", "what", "search", "meters", "moves"],
                                          "properties": {"id": STR, "what": STR, "search": STR, "meters": NUM, "moves": {"type": "boolean"},
                                                         "parts": {"type": "array", "items": ANY}, "spots": ANY}}}})
SOURCE = _obj({"seen": STR, "choice": {"type": "integer"}, "why": STR})
THING_LOOK = _obj({"seen": STR, "right_thing": {"type": "boolean"}, "turn": NUM,
                   "tilt": {"type": "array", "items": NUM}, "meters": NUM, "rest": STR, "moves": ANY, "spots": ANY,
                   "problems": NAMES})
DIRECTION = {"type": "object", "additionalProperties": False, "required": ["scenes"],
             "properties": {"scenes": {"type": "array", "items": ANY}, "marks": {"type": "array", "items": ANY}}}
FILM = _obj({"seen": STR, "problems": {"type": "array", "items": _obj({"shot": STR, "what": STR, "fix": STR})}})
FRAMES = _obj({"seen": STR, "problems": {"type": "array", "items": _obj({"at": STR, "what": STR, "fix": STR})}})
CRITIQUE = _obj({"verdict": {"type": "string", "enum": ["fine", "revise"]},  # prompts/critic.md, core/review.py
                 "problems": {"type": "array", "items": _obj({"where": STR, "what": STR, "fix": STR})}})
JOINS = _obj({"seen": STR, "problems": {"type": "array", "items": _obj(  # prompts/transitions.md, core/transitions.py
    {"at": STR, "in": {"type": "string", "enum": ["words", "picture"]}, "what": STR, "fix": STR, "serious": {"type": "boolean"}})}})
JOIN_VALUES = {"outline": "", "lines": "", "cuts": "", "measured": "", "sheets": ""}   # what prompts/transitions.md's turns fill


class _SceneCounter:
    """Counts scenes in the script's JSON so the thread can show how many were written."""
    KEY = '"narration"'

    def __init__(self, progress: Callable[[int], None]) -> None:
        self.progress = progress
        self.reset()

    def reset(self) -> None:
        self.n, self.tail = 0, ""

    def __call__(self, chunk: str) -> None:
        window = self.tail + chunk
        found = window.count(self.KEY)
        self.tail = window[-(len(self.KEY) - 1):]  # too short to hold a whole key, so nothing is counted twice
        if found:
            self.n += found
            self.progress(self.n)


def _tidy_sheet(data: dict) -> dict:
    """The sheet with the schema's empty strings dropped, as puppet/sheet.py reads it."""
    figures = []
    for f in data.get("figures") or []:
        actions = [{k: v for k, v in a.items() if v not in ("", None)} for a in f.get("actions") or []]
        figures.append({"who": f.get("who", "").strip(), "actions": actions, "attached": list(f.get("attached") or [])})
    crowds = [{k: v for k, v in c.items() if v not in ("", None)} for c in data.get("crowds") or []]
    changes = []
    for c in data.get("set") or []:
        if c.get("remove"):
            changes.append({"remove": c["remove"]})
        elif c.get("place"):
            change = {"place": c["place"], "at": c.get("at", ""), "angle": float(c.get("angle") or 0.0)}
            if c.get("lift"):
                change["lift"] = float(c["lift"])
            changes.append(change)
    light = data.get("light") or {}
    return {"figures": figures, "crowds": crowds, "set": changes, "camera": list(data.get("camera") or []),
            "light": {"time": str(light.get("time", "")).strip().lower(), "lamp": str(light.get("lamp") or "").strip()}}


def _checked(text: str, check: Callable[[dict], list[str]]) -> tuple[dict | None, list[str]]:
    """The reply parsed, and what its checks found wrong with it."""
    try:
        data = json.loads(text)
        return data, check(data)
    except (ValueError, KeyError, TypeError, AttributeError) as e:
        return None, [f"the reply isn't the JSON that was asked for ({type(e).__name__}: {e})"]


def _image(path: Path) -> dict:
    """A picture sent with a request: the file, and a hash of what's in it, so a picture drawn again is a new
    request rather than the old one's answer."""
    return {"type": "image", "path": str(path), "sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest()}


class ClaudeLLM:
    """The LLM protocol (providers/llm.py) as prompts, schemas and checks. `_call` sends one request and returns
    the reply's text; providers/session.py's SessionLLM sends it to the Claude Code session."""

    def __init__(self, config) -> None:
        self.config = config

    # --- the LLM protocol (providers/llm.py) -------------------------------------------------

    def outline(self, channel, topic: str, notes: list[str], previous: dict | None, meter: Meter,
                sequel: dict | None = None) -> dict:
        if channel.format == formats.CHARACTER:
            return self._short_outline(channel, topic, notes, previous, meter)
        values = {"idea": topic, "notes": prompts.notes_text(notes),
                  "previous": prompts.outline_text(previous) if previous else "",
                  "part": sequel["part"] if sequel else 1, "story_so_far": sequel["story"] if sequel else ""}
        turn = "revise" if previous else "next_part" if sequel else "new"
        data = self._ask("outline", "outline.md", turn, channel, values, OUTLINE, checks.outline, meter)
        cast = [{k: c[k].strip() for k in ("name", "look", "role", "thread")} for c in data["cast"]]
        named = {c["name"].lower(): c["name"] for c in cast}  # beats spell names the way the cast does
        beats = [{"label": b["label"].strip(), "title": b["title"].strip(), "summary": b["summary"].strip(),
                  "skill": b["skill"].strip(), "hero": bool(b["hero"]),
                  "cast": [named[n.strip().lower()] for n in b["cast"]]} for b in data["beats"]]
        tracker = [{"item": t["item"].strip(), "unit": t["unit"].strip(), "start": t["start"]} for t in data["tracker"]]
        return {"topic": topic, "hook": data["hook"].strip(), "backstory": data["backstory"].strip(), "cast": cast,
                "tracker": tracker, "beats": beats, "ending": data["ending"].strip()}

    def script(self, channel, outline: dict, notes: list[str], previous: dict | None, meter: Meter,
               progress: Callable[[int], None] | None = None, earlier_places: str = "") -> dict:
        if channel.format == formats.CHARACTER:
            return self._short_script(channel, outline, notes, previous, meter, progress)
        values = {"outline": prompts.outline_text(outline), "notes": prompts.notes_text(notes),
                  "previous": prompts.script_text(previous) if previous else "",
                  "earlier_places": earlier_places or "(none: this is the first part)"}
        data = self._ask("script", "script.md", "revise" if previous else "new", channel, values, SCRIPT,
                         lambda d: checks.script(d["scenes"], outline, channel.clips_per_video, d["places"]), meter,
                         _SceneCounter(progress) if progress else None,
                         part_check=lambda d: checks.script(d.get("scenes") or [], outline, channel.clips_per_video,
                                                            d.get("places") or [], partial=True))
        named = {c["name"].lower(): c["name"] for c in outline.get("cast") or []}
        items = {t["item"].lower(): t["item"] for t in outline.get("tracker") or []}
        places = [{k: p[k].strip() for k in ("id", "name", "look")} for p in data["places"]]
        scenes = [{"idx": n, "beat_idx": s["beat"] - 1, "label": s["label"].strip(), "place": s["place"].strip(),
                   "cast": [named[c.strip().lower()] for c in s["cast"]], "narration": s["narration"].strip(),
                   "move": s["move"].strip(),
                   "tracker": [{"item": items[t["item"].strip().lower()], "amount": t["amount"]} for t in s["tracker"]],
                   "set_change": s["set_change"].strip(),
                   "looks": [{"who": checks.HERO if lk["who"].strip().lower() == checks.HERO
                              else named[lk["who"].strip().lower()], "now": lk["now"].strip()} for lk in s["looks"]],
                   "shot": s["shot"],
                   "visual_prompt": s["visual_prompt"].strip(), "motion": s["motion"]}
                  for n, s in enumerate(data["scenes"], 1)]
        return {"places": places, "scenes": scenes}

    def revise_visual(self, channel, scene: dict, note: str, meter: Meter) -> str:
        data = self._ask("regen", "regen.md", "visual", channel, self._scene_values(scene, note), VISUAL,
                         lambda d: checks.visual_prompt(d["visual_prompt"]), meter)
        return data["visual_prompt"].strip()

    def rewrite_line(self, channel, scene: dict, note: str, meter: Meter) -> str:
        data = self._ask("regen", "regen.md", "narration", channel, self._scene_values(scene, note), LINE,
                         lambda d: checks.narration(d["narration"]), meter)
        return data["narration"].strip()

    def titles(self, channel, outline: dict, meter: Meter) -> dict:
        part = outline.get("part", 1)
        values = {"topic": outline["topic"], "outline": prompts.outline_text(outline),
                  "series": (f"This is Part {part} of a series: end every title with \" (Part {part})\"." if part > 1
                             else "This is a standalone video or the first part of a series.")}
        if channel.format == formats.CHARACTER:
            data = self._ask("titles", "character/titles.md", "", channel, values, SHORT_TITLES,
                             lambda d: checks.titles(d["titles"]) + checks.description(d["description"]), meter)
            return {"titles": [t.strip() for t in data["titles"]], "thumb_texts": [], "description": data["description"].strip()}
        data = self._ask("titles", "titles.md", "", channel, values, TITLES,
                         lambda d: (checks.titles(d["titles"]) + checks.thumb_texts(d["thumb_texts"])
                                    + checks.description(d["description"])), meter)
        return {"titles": [t.strip() for t in data["titles"]], "thumb_texts": [t.strip() for t in data["thumb_texts"]],
                "description": data["description"].strip()}

    def topics(self, channel, hits: list[dict], taken: list[str], count: int, meter: Meter, families=(), held=(),
               winner: dict | None = None) -> list[dict]:
        values = {"competitors": prompts.competitors_text(hits), "taken": prompts.taken_text(taken), "count": count,
                  "families": ", ".join(families) or "(none yet)", "held": ", ".join(held) or "(none)",
                  "winner": prompts.winner_text(winner) if winner else ""}
        file = "character/topic.md" if channel.format == formats.CHARACTER else "topic.md"
        data = self._ask("topic", file, "winner" if winner else "competitors", channel, values, TOPICS,
                         lambda d: checks.topics(d["topics"], count, len(hits), taken, held), meter)
        return [{"title": t["title"].strip(), "why": t["why"].strip(), "family": t["family"].strip().lower(),
                 "based_on": t["based_on"]} for t in data["topics"]]

    def check_picture(self, channel, turn: str, values: dict, pictures: list, meter: Meter) -> list[str]:
        filled = {**{name: "" for name in PICTURE_VALUES}, **values}  # every turn's placeholders, so render() passes
        data = self._ask("picture", "picture.md", turn, channel, filled, PICTURE,
                         lambda d: [] if isinstance(d["problems"], list) else ["problems isn't a list"], meter,
                         images=[Path(p) for p in pictures])
        log.info("picture check, %s: seen %r, noticed %r, problems %r", values.get("idx") or values.get("what", "")[:60],
                 data["seen"], data.get("noticed"), data["problems"])
        return [p.strip() for p in data["problems"] if isinstance(p, str) and p.strip()]

    def map_stage(self, channel, name: str, picture, meter: Meter) -> dict:
        values = {**{k: "" for k in PUPPET_VALUES}, "name": name}
        data = self._ask("map", "puppet.md", "stage", channel, values, STAGE, checks.stage_map, meter,
                         images=[Path(picture)])
        log.info("stage map of %s: %s; spots %s", name, data["seen"], [s["name"] for s in data["spots"]])
        return data

    def name_parts(self, channel, picture, names: list[str], meter: Meter) -> dict[str, dict]:
        values = {**{k: "" for k in PUPPET_VALUES}, "names": ", ".join(names)}
        data = self._ask("parts", "puppet.md", "parts", channel, values, PARTS,
                         lambda d: checks.parts_map(d, names), meter, images=[Path(picture)])
        log.info("parts named: %s", data["seen"])
        return {p["name"].strip().lower(): {"box": int(p["box"]), "faces": p["faces"]} for p in data["parts"]}

    def critique(self, channel, kind: str, values: dict, meter: Meter) -> dict:
        filled = {"outline": "", "script": "", **values}
        file = "character/critic.md" if channel.format == formats.CHARACTER else "critic.md"
        data = self._ask("critic", file, kind, channel, filled, CRITIQUE, checks.critique, meter)
        return {"verdict": data["verdict"],
                "problems": [{k: p[k].strip() for k in ("where", "what", "fix")} for p in data["problems"]]}

    def scene_sheet(self, channel, values: dict, context: dict, check: Callable[[dict], list[str]], meter: Meter) -> dict:
        filled = {**{k: "" for k in SHEET_VALUES}, **values}
        data = self._ask("sheet", "sheet.md", "scene", channel, filled, SHEET, lambda d: check(_tidy_sheet(d)), meter)
        return _tidy_sheet(data)

    def inventory(self, channel, cast: str, script: str, have: list[str], meter: Meter) -> dict:
        data = self._ask("inventory", "inventory.md", "script", channel,
                         {"cast": cast, "script": script, "have": ", ".join(have) or "none"}, INVENTORY,
                         checks.inventory, meter)
        return {"props": [{**p, "name": p["name"].strip().lower()} for p in data["props"]],
                "people": [{"name": p["name"].strip(), "scale": float(p["scale"])} for p in data["people"]]}

    # --- a character short (core/formats.py, prompts/character/) --------------------------------

    def _short_outline(self, channel, topic: str, notes: list[str], previous: dict | None, meter: Meter) -> dict:
        values = {"idea": topic, "notes": prompts.notes_text(notes),
                  "previous": prompts.outline_text(previous) if previous else ""}
        data = self._ask("outline", "character/outline.md", "revise" if previous else "new", channel, values, SHORT_OUTLINE,
                         checks.short_outline, meter)
        beats = [{"label": f"Beat {n}", "title": b["title"].strip(), "summary": b["summary"].strip(), "skill": "",
                  "hero": False, "cast": []} for n, b in enumerate(data["beats"], 1)]
        return {"topic": topic, "shape": data["shape"], "hook": data["hook"].strip(), "fact": data["fact"].strip(), "backstory": "",
                "cast": [], "tracker": [], "beats": beats, "turn": data["turn"].strip(), "ending": data["ending"].strip()}

    def _short_script(self, channel, outline: dict, notes: list[str], previous: dict | None, meter: Meter,
                      progress: Callable[[int], None] | None) -> dict:
        values = {"outline": prompts.outline_text(outline), "notes": prompts.notes_text(notes),
                  "previous": prompts.script_text(previous) if previous else ""}
        data = self._ask("script", "character/script.md", "revise" if previous else "new", channel, values, SHORT_SCRIPT,
                         lambda d: checks.short_script(d["scenes"], outline), meter, _SceneCounter(progress) if progress else None)
        scenes = [{"idx": n, "beat_idx": s["beat"] - 1, "label": f"Beat {s['beat']}", "place": "", "cast": [],
                   "narration": s["narration"].strip(), "move": "", "tracker": [], "set_change": "", "looks": [],
                   "shot": "close-up", "visual_prompt": s["shows"].strip(), "motion": "kenburns"}
                  for n, s in enumerate(data["scenes"], 1)]
        return {"places": [], "scenes": scenes}

    def cast_short(self, channel, values: dict, check: Callable[[dict], list[str]], meter: Meter) -> dict:
        filled = {**values, "outline": prompts.outline_text(values["outline"]), "notes": prompts.notes_text(values["notes"])}
        return self._ask("cast", "character/cast.md", "", channel, filled, SHORT_CAST, check, meter)

    def pick_thing(self, channel, want: dict, hits: list[dict], sheet, rejected: list[str], meter: Meter) -> dict:
        listed = "\n".join(f"{n}. {h['title']} by {h['by']}: {h['license']}, {h['moves']} moves, {h['faces']} faces"
                           for n, h in enumerate(hits, 1))
        values = {"what": want["what"], "meters": want["meters"], "moves": bool(want.get("moves")), "hits": listed,
                  "rejected": ", ".join(rejected) or "none"}
        return self._ask("source", "character/source.md", "", channel, values, SOURCE,
                         lambda d: [] if 0 <= d["choice"] <= len(hits) else [f"choice has to be 0 to {len(hits)}"], meter,
                         images=[Path(sheet)])

    def check_thing(self, channel, want: dict, manifest: dict, sheet, round_n: int, meter: Meter) -> dict:
        clips = "; ".join(f"{n} (frames {c['from']} to {c['to']})" for n, c in manifest["clips"].items()) or "none"
        values = {"what": want["what"], "meters": want["meters"], "moves": bool(want.get("moves")),
                  "size": " x ".join(str(round(v, 3)) for v in manifest["size"]), "clips": clips,
                  "materials": ", ".join(manifest.get("materials") or []) or "none", "round": round_n}
        return self._ask("thing", "character/thing.md", "", channel, values, THING_LOOK,
                         lambda d: checks.thing_look(d, manifest["clips"]), meter, images=[Path(sheet)])

    def direct(self, channel, values: dict, check: Callable[[dict], list[str]], meter: Meter) -> dict:
        notes, previous = values["notes"], values.get("previous")
        turn = "revise" if previous and notes else "new"
        filled = {**values, "outline": prompts.outline_text(values["outline"]), "notes": prompts.notes_text(notes),
                  "previous": json.dumps(previous, indent=1) if previous else ""}
        return self._ask("direct", "character/direct.md", turn, channel, filled, DIRECTION, check, meter)

    def check_film(self, channel, shots: str, sheet, meter: Meter) -> list[dict]:
        data = self._ask("film", "character/film.md", "", channel, {"shots": shots}, FILM,
                         lambda d: [] if isinstance(d["problems"], list) else ["problems isn't a list"], meter,
                         images=[Path(sheet)])
        log.info("the look at the shots: seen %r, problems %r", data["seen"], data["problems"])
        return data["problems"]

    def check_frames(self, channel, said: str, planned: str, sheets: list[dict], every: int, meter: Meter) -> list[dict]:
        listed = "\n".join(f"- {s['file']}: {s['from']} s to {s['to']} s" for s in sheets)
        data = self._ask("frames", "character/frames.md", "", channel, {"said": said, "planned": planned, "sheets": listed, "every": every}, FRAMES,
                         lambda d: [] if isinstance(d["problems"], list) else ["problems isn't a list"], meter)
        log.info("the review of the frames: seen %r, problems %r", data["seen"], data["problems"])
        return data["problems"]

    def check_joins(self, channel, turn: str, values: dict, meter: Meter) -> dict:
        filled = {**JOIN_VALUES, **values}       # each turn's placeholders, so the other turn's check passes too
        data = self._ask("transitions", "transitions.md", turn, channel, filled, JOINS, checks.joins, meter)
        log.info("the check of the joins (%s): seen %r, problems %r", turn, data["seen"], data["problems"])
        return data

    @staticmethod
    def _scene_values(scene: dict, note: str) -> dict:
        return {"idx": scene["idx"], "label": scene["label"], "narration": scene["narration"],
                "visual_prompt": scene["visual_prompt"], "note": note,
                "place": scene.get("place_text") or "(not recorded)", "cast": scene.get("cast_text") or "nobody",
                "before": scene.get("before") or "(this is the first scene)",
                "after": scene.get("after") or "(this is the last scene)"}

    # --- one request, checked, with one retry ------------------------------------------------

    def _ask(self, kind: str, file: str, turn: str, channel, values: dict, schema: dict,
             check: Callable[[dict], list[str]], meter: Meter, on_text: _SceneCounter | None = None,
             images: list[Path] = (), part_check: Callable[[dict], list[str]] | None = None) -> dict:
        """`part_check` is for a reply long enough to come in parts (the script): what's wrong with the reply so far
        (providers/session.py, core/jobs.py)."""
        system, user = prompts.render(self.config.root, file, turn, channel, values)
        content = [*(_image(p) for p in images), {"type": "text", "text": user}] if images else user
        messages: list[dict] = [{"role": "user", "content": content}]
        for attempt in (1, 2):
            if on_text:
                on_text.reset()
            text = self._call(kind, system, messages, schema, meter, on_text,
                              lambda reply: _checked(reply, check)[1],
                              (lambda reply: _checked(reply, part_check)[1]) if part_check else None)
            data, problems = _checked(text, check)
            if not problems:
                return data
            log.warning("claude %s attempt %d failed its checks: %s", kind, attempt, problems)
            if attempt == 2:
                listed = "; ".join(problems[:8]) + (f"; and {len(problems) - 8} more" if len(problems) > 8 else "")
                raise FinalError(f"Claude's {WHAT[kind]} failed its checks twice: {listed}. Retry for another go, "
                                 f"or ask the assistant to adjust prompts/{file}")
            shown = problems[:SHOWN] + ([f"...and {len(problems) - SHOWN} more like these"]
                                        if len(problems) > SHOWN else [])
            messages += [{"role": "assistant", "content": text},
                         {"role": "user", "content": FIX.format(problems="\n".join(f"- {p}" for p in shown))}]
        raise AssertionError("unreachable")

    def _call(self, kind: str, system: str, messages: list[dict], schema: dict, meter: Meter,
              on_text: _SceneCounter | None, verify: Callable[[str], list[str]],
              verify_part: Callable[[str], list[str]] | None = None) -> str:
        """One request; returns the reply's text. `verify` says what's wrong with a reply's text, and `verify_part`
        with the parts of one so far, so the answer can be checked as it comes in."""
        raise NotImplementedError

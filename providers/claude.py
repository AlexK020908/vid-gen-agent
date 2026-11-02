"""Claude (Anthropic API) writes the outline, the script, scene fixes, titles with their thumbnail text, and
topic ideas from competitors' recent hits, and looks at each drawn picture to say what's wrong with it.

Every call sends the prompt file's system part (channel facts filled in) as a cached system block and
the idea, outline and notes in the user turn (providers/prompts.py). Replies come back as JSON
(structured outputs) and are checked in code (providers/checks.py). A reply that fails its checks
gets one more try with the problems listed; after that the stage fails with them on the error card
(FinalError) instead of paying for three more attempts. Each API call is guarded and logged through
the stage's meter, the failed ones too.

A picture check (check_picture) sends the pictures as image blocks in the user turn, each scaled to
CHECK_WIDTH across as a JPEG (a 1920×1080 PNG is a few MB and the API scales big pictures down anyway).
"""
from __future__ import annotations

import base64
import io
import json
import logging
import os
from pathlib import Path
from typing import Callable

import anthropic
from PIL import Image

from core.errors import FinalError, Stopped
from providers import checks, prompts
from providers.llm import Meter

log = logging.getLogger("stickfleet.claude")

DEFAULTS = {
    "effort": {"outline": "high", "script": "high", "regen": "medium", "titles": "medium", "topic": "medium",
               "check": "medium", "critic": "high"},
    "max_tokens": {"outline": 32000, "script": 64000, "regen": 8000, "titles": 8000, "topic": 8000, "check": 4000,
                   "critic": 16000},
}
WHAT = {"outline": "outline", "script": "script", "regen": "scene fix", "titles": "titles", "topic": "topic ideas",
        "check": "picture check", "critic": "review"}
CHARS_PER_TOKEN = 3  # for the estimate before a call; generous, since JSON packs more tokens per character
CHECK_WIDTH = 1280   # pictures are sent this wide for a check: enough to see a towel beside a knee, 1/3 the tokens of full size
IMAGE_TOKENS = 1600  # what a CHECK_WIDTH picture costs in input tokens, for the estimate
PICTURE_VALUES = ("idx", "label", "shot", "before", "narration", "visual_prompt", "people", "what", "images")  # picture.md
FALLBACK_BETA = "server-side-fallback-2026-07-01"
DROP_BEFORE_FALLBACK = {"thinking", "redacted_thinking", "connector_text", "tool_use"}
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
                  {"name": STR, "polygon": {"type": "array", "items": _obj({"x": NUM, "y": NUM})}, "base_y": NUM})},
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
    "set": {"type": "array", "items": _obj({"place": STR, "at": STR, "angle": NUM, "remove": STR})},
    "camera": {"type": "array", "items": _obj({"at_ms": {"type": "integer"}, "center": STR, "zoom": NUM})},
    "light": _obj({"time": STR, "lamp": STR})})
INVENTORY = _obj({  # prompts/inventory.md: the props a script uses and how big each cast member is
    "props": {"type": "array", "items": _obj({"name": STR, "draw": STR, "height": NUM, "stands": STR})},
    "people": {"type": "array", "items": _obj({"name": STR, "scale": NUM})}})
SHEET_VALUES = ("idx", "label", "shot", "duration_ms", "place_name", "words", "visual_prompt", "set_change", "looks",
                "people", "stage", "props", "poses", "cycles", "previous", "state")
CRITIQUE = _obj({"verdict": {"type": "string", "enum": ["fine", "revise"]},  # prompts/critic.md, core/review.py
                 "problems": {"type": "array", "items": _obj({"where": STR, "what": STR, "fix": STR})}})


class _SceneCounter:
    """Counts scenes in the streamed JSON so the thread can show the script being written."""
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


def _text(content) -> str:
    """The reply's text. After a fallback mid-reply, the text blocks either side of the `fallback` block join up:
    the fallback model carries on from where the declined one stopped."""
    return "".join(getattr(b, "text", "") or "" for b in content if getattr(b, "type", "") == "text")


def _echo(content) -> list:
    """The assistant turn to send back for a retry. After a fallback the API rejects thinking and tool blocks from
    before the last `fallback` block, so those go; everything else stays where it was."""
    last = max((i for i, b in enumerate(content) if getattr(b, "type", "") == "fallback"), default=-1)
    return [b for i, b in enumerate(content) if not (i < last and getattr(b, "type", "") in DROP_BEFORE_FALLBACK)]


def _chars(messages: list[dict]) -> int:
    """Characters in the messages, for the cost estimate; a picture counts as IMAGE_TOKENS' worth."""
    total = 0
    for m in messages:
        c = m["content"]
        if isinstance(c, str):
            total += len(c)
            continue
        for b in c:
            if isinstance(b, dict):
                total += IMAGE_TOKENS * CHARS_PER_TOKEN if b.get("type") == "image" else len(b.get("text") or "")
            else:
                total += len(getattr(b, "text", "") or "")
    return total


def _tidy_sheet(data: dict) -> dict:
    """The sheet with the schema's empty strings dropped, as puppet/sheet.py reads it."""
    figures = []
    for f in data.get("figures") or []:
        actions = [{k: v for k, v in a.items() if v not in ("", None)} for a in f.get("actions") or []]
        figures.append({"who": f.get("who", "").strip(), "actions": actions, "attached": list(f.get("attached") or [])})
    changes = []
    for c in data.get("set") or []:
        if c.get("remove"):
            changes.append({"remove": c["remove"]})
        elif c.get("place"):
            changes.append({"place": c["place"], "at": c.get("at", ""), "angle": float(c.get("angle") or 0.0)})
    light = data.get("light") or {}
    return {"figures": figures, "set": changes, "camera": list(data.get("camera") or []),
            "light": {"time": str(light.get("time", "")).strip().lower(), "lamp": str(light.get("lamp") or "").strip()}}


def _checked(text: str, check: Callable[[dict], list[str]]) -> tuple[dict | None, list[str]]:
    """The reply parsed, and what its checks found wrong with it."""
    try:
        data = json.loads(text)
        return data, check(data)
    except (ValueError, KeyError, TypeError, AttributeError) as e:
        return None, [f"the reply isn't the JSON that was asked for ({type(e).__name__}: {e})"]


def _image_block(path: Path) -> dict:
    with Image.open(path) as img:
        img = img.convert("RGB")
        img.thumbnail((CHECK_WIDTH, CHECK_WIDTH))
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=85)
    return {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                        "data": base64.b64encode(buf.getvalue()).decode()}}


class ClaudeLLM:
    def __init__(self, config, client=None) -> None:
        self.config = config
        self._client = client  # tests pass a fake

    @property
    def client(self):
        if self._client is None:
            if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
                raise FinalError("Claude needs ANTHROPIC_API_KEY in .env (see .env.example). Add it, restart "
                                 "run.py serve, then Retry")
            self._client = anthropic.Anthropic()
        return self._client

    # --- the LLM protocol (providers/llm.py) -------------------------------------------------

    def outline(self, channel, topic: str, notes: list[str], previous: dict | None, meter: Meter,
                sequel: dict | None = None) -> dict:
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
        values = {"outline": prompts.outline_text(outline), "notes": prompts.notes_text(notes),
                  "previous": prompts.script_text(previous) if previous else "",
                  "earlier_places": earlier_places or "(none: this is the first part)"}
        data = self._ask("script", "script.md", "revise" if previous else "new", channel, values, SCRIPT,
                         lambda d: checks.script(d["scenes"], outline, channel.clips_per_video, d["places"]), meter,
                         _SceneCounter(progress) if progress else None)
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
        data = self._ask("topic", "topic.md", "winner" if winner else "competitors", channel, values, TOPICS,
                         lambda d: checks.topics(d["topics"], count, len(hits), taken, held), meter)
        return [{"title": t["title"].strip(), "why": t["why"].strip(), "family": t["family"].strip().lower(),
                 "based_on": t["based_on"]} for t in data["topics"]]

    def check_picture(self, channel, turn: str, values: dict, pictures: list, meter: Meter) -> list[str]:
        filled = {**{name: "" for name in PICTURE_VALUES}, **values}  # every turn's placeholders, so render() passes
        data = self._ask("check", "picture.md", turn, channel, filled, PICTURE,
                         lambda d: [] if isinstance(d["problems"], list) else ["problems isn't a list"], meter,
                         images=[Path(p) for p in pictures])
        log.info("picture check, %s: seen %r, noticed %r, problems %r", values.get("idx") or values.get("what", "")[:60],
                 data["seen"], data.get("noticed"), data["problems"])
        return [p.strip() for p in data["problems"] if isinstance(p, str) and p.strip()]

    def map_stage(self, channel, name: str, picture, meter: Meter) -> dict:
        values = {**{k: "" for k in PUPPET_VALUES}, "name": name}
        data = self._ask("check", "puppet.md", "stage", channel, values, STAGE, checks.stage_map, meter,
                         images=[Path(picture)])
        log.info("stage map of %s: %s; spots %s", name, data["seen"], [s["name"] for s in data["spots"]])
        return data

    def name_parts(self, channel, picture, names: list[str], meter: Meter) -> dict[str, dict]:
        values = {**{k: "" for k in PUPPET_VALUES}, "names": ", ".join(names)}
        data = self._ask("check", "puppet.md", "parts", channel, values, PARTS,
                         lambda d: checks.parts_map(d, names), meter, images=[Path(picture)])
        log.info("parts named: %s", data["seen"])
        return {p["name"].strip().lower(): {"box": int(p["box"]), "faces": p["faces"]} for p in data["parts"]}

    def critique(self, channel, kind: str, values: dict, meter: Meter) -> dict:
        filled = {"outline": "", "script": "", **values}
        data = self._ask("critic", "critic.md", kind, channel, filled, CRITIQUE, checks.critique, meter)
        return {"verdict": data["verdict"],
                "problems": [{k: p[k].strip() for k in ("where", "what", "fix")} for p in data["problems"]]}

    def scene_sheet(self, channel, values: dict, context: dict, check: Callable[[dict], list[str]], meter: Meter) -> dict:
        filled = {**{k: "" for k in SHEET_VALUES}, **values}
        data = self._ask("check", "sheet.md", "scene", channel, filled, SHEET, lambda d: check(_tidy_sheet(d)), meter)
        return _tidy_sheet(data)

    def inventory(self, channel, cast: str, script: str, have: list[str], meter: Meter) -> dict:
        data = self._ask("check", "inventory.md", "script", channel,
                         {"cast": cast, "script": script, "have": ", ".join(have) or "none"}, INVENTORY,
                         checks.inventory, meter)
        return {"props": [{**p, "name": p["name"].strip().lower()} for p in data["props"]],
                "people": [{"name": p["name"].strip(), "scale": float(p["scale"])} for p in data["people"]]}

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
             images: list[Path] = ()) -> dict:
        system, user = prompts.render(self.config.root, file, turn, channel, values)
        content = [*(_image_block(p) for p in images), {"type": "text", "text": user}] if images else user
        messages: list[dict] = [{"role": "user", "content": content}]
        for attempt in (1, 2):
            if on_text:
                on_text.reset()
            message = self._call(kind, system, messages, schema, meter, on_text,
                                 lambda text: _checked(text, check)[1])
            data, problems = _checked(_text(message.content), check)
            if not problems:
                return data
            log.warning("claude %s attempt %d failed its checks: %s", kind, attempt, problems)
            if attempt == 2:
                listed = "; ".join(problems[:8]) + (f"; and {len(problems) - 8} more" if len(problems) > 8 else "")
                raise FinalError(f"Claude's {WHAT[kind]} failed its checks twice: {listed}. Retry for another go, "
                                 f"or ask the assistant to adjust prompts/{file}")
            shown = problems[:SHOWN] + ([f"...and {len(problems) - SHOWN} more like these"]
                                        if len(problems) > SHOWN else [])
            messages += [{"role": "assistant", "content": _echo(message.content)},
                         {"role": "user", "content": FIX.format(problems="\n".join(f"- {p}" for p in shown))}]
        raise AssertionError("unreachable")

    def _setting(self, name: str, kind: str):
        return (self.config.claude.get(name) or {}).get(kind, DEFAULTS[name][kind])

    def _price(self, model: str) -> dict:
        price = (self.config.claude.get("prices") or {}).get(model)
        if not price:
            raise FinalError(f"there's no price for {model}: add it under claude.prices in stickfleet.yaml, "
                             "so its spend can count toward the budget")
        return price

    def _call(self, kind: str, system: str, messages: list[dict], schema: dict, meter: Meter,
              on_text: _SceneCounter | None, verify: Callable[[str], list[str]] | None = None):
        """One request. `verify` says what's wrong with a reply's text; the API path checks after the call returns
        (in _ask), so it's for providers/session.py, which checks the session's answer as it arrives."""
        model = self.config.models.get(kind) or self.config.models["script"]
        price = self._price(model)
        max_tokens = int(self._setting("max_tokens", kind))
        prompt_tokens = (len(system) + _chars(messages)) / CHARS_PER_TOKEN
        estimate = (prompt_tokens * price["input"] + max_tokens * price["output"]) / 1e6  # the most it can cost
        fallbacks = self.config.claude.get("fallbacks", "default")
        if fallbacks:
            estimate *= 2  # a declined attempt and the fallback that finishes it are both billed
        meter.check(estimate)
        request = {
            "model": model, "max_tokens": max_tokens, "messages": messages,
            "system": [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            "output_config": {"effort": self._setting("effort", kind),
                              "format": {"type": "json_schema", "schema": schema}},
        }
        stream_call = self.client.messages.stream
        if fallbacks:  # a safety-classifier refusal is retried on Anthropic's recommended model, on the same stream
            request.update(fallbacks=fallbacks, betas=[FALLBACK_BETA])
            stream_call = self.client.beta.messages.stream
        streamed = 0
        try:
            try:
                with stream_call(**request) as stream, meter.writing(stream.close):
                    for text in stream.text_stream:
                        streamed += len(text)
                        if on_text:
                            on_text(text)
                    if meter.stopped:  # cut off between chunks: what came back is a fragment
                        raise Stopped(f"stopped writing the {WHAT[kind]}")
                    message = stream.get_final_message()
            except Exception:
                if meter.stopped:  # Stop closed the stream; whatever that raised, this is what happened
                    self._log_stopped(model, price, prompt_tokens, streamed, estimate, meter)
                    raise Stopped(f"stopped writing the {WHAT[kind]}") from None
                raise
        except anthropic.AuthenticationError:
            raise FinalError("Claude turned down the API key: check ANTHROPIC_API_KEY in .env, restart, then "
                             "Retry") from None
        except anthropic.PermissionDeniedError as e:
            raise FinalError(f"this API key can't use {model}: {e.message}") from None
        except anthropic.NotFoundError:
            raise FinalError(f"Claude has no model {model!r}: check models in stickfleet.yaml") from None
        except anthropic.BadRequestError as e:
            raise FinalError(f"Claude refused the request: {e.message}") from None

        usd, detail = self._cost(message, model, price)
        detail["estimate_usd"] = round(estimate, 4)
        meter.spend(usd, detail)
        log.info("claude %s: %s, $%.4f", kind, detail, usd)
        if message.stop_reason == "max_tokens":
            raise FinalError(f"Claude ran out of room writing the {WHAT[kind]} ({max_tokens:,} tokens). Raise "
                             f"claude.max_tokens.{kind} in stickfleet.yaml, then Retry")
        if message.stop_reason == "refusal":
            details = getattr(message, "stop_details", None)
            why = getattr(details, "explanation", None)
            tried = " (the fallback model declined too)" if detail.get("attempts") else ""
            raise FinalError(f"Claude declined to write the {WHAT[kind]}{tried}{f': {why}' if why else ''}. Anthropic's "
                             "safety filter sometimes misfires on survival stories; Retry, or rephrase the idea or note")
        return message

    @staticmethod
    def _log_stopped(model: str, price: dict, prompt_tokens: float, streamed: int, estimate: float, meter) -> None:
        """A stopped call is billed for what it produced, but there's no usage to read: log an estimate from the
        prompt and the text that had arrived (thinking that never reached the text isn't counted)."""
        usd = (prompt_tokens * price["input"] + streamed / CHARS_PER_TOKEN * price["output"]) / 1e6
        meter.spend(usd, {"model": model, "stop": "stopped", "approx": True, "input": round(prompt_tokens),
                          "cache_write": 0, "cache_read": 0, "output": round(streamed / CHARS_PER_TOKEN),
                          "estimate_usd": round(estimate, 4)})

    def _cost(self, message, model: str, price: dict) -> tuple[float, dict]:
        """What the call cost, from usage. With a fallback, usage.iterations has one entry per attempt (the declined
        one and the one that finished), each billed at its own model's rates."""
        u = message.usage
        attempts = getattr(u, "iterations", None) or [u]
        prices = self.config.claude.get("prices") or {}
        usd, parts = 0.0, []
        for a in attempts:
            used = getattr(a, "model", None) or model
            rate = prices.get(used) or price  # a fallback model with no listed price is costed at the requested model's
            tokens = {"input": a.input_tokens or 0, "cache_write": getattr(a, "cache_creation_input_tokens", 0) or 0,
                      "cache_read": getattr(a, "cache_read_input_tokens", 0) or 0, "output": a.output_tokens or 0}
            usd += sum(tokens[k] * rate[k] for k in tokens) / 1e6
            parts.append({"model": used, "type": getattr(a, "type", "message"), **tokens,
                          **({} if used in prices else {"priced_as": model})})
        detail = {"model": getattr(message, "model", None) or model, "stop": message.stop_reason,
                  **{k: sum(p[k] for p in parts) for k in ("input", "cache_write", "cache_read", "output")}}
        if len(parts) > 1:
            detail["attempts"] = parts
        return usd, detail

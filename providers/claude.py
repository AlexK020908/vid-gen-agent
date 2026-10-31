"""Claude (Anthropic API) writes the outline, the script, scene fixes, titles with their thumbnail text, and
topic ideas from competitors' recent hits.

Every call sends the prompt file's system part (channel facts filled in) as a cached system block and
the idea, outline and notes in the user turn (providers/prompts.py). Replies come back as JSON
(structured outputs) and are checked in code (providers/checks.py). A reply that fails its checks
gets one more try with the problems listed; after that the stage fails with them on the error card
(FinalError) instead of paying for three more attempts. Each API call is guarded and logged through
the stage's meter, the failed ones too.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Callable

import anthropic

from core.errors import FinalError, Stopped
from providers import checks, prompts
from providers.llm import Meter

log = logging.getLogger("stickfleet.claude")

DEFAULTS = {
    "effort": {"outline": "high", "script": "high", "regen": "medium", "titles": "medium", "topic": "medium"},
    "max_tokens": {"outline": 32000, "script": 64000, "regen": 8000, "titles": 8000, "topic": 8000},
}
WHAT = {"outline": "outline", "script": "script", "regen": "scene fix", "titles": "titles", "topic": "topic ideas"}
CHARS_PER_TOKEN = 3  # for the estimate before a call; generous, since JSON packs more tokens per character
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
         "shot": {"type": "string", "enum": list(checks.SHOTS)}, "visual_prompt": STR,
         "motion": {"type": "string", "enum": list(checks.MOTIONS)}})}})
VISUAL = _obj({"visual_prompt": STR})
LINE = _obj({"narration": STR})
TITLES = _obj({"titles": {"type": "array", "items": STR}, "thumb_texts": {"type": "array", "items": STR}})
TOPICS = _obj({"topics": {"type": "array", "items": _obj(
    {"title": STR, "why": STR, "family": STR, "based_on": {"type": "array", "items": {"type": "integer"}}})}})


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
    total = 0
    for m in messages:
        c = m["content"]
        total += len(c) if isinstance(c, str) else sum(len(getattr(b, "text", "") or "") for b in c)
    return total


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

    def outline(self, channel, topic: str, notes: list[str], previous: dict | None, meter: Meter) -> dict:
        values = {"idea": topic, "notes": prompts.notes_text(notes),
                  "previous": prompts.outline_text(previous) if previous else ""}
        data = self._ask("outline", "outline.md", "revise" if previous else "new", channel, values, OUTLINE,
                         checks.outline, meter)
        cast = [{k: c[k].strip() for k in ("name", "look", "role", "thread")} for c in data["cast"]]
        named = {c["name"].lower(): c["name"] for c in cast}  # beats spell names the way the cast does
        beats = [{"label": b["label"].strip(), "title": b["title"].strip(), "summary": b["summary"].strip(),
                  "skill": b["skill"].strip(), "hero": bool(b["hero"]),
                  "cast": [named[n.strip().lower()] for n in b["cast"]]} for b in data["beats"]]
        tracker = [{"item": t["item"].strip(), "unit": t["unit"].strip(), "start": t["start"]} for t in data["tracker"]]
        return {"topic": topic, "hook": data["hook"].strip(), "backstory": data["backstory"].strip(), "cast": cast,
                "tracker": tracker, "beats": beats, "ending": data["ending"].strip()}

    def script(self, channel, outline: dict, notes: list[str], previous: dict | None, meter: Meter,
               progress: Callable[[int], None] | None = None) -> dict:
        values = {"outline": prompts.outline_text(outline), "notes": prompts.notes_text(notes),
                  "previous": prompts.script_text(previous) if previous else ""}
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
                   "set_change": s["set_change"].strip(), "shot": s["shot"],
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
        values = {"topic": outline["topic"], "outline": prompts.outline_text(outline)}
        data = self._ask("titles", "titles.md", "", channel, values, TITLES,
                         lambda d: checks.titles(d["titles"]) + checks.thumb_texts(d["thumb_texts"]), meter)
        return {"titles": [t.strip() for t in data["titles"]], "thumb_texts": [t.strip() for t in data["thumb_texts"]]}

    def topics(self, channel, hits: list[dict], taken: list[str], count: int, meter: Meter, families=(), held=(),
               winner: dict | None = None) -> list[dict]:
        values = {"competitors": prompts.competitors_text(hits), "taken": prompts.taken_text(taken), "count": count,
                  "families": ", ".join(families) or "(none yet)", "held": ", ".join(held) or "(none)",
                  "winner": prompts.winner_text(winner) if winner else ""}
        data = self._ask("topic", "topic.md", "winner" if winner else "competitors", channel, values, TOPICS,
                         lambda d: checks.topics(d["topics"], count, len(hits), taken, held), meter)
        return [{"title": t["title"].strip(), "why": t["why"].strip(), "family": t["family"].strip().lower(),
                 "based_on": t["based_on"]} for t in data["topics"]]

    @staticmethod
    def _scene_values(scene: dict, note: str) -> dict:
        return {"idx": scene["idx"], "label": scene["label"], "narration": scene["narration"],
                "visual_prompt": scene["visual_prompt"], "note": note,
                "place": scene.get("place_text") or "(not recorded)", "cast": scene.get("cast_text") or "nobody",
                "before": scene.get("before") or "(this is the first scene)",
                "after": scene.get("after") or "(this is the last scene)"}

    # --- one request, checked, with one retry ------------------------------------------------

    def _ask(self, kind: str, file: str, turn: str, channel, values: dict, schema: dict,
             check: Callable[[dict], list[str]], meter: Meter, on_text: _SceneCounter | None = None) -> dict:
        system, user = prompts.render(self.config.root, file, turn, channel, values)
        messages: list[dict] = [{"role": "user", "content": user}]
        for attempt in (1, 2):
            if on_text:
                on_text.reset()
            message = self._call(kind, system, messages, schema, meter, on_text)
            try:
                data = json.loads(_text(message.content))
                problems = check(data)
            except (ValueError, KeyError, TypeError, AttributeError) as e:
                problems = [f"the reply isn't the JSON that was asked for ({type(e).__name__}: {e})"]
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
              on_text: _SceneCounter | None):
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

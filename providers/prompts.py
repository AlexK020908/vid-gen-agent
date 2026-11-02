"""Prompt files in prompts/, read fresh on every call so an approved edit applies to the next run.

A file is a system prompt followed by one or more user-turn templates, each starting at a marker line:

    <!-- user turn -->            the only one
    <!-- user turn: revise -->    one of several, picked by name (outline.md has `new` and `revise`)

Placeholders are `{name}`. The system part may use only the channel's (it is sent as a cached block,
so it must not change from video to video); the user turns may use the channel's and the request's.
A placeholder the code doesn't know stops the stage with a message naming it. Image prompts
(still.md, thumbnail.md, clip.md) are whole-file templates for `fill()`.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from core.errors import FinalError
from core.config import NARRATORS
from providers import checks

MARKER = re.compile(r"^<!--\s*user turn(?::\s*([a-z_]+))?\s*-->[ \t]*$", re.M)
PLACEHOLDER = re.compile(r"\{([a-z_]+)\}")
CHANNEL_NAMES = ("channel_name", "scenario_family", "style_prompt", "clips_per_video", "beat_count", "hero_count",
                 "hero_scenes", "scene_count", "scene_words", "total_words", "minutes", "thumb_words", "thumb_chars", "cold_open",
                 "cast_max", "tracker_count", "places_count", "narrator", "visual_guide",
                 "stretch_days")


class PromptError(FinalError):
    pass


def _span(lo_hi: tuple[int, int]) -> str:
    return f"{lo_hi[0]} to {lo_hi[1]}"


def _split(path: Path, text: str) -> tuple[str, dict[str, str]]:
    marks = list(MARKER.finditer(text))
    if not marks:
        raise PromptError(f"prompts/{path.name} has no `<!-- user turn -->` line, so there is no user turn to send")
    turns = {}
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        turns[m.group(1) or ""] = text[m.end():end].strip()
    return text[:marks[0].start()].strip(), turns


def _check(path: Path, part: str, text: str, allowed: set[str], request: set[str]) -> None:
    for name in sorted(set(PLACEHOLDER.findall(text)) - allowed):
        if name in request:
            raise PromptError(f"prompts/{path.name} uses {{{name}}} above the user-turn line. It changes for every "
                              "video, so move it below `<!-- user turn -->`")
        known = ", ".join(f"{{{n}}}" for n in sorted(allowed | request))
        raise PromptError(f"prompts/{path.name} uses {{{name}}} in its {part}, which isn't a placeholder. "
                          f"Known here: {known}")


def _fill(text: str, values: dict) -> str:
    return PLACEHOLDER.sub(lambda m: str(values[m.group(1)]), text)


def channel_values(root: Path, channel) -> dict:
    values = {
        "channel_name": channel.name, "scenario_family": channel.scenario_family,
        "style_prompt": channel.style_prompt, "clips_per_video": channel.clips_per_video,
        "beat_count": _span(checks.BEATS), "hero_count": _span(checks.HERO_BEATS),
        "hero_scenes": _span(checks.HERO_SCENES),        "scene_count": _span(checks.SCENES), "scene_words": _span(checks.SCENE_WORDS),
        "total_words": f"{checks.TOTAL_WORDS:,}", "minutes": round(checks.TOTAL_WORDS / checks.WPM),
        "thumb_words": _span(checks.THUMB_WORDS), "thumb_chars": checks.THUMB_CHARS,
        "cold_open": checks.COLD_OPEN_SCENES, "cast_max": checks.CAST[1], "tracker_count": _span(checks.TRACKER),
        "places_count": _span(checks.PLACES), "narrator": NARRATORS[channel.narrator],
        "stretch_days": checks.STRETCH_DAYS,
    }
    guide = root / "prompts" / "visual.md"
    text = guide.read_text(encoding="utf-8").strip()
    _check(guide, "text", text, set(values), set())
    values["visual_guide"] = _fill(text, values)
    return values


def render(root: Path, file: str, turn: str, channel, values: dict) -> tuple[str, str]:
    """(system, user) for one call. `values` holds every request placeholder the file's turns may use."""
    path = root / "prompts" / file
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise PromptError(f"prompts/{file} is missing") from None
    system, turns = _split(path, text)
    allowed, request = set(CHANNEL_NAMES), set(values)
    _check(path, "system part", system, allowed, request)
    for name, body in turns.items():
        _check(path, f"`{name or 'user'}` turn", body, allowed | request, set())
    if turn not in turns:
        have = ", ".join(f"`<!-- user turn: {n} -->`" if n else "`<!-- user turn -->`" for n in turns)
        raise PromptError(f"prompts/{file} needs a `<!-- user turn: {turn} -->` section (it has {have})")
    filled = {**channel_values(root, channel), **values}
    return _fill(system, filled), _fill(turns[turn], filled)


def fill(root: Path, file: str, channel, values: dict) -> str:
    """A whole-file template with no user turns (the picture and clip prompts still.md, thumbnail.md, clip.md)."""
    path = root / "prompts" / file
    try:
        text = path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        raise PromptError(f"prompts/{file} is missing") from None
    _check(path, "text", text, set(CHANNEL_NAMES) | set(values), set())
    return _fill(text, {**channel_values(root, channel), **values})


# --- request values in the shape the prompts show them ------------------------------------

def notes_text(notes: list[str]) -> str:
    if not notes:
        return "(none)"
    lines = [f"{i}. {n}" for i, n in enumerate(notes, 1)]
    if len(lines) > 1:
        lines[-1] += "  (newest)"
    return "\n".join(lines)


def competitors_text(hits: list[dict]) -> str:
    """The ranked competitor videos, numbered from 1 as `based_on` cites them."""
    return "\n".join(f"{n}. \"{h['title']}\" by {h['channel']}: {h['views']:,} views in {h['age_days']:.0f} days "
                     f"({h['per_day']:,.0f} a day)" for n, h in enumerate(hits, 1))


def winner_text(w: dict) -> str:
    """The channel's own winning video, as the follow-ups turn shows it."""
    return (f"\"{w['title']}\" ({w['family'] or 'no family tag'}): {w['views']:,} views in 48 hours. Average view "
            f"{w['avd_pct']:.1f}% of the video against a median of {w['median_avd_pct']:.1f}%; click-through "
            f"{w['ctr']:.1f}% against {w['median_ctr']:.1f}%.")


def taken_text(titles: list[str]) -> str:
    return "\n".join(f"- {t}" for t in titles) if titles else "(none yet)"


def amount(value: float) -> str:
    """A tracked amount the way the tracker box and the cards show it: 12, 1,500, 2.5."""
    return f"{int(value):,}" if float(value).is_integer() else f"{value:,.2f}".rstrip("0").rstrip(".")


def outline_text(outline: dict) -> str:
    """The outline as the script, titles and revise turns read it. Outlines from before the backstory, cast and
    tracker leave those lines out."""
    lines = [f"Hook: {outline['hook']}"]
    if outline.get("backstory"):
        lines.append(f"Backstory: {outline['backstory']}")
    if outline.get("cast"):
        lines += ["", "Cast:"] + [f"- {c['name']}, {c['role']}. Looks: {c['look']} Thread: {c['thread']}"
                                  for c in outline["cast"]]
    if outline.get("tracker"):
        lines += ["", "Tracker: " + "; ".join(f"{t['item']}, {amount(t['start'])} {t['unit']} at the start"
                                              for t in outline["tracker"])]
    lines.append("")
    for n, b in enumerate(outline["beats"], 1):
        hero = " (hero beat)" if b.get("hero") else ""
        lines += [f"Beat {n} | {b['label']} | {b['title']}{hero}", f"  What happens: {b['summary']}",
                  f"  Skill: {b['skill']}"]
        if b.get("cast"):
            lines.append(f"  Cast: {', '.join(b['cast'])}")
    return "\n".join(lines + ["", f"Ending: {outline['ending']}"])


def script_text(script: dict) -> str:
    """The places, then one scene per line, in the shape the script is written in (beats numbered from 1)."""
    places = [json.dumps({"id": p["id"], "name": p["name"], "look": p["look"]}, ensure_ascii=False)
              for p in script.get("places") or []]
    scenes = [json.dumps({"beat": s["beat_idx"] + 1, "label": s["label"], "place": s.get("place", ""),
                          "cast": s.get("cast", []), "narration": s["narration"], "move": s.get("move", ""),
                          "tracker": s.get("tracker", []), "set_change": s.get("set_change", ""),
                          "looks": s.get("looks", []), "shot": s.get("shot", "medium"), "visual_prompt": s["visual_prompt"],
                          "motion": s["motion"]}, ensure_ascii=False)
              for s in script["scenes"]]
    return "\n".join(["Places:", *(places or ["(none yet)"]), "", "Scenes:", *scenes])

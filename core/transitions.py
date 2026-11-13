"""The joins, checked by someone who didn't make the short: where each line gives way to the next, and each shot to the
next, would a viewer go on without a jolt? (prompts/transitions.md; a `transitions` job, which the session hands to its
`transition-checker` agent.)

The owner asked for it on Nov 8, 2026: "something i would add is another agent that looks at the transitions between
scnenes, like the b ird example, I actually had to make sure the tranasistion into sponge on hammer was clean. We need a
transition checker. this mainly comes from the script and also how cclean the scnenes are". The reviewer and the frame
reviewer each had joins as one point among many, and both let that one through.

It reads a short twice:
- the script, after the reviewer and before any voice is paid for. What it finds goes back to the writer as
  notes, and the rewrite is read again (ROUNDS rewrites at most), through the revise turn a sent-back script uses, as core/review.py does;
- a 3D short's finished film, with the frames either side of every cut (render/cut_sheets.py). What's in the picture
  goes back to the director with the frame reviewer's notes (stages/film.py). What's in the words goes to the owner,
  since changing a line then means paying for its voice again.

Blemishes (`serious` false) are only listed. Nothing runs when models.transitions is unset or `off` in stickfleet.yaml.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable

from core.errors import FinalError
from providers import prompts
from render import cut_sheets

log = logging.getLogger("stickfleet.transitions")

NAME = "transitions"
NOTE = "Joins, "          # how the writer's and the director's notes from it start
ROUNDS = 2                # how many times a script is rewritten for its joins, each rewrite read again
MEASURED = ("These cuts were measured from the picture, not planned, so one of them may be a fast move rather than a "
            "cut: judge it as what it is.")


def enabled(ctx) -> bool:
    return bool(ctx.config.models.get(NAME)) and str(ctx.config.models.get(NAME)).lower() != "off"


def lines_text(script: dict) -> str:
    """The script as its joins are read: each line, and what it shows."""
    return "\n".join(f"{n}. Says: {s['narration']}\n   Shows: {s.get('visual_prompt') or s.get('shows') or '(not given)'}"
                     for n, s in enumerate(script["scenes"], 1))


def listed(problems: list[dict]) -> str:
    return "\n".join(f"- {p['at']}: {p['what']} Fix: {p['fix']}" for p in problems)


def checked_script(ctx, conn, video, channel, outline: dict, script: dict, rewrite: Callable[[list[str], dict], dict]) -> dict:
    """`script` with its joins checked: as it was if they're fine, or rewritten with the bad ones as notes and read
    again, up to ROUNDS rewrites (`rewrite(notes, draft)` is the writer's revise call on that draft). A rewrite is
    read again because fixing a join can break another: on Nov 10, 2026, seven scripts that had each been checked and
    rewritten once still had twelve serious joins between them, one of them made by a fix."""
    if not enabled(ctx) or len(script["scenes"]) < 2:      # one line has no joins
        return script
    fixed: list[dict] = []
    for round_no in range(ROUNDS + 1):
        found = ctx.llm.check_joins(channel, "script", {"outline": prompts.outline_text(outline), "lines": lines_text(script)},
                                    ctx.meter(conn, video, NAME, "the check of the joins"))
        problems = found.get("problems") or []
        serious = [p for p in problems if p.get("serious", True)]
        small = [p for p in problems if not p.get("serious", True)]
        tail = f"\nAnd blemishes it left alone:\n{listed(small)}" if small else ""
        if not serious:
            log.info("the check of the joins passed the script of video %s", video["id"])
            if fixed:
                ctx.events.emit("notice", video["id"], text=f"The check of the joins found {_count(fixed)} a viewer would trip on, and the "
                                                            f"script was rewritten to fix them:\n{listed(fixed)}{tail}")
            elif small:
                ctx.events.emit("notice", video["id"], text=f"The check of the joins passed the script.{tail}")
            return script
        if round_no == ROUNDS:      # still tripping after the last rewrite: the owner hears which, and it goes through
            ctx.events.emit("notice", video["id"], text=f"The check of the joins still finds {_count(serious)} a viewer would trip on after "
                                                        f"{ROUNDS} rewrites. Send it back with any of these as a note to fix them:\n{listed(serious)}{tail}")
            return script
        notes = [f"{NOTE}{p['at']}: {p['what']} Fix: {p['fix']}" for p in serious]
        try:
            revised = rewrite(notes, script)
        except FinalError as e:  # the rewrite couldn't pass the checks: the draft that did goes through, notes and all
            log.warning("the script of video %s couldn't be rewritten for its joins (%s); keeping the draft", video["id"], e)
            ctx.events.emit("notice", video["id"], text=f"The check of the joins found {_count(serious)} a viewer would trip on, but "
                                                        f"the rewrite failed the pipeline's checks ({str(e)[:300]}), so the "
                                                        f"script goes through as it was. Send it back with any of these as a "
                                                        f"note to fix them:\n{listed(serious)}{tail}")
            return script
        fixed += serious
        script = revised
        if len(script.get("scenes") or []) < 2:
            break
    ctx.events.emit("notice", video["id"], text=f"The check of the joins found {_count(fixed)} a viewer would trip on, and the "
                                                f"script was rewritten to fix them:\n{listed(fixed)}{tail}")      # too short now to read again, so the last read's blemishes stand
    return script


def _count(problems: list[dict]) -> str:
    return f"{len(problems)} join{'s' if len(problems) != 1 else ''}"


def film_values(out: Path, direction: dict | None, lines: list[dict], folder: Path) -> dict:
    """What the film turn is filled with: the lines, the cuts and the sheets of a finished short at `out`. With no
    direction, the cuts are measured from the picture."""
    laid = cut_sheets.sheets(out, cut_sheets.planned(direction) if direction else None, folder, lines)
    return {"lines": cut_sheets.script_text(lines), "cuts": cut_sheets.listing(laid),
            "measured": MEASURED if laid["measured"] else "The cuts are where the direction starts each shot.",
            "sheets": "\n".join(f"- {s['file']}" for s in laid["sheets"]) or "(none: it's one shot)"}


def check_film(ctx, conn, video, channel, out: Path, direction: dict, lines: list[dict]) -> list[dict]:
    """The finished short's joins: [{at, in, what, fix, serious}]. Those `in` the words go to the owner as a notice here,
    since a new line means new voice; the caller sends the picture's on to the director."""
    if not enabled(ctx):
        return []
    values = film_values(out, direction, lines, out.parent / "cuts_review")
    if values["cuts"] == cut_sheets.NO_CUTS:                 # one shot has no joins to see
        return []
    found = ctx.llm.check_joins(channel, "film", values, ctx.meter(conn, video, NAME, "the check of the joins in the film"))
    problems = found.get("problems") or []
    words = [p for p in problems if p.get("in") == "words"]
    if words:
        ctx.events.emit("notice", video["id"], text=f"The check of the joins found {len(words)} in the words. Changing a "
                                                    f"line now means paying for its voice again, so these are yours to "
                                                    f"decide (send the short back with a note to fix one):\n{listed(words)}")
    return [p for p in problems if p.get("in") != "words"]

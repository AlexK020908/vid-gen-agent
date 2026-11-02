"""The reviewer's pass over a draft outline or script before the owner sees it.

A second Claude call (prompts/critic.md, models.critic) reads the draft as the channel's toughest viewer: would a
sensible person do this, could it be done that way, does it take the time it takes, do the rules bind everyone,
is every day told and every thread closed. What it finds goes back to the writer once, as notes alongside the
owner's, through the same revise turn a sent-back draft uses; the thread is told what was fixed. One pass only:
a draft that still has problems after it goes to the owner, who can send it back with a note as always.
Nothing runs when models.critic is unset (or stickfleet.yaml says `critic: off`).
"""
from __future__ import annotations

import logging
from typing import Callable

from core.errors import FinalError

log = logging.getLogger("stickfleet.review")

NAME = "critic"


def enabled(ctx) -> bool:
    return bool(ctx.config.models.get(NAME)) and str(ctx.config.models.get(NAME)).lower() != "off"


def reviewed(ctx, conn, video, channel, kind: str, values: dict, draft, rewrite: Callable[[list[str]], object]):
    """`draft` as the reviewer passes it, or rewritten once with the reviewer's notes (`rewrite(notes)` is the
    writer's revise call). `values` fill prompts/critic.md's `kind` turn."""
    if not enabled(ctx):
        return draft
    meter = ctx.meter(conn, video, NAME, f"the review of the {kind}")
    found = ctx.llm.critique(channel, kind, values, meter)
    problems = found.get("problems") or []
    if found.get("verdict") == "fine" or not problems:
        log.info("the reviewer passed the %s of video %s", kind, video["id"])
        return draft
    notes = [f"Reviewer, {p['where']}: {p['what']} Fix: {p['fix']}" for p in problems]
    log.info("the reviewer sent the %s of video %s back with %d problems", kind, video["id"], len(notes))
    said = "\n".join(f"- {p['where']}: {p['what']} Fix: {p['fix']}" for p in problems)
    things = f"{len(problems)} thing{'s' if len(problems) != 1 else ''}"
    try:
        revised = rewrite(notes)
    except FinalError as e:  # the rewrite couldn't pass the checks: the draft that did goes through, notes and all
        log.warning("the reviewed %s of video %s couldn't be rewritten cleanly (%s); keeping the draft", kind,
                    video["id"], e)
        ctx.events.emit("notice", video["id"], text=f"The reviewer found {things} in the {kind} that wouldn't work, "
                                                    f"but the rewrite with its fixes failed the pipeline's checks "
                                                    f"({str(e)[:300]}), so the {kind} goes through as first written. "
                                                    f"Send it back with any of these as a note to fix them:\n{said}")
        return draft
    ctx.events.emit("notice", video["id"], text=f"The reviewer found {things} in the {kind} that wouldn't work, and "
                                                f"it was rewritten to fix them:\n{said}")
    return revised

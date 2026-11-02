"""`providers.llm: session`: the Claude Code session does Claude's work, never the API key.

Every call builds the same prompt, schema and checks as providers/claude.py; only the API request is swapped for a
job the session answers over MCP (core/jobs.py). The first time a stage asks, the request is stored and the stage
parks; once the session's answer has passed the checks, the stage runs again and gets it back as Claude's reply.

The calls move over phase by phase (BUILD.md, phases 17–20). READY lists the ones the session does so far; the rest
fail with a clear error rather than reach the API. Tests pass a stub `fallback` for them instead.
"""
from __future__ import annotations

from contextlib import closing
from types import SimpleNamespace
from typing import Callable

from core import cards, db, jobs
from core.errors import FinalError, Stopped
from providers.claude import WHAT, ClaudeLLM

# LLM method → claude.py's kind
METHODS = {"outline": "outline", "script": "script", "revise_visual": "regen", "rewrite_line": "regen",
           "titles": "titles", "topics": "topic", "check_picture": "check", "map_stage": "check",
           "name_parts": "check", "critique": "critic", "scene_sheet": "check", "inventory": "check"}
READY = {"titles", "outline", "script", "critique", "rewrite_line", "revise_visual", "topics"}  # phase 20: the looking


class _NoAPI:
    def __getattr__(self, name):
        raise FinalError("the session provider never calls the Claude API")


class SessionLLM(ClaudeLLM):
    def __init__(self, config, fallback=None) -> None:
        super().__init__(config, client=_NoAPI())
        self.fallback = fallback
        for name in METHODS:
            if name not in READY:
                setattr(self, name, self._not_yet(name))

    def _not_yet(self, name: str):
        def call(*args, **kwargs):
            if self.fallback is None:
                raise FinalError(f"Claude Code doesn't do the {WHAT[METHODS[name]]} yet (it moves over in phase 20, "
                                 "see BUILD.md), and the API key isn't used for it")
            return getattr(self.fallback, name)(*args, **kwargs)
        return call

    def _call(self, kind: str, system: str, messages: list[dict], schema: dict, meter, on_text,
              verify: Callable[[str], list[str]] | None = None, verify_part: Callable[[str], list[str]] | None = None):
        """The stored answer to this exact request, or a new job and NeedsClaude. After Stop, answers already in
        are still replayed (a stage runs again from the top), and it stops where it would have waited."""
        request = jobs.plain(messages)
        k = jobs.key(kind, system, request, schema)
        video = getattr(meter, "video", None)  # a Meter; a ChannelMeter has the channel, and maybe a video it's about
        video_id = video["id"] if video else getattr(meter, "video_id", None)
        channel_id = video["channel_id"] if video else getattr(meter, "channel_id", None)
        what = getattr(meter, "what", None) or f"the {WHAT[kind]}"
        with closing(db.connect(self.config.db_path)) as conn:
            found = jobs.answer_for(conn, k)
            if found is None:
                if getattr(meter, "stopped", False):
                    raise Stopped(f"stopped before writing the {WHAT[kind]}")
                job_id, new = jobs.park(conn, k, kind, what, system, request, schema, verify, video_id=video_id,
                                        scene_id=getattr(meter, "scene_id", None), channel_id=channel_id,
                                        part_check=verify_part)
        if found is None:
            ctx = getattr(meter, "ctx", None)
            if new and ctx is not None:
                said = f"Waiting for Claude Code: {what} (job {job_id}). Ask it to do the waiting jobs."
                ctx.events.emit("claude_job", video["id"] if video else None, job_id=job_id, what=what)
                if video:
                    ctx.events.emit("notice", video["id"], text=said)
                elif channel_id:  # topic ideas: the channel's home thread
                    with closing(db.connect(self.config.db_path)) as conn:
                        cards.post(ctx, conn, cards.home_thread_id(conn, channel_id), "system", text=said)
            raise jobs.NeedsClaude(job_id, what)
        _, text = found
        if on_text:
            on_text(text)
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=text)], stop_reason="end_turn")

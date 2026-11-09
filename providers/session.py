"""`providers.llm: session`: the Claude Code session does all of Claude's work, on the owner's plan; nothing calls the
Claude API (BUILD.md, phases 17–20).

Every call builds its prompt, schema and checks in providers/claude.py; the request becomes a job the session
answers over MCP (core/jobs.py). The first time a stage asks, the request is stored and the stage parks; once the
session's answer has passed the checks, the stage runs again and gets it back as Claude's reply.

The looking jobs (LOOKING: picture checks, stage maps, part names, the props list, scene sheets, and a 3D short's
models and shots) carry pictures or
come one per scene, so the session hands them to its `worker` agent (.claude/agents/worker.md) and keeps them out of
the main chat. The writing and the reviews stay in the main chat and the `critic` agent.
"""
from __future__ import annotations

from contextlib import closing
from typing import Callable

from core import cards, db, jobs
from core.errors import Stopped
from providers.claude import WHAT, ClaudeLLM

LOOKING = ("picture", "map", "parts", "inventory", "sheet", "source", "thing", "film", "look")  # job kinds the worker agent does


class SessionLLM(ClaudeLLM):
    def __init__(self, config, stub=None, stubbed: tuple[str, ...] = ()) -> None:
        """Tests: the LLM methods named in `stubbed` are answered by `stub` (a StubLLM) instead of becoming jobs."""
        super().__init__(config)
        for name in stubbed:
            setattr(self, name, getattr(stub, name))

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
        return text

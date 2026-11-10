"""Shared runtime handle passed to stages, actions, cards and the server."""
from __future__ import annotations

import sqlite3
import threading
from contextlib import closing, contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

from core import costs, db
from core.errors import Stopped
from core.config import ROOT, Channel, Config, load
from core.events import EventBus

MEDIA_DIRS = ("stills", "audio", "clips", "thumbs", "render")


@dataclass
class Ctx:
    config: Config
    events: EventBus
    llm: Any
    tts: Any
    images: Any
    video: Any
    youtube: Any = None  # tests set a fake: channel_id -> YouTube service object (see youtube/client.py)
    google: dict = field(default_factory=dict)  # tests set fakes: API name -> (channel_id -> service); youtube/client.py
    instagram: Any = None  # tests set a fake in place of instagram.client.Client
    _held: dict[int, float] = field(default_factory=dict, repr=False)  # video id → money promised to running calls
    _held_lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _stops: set[int] = field(default_factory=set, repr=False)  # videos whose writing was stopped

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        with closing(db.connect(self.config.db_path)) as conn:
            yield conn

    def channel(self, channel_id: str) -> Channel:
        try:
            return self.config.channels[channel_id]
        except KeyError:
            raise ValueError(f"unknown channel {channel_id!r}") from None

    # --- media paths: stored relative to data/media, served at /media ---------

    def media(self, video_id: int) -> Path:
        base = self.config.media_dir / f"v{video_id}"
        for name in MEDIA_DIRS:
            (base / name).mkdir(parents=True, exist_ok=True)
        return base

    def rel(self, path: Path) -> str:
        return Path(path).resolve().relative_to(self.config.media_dir.resolve()).as_posix()

    def abs(self, rel: str | None) -> Path | None:
        return self.config.media_dir / rel if rel else None

    # --- costs: stub providers log simulated costs, real ones what the call cost ---

    def is_stub(self, provider: str) -> bool:
        return self.config.provider(provider) == "stub"

    def _counts(self, provider: str) -> bool:
        return not self.is_stub(provider) or self.config.stub.get("simulate_costs", True)

    def log_cost(self, conn: sqlite3.Connection, video_id: int, stage: str, provider: str, usd: float,
                 detail: dict | None = None) -> None:
        if self._counts(provider):
            costs.log(conn, video_id, stage, provider, usd, simulated=self.is_stub(provider), detail=detail)

    def guard(self, conn: sqlite3.Connection, video: sqlite3.Row, usd: float, what: str, provider: str) -> None:
        if self._counts(provider):
            usd += self._held.get(video["id"], 0.0)
            costs.guard(conn, video["id"], self.channel(video["channel_id"]).budget_usd, usd, what)

    @contextmanager
    def reserve(self, conn: sqlite3.Connection, video: sqlite3.Row, usd: float, what: str, provider: str,
                downgrade: bool = False) -> Iterator[bool]:
        """Guard a call costing up to `usd` and count it against the budget until the block ends, so calls
        running in parallel can't all pass the same check. Log the call's cost inside the block.

        Yields True. With downgrade=True it yields False instead of raising when the call doesn't fit.
        """
        with self._held_lock:
            try:
                self.guard(conn, video, usd, what, provider)
            except costs.BudgetExceeded:
                if not downgrade:
                    raise
                fits = False
            else:
                fits = True
                self._held[video["id"]] = self._held.get(video["id"], 0.0) + usd
        try:
            yield fits
        finally:
            if fits:
                with self._held_lock:
                    self._held[video["id"]] -= usd

    def stop_writing(self, video_id: int) -> None:
        """Stop the writing of this video's outline or script: its next Claude call stops instead of waiting for
        the session (providers/session.py)."""
        with self._held_lock:
            self._stops.add(video_id)

    def writing_done(self, video_id: int) -> None:
        with self._held_lock:
            self._stops.discard(video_id)

    def meter(self, conn: sqlite3.Connection, video: sqlite3.Row, stage: str, what: str,
              scene_id: int | None = None) -> "Meter":
        return Meter(self, conn, video, stage, what, scene_id)

    def channel_meter(self, conn: sqlite3.Connection, stage: str, what: str, channel_id: str,
                      video_id: int | None = None) -> "ChannelMeter":
        return ChannelMeter(self, conn, stage, what, channel_id, video_id)

    # --- engine settings -------------------------------------------------------

    @property
    def lease_s(self) -> float:
        return float(self.config.engine.get("lease_s", 600))

    @property
    def max_attempts(self) -> int:
        return int(self.config.engine.get("max_attempts", 3))

    @property
    def retry_backoff_s(self) -> float:
        return float(self.config.engine.get("retry_backoff_s", 5))

    @property
    def parallel_calls(self) -> int:
        return int(self.config.engine.get("parallel_calls", 8))


@dataclass
class Meter:
    """One stage's LLM calls on one video: what they're for (`what`, the job's name in the thread), whether the
    person pressed Stop, and the scene a scene stage's call is for (`scene_id`), so a Claude Code job waiting on it
    wakes that scene (core/jobs.py). The session's work costs nothing; the stub LLM logs what Claude used to cost
    on the API through `check` and `spend`, as simulated costs."""
    ctx: Ctx
    conn: sqlite3.Connection
    video: sqlite3.Row
    stage: str
    what: str
    scene_id: int | None = None

    def check(self, usd: float) -> None:
        """Raises BudgetExceeded if a call costing up to `usd` would take the video over budget, and Stopped if
        the person has pressed Stop."""
        if self.stopped:
            raise Stopped(f"stopped before writing {self.what}")
        self.ctx.guard(self.conn, self.video, usd, self.what, "llm")

    def spend(self, usd: float, detail: dict | None = None) -> None:
        self.ctx.log_cost(self.conn, self.video["id"], self.stage, "llm", usd, detail)

    @property
    def stopped(self) -> bool:
        return self.video["id"] in self.ctx._stops


@dataclass
class ChannelMeter:
    """Like Meter, for an LLM call that belongs to a channel rather than a video (topic ideas): there's no video
    budget to count against, and the stub's simulated costs are logged with no video. `video_id` is a video the
    call is about (a winner's follow-ups), so its Claude Code job is told apart from the channel's other topic
    ideas."""
    ctx: Ctx
    conn: sqlite3.Connection
    stage: str
    what: str
    channel_id: str
    video_id: int | None = None

    def check(self, usd: float) -> None:
        pass

    def spend(self, usd: float, detail: dict | None = None) -> None:
        self.ctx.log_cost(self.conn, None, self.stage, "llm", usd, detail)

    stopped = False  # topic ideas can't be stopped


def make_ctx(root: Path | None = None, data_dir: Path | None = None, overrides: dict | None = None) -> Ctx:
    from core.cards import CardPoster
    from providers import make_providers

    config = load(root or ROOT, data_dir, overrides)
    config.media_dir.mkdir(parents=True, exist_ok=True)
    db.init(config.db_path)
    with closing(db.connect(config.db_path)) as conn:
        db.sync_channels(conn, config.channels)
    ctx = Ctx(config, EventBus(), *make_providers(config))
    CardPoster(ctx).attach()
    return ctx

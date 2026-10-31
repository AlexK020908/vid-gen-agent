"""The assembly line. Runs every stage in a loop and never moves a video past a gate."""
from __future__ import annotations

import asyncio
import logging

from core import db

log = logging.getLogger("stickfleet.engine")


def default_stages() -> list:
    from stages import ALL
    return ALL


class Engine:
    def __init__(self, ctx, stages: list | None = None) -> None:
        self.ctx = ctx
        self.stages = stages or default_stages()
        self._stop = asyncio.Event()

    def run_round(self) -> bool:
        """Give every stage one turn. True if any stage did work."""
        ran = False
        for stage in self.stages:
            ran = stage.run_once(self.ctx) or ran
        return ran

    def run_until_idle(self, max_rounds: int = 10_000) -> int:
        """Synchronous loop for the CLI and tests: stops when nothing is left to do without a person."""
        for rounds in range(1, max_rounds + 1):
            if not self.run_round():
                return rounds
        raise RuntimeError(f"engine still busy after {max_rounds} rounds")

    async def run_forever(self) -> None:
        """Server mode: one async loop per stage so a long render doesn't hold up other videos."""
        with self.ctx.connect() as conn:
            db.clear_leases(conn)
        idle = float(self.ctx.config.engine.get("idle_sleep_s", 2))

        async def loop(stage) -> None:
            while not self._stop.is_set():
                try:
                    ran = await asyncio.to_thread(stage.run_once, self.ctx)
                except Exception:
                    log.exception("stage %s crashed", stage.NAME)
                    ran = False
                if not ran:
                    try:
                        await asyncio.wait_for(self._stop.wait(), timeout=idle)
                    except asyncio.TimeoutError:
                        pass

        await asyncio.gather(*(loop(s) for s in self.stages))

    def stop(self) -> None:
        self._stop.set()

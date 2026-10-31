"""Per-call cost logging and the per-video budget guard."""
from __future__ import annotations

import json
import sqlite3
import time

from core import db


class BudgetExceeded(Exception):
    pass


def log(conn: sqlite3.Connection, video_id: int, stage: str, provider: str, usd: float, simulated: bool = False,
        detail: dict | None = None) -> None:
    """`detail` is what the call was (model, token counts), kept for checking estimates against real runs."""
    if usd <= 0:
        return
    with db.tx(conn):
        conn.execute(
            """INSERT INTO costs (video_id, stage, provider, usd, simulated, detail, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (video_id, stage, provider, usd, int(simulated), json.dumps(detail) if detail else None, time.time()),
        )
        conn.execute("UPDATE videos SET cost_usd = cost_usd + ? WHERE id = ?", (usd, video_id))


def spent(conn: sqlite3.Connection, video_id: int) -> float:
    row = conn.execute("SELECT cost_usd FROM videos WHERE id = ?", (video_id,)).fetchone()
    return float(row["cost_usd"]) if row else 0.0


def would_exceed(conn: sqlite3.Connection, video_id: int, budget_usd: float, usd: float) -> bool:
    return spent(conn, video_id) + usd > budget_usd + 1e-9


def guard(conn: sqlite3.Connection, video_id: int, budget_usd: float, usd: float, what: str) -> None:
    if would_exceed(conn, video_id, budget_usd, usd):
        total = spent(conn, video_id) + usd
        raise BudgetExceeded(
            f"{what} would bring video {video_id} to ${total:.2f}, over its ${budget_usd:.2f} budget. "
            "Raise budget_usd in the channel YAML, then Retry."
        )

"""Claude's work done by the Claude Code session instead of the API (providers/session.py, server/claude_code.py).

A stage that needs Claude builds the request it would send the API. If that exact request has an answer here, the
answer comes back as Claude's reply. If not, the request is stored as a pending job and the stage parks
(NeedsClaude): the video is leased for PARK_S, nothing counts as a failed attempt, and the thread says what's
waiting. The session lists the jobs, takes one and answers it over MCP. The answer is checked at once with the
checks the API's reply goes through (the stage's own check, registered here while the server runs); once it
passes, the lease is cleared, so the engine runs the stage again straight away and this time the request finds
its answer. A stage that runs again builds the same request, so it finds the same job: re-running is free.
"""
from __future__ import annotations

import hashlib
import json
import threading
import time
from typing import Callable

from core import db

PARK_S = 900    # a parked stage looks again after this long, in case an answer's un-park was missed (or a restart)
TAKEN_S = 900   # a job taken this recently is left to whoever took it, so two workers never do the same one


class NeedsClaude(Exception):
    """Raised by a Claude call that has no answer yet; core/stage.py parks the stage instead of failing it."""

    def __init__(self, job_id: int, what: str) -> None:
        super().__init__(f"waiting for Claude Code: {what} (job {job_id})")
        self.job_id = job_id


_checks: dict[int, Callable[[str], list[str]]] = {}
_lock = threading.Lock()


def plain(messages: list[dict]) -> list[dict]:
    """The messages as JSON: the assistant turn of a retry holds reply objects, not dicts."""
    out = []
    for m in messages:
        content = m["content"]
        if not isinstance(content, str):
            content = [b if isinstance(b, dict) else {"type": "text", "text": getattr(b, "text", "") or ""}
                       for b in content if isinstance(b, dict) or getattr(b, "type", "") == "text"]
        out.append({"role": m["role"], "content": content})
    return out


def key(kind: str, system: str, messages: list[dict], schema: dict) -> str:
    raw = json.dumps({"kind": kind, "system": system, "messages": messages, "schema": schema}, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()


def answer_for(conn, k: str) -> tuple[int, str] | None:
    row = conn.execute("SELECT id, answer FROM claude_jobs WHERE key = ? AND status = 'answered'", (k,)).fetchone()
    return (row["id"], row["answer"]) if row else None


def park(conn, k: str, kind: str, what: str, system: str, messages: list[dict], schema: dict,
         check: Callable[[str], list[str]] | None, video_id: int | None = None, scene_id: int | None = None,
         channel_id: str | None = None) -> tuple[int, bool]:
    """Stores the request as a pending job unless it's there already, and registers its check. A newer request
    for the same video, scene and kind (a prompt edited in between, say) supersedes the older one.
    Returns (job id, whether it's new)."""
    with db.tx(conn):
        row = conn.execute("SELECT id, status FROM claude_jobs WHERE key = ?", (k,)).fetchone()
        new = row is None
        if new:
            conn.execute("""UPDATE claude_jobs SET status = 'superseded' WHERE status = 'pending' AND kind = ?
                              AND video_id IS ? AND scene_id IS ? AND channel_id IS ?""",
                         (kind, video_id, scene_id, channel_id))
            job_id = conn.execute(
                """INSERT INTO claude_jobs (key, kind, what, video_id, scene_id, channel_id, system, messages_json,
                     schema_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (k, kind, what, video_id, scene_id, channel_id, system, json.dumps(messages), json.dumps(schema),
                 time.time())).lastrowid
        else:
            job_id = row["id"]
            if row["status"] == "superseded":  # asked for again (the prompt edit was undone)
                conn.execute("UPDATE claude_jobs SET status = 'pending' WHERE id = ?", (job_id,))
    if check is not None:
        with _lock:
            _checks[job_id] = check
    return job_id, new


def pending(conn) -> list:
    return conn.execute("""SELECT j.*, s.idx AS scene_idx FROM claude_jobs j LEFT JOIN scenes s ON s.id = j.scene_id
                           WHERE j.status = 'pending' ORDER BY j.id""").fetchall()


def get(conn, job_id: int):
    row = conn.execute("SELECT * FROM claude_jobs WHERE id = ?", (job_id,)).fetchone()
    if row is None:
        raise LookupError(f"there's no job {job_id}")
    return row


def take(conn, job_id: int, again: bool = False):
    """Marks the job taken and returns it. Refuses one another worker took within TAKEN_S, unless `again`."""
    row = get(conn, job_id)
    if row["status"] != "pending":
        raise ValueError(f"job {job_id} is {row['status']}, not waiting")
    now = time.time()
    if row["taken_at"] and now - row["taken_at"] < TAKEN_S and not again:
        raise ValueError(f"job {job_id} was taken {int((now - row['taken_at']) // 60)} min ago, so another worker "
                         "may be on it; pass again=true if that worker is gone")
    with db.tx(conn):
        conn.execute("UPDATE claude_jobs SET taken_at = ? WHERE id = ?", (now, job_id))
    return row


def answer(conn, job_id: int, text: str) -> list[str]:
    """Checks the answer; [] means it passed, was stored, and the parked stage was woken. Otherwise it returns what's
    wrong and the job stays waiting. After a restart there's no registered check, so only the JSON is checked
    here; the stage's own check runs when it uses the answer, and a failure there comes back as a new job."""
    row = get(conn, job_id)
    if row["status"] != "pending":
        raise ValueError(f"job {job_id} is {row['status']}, not waiting")
    with _lock:
        check = _checks.get(job_id)
    problems = check(text) if check else _json_problems(text)
    if problems:
        return problems
    with db.tx(conn):
        conn.execute("UPDATE claude_jobs SET status = 'answered', answer = ?, answered_at = ? WHERE id = ?",
                     (text, time.time(), job_id))
        if row["video_id"] is not None:
            conn.execute("UPDATE videos SET lease_until = NULL WHERE id = ?", (row["video_id"],))
        if row["scene_id"] is not None:
            conn.execute("UPDATE scenes SET lease_until = NULL WHERE id = ?", (row["scene_id"],))
    with _lock:
        _checks.pop(job_id, None)
    return []


def _json_problems(text: str) -> list[str]:
    try:
        json.loads(text)
    except ValueError as e:
        return [f"the reply isn't the JSON that was asked for ({e})"]
    return []

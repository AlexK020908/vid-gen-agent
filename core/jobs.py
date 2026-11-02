"""Claude's work, done by the Claude Code session (providers/session.py, server/claude_code.py).

A stage that needs Claude builds its request: the prompt, any pictures, and the JSON shape of the reply. If that
exact request has an answer here, the answer comes back as Claude's reply. If not, the request is stored as a
pending job and the stage parks (NeedsClaude): the video (or scene) is leased for PARK_S, nothing counts as a
failed attempt, and the thread says what's waiting. The session lists the jobs, takes one and answers it over MCP.
The answer is checked at once with the stage's own check (registered here while the server runs); once it passes,
the lease is cleared, so the engine runs the stage again straight away and this time the request finds its
answer. A stage that runs again builds the same request, so it finds the same job: re-running is free.

A long answer (a script) can come in parts, each a JSON object of whole pieces (a script's beats, in order): the
parts merge into one reply (lists joined), each part is checked with the stage's part check as it arrives, and the
last one is checked as the whole reply. A job no stage is parked on (topic ideas) carries `resume_json`, what to
run once it's answered.
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


Check = Callable[[str], list[str]]
_checks: dict[int, tuple[Check | None, Check | None]] = {}  # job id → (the whole reply's check, a part's)
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
         check: Check | None, video_id: int | None = None, scene_id: int | None = None,
         channel_id: str | None = None, part_check: Check | None = None) -> tuple[int, bool]:
    """Stores the request as a pending job unless it's there already, and registers its checks. A newer request
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
    if check is not None or part_check is not None:
        with _lock:
            _checks[job_id] = (check, part_check)
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


def answer(conn, job_id: int, text: str, part: int | None = None, last: bool = False) -> list[str]:
    """Checks the answer; [] means it passed. A whole answer that passes is stored and the parked stage woken;
    otherwise this returns what's wrong and the job stays waiting. After a restart there's no registered check, so
    only the JSON is checked here; the stage's own check runs when it uses the answer, and a failure there comes
    back as a new job.

    With `part` (from 1), `text` is one part: the next one, or an earlier one sent again to replace it. A part that
    passes the part check is kept; `last` makes the parts so far the whole answer, checked as such (the parts stay
    either way, so a failure is fixed by sending the parts that need it again, the final one with `last`)."""
    row = get(conn, job_id)
    if row["status"] != "pending":
        raise ValueError(f"job {job_id} is {row['status']}, not waiting")
    with _lock:
        check, part_check = _checks.get(job_id, (None, None))
    if part is not None:
        parts = json.loads(row["parts_json"] or "[]")
        if not 1 <= part <= len(parts) + 1:
            return [f"part {part} can't come yet: {len(parts)} part{'s are' if len(parts) != 1 else ' is'} in, so "
                    f"the next is part {len(parts) + 1}"]
        try:
            piece = json.loads(text)
        except ValueError as e:
            return [f"part {part} isn't JSON ({e})"]
        if not isinstance(piece, dict):
            return [f"part {part} must be a JSON object, a piece of the reply's shape"]
        parts[part - 1:part] = [piece]
        if not last:
            problems = part_check(json.dumps(merge(parts[:part]))) if part_check else []
            if not problems:
                with db.tx(conn):
                    conn.execute("UPDATE claude_jobs SET parts_json = ? WHERE id = ?", (json.dumps(parts), job_id))
            return problems
        with db.tx(conn):
            conn.execute("UPDATE claude_jobs SET parts_json = ? WHERE id = ?", (json.dumps(parts), job_id))
        text = json.dumps(merge(parts))
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


def merge(parts: list[dict]) -> dict:
    """The parts as one reply: a list in more than one part is joined in order; anything else, the latest wins."""
    whole: dict = {}
    for piece in parts:
        for name, value in piece.items():
            if isinstance(value, list) and isinstance(whole.get(name), list):
                whole[name] = whole[name] + value
            else:
                whole[name] = value
    return whole


def parts_so_far(row) -> str:
    """"2 parts in (places 3, scenes 14)": what a job's parts add up to, for the session."""
    parts = json.loads(row["parts_json"] or "[]")
    if not parts:
        return ""
    sizes = ", ".join(f"{name} {len(value)}" for name, value in merge(parts).items() if isinstance(value, list))
    return f"{len(parts)} part{'s' if len(parts) != 1 else ''} in" + (f" ({sizes})" if sizes else "")


def resume_with(conn, job_id: int, what: dict) -> None:
    """Marks a job that no parked stage waits on with what to run once it's answered (stages/topics.py)."""
    with db.tx(conn):
        conn.execute("UPDATE claude_jobs SET resume_json = ? WHERE id = ?", (json.dumps(what), job_id))


def to_resume(conn) -> list:
    return conn.execute("""SELECT * FROM claude_jobs WHERE status = 'answered' AND resume_json IS NOT NULL
                           ORDER BY id""").fetchall()


def resumed(conn, job_id: int) -> None:
    with db.tx(conn):
        conn.execute("UPDATE claude_jobs SET resume_json = NULL WHERE id = ?", (job_id,))


def supersede(conn, video_id: int, kinds: tuple[str, ...]) -> int:
    """Drops a video's waiting jobs of these kinds (Stop on a parked outline or script). Returns how many."""
    with db.tx(conn):
        return conn.execute(f"""UPDATE claude_jobs SET status = 'superseded' WHERE status = 'pending'
                                AND video_id = ? AND kind IN ({','.join('?' * len(kinds))})""",
                            (video_id, *kinds)).rowcount


def _json_problems(text: str) -> list[str]:
    try:
        json.loads(text)
    except ValueError as e:
        return [f"the reply isn't the JSON that was asked for ({e})"]
    return []

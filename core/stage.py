"""Claim → work → release helpers shared by every stage, with retry and failure handling."""
from __future__ import annotations

import logging
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

from core import db, formats
from core.costs import BudgetExceeded
from core.errors import FinalError, Stopped
from core.jobs import PARK_S, NeedsClaude

log = logging.getLogger("stickfleet.stage")

# Returns None, or seconds to wait before the video is claimed again (e.g. "YouTube hasn't flipped it yet").
VideoWork = Callable[["Ctx", sqlite3.Connection, sqlite3.Row], float | None]  # noqa: F821
SceneWork = Callable[["Ctx", sqlite3.Connection, sqlite3.Row, sqlite3.Row], tuple[dict, str]]  # noqa: F821


def fail(ctx, conn: sqlite3.Connection, video_id: int, stage: str, message: str, final: bool = False) -> None:
    """Count a failed attempt; after max_attempts (or a final error) the video goes to `failed`."""
    error = f"{stage}: {message}"
    with db.tx(conn):
        video = db.get_video(conn, video_id)
        if video["state"] == "failed":
            return
        attempts = video["attempts"] + 1
        failed = final or attempts >= ctx.max_attempts
        if failed:
            conn.execute(
                """UPDATE videos SET state = 'failed', resume_state = ?, attempts = ?, error = ?,
                     lease_until = NULL, updated_at = ? WHERE id = ?""",
                (video["state"], attempts, error, time.time(), video_id),
            )
        else:
            db.update_video(conn, video_id, attempts=attempts, error=error,
                            lease_until=time.time() + ctx.retry_backoff_s * attempts)
    if failed:
        ctx.events.emit("stage_failed", video_id, stage=stage, error=error)


def run_video_stage(ctx, name: str, state: str, work: VideoWork, where: str = "", params: tuple = (),
                    lease_s: float | None = None) -> bool:
    """Claim one video in `state` and run `work` on it. Returns True if anything was claimed."""
    with ctx.connect() as conn:
        video = db.claim_video(conn, state, lease_s or ctx.lease_s, f"{where} {formats.condition(ctx.config, name)}", params)
        if video is None:
            return False
        try:
            wait = work(ctx, conn, video)
        except NeedsClaude:  # parked until the Claude Code session answers (core/jobs.py); not a failed attempt
            db.update_video(conn, video["id"], lease_until=time.time() + PARK_S)
        except Stopped:
            back_to_review(ctx, conn, video["id"], name)
        except (BudgetExceeded, FinalError) as e:
            fail(ctx, conn, video["id"], name, str(e), final=True)
        except Exception as e:
            log.exception("%s failed on video %s", name, video["id"])
            fail(ctx, conn, video["id"], name, f"{type(e).__name__}: {e}")
        else:
            db.update_video(conn, video["id"], lease_until=time.time() + wait if wait else None)
        finally:
            ctx.writing_done(video["id"])
        return True


def back_to_review(ctx, conn: sqlite3.Connection, video_id: int, stage: str) -> None:
    """Stop pressed while Claude wrote: go back to the card it came from. A revision returns to its draft with the
    note that started it taken back as the card's draft note; a first script returns to the outline it was written
    from."""
    video = db.get_video(conn, video_id)
    to, gate = None, None
    if stage == "outline" and video["outline_json"]:
        to, gate = "outlined", "outline"
    elif stage == "script":
        to, gate = ("scripted", "script") if video["script_json"] else ("outlined", "outline")
    if to is None:
        fail(ctx, conn, video_id, stage, "you stopped it before the outline was written; Retry to write it",
             final=True)
        return
    note = None
    with db.tx(conn):
        if gate == stage:  # a revision: the newest note for this card is the one it was rewriting with
            row = conn.execute("SELECT id, note FROM feedback WHERE video_id = ? AND gate = ? ORDER BY id DESC LIMIT 1",
                               (video_id, gate)).fetchone()
            card = conn.execute("""SELECT card_status FROM messages WHERE video_id = ?
                                   AND json_extract(card_json, '$.kind') = ? ORDER BY id DESC LIMIT 1""",
                                (video_id, gate)).fetchone()
            if row and card and card["card_status"] == "revised":  # regenerate adds no note
                note = row["note"]
                conn.execute("DELETE FROM feedback WHERE id = ?", (row["id"],))
        db.transition(conn, video_id, video["state"], to, draft_note=note)
    ctx.events.emit("notice", video_id, text="Stopped. " + (f"Back to the card, with your note kept as its draft "
                                                            f"note to change and send again with revise: {note}"
                                                            if note else "Back to the card."))
    ctx.events.emit("gate_reached", video_id, gate=gate)


def run_scene_stage(ctx, name: str, state: str, work: SceneWork, done_sql: str, limit: int | None = None,
                    where: str = "") -> bool:
    """Claim a batch of scenes in `state` and run `work` on them in parallel.

    `work` returns (fields to update, next scene state). `done_sql` is a scene-level SQL
    condition used for the progress line ("voice 40/120"). `limit` is how many scenes to claim at once
    (two per parallel call when None); 1 runs the scenes one at a time in order, for work where each
    scene builds on the one before it: a scene waiting (on Claude Code, or to try again) holds its place.
    A scene whose work needs Claude Code waits for it (NeedsClaude) without counting a failed attempt.
    """
    with ctx.connect() as conn:
        scenes = db.claim_scenes(conn, state, limit or ctx.parallel_calls * 2, ctx.lease_s, ctx.max_attempts,
                                 f"{where} {formats.condition(ctx.config, name, 'v.channel_id')}", in_order=limit == 1)
    if not scenes:
        return False

    def one(scene: sqlite3.Row) -> None:
        with ctx.connect() as c:
            video = db.get_video(c, scene["video_id"])
            if video["state"] != "generating":
                db.update_scene(c, scene["id"], lease_until=None)
                return
            try:
                fields, next_state = work(ctx, c, video, scene)
                db.update_scene(c, scene["id"], state=next_state, attempts=0, lease_until=None, **fields)
            except NeedsClaude:  # parked until the session answers, which clears the lease (core/jobs.py)
                db.update_scene(c, scene["id"], lease_until=time.time() + PARK_S)
            except (BudgetExceeded, FinalError) as e:
                db.update_scene(c, scene["id"], lease_until=None)
                fail(ctx, c, video["id"], name, str(e), final=True)
            except Exception as e:
                log.exception("%s failed on video %s scene %s", name, video["id"], scene["idx"])
                attempts = scene["attempts"] + 1
                db.update_scene(c, scene["id"], attempts=attempts,
                                lease_until=time.time() + ctx.retry_backoff_s * attempts)
                if attempts >= ctx.max_attempts:
                    fail(ctx, c, video["id"], name, f"scene {scene['idx']}: {type(e).__name__}: {e}", final=True)

    with ThreadPoolExecutor(max_workers=ctx.parallel_calls) as pool:
        list(pool.map(one, scenes))

    with ctx.connect() as conn:
        for video_id in sorted({s["video_id"] for s in scenes}):
            row = conn.execute(
                f"""SELECT SUM(CASE WHEN {done_sql} THEN 1 ELSE 0 END) AS done, COUNT(*) AS total
                    FROM scenes WHERE video_id = ?""",
                (video_id,),
            ).fetchone()
            cost = conn.execute("SELECT cost_usd FROM videos WHERE id = ?", (video_id,)).fetchone()["cost_usd"]
            ctx.events.emit("stage_progress", video_id, stage=name, done=row["done"] or 0,
                            total=row["total"], cost_usd=cost)
    return True

"""SQLite schema, connections, state transitions and leases.

Connections run in autocommit mode; multi-statement writes go through `tx()`,
which takes the write lock up front so concurrent stage threads never deadlock.
"""
from __future__ import annotations

import json
import sqlite3
import time
from contextlib import closing, contextmanager
from pathlib import Path
from typing import Iterable, Iterator

from core.errors import StateError

VIDEO_STATES = (
    "new", "outlined", "outline_approved", "scripted", "generating", "assembled",
    "render_approved", "publishing", "scheduled", "live", "failed", "blocked",
)
SCENE_STATES = ("pending", "voiced", "still_done", "ok", "flagged")

SCHEMA = """
CREATE TABLE IF NOT EXISTS channels (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  scenario_family TEXT,
  character_ref_image TEXT,
  voice_id TEXT,
  style_prompt TEXT,
  gates TEXT,
  youtube_channel_id TEXT
);
CREATE TABLE IF NOT EXISTS topics (
  id INTEGER PRIMARY KEY,
  channel_id TEXT NOT NULL REFERENCES channels(id),
  title TEXT NOT NULL,
  score REAL NOT NULL DEFAULT 0,
  source TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'queued',
  created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS videos (
  id INTEGER PRIMARY KEY,
  channel_id TEXT NOT NULL REFERENCES channels(id),
  topic_id INTEGER REFERENCES topics(id),
  state TEXT NOT NULL,
  outline_json TEXT,
  script_json TEXT,
  thumbs_json TEXT,
  title TEXT,
  thumb_idx INTEGER,
  publish_at REAL,
  publish_json TEXT,
  video_path TEXT,
  highlight_path TEXT,
  srt_path TEXT,
  chapters_json TEXT,
  duration_ms INTEGER,
  cost_usd REAL NOT NULL DEFAULT 0,
  youtube_id TEXT,
  attempts INTEGER NOT NULL DEFAULT 0,
  lease_until REAL,
  error TEXT,
  resume_state TEXT,
  created_at REAL NOT NULL,
  updated_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS videos_state ON videos(state);
CREATE TABLE IF NOT EXISTS scenes (
  id INTEGER PRIMARY KEY,
  video_id INTEGER NOT NULL REFERENCES videos(id),
  idx INTEGER NOT NULL,
  beat_idx INTEGER NOT NULL,
  label TEXT,
  narration TEXT NOT NULL,
  visual_prompt TEXT NOT NULL,
  motion TEXT NOT NULL,
  state TEXT NOT NULL,
  audio_path TEXT,
  still_path TEXT,
  clip_path TEXT,
  duration_ms INTEGER,
  words_json TEXT,
  audio_start_ms INTEGER,
  audio_end_ms INTEGER,
  regen_count INTEGER NOT NULL DEFAULT 0,
  flag_kind TEXT,
  flag_note TEXT,
  attempts INTEGER NOT NULL DEFAULT 0,
  lease_until REAL,
  UNIQUE (video_id, idx)
);
CREATE INDEX IF NOT EXISTS scenes_state ON scenes(state, video_id);
CREATE TABLE IF NOT EXISTS feedback (
  id INTEGER PRIMARY KEY,
  video_id INTEGER NOT NULL REFERENCES videos(id),
  gate TEXT NOT NULL,
  scene_id INTEGER REFERENCES scenes(id),
  note TEXT NOT NULL,
  created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS threads (
  id INTEGER PRIMARY KEY,
  channel_id TEXT NOT NULL REFERENCES channels(id),
  video_id INTEGER UNIQUE REFERENCES videos(id),
  title TEXT NOT NULL,
  sdk_session_id TEXT,
  agent_cost_usd REAL NOT NULL DEFAULT 0,
  created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
  id INTEGER PRIMARY KEY,
  thread_id INTEGER NOT NULL REFERENCES threads(id),
  video_id INTEGER REFERENCES videos(id),
  role TEXT NOT NULL,
  text TEXT,
  card_json TEXT,
  card_status TEXT,
  created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS messages_thread ON messages(thread_id, id);
CREATE TABLE IF NOT EXISTS metrics (
  video_id INTEGER NOT NULL REFERENCES videos(id),
  captured_at REAL NOT NULL,
  views INTEGER,
  avd_seconds REAL,
  avd_pct REAL,
  impressions INTEGER,
  ctr REAL,
  subs_gained INTEGER
);
CREATE TABLE IF NOT EXISTS competitor_videos (
  youtube_id TEXT PRIMARY KEY,
  competitor_id TEXT NOT NULL,
  competitor_name TEXT,
  title TEXT NOT NULL,
  published_at REAL NOT NULL,
  duration_s INTEGER,
  views INTEGER NOT NULL,
  checked_at REAL NOT NULL,
  simulated INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS competitor_views (
  youtube_id TEXT NOT NULL REFERENCES competitor_videos(youtube_id),
  captured_at REAL NOT NULL,
  views INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS reach_days (
  channel_id TEXT NOT NULL REFERENCES channels(id),
  day TEXT NOT NULL,
  report_id TEXT NOT NULL,
  created TEXT NOT NULL,
  PRIMARY KEY (channel_id, day)
);
CREATE TABLE IF NOT EXISTS reach (
  youtube_id TEXT NOT NULL,
  day TEXT NOT NULL,
  impressions INTEGER NOT NULL,
  ctr REAL,
  PRIMARY KEY (youtube_id, day)
);
CREATE TABLE IF NOT EXISTS family_holds (
  channel_id TEXT NOT NULL REFERENCES channels(id),
  family TEXT NOT NULL,
  until REAL NOT NULL,
  video_id INTEGER REFERENCES videos(id),
  created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS swaps (
  id INTEGER PRIMARY KEY,
  video_id INTEGER NOT NULL REFERENCES videos(id),
  applied_at REAL NOT NULL,
  old_title TEXT,
  new_title TEXT,
  old_thumb_idx INTEGER,
  new_thumb_idx INTEGER,
  ctr_before REAL,
  live INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS costs (
  id INTEGER PRIMARY KEY,
  video_id INTEGER REFERENCES videos(id),
  stage TEXT NOT NULL,
  provider TEXT NOT NULL,
  usd REAL NOT NULL,
  simulated INTEGER NOT NULL DEFAULT 0,
  detail TEXT,
  created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS quota (
  date TEXT NOT NULL,
  bucket TEXT NOT NULL,
  units INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY (date, bucket)
);
"""

# Columns added after a table first shipped: (table, column, declaration). init() adds any that are missing.
MIGRATIONS = (
    ("threads", "agent_cost_usd", "REAL NOT NULL DEFAULT 0"),
    ("costs", "detail", "TEXT"),
    ("topics", "why", "TEXT"),                 # Claude's one line on why it should work
    ("topics", "based_on", "TEXT"),            # JSON list of the competitor videos it varies
    ("topics", "message_id", "INTEGER"),       # the topics card it appears on
    ("channels", "polled_at", "REAL"),         # last competitor check (or when the next retry is due, less the interval)
    ("channels", "poll_error", "TEXT"),        # the last check's error, so it's posted once
    ("channels", "reach_job_id", "TEXT"),      # the Reporting API job for channel_reach_basic_a1
    ("channels", "reach_after", "TEXT"),       # createTime of the newest reach report imported
    ("channels", "reach_checked_at", "REAL"),
    ("channels", "reach_error", "TEXT"),
    ("metrics", "after_h", "INTEGER"),         # hours after the video went public: 48 or 168
    ("metrics", "simulated", "INTEGER NOT NULL DEFAULT 0"),
    ("metrics", "verdict", "TEXT"),            # winner / loser / mixed / early, once the reading is complete
    ("metrics", "median_avd_pct", "REAL"),     # the medians it was judged against
    ("metrics", "median_ctr", "REAL"),
    ("metrics", "median_n", "INTEGER"),
    ("topics", "family", "TEXT"),              # the setting tag Claude gives an idea (ocean, underground, ...)
    ("channels", "signin_checked_at", "REAL"),
    ("channels", "signin_error", "TEXT"),
    ("videos", "draft_note", "TEXT"),          # a note taken back by Stop, shown in the card's note box to edit
    ("videos", "places_json", "TEXT"),         # the script's places; once generating starts, each has its set changes
    ("scenes", "place", "TEXT"),               # the id of the place the still is drawn in (NULL: older scripts)
    ("scenes", "place_v", "INTEGER"),          # how many of that place's set changes came before this scene
    ("scenes", "cast_json", "TEXT"),           # cast members in the still, by name
    ("scenes", "tracker_json", "TEXT"),        # the tracked amounts as this scene leaves them ([] = unchanged)
    ("scenes", "shot", "TEXT"),                # wide, medium or close-up; a close-up gets its place in words only
)

VIDEO_COLUMNS = {
    "outline_json", "script_json", "thumbs_json", "title", "thumb_idx", "publish_at", "publish_json",
    "video_path", "highlight_path", "srt_path", "chapters_json", "duration_ms", "youtube_id",
    "attempts", "lease_until", "error", "resume_state", "draft_note", "places_json",
}
SCENE_COLUMNS = {
    "narration", "visual_prompt", "motion", "state", "audio_path", "still_path", "clip_path",
    "duration_ms", "words_json", "audio_start_ms", "audio_end_ms", "regen_count", "flag_kind",
    "flag_note", "attempts", "lease_until",
}


def connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path, timeout=30, isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


@contextmanager
def tx(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """Write transaction. Nested calls join the outer one."""
    if conn.in_transaction:
        yield conn
        return
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    else:
        conn.execute("COMMIT")


def init(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(connect(path)) as conn:
        conn.executescript(SCHEMA)
        for table, column, decl in MIGRATIONS:
            if column not in {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")


def sync_channels(conn: sqlite3.Connection, channels: dict) -> None:
    """Upsert channel rows from YAML and make sure each has a home thread."""
    with tx(conn):
        for c in channels.values():
            conn.execute(
                """INSERT INTO channels (id, name, scenario_family, character_ref_image, voice_id, style_prompt, gates,
                     youtube_channel_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET name = excluded.name, scenario_family = excluded.scenario_family,
                     character_ref_image = excluded.character_ref_image, voice_id = excluded.voice_id,
                     style_prompt = excluded.style_prompt, gates = excluded.gates,
                     youtube_channel_id = excluded.youtube_channel_id""",
                (c.id, c.name, c.scenario_family, str(c.character_ref), c.voice_id, c.style_prompt, json.dumps(c.gates),
                 c.youtube.get("channel_id")),
            )
            home = conn.execute("SELECT 1 FROM threads WHERE channel_id = ? AND video_id IS NULL", (c.id,)).fetchone()
            if not home:
                conn.execute(
                    "INSERT INTO threads (channel_id, video_id, title, created_at) VALUES (?, NULL, ?, ?)",
                    (c.id, c.name, time.time()),
                )


def clear_leases(conn: sqlite3.Connection) -> None:
    """Single-process app: on startup no one holds a lease."""
    with tx(conn):
        conn.execute("UPDATE videos SET lease_until = NULL")
        conn.execute("UPDATE scenes SET lease_until = NULL")


# --- reads -------------------------------------------------------------------

def get_video(conn: sqlite3.Connection, video_id: int) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM videos WHERE id = ?", (video_id,)).fetchone()
    if row is None:
        raise StateError(f"video {video_id} does not exist")
    return row


def scenes_for(conn: sqlite3.Connection, video_id: int) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM scenes WHERE video_id = ? ORDER BY idx", (video_id,)).fetchall()


def neighbors(conn: sqlite3.Connection, video_id: int, idx: int) -> tuple[str | None, str | None]:
    """The narration of the scenes before and after scene `idx` (None at either end)."""
    rows = conn.execute("SELECT idx, narration FROM scenes WHERE video_id = ? AND idx IN (?, ?)",
                        (video_id, idx - 1, idx + 1)).fetchall()
    around = {r["idx"]: r["narration"] for r in rows}
    return around.get(idx - 1), around.get(idx + 1)


def notes(conn: sqlite3.Connection, video_id: int, gate: str) -> list[str]:
    rows = conn.execute(
        "SELECT note FROM feedback WHERE video_id = ? AND gate = ? ORDER BY id", (video_id, gate)
    ).fetchall()
    return [r["note"] for r in rows]


# --- writes ------------------------------------------------------------------

def _sets(fields: dict, allowed: set[str]) -> tuple[str, list]:
    unknown = set(fields) - allowed
    if unknown:
        raise ValueError(f"unknown columns: {sorted(unknown)}")
    return ", ".join(f"{k} = ?" for k in fields), list(fields.values())


def update_video(conn: sqlite3.Connection, video_id: int, **fields) -> None:
    if not fields:
        return
    sets, values = _sets(fields, VIDEO_COLUMNS)
    conn.execute(f"UPDATE videos SET {sets}, updated_at = ? WHERE id = ?", (*values, time.time(), video_id))


def update_scene(conn: sqlite3.Connection, scene_id: int, **fields) -> None:
    if not fields:
        return
    sets, values = _sets(fields, SCENE_COLUMNS)
    conn.execute(f"UPDATE scenes SET {sets} WHERE id = ?", (*values, scene_id))


def transition(conn: sqlite3.Connection, video_id: int, from_states: str | Iterable[str], to_state: str, **fields) -> None:
    """Move a video between states atomically; raises StateError if it isn't in `from_states`."""
    if to_state not in VIDEO_STATES:
        raise ValueError(f"unknown state {to_state}")
    froms = (from_states,) if isinstance(from_states, str) else tuple(from_states)
    sets, values = _sets(fields, VIDEO_COLUMNS) if fields else ("", [])
    extra = f", {sets}" if sets else ""
    placeholders = ", ".join("?" * len(froms))
    cur = conn.execute(
        f"""UPDATE videos SET state = ?, attempts = 0, error = NULL, lease_until = NULL, updated_at = ?{extra}
            WHERE id = ? AND state IN ({placeholders})""",
        (to_state, time.time(), *values, video_id, *froms),
    )
    if cur.rowcount == 0:
        row = conn.execute("SELECT state FROM videos WHERE id = ?", (video_id,)).fetchone()
        current = row["state"] if row else "missing"
        raise StateError(f"video {video_id} is {current}; this needs it to be {' or '.join(froms)}")


def add_feedback(conn: sqlite3.Connection, video_id: int, gate: str, note: str, scene_id: int | None = None) -> None:
    conn.execute(
        "INSERT INTO feedback (video_id, gate, scene_id, note, created_at) VALUES (?, ?, ?, ?, ?)",
        (video_id, gate, scene_id, note, time.time()),
    )


# --- leases ------------------------------------------------------------------

def claim_video(conn: sqlite3.Connection, state: str, lease_s: float, where: str = "", params: tuple = ()) -> sqlite3.Row | None:
    """Lease the oldest video in `state` (plus an optional extra SQL condition)."""
    now = time.time()
    rows = conn.execute(
        f"""UPDATE videos SET lease_until = ? WHERE id = (
              SELECT id FROM videos WHERE state = ? AND (lease_until IS NULL OR lease_until < ?) {where}
              ORDER BY id LIMIT 1)
            RETURNING *""",
        (now + lease_s, state, now, *params),
    ).fetchall()
    return rows[0] if rows else None


def claim_scenes(conn: sqlite3.Connection, state: str, limit: int, lease_s: float, max_attempts: int) -> list[sqlite3.Row]:
    """Lease up to `limit` scenes in `state` belonging to videos that are generating."""
    now = time.time()
    rows = conn.execute(
        """UPDATE scenes SET lease_until = ? WHERE id IN (
             SELECT s.id FROM scenes s JOIN videos v ON v.id = s.video_id
             WHERE v.state = 'generating' AND s.state = ? AND s.attempts < ?
               AND (s.lease_until IS NULL OR s.lease_until < ?)
             ORDER BY s.video_id, s.idx LIMIT ?)
           RETURNING *""",
        (now + lease_s, state, max_attempts, now, limit),
    ).fetchall()
    return sorted(rows, key=lambda r: (r["video_id"], r["idx"]))

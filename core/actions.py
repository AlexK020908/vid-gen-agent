"""Everything a person (card button) or the agent can do to a video.

Every verb checks state in code, so neither a stale card nor a confused agent can skip a gate.
Approving and publishing are only wired to card buttons; the agent never gets those verbs.
"""
from __future__ import annotations

import json
import sqlite3
import time

from core import db, metadata
from core.errors import ActionError

FLAG_KINDS = ("visual", "narration")
MAX_REGENS = 3
CARD_STATES = {"outline": "outlined", "script": "scripted", "render": "assembled", "publish": "render_approved"}


def _create_video(conn: sqlite3.Connection, channel_id: str, topic_id: int, title: str) -> int:
    now = time.time()
    video_id = conn.execute(
        "INSERT INTO videos (channel_id, topic_id, state, created_at, updated_at) VALUES (?, ?, 'new', ?, ?)",
        (channel_id, topic_id, now, now),
    ).lastrowid
    conn.execute("INSERT INTO threads (channel_id, video_id, title, created_at) VALUES (?, ?, ?, ?)",
                 (channel_id, video_id, title, now))
    return video_id


def new_video(ctx, channel_id: str, idea: str) -> int:
    idea = idea.strip()
    if not idea:
        raise ActionError("the idea is empty")
    ctx.channel(channel_id)
    with ctx.connect() as conn, db.tx(conn):
        topic_id = conn.execute(
            "INSERT INTO topics (channel_id, title, source, status, created_at) VALUES (?, ?, 'manual', 'used', ?)",
            (channel_id, idea, time.time()),
        ).lastrowid
        video_id = _create_video(conn, channel_id, topic_id, idea)
    ctx.events.emit("video_created", video_id, channel_id=channel_id, title=idea)
    return video_id


def _queued_topic(conn: sqlite3.Connection, topic_id: int, channel_id: str | None) -> sqlite3.Row:
    topic = conn.execute("SELECT * FROM topics WHERE id = ?", (topic_id,)).fetchone()
    if topic is None or (channel_id and topic["channel_id"] != channel_id):
        raise ActionError(f"there is no topic {topic_id}{' in this channel' if channel_id else ''}")
    if topic["status"] != "queued":
        raise ActionError(f"topic {topic_id} was already {'started' if topic['status'] == 'used' else topic['status']}")
    return topic


def start_topic(ctx, topic_id: int, channel_id: str | None = None, note: str | None = None) -> int:
    """Start a video from a queued topic (its card's Start button, the agent, or the cadence)."""
    with ctx.connect() as conn, db.tx(conn):
        topic = _queued_topic(conn, topic_id, channel_id)
        conn.execute("UPDATE topics SET status = 'used' WHERE id = ?", (topic_id,))
        video_id = _create_video(conn, topic["channel_id"], topic_id, topic["title"])
    ctx.events.emit("video_created", video_id, channel_id=topic["channel_id"], title=topic["title"], note=note)
    ctx.events.emit("topic_changed", None, topic_id=topic_id)
    return video_id


def suggest_swap(ctx, video_id: int, reason: str | None = None) -> None:
    """Post a card offering a live video's other thumbnails and titles (from its render card). Nothing changes on
    YouTube until the person clicks Apply."""
    with ctx.connect() as conn:
        video = db.get_video(conn, video_id)
    if video["state"] != "live":
        raise ActionError(f"a swap is for a video that's live; this one is {video['state']}")
    if not video["thumbs_json"]:
        raise ActionError("this video has no other thumbnails or titles to swap to")
    ctx.events.emit("swap_suggested", video_id, reason=reason)


def apply_swap(ctx, video_id: int, title_idx: int | None = None, thumb_idx: int | None = None) -> dict:
    """The swap card's Apply: change the live video's title and/or thumbnail to another option (0-based).
    Each change that went through is recorded, even if a later one fails."""
    from youtube import client, quota
    with ctx.connect() as conn:
        video = db.get_video(conn, video_id)
        if video["state"] != "live":
            raise ActionError(f"a swap is for a video that's live; this one is {video['state']}")
        options = json.loads(video["thumbs_json"] or '{"titles": [], "thumbs": []}')
        title = thumb = None
        if title_idx is not None:
            if not 0 <= title_idx < len(options["titles"]):
                raise ActionError(f"there is no title option {title_idx + 1}")
            if options["titles"][title_idx] != video["title"]:
                title = options["titles"][title_idx]
        if thumb_idx is not None:
            if not 0 <= thumb_idx < len(options["thumbs"]):
                raise ActionError(f"there is no thumbnail option {thumb_idx + 1}")
            if thumb_idx != video["thumb_idx"]:
                thumb = thumb_idx
        if title is None and thumb is None:
            raise ActionError("pick a title or thumbnail different from the current one")
        last = conn.execute("SELECT ctr FROM metrics WHERE video_id = ? AND ctr IS NOT NULL ORDER BY after_h DESC "
                            "LIMIT 1", (video_id,)).fetchone()
        live = ctx.config.youtube.get("mode", "stub") == "live" and not (video["youtube_id"] or "").startswith("stub-")
        if live:
            quota.check(conn, (["videos.list", "videos.update"] if title else []) + (["thumbnails.set"] if thumb is not None
                                                                                       else []))
    changed: dict = {}
    try:
        if live:
            yt = client.Client(ctx, video["channel_id"])
            if title:
                yt.update_title(video["youtube_id"], title)
                changed["title"] = title
            if thumb is not None:
                yt.set_thumbnail(video["youtube_id"], ctx.abs(options["thumbs"][thumb]))
                changed["thumb_idx"] = thumb
        else:
            changed = {k: v for k, v in (("title", title), ("thumb_idx", thumb)) if v is not None}
            request = {}
            if title:
                request["videos.update"] = {"id": video["youtube_id"], "snippet": {"title": title}}
            if thumb is not None:
                request["thumbnails.set"] = {"videoId": video["youtube_id"], "image": options["thumbs"][thumb]}
            (ctx.media(video_id) / "swap_request.json").write_text(json.dumps(request, indent=2), encoding="utf-8")
    finally:
        if changed:
            with ctx.connect() as conn, db.tx(conn):
                db.update_video(conn, video_id, **changed)
                conn.execute(
                    """INSERT INTO swaps (video_id, applied_at, old_title, new_title, old_thumb_idx, new_thumb_idx,
                         ctr_before, live) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (video_id, time.time(), video["title"], changed.get("title"), video["thumb_idx"],
                     changed.get("thumb_idx"), last["ctr"] if last else None, int(live)))
            ctx.events.emit("swap_applied", video_id, live=live, **changed)
    return changed


def keep_swap(ctx, video_id: int) -> None:
    """The swap card's Keep as is."""
    from core import cards
    with ctx.connect() as conn:
        if not cards.active_cards(conn, video_id, "swap"):
            raise ActionError("there's no swap card waiting on this video")
    ctx.events.emit("swap_kept", video_id)


def dismiss_topic(ctx, topic_id: int, channel_id: str | None = None) -> None:
    with ctx.connect() as conn, db.tx(conn):
        _queued_topic(conn, topic_id, channel_id)
        conn.execute("UPDATE topics SET status = 'dismissed' WHERE id = ?", (topic_id,))
    ctx.events.emit("topic_changed", None, topic_id=topic_id)


def start_generating(conn: sqlite3.Connection, video_id: int) -> None:
    """Script approved: create scene rows and hand the video to the per-scene stages. Each place collects its set
    changes in story order, and each scene notes how many came before it: the version of the place it's drawn in."""
    video = db.get_video(conn, video_id)
    places = {p["id"]: {**p, "changes": []} for p in json.loads(video["places_json"] or "[]")}
    for s in json.loads(video["script_json"]):
        place = places.get(s.get("place"))
        conn.execute(
            """INSERT INTO scenes (video_id, idx, beat_idx, label, narration, visual_prompt, motion, state,
                                   place, place_v, cast_json, tracker_json, shot)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?, ?)""",
            (video_id, s["idx"], s["beat_idx"], s["label"], s["narration"], s["visual_prompt"], s["motion"],
             s.get("place") if place else None, len(place["changes"]) if place else None,
             json.dumps(s.get("cast") or []), json.dumps(s.get("tracker") or []), s.get("shot")),
        )
        if place and s.get("set_change"):
            place["changes"].append(s["set_change"])
    db.transition(conn, video_id, "scripted", "generating", draft_note=None,
                  places_json=json.dumps(list(places.values())) if places else video["places_json"])


def approve(ctx, video_id: int, gate: str) -> None:
    with ctx.connect() as conn, db.tx(conn):
        if gate == "outline":
            db.transition(conn, video_id, "outlined", "outline_approved", draft_note=None)
        elif gate == "script":
            start_generating(conn, video_id)
        elif gate == "render":
            video = db.get_video(conn, video_id)
            if video["state"] == "assembled" and (video["title"] is None or video["thumb_idx"] is None):
                raise ActionError("pick a title and a thumbnail first")
            db.transition(conn, video_id, "assembled", "render_approved")
        else:
            raise ActionError(f"unknown gate {gate!r}")
    ctx.events.emit("gate_resolved", video_id, gate=gate, outcome="approved")
    if gate == "render":
        ctx.events.emit("gate_reached", video_id, gate="publish")


def revise(ctx, video_id: int, gate: str, note: str) -> None:
    note = (note or "").strip()
    if not note:
        raise ActionError("a revision needs a note saying what to change")
    with ctx.connect() as conn, db.tx(conn):
        if gate == "outline":
            db.transition(conn, video_id, "outlined", "new", draft_note=None)
        elif gate == "script":
            db.transition(conn, video_id, "scripted", "outline_approved", draft_note=None)
        else:
            raise ActionError("only the outline and the script can be revised with a note; flag scenes instead")
        db.add_feedback(conn, video_id, gate, note)
    ctx.events.emit("gate_resolved", video_id, gate=gate, outcome="revised")
    ctx.events.emit("notice", video_id, text=f"Rewriting the {gate} with your note…")


def stop_writing(ctx, video_id: int) -> None:
    """The Stop button while Claude writes an outline or script: cut the call off and go back to the card. A
    revision's note comes back into the card's note box to change (core/stage.py back_to_review)."""
    with ctx.connect() as conn:
        state = db.get_video(conn, video_id)["state"]
    if state not in ("new", "outline_approved"):
        raise ActionError("Claude isn't writing anything for this video right now")
    ctx.stop_writing(video_id)
    ctx.events.emit("notice", video_id, text="Stopping…")


def regenerate(ctx, video_id: int, gate: str) -> None:
    """Write the outline or script again from scratch with the current prompts, keeping every note so far.

    For prompt iteration: no note needed. Inline edits on the waiting card are dropped with the old draft.
    """
    with ctx.connect() as conn, db.tx(conn):
        if gate == "outline":
            db.transition(conn, video_id, "outlined", "new", outline_json=None, draft_note=None)
        elif gate == "script":
            db.transition(conn, video_id, "scripted", "outline_approved", script_json=None, places_json=None,
                          draft_note=None)
        else:
            raise ActionError("only the outline and the script can be regenerated; flag scenes instead")
    ctx.events.emit("gate_resolved", video_id, gate=gate, outcome="regenerated")
    ctx.events.emit("notice", video_id, text=f"Writing a fresh {gate} with the current prompts…")


def _apply_outline_op(outline: dict, op: dict) -> None:
    beats = outline["beats"]

    def beat_index(key: str = "beat") -> int:
        n = int(op.get(key, 0))
        if not 1 <= n <= len(beats):
            raise ActionError(f"there is no beat {n}; the outline has {len(beats)}")
        return n - 1

    kind = op.get("op")
    if kind == "set_hook":
        outline["hook"] = op["text"]
    elif kind == "set_backstory":
        outline["backstory"] = op["text"]
    elif kind == "set_ending":
        outline["ending"] = op["text"]
    elif kind == "edit_beat":
        beat = beats[beat_index()]
        for field in ("label", "title", "summary", "skill", "hero"):
            if field in op:
                beat[field] = op[field]
    elif kind == "cut_beat":
        if len(beats) <= 3:
            raise ActionError("an outline needs at least 3 beats")
        beats.pop(beat_index())
    elif kind == "move_beat":
        beat = beats.pop(beat_index())
        to = max(1, min(int(op["to"]), len(beats) + 1))
        beats.insert(to - 1, beat)
    elif kind == "add_beat":
        after = int(op.get("after", len(beats)))
        beats.insert(max(0, min(after, len(beats))), {
            "label": op.get("label", ""), "title": op.get("title", ""), "summary": op.get("summary", ""),
            "skill": op.get("skill", ""), "hero": bool(op.get("hero", False)), "cast": [],
        })
    else:
        raise ActionError(f"unknown outline edit {kind!r}")


def edit_outline(ctx, video_id: int, ops: list[dict]) -> None:
    """Small inline edits without a full regen. Beat numbers are 1-based, as shown on the card."""
    with ctx.connect() as conn, db.tx(conn):
        video = db.get_video(conn, video_id)
        if video["state"] != "outlined":
            raise ActionError(f"the outline can only be edited while it waits for review (video is {video['state']})")
        outline = json.loads(video["outline_json"])
        for op in ops:
            _apply_outline_op(outline, op)
        db.update_video(conn, video_id, outline_json=json.dumps(outline))
    ctx.events.emit("gate_reached", video_id, gate="outline", repost=True)


def flag_scenes(ctx, video_id: int, idxs: list[int], kind: str, note: str = "") -> None:
    """Gate 2: send scenes back. visual = new still/clip; narration = rewrite the line and re-voice."""
    if kind not in FLAG_KINDS:
        raise ActionError(f"kind must be one of {FLAG_KINDS}")
    note = (note or "").strip()
    if kind == "narration" and not note:
        raise ActionError("say how the line should change")
    if not idxs:
        raise ActionError("no scenes given")
    with ctx.connect() as conn, db.tx(conn):
        video = db.get_video(conn, video_id)
        if video["state"] != "assembled":
            raise ActionError(f"scenes can be flagged at the render review (video is {video['state']})")
        rows = {s["idx"]: s for s in db.scenes_for(conn, video_id)}
        missing = [i for i in idxs if i not in rows]
        if missing:
            raise ActionError(f"no scene {missing[0]}; this video has scenes 1-{len(rows)}")
        stuck = [i for i in idxs if rows[i]["regen_count"] >= MAX_REGENS]
        for i in idxs:
            db.update_scene(conn, rows[i]["id"], state="flagged", flag_kind=kind, flag_note=note or None)
            if note:
                db.add_feedback(conn, video_id, "render", note, scene_id=rows[i]["id"])
        if stuck:
            listed = ", ".join(map(str, stuck))
            db.transition(conn, video_id, "assembled", "blocked", resume_state="generating",
                          error=f"scene {listed} was regenerated {MAX_REGENS} times. Edit its prompt, then Retry.")
        else:
            db.transition(conn, video_id, "assembled", "generating")
    ctx.events.emit("gate_resolved", video_id, gate="render", outcome="flagged")
    if stuck:
        ctx.events.emit("blocked", video_id)


def edit_scene(ctx, video_id: int, idx: int, visual_prompt: str | None = None, narration: str | None = None) -> None:
    """Manual prompt or line edit (the fix for a blocked scene). Regenerates that scene as written."""
    if visual_prompt is None and narration is None:
        raise ActionError("give a new visual_prompt or narration")
    with ctx.connect() as conn, db.tx(conn):
        video = db.get_video(conn, video_id)
        if video["state"] not in ("assembled", "blocked"):
            raise ActionError(f"scenes can be edited at the render review or when blocked (video is {video['state']})")
        scene = conn.execute("SELECT * FROM scenes WHERE video_id = ? AND idx = ?", (video_id, idx)).fetchone()
        if scene is None:
            raise ActionError(f"no scene {idx}")
        fields = {"state": "flagged", "flag_note": None, "regen_count": 0,
                  "flag_kind": "narration" if narration is not None else "visual"}
        if visual_prompt is not None:
            fields["visual_prompt"] = visual_prompt
            if narration is not None:  # the narration path keeps the picture, so drop it to get a new one
                fields.update(still_path=None, clip_path=None)
        if narration is not None:
            fields["narration"] = narration
        db.update_scene(conn, scene["id"], **fields)
        if video["state"] == "assembled":
            db.transition(conn, video_id, "assembled", "generating")
    if video["state"] == "assembled":
        ctx.events.emit("gate_resolved", video_id, gate="render", outcome="flagged")


def pick(ctx, video_id: int, title_idx: int | None = None, thumb_idx: int | None = None, title: str | None = None) -> None:
    with ctx.connect() as conn:
        video = db.get_video(conn, video_id)
        if video["state"] not in ("assembled", "render_approved"):
            raise ActionError(f"titles and thumbnails are picked at the render review (video is {video['state']})")
        thumbs = json.loads(video["thumbs_json"])
        fields = {}
        if title_idx is not None:
            if not 0 <= title_idx < len(thumbs["titles"]):
                raise ActionError(f"there is no title option {title_idx + 1}")
            fields["title"] = thumbs["titles"][title_idx]
        if title is not None:
            fields["title"] = title.strip()
        if thumb_idx is not None:
            if not 0 <= thumb_idx < len(thumbs["thumbs"]):
                raise ActionError(f"there is no thumbnail option {thumb_idx + 1}")
            fields["thumb_idx"] = thumb_idx
        db.update_video(conn, video_id, **fields)
    ctx.events.emit("card_refresh", video_id, kind="render")
    ctx.events.emit("card_refresh", video_id, kind="publish")


def update_publish(ctx, video_id: int, **fields) -> None:
    """Save edits to the publish card (title, description, tags, publish_at, ai_disclosure)."""
    unknown = set(fields) - metadata.EDITABLE
    if unknown:
        raise ActionError(f"can't edit {sorted(unknown)}")
    with ctx.connect() as conn, db.tx(conn):
        video = db.get_video(conn, video_id)
        if video["state"] not in ("assembled", "render_approved"):
            raise ActionError(f"publish details are edited before publishing (video is {video['state']})")
        saved = json.loads(video["publish_json"] or "{}")
        saved.update({k: v for k, v in fields.items() if v is not None})
        updates = {"publish_json": json.dumps(saved)}
        if "publish_at" in saved:
            if float(saved["publish_at"]) < time.time() + 60:
                raise ActionError("the publish time must be in the future")
            updates["publish_at"] = float(saved["publish_at"])
        if "title" in saved:
            updates["title"] = saved["title"]
        db.update_video(conn, video_id, **updates)
    ctx.events.emit("card_refresh", video_id, kind="publish")


def request_publish(ctx, video_id: int, **fields) -> None:
    """The Publish button. Only the server's card endpoint calls this."""
    if fields:
        update_publish(ctx, video_id, **fields)
    with ctx.connect() as conn, db.tx(conn):
        video = db.get_video(conn, video_id)
        if video["state"] != "render_approved":
            raise ActionError(f"publishing needs an approved render (video is {video['state']})")
        live = ctx.config.youtube.get("mode", "stub") == "live"
        if live:
            from youtube import auth
            auth.require_connected(ctx, video["channel_id"])
        meta = metadata.publish_meta(ctx, conn, video)
        metadata.validate(meta)
        if live and float(meta["publish_at"]) < time.time() + metadata.LIVE_LEAD_S:
            raise ActionError("pick a go-public time at least 15 minutes away; the upload takes a while")
        db.transition(conn, video_id, "render_approved", "publishing", title=meta["title"],
                      publish_at=float(meta["publish_at"]), publish_json=json.dumps(meta))
    ctx.events.emit("gate_resolved", video_id, gate="publish", outcome="approved")
    ctx.events.emit("notice", video_id, text="Publishing…")


def show(ctx, video_id: int, card: str) -> None:
    """Post the waiting review card again at the bottom of the thread; the old copy is marked replaced."""
    if card not in CARD_STATES:
        raise ActionError(f"card must be one of {', '.join(CARD_STATES)}")
    with ctx.connect() as conn:
        video = db.get_video(conn, video_id)
    if video["state"] != CARD_STATES[card]:
        raise ActionError(f"no {card} card is waiting (video is {video['state']})")
    ctx.events.emit("gate_reached", video_id, gate=card, repost=True)


def retry(ctx, video_id: int) -> None:
    with ctx.connect() as conn, db.tx(conn):
        video = db.get_video(conn, video_id)
        if video["state"] not in ("failed", "blocked"):
            raise ActionError(f"only failed or blocked videos can be retried (video is {video['state']})")
        conn.execute("UPDATE scenes SET attempts = 0, lease_until = NULL WHERE video_id = ?", (video_id,))
        if video["state"] == "blocked":
            conn.execute("UPDATE scenes SET regen_count = 0 WHERE video_id = ? AND regen_count >= ?",
                         (video_id, MAX_REGENS))
        db.transition(conn, video_id, ("failed", "blocked"), video["resume_state"] or "new", resume_state=None)
    ctx.events.emit("gate_resolved", video_id, gate="error", outcome="retried")


def status(ctx, video_id: int | None = None, channel_id: str | None = None) -> dict:
    with ctx.connect() as conn:
        if video_id is not None:
            video = db.get_video(conn, video_id)
            scenes = conn.execute(
                "SELECT state, COUNT(*) AS n FROM scenes WHERE video_id = ? GROUP BY state", (video_id,)
            ).fetchall()
            topic = conn.execute("SELECT title FROM topics WHERE id = ?", (video["topic_id"],)).fetchone()
            metrics = conn.execute(
                """SELECT after_h, views, avd_seconds, avd_pct, impressions, ctr, subs_gained, simulated FROM metrics
                   WHERE video_id = ? ORDER BY after_h""", (video_id,)).fetchall()
            return {
                "video_id": video_id, "channel": video["channel_id"], "topic": topic["title"] if topic else None,
                "state": video["state"], "cost_usd": round(video["cost_usd"], 2),
                "budget_usd": ctx.channel(video["channel_id"]).budget_usd, "error": video["error"],
                "scenes": {r["state"]: r["n"] for r in scenes}, "youtube_id": video["youtube_id"],
                "publish_at": video["publish_at"], "metrics": [dict(m) for m in metrics],
            }
        sql = """SELECT v.id, v.channel_id, v.state, v.cost_usd, t.title AS topic FROM videos v
                 LEFT JOIN topics t ON t.id = v.topic_id"""
        params: tuple = ()
        if channel_id:
            sql += " WHERE v.channel_id = ?"
            params = (channel_id,)
        rows = conn.execute(sql + " ORDER BY v.id DESC LIMIT 50", params).fetchall()
        return {"videos": [dict(r) for r in rows]}

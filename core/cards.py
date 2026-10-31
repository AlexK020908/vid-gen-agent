"""Turns engine events into chat messages and review cards, stored in `messages`.

A card is a snapshot of what needed review. `card_status` tracks its life:
active → approved / revised / regenerated / flagged / superseded / retried / done.
Topic cards live in a channel's home thread; metrics cards are information and post as done.
"""
from __future__ import annotations

import json
import sqlite3
import time

from core import db, metadata
from core.events import Event
from providers.prompts import amount


def url(rel: str | None) -> str | None:
    return f"/media/{rel}" if rel else None


def preview_url(rel: str | None) -> str | None:
    return url(rel.rsplit(".", 1)[0] + ".thumb.jpg") if rel else None


# --- messages ------------------------------------------------------------------

def to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    raw = d.pop("card_json")
    d["card"] = json.loads(raw) if raw else None
    return d


def thread_id(conn: sqlite3.Connection, video_id: int) -> int:
    return conn.execute("SELECT id FROM threads WHERE video_id = ?", (video_id,)).fetchone()["id"]


def home_thread_id(conn: sqlite3.Connection, channel_id: str) -> int:
    return conn.execute(
        "SELECT id FROM threads WHERE channel_id = ? AND video_id IS NULL", (channel_id,)
    ).fetchone()["id"]


def post(ctx, conn: sqlite3.Connection, thread: int, role: str, text: str | None = None,
         card: dict | None = None, video_id: int | None = None, status: str | None = "active") -> dict:
    """Add a message. Cards start `active` unless `status` says otherwise (tool lines carry no status)."""
    cur = conn.execute(
        """INSERT INTO messages (thread_id, video_id, role, text, card_json, card_status, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (thread, video_id, role, text, json.dumps(card) if card else None, status if card else None, time.time()),
    )
    msg = to_dict(conn.execute("SELECT * FROM messages WHERE id = ?", (cur.lastrowid,)).fetchone())
    ctx.events.emit("message", video_id, message=msg)
    return msg


def _emit_updated(ctx, conn: sqlite3.Connection, message_id: int) -> None:
    msg = to_dict(conn.execute("SELECT * FROM messages WHERE id = ?", (message_id,)).fetchone())
    ctx.events.emit("message_updated", msg["video_id"], message=msg)


def active_cards(conn: sqlite3.Connection, video_id: int, kind: str) -> list[sqlite3.Row]:
    return conn.execute(
        """SELECT * FROM messages WHERE video_id = ? AND card_status = 'active'
           AND json_extract(card_json, '$.kind') = ? ORDER BY id""",
        (video_id, kind),
    ).fetchall()


def set_status(ctx, conn: sqlite3.Connection, video_id: int, kind: str, status: str) -> None:
    for row in active_cards(conn, video_id, kind):
        conn.execute("UPDATE messages SET card_status = ? WHERE id = ?", (status, row["id"]))
        _emit_updated(ctx, conn, row["id"])


def set_message_status(ctx, conn: sqlite3.Connection, message_id: int, status: str) -> None:
    conn.execute("UPDATE messages SET card_status = ? WHERE id = ?", (status, message_id))
    _emit_updated(ctx, conn, message_id)


def update_text(ctx, conn: sqlite3.Connection, message_id: int, text: str) -> None:
    conn.execute("UPDATE messages SET text = ? WHERE id = ?", (text, message_id))
    _emit_updated(ctx, conn, message_id)


def update_card(ctx, conn: sqlite3.Connection, message_id: int, card: dict, text: str | None = None) -> None:
    conn.execute("UPDATE messages SET card_json = ?, text = COALESCE(?, text) WHERE id = ?",
                 (json.dumps(card), text, message_id))
    _emit_updated(ctx, conn, message_id)


# --- card payloads ---------------------------------------------------------------

def _version(conn: sqlite3.Connection, video_id: int, gate: str) -> int:
    """1 + the drafts sent back (with a note, or regenerated)."""
    return 1 + conn.execute(
        """SELECT COUNT(*) FROM messages WHERE video_id = ? AND card_status IN ('revised', 'regenerated')
           AND json_extract(card_json, '$.kind') = ?""",
        (video_id, gate),
    ).fetchone()[0]


def outline_card(ctx, conn: sqlite3.Connection, video: sqlite3.Row) -> dict:
    o = json.loads(video["outline_json"])
    return {
        "kind": "outline", "video_id": video["id"], "version": _version(conn, video["id"], "outline"),
        "topic": o["topic"], "hook": o["hook"], "ending": o["ending"], "draft_note": video["draft_note"],
        "backstory": o.get("backstory", ""), "cast": o.get("cast") or [],
        "tracker": [{**t, "start": amount(t["start"])} for t in o.get("tracker") or []],
        "beats": [{"n": i + 1, **b} for i, b in enumerate(o["beats"])],
    }


def script_card(ctx, conn: sqlite3.Connection, video: sqlite3.Row) -> dict:
    o = json.loads(video["outline_json"])
    script = json.loads(video["script_json"])
    places = {p["id"]: p for p in json.loads(video["places_json"] or "[]")}
    units = {t["item"]: t["unit"] for t in o.get("tracker") or []}
    beats = [{"n": i + 1, "label": b["label"], "title": b["title"], "scenes": []} for i, b in enumerate(o["beats"])]
    for s in script:
        tracker = " · ".join(f"{t['item']} {amount(t['amount'])} {units.get(t['item'], '')}".strip()
                             for t in s.get("tracker") or [])
        beats[s["beat_idx"]]["scenes"].append(
            {"idx": s["idx"], "narration": s["narration"], "visual_prompt": s["visual_prompt"], "motion": s["motion"],
             "place": places[s["place"]]["name"] if s.get("place") in places else None, "cast": s.get("cast") or [],
             "tracker": tracker or None, "set_change": s.get("set_change") or None,
             "looks": "; ".join(f"{lk['who']} now: {lk['now']}" for lk in s.get("looks") or []) or None}
        )
    words = sum(len(s["narration"].split()) for s in script)
    return {
        "kind": "script", "video_id": video["id"], "version": _version(conn, video["id"], "script"),
        "topic": o["topic"], "beats": beats, "scene_count": len(script), "word_count": words,
        "draft_note": video["draft_note"],
        "places": [{"name": p["name"], "look": p["look"]} for p in places.values()],
        "est_minutes": round(words / 145, 1),
    }


def render_card(ctx, conn: sqlite3.Connection, video: sqlite3.Row) -> dict:
    o = json.loads(video["outline_json"])
    thumbs = json.loads(video["thumbs_json"] or '{"titles": [], "thumbs": []}')
    channel = ctx.channel(video["channel_id"])
    scenes = db.scenes_for(conn, video["id"])
    return {
        "kind": "render", "video_id": video["id"], "topic": o["topic"],
        "titles": thumbs["titles"], "thumbs": [url(p) for p in thumbs["thumbs"]],
        "thumb_texts": thumbs.get("texts") or [],  # the words drawn on each thumbnail
        "picked": {"title": video["title"], "thumb_idx": video["thumb_idx"]},
        "video_url": url(video["video_path"]), "highlight_url": url(video["highlight_path"]),
        "duration_ms": video["duration_ms"], "cost_usd": round(video["cost_usd"], 2),
        "budget_usd": channel.budget_usd,
        "scenes": [
            {"idx": s["idx"], "beat": s["beat_idx"] + 1, "label": s["label"], "motion": s["motion"],
             "regen_count": s["regen_count"], "narration": s["narration"], "visual_prompt": s["visual_prompt"],
             "start_ms": s["audio_start_ms"], "still_url": url(s["still_path"]),
             "preview_url": preview_url(s["still_path"])}
            for s in scenes
        ],
    }


def publish_card(ctx, conn: sqlite3.Connection, video: sqlite3.Row) -> dict:
    meta = metadata.publish_meta(ctx, conn, video)
    meta["thumbnail"] = url(meta["thumbnail"])
    mode = ctx.config.youtube.get("mode", "stub")
    connected = None
    if mode == "live":
        from youtube import auth
        connected = auth.status(ctx, video["channel_id"])["connected"]
    return {"kind": "publish", "video_id": video["id"], "youtube_mode": mode, "youtube_connected": connected, **meta}


def _hit(conn: sqlite3.Connection, ref: str) -> dict | None:
    """One thing a topic builds on: a competitor's video, or (for a follow-up) "video:<id>", one of ours."""
    from youtube.competitors import age_days
    if ref.startswith("video:"):
        v = conn.execute("SELECT id, title, youtube_id FROM videos WHERE id = ?", (int(ref[6:]),)).fetchone()
        m = conn.execute("SELECT views FROM metrics WHERE video_id = ? AND after_h = 48", (int(ref[6:]),)).fetchone()
        if not v:
            return None
        real = v["youtube_id"] and not v["youtube_id"].startswith("stub-")
        return {"title": f"#{v['id']} {v['title']}", "channel": "this channel",
                "per_day": round((m["views"] or 0) / 2) if m else 0,
                "url": f"https://youtu.be/{v['youtube_id']}" if real else None}
    v = conn.execute("SELECT * FROM competitor_videos WHERE youtube_id = ?", (ref,)).fetchone()
    if not v:
        return None
    return {"title": v["title"], "channel": v["competitor_name"] or v["competitor_id"],
            "per_day": round(v["views"] / age_days(v["published_at"], v["checked_at"])),
            "url": None if v["simulated"] else f"https://youtu.be/{ref}"}


def topics_card(ctx, conn: sqlite3.Connection, topic_ids: list[int], simulated: bool,
                winner_video_id: int | None = None) -> dict:
    """Topic ideas, each with what it builds on, its family and rank note, and where it stands (queued, used,
    dismissed). `winner_video_id`: the round is follow-ups to that video (the surge)."""
    from core import performance
    rows = conn.execute(f"SELECT * FROM topics WHERE id IN ({','.join('?' * len(topic_ids))}) ORDER BY id",
                        topic_ids).fetchall()
    notes = {t["id"]: t["note"] for t in performance.ranked_topics(conn, rows[0]["channel_id"])} if rows else {}
    topics = []
    for t in rows:
        hits = [h for ref in json.loads(t["based_on"] or "[]") if (h := _hit(conn, ref))]
        video = conn.execute("SELECT id FROM videos WHERE topic_id = ?", (t["id"],)).fetchone()
        topics.append({"id": t["id"], "title": t["title"], "why": t["why"], "status": t["status"],
                       "family": t["family"], "note": notes.get(t["id"]),
                       "video_id": video["id"] if video else None, "based_on": hits})
    return {"kind": "topics", "channel_id": rows[0]["channel_id"] if rows else None, "simulated": simulated,
            "winner_video_id": winner_video_id, "topics": topics}


def metrics_card(ctx, conn: sqlite3.Connection, video: sqlite3.Row, after_h: int) -> dict:
    m = conn.execute("SELECT * FROM metrics WHERE video_id = ? AND after_h = ?", (video["id"], after_h)).fetchone()
    from core import performance
    late_h = (m["captured_at"] - (video["publish_at"] + after_h * 3600)) / 3600
    swap = conn.execute("SELECT * FROM swaps WHERE video_id = ? AND applied_at <= ? ORDER BY id DESC LIMIT 1",
                        (video["id"], m["captured_at"])).fetchone()
    return {"kind": "metrics", "video_id": video["id"], "after_h": after_h, "views": m["views"],
            "avd_seconds": m["avd_seconds"], "avd_pct": m["avd_pct"], "subs_gained": m["subs_gained"],
            "impressions": m["impressions"], "ctr": m["ctr"], "simulated": bool(m["simulated"]),
            "captured_at": m["captured_at"], "late_h": round(late_h) if late_h >= 6 else 0,
            "verdict": m["verdict"], "min_videos": performance.MIN_VIDEOS,
            "medians": {"avd_pct": m["median_avd_pct"], "ctr": m["median_ctr"], "n": m["median_n"]}
            if m["median_n"] else None,
            "swap": {"applied_at": swap["applied_at"], "title": swap["new_title"], "thumb": swap["new_thumb_idx"],
                     "ctr_before": swap["ctr_before"], "ctr_since": performance.swap_since(conn, video, swap)}
            if swap else None}


def swap_card(ctx, conn: sqlite3.Connection, video: sqlite3.Row, reason: str | None = None) -> dict:
    options = json.loads(video["thumbs_json"] or '{"titles": [], "thumbs": []}')
    live = ctx.config.youtube.get("mode", "stub") == "live" and not (video["youtube_id"] or "").startswith("stub-")
    return {"kind": "swap", "video_id": video["id"], "reason": reason, "live": live, "title": video["title"],
            "thumb_idx": video["thumb_idx"], "titles": options["titles"], "thumbs": [url(p) for p in options["thumbs"]],
            "texts": options.get("texts") or []}


def error_card(ctx, conn: sqlite3.Connection, video: sqlite3.Row) -> dict:
    return {"kind": "error", "video_id": video["id"], "state": video["state"],
            "error": video["error"], "resume_state": video["resume_state"]}


BUILDERS = {"outline": outline_card, "script": script_card, "render": render_card,
            "publish": publish_card, "error": error_card}
INTRO = {
    "outline": "Outline ready for review.",
    "script": "Script ready for review.",
    "render": "Render ready: pick a thumbnail and title, flag anything that looks off, then approve.",
    "publish": "Check the publish details, then click Publish.",
}


def build(ctx, conn: sqlite3.Connection, video_id: int, kind: str) -> dict:
    return BUILDERS[kind](ctx, conn, db.get_video(conn, video_id))


# --- event → message mapping --------------------------------------------------------

class CardPoster:
    def __init__(self, ctx) -> None:
        self.ctx = ctx

    def attach(self) -> None:
        self.ctx.events.subscribe(self.handle)

    def handle(self, event: Event) -> None:
        fn = getattr(self, f"on_{event.kind}", None)
        if fn is not None:
            with self.ctx.connect() as conn:
                fn(conn, event)

    def on_video_created(self, conn, ev: Event) -> None:
        video = db.get_video(conn, ev.video_id)
        note = f" ({ev.data['note']})" if ev.data.get("note") else ""
        post(self.ctx, conn, home_thread_id(conn, video["channel_id"]), "system",
             text=f"Started video #{ev.video_id}: {ev.data['title']}{note}", video_id=ev.video_id)
        post(self.ctx, conn, thread_id(conn, ev.video_id), "system", text="Writing the outline…", video_id=ev.video_id)

    def on_gate_reached(self, conn, ev: Event) -> None:
        gate = ev.data["gate"]
        set_status(self.ctx, conn, ev.video_id, gate, "superseded")
        if gate in ("outline", "script", "render"):  # the script's line (also after Stop), or the generation lines
            set_status(self.ctx, conn, ev.video_id, "progress", "done")
        post(self.ctx, conn, thread_id(conn, ev.video_id), "card", text=INTRO[gate],
             card=build(self.ctx, conn, ev.video_id, gate), video_id=ev.video_id)

    def on_gate_resolved(self, conn, ev: Event) -> None:
        set_status(self.ctx, conn, ev.video_id, ev.data["gate"], ev.data["outcome"])
        if ev.data["gate"] == "render" and ev.data["outcome"] == "flagged":
            set_status(self.ctx, conn, ev.video_id, "progress", "done")

    def on_card_refresh(self, conn, ev: Event) -> None:
        for row in active_cards(conn, ev.video_id, ev.data["kind"]):
            update_card(self.ctx, conn, row["id"], build(self.ctx, conn, ev.video_id, ev.data["kind"]))

    def on_stage_progress(self, conn, ev: Event) -> None:
        stage, done, total = ev.data["stage"], ev.data["done"], ev.data["total"]
        cost = ev.data.get("cost_usd")
        unit = ev.data.get("unit")
        card = {"kind": "progress", "video_id": ev.video_id, "stage": stage, "done": done, "total": total,
                "unit": unit, "cost_usd": round(cost, 2) if cost is not None else None}
        text = f"{stage} {done}%" if unit == "%" else f"{stage} {done} {unit}" if unit else f"{stage} {done}/{total}"
        for row in active_cards(conn, ev.video_id, "progress"):
            if json.loads(row["card_json"])["stage"] == stage:
                update_card(self.ctx, conn, row["id"], card, text)
                return
        post(self.ctx, conn, thread_id(conn, ev.video_id), "progress", text=text, card=card, video_id=ev.video_id)

    def on_stage_failed(self, conn, ev: Event) -> None:
        set_status(self.ctx, conn, ev.video_id, "error", "superseded")
        post(self.ctx, conn, thread_id(conn, ev.video_id), "card", text="Something failed and needs you.",
             card=build(self.ctx, conn, ev.video_id, "error"), video_id=ev.video_id)

    on_blocked = on_stage_failed

    def on_notice(self, conn, ev: Event) -> None:
        post(self.ctx, conn, thread_id(conn, ev.video_id), "system", text=ev.data["text"], video_id=ev.video_id)

    def on_topics_proposed(self, conn, ev: Event) -> None:
        ids = ev.data["topic_ids"]
        winner = ev.data.get("winner_video_id")
        card = topics_card(self.ctx, conn, ids, ev.data.get("simulated", False), winner)
        if winner:
            title = db.get_video(conn, winner)["title"]
            made_up = " (made-up numbers: youtube.mode is stub)" if card["simulated"] else ""
            text = (f"#{winner} \"{title}\" is beating this channel's medians 48 hours in{made_up}, so here are "
                    f"{len(ids)} follow-ups, at the top of the queue.")
        else:
            made_up = " (made-up competitor data: topics.competitors is stub)" if card["simulated"] else ""
            text = (f"{len(ids)} topic ideas from what's working for competitors right now{made_up}. Start one to "
                    "write its outline, or dismiss it.")
        msg = post(self.ctx, conn, home_thread_id(conn, ev.data["channel_id"]), "card", text=text, card=card)
        conn.execute(f"UPDATE topics SET message_id = ? WHERE id IN ({','.join('?' * len(ids))})", (msg["id"], *ids))

    def on_topic_changed(self, conn, ev: Event) -> None:
        row = conn.execute("""SELECT m.* FROM topics t JOIN messages m ON m.id = t.message_id
                              WHERE t.id = ?""", (ev.data["topic_id"],)).fetchone()
        if row is None:  # a topic with no card (queued before cards existed)
            return
        old = json.loads(row["card_json"])
        card = topics_card(self.ctx, conn, [t["id"] for t in old["topics"]], old["simulated"],
                           old.get("winner_video_id"))
        update_card(self.ctx, conn, row["id"], card)
        if row["card_status"] == "active" and all(t["status"] != "queued" for t in card["topics"]):
            set_message_status(self.ctx, conn, row["id"], "done")

    def on_metrics(self, conn, ev: Event) -> None:
        video = db.get_video(conn, ev.video_id)
        card = metrics_card(self.ctx, conn, video, ev.data["after_h"])
        span = f"{card['after_h']} hours" if card["after_h"] < 72 else f"{card['after_h'] // 24} days"
        post(self.ctx, conn, thread_id(conn, ev.video_id), "card", text=f"How it's doing {span} after going public.",
             card=card, video_id=ev.video_id, status="done")

    def on_metrics_updated(self, conn, ev: Event) -> None:
        row = conn.execute("""SELECT id FROM messages WHERE video_id = ? AND json_extract(card_json, '$.kind') =
                              'metrics' AND json_extract(card_json, '$.after_h') = ?""",
                           (ev.video_id, ev.data["after_h"])).fetchone()
        if row:
            video = db.get_video(conn, ev.video_id)
            update_card(self.ctx, conn, row["id"], metrics_card(self.ctx, conn, video, ev.data["after_h"]))

    def on_swap_suggested(self, conn, ev: Event) -> None:
        set_status(self.ctx, conn, ev.video_id, "swap", "superseded")
        video = db.get_video(conn, ev.video_id)
        reason = ev.data.get("reason")
        post(self.ctx, conn, thread_id(conn, ev.video_id), "card",
             text=f"{reason + ' ' if reason else ''}Try another of its thumbnails or titles?",
             card=swap_card(self.ctx, conn, video, reason), video_id=ev.video_id)

    def on_swap_applied(self, conn, ev: Event) -> None:
        set_status(self.ctx, conn, ev.video_id, "swap", "approved")
        parts = []
        if "title" in ev.data:
            parts.append(f"the title to \"{ev.data['title']}\"")
        if "thumb_idx" in ev.data:
            parts.append(f"the thumbnail to option {ev.data['thumb_idx'] + 1}")
        where = "on YouTube" if ev.data.get("live") else "(stub: wrote swap_request.json, nothing was sent)"
        post(self.ctx, conn, thread_id(conn, ev.video_id), "system", text=f"Changed {' and '.join(parts)} {where}. "
             "The next reading shows how click-through does since.", video_id=ev.video_id)

    def on_swap_kept(self, conn, ev: Event) -> None:
        set_status(self.ctx, conn, ev.video_id, "swap", "kept")

    def on_published(self, conn, ev: Event) -> None:
        set_status(self.ctx, conn, ev.video_id, "progress", "done")
        when = time.strftime("%a %d %b %Y %H:%M", time.localtime(ev.data["publish_at"]))
        if ev.data.get("live"):
            text = (f"Uploaded as private, scheduled to go public {when}. "
                    f"Studio: https://studio.youtube.com/video/{ev.data['youtube_id']}/edit")
        else:
            text = f"Scheduled on YouTube as {ev.data['youtube_id']} for {when} (stub: nothing was uploaded)."
        post(self.ctx, conn, thread_id(conn, ev.video_id), "system", text=text, video_id=ev.video_id)

    def on_went_live(self, conn, ev: Event) -> None:
        youtube_id = db.get_video(conn, ev.video_id)["youtube_id"] or ""
        text = "Video is live." if youtube_id.startswith("stub-") else f"Video is live: https://youtu.be/{youtube_id}"
        post(self.ctx, conn, thread_id(conn, ev.video_id), "system", text=text, video_id=ev.video_id)

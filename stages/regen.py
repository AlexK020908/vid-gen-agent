"""Flagged scenes from Gate 2. Visual: new still/clip with a prompt tweak. Narration: rewrite + re-voice."""
import json

from core import db
from core.stage import run_scene_stage

NAME = "regen"


def run_once(ctx) -> bool:
    return run_scene_stage(ctx, NAME, "flagged", _work, done_sql="state != 'flagged'")


def _work(ctx, conn, video, scene) -> tuple[dict, str]:
    channel = ctx.channel(video["channel_id"])
    note = scene["flag_note"]
    fields = {"regen_count": scene["regen_count"] + 1, "flag_kind": None, "flag_note": None}
    meter = ctx.meter(conn, video, NAME, f"the fix for scene {scene['idx']}")
    if scene["flag_kind"] == "narration":
        if note:  # no note = the line was edited by hand; use it as written
            fields["narration"] = ctx.llm.rewrite_line(channel, _with_context(conn, video, scene), note, meter)
        fields["audio_path"] = None
        return fields, "pending"  # keeps the still; voice → stills skips → ok
    if note:
        fields["visual_prompt"] = ctx.llm.revise_visual(channel, _with_context(conn, video, scene), note, meter)
    fields.update(still_path=None, clip_path=None)
    return fields, "voiced" if scene["audio_path"] else "pending"


def _with_context(conn, video, scene) -> dict:
    """The scene plus the lines either side of it, so a rewrite still flows, and its place and cast, so a new
    picture prompt stays where the story is (the still is drawn from the same references either way)."""
    before, after = db.neighbors(conn, scene["video_id"], scene["idx"])
    place = next((p for p in json.loads(video["places_json"] or "[]") if p["id"] == scene["place"]), None)
    return {**dict(scene), "before": before, "after": after,
            "place_text": f"{place['name']}: {place['look']}" if place else None,
            "cast_text": ", ".join(json.loads(scene["cast_json"] or "[]")) or None}

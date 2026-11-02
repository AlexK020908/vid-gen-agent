"""Stage 5b (puppet pictures): one scene sheet per scene, written by Claude in scene order. Each is a job for the
Claude Code session (its worker agent); the scene waits for it, holding its place, and the next scene's job comes
once it's answered.

Each sheet (puppet/sheet.py) says who stands where doing what from when to when, what stands in the place,
the camera and the light, from the scene's line (with each word's time), its visual prompt, the stage's spots,
the people in it and the props. It is written with the scene before it in hand: where everyone ended and what
stood in the place, so people and things carry over. The sheet is checked in code against the stage before
it's kept (a spot or a pose that doesn't exist sends it back to Claude with what was wrong), and the set
state after the scene is kept on the scene for the next one. Runs only when render.pictures is `puppet`.
"""
import json

from core import series
from core.stage import run_scene_stage
from providers import checks
from puppet import props, sheet as sheets
from puppet.stage import Stage
from stages.assets import puppet_mode, written_scenes

NAME = "sheets"


def run_once(ctx) -> bool:
    if not puppet_mode(ctx):
        return False
    return run_scene_stage(ctx, NAME, "voiced", _work, done_sql="sheet_json IS NOT NULL", limit=1,
                           where="AND v.assets_json IS NOT NULL")


def _work(ctx, conn, video, scene) -> tuple[dict, str]:
    channel = ctx.channel(video["channel_id"])
    assets = json.loads(video["assets_json"])
    places = {p["id"]: p for p in json.loads(video["places_json"] or "[]")}
    place_id = scene["place"] or next(iter(places), "")
    try:
        stage = Stage.load(assets["stages"][place_id])
    except KeyError:
        raise ValueError(f"scene {scene['idx']} happens in {place_id!r}, which has no stage map") from None
    people = list(json.loads(scene["cast_json"] or "[]"))
    if checks.HERO in scene["visual_prompt"].lower() or not people:
        people.insert(0, checks.HERO)
    library = props.load_library(assets["props"])
    before = conn.execute("SELECT sheet_json, set_json FROM scenes WHERE video_id = ? AND idx = ?",
                          (scene["video_id"], scene["idx"] - 1)).fetchone()
    state = json.loads(before["set_json"]) if before and before["set_json"] else {}
    previous = "(this is the first scene)"
    if before and before["sheet_json"]:
        previous = sheets.summary(json.loads(before["sheet_json"]), state.get(place_id) or {})
    written = next((s for s in written_scenes(video) if s.get("idx") == scene["idx"]), {})
    looks = "; ".join(f"{who}: {chain[-1]}" for who, chain in series.looks_of(scene).items())
    values = {
        "idx": scene["idx"], "label": scene["label"], "shot": scene["shot"] or "medium",
        "duration_ms": scene["duration_ms"], "place_name": places.get(place_id, {}).get("name", place_id),
        "words": sheets.words_text(json.loads(scene["words_json"] or "[]")) or scene["narration"],
        "visual_prompt": scene["visual_prompt"],
        "set_change": f"The line changes the place for good: {written['set_change']}" if written.get("set_change") else "",
        "looks": f"What people have on: {looks}" if looks else "",
        "people": ", ".join(people), "stage": sheets.stage_text(stage),
        "props": ", ".join(sorted(library.parts)) or "none", "poses": ", ".join(sheets.rig.POSES),
        "cycles": ", ".join(sheets.rig.CYCLES), "previous": previous,
        "state": "; ".join(f"{prop} at {p.get('at')}" for prop, p in (state.get(place_id) or {}).items()) or "nothing",
    }
    context = {"spots": list(stage.spots), "people": people, "props": sorted(library.parts),
               "duration_ms": scene["duration_ms"], "set_change": written.get("set_change", ""),
               "narration": scene["narration"]}
    written_sheet = ctx.llm.scene_sheet(
        channel, values, context, lambda d: sheets.check(d, stage, people, sorted(library.parts), scene["duration_ms"]),
        ctx.meter(conn, video, NAME, f"the sheet for scene {scene['idx']}", scene["id"]))
    after = sheets.after(written_sheet, state, place_id)
    return {"sheet_json": json.dumps(written_sheet), "set_json": json.dumps(after)}, "staged"

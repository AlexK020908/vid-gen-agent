"""Stage 5c (puppet pictures): every scene animated by code from its sheet, as a clip the length of its line.

puppet/animate.py draws the frames (the stage picture, the props standing in it, the puppets moving, the
light, the camera) and ffmpeg encodes them with the scene's narration. The first frame is kept as the scene's
still (for the render card's contact sheet) and the scene becomes a `clip` scene for the assembly, which
plays it once and holds its last frame through the pause after the line. Scenes render in parallel; nothing
here costs money. Runs only when render.pictures is `puppet`.
"""
import json

from core import series
from core.stage import run_scene_stage
from providers.images import make_preview
from puppet import animate, parts, props, sheet as sheets, state
from puppet.stage import Stage
from stages.assets import puppet_mode

NAME = "animate"


def run_once(ctx) -> bool:
    if not puppet_mode(ctx):
        return False
    return run_scene_stage(ctx, NAME, "staged", _work, done_sql="clip_path IS NOT NULL")


def _work(ctx, conn, video, scene) -> tuple[dict, str]:
    assets = json.loads(video["assets_json"])
    places = {p["id"]: p for p in json.loads(video["places_json"] or "[]")}
    place_id = scene["place"] or next(iter(places), "")
    stage = Stage.load(assets["stages"][place_id])
    looks = {sheets.who_key(who): chain[-1] for who, chain in series.looks_of(scene).items()}
    puppets = {key: parts.Puppet.load(folder).wearing(looks.get(key, "")) for key, folder in assets["puppets"].items()}
    library = props.load_library(assets["props"])
    written = json.loads(scene["sheet_json"])
    placements = state.placements(json.loads(scene["set_json"] or "{}"), place_id)
    fps = int(ctx.config.render.get("puppet_fps", 30))
    scene_sheet = sheets.resolve(written, stage, puppets, library, placements, scene["duration_ms"], fps)
    out = ctx.media(video["id"]) / "clips" / f"s{scene['idx']:03d}_r{scene['regen_count']}.mp4"
    still = ctx.media(video["id"]) / "stills" / f"s{scene['idx']:03d}_r{scene['regen_count']}.png"
    drawing = animate.Scene(scene_sheet)
    drawing.frame(0).save(still)
    make_preview(still)
    drawing.render(out, ctx.abs(scene["audio_path"]))
    return {"clip_path": ctx.rel(out), "still_path": ctx.rel(still), "motion": "clip"}, "ok"

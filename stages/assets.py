"""Stage 5a (puppet pictures): everything the scene sheets and the animator need, made once per video.

Runs only when render.pictures is `puppet` (stickfleet.yaml), after the voice. For each place of the script it
draws the place's picture (the same picture the stills pipeline draws, stages/stills.py _place) and has the
check model map it into a stage (puppet/stage.py: the floor, the spots, the light, what's in the foreground).
It builds the main character's puppet once per channel (channels/<id>/puppet/hero/) and each cast member's
once per video (media/<video>/puppets/<slug>/) from their cast picture, and asks Claude which props the script
uses (prompts/inventory.md); props already in the channel's library (channels/<id>/props/) are reused, the
rest are painted on one sheet and cut into it. What was made is written to videos.assets_json, and the sheets
stage then takes the video's scenes.
"""
import json
import logging
import shutil
from pathlib import Path

from core import db
from core.stage import run_video_stage
from puppet import parts, props
from puppet.stage import Stage, grid, overlay
from stages import stills

log = logging.getLogger("stickfleet.assets")

NAME = "assets"
READY = "AND assets_json IS NULL AND EXISTS (SELECT 1 FROM scenes s WHERE s.video_id = videos.id AND s.state = 'voiced')"
CAST_PARTS = {
    "head": "the head alone: the round white head with whatever it wears on it (a cap, a hood, hair), its eyes, "
            "eyebrows and calm mouth, cut off at the bottom of the chin, no neck, nothing around the neck",
    "head_side": parts.HEAD_SIDE,
    "shirt": "what they wear on the torso alone (a shirt, a jacket, a hoodie, a vest), as it hangs when worn, with "
             "nothing inside it: no neck stick, no arms",
}


def puppet_mode(ctx) -> bool:
    return str(ctx.config.render.get("pictures", "generative")).lower() == "puppet"


def run_once(ctx) -> bool:
    if not puppet_mode(ctx):
        return False
    return run_video_stage(ctx, NAME, "generating", _work, where=READY)


def _work(ctx, conn, video) -> None:
    channel = ctx.channel(video["channel_id"])
    outline = json.loads(video["outline_json"] or "{}")
    places = json.loads(video["places_json"] or "[]")
    assets = {"stages": {}, "puppets": {}, "props": str(props_dir(ctx, channel))}
    for spot in places:
        picture = stills._place(ctx, conn, video, channel, spot, 0)
        assets["stages"][spot["id"]] = str(_stage(ctx, conn, video, channel, spot, picture))
    assets["puppets"]["hero"] = str(_hero(ctx, conn, video, channel))
    inventory = ctx.llm.inventory(channel, _cast_text(outline), _script_text(conn, video, places),
                                  sorted(props.load_library(props_dir(ctx, channel)).parts),
                                  ctx.meter(conn, video, NAME, "the props list"))
    scales = {p["name"].lower(): float(p["scale"]) for p in inventory.get("people") or []}
    for member in outline.get("cast") or []:
        assets["puppets"][parts.slug(member["name"])] = str(
            _cast_puppet(ctx, conn, video, channel, member, scales.get(member["name"].lower(), 1.0)))
    _props(ctx, conn, video, channel, inventory.get("props") or [])
    db.update_video(conn, video["id"], assets_json=json.dumps(assets))
    ctx.events.emit("stage_progress", video["id"], stage=NAME, done=1, total=1,
                    cost_usd=db.get_video(conn, video["id"])["cost_usd"])


def props_dir(ctx, channel) -> Path:
    return ctx.config.data_dir / "channels" / channel.id / "props"


def _stage(ctx, conn, video, channel, spot: dict, picture: Path) -> Path:
    out = picture.with_suffix(".stage.json")
    if out.exists():
        return out
    gridded = grid(picture, picture.with_suffix(".grid.jpg"))
    data = ctx.llm.map_stage(channel, spot["name"], gridded, ctx.meter(conn, video, NAME, f"the map of {spot['name']}"))
    stage = Stage.from_percent(picture, data)
    stage.save(out)
    overlay(stage, picture.with_suffix(".map.jpg"))
    return out


def _hero(ctx, conn, video, channel) -> Path:
    folder = ctx.config.data_dir / "channels" / channel.id / "puppet" / "hero"
    if (folder / "puppet.json").exists():
        return folder
    wanted = channel.puppet or parts.HERO_PARTS
    return _puppet(ctx, conn, video, channel, folder, Path(channel.character_ref), wanted, 1.0, "the main character")


def _cast_puppet(ctx, conn, video, channel, member: dict, scale: float) -> Path:
    folder = ctx.media(video["id"]) / "puppets" / parts.slug(member["name"])
    if (folder / "puppet.json").exists():
        return folder
    picture = stills._person(ctx, conn, video, channel, member)
    return _puppet(ctx, conn, video, channel, folder, picture, CAST_PARTS, scale, member["name"])


def _puppet(ctx, conn, video, channel, folder: Path, reference: Path, wanted: dict, scale: float, who: str) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    sheet = folder / "sheet.png"
    if not sheet.exists():
        with ctx.reserve(conn, video, ctx.images.still_price, f"the parts of {who}", "images"):
            usd = ctx.images.sheet(channel, reference, parts.items_text(wanted), sheet)
            ctx.log_cost(conn, video["id"], NAME, "images", usd)
    meter = ctx.meter(conn, video, NAME, f"naming the parts of {who}")
    try:
        parts.build(sheet, folder, list(wanted), lambda pic, names: ctx.llm.name_parts(channel, pic, names, meter),
                    scale=scale)
    except ValueError as e:
        if "head" not in str(e).replace("head_side", ""):   # no shirt is fine; a head there must be
            parts.build(sheet, folder, [n for n in wanted if n.startswith("head")],
                        lambda pic, names: ctx.llm.name_parts(channel, pic, names, meter), scale=scale)
        else:
            raise
    return folder


def _props(ctx, conn, video, channel, wanted: list[dict]) -> None:
    folder = props_dir(ctx, channel)
    have = props.load_library(folder)
    new = [p for p in wanted if p["name"] not in have.parts]
    if not new:
        return
    specs = {p["name"]: {"draw": p["draw"], "height": float(p["height"]),
                         "pivot": props.PIVOT_OF.get(p.get("stands"), (0.5, 0.5))} for p in new}
    sheet = ctx.media(video["id"]) / "props" / "sheet.png"
    sheet.parent.mkdir(parents=True, exist_ok=True)
    with ctx.reserve(conn, video, ctx.images.still_price, "the props sheet", "images"):
        usd = ctx.images.sheet(channel, Path(channel.character_ref), props.items_text(list(specs), specs), sheet,
                               file="props.md")
        ctx.log_cost(conn, video["id"], NAME, "images", usd)
    meter = ctx.meter(conn, video, NAME, "naming the props")
    made = props.build(sheet, sheet.parent / "cut", list(specs),
                       lambda pic, names: ctx.llm.name_parts(channel, pic, names, meter), specs)
    props.add_to_library(folder, made)
    shutil.copyfile(sheet, folder / f"sheet_v{video['id']}.png")


def _cast_text(outline: dict) -> str:
    return "\n".join(f"- {c['name']}: {c['look']}" for c in outline.get("cast") or []) or "(nobody besides the main character)"


def _script_text(conn, video, places: list[dict]) -> str:
    names = {p["id"]: p["name"] for p in places}
    changes = {s["idx"]: s.get("set_change") for s in written_scenes(video) if s.get("set_change")}
    lines = []
    for s in db.scenes_for(conn, video["id"]):
        who = ", ".join(json.loads(s["cast_json"] or "[]")) or "nobody from the cast"
        line = f"{s['idx']}. [{names.get(s['place'], s['place'] or '?')}; {who}] {s['narration']} | shows: {s['visual_prompt']}"
        if changes.get(s["idx"]):
            line += f" | changes the place: {changes[s['idx']]}"
        lines.append(line)
    return "\n".join(lines)


def written_scenes(video) -> list[dict]:
    """The script's scenes as written (videos.script_json: the list, or {places, scenes} in older rows)."""
    script = json.loads(video["script_json"] or "[]")
    return script if isinstance(script, list) else list(script.get("scenes") or [])

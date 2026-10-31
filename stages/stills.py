"""Stage 5: one still per scene, drawn from fixed reference pictures so the video stays consistent.

Every still gets the channel's character reference. A wide or medium shot also gets its place's reference
picture (the image model keeps that picture's viewpoint, so a close-up gets the place in words instead, or
it pastes the whole room in behind), and each cast member in it (up to REFS_PER_STILL) their own; the rest
are described in words. These references are drawn here the first time a scene needs them, under a lock so parallel scenes
wait for one picture instead of each drawing their own, and kept in media/<video>/sets/.

A place the story changes for good (a scene's set_change) gets a new version drawn from the version before
it, so the barricade built on Day 2 is still in the picture on Day 30. Each scene is drawn in the version
it comes after (scenes.place_v). The file names carry a hash of what each picture was drawn from, so a
changed description draws a fresh one. Scripts from before places existed draw from the character alone.
"""
import hashlib
import json
import re
import threading

from core.stage import run_scene_stage
from providers.images import make_preview

NAME = "stills"
SETS = "sets"         # the stage name the reference pictures' cost is logged under
REFS_PER_STILL = 2    # cast reference pictures sent with one still, besides the character and the place

_locks: dict[tuple, threading.Lock] = {}
_locks_guard = threading.Lock()


def run_once(ctx) -> bool:
    return run_scene_stage(ctx, NAME, "voiced", _work, done_sql="still_path IS NOT NULL")


def _work(ctx, conn, video, scene) -> tuple[dict, str]:
    existing = ctx.abs(scene["still_path"])
    if existing and existing.exists():  # narration-only regen keeps its picture
        return {}, "still_done"
    channel = ctx.channel(video["channel_id"])
    place, people = _references(ctx, conn, video, channel, scene)
    out = ctx.media(video["id"]) / "stills" / f"s{scene['idx']:03d}_r{scene['regen_count']}.png"
    with ctx.reserve(conn, video, ctx.images.still_price, f"still for scene {scene['idx']}", "images"):
        usd = ctx.images.still(channel, scene["visual_prompt"], f"{scene['label']} · scene {scene['idx']}", out,
                               place=place, people=people)
        ctx.log_cost(conn, video["id"], NAME, "images", usd)
    make_preview(out)
    return {"still_path": ctx.rel(out)}, "still_done"


def _references(ctx, conn, video, channel, scene) -> tuple[tuple | None, list[tuple]]:
    """(name, look, picture or None) for the place, or None, and the same for each cast member in the scene."""
    places = {p["id"]: p for p in json.loads(video["places_json"] or "[]")}
    spot = places.get(scene["place"])
    place = None
    if spot:
        drawn = _place(ctx, conn, video, channel, spot, scene["place_v"] or 0) if scene["shot"] != "close-up" else None
        place = (spot["name"], spot["look"], drawn)
    cast = {c["name"]: c for c in json.loads(video["outline_json"]).get("cast") or []}
    people = []
    for name in json.loads(scene["cast_json"] or "[]"):
        member = cast.get(name)
        if member:
            drawn = _person(ctx, conn, video, channel, member) if len(people) < REFS_PER_STILL else None
            people.append((member["name"], member["look"], drawn))
    return place, people


def _place(ctx, conn, video, channel, spot: dict, version: int):
    """The place's picture after `version` of its set changes. Versions not drawn yet are drawn in order, each
    from the one before."""
    changes = spot.get("changes") or []
    with _lock(video["id"], "place", spot["id"]):
        made, recipe = None, [channel.style_prompt, spot["look"]]
        for v in range(min(version, len(changes)) + 1):
            if v:
                recipe.append(changes[v - 1])
            out = ctx.media(video["id"]) / SETS / f"place_{_slug(spot['id'])}_v{v}_{_digest(recipe)}.png"
            if not out.exists():
                what = f"the picture of {spot['name']}" + (f" after change {v}" if v else "")
                with ctx.reserve(conn, video, ctx.images.still_price, what, "images"):
                    usd = (ctx.images.change_place(channel, made, changes[v - 1], out) if v
                           else ctx.images.place(channel, spot["name"], spot["look"], out))
                    ctx.log_cost(conn, video["id"], SETS, "images", usd)
            made = out
        return made


def _person(ctx, conn, video, channel, member: dict):
    out = (ctx.media(video["id"]) / SETS /
           f"person_{_slug(member['name'])}_{_digest([channel.style_prompt, member['look']])}.png")
    with _lock(video["id"], "person", member["name"]):
        if not out.exists():
            with ctx.reserve(conn, video, ctx.images.still_price, f"the picture of {member['name']}", "images"):
                usd = ctx.images.person(channel, member["name"], member["look"], out)
                ctx.log_cost(conn, video["id"], SETS, "images", usd)
    return out


def _lock(*key) -> threading.Lock:
    with _locks_guard:
        return _locks.setdefault(key, threading.Lock())


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or "x"


def _digest(parts: list[str]) -> str:
    return hashlib.sha1("\n".join(parts).encode("utf-8")).hexdigest()[:8]

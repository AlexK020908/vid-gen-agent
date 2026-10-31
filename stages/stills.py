"""Stage 5: one still per scene, drawn from fixed reference pictures so the video stays consistent.

A still gets the main character's reference only when its visual prompt shows them ("the stick figure"):
sent with every still, it put them into street shots and over other characters. A wide or medium shot also
gets its place's reference picture (the image model keeps that picture's viewpoint, so a close-up gets the
place in words instead, or it pastes the whole room in behind), and each cast member in it (up to
REFS_PER_STILL) their own; the rest are described in words. Someone whose look has changed (body armor on, a
bandage, a borrowed cap; scenes.looks_json) is sent as their reference redrawn with it, once per look. These references are drawn here the first time a scene needs them, under a lock so parallel scenes
wait for one picture instead of each drawing their own, and kept in media/<video>/sets/.

A place the story changes for good (a scene's set_change) gets a new version drawn from the version before
it, so the barricade built on Day 2 is still in the picture on Day 30. Each scene is drawn in the version
it comes after (scenes.place_v). The file names carry a hash of what each picture was drawn from, so a
changed description draws a fresh one, and a next part copies the earlier parts' pictures instead of drawing
them again (the same names, since its places, cast looks and looks continue word for word). Scripts from
before places existed draw from the character alone.
"""
import hashlib
import json
import re
import shutil
import threading
from pathlib import Path

from core import series
from core.stage import run_scene_stage
from providers import checks
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
    hero, place, people = _references(ctx, conn, video, channel, scene)
    out = ctx.media(video["id"]) / "stills" / f"s{scene['idx']:03d}_r{scene['regen_count']}.png"
    with ctx.reserve(conn, video, ctx.images.still_price, f"still for scene {scene['idx']}", "images"):
        usd = ctx.images.still(channel, scene["visual_prompt"], f"{scene['label']} · scene {scene['idx']}", out,
                               place=place, people=people, hero=hero)
        ctx.log_cost(conn, video["id"], NAME, "images", usd)
    make_preview(out)
    return {"still_path": ctx.rel(out)}, "still_done"


def _references(ctx, conn, video, channel, scene) -> tuple[tuple | None, tuple | None, list[tuple]]:
    """The main character as (what they have on now, their picture), or None when the picture doesn't show them;
    (name, look, picture or None) for the place, or None; and the same as the place for each cast member."""
    looks = series.looks_of(scene)
    hero = None
    if checks.HERO in scene["visual_prompt"].lower():
        chain = looks.get(checks.HERO)
        hero = (chain[-1], _dressed(ctx, conn, video, channel, checks.HERO, Path(channel.character_ref), chain)) \
            if chain else (None, None)
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
            chain = looks.get(member["name"])
            drawn = None
            if len(people) < REFS_PER_STILL:
                drawn = _person(ctx, conn, video, channel, member)
                if chain:
                    drawn = _dressed(ctx, conn, video, channel, member["name"], drawn, chain)
            people.append((member["name"], f"{member['look']}, now with {chain[-1]}" if chain else member["look"],
                           drawn))
    return hero, place, people


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
            if not _from_earlier(ctx, conn, video, out):
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
        if not _from_earlier(ctx, conn, video, out):
            with ctx.reserve(conn, video, ctx.images.still_price, f"the picture of {member['name']}", "images"):
                usd = ctx.images.person(channel, member["name"], member["look"], out)
                ctx.log_cost(conn, video["id"], SETS, "images", usd)
    return out


def _dressed(ctx, conn, video, channel, who: str, base: Path, chain: list[str]) -> Path:
    """`who`'s reference as of the newest of `chain` (their looks so far, oldest first). Each look is drawn from
    the one before it, so the brace taped on Day 2 is the same brace wrapped on Day 9; each is drawn once and
    reused whenever they look that way again."""
    made, recipe = base, [base.name, str(base.stat().st_mtime_ns)]  # mtime: a replaced reference draws again
    with _lock(video["id"], "look", who):
        for now in chain:
            recipe.append(now)
            out = ctx.media(video["id"]) / SETS / f"look_{_slug(who)}_{_digest(recipe)}.png"
            if not _from_earlier(ctx, conn, video, out):
                with ctx.reserve(conn, video, ctx.images.still_price, f"the picture of {who} with {now}", "images"):
                    usd = ctx.images.change_look(channel, made, now, out)
                    ctx.log_cost(conn, video["id"], SETS, "images", usd)
            made = out
    return made


def _from_earlier(ctx, conn, video, out: Path) -> bool:
    """True if `out` exists, copying it from an earlier part of the series if one drew it."""
    if out.exists():
        return True
    for part in reversed(series.earlier_parts(conn, video)):
        drawn = ctx.media(part["id"]) / SETS / out.name
        if drawn.exists():
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(drawn, out)
            return True
    return False


def _lock(*key) -> threading.Lock:
    with _locks_guard:
        return _locks.setdefault(key, threading.Lock())


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or "x"


def _digest(parts: list[str]) -> str:
    return hashlib.sha1("\n".join(parts).encode("utf-8")).hexdigest()[:8]

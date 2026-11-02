"""Stage 5: one still per scene, drawn in order from fixed reference pictures and the picture before it, and
looked at by a vision model before the next one is drawn.

A still gets the main character's reference only when its visual prompt shows them ("the stick figure"):
sent with every still, it put them into street shots and over other characters. A wide or medium shot also
gets its place's reference picture (the image model keeps that picture's viewpoint, so a close-up gets the
place in words instead, or it pastes the whole room in behind), and each cast member in it (up to
REFS_PER_STILL) their own; the rest are described in words. Someone whose look has changed (body armor on, a
bandage, a borrowed cap; scenes.looks_json) is sent as their reference redrawn with it, once per look. These
references are drawn here the first time a scene needs them, under a lock so parallel scenes wait for one
picture instead of each drawing their own, and kept in media/<video>/sets/.

The stills are drawn one at a time in scene order (run_scene_stage's limit of 1), and a scene that carries
straight on from the one before it (the same place on the same day) is drawn with that scene's still as one
more reference, the moment just before it: so poses, light and who holds what carry over, and a close-up
happens in the same room as the wide shot before it. Drawn separately and in parallel, the pictures of one
continuous moment came out as unrelated compositions (video 3's break-in), and consecutive close-ups as
different rooms.

Every still, set change and look picture is then checked (ctx.llm.check_picture, prompts/picture.md): a
vision model looks at it against the scene's line and description, who's in it and what they have on, and
the picture before it, and lists what a viewer would see is wrong. A picture with problems is drawn once more
with them named (the {fix} paragraph of still.md, place_change.md and person_change.md); if the second try
still has problems it's kept and they're posted in the thread, so the person can flag the scene from the
render card. The image model gets about one picture in ten wrong (a towel beside the knee it should press on,
a midnight scene by day, a pickup drawn as a sedan), and nothing caught it before. A check costs about a
cent, logged as stage `check`.

A place the story changes for good (a scene's set_change) gets a new version drawn from the version before
it, so the barricade built on Day 2 is still in the picture on Day 30. Each scene is drawn in the version
it comes after (scenes.place_v). The file names carry a hash of what each picture was drawn from, so a
changed description draws a fresh one, and a next part copies the earlier parts' pictures instead of drawing
them again (the same names, since its places, cast looks and looks continue word for word). Scripts from
before places existed draw from the character alone.
"""
import hashlib
import json
import logging
import re
import shutil
import threading
from pathlib import Path

from core import series
from core.costs import BudgetExceeded
from core.stage import run_scene_stage
from providers import checks
from providers.images import make_preview

log = logging.getLogger("stickfleet.stills")

NAME = "stills"
SETS = "sets"         # the stage name the reference pictures' cost is logged under
CHECK = "check"       # the stage name the picture checks' cost is logged under
REFS_PER_STILL = 2    # cast reference pictures sent with one still, besides the character and the place

_locks: dict[tuple, threading.Lock] = {}
_locks_guard = threading.Lock()


def run_once(ctx) -> bool:
    if str(ctx.config.render.get("pictures", "generative")).lower() == "puppet":  # stages/sheets.py takes them
        return False
    return run_scene_stage(ctx, NAME, "voiced", _work, done_sql="still_path IS NOT NULL", limit=1)  # in order


def _work(ctx, conn, video, scene) -> tuple[dict, str]:
    existing = ctx.abs(scene["still_path"])
    if existing and existing.exists():  # narration-only regen keeps its picture
        return {}, "still_done"
    channel = ctx.channel(video["channel_id"])
    hero, place, people = _references(ctx, conn, video, channel, scene)
    previous = _previous(ctx, conn, scene)
    out = ctx.media(video["id"]) / "stills" / f"s{scene['idx']:03d}_r{scene['regen_count']}.png"

    def draw(fix: str) -> None:
        with ctx.reserve(conn, video, ctx.images.still_price, f"still for scene {scene['idx']}", "images"):
            usd = ctx.images.still(channel, scene["visual_prompt"], f"{scene['label']} · scene {scene['idx']}", out,
                                   place=place, people=people, hero=hero, previous=previous, fix=fix)
            ctx.log_cost(conn, video["id"], NAME, "images", usd)

    before = conn.execute("SELECT narration FROM scenes WHERE video_id = ? AND idx = ?",
                          (scene["video_id"], scene["idx"] - 1)).fetchone()
    pictures = [Path(channel.character_ref), *([previous] if previous else []), out]
    images = ["Image 1 is the main character's reference picture."]
    if previous:
        images.append("Image 2 is the moment before this scene, as it was drawn.")
    images.append(f"Image {len(pictures)} is the new picture to check.")
    values = {"idx": scene["idx"], "label": scene["label"], "shot": scene["shot"], "narration": scene["narration"],
              "before": before["narration"] if before else "(this is the first scene)",
              "visual_prompt": scene["visual_prompt"], "people": _who(hero, people), "images": " ".join(images)}
    _checked(ctx, conn, video, channel, f"scene {scene['idx']}", draw, "still", values, pictures,
             "Flag it on the render card to draw it again with a note.")
    make_preview(out)
    return {"still_path": ctx.rel(out)}, "still_done"


def _checked(ctx, conn, video, channel, what: str, draw, turn: str, values: dict, pictures: list[Path],
             advice: str = "") -> list[str]:
    """Draw, look, and draw once more naming what was wrong when the first try had problems; of the two drawings,
    the one that checked better is kept (a redraw can lose what was right). What's still wrong is posted in the
    thread. A check the budget can't cover is skipped."""
    out = pictures[-1]
    draw("")
    meter = ctx.meter(conn, video, CHECK, f"the check of {what}")
    first = out.with_name(f"{out.stem}.first{out.suffix}")
    try:
        problems = ctx.llm.check_picture(channel, turn, values, pictures, meter)
        if problems:
            log.info("%s: drawing again; the check found: %s", what, problems)
            shutil.copyfile(out, first)
            draw("; ".join(problems))
            again = ctx.llm.check_picture(channel, turn, values, pictures, meter)
            if len(again) > len(problems):
                log.info("%s: the redraw checked worse (%s); keeping the first drawing", what, again)
                shutil.copyfile(first, out)
            else:
                problems = again
    except BudgetExceeded as e:
        ctx.events.emit("notice", video["id"], text=f"The picture for {what} wasn't checked: {e}")
        return []
    finally:
        first.unlink(missing_ok=True)
    if problems:
        said = " ".join(p if p.endswith((".", "!", "?")) else p + "." for p in problems)
        ctx.events.emit("notice", video["id"], text=f"The picture for {what} still looks wrong after a second "
                                                    f"drawing: {said} {advice}".rstrip())
    return problems


def _previous(ctx, conn, scene) -> Path | None:
    """The still of the scene before this one when this one carries straight on from it (the same place on the
    same day) and it has been drawn; None otherwise, and the scene is drawn from the references alone."""
    row = conn.execute("SELECT place, label, still_path FROM scenes WHERE video_id = ? AND idx = ?",
                       (scene["video_id"], scene["idx"] - 1)).fetchone()
    if row is None or (row["place"], row["label"]) != (scene["place"], scene["label"]):
        return None
    path = ctx.abs(row["still_path"])
    return path if path and path.exists() else None


def _who(hero, people) -> str:
    """Who the check should see in the picture and what they have on, from the references the still was drawn with."""
    who = ([f"{checks.HERO} (the main character)" + (f": {hero[0]}" if hero[0] else "")] if hero is not None
           else ["the main character is not in it"])
    who += [f"{name}: {look}" for name, look, _ in people]
    return "; ".join(who)


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
    from the one before, and each change is checked against its words."""
    changes = spot.get("changes") or []
    with _lock(video["id"], "place", spot["id"]):
        made, recipe = None, [channel.style_prompt, spot["look"]]
        for v in range(min(version, len(changes)) + 1):
            if v:
                recipe.append(changes[v - 1])
            out = ctx.media(video["id"]) / SETS / f"place_{_slug(spot['id'])}_v{v}_{_digest(recipe)}.png"
            if not _from_earlier(ctx, conn, video, out):
                if v:
                    before, change, what = made, changes[v - 1], f"{spot['name']} after change {v}"

                    def draw(fix: str) -> None:
                        with ctx.reserve(conn, video, ctx.images.still_price, f"the picture of {what}", "images"):
                            usd = ctx.images.change_place(channel, before, change, out, fix=fix)
                            ctx.log_cost(conn, video["id"], SETS, "images", usd)

                    _checked(ctx, conn, video, channel, what, draw, "change",
                             {"what": f"This should be {spot['name']} after a change that lasts: {change} The place "
                                      f"before the change: {spot['look']}",
                              "images": "Image 1 is the place before the change; image 2 is the new picture to "
                                        "check."}, [before, out])
                else:
                    with ctx.reserve(conn, video, ctx.images.still_price, f"the picture of {spot['name']}", "images"):
                        usd = ctx.images.place(channel, spot["name"], spot["look"], out)
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
    the one before it, so the brace taped on Day 2 is the same brace wrapped on Day 9; each is drawn once,
    checked against its words, and reused whenever they look that way again."""
    made, recipe = base, [base.name, str(base.stat().st_mtime_ns)]  # mtime: a replaced reference draws again
    with _lock(video["id"], "look", who):
        for now in chain:
            recipe.append(now)
            out = ctx.media(video["id"]) / SETS / f"look_{_slug(who)}_{_digest(recipe)}.png"
            if not _from_earlier(ctx, conn, video, out):
                before, what = made, f"{who} with {now}"

                def draw(fix: str) -> None:
                    with ctx.reserve(conn, video, ctx.images.still_price, f"the picture of {what}", "images"):
                        usd = ctx.images.change_look(channel, before, now, out, fix=fix)
                        ctx.log_cost(conn, video["id"], SETS, "images", usd)

                _checked(ctx, conn, video, channel, what, draw, "change",
                         {"what": f"This should be {who} as drawn in image 1, redrawn with: {now}",
                          "images": "Image 1 is them before; image 2 is the new picture to check."}, [before, out])
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

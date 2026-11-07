"""A character short's direction, once its voice is made. The agent says who and what it needs, what's missing is got and
looked at, and then it directs the whole short in the scene language, timed to the voice's words (CHARACTERS.md). No code
per video: it all ends up as data, checked before anything's rendered.

A stage waiting on the Claude Code session runs again from the top once it's answered, so each step has to ask the same
thing and get its stored answer. The library grows while this runs, which would change the question, so what's been decided is
kept in files under the video: what it needs, each search, how far each thing has got. A thing's spec goes in things/specs once
it's been looked at and passed. Nothing here spends money. A thing that can only be generated is left out, and the owner's told.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from characters import build as character_build
from characters import spec as character_spec
from core import db
from core.stage import run_video_stage
from machines import spec as machine_spec
from render import clips, humgen
from scenes import direction as short
from scenes import spec as scene_spec
from things import build as thing_build
from things import get
from things import spec as thing_spec

NAME = "direct"
LOOK_NOTE = "From the look at the shots, "     # how film.py's notes start: they're about the shots, not what it needs
READY = """AND direction_json IS NULL
           AND EXISTS (SELECT 1 FROM scenes s WHERE s.video_id = videos.id)
           AND NOT EXISTS (SELECT 1 FROM scenes s WHERE s.video_id = videos.id AND s.state NOT IN ('voiced', 'ok'))"""
EXAMPLES = [Path(__file__).resolve().parent.parent / "scenes" / "examples" / name for name in ("bird_lands_on_head.json", "magnet_under_pan.json")]
BUILT_NOTE = "A built thing looked wrong: "     # sent back to whoever wrote its parts, so they write them again
MOST_REBUILDS = 3
STANCES = ("Idle_relaxed", "Idle_arms_folded_waiting", "Idle_with_a_sword", "Idle_FoldArms_Loop", "Idle_TalkingPhone_Loop",
           "Idle_No_Loop")
STUB_STANCE = "Idle_relaxed"
# what a body can do, and what each looks like: each has been looked at on a person, and the speeds measured. Those that go somewhere are for `walk`
GOES = {"Walk_forwards": "walking, 0.6 to 1.4 m/s", "Walk_formal": "walking upright, 0.6 to 1.4 m/s", "Walk_crouched_forwards": "creeping along low, 0.4 to 1 m/s",
        "Walk_carrying": "walking leaning back, as under a weight, 0.4 to 0.9 m/s", "Walk_zombie_forwards": "a zombie's shamble, 0.6 to 1.5 m/s",
        "Run_jog_forwards": "running, 3.2 to 8 m/s", "Run_sprint": "sprinting, 4.8 to 12 m/s"}
ACTS = {"Hit_to_the_head": "flinches from a blow to the head, on their feet, 0.5 s", "Hit_to_the_chest": "flinches from a blow to the chest, on their feet, 0.4 s",
        "Hit_knockback": "thrown back off their feet onto the ground in under a second, travelling over a meter: use stays",
        "Death_fall_backwards": "doubles over, staggers, and goes down flat on their back with an arm up, 2.4 s: use stays",
        "Move_get_up_from_the_ground": "gets up off the ground, after one of those", "Action_pick_up_from_a_table": "reaches forward to pick something up",
        "Action_sit_down": "sits down, on nothing unless something's there: use stays", "Action_stand_up_from_sitting": "stands up from sitting",
        "Yes": "holds an arm out in front, then lowers it", "Idle_No_Loop": "shakes their head", "Punch_jab_left_2": "a quick left jab", "Punch_cross_right_2": "a hard right punch",
        "OverhandThrow": "throws overhand", "Consume": "brings a hand up towards their mouth", "TreeChopping_Loop": "chops with both hands, over and over"}


def run_once(ctx) -> bool:
    return run_video_stage(ctx, NAME, "generating", _work, where=READY, lease_s=3600)


def timeline(ctx, conn, video) -> dict:
    scenes = db.scenes_for(conn, video["id"])
    rows = [{"idx": s["idx"], "narration": s["narration"], "shows": s["visual_prompt"], "duration_ms": s["duration_ms"],
             "words": json.loads(s["words_json"] or "[]")} for s in scenes]
    gaps = ctx.channel(video["channel_id"]).pauses_ms
    return short.lines(rows, short.pauses([{"narration": s["narration"], "beat_idx": s["beat_idx"]} for s in scenes], gaps))


def _stub(ctx) -> bool:
    return ctx.config.mode == "stub"


def _stances(ctx) -> list[str]:
    if _stub(ctx) or clips.missing(ctx.config):
        return [STUB_STANCE]
    return [s for s in STANCES if s in clips.catalog(ctx.config)]


def _moves(ctx) -> list[str]:
    """The moves there are here, of those a body can do."""
    if _stub(ctx) or clips.missing(ctx.config):
        return []
    found = clips.catalog(ctx.config)
    return [name for name in (*GOES, *ACTS) if name in found]


def _moves_text(moves: list[str]) -> str:
    goes = [f"- {name}: {GOES[name]}" for name in moves if name in GOES]
    acts = [f"- {name}: {ACTS[name]}" for name in moves if name in ACTS]
    return "Going somewhere, for `walk`:\n" + ("\n".join(goes) or "(none)") + "\n\nOn the spot, for `act`:\n" + ("\n".join(acts) or "(none)")


def _people_text() -> str:
    rows = []
    for cid in character_spec.all_ids():
        spec = character_spec.load(character_spec.path_for(cid))
        rows.append(f"- {cid}: {spec['name']}, {spec['gender']}, {spec['age']}, {spec['hair_color']} hair, {spec['outfit']}")
    return "\n".join(rows) or "(nobody yet)"


def _things_text(config, only: list[str] | None = None) -> str:
    rows = []
    for tid in only if only is not None else thing_spec.all_ids():
        spec = thing_spec.load(thing_spec.path_for(tid))
        made = thing_build.made(config, tid) or {}
        size = "x".join(str(round(v, 2)) for v in made.get("size") or []) or f"{spec.get('meters', '?')} long"
        lines = sorted(part["id"] for part in spec["source"].get("parts") or [] if part.get("kind") in ("pipe", "spiral"))
        parts = sorted(part["id"] for part in spec["source"].get("parts") or [])
        rows.append(f"- {tid}: {spec['what']}. {size} m. Moves: {', '.join(made.get('moves') or spec.get('moves') or []) or 'none'}. "
                    f"Spots: {', '.join(spec.get('spots') or []) or 'none'}."
                    + (f" Parts: {', '.join(parts)}." if parts else "") + (f" Lines: {', '.join(lines)}." if lines else ""))
    return "\n".join(rows) or "(nothing yet)"


def _character_format() -> str:
    return character_spec.__doc__.strip()


def _check_cast(ctx) -> callable:
    def check(data: dict) -> list[str]:
        out = []
        people, things = data.get("people") or [], data.get("things") or []
        if not 1 <= len(people) <= 3:
            out.append("people: one to three")
        known = set(character_spec.all_ids())
        for p in people:
            if p.get("id") not in known and not p.get("spec"):
                out.append(f"{p.get('id')!r} isn't made yet, so it needs a spec")
            elif p.get("spec") and p.get("id") not in known and not _stub(ctx) and not humgen.missing(ctx.config):
                out += [f"person {p['id']}: {w}" for w in character_spec.check(p["spec"], humgen.options(ctx.config))]
        library = set(thing_spec.all_ids())
        for t in things:
            if t.get("id") in library:
                continue
            if t.get("parts"):
                out += [f"thing {t.get('id')}: {w}" for w in thing_spec.check(_built_spec(t))]
                continue
            for key in ("what", "search"):
                if not str(t.get(key) or "").strip():
                    out.append(f"thing {t.get('id')}: says {key}")
            if not (isinstance(t.get("meters"), (int, float)) and t["meters"] > 0):
                out.append(f"thing {t.get('id')}: says how long it is in meters")
        return out
    return check


def _built_spec(want: dict) -> dict:
    """What the short asked to be built, as a thing's spec."""
    spec = {"what": want["what"], "source": {"kind": "built", "parts": want["parts"]}}
    return {**spec, "spots": want["spots"]} if want.get("spots") else spec


def _asked_once(ctx, video, notes: list[str], ask) -> dict:
    """What the short needs, asked once for each set of the owner's notes: the library it's asked with grows as things are
    got, so asking again would be a new question each time."""
    keep = ctx.media(video["id"]) / "direct" / "cast.json"
    if keep.exists():
        saved = json.loads(keep.read_text(encoding="utf-8"))
        if saved["notes"] == notes:
            return saved["cast"]
    cast = ask()
    keep.parent.mkdir(parents=True, exist_ok=True)
    keep.write_text(json.dumps({"notes": notes, "cast": cast}, indent=1), encoding="utf-8")
    return cast


def _make_people(ctx, cast: dict, say) -> list[str]:
    ids = []
    for p in cast["people"]:
        if p["id"] not in character_spec.all_ids():
            character_spec.path_for(p["id"]).write_text(json.dumps(p["spec"], indent=1), encoding="utf-8")
        if not _stub(ctx) and not (character_build.folder(ctx.config, p["id"]) / "person.blend").exists():
            character_build.build(ctx.config, p["id"], say)
        ids.append(p["id"])
    return ids


def _search(ctx, video, tid: str, words: str) -> dict:
    """What's out there for a thing, once per video, so it's the same list every time this stage runs again. Without a token
    Sketchfab's can't be downloaded, so they aren't offered."""
    keep = ctx.media(video["id"]) / "direct" / f"{tid}.json"
    if keep.exists():
        return json.loads(keep.read_text(encoding="utf-8"))
    found = get.search(ctx.config, words)
    if not os.environ.get("SKETCHFAB_TOKEN"):
        found["hits"] = [h for h in found["hits"] if h["source"]["kind"] != "sketchfab"]
        found["sheet"] = str(get.picture(found["hits"], Path(found["sheet"])))
    keep.parent.mkdir(parents=True, exist_ok=True)
    keep.write_text(json.dumps(found, indent=1), encoding="utf-8")
    return found


def _get_thing(ctx, conn, video, channel, want: dict, meter) -> str | None:
    """One thing the short asked for: a model chosen from pictures, fetched, looked at and put right, and kept. Returns its
    id, or None if nothing free would do."""
    tid = want["id"]
    if thing_spec.path_for(tid).exists():
        thing_build.build(ctx.config, tid, say=lambda _: None)
        return tid
    if want.get("parts"):
        return _build_thing(ctx, conn, video, channel, want, meter)
    found = _search(ctx, video, tid, want["search"])
    keep = ctx.media(video["id"]) / "direct" / f"{tid}.state.json"     # so running again carries on where it was
    state = json.loads(keep.read_text(encoding="utf-8")) if keep.exists() else {"rejected": [], "spec": None, "look": 1, "title": ""}

    def save() -> None:
        keep.parent.mkdir(parents=True, exist_ok=True)
        keep.write_text(json.dumps(state, indent=1), encoding="utf-8")

    while len(state["rejected"]) < 3 and found["hits"]:
        if state["spec"] is None:
            picked = ctx.llm.pick_thing(channel, want, found["hits"], found["sheet"], state["rejected"], meter(f"choosing {want['what']}"))
            if picked["choice"] == 0:
                break
            hit = found["hits"][picked["choice"] - 1]
            state.update(spec={"what": want["what"], "source": hit["source"], "meters": want["meters"]}, look=1, title=hit["title"])
            save()
        made = thing_build.build(ctx.config, tid, say=lambda _: None, spec=state["spec"])
        looked = ctx.llm.check_thing(channel, want, made["manifest"], made["sheet"], state["look"], meter(f"checking {want['what']}"))
        if not looked["right_thing"]:
            state.update(rejected=[*state["rejected"], state["title"]], spec=None)
            save()
            continue
        changed = _with_changes(state["spec"], looked)
        if changed != state["spec"] and state["look"] == 1:      # looked at once more, as it now is
            state.update(spec=changed, look=2)
            save()
            continue
        thing_build.build(ctx.config, tid, say=lambda _: None, spec=changed)
        thing_spec.path_for(tid).write_text(json.dumps(changed, indent=1), encoding="utf-8")
        return tid
    ctx.events.emit("notice", video["id"], text=f"No free model would do for {want['what']}, so it's directed without one. "
                                                f"Generating one costs about ${get.GENERATE['usd']}: say the word if it's worth it.")
    return None


def _build_thing(ctx, conn, video, channel, want: dict, meter) -> str | None:
    """A thing made from its parts, and looked at. If it looks wrong, the note goes back to whoever wrote its parts, a few times
    at most: with a new note, what the short needs is asked again."""
    tid, spec = want["id"], _built_spec(want)
    made = thing_build.build(ctx.config, tid, say=lambda _: None, spec=spec)
    looked = ctx.llm.check_thing(channel, {**want, "meters": max(made["manifest"]["size"])}, made["manifest"], made["sheet"], 2,
                                 meter(f"checking {want['what']}"))
    if looked["right_thing"]:
        thing_spec.path_for(tid).write_text(json.dumps(spec, indent=1), encoding="utf-8")
        return tid
    rebuilt = sum(note.startswith(BUILT_NOTE) for note in db.notes(conn, video["id"], "direct"))
    if rebuilt < MOST_REBUILDS:
        with db.tx(conn):
            db.add_feedback(conn, video["id"], "direct", f"{BUILT_NOTE}{tid}: {looked['seen']} {'; '.join(looked.get('problems') or [])}")
    else:
        ctx.events.emit("notice", video["id"], text=f"{want['what']} still doesn't look right after {rebuilt} tries, so it's directed without it.")
    return None


def _with_changes(spec: dict, looked: dict) -> dict:
    """The spec with what the look found, turned, tilted, sized and named."""
    out = {**spec, "meters": looked["meters"] if looked.get("meters") else spec["meters"]}
    if looked.get("turn"):
        out["turn"] = (spec.get("turn", 0) + looked["turn"]) % 360
    if looked.get("tilt") and any(looked["tilt"]):
        out["tilt"] = looked["tilt"]
    for key in ("rest", "moves", "spots"):
        if looked.get(key):
            out[key] = looked[key]
    return out


def _work(ctx, conn, video) -> None:
    channel = ctx.channel(video["channel_id"])
    outline = json.loads(video["outline_json"])
    clock = timeline(ctx, conn, video)
    notes = db.notes(conn, video["id"], "direct")
    say = lambda _: None

    def meter(what: str):
        return ctx.meter(conn, video, NAME, what)

    def needs() -> tuple[dict, list[str]]:
        latest = db.notes(conn, video["id"], "direct")
        wanted = _asked_once(ctx, video, [n for n in latest if not n.startswith(LOOK_NOTE)], lambda: ctx.llm.cast_short(
            channel, {"outline": outline, "lines": short.lines_text(clock), "people": _people_text(),
                      "things": _things_text(ctx.config), "built_in": ", ".join(scene_spec.PROPS),
                      "character_format": _character_format(), "thing_format": f"{thing_spec.__doc__.strip()}\n\n{machine_spec.__doc__.strip()}",
                      "notes": latest}, _check_cast(ctx), meter("what the short needs")))
        return wanted, [tid for t in wanted["things"] if (tid := _get_thing(ctx, conn, video, channel, t, meter))]

    before = len(notes)
    cast, things = needs()
    while len(db.notes(conn, video["id"], "direct")) > before:     # a built thing looked wrong: its parts are written again
        before = len(db.notes(conn, video["id"], "direct"))
        cast, things = needs()
    notes = db.notes(conn, video["id"], "direct")
    people = _make_people(ctx, cast, say)
    menu = {tid: entry for tid, entry in thing_build.menu(ctx.config).items() if tid in things}
    stances, moves = _stances(ctx), _moves(ctx)
    check = lambda d: short.check(d, clock["total"], people, stances, menu, moves)
    draft = json.loads(video["direction_draft_json"] or "{}")
    previous = draft.get("scenes")
    written = ctx.llm.direct(channel, {
        "outline": outline, "lines": short.lines_text(clock), "total": clock["total"],
        "people": "\n".join(f"- {p['id']}, who plays {p['plays']}" for p in cast["people"]), "cast_ids": people,
        "things": _things_text(ctx.config, things), "stances": ", ".join(stances), "moves": _moves_text(moves), "language": scene_spec.__doc__.strip(),
        "example": "\n\n".join(path.read_text(encoding="utf-8") for path in EXAMPLES), "notes": notes, "previous": previous,
    }, check, meter("the direction"))
    credits = sorted({made["credit"] for tid in things if (made := thing_build.made(ctx.config, tid)) and made.get("credit")})
    direction = {"scenes": written["scenes"], "marks": written.get("marks") or [], "people": people, "things": things, "credits": credits,
                 "look": 1 if draft.get("looked") else 0, "approved": "character" not in channel.gates}
    with db.tx(conn):
        db.update_video(conn, video["id"], direction_json=json.dumps(direction),
                        direction_draft_json=json.dumps({"scenes": written["scenes"], "looked": bool(draft.get("looked")), "refused": draft.get("refused", 0)}))
        conn.execute("UPDATE scenes SET state = 'ok' WHERE video_id = ? AND state = 'voiced'", (video["id"],))
    if not direction["approved"]:
        ctx.events.emit("gate_reached", video["id"], gate="character")

"""Checks on what the LLM writes. They live in code so a prompt edit can't loosen them.

Each returns problems in plain words, numbered from 1 like the cards (empty list = fine). The Claude
provider sends them back for one more try. These numbers also fill the prompts' {beat_count},
{scene_count}, ... placeholders, so a prompt always asks for what the checks accept.
"""
from __future__ import annotations

import re
from pathlib import Path

from puppet.stage import Stage, inside

BEATS = (8, 10)
HERO_BEATS = (3, 4)
HERO_SCENES = (7, 9)            # what the prompt asks for each hero beat: the build-up, the moment, the aftermath
HERO_SCENES_OK = 6              # fewer and the set piece is rushed
SCENES = (40, 65)
SCENE_WORDS = (30, 40)          # what the prompt asks for
SCENE_WORDS_OK = (25, 45)       # what passes: a line a few words off isn't worth rewriting the whole script
TOTAL_WORDS = 1750              # asked for: about 12 minutes at 150 words a minute, with the pauses between scenes
TOTAL_WORDS_OK = (1500, 2000)   # passes: about 10 to 14 minutes
WPM = 150                       # elevenlabs.speed slows the voices to about this; their own pace is 160 to 170
# A character short: 30 to 60 seconds, read slowly (prompts/character/)
SHORT_BEATS = (3, 6)
SHORT_LINES = (4, 16)
SHORT_LINE_WORDS = (3, 22)      # one step a line: the owner's two star shorts run 10 to 15 words, none over 22 (BUILD.md, phase 45)
SHORT_WORDS = (60, 150)         # what the prompt asks for
SHORT_WORDS_OK = (50, 165)      # what passes
SHORT_HOOK_WORDS = 26           # a moment is short, but an "If you..." setup runs to about 25
SHORT_SHAPES = ("true_story", "absurd_test", "why_it_happens", "thought_experiment", "fake_invention", "fix_in_steps", "ladder",
                "you_invent", "mystery", "parody")
QUESTION_OPENS = ("why_it_happens",)     # the only shape that may open on a bare question
TITLES = 3
TITLE_MAX = 100                 # YouTube's limit
DESCRIPTION_CHARS = (150, 900)  # the viewer-facing blurb above the chapters: a short paragraph, not a note or an essay
THUMB_WORDS = (2, 4)            # thumbnail text, drawn on in code (providers/images.py caption)
THUMB_CHARS = 24                # longer won't fit big enough to read on a phone
FAMILY_WORDS = 3                # a topic's setting tag: "ocean", "frozen north"
THUMB_TEXT = re.compile(r"^[A-Za-z0-9 !?'\-:.,&$%]+$")  # what the caption font has
MOTIONS = ("kenburns", "clip")
SHOTS = ("wide", "medium", "close-up")  # a close-up is drawn without the place's picture (stages/stills.py)
HERO = "the stick figure"       # what visual prompts and looks call the main character; a still shows them only if
                                # its visual prompt says this
COLD_OPEN_SCENES = 6            # a script may open on a later day for this many scenes, then start again from Day 1
CAST = (0, 4)                   # people besides the main character with a thread of their own
TRACKER = (2, 4)                # things the viewer counts along with the character (water, food, days left)
PLACES = (1, 10)                # places the pictures happen in; each is drawn once as a reference picture
STRETCH_DAYS = 3                # quiet days one scene may tell together ("Day 3-5"); a tenth of the span if longer
LABEL = re.compile(r"^(Day|Week|Month|Year) (\d+)\b")
STRETCH = re.compile(r"^Day (\d+)(?:\s*(?:-|–|—|to)\s*(?:Day\s*)?(\d+))?\b")
DAYS = {"Day": 1, "Week": 7, "Month": 30, "Year": 365}


def words(text: str) -> int:
    return len(text.split())


def _day(label: str) -> int | None:
    m = LABEL.match(label.strip())
    return int(m.group(2)) * DAYS[m.group(1)] if m else None


def _days(label: str) -> tuple[int, int] | None:
    """(first, last) day a "Day 3" or "Day 3-5" label tells; None for weeks, months and anything else."""
    m = STRETCH.match(label.strip())
    return (int(m.group(1)), int(m.group(2) or m.group(1))) if m else None


def _blank(value) -> bool:
    return not isinstance(value, str) or not value.strip()


def _number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0


def _key(name) -> str:
    return name.strip().lower() if isinstance(name, str) else ""


def _plain(text: str) -> str:
    """Lowercase words and numbers, one space apart and one at each end, so `in` only matches whole words."""
    return f" {' '.join(re.findall(r'[a-z0-9]+', text.lower()))} "


def cold_open(labels: list[str]) -> int:
    """How many scenes open on a later day before the story starts again from its first day (0 if none do), by
    the same rule as _timeline."""
    last = None
    for n, label in enumerate(labels[:COLD_OPEN_SCENES]):
        day = _day(label)
        if day is not None and last is not None and day < last:
            return n
        if day is not None:
            last = day
    return 0


def _timeline(labels: list[tuple[str, str]], cold_open: int = 0) -> list[str]:
    """`labels` is (where, label). Labels must read like "Day 12" and never go back in time, except once within the
    first `cold_open` entries: a cold open on a later day ("Day 30"), then the story from the start ("Day 1")."""
    problems, last, restarted = [], None, False
    for n, (where, label) in enumerate(labels):
        day = _day(label)
        if day is None:
            problems.append(f"{where}: label {label!r} should start like \"Day 12\", \"Week 3\" or \"Month 4\"")
        elif last is not None and day < last[0]:
            if n < cold_open and not restarted:
                restarted = True  # the cold open ends here
            else:
                problems.append(f"{where}: {label} comes after {last[1]}, which goes back in time")
        if day is not None:
            last = (day, label)
    return problems


def _every_day(scenes: list[dict], cold_open: int = 0, last_day: int | None = None) -> list[str]:
    """A story labeled in days tells every one of them, in order: each new label starts at most the day after the
    last one ended, and quiet days told together ("Day 3-5") are at most STRETCH_DAYS, or a tenth of the span in a
    longer story. Scenes before a cold open's restart, and stories labeled in weeks or months, aren't checked.
    `last_day`: where the story ends, for a script that has only come in part of the way."""
    told = [(n, s.get("label") or "") for n, s in enumerate(scenes, 1) if n > cold_open]
    spans = [_days(label) for _, label in told]
    if not told or None in spans:
        return []
    longest = max(STRETCH_DAYS, (max(spans[-1][1], last_day or 0) - spans[0][0] + 1) // 10)
    problems, end, last = [], None, None
    for (n, label), (first, final) in zip(told, spans):
        if final - first + 1 > longest:
            problems.append(f"scene {n} tells {final - first + 1} days at once ({label}); keep a stretch to {longest} days")
        if end is not None and first > end + 1:
            gap = f"Day {end + 1}" if first == end + 2 else f"Days {end + 1} to {first - 1}"
            like = f"Day {end + 1}" if first == end + 2 else f"Day {end + 1}-{min(first - 1, end + longest)}"
            problems.append(f"scene {n} jumps from {last} to {label}, skipping {gap}; tell every day, on its own or a "
                            f"few quiet ones together, like \"{like}\"")
        end, last = final if end is None else max(end, final), label
    return problems


def outline(data: dict) -> list[str]:
    problems = [f"the {k} is empty" for k in ("hook", "ending") if _blank(data.get(k))]
    beats = data.get("beats") or []
    lo, hi = BEATS
    if not lo <= len(beats) <= hi:
        problems.append(f"there are {len(beats)} beats; it needs {lo} to {hi}")
    heroes = sum(1 for b in beats if b.get("hero") is True)
    lo, hi = HERO_BEATS
    if not lo <= heroes <= hi:
        problems.append(f"{heroes} beats are hero beats; it needs {lo} to {hi}")
    for n, b in enumerate(beats, 1):
        empty = [k for k in ("label", "title", "summary", "skill") if _blank(b.get(k))]
        if empty:
            problems.append(f"beat {n} has no {' or '.join(empty)}")
    problems += _timeline([(f"beat {n}", b.get("label") or "") for n, b in enumerate(beats, 1) if b.get("label")])
    seen: dict[str, int] = {}
    for n, b in enumerate(beats, 1):
        skill = (b.get("skill") or "").strip().lower()
        if skill and skill in seen:
            problems.append(f"beat {n} teaches the same skill as beat {seen[skill]} ({b['skill']})")
        seen.setdefault(skill, n)
    if _blank(data.get("backstory")):
        problems.append("the backstory is empty")
    return problems + _cast(data.get("cast") or [], beats) + _tracker(data.get("tracker") or [])


def _cast(cast: list[dict], beats: list[dict]) -> list[str]:
    """Everyone with a part has a name, a look and a thread, and appears in at least one beat."""
    problems, names = [], {}
    if len(cast) > CAST[1]:
        problems.append(f"there are {len(cast)} cast members; keep it to {CAST[1]}")
    for n, c in enumerate(cast, 1):
        empty = [k for k in ("name", "look", "role", "thread") if _blank(c.get(k))]
        if empty:
            problems.append(f"cast member {n} has no {' or '.join(empty)}")
        key = _key(c.get("name"))
        if key in names:
            problems.append(f"cast members {names[key]} and {n} are both called {c['name'].strip()}")
        elif key:
            names[key] = n
    listed = set()
    for n, b in enumerate(beats, 1):
        for name in b.get("cast") or []:
            if _key(name) not in names:
                problems.append(f"beat {n} lists {name!r} in its cast, but the cast has no one by that name")
            listed.add(_key(name))
    for key, n in names.items():
        if key not in listed:
            problems.append(f"cast member {n} ({cast[n - 1]['name'].strip()}) isn't in any beat's cast")
    return problems


def _tracker(tracker: list[dict]) -> list[str]:
    lo, hi = TRACKER
    many = "" if len(tracker) == 1 else "s"
    problems = [] if lo <= len(tracker) <= hi else [f"the tracker has {len(tracker)} item{many}; it needs {lo} to {hi}"]
    seen = set()
    for n, t in enumerate(tracker, 1):
        empty = [k for k in ("item", "unit") if _blank(t.get(k))]
        if empty:
            problems.append(f"tracker item {n} has no {' or '.join(empty)}")
        if not _number(t.get("start")):
            problems.append(f"tracker item {n}'s start should be a number of 0 or more")
        key = _key(t.get("item"))
        if key in seen:
            problems.append(f"the tracker has {t['item'].strip()} twice")
        seen.add(key)
    return problems


def _beats_done(scenes: list[dict], beats: list, partial: bool) -> int:
    """The beats the scenes have finished: all of them, or for a script still coming in parts (whole beats at a
    time, in order), every beat up to the last one written."""
    if not partial:
        return len(beats)
    return max((s["beat"] for s in scenes if isinstance(s.get("beat"), int) and 1 <= s["beat"] <= len(beats)),
               default=0)


def script(scenes: list[dict], outline: dict, clips_per_video: int, places: list[dict],
           partial: bool = False) -> list[str]:
    """`scenes` as the model writes them: `beat` numbered from 1, no idx (scene numbers are list order).

    `partial`: the script so far, sent in parts of whole beats (core/jobs.py). Every rule holds for the beats
    written; the counts that need the whole script (scenes, words, places) are only checked for going over."""
    problems = []
    beats = outline["beats"]
    done = _beats_done(scenes, beats, partial)
    lo, hi = SCENES
    if len(scenes) > hi or not partial and len(scenes) < lo:
        problems.append(f"there are {len(scenes)} scenes; it needs {lo} to {hi}")
    lo, hi = SCENE_WORDS_OK
    last_beat, clips = 0, 0
    for n, s in enumerate(scenes, 1):
        beat = s.get("beat")
        if not isinstance(beat, int) or not 1 <= beat <= len(beats):
            problems.append(f"scene {n}: beat {beat} doesn't exist; the outline has beats 1 to {len(beats)}")
        elif beat < last_beat:
            problems.append(f"scene {n} is in beat {beat} but comes after a scene in beat {last_beat}")
        else:
            last_beat = beat
        if _blank(s.get("narration")):
            problems.append(f"scene {n} has no narration")
        elif not lo <= words(s["narration"]) <= hi:
            problems.append(f"scene {n}'s narration is {words(s['narration'])} words; keep each scene to "
                            f"{SCENE_WORDS[0]} to {SCENE_WORDS[1]}")
        if _blank(s.get("visual_prompt")):
            problems.append(f"scene {n} has no visual_prompt")
        if s.get("shot") not in SHOTS:
            problems.append(f"scene {n}: shot must be wide, medium or close-up, not {s.get('shot')!r}")
        if s.get("motion") not in MOTIONS:
            problems.append(f"scene {n}: motion must be kenburns or clip, not {s.get('motion')!r}")
        elif s["motion"] == "clip":
            clips += 1
            if isinstance(beat, int) and 1 <= beat <= len(beats) and not beats[beat - 1].get("hero"):
                problems.append(f"scene {n} is a clip in beat {beat}, which isn't a hero beat")
    missing = sorted(set(range(1, done + 1)) - {s.get("beat") for s in scenes})
    if missing:
        problems.append(f"beat{'s' if len(missing) > 1 else ''} {', '.join(map(str, missing))} "
                        f"{'have' if len(missing) > 1 else 'has'} no scenes")
    for b, beat in enumerate(beats[:done], 1):
        count = sum(1 for s in scenes if s.get("beat") == b)
        if beat.get("hero") and 0 < count < HERO_SCENES_OK:
            problems.append(f"beat {b} is a hero beat but has only {count} scene{'s' if count > 1 else ''}; give it "
                            f"{HERO_SCENES[0]} to {HERO_SCENES[1]}, with the build-up, the moment and the aftermath")
    if clips > clips_per_video:
        problems.append(f"there are {clips} clip scenes; this channel allows {clips_per_video}")
    total = sum(words(s.get("narration") or "") for s in scenes)
    lo, hi = TOTAL_WORDS_OK
    if total > hi or not partial and total < lo:
        problems.append(f"the narration is {total:,} words in total; aim for about {TOTAL_WORDS:,} "
                        f"(it must land between {lo:,} and {hi:,})")
    problems += _timeline([(f"scene {n}", s.get("label") or "") for n, s in enumerate(scenes, 1)], COLD_OPEN_SCENES)
    end = _days(beats[-1].get("label") or "") if partial and beats else None
    problems += _every_day(scenes, cold_open([s.get("label") or "" for s in scenes]), end[1] if end else None)
    return problems + _continuity(scenes, outline, places, done, partial)


def _continuity(scenes: list[dict], outline: dict, places: list[dict], done: int | None = None,
                partial: bool = False) -> list[str]:
    """What makes each scene follow on from the last: a known place, a told move whenever the place changes, the
    cast where the outline puts them with every thread ended in words, and the tracker on every beat. An outline
    from before the cast and tracker existed skips those rules. `done`: the beats written so far (script())."""
    problems, ids = [], {}
    done = len(outline["beats"]) if done is None else done
    lo, hi = PLACES
    if len(places) > hi or not partial and len(places) < lo:
        problems.append(f"there are {len(places)} places; it needs {lo} to {hi}")
    for n, p in enumerate(places, 1):
        empty = [k for k in ("id", "name", "look") if _blank(p.get(k))]
        if empty:
            problems.append(f"place {n} has no {' or '.join(empty)}")
        pid = (p.get("id") or "").strip()
        if pid in ids:
            problems.append(f"places {ids[pid]} and {n} have the same id ({pid})")
        elif pid:
            ids[pid] = n
    beats = outline["beats"]
    cast = {_key(c.get("name")): c["name"].strip() for c in outline.get("cast") or []}
    in_beat = [{_key(name) for name in b.get("cast") or []} for b in beats]
    items = sorted(_key(t.get("item")) for t in outline.get("tracker") or [])
    cold = cold_open([s.get("label") or "" for s in scenes])  # cold-open scenes may show people before they enter
    tracked, here = set(), None
    for n, s in enumerate(scenes, 1):
        beat = s.get("beat") if isinstance(s.get("beat"), int) and 1 <= s["beat"] <= len(beats) else None
        place = (s.get("place") or "").strip()
        if place not in ids:
            problems.append(f"scene {n}: place {place!r} isn't one of the places")
        else:
            if here is not None and place != here:
                move = s.get("move") or ""
                if _blank(move):
                    problems.append(f"scene {n} goes from {here} to {place}, so its move must quote the words in "
                                    "its narration that tell where we are now")
                elif _plain(move) not in _plain(s.get("narration") or ""):
                    problems.append(f"scene {n}'s move ({move.strip()!r}) isn't in its narration word for word")
            here = place
        for name in s.get("cast") or []:
            if _key(name) not in cast:
                problems.append(f"scene {n} has {name!r} in its cast, but the outline's cast has no one by that name")
            elif beat and n > cold and _key(name) not in in_beat[beat - 1]:
                problems.append(f"scene {n} shows {cast[_key(name)]}, but the outline doesn't list them in beat {beat}")
        for look in s.get("looks") or []:
            if _key(look.get("who")) != HERO and _key(look.get("who")) not in cast:
                problems.append(f"scene {n}'s looks names {look.get('who')!r}; use \"{HERO}\" or a cast name")
            if _blank(look.get("now")):
                problems.append(f"scene {n}'s look for {look.get('who')} has no now; say what they have on, or "
                                "\"as usual\"")
        snapshot = s.get("tracker") or []
        if snapshot and not items:
            problems.append(f"scene {n} has a tracker, but the outline tracks nothing; leave it empty")
        elif snapshot:
            listed = sorted(_key(t.get("item")) for t in snapshot)
            if listed != items:
                problems.append(f"scene {n}'s tracker lists {', '.join(listed)}; list every tracked item once: "
                                f"{', '.join(items)}")
            if not all(_number(t.get("amount")) for t in snapshot):
                problems.append(f"scene {n}'s tracker has an amount that isn't a number of 0 or more")
            if beat:
                tracked.add(beat)
    untracked = sorted(set(range(1, done + 1)) - tracked) if items else []
    if untracked:
        many = len(untracked) > 1
        problems.append(f"beat{'s' if many else ''} {', '.join(map(str, untracked))} never show{'' if many else 's'} "
                        "the tracker; give the first scene of every beat one")
    for key, name in cast.items():
        last = max((i for i, names in enumerate(in_beat, 1) if key in names), default=None)
        said = _plain(" ".join(s.get("narration") or "" for s in scenes if s.get("beat") == last))
        if last is not None and last <= done and _plain(name.split()[-1]) not in said:
            problems.append(f"{name}'s part ends in beat {last}, the last beat that lists them, but no line in it "
                            "names them; say there what happens to them")
    return problems


def visual_prompt(text: str) -> list[str]:
    return ["the visual_prompt is empty"] if _blank(text) else []


def _bare_question(hook: str) -> bool:
    """A hook that only asks. An "If you..." setup can end on a question: it has already put something in front of the viewer."""
    text = hook.strip().lower()
    return text.endswith("?") and not text.startswith("if ")


def short_hook(hook, shape) -> list[str]:
    """A character short's first line and the shape it's built on, in an outline or on an idea card."""
    out = []
    if _blank(hook) or words(hook) > SHORT_HOOK_WORDS:
        out.append(f"the hook has to be there, in {SHORT_HOOK_WORDS} words at most")
    elif _bare_question(hook) and shape not in QUESTION_OPENS:
        out.append("the hook is a bare question: open on a moment already happening, or an \"If you...\" setup. Only "
                   f"{' or '.join(QUESTION_OPENS)} can open on a question")
    if shape not in SHORT_SHAPES:
        out.append(f"the shape has to be one of {', '.join(SHORT_SHAPES)}")
    return out


def short_outline(data: dict) -> list[str]:
    """A character short's outline (prompts/character/outline.md)."""
    out = short_hook(data.get("hook"), data.get("shape"))
    if _blank(data.get("turn")):
        out.append("the turn has to be there: what comes after the answer, or \"none:\" and why the short is stronger without one")
    if _blank(data.get("fact")):
        out.append("the fact has to be there, with where it's known from")
    lo, hi = SHORT_BEATS
    if not lo <= len(data.get("beats") or []) <= hi:
        out.append(f"there are {len(data.get('beats') or [])} beats; it needs {lo} to {hi}")
    for n, b in enumerate(data.get("beats") or [], 1):
        if _blank(b.get("title")) or _blank(b.get("summary")):
            out.append(f"beat {n} needs a title and a summary")
    if _blank(data.get("ending")):
        out.append("the ending has to be there")
    return out


def short_script(scenes: list[dict], outline: dict) -> list[str]:
    """A character short's lines (prompts/character/script.md)."""
    out = []
    lo, hi = SHORT_LINES
    if not lo <= len(scenes) <= hi:
        out.append(f"there are {len(scenes)} lines; it needs {lo} to {hi}")
    beats, last = len(outline["beats"]), 0
    for n, s in enumerate(scenes, 1):
        count = words(s.get("narration") or "")
        if not SHORT_LINE_WORDS[0] <= count <= SHORT_LINE_WORDS[1]:
            out.append(f"line {n} is {count} words; keep it to {SHORT_LINE_WORDS[0]} to {SHORT_LINE_WORDS[1]}")
        if "\u2014" in (s.get("narration") or ""):
            out.append(f"line {n} has an em dash; a voice reads those badly")
        if not 1 <= s.get("beat", 0) <= beats:
            out.append(f"line {n} says beat {s.get('beat')}; the outline has {beats}")
        elif s["beat"] < last:
            out.append(f"line {n} goes back to beat {s['beat']}: beats go in order")
        else:
            last = s["beat"]
    missing = sorted(set(range(1, beats + 1)) - {s.get("beat") for s in scenes})
    if missing:
        out.append(f"beats {missing} have no line")
    total = sum(words(s.get("narration") or "") for s in scenes)
    if not SHORT_WORDS_OK[0] <= total <= SHORT_WORDS_OK[1]:
        out.append(f"it's {total} words in all; keep it to {SHORT_WORDS[0]} to {SHORT_WORDS[1]}")
    return out


def thing_look(data: dict, clips: dict) -> list[str]:
    """What the look at a thing's sheet says to change (prompts/character/thing.md). `clips` are what the file really has."""
    out = []
    if not isinstance(data.get("right_thing"), bool):
        out.append("right_thing has to be true or false")
    tilt = data.get("tilt")
    if not (isinstance(tilt, list) and len(tilt) == 2):
        out.append("tilt has to be [x, y] degrees")
    if not (isinstance(data.get("meters"), (int, float)) and data["meters"] > 0):
        out.append("meters has to be its longest side in real life")
    moves = data.get("moves") or {}
    for name, move in moves.items():
        if not isinstance(move, dict) or move.get("clip") not in clips:
            out.append(f"move {name}: its clip has to be one of {', '.join(clips) or 'none: this model has no clips'}")
    if data.get("rest") and data["rest"] not in (moves or clips):
        out.append(f"rest {data['rest']!r} isn't one of its moves")
    return out


def narration(text: str) -> list[str]:
    if _blank(text):
        return ["the narration is empty"]
    lo, hi = SCENE_WORDS_OK
    n = words(text)
    return [] if lo <= n <= hi else [f"the line is {n} words; keep it to {SCENE_WORDS[0]} to {SCENE_WORDS[1]}"]


def titles(options: list[str]) -> list[str]:
    problems = [] if len(options) == TITLES else [f"there are {len(options)} titles; it needs {TITLES}"]
    for n, t in enumerate(options, 1):
        if _blank(t):
            problems.append(f"title {n} is empty")
        elif len(t.strip()) > TITLE_MAX:
            problems.append(f"title {n} is {len(t.strip())} characters; YouTube allows {TITLE_MAX}")
        elif "<" in t or ">" in t:
            problems.append(f"title {n} has < or >, which YouTube doesn't allow")
    if len({t.strip().lower() for t in options}) < len(options):
        problems.append("two titles are the same")
    return problems


def description(text: str) -> list[str]:
    """The viewer-facing blurb for the YouTube page (the chapters and the disclosure are added in code)."""
    if _blank(text):
        return ["the description is empty"]
    n = len(text.strip())
    if not DESCRIPTION_CHARS[0] <= n <= DESCRIPTION_CHARS[1]:
        return [f"the description is {n} characters; keep it to {DESCRIPTION_CHARS[0]} to {DESCRIPTION_CHARS[1]}"]
    if "<" in text or ">" in text:
        return ["the description has < or >, which YouTube doesn't allow"]
    planning = [w for w in ("open cold", "rewind", "the hook", "the promise") if w in text.lower()]
    return [f"the description reads like the outline's note (\"{planning[0]}\"); write it for viewers"] if planning else []


def thumb_texts(texts: list[str]) -> list[str]:
    """The words drawn on each thumbnail, one per title."""
    problems = [] if len(texts) == TITLES else [f"there are {len(texts)} thumb_texts; it needs {TITLES}"]
    lo, hi = THUMB_WORDS
    for n, t in enumerate(texts, 1):
        if _blank(t):
            problems.append(f"thumb_text {n} is empty")
        elif not lo <= words(t) <= hi:
            n_words = f"{words(t)} word{'' if words(t) == 1 else 's'}"
            problems.append(f"thumb_text {n} is {n_words}; keep it to {lo} to {hi}")
        elif len(t.strip()) > THUMB_CHARS:
            problems.append(f"thumb_text {n} is {len(t.strip())} characters; keep it to {THUMB_CHARS}")
        elif not THUMB_TEXT.match(t.strip()):
            problems.append(f"thumb_text {n} has characters the thumbnail font can't draw; use plain letters, "
                            "numbers and ! ? ' - : . , & $ %")
    return problems


def topics(proposed: list[dict], count: int, shown: int, taken: list[str], held: tuple | list = ()) -> list[str]:
    """Topic ideas: `count` of them, each a one-line idea built on hits numbered 1..`shown`, none already taken,
    each with a short family tag that isn't one of the `held` ones."""
    problems = [] if len(proposed) == count else [f"there are {len(proposed)} topics; it needs {count}"]
    have = {t.strip().lower() for t in taken}
    seen: set[str] = set()
    for n, t in enumerate(proposed, 1):
        title = t.get("title") if isinstance(t, dict) else None
        if _blank(title):
            problems.append(f"topic {n} has no title")
            continue
        key = title.strip().lower()
        if len(title.strip()) > TITLE_MAX:
            problems.append(f"topic {n} is {len(title.strip())} characters; keep it under {TITLE_MAX}")
        if key in have:
            problems.append(f"topic {n} (\"{title.strip()}\") is one this channel already has")
        elif key in seen:
            problems.append(f"topic {n} repeats an earlier one")
        seen.add(key)
        if _blank(t.get("why")):
            problems.append(f"topic {n} has no why")
        family = t.get("family")
        if _blank(family):
            problems.append(f"topic {n} has no family")
        elif words(family) > FAMILY_WORDS:
            problems.append(f"topic {n}'s family is {words(family)} words; keep it to {FAMILY_WORDS} or fewer")
        elif family.strip().lower() in {h.lower() for h in held}:
            problems.append(f"topic {n} is in the {family.strip().lower()!r} family, which is on hold")
        based = t.get("based_on") or []
        if not based:
            problems.append(f"topic {n} doesn't say which hits it builds on (based_on)")
        elif bad := [b for b in based if not isinstance(b, int) or not 1 <= b <= shown]:
            problems.append(f"topic {n} cites hit {bad[0]}; the hits are numbered 1 to {shown}")
    return problems


def stage_map(data: dict) -> list[str]:
    """Claude's map of a place (puppet/stage.py): a floor line, spots, a light, all inside the picture."""
    problems = []
    floor = data.get("floor") or []
    if not 3 <= len(floor) <= 8:
        problems.append(f"floor has {len(floor)} points; give 3 to 6")
    for p in floor:
        if not (0 <= p["x"] <= 100 and 0 <= p["y"] <= 100):
            problems.append(f"floor point ({p['x']}, {p['y']}) is outside the picture")
        if not 5 <= p["height"] <= 100:
            problems.append(f"a floor point's height of {p['height']} isn't a sensible percentage of the picture")
    spots = data.get("spots") or []
    if not spots:
        problems.append("spots is empty; name at least the doors, stairs and main furniture")
    names = [s["name"].strip().lower() for s in spots]
    if len(set(names)) != len(names):
        problems.append("two spots have the same name")
    for s in spots:
        if not (0 <= s["x"] <= 100 and 0 <= s["y"] <= 100):
            problems.append(f"spot {s['name']} is outside the picture")
    measure = Stage(Path(), (100, 100), [(p["x"], p["y"], p["height"]) for p in floor], {}, {}) if floor else None
    for o in data.get("occluders") or []:
        polygon = [(p["x"], p["y"]) for p in o.get("polygon") or []]
        if not 3 <= len(polygon) <= 10:
            problems.append(f"occluder {o.get('name')} needs a polygon of 4 to 8 points")
        if any(not (0 <= x <= 100 and 0 <= y <= 100) for x, y in polygon):
            problems.append(f"occluder {o.get('name')} has a point outside the picture")
        for s in spots:
            if o.get("see_through") or not (s["y"] < o.get("base_y", 0) and inside(s["x"], s["y"], polygon)):
                continue
            # behind a low wall a person's head and shoulders show over it (the slope beyond the back wall): fine
            head = s["y"] - (measure.height_at(s["x"], s["y"]) if measure else 0)
            if min(y for _, y in polygon) <= head + 0.25 * (s["y"] - head):
                problems.append(f"spot {s['name']} is behind {o.get('name')}, which is solid and taller than a person "
                                "there: whoever stands there would be hidden by it. Move the spot to open floor beside it, "
                                "or drop it")
    light = data.get("light") or {}
    if not (0 <= light.get("x", -1) <= 100 and 0 <= light.get("y", -1) <= 100):
        problems.append("the light is outside the picture")
    return problems


def parts_map(data: dict, names: list[str]) -> list[str]:
    """Claude's naming of the blobs on a parts sheet (puppet/parts.py): every name once, boxes from 0 up."""
    given = [p["name"].strip().lower() for p in data.get("parts") or []]
    problems = [f"{n} is missing from parts" for n in names if n.lower() not in given]
    problems += [f"{n} is named more than once" for n in set(given) if given.count(n) > 1]
    boxes = [p["box"] for p in data.get("parts") or [] if p["box"]]
    if len(set(boxes)) != len(boxes):
        problems.append("two parts are given the same box")
    return problems


def inventory(data: dict) -> list[str]:
    """Claude's props list (prompts/inventory.md): short lowercase names, sensible sizes, a known `stands`."""
    problems = []
    names = [p["name"].strip().lower() for p in data.get("props") or []]
    if len(names) > 16:
        problems.append(f"{len(names)} props is too many; keep the ones scenes show, at most 16")
    if len(set(names)) != len(names):
        problems.append("a prop is listed twice")
    for p in data.get("props") or []:
        if not re.fullmatch(r"[a-z][a-z0-9 ]{0,24}", p["name"].strip().lower()):
            problems.append(f"the prop name {p['name']!r} isn't one or two plain lowercase words")
        if not 0.02 <= float(p["height"]) <= 2.5:
            problems.append(f"{p['name']}: a height of {p['height']} isn't a sensible fraction of a person")
        if p.get("stands") not in ("bottom", "center", "grip"):
            problems.append(f"{p['name']}: stands must be bottom, center or grip")
    for person in data.get("people") or []:
        if not 0.3 <= float(person["scale"]) <= 1.3:
            problems.append(f"{person['name']}: a scale of {person['scale']} isn't a person's height against an adult")
    return problems


def critique(data: dict) -> list[str]:
    """The reviewer's answer (prompts/critic.md): a verdict that matches its list, each problem with a real fix."""
    problems = data.get("problems") or []
    out = []
    if data.get("verdict") == "revise" and not problems:
        out.append("the verdict is revise but no problems are listed")
    if data.get("verdict") == "fine" and problems:
        out.append("the verdict is fine but problems are listed; one or the other")
    if len(problems) > 8:
        out.append(f"{len(problems)} problems; keep the worst 8")
    for p in problems:
        if len((p.get("fix") or "").split()) < 4:
            out.append(f"the fix for {p.get('where')} is too thin to write from")
        if not (p.get("where") or "").strip():
            out.append("a problem has no where")
    return out


JOINS_MOST = 10   # bad joins a check of the joins lists (prompts/transitions.md)


def look(data: dict) -> list[str]:
    """A look at a systems short's frames (prompts/diagram/look.md): each problem says where, what and a fix."""
    out = []
    if not isinstance(data.get("problems"), list):
        return ["problems isn't a list"]
    for i, p in enumerate(data["problems"], 1):
        if not isinstance(p, dict) or not all(str(p.get(k) or "").strip() for k in ("phase", "what", "fix")):
            out.append(f"problem {i} needs phase, what and fix")
        elif len(str(p["fix"]).split()) < 4:
            out.append(f"problem {i}'s fix is too short to act on: say what to change")
    if len(data["problems"]) > 8:
        out.append("at most 8 problems, the ones a viewer would notice first")
    return out


def joins(data: dict) -> list[str]:
    """The check of the joins (prompts/transitions.md): each bad join placed, in the words or the picture, with a fix
    someone could make."""
    problems = data.get("problems")
    if not isinstance(problems, list):
        return ["problems isn't a list"]
    out = [f"{len(problems)} bad joins; keep the worst {JOINS_MOST}"] if len(problems) > JOINS_MOST else []
    for p in problems:
        at = (p.get("at") or "").strip()
        if not at:
            out.append("a bad join has no `at`: say which, as \"line 6 to 7\" or \"cut 12 at 26.29 s\"")
        if p.get("in") not in ("words", "picture"):
            out.append(f"the join at {at or '?'} needs `in` as words or picture")
        if len((p.get("fix") or "").split()) < 4:
            out.append(f"the fix for the join at {at or '?'} is too thin to make from")
    return out

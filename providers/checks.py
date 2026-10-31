"""Checks on what the LLM writes. They live in code so a prompt edit can't loosen them.

Each returns problems in plain words, numbered from 1 like the cards (empty list = fine). The Claude
provider sends them back for one more try. These numbers also fill the prompts' {beat_count},
{scene_count}, ... placeholders, so a prompt always asks for what the checks accept.
"""
from __future__ import annotations

import re

BEATS = (10, 12)
HERO_BEATS = (3, 4)
SCENES = (45, 70)
SCENE_WORDS = (30, 40)          # what the prompt asks for
SCENE_WORDS_OK = (25, 45)       # what passes: a line a few words off isn't worth rewriting the whole script
TOTAL_WORDS = 1900              # asked for: about 12 minutes at 160 words a minute
TOTAL_WORDS_OK = (1600, 2200)   # passes: about 10 to 14 minutes
WPM = 160                       # the narration voices read 145 to 170 a minute
TITLES = 3
TITLE_MAX = 100                 # YouTube's limit
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
LABEL = re.compile(r"^(Day|Week|Month|Year) (\d+)\b")
DAYS = {"Day": 1, "Week": 7, "Month": 30, "Year": 365}


def words(text: str) -> int:
    return len(text.split())


def _day(label: str) -> int | None:
    m = LABEL.match(label.strip())
    return int(m.group(2)) * DAYS[m.group(1)] if m else None


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


def script(scenes: list[dict], outline: dict, clips_per_video: int, places: list[dict]) -> list[str]:
    """`scenes` as the model writes them: `beat` numbered from 1, no idx (scene numbers are list order)."""
    problems = []
    beats = outline["beats"]
    lo, hi = SCENES
    if not lo <= len(scenes) <= hi:
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
    missing = sorted(set(range(1, len(beats) + 1)) - {s.get("beat") for s in scenes})
    if missing:
        problems.append(f"beat{'s' if len(missing) > 1 else ''} {', '.join(map(str, missing))} "
                        f"{'have' if len(missing) > 1 else 'has'} no scenes")
    if clips > clips_per_video:
        problems.append(f"there are {clips} clip scenes; this channel allows {clips_per_video}")
    total = sum(words(s.get("narration") or "") for s in scenes)
    lo, hi = TOTAL_WORDS_OK
    if not lo <= total <= hi:
        problems.append(f"the narration is {total:,} words in total; aim for about {TOTAL_WORDS:,} "
                        f"(it must land between {lo:,} and {hi:,})")
    problems += _timeline([(f"scene {n}", s.get("label") or "") for n, s in enumerate(scenes, 1)], COLD_OPEN_SCENES)
    return problems + _continuity(scenes, outline, places)


def _continuity(scenes: list[dict], outline: dict, places: list[dict]) -> list[str]:
    """What makes each scene follow on from the last: a known place, a told move whenever the place changes, the
    cast where the outline puts them with every thread ended in words, and the tracker on every beat. An outline
    from before the cast and tracker existed skips those rules."""
    problems, ids = [], {}
    lo, hi = PLACES
    if not lo <= len(places) <= hi:
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
    untracked = sorted(set(range(1, len(beats) + 1)) - tracked) if items else []
    if untracked:
        many = len(untracked) > 1
        problems.append(f"beat{'s' if many else ''} {', '.join(map(str, untracked))} never show{'' if many else 's'} "
                        "the tracker; give the first scene of every beat one")
    for key, name in cast.items():
        last = max((i for i, names in enumerate(in_beat, 1) if key in names), default=None)
        said = _plain(" ".join(s.get("narration") or "" for s in scenes if s.get("beat") == last))
        if last is not None and _plain(name.split()[-1]) not in said:
            problems.append(f"{name}'s part ends in beat {last}, the last beat that lists them, but no line in it "
                            "names them; say there what happens to them")
    return problems


def visual_prompt(text: str) -> list[str]:
    return ["the visual_prompt is empty"] if _blank(text) else []


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

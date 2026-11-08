"""Idea cards, and what's checked in them (prompts/ideas/: all.md for every card, and a brief for each category).

Nothing here says an idea is good. A blind test couldn't pick the reference's winners from their titles better than a coin flip (BUILD.md, What his scripts
taught), so there's no score: these checks turn away what can't be used, and the owner's eye and real views do the rest.

A file of cards is `{"category": "<a brief's name>", "cards": [...]}`. Every card has COMMON's fields and LISTS' lists, and its category's brief adds
its own. A file with no category is the explainers' (phase 42's cards came before there were categories).
"""
import json
import re
from pathlib import Path

from ideas import briefs, reference, taste
from providers import checks

ROOT = Path(__file__).resolve().parent.parent
COMMON = ("topic", "hook", "first_picture", "ending", "shape", "source", "source_url")   # the owner judges by the first second and the last
LISTS = {"terms": (1, 3), "like": (1, 3), "needs": (1, 8)}     # like: his shorts that make the same kind of promise, by their titles
TOPIC_MOST = 100
OLD = "explainers"        # the category of a file written before there were categories


def reference_titles(data_dir: Path) -> list[str]:
    """The reference's titles, which a card mustn't repeat."""
    return [v["title"] for v in reference.raw(data_dir)]


def _has(title: str, term: str) -> bool:
    return re.search(rf"\b{re.escape(term)}(s|es)?\b", title, re.IGNORECASE) is not None


def already_done(terms: list[str], titles: list[str]) -> list[str]:
    """The titles that have all of these terms in them, singular or plural."""
    return [t for t in titles if all(_has(t, term) for term in terms)]


def _items(value) -> list | None:
    return [x for x in value if str(x).strip()] if isinstance(value, list) else None


def problems(cards: list[dict], titles: list[str], brief: briefs.Brief, answered: list[dict] = ()) -> list[str]:
    """What's wrong with these cards, in words. Empty if they can go to the owner. `answered` is the taste file's entries."""
    out, seen = [], {}
    plain_titles = {reference.plain(t) for t in titles}
    spans = {**LISTS, **brief.lists}
    fields = [f for f in (*COMMON, *brief.fields) if f not in spans]
    for n, card in enumerate(cards, 1):
        label = card.get("topic") or f"card {n}"
        for name in dict.fromkeys(fields):
            if not str(card.get(name) or "").strip():
                out.append(f"{label}: {name} has to be there")
        for name, (lo, hi) in spans.items():
            items = _items(card.get(name))
            if items is None or not lo <= len(items) <= hi:
                count = "none" if not items else len(items)
                out.append(f"{label}: {name} has {count}; it needs a list of {lo} to {hi}")
        if len(card.get("topic") or "") > TOPIC_MOST:
            out.append(f"{label}: the topic has to be one line, under {TOPIC_MOST} characters")
        out += [f"{label}: {p}" for p in checks.short_hook(card.get("hook"), card.get("shape"))]
        if card.get("shape") in checks.SHORT_SHAPES and card.get("shape") not in brief.shapes:
            out.append(f"{label}: {brief.name} ideas are built as {', '.join(brief.shapes)}, not {card.get('shape')}")
        if card.get("source_url") and not str(card["source_url"]).startswith("http"):
            out.append(f"{label}: source_url has to be a link someone could check")
        for title in _items(card.get("like")) or []:
            if reference.plain(str(title)) not in plain_titles:
                out.append(f"{label}: like names {title!r}, which isn't one of his titles: copy it from `run.py ideas reference`")
        out += [f"{label}: {p}" for p in taste.problems(card, list(answered))]
        terms = [str(t).strip() for t in card.get("terms") or [] if str(t).strip()]
        if not LISTS["terms"][0] <= len(terms) <= LISTS["terms"][1]:
            continue
        done = already_done(terms, titles)
        if done:
            out.append(f"{label}: the reference has done it: {'; '.join(done[:3])}")
        key = frozenset(t.lower() for t in terms)
        if key in seen:
            out.append(f"{label}: it's the same as {seen[key]}")
        seen[key] = label
    return out


def path_for(data_dir: Path, what: str | None) -> Path:
    """A file of cards from what was asked: a category's own file (data/ideas/<category>/cards.json), a path, or phase 42's file."""
    folder = Path(data_dir) / "ideas"
    if not what:
        return folder / "cards.json"
    if what in briefs.names(ROOT):
        return folder / what / "cards.json"
    return Path(what)


def check_file(path: Path, data_dir: Path, root: Path = ROOT, say=print) -> list[str]:
    """Says what's wrong with a file of cards, or that they passed, with the numbers of the shorts of his each one is like."""
    if not Path(path).exists():
        raise FileNotFoundError(f"there's no file of cards at {path}: give a category ({', '.join(briefs.names(root))}) or a file")
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    brief = briefs.load(root, data.get("category") or OLD)
    videos = reference.raw(data_dir)
    answered = taste.load(Path(root) / "ideas")["entries"]
    cards = data["cards"]
    wrong = problems(cards, [v["title"] for v in videos], brief, answered)
    for line in wrong:
        say(line)
    if wrong:
        return wrong
    judged = reference.shorts(videos)
    say(f"{len(cards)} {brief.name} cards passed: none repeats the reference's titles or what the owner has answered. "
        "That says they can be used, not that they're good.")
    for n, card in enumerate(cards, 1):
        say(f"{n}. {card['topic']}")
        for title in card["like"]:
            v = reference.find(videos, judged, title)
            if v and "x_views" in v:
                say(f"   like \"{v['title']}\": {v['x_views']:.1f}x his median for {v['quarter']}{', in its top tenth' if v['top'] else ''}")
            elif v:
                say(f"   like \"{v['title']}\": too young or too long to judge")
    return wrong

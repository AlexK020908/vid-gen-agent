"""Idea cards, and what's checked in them (prompts/character/ideas.md).

Nothing here says an idea is good. A blind test couldn't pick the reference's winners from their titles better than a coin flip (BUILD.md, What his scripts
taught), so there's no score: these checks turn away what can't be used, and the owner's eye and real views do the rest.
"""
import json
import re
from pathlib import Path

from providers import checks

FIELDS = ("topic", "hook", "people_think", "truth", "turn", "first_picture", "inside", "shape", "source", "source_url")
STEPS = (3, 6)
TERMS = (1, 3)
TOPIC_MOST = 100
REFERENCE = Path("benchmarks") / "idea_study" / "zack_uploads_nov05.json"      # under the data folder: his titles and views, from the YouTube Data API


def reference_titles(data_dir: Path) -> list[str]:
    """The reference's titles, which a card mustn't repeat. Without them nothing can be said to be new, so that stops the check, in words."""
    path = Path(data_dir) / REFERENCE
    if not path.exists():
        raise FileNotFoundError(f"the reference's titles aren't at {path}: run data/benchmarks/idea_study/scripts/channel_titles.py")
    return [v["title"] for v in json.loads(path.read_text(encoding="utf-8"))["videos"]]


def _has(title: str, term: str) -> bool:
    return re.search(rf"\b{re.escape(term)}(s|es)?\b", title, re.IGNORECASE) is not None


def already_done(terms: list[str], titles: list[str]) -> list[str]:
    """The titles that have all of these terms in them, singular or plural."""
    return [t for t in titles if all(_has(t, term) for term in terms)]


def problems(cards: list[dict], titles: list[str]) -> list[str]:
    """What's wrong with these cards, in words. Empty if they can go to the owner."""
    out, seen = [], {}
    for n, card in enumerate(cards, 1):
        label = card.get("topic") or f"card {n}"
        for field in FIELDS:
            if not str(card.get(field) or "").strip():
                out.append(f"{label}: {field} has to be there")
        if len(card.get("topic") or "") > TOPIC_MOST:
            out.append(f"{label}: the topic has to be one line, under {TOPIC_MOST} characters")
        out += [f"{label}: {p}" for p in checks.short_hook(card.get("hook"), card.get("shape"))]
        lo, hi = STEPS
        if not lo <= len(card.get("steps") or []) <= hi:
            out.append(f"{label}: there are {len(card.get('steps') or [])} steps; it needs {lo} to {hi}, each saying what causes what")
        if card.get("source_url") and not str(card["source_url"]).startswith("http"):
            out.append(f"{label}: source_url has to be a link someone could check")
        terms = [str(t).strip() for t in card.get("terms") or [] if str(t).strip()]
        lo, hi = TERMS
        if not lo <= len(terms) <= hi:
            out.append(f"{label}: it needs {lo} to {hi} terms that name what it's about, to check it against the reference's titles")
            continue
        done = already_done(terms, titles)
        if done:
            out.append(f"{label}: the reference has done it: {'; '.join(done[:3])}")
        key = frozenset(t.lower() for t in terms)
        if key in seen:
            out.append(f"{label}: it's the same as {seen[key]}")
        seen[key] = label
    return out


def check_file(path: Path, data_dir: Path, say=print) -> list[str]:
    """Says what's wrong with a file of cards, or how many are fine."""
    cards = json.loads(Path(path).read_text(encoding="utf-8"))["cards"]
    wrong = problems(cards, reference_titles(data_dir))
    for line in wrong:
        say(line)
    if not wrong:
        say(f"{len(cards)} cards passed: none repeats the reference's titles. That says they can be used, not that they're good.")
    return wrong

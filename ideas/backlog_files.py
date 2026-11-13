"""The idea backlog as files the owner can read: one Markdown file a card, in a folder for each category (ideas/backlog/<category>/).

    .venv/Scripts/python -m ideas.backlog_files            (every category that has cards)

A card is written when the taste file has it as taken, or has no answer on it yet. Turned-down cards are left out, and their files removed.
The owner asked for this on Nov 11, 2026: "each of them as its own md file, ill read them all later", "just categorize them into diff categories".
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "ideas" / "backlog"
SKIP = {"topic", "hook", "first_picture", "ending", "terms", "like", "shape", "source", "source_url", "needs", "checker_fixes", "steps", "clues",
        "silent", "mistake", "stake", "seen"}


def slug(topic: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-")[:70]


def answers() -> dict[str, dict]:
    taste = json.loads((ROOT / "ideas" / "taste.json").read_text(encoding="utf-8"))
    return {e.get("idea"): e for e in taste.get("entries", []) if e.get("idea")}


def page(card: dict, category: str, answer: dict | None) -> str:
    said = f'"{" / ".join(answer["their_words"])}" ({answer.get("date")})' if answer and answer.get("their_words") else "not shown to you yet"
    lines = [f"# {card['topic']}", "", f"- **Kind:** {category}, built as `{card.get('shape')}`", f"- **Your answer so far:** {said}", "",
             "## The first second", "", f"**Heard:** {card['hook']}", "", f"**Seen:** {card['first_picture']}", "",
             "## Why someone would stop", ""]
    for name, label in (("silent", "With the sound off"), ("mistake", "What grabs them"), ("stake", "What's at stake"), ("seen", "The answer you watch")):
        if card.get(name):
            lines.append(f"- **{label}:** {card[name]}")
    lines += ["", "## How it goes", ""]
    for name, value in card.items():
        if name in SKIP or not isinstance(value, str) or name == "turn":
            continue
        lines += [f"**{name.replace('_', ' ').capitalize()}:** {value}", ""]
    for name in ("steps", "clues"):
        if card.get(name):
            lines += [f"{n}. {step}" for n, step in enumerate(card[name], 1)] + [""]
    if card.get("turn"):
        lines += [f"**The turn:** {card['turn']}", ""]
    lines += [f"**The ending:** {card['ending']}", ""]
    if card.get("checker_fixes"):
        lines += ["## To settle before it's written", ""] + [f"- {fix}" for fix in card["checker_fixes"]] + [""]
    lines += ["## Where it's known from", "", card.get("source", ""), "", card.get("source_url", ""), ""]
    if card.get("needs"):
        lines += ["## What has to be made", ""] + [f"- {need}" for need in card["needs"]] + [""]
    return "\n".join(lines)


def write(categories: list[str]) -> None:
    known = answers()
    for old in OUT.glob("*.md"):
        old.unlink()                                    # from before there was a folder for each category
    for category in categories:
        source = ROOT / "data" / "ideas" / category / "cards.json"
        if not source.exists():
            continue
        (OUT / category).mkdir(parents=True, exist_ok=True)
        cards = json.loads(source.read_text(encoding="utf-8"))["cards"]
        for card in cards:
            answer = known.get(card["topic"])
            path = OUT / category / f"{slug(card['topic'])}.md"
            if answer and answer.get("verdict") == "turned_down":
                path.unlink(missing_ok=True)
                continue
            path.write_text(page(card, category, answer), encoding="utf-8")
            print(path.relative_to(ROOT))


if __name__ == "__main__":
    write(sys.argv[1:] or sorted(p.name for p in (ROOT / "data" / "ideas").iterdir() if p.is_dir()))

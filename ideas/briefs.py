"""A category's brief (prompts/ideas/<category>.md): the kind of idea a channel wants, what its cards hold, and the words that find the
reference's shorts of that kind. `prompts/ideas/all.md` is what every idea needs, whatever its category.

A brief is Markdown with a YAML block on top:

    ---
    for: the channels it's for
    words: [invent*, machine*]       # the reference's titles with any of these are its kin; a * ends the start of a word
    fields: [goal, steps, invention] # what its cards need besides what every card has (cards.COMMON)
    lists: {steps: [4, 7]}           # how many a field that's a list holds
    shapes: [you_invent, ladder]     # the outline shapes (checks.SHORT_SHAPES) its ideas are built on
    ---

A new category is a new brief, with no code.
"""
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from providers import checks

FOLDER = Path("prompts") / "ideas"
ALL = "all"               # what every idea needs: not a category


class BriefError(ValueError):
    pass


@dataclass(frozen=True)
class Brief:
    name: str
    path: Path
    words: tuple[str, ...]
    fields: tuple[str, ...]
    lists: dict = field(default_factory=dict)
    shapes: tuple[str, ...] = ()
    text: str = ""


def _split(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise BriefError(f"{path} has no YAML block on top: it needs words, fields, lists and shapes between two --- lines")
    _, head, body = text.split("---", 2)
    return yaml.safe_load(head) or {}, body.strip()


def names(root: Path) -> list[str]:
    """Every category there's a brief for."""
    return sorted(p.stem for p in (Path(root) / FOLDER).glob("*.md") if p.stem != ALL)


def load(root: Path, name: str) -> Brief:
    path = Path(root) / FOLDER / f"{name}.md"
    if name == ALL or not path.exists():
        raise BriefError(f"there's no brief for {name!r}: the categories are {', '.join(names(root)) or 'none yet'} (prompts/ideas/<category>.md)")
    head, body = _split(path)
    brief = Brief(name=name, path=path, words=tuple(head.get("words") or ()), fields=tuple(head.get("fields") or ()),
                  lists={k: tuple(v) for k, v in (head.get("lists") or {}).items()}, shapes=tuple(head.get("shapes") or ()), text=body)
    wrong = problems(brief)
    if wrong:
        raise BriefError(f"{path}: " + "; ".join(wrong))
    return brief


def problems(brief: Brief) -> list[str]:
    """What's wrong with a brief's YAML block, in words."""
    out = []
    if not brief.words:
        out.append("it needs words to find the reference's shorts of its kind")
    if not brief.fields:
        out.append("it needs the fields its cards hold")
    for name, span in brief.lists.items():
        if name not in brief.fields:
            out.append(f"lists names {name}, which isn't one of its fields")
        if len(span) != 2 or not 0 < span[0] <= span[1]:
            out.append(f"lists gives {name} {list(span)}: it needs [least, most]")
    if not brief.shapes:
        out.append("it needs the shapes its ideas are built on")
    out += [f"{s} isn't an outline shape ({', '.join(checks.SHORT_SHAPES)})" for s in brief.shapes if s not in checks.SHORT_SHAPES]
    return out

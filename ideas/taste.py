"""The owner's taste, written down (ideas/taste.json, in the repo rather than data/, so a fresh pipeline doesn't lose it): every idea they were
shown or praised, what they did with it, and what they said, word for word, and what they've said about ideas in general (`said`). The idea
researcher reads it before writing anything, and the card check refuses an idea they've turned down, taken, or liked as made.

`their_words` are the owner's and nobody else's, typos and all. `reading` is the session's reading of them, and is marked as such wherever
it's shown, since a reading can be wrong where their words can't.
"""
import datetime as dt
import json
from pathlib import Path

FILE = "taste.json"
VERDICTS = ("liked", "took", "turned_down", "offered")
BLOCKS = {"liked": "the owner liked {idea!r} as made ({date}): don't make it again; find another with what made it good",
          "took": "the owner took {idea!r} on {date}: it's being made",
          "turned_down": "the owner turned down {idea!r} on {date}, last saying {words} (all they said: run.py ideas taste)"}
QUOTE_MOST = 160          # characters of their last word on it, in a refusal
ABOUT = ("Every idea the owner was shown or praised, what they did with it, and what they said, word for word. `their_words` are theirs; "
         "`reading` is the session's reading of them, not theirs. Read all of it before proposing anything: never bring back what they turned "
         "down, or another idea with the same flaw.")


def path(folder: Path) -> Path:
    return Path(folder) / FILE


def load(folder: Path) -> dict:
    p = path(folder)
    if not p.exists():
        return {"about": ABOUT, "entries": []}
    return json.loads(p.read_text(encoding="utf-8"))


def _save(folder: Path, data: dict) -> None:
    Path(folder).mkdir(parents=True, exist_ok=True)
    path(folder).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def _stem(term: str) -> str:
    t = " ".join(str(term).lower().split())
    if t.endswith("es") and len(t) > 4:
        return t[:-2]
    if t.endswith("s") and len(t) > 3:
        return t[:-1]
    return t


def _words(terms: list[str]) -> set[str]:
    return {_stem(w) for t in terms for w in str(t).split()}


def same(a: list[str], b: list[str]) -> bool:
    """Whether two ideas' terms name one subject: one's words are all among the other's, singular or plural ("steam engine" and "engine" do;
    "steam engine" and "steam locomotive" don't)."""
    sa, sb = _words(a), _words(b)
    return bool(sa and sb) and (sa <= sb or sb <= sa)


def problems(card: dict, entries: list[dict]) -> list[str]:
    """Why the owner has already answered this idea, in words. An idea that was only offered, with no answer, isn't refused."""
    out = []
    for e in entries:
        if e.get("verdict") in BLOCKS and same(card.get("terms") or [], e.get("terms") or []):
            last = (e.get("their_words") or [""])[-1]
            words = f'"{last[:QUOTE_MOST]}{"..." if len(last) > QUOTE_MOST else ""}"' if last else "nothing recorded"
            out.append(BLOCKS[e["verdict"]].format(idea=e.get("idea", ""), date=e.get("date", "?"), words=words))
    return out


def add(folder: Path, entry: dict) -> dict:
    """One more of the owner's answers, dated today unless it says otherwise."""
    if entry.get("verdict") not in VERDICTS:
        raise ValueError(f"a verdict is one of {', '.join(VERDICTS)}, not {entry.get('verdict')!r}")
    if not str(entry.get("idea") or "").strip():
        raise ValueError("an answer needs the idea it's about")
    entry = {"date": dt.date.today().isoformat(), **entry}
    data = load(folder)
    data.setdefault("about", ABOUT)
    data.setdefault("entries", []).append(entry)
    _save(folder, data)
    return entry


def verdict(folder: Path, cards_path: Path, number: int, answer: str, words: str = "", reading: str = "") -> dict:
    """The owner's answer on card `number` (from 1) of a file of cards, with what they said, kept with the whole card."""
    data = json.loads(Path(cards_path).read_text(encoding="utf-8"))
    cards = data["cards"]
    if not 1 <= number <= len(cards):
        raise ValueError(f"{cards_path} has {len(cards)} cards, numbered from 1, so there's no card {number}")
    card = cards[number - 1]
    entry = {"category": data.get("category", ""), "verdict": answer, "idea": card.get("topic", ""), "their_words": [words] if words else [],
             "terms": card.get("terms") or [], "card": card}
    if reading:
        entry["reading"] = reading
    return add(folder, entry)


def show(folder: Path, say=print) -> None:
    """The taste file to read: what they've said about ideas, then what they liked, took, turned down, and were offered with no answer, in their
    words."""
    data = load(folder)
    entries = data["entries"]
    if not entries and not data.get("said"):
        say(f"nothing yet in {path(folder)}")
        return
    if data.get("said"):
        say("## What the owner has said about ideas")
        for s in data["said"]:
            say(f'- {s.get("date", "?")}, {s.get("about", "")}: "{s["their_words"]}"')
    heads = {"liked": "Liked, as made", "took": "Taken", "turned_down": "Turned down", "offered": "Offered, with no answer either way"}
    for kind in VERDICTS:
        group = [e for e in entries if e.get("verdict") == kind]
        if not group:
            continue
        say(f"## {heads[kind]} ({len(group)})")
        for e in group:
            say(f"- {e.get('date', '?')} [{e.get('category') or '-'}] {e['idea']}")
            if e.get("pitch"):
                say(f"  shown as: {e['pitch']}")
            for w in e.get("their_words") or []:
                say(f'  the owner: "{w}"')
            if e.get("reading"):
                say(f"  our reading, not theirs: {e['reading']}")
            if e.get("note"):
                say(f"  note: {e['note']}")

"""The reference's own shorts as evidence: which of them are like an idea, and how far above or below his median they did.

Never a score. Blind judges couldn't pick his winners from their titles better than a coin flip (BUILD.md, What his scripts taught), so this
shows what kind of promise his hits made and how they did, for the owner and the idea researcher to weigh. It never says an idea will win.

Each short is set against its own quarter, since his median went from 9M to 31M and back: a 2024 hit and a 2026 hit aren't on one scale. His
few long videos are left out, and so is anything too young to have its views yet.
"""
import datetime as dt
import json
import math
import re
import statistics
from collections import defaultdict
from pathlib import Path

REFERENCE = Path("benchmarks") / "idea_study" / "zack_uploads_nov05.json"   # under the data folder: his titles and numbers, from the YouTube Data API
SHORT_MOST_S = 180        # a short; the dozen long videos he's posted are left out
YOUNG_DAYS = 28           # younger than this when the list was fetched, and its views are still climbing
TOP = 9                   # his top tenth: at or above the ninth tenth of its own quarter's views
Z90 = 1.645               # a 90% interval round a share, so a handful of videos isn't read as a pattern
COUNTS = ("views", "likes", "comments")


def raw(data_dir: Path) -> list[dict]:
    """Every upload in the reference's list. Without it nothing can be said to be new or like his, so that stops what asked, in words."""
    path = Path(data_dir) / REFERENCE
    if not path.exists():
        raise FileNotFoundError(f"the reference's titles aren't at {path}: run data/benchmarks/idea_study/scripts/channel_titles.py")
    return json.loads(path.read_text(encoding="utf-8"))["videos"]


def _quarter(day: str) -> str:
    year, month, _ = day.split("-")
    return f"{year}Q{(int(month) - 1) // 3 + 1}"


def plain(title: str) -> str:
    """A title as words only: no emoji, no punctuation, any case. A title copied from a terminal that can't print emoji still matches."""
    return " ".join(re.sub(r"[^a-z0-9]+", " ", title.lower()).split())


def shorts(videos: list[dict]) -> list[dict]:
    """His shorts old enough to judge, each with its quarter, its counts as times its quarter's median, and whether it's in that quarter's top tenth."""
    fetched = max(dt.date.fromisoformat(v["published"]) for v in videos)        # the list has no fetch date; its newest upload is within a day of it
    oldest = fetched - dt.timedelta(days=YOUNG_DAYS)
    kept = [v for v in videos if v["seconds"] <= SHORT_MOST_S and dt.date.fromisoformat(v["published"]) <= oldest]
    by_quarter = defaultdict(list)
    for v in kept:
        by_quarter[_quarter(v["published"])].append(v)
    out = []
    for quarter, group in by_quarter.items():
        medians = {c: statistics.median(v[c] for v in group) or 1 for c in COUNTS}
        line = (statistics.quantiles([v["views"] for v in group], n=10, method="inclusive")[TOP - 1]     # inside the quarter's own range
                if len(group) > 1 else group[0]["views"])
        out += [{**v, "quarter": quarter, **{f"x_{c}": v[c] / medians[c] for c in COUNTS}, "top": v["views"] >= line} for v in group]
    return out


def _pattern(word: str) -> re.Pattern:
    """A word as a whole word, singular or plural; ending in * it's the start of a word (invent* finds invented and invention)."""
    w = word.strip()
    if w.endswith("*"):
        return re.compile(rf"\b{re.escape(w[:-1])}", re.IGNORECASE)
    return re.compile(rf"\b{re.escape(w)}(s|es)?\b", re.IGNORECASE)


def kin(videos: list[dict], words: list[str]) -> list[dict]:
    """The shorts with any of these words in their titles, best first."""
    patterns = [_pattern(w) for w in words if w.strip()]
    return sorted((v for v in videos if any(p.search(v["title"]) for p in patterns)), key=lambda v: -v["x_views"])


def share(hits: int, n: int) -> tuple[float, float, float]:
    """A share and the 90% interval round it (Wilson's), so 3 of 8 isn't taken for 37% of everything."""
    if not n:
        return 0.0, 0.0, 1.0
    p = hits / n
    middle = (p + Z90 ** 2 / (2 * n)) / (1 + Z90 ** 2 / n)
    half = Z90 * math.sqrt(p * (1 - p) / n + Z90 ** 2 / (4 * n * n)) / (1 + Z90 ** 2 / n)
    return p, max(0.0, middle - half), min(1.0, middle + half)


def summary(found: list[dict], everything: list[dict]) -> dict:
    """How the found shorts did together, beside all of his: their middle, and how many reached their quarter's top tenth."""
    top = sum(v["top"] for v in found)
    p, low, high = share(top, len(found))
    return {"n": len(found), "of": len(everything), "median_x": statistics.median(v["x_views"] for v in found) if found else 0.0,
            "top": top, "top_share": p, "low": low, "high": high, "base": sum(v["top"] for v in everything) / max(1, len(everything))}


def line(v: dict) -> str:
    return (f"{v['x_views']:5.1f}x views {v['x_likes']:4.1f}x likes {v['x_comments']:4.1f}x comments  {v['views'] / 1e6:6.1f}M  "
            f"{v['published']}  {v['title']}")


def find(videos: list[dict], judged: list[dict], title: str) -> dict | None:
    """One of his uploads by its title, with its numbers if it's a short old enough to judge (`x_views` is missing when it isn't)."""
    want = plain(title)
    for v in judged:
        if plain(v["title"]) == want:
            return v
    for v in videos:
        if plain(v["title"]) == want:
            return v
    return None


def show(data_dir: Path, words: list[str], name: str = "", top: int = 25, say=print) -> dict:
    """His shorts with these words, best first, against his median for their quarter, and how they did together beside all of his."""
    everything = shorts(raw(data_dir))
    found = kin(everything, words)
    s = summary(found, everything)
    say(f"{name or 'these words'}: his shorts with {', '.join(words)} in the title: {s['n']} of {s['of']:,} ({s['n'] / max(1, s['of']):.0%})")
    if not found:
        say("none: either it's free ground, or the words are wrong. Try the words a title would use.")
        return s
    say(f"  their middle: {s['median_x']:.2f}x his median for their quarter. In his top tenth: {s['top']} of {s['n']}, "
        f"{s['top_share']:.0%} (likely {s['low']:.0%} to {s['high']:.0%}), against {s['base']:.0%} for all his shorts")
    say(f"  the {min(top, len(found))} best, then the {min(5, max(0, len(found) - top))} worst:")
    for v in found[:top]:
        say("  " + line(v))
    if len(found) > top:
        say("  ...")
        for v in found[-min(5, len(found) - top):]:
            say("  " + line(v))
    say("A lean, not a score: blind judges couldn't pick his winners from titles. Read what each promises in its first second, and never reuse his "
        "titles or wording.")
    return s


# ---------------------------------------------------------------------------------------------------------------- the whole catalogue, by kind
def _opens(*openings: str):
    return lambda title: any(title == o or title.startswith(o + " ") for o in openings)


def _has(*words: str):
    patterns = [_pattern(w) for w in words]
    return lambda title: any(p.search(title) for p in patterns)


# The kinds of short he posts, told from a title alone: how it opens, or a word in it. A first map and not a careful sort: a title says only part
# of what a short is, kinds overlap, and about half his titles open in none of these ways.
KINDS = {
    "explainers: how it works": lambda title: _opens("how", "inside")(title) and not _opens("how to")(title),
    "explainers: why": _opens("why"),
    "what ifs": _opens("what if", "what happens", "what would", "if you", "if a", "if the"),
    "tests: can it, could you": _opens("can", "could", "would", "does", "do", "should", "is it possible"),
    "advice: how to, what to do if": _opens("how to", "what to do", "never", "don t", "do not"),
    "a person's story": _opens("he", "she", "they", "his", "her", "man", "woman", "a man", "a woman", "the man", "the woman", "the boy", "the girl", "the guy",
                               "this man", "this woman", "this boy", "this girl", "this guy"),
    "crime": _has("murder*", "kill*", "robb*", "heist*", "stole", "steal*", "thief", "thieves", "prison*", "jail*", "serial", "scam*", "fraud*", "fake*",
                  "kidnap*", "police", "cop", "fbi", "criminal*", "smuggl*", "cartel*", "hitman", "assassin*", "poison*", "crime*", "arrest*", "bank"),      # not "escape": he escapes gorilla exhibits and sinking cars far more than prisons
    "trapped and survival": _has("cave", "caver*", "trapped", "stuck", "drown*", "diver*", "rescue*", "surviv*", "lost", "strand*", "sank", "sink*", "crash*",
                                 "buried", "avalanche*", "shipwreck*"),
    "mystery": _has("myster*", "unsolved", "vanish*", "disappear*", "creepy", "haunted", "curse*", "secret*", "strange*", "weird*", "bizarre"),
    "war and old history": _has("war", "wars", "ww2", "wwii", "soldier*", "army", "nazi*", "ancient", "medieval", "roman*", "viking*", "samurai*", "knight*",
                                "sword*", "castle*", "pirate*", "egypt*", "pharaoh*", "titanic", "bomb*", "tank*", "sniper*"),
    "the body and medicine": _has("body", "brain*", "heart*", "blood", "teeth", "tooth", "stomach*", "eye*", "skin", "bone*", "surgery", "surgeon*", "doctor*",
                                  "disease*", "virus*", "lung*", "poop*", "pee", "sleep*", "die*", "death*", "dead", "pain*", "hair"),
    "animals": _has("animal*", "dog*", "cat*", "shark*", "snake*", "bear*", "whale*", "spider*", "bird*", "fish*", "horse*", "cow*", "pig*", "elephant*", "lion*",
                    "tiger*", "monkey*", "gorilla*", "ant*", "bee*", "crocodile*", "octopus*", "rat*", "mouse", "mice", "wolf", "wolves", "insect*", "bug*",
                    "turtle*", "frog*", "chicken*", "dinosaur*"),
    "machines and inventions": _has("invent*", "machine*", "engine*", "robot*", "phone*", "car", "cars", "plane*", "airplane*", "train*", "ship*", "submarine*",
                                    "rocket*", "elevator*", "bridge*", "factory*", "tunnel*", "skyscraper*", "building*", "gun*", "bullet*", "lock*", "toilet*", "atm"),
    "space": _has("space", "astronaut*", "moon", "mars", "planet*", "sun", "earth", "black hole*", "nasa", "asteroid*"),
    "food": _has("food*", "eat*", "ate", "cook*", "mcdonald*", "candy", "chocolate", "meat", "egg*", "milk", "cheese", "pizza", "burger*", "sugar", "salt",
                 "coffee", "gum"),
}


def kinds(judged: list[dict]) -> list[dict]:
    """Each kind of short among his: how many, their middle against his median for their quarter, and how many reached that quarter's top tenth."""
    rows = []
    for name, is_one in KINDS.items():
        found = [v for v in judged if is_one(plain(v["title"]))]
        rows.append({"kind": name, "found": found, **summary(found, judged)})
    return rows


def catalogue(data_dir: Path, top: int = 25, say=print) -> list[dict]:
    """Everything he posts, by kind, and his best shorts of all: what he makes most, and what does better or worse than his usual."""
    judged = shorts(raw(data_dir))
    rows = kinds(judged)
    base = rows[0]["base"] if rows else 0.0
    say(f"his {len(judged):,} shorts by kind (kinds overlap). Any short reaches his top tenth {base:.0%} of the time.")
    for row in rows:
        if not row["n"]:
            continue
        say(f"  {row['kind']:30s} {row['n']:5,} ({row['n'] / len(judged):4.0%} of all)   middle {row['median_x']:.2f}x   top tenth {row['top_share']:4.0%} "
            f"(likely {row['low']:.0%} to {row['high']:.0%})")
    say(f"  his {top} best, each against its own quarter:")
    for v in sorted(judged, key=lambda v: -v["x_views"])[:top]:
        say("  " + line(v))
    say("A lean, not a score: a kind whose likely range sits wholly above or below the top-tenth rate for all his shorts is the only kind that "
        "differs from his usual. These are his YouTube counts, sorted by title words alone.")
    return rows

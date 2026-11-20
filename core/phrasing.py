"""Where a caption breaks: between phrases, never inside one.

A caption is read on its own, so one that stops halfway through a phrase says something else. On the microwave short
(Nov 15, 2026) the transition checker caught "So you keep metal" standing alone for a second, the opposite of "...out",
and "The waves slosh loose", which reads as the waves sloshing loosely; the frame reviewer caught "The metal walls
around" then "it don't.". So a caption breaks after punctuation, or before a word that starts a phrase ("in", "and",
"the", "which"), never after a word that leans on the next ("the", "into", "its", "can't"), and never inside a fixed
pair ("back and forth").
"""
from __future__ import annotations

import math

PUNCTUATION = ".,?!;:"

# a word that leans on the one after it: a caption never ends on one
LEANS = frozenset("""
a an the my your its his her our their this that these those some any no every each both all another other such
what which whose who whom when where while if as than so but and or nor because until unless though although
in into inside outside on onto upon at by for from of to with without within around about above below beneath under
underneath over through throughout across along among against between behind beside beyond near past toward towards
like via per during since despite except
can can't cannot could couldn't will won't would wouldn't shall should shouldn't may might must
is isn't are aren't was wasn't were weren't be been being am has hasn't have haven't had hadn't
do does doesn't did didn't don't not very too more most less much many few
one two three four five six seven eight nine ten twenty hundred thousand million billion
""".split())

# a word a phrase starts with: a caption may break just before one
STARTS = frozenset("""
a an the my your its his her our their this that these those some any no every each both all
and or but so nor because until unless though although which who whom whose where when while if as than then
in into inside outside on onto upon at by for from of to with without within around about above below beneath under
underneath over through throughout across along among against between behind beside beyond near past toward towards
like via during since despite except
""".split())

# pairs read as one thing: never split inside them
FIXED = [tuple(p.split()) for p in """back and forth|up and down|in and out|on and off|round and round|over and over|again and again
more and more|each other|one another|a few|a lot|at least|at all|of course|as well|so far|and so on""".split("|")]

LEANING, NEUTRAL = 10.0, 3.0


def _bare(word: str) -> str:
    return word.lower().replace("’", "'").strip("\"'()[]“”" + PUNCTUATION)


def ends(word: str) -> bool:
    """Does the word close a clause (a comma, a full stop, a question mark...), allowing for a closing quote after it?"""
    return word.rstrip().rstrip("\"')”’")[-1:] in PUNCTUATION


def costs(words: list[str]) -> list[float]:
    """What it costs to break a caption just before each word (the first is never a break, so it's 0): nothing after
    punctuation or before a word that starts a phrase, a lot after a word that leans on the next or inside a fixed pair,
    and something in between."""
    bare = [_bare(w) for w in words]
    out = [0.0] * len(words)
    for j in range(1, len(words)):
        out[j] = (0.0 if ends(words[j - 1]) else LEANING if bare[j - 1] in LEANS else 0.0 if bare[j] in STARTS else NEUTRAL)
    for pair in FIXED:
        for i in range(len(words) - len(pair) + 1):
            if tuple(bare[i:i + len(pair)]) == pair:
                for j in range(i + 1, i + len(pair)):
                    out[j] = max(out[j], LEANING)
    return out


def split(words: list[str], most: int, widest: int = 40) -> list[list[str]]:
    """Words as captions of at most `most` words and `widest` characters, broken where it costs least: between phrases
    (`costs`), into as few captions as read well, a full one costing a little more than one with room, and a word left
    on its own costing a lot. Punctuation inside the words is only a cheap place to break; a caller that always breaks
    there passes one clause at a time."""
    n = len(words)
    if n == 0:
        return []
    breaks = costs(words)
    best, back = [0.0] + [math.inf] * n, [0] * (n + 1)     # best[j]: the cheapest captions for words[:j]
    for j in range(1, n + 1):
        for i in range(max(0, j - most), j):
            piece = words[i:j]
            if len(piece) > 1 and len(" ".join(piece)) > widest:
                continue
            here = best[i] + 1.5 + (1.0 if len(piece) == most else 0.0) + (4.0 if len(piece) == 1 and n > 1 else 0.0)
            here += breaks[j] if j < n else 0.0
            if here < best[j]:
                best[j], back[j] = here, i
    out, j = [], n
    while j > 0:
        out.append(words[back[j]:j])
        j = back[j]
    return out[::-1]

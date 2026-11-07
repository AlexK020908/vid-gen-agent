"""Where ideas come from: things that are written down with their sources, and what people actually ask. Free, with no account.

- Wikipedia's lists of common misconceptions: what nearly everyone believes, what's true, and a citation for it.
- Wikipedia's list of Ig Nobel winners: real studies of absurd things, which is where a silly setup answered with real science comes from.
- YouTube's search suggestions: the questions people type. Most of it's noise, and it says nothing about how a short would do.

A lead isn't an idea. The session reads these and writes cards (ideas/cards.py).
"""
import json
import string
import time
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

AGENT = {"User-Agent": "StickFleet-research/1.0"}
WIKIPEDIA = "https://en.wikipedia.org/w/api.php?"
SUGGEST = "https://suggestqueries.google.com/complete/search?"
PAGES = ("List of common misconceptions about science, technology, and mathematics",
         "List of common misconceptions about history",
         "List of Ig Nobel Prize winners")
ASKED = ("why does your", "why do we", "why do humans", "why do animals", "why can't humans", "what happens if you",
         "what happens to your body if", "what would happen if", "how do animals", "could you survive", "how does a")
LEFT_OUT = {"see also", "references", "notes", "further reading", "external links", "bibliography", "citations", "sources"}
LEAST = 40                # characters: anything shorter is a stray line, not a lead
WAIT_S = 0.1              # between suggestion requests, to be polite


def _get(url: str) -> str:
    with urllib.request.urlopen(urllib.request.Request(url, headers=AGENT), timeout=30) as reply:
        return reply.read().decode("utf-8", "replace")


class _Reader(HTMLParser):
    """A page's sections, paragraphs, list items and table rows. The plain text Wikipedia offers leaves tables out, and the Ig Nobel winners since 2001 are in tables."""
    LEADS, HEADS, SKIP = {"p", "li", "tr"}, {"h2", "h3", "h4"}, {"sup", "style", "script"}

    def __init__(self, page: str):
        super().__init__()
        self.page, self.section, self.found, self.now, self.head, self.skipping = page, "", [], [], None, 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skipping += 1
        elif tag in self.HEADS:
            self.head = []
        elif tag in ("td", "th") and self.now:
            self.now.append(" | ")

    def handle_endtag(self, tag):
        if tag in self.SKIP:
            self.skipping = max(0, self.skipping - 1)
        elif tag in self.HEADS and self.head is not None:
            self.section, self.head = " ".join("".join(self.head).split()), None
        elif tag in self.LEADS:
            text = " ".join("".join(self.now).split())
            self.now = []
            if len(text) >= LEAST and self.section.lower() not in LEFT_OUT:
                self.found.append({"page": self.page, "section": self.section, "text": text})

    def handle_data(self, data):
        if not self.skipping:
            (self.head if self.head is not None else self.now).append(data)


def paragraphs(page: str, html: str) -> list[dict]:
    """A page as leads, each with the section it's in, leaving out its references and the like."""
    reader = _Reader(page)
    reader.feed(html)
    return reader.found


def _wikipedia(page: str) -> list[dict]:
    url = WIKIPEDIA + urllib.parse.urlencode({"action": "parse", "prop": "text", "redirects": 1, "disableeditsection": 1, "page": page, "format": "json", "formatversion": 2})
    return paragraphs(page, json.loads(_get(url))["parse"]["text"])


def _suggestions(stem: str) -> list[str]:
    url = SUGGEST + urllib.parse.urlencode({"client": "firefox", "ds": "yt", "q": stem})
    return json.loads(_get(url))[1]


def fetch(folder: Path, say=print) -> Path:
    """Every source, into `folder`/leads.json. A source that doesn't answer is said and left out, rather than stopping the rest."""
    found, asked, failed = [], set(), []
    for page in PAGES:
        try:
            found += _wikipedia(page)
        except OSError as e:
            failed.append(f"{page}: {e}")
    for stem in ASKED:
        for letter in string.ascii_lowercase:
            try:
                asked.update(_suggestions(f"{stem} {letter}"))
            except (OSError, ValueError) as e:
                failed.append(f"{stem} {letter}: {e}")
            time.sleep(WAIT_S)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "leads.json"
    path.write_text(json.dumps({"fetched_at": time.time(), "written": found, "asked": sorted(asked), "failed": failed}, ensure_ascii=False, indent=0), encoding="utf-8")
    say(f"{len(found)} written leads and {len(asked)} questions in {path}")
    for line in failed[:5]:
        say(f"  didn't answer: {line}")
    return path


def show(folder: Path, page: str = "", width: int = 240, say=print) -> None:
    """The leads to read, cut short: `page` narrows them to the pages with that in their name, and "asked" gives the questions."""
    path = folder / "leads.json"
    if not path.exists():
        raise FileNotFoundError(f"there are no leads in {folder} yet: run `run.py ideas fetch`")
    data = json.loads(path.read_text(encoding="utf-8"))
    if page == "asked":
        for question in data["asked"]:
            say(question)
        return
    section = None
    for lead in data["written"]:
        if page.lower() in lead["page"].lower():
            if lead["section"] != section:
                section = lead["section"]
                say(f"## {section}")
            say(lead["text"][:width])

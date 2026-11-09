"""A systems short's spec: what the agent writes, and the checks it has to pass before anything's drawn.

A spec is JSON:

  title      the short's title in capitals ("HOW LOAD BALANCING WORKS")
  layout     how the nodes are placed (LAYOUTS): pipeline, fan_out and fan_in run left to right by how far a node is
             from where traffic starts; layers runs top to bottom the same way; hub puts the first node in the middle
             and the rest round it; ring puts them all on a circle; grid in rows. Code places everything, in the
             nodes' order
  beat       the music's tempo (BPM, default 120): requests leave and land on its sixteenth notes
  nodes      [{id, icon (ICONS), label, tone (NODE_TONES), capacity (requests a second it serves; leave it out for
             one that passes them straight on), ms (how long it takes to do its part for one request, in ms: a request's
             time is every node's it went through, once more for each request waiting ahead of it there), count (false
             hides its counter)}]
  edges      [[a, b], ...]: every line the short ever draws
  stats      the pills under the title, at most three: {name, unit, measure (MEASURES), ...}
               response   with `ms` on the nodes, the average time of the last four requests answered (plus
                          `base`, the network); without, base + per_queued x every request waiting anywhere
               up         how many of `of` are on screen and not dead
               count      how many requests have reached `of`
               hits       the share of the last eight requests a cache answered, in %
               rate       requests a second leaving `of`
               values     one value per phase, given
             `good` and `bad` colour it (green at or past good, red at or past bad, orange between); lower is better
             unless `higher_better`
  phases     what happens, in order, each with:
               seconds    how long it lasts
               caption    {text, tone (CAPTION_TONES)}: the one line under the diagram
               subtitle   the grey line under the title
               show       the nodes on screen
               edges      the lines on screen (in a first phase, every edge between the nodes shown)
               state      {node: state (STATES)}
               traffic    [{from, to: [nodes], via: [nodes], rate, route (ROUTES), ratio, back}]
               code       {language, lines, bind}: the panel. `bind` lights lines as a request goes through the code:
                          {node: line} when a request reaches the node, "hit" and "miss" when a cache answers it or
                          doesn't, "node:back" when its answer comes back through the node; a list of lines lights
                          them a sixteenth note apart. Every request blinks each line it runs the moment its dot gets
                          there, and each blink is its sound: with code on screen, nothing else ticks. So every node
                          a request reaches needs a line. A dead node's lines dim
               stats      the pills shown
               follow     which request the diagram follows, one at a time, ringed, with its badges and its code
                          lines lit: any (the default), hit, miss, lost, or a node it reaches. Make it what the
                          caption says ("A hit answers in 20 ms": hit)
             Everything but seconds, caption and follow carries on from the phase before until a phase changes it.
  badges     drawn by code under a node, never written: HIT or MISS at a cache, LOST where a request is lost, and
             with `ms` on the nodes, the time at the node a request ends at and the whole trip's time when its answer
             gets back
  end        the end card: {stat, claim, note, seconds}. Its two numbers are the stat's worst and its last, as shown
             on the pill, so they always agree with what was on screen. The short then crossfades to its first frame,
             so it loops.
"""
from __future__ import annotations

import re

ICONS = ("client", "users", "browser", "phone", "dns", "cdn", "api_gateway", "load_balancer", "server", "function",
         "worker", "queue", "cache", "database", "replica", "storage", "auth", "region")
LAYOUTS = ("pipeline", "fan_out", "fan_in", "layers", "hub", "ring", "grid")
STATES = ("healthy", "busy", "warning", "failing", "dead", "cold")
ROUTES = ("direct", "round_robin", "least_connections", "hash", "random", "failover", "cache_hit", "broadcast")
NODE_TONES = ("green", "blue", "orange", "purple", "teal", "red", "grey", "yellow")
CAPTION_TONES = {"white": "the setup", "orange": "trouble", "blue": "an action", "green": "it working",
                 "red": "a failure"}
MEASURES = ("response", "up", "count", "hits", "rate", "values")
LANGUAGES = ("nginx", "python", "javascript", "typescript", "go", "java", "rust", "yaml", "json", "sql", "bash",
             "http", "dockerfile", "ini", "text")

MOST_NODES = 9
MOST_PHASES = 10
MOST_STATS = 3
MOST_STREAMS = 3
CAPTION_WORDS = 6
CLAIM_WORDS = 8
NOTE_CHARS = 48
TITLE_CHARS = 32
SUBTITLE_CHARS = 44
LABEL_CHARS = 16
STAT_CHARS = 10
CODE_CHARS = 32
CODE_LINES = 6
PHASE_SECONDS = (0.8, 8.0)
END_SECONDS = (1.5, 4.0)
SHORTEST, LONGEST = 15.0, 45.0
RATES = (0.5, 8.0)
ID = re.compile(r"^[a-z][a-z0-9_]{0,23}$")
CARRIED = ("subtitle", "show", "edges", "state", "traffic", "code", "stats")


BEAT_RATES = "8, 4, 2.67, 2, 1.6, 1.33, 1.14, 1, 0.8, 0.67 or 0.5"   # at 120 BPM, the default


def on_beat(rate: float, beat: float = 120.0) -> float:
    """What a rate becomes once requests leave (or are served) on sixteenth notes."""
    grid = 60.0 / beat / 4
    steps = max(1, round(1.0 / rate / grid))
    return round(1.0 / (steps * grid), 2)


def _key(a: str, b: str) -> tuple[str, str]:
    return (a, b) if a <= b else (b, a)


def _list(v) -> list:
    if v is None:
        return []
    return list(v) if isinstance(v, (list, tuple)) else [v]


def resolved(spec: dict) -> list[dict]:
    """Every phase with what it carries on from the phases before it filled in, and its start and end in seconds."""
    nodes = [n["id"] for n in spec.get("nodes") or [] if isinstance(n, dict) and "id" in n]
    stats = [s["name"] for s in spec.get("stats") or [] if isinstance(s, dict) and "name" in s]
    out, t = [], 0.0
    cur: dict = {"subtitle": "", "show": [], "edges": [], "state": {}, "traffic": [], "code": None, "stats": stats}
    for i, raw in enumerate(spec.get("phases") or []):
        p = dict(raw) if isinstance(raw, dict) else {}
        nxt = dict(cur)
        nxt["state"] = dict(cur["state"])
        for field in CARRIED:
            if field in p:
                nxt[field] = dict(cur["state"], **(p[field] or {})) if field == "state" else p[field]
        nxt["show"] = [n for n in _list(nxt["show"]) if n in nodes] if i or "show" in p else []
        if i == 0 and "edges" not in p:
            shown = set(nxt["show"])
            nxt["edges"] = [e for e in spec.get("edges") or [] if isinstance(e, (list, tuple)) and len(e) == 2
                            and e[0] in shown and e[1] in shown]
        nxt["edges"] = [list(e) for e in _list(nxt["edges"]) if isinstance(e, (list, tuple)) and len(e) == 2]
        nxt["traffic"] = [s for s in _list(nxt["traffic"]) if isinstance(s, dict)]
        seconds = float(p.get("seconds") or 0)
        nxt.update(index=i, start=round(t, 4), end=round(t + seconds, 4), seconds=seconds,
                   caption=p.get("caption") or {}, raw=p)
        out.append(nxt)
        cur = nxt
        t += seconds
    return out


def stream_targets(stream: dict) -> list[str]:
    return [str(x) for x in _list(stream.get("to"))]


def route_of(stream: dict) -> str:
    return stream.get("route") or ("direct" if len(stream_targets(stream)) == 1 else "round_robin")


def words(text: str) -> int:
    return len([w for w in re.split(r"\s+", str(text or "").strip()) if w and w not in ("·", "-", "→", "—")])


def problems(spec) -> list[str]:
    """What's wrong with a spec, each said so it can be fixed; [] when it can be drawn. Geometry (whether things fit
    and don't overlap) is layout.problems, once this passes."""
    if not isinstance(spec, dict):
        return ["the spec isn't a JSON object"]
    out: list[str] = []
    title = str(spec.get("title") or "")
    if not title.strip():
        out.append("there's no title")
    elif len(title) > TITLE_CHARS:
        out.append(f"the title is {len(title)} characters; at most {TITLE_CHARS} fit on one line")
    elif title != title.upper():
        out.append("the title goes in capitals")
    if spec.get("layout") not in LAYOUTS:
        out.append(f"layout {spec.get('layout')!r} isn't one of {', '.join(LAYOUTS)}")
    beat = spec.get("beat", 120)
    if not isinstance(beat, (int, float)) or not 80 <= beat <= 160:
        out.append("beat is the music's tempo, 80 to 160 BPM")

    nodes = spec.get("nodes")
    ids: list[str] = []
    if not isinstance(nodes, list) or not nodes:
        out.append("there are no nodes")
        nodes = []
    if len(nodes) > MOST_NODES:
        out.append(f"{len(nodes)} nodes; at most {MOST_NODES} fit on a phone")
    for n in nodes:
        if not isinstance(n, dict):
            out.append("a node isn't an object")
            continue
        nid = str(n.get("id") or "")
        if not ID.match(nid):
            out.append(f"node id {nid!r} must be short, lower case, letters, digits and _")
        if nid in ids:
            out.append(f"two nodes are called {nid}")
        ids.append(nid)
        if n.get("icon") not in ICONS:
            out.append(f"{nid}: icon {n.get('icon')!r} isn't one of {', '.join(ICONS)}")
        label = str(n.get("label") or "")
        if not label.strip():
            out.append(f"{nid} has no label")
        elif len(label) > LABEL_CHARS:
            out.append(f"{nid}'s label is {len(label)} characters; at most {LABEL_CHARS}")
        if n.get("tone", "blue") not in NODE_TONES:
            out.append(f"{nid}: tone {n.get('tone')!r} isn't one of {', '.join(NODE_TONES)}")
        cap = n.get("capacity")
        if cap is not None and (not isinstance(cap, (int, float)) or not 0.5 <= cap <= 16):
            out.append(f"{nid}: capacity is requests a second it serves, 0.5 to 16")
        elif cap and abs(on_beat(cap) - cap) > 0.06 * cap:
            out.append(f"{nid}: capacity {cap} would run as {on_beat(cap):g} a second. A node serves one request "
                       f"every so many sixteenth notes, so a capacity is one of {BEAT_RATES}")
        ms = n.get("ms")
        if ms is not None and (not isinstance(ms, (int, float)) or not 0 <= ms <= 5000):
            out.append(f"{nid}: ms is how long it takes for one request, 0 to 5000")

    edges = spec.get("edges")
    known: set[tuple[str, str]] = set()
    if not isinstance(edges, list):
        out.append("edges is a list of [a, b] pairs")
        edges = []
    for e in edges:
        if not isinstance(e, (list, tuple)) or len(e) != 2:
            out.append(f"edge {e!r} isn't an [a, b] pair")
            continue
        a, b = str(e[0]), str(e[1])
        for x in (a, b):
            if x not in ids:
                out.append(f"edge {a}-{b} names {x}, which isn't a node")
        if a == b:
            out.append(f"edge {a}-{b} goes nowhere")
        if _key(a, b) in known:
            out.append(f"edge {a}-{b} is listed twice")
        known.add(_key(a, b))
    if ids and edges and not _whole(ids, known):
        out.append("the graph isn't whole: some nodes can't be reached from the others along the edges")

    stats = spec.get("stats") or []
    names = []
    if not isinstance(stats, list):
        out.append("stats is a list")
        stats = []
    if len(stats) > MOST_STATS:
        out.append(f"{len(stats)} stats; at most {MOST_STATS} pills fit")
    for s in stats:
        if not isinstance(s, dict):
            out.append("a stat isn't an object")
            continue
        name = str(s.get("name") or "")
        names.append(name)
        if not name or len(name) > STAT_CHARS or name != name.upper():
            out.append(f"stat {name!r}: a name in capitals, at most {STAT_CHARS} characters")
        if s.get("measure") not in MEASURES:
            out.append(f"stat {name}: measure {s.get('measure')!r} isn't one of {', '.join(MEASURES)}")
        for x in _list(s.get("of")):
            if x not in ids:
                out.append(f"stat {name} counts {x}, which isn't a node")
        if s.get("measure") in ("up", "count") and not _list(s.get("of")):
            out.append(f"stat {name}: say which nodes it's `of`")
        if s.get("measure") == "values" and len(_list(s.get("values"))) != len(spec.get("phases") or []):
            out.append(f"stat {name}: `values` needs one per phase")
        if len(str(s.get("unit") or "")) > 4:
            out.append(f"stat {name}: a unit is at most 4 characters (ms, %, /s)")

    phases = spec.get("phases")
    if not isinstance(phases, list) or len(phases) < 2:
        out.append("a short needs at least two phases")
        phases = []
    if len(phases) > MOST_PHASES:
        out.append(f"{len(phases)} phases; at most {MOST_PHASES}")
    res = resolved(spec)
    prev = None
    used: set[str] = set()
    for p in res:
        where = f"phase {p['index'] + 1}"
        raw = p["raw"]
        lo, hi = PHASE_SECONDS
        if not lo <= p["seconds"] <= hi:
            out.append(f"{where}: seconds is {p['seconds']}; each phase lasts {lo} to {hi}")
        cap = p["caption"] if isinstance(p["caption"], dict) else {}
        text = str(cap.get("text") or "")
        if not text.strip():
            out.append(f"{where} has no caption")
        elif words(text) > CAPTION_WORDS:
            out.append(f"{where}: the caption is {words(text)} words; at most {CAPTION_WORDS}, to read in a glance")
        if cap.get("tone", "white") not in CAPTION_TONES:
            out.append(f"{where}: caption tone {cap.get('tone')!r} isn't one of {', '.join(CAPTION_TONES)}")
        if len(str(p["subtitle"] or "")) > SUBTITLE_CHARS:
            out.append(f"{where}: the subtitle is over {SUBTITLE_CHARS} characters")
        for x in _list(raw.get("show")):
            if x not in ids:
                out.append(f"{where} shows {x}, which isn't a node")
        if not p["show"]:
            out.append(f"{where} shows no nodes")
        shown = set(p["show"])
        used |= shown
        for e in p["edges"]:
            a, b = str(e[0]), str(e[1])
            if _key(a, b) not in known:
                out.append(f"{where}: edge {a}-{b} isn't in the short's edges")
            for x in (a, b):
                if x not in shown:
                    out.append(f"{where}: edge {a}-{b} is on screen but {x} isn't")
        drawn = {_key(str(e[0]), str(e[1])) for e in p["edges"]}
        for x in p["show"]:
            if len(p["show"]) > 1 and not any(x in k for k in drawn):
                out.append(f"{where}: {x} is on screen with no line to it")
        for x, st in (raw.get("state") or {}).items():
            if x not in ids:
                out.append(f"{where}: state for {x}, which isn't a node")
            if st not in STATES:
                out.append(f"{where}: {x}'s state {st!r} isn't one of {', '.join(STATES)}")
        if len(p["traffic"]) > MOST_STREAMS:
            out.append(f"{where}: at most {MOST_STREAMS} streams of traffic")
        for s in p["traffic"]:
            out += [f"{where}: {m}" for m in _stream(s, ids, shown, drawn)]
        out += [f"{where}: {m}" for m in _code(p["code"], ids)]
        out += [f"{where}: {m}" for m in _unbound(p)]
        for x in _list(p["stats"]):
            if x not in names:
                out.append(f"{where} shows stat {x}, which isn't one of the stats")
        follow = raw.get("follow", "any")
        if follow not in ("any", "hit", "miss", "lost") and follow not in ids:
            out.append(f"{where}: follow {follow!r} is any, hit, miss, lost or a node")
        if prev is not None and _same(prev, p):
            out.append(f"{where} changes nothing from the phase before; join them or change something")
        prev = p
    for x in ids:
        if res and x not in used:
            out.append(f"{x} is never on screen")

    end = spec.get("end")
    total = sum(p["seconds"] for p in res)
    if not isinstance(end, dict):
        out.append("there's no end card")
    else:
        if end.get("stat") not in names:
            out.append(f"the end card's stat {end.get('stat')!r} isn't one of the stats")
        if not str(end.get("claim") or "").strip():
            out.append("the end card has no claim")
        elif words(end["claim"]) > CLAIM_WORDS:
            out.append(f"the end card's claim is {words(end['claim'])} words; at most {CLAIM_WORDS}")
        if len(str(end.get("note") or "")) > NOTE_CHARS:
            out.append(f"the end card's note is over {NOTE_CHARS} characters")
        lo, hi = END_SECONDS
        if not lo <= float(end.get("seconds", 2.5)) <= hi:
            out.append(f"the end card lasts {lo} to {hi} seconds")
        total += float(end.get("seconds", 2.5))
    if res and not SHORTEST <= total <= LONGEST:
        out.append(f"it lasts {total:.1f} s with its end card; a systems short is {SHORTEST:.0f} to {LONGEST:.0f} s")
    return out


def _whole(ids: list[str], edges: set[tuple[str, str]]) -> bool:
    seen, todo = {ids[0]}, [ids[0]]
    while todo:
        x = todo.pop()
        for a, b in edges:
            for u, v in ((a, b), (b, a)):
                if u == x and v not in seen:
                    seen.add(v)
                    todo.append(v)
    return seen >= set(ids)


def _stream(s: dict, ids: list[str], shown: set[str], drawn: set[tuple[str, str]]) -> list[str]:
    out = []
    src = str(s.get("from") or "")
    via = [str(x) for x in _list(s.get("via"))]
    to = stream_targets(s)
    route = route_of(s)
    if src not in ids:
        return [f"traffic from {src!r}, which isn't a node"]
    if not to:
        return [f"traffic from {src} goes nowhere: give `to`"]
    if route not in ROUTES:
        out.append(f"route {route!r} isn't one of {', '.join(ROUTES)}")
    if route == "direct" and len(to) != 1:
        out.append("a direct route has one node in `to`")
    if route == "cache_hit":
        if not via:
            out.append("cache_hit goes through the cache: put it last in `via`")
        ratio = s.get("ratio")
        if not isinstance(ratio, (int, float)) or not 0 <= ratio <= 1:
            out.append("cache_hit needs `ratio`, the share the cache answers, 0 to 1")
    rate = s.get("rate")
    if not isinstance(rate, (int, float)) or not (rate == 0 or RATES[0] <= rate <= RATES[1]):
        out.append(f"traffic from {src}: rate is requests a second, 0 or {RATES[0]} to {RATES[1]}")
    elif rate and abs(on_beat(rate) - rate) > 0.06 * rate:
        out.append(f"traffic from {src}: rate {rate} would run as {on_beat(rate):g} a second. Requests leave on the "
                   f"beat, so a rate is one of {BEAT_RATES}")
    for x in [src, *via, *to]:
        if x not in ids:
            out.append(f"traffic from {src} goes through {x}, which isn't a node")
        elif x not in shown:
            out.append(f"traffic from {src} goes through {x}, which isn't on screen")
    path = [src, *via]
    for a, b in zip(path, path[1:]):
        if _key(a, b) not in drawn:
            out.append(f"traffic from {src} travels {a}-{b}, which has no line on screen")
    for t in to:
        if _key(path[-1], t) not in drawn:
            out.append(f"traffic from {src} travels {path[-1]}-{t}, which has no line on screen")
    return out


def _code(code, ids: list[str]) -> list[str]:
    if code is None:
        return []
    if not isinstance(code, dict):
        return ["code is {language, lines, bind}"]
    out = []
    if code.get("language", "text") not in LANGUAGES:
        out.append(f"code language {code.get('language')!r} isn't one of {', '.join(LANGUAGES)}")
    lines = code.get("lines")
    if not isinstance(lines, list) or not lines:
        return out + ["the code panel has no lines"]
    if len(lines) > CODE_LINES:
        out.append(f"the code is {len(lines)} lines; at most {CODE_LINES} fit")
    for i, line in enumerate(lines, 1):
        if len(str(line)) > CODE_CHARS:
            out.append(f"code line {i} is {len(str(line))} characters; at most {CODE_CHARS} fit the panel")
    for key, n in (code.get("bind") or {}).items():
        node = key[:-5] if key.endswith(":back") else key
        if node not in ids and key not in ("hit", "miss"):
            out.append(f"the code binds a line to {key!r}: a node, \"hit\", \"miss\" or \"<node>:back\"")
        got = n if isinstance(n, list) else [n]
        if not got or not all(isinstance(x, int) and 1 <= x <= len(lines) for x in got):
            out.append(f"the code binds {key} to line {n}, which isn't one of its {len(lines)} lines")
    return out


def _unbound(phase: dict) -> list[str]:
    """With code on screen, every node a request reaches has a line: a request landing, its line and its sound are one
    event (the owner, Nov 9: "everytime a souind or a request hit a servic, it correponsd to a line of code")."""
    code = phase.get("code")
    if not isinstance(code, dict) or not code.get("lines"):
        return []
    bind = code.get("bind") or {}
    out = []
    for s in phase.get("traffic") or []:
        if not isinstance(s, dict) or not s.get("rate"):
            continue
        for x in [str(v) for v in _list(s.get("via"))] + stream_targets(s):
            if x not in bind and not any(f"requests reach {x}," in m for m in out):
                out.append(f"requests reach {x}, but no code line is bound to it. Every request that reaches a node "
                           f"lights its line and makes its sound, so bind {x} to the line that runs there")
    return out


def _same(a: dict, b: dict) -> bool:
    keys = ("subtitle", "show", "edges", "state", "traffic", "code", "stats")
    cap = lambda p: (p["caption"] or {}).get("text") if isinstance(p["caption"], dict) else None  # noqa: E731
    return all(a[k] == b[k] for k in keys) and cap(a) == cap(b)

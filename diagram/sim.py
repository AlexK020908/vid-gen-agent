"""The one source of truth for a systems short: every request's trip, every counter, queue, stat and sound, worked out
from the spec and written as the timeline Remotion only draws (render/remotion/src/shorts/DiagramShort.tsx).

Requests leave on the music's sixteenth notes, and each trip along a line takes a whole number of them, so every tick
lands on the beat. A node with a `capacity` serves one request every 1/capacity seconds (also a whole number of
sixteenths), and the ones that arrive while it's busy wait in its queue, drawn as dots stacked above it. Every number on
screen comes from these requests, so a counter, a queue and a pill can never disagree with what's moving.
"""
from __future__ import annotations

import math
import random

from diagram import layout
from diagram import spec as dspec

MOVE = 0.5          # seconds a node takes to move to where the next phase puts it
SPEED = 700.0       # px a second a request travels along a line
TRIM = layout.ICON * 0.62   # a line stops this far from a node's centre
BLINK = 0.35        # seconds a code line's flash takes to fade, each time a request runs the line
HOLD = 2 / 30       # seconds a line stays fully lit from the frame its request gets there, before fading
GAP = 1 / 30        # a line run again drops to DIP for the one frame before, so it visibly blinks
DIP = 0.15          # how far a lit line drops just before it's run again
RESET = 0.6         # the end card's last seconds, over which it crossfades back to the first frame
HITS_OVER = 8       # a hit rate is over the cache's last eight requests
ANSWERS_OVER = 4    # a timed response pill is the average of the last four answers
DECIDE = 0.25       # seconds after a request reaches a cache that it's seen to be a hit or a miss
BADGE_HOLD = 0.9    # seconds a LOST badge stays, unless the next one at its node replaces it
TRACE_GAP = 0.25    # seconds between one followed request being done and the next one being picked up
TRACE_HOLD = 0.4    # seconds a followed request's badges stay after it's done
DOWN = ("dead", "cold")         # states routing leaves out
DROPS = ("failing", "dead")     # states where a request that arrives is lost


def timeline(spec: dict) -> dict:
    """The whole short, worked out: run spec.problems first. Laid out, simulated, laid out again with the room each
    node's queue needs, and simulated again."""
    beat = float(spec.get("beat", 120))
    grid = 60.0 / beat / 4
    phases = _timed(dspec.resolved(spec), grid)
    fr = layout.frame(spec, phases)
    queues: dict[int, dict[str, int]] = {}
    for _ in range(3):
        places = [layout.place(spec, p, fr["box"], queues.get(p["index"])) for p in phases]
        run = _simulate(spec, phases, places, grid)
        if run["most_queued"] == queues:
            break
        queues = run["most_queued"]
    return _drawn(spec, phases, places, run, fr, beat, grid)


def _timed(phases: list[dict], grid: float) -> list[dict]:
    """Each phase's length rounded to the music's eighth notes, so captions change on the beat."""
    t = 0.0
    out = []
    for p in phases:
        steps = max(2, round(p["seconds"] / (2 * grid))) * 2
        q = dict(p, start=round(t, 4), end=round(t + steps * grid, 4), seconds=round(steps * grid, 4))
        out.append(q)
        t = q["end"]
    return out


def _q(t: float, grid: float) -> float:
    return round(round(t / grid) * grid, 4)


def _hop(places: dict, a: str, b: str, grid: float) -> float:
    (ax, ay), (bx, by) = places[a], places[b]
    run = max(1.0, math.hypot(bx - ax, by - ay) - 2 * TRIM)
    return max(2, round(run / SPEED / grid)) * grid


def _state_at(phases: list[dict], node: str, t: float) -> str:
    for p in reversed(phases):
        if p["start"] <= t + 1e-6:
            return p["state"].get(node, "healthy")
    return "healthy"


def _phase_at(phases: list[dict], t: float) -> dict:
    for p in reversed(phases):
        if p["start"] <= t + 1e-6:
            return p
    return phases[0]


def _simulate(spec: dict, phases: list[dict], places: list[dict], grid: float) -> dict:
    nodes = {n["id"]: n for n in spec["nodes"]}
    service = {n: max(1, round(1.0 / float(v["capacity"]) / grid)) * grid
               for n, v in nodes.items() if v.get("capacity")}
    spawns = []   # (time, order, phase index, stream index, stream, k)
    for p in phases:
        for si, s in enumerate(p["traffic"]):
            rate = float(s.get("rate") or 0)
            if rate <= 0:
                continue
            every = max(1, round(1.0 / rate / grid)) * grid
            t, k = p["start"], 0
            while t < p["end"] - 1e-6:
                spawns.append((round(t, 4), si, p["index"], si, s, k))
                k += 1
                t = round(t + every, 4)
    spawns.sort(key=lambda x: (x[0], x[1]))

    free_at: dict[str, float] = {}
    waits: dict[str, list[tuple[float, float]]] = {n: [] for n in nodes}   # [arrived, served from)
    arrivals: dict[str, list[float]] = {n: [] for n in nodes}
    dots: list[list] = []
    flashes: list[list] = []
    cues: list[list] = []
    lit: list[list] = []                          # every request's every event: [what happened (a node it reached,
                                                  # hit, miss, "<node>:back"), when, whether it was lost there]. The
                                                  # code's lines and the sounds both come from these (_code, _drawn)
    decisions: list[tuple[float, bool]] = []      # a cache's (time, hit)
    answers: list[tuple[float, int, str]] = []    # a request answered: (when it reached where it's answered, how long
                                                  # its trip takes in ms, where it came from). Its wait there is known
                                                  # then, so the pill moves as a queue builds, not once answers are back
    badges: list[list] = []                       # [node, from, to, text, tone]
    cursor: dict[tuple, int] = {}
    counted = layout.counted(spec)
    rng = random.Random(7)
    timed = is_timed(spec)
    rstat = next((x for x in spec.get("stats") or [] if x.get("measure") == "response"), {})
    free_trace = 0.0                              # when the request being followed is done, and the next can be
    followed_in: set[int] = set()                 # the phases a request has been followed in

    def queued_at(n: str, t: float) -> int:
        return sum(1 for a, b in waits[n] if a <= t < b)

    def visit(n: str, t: float, req: dict) -> tuple[bool, float]:
        """A request reaches n at t: (whether it got there, when it leaves after being served). Its time grows by
        n's `ms`, once for itself and once for each request waiting ahead of it there."""
        if _state_at(phases, n, t) in DROPS:
            flashes.append([n, t, "drop"])
            cues.append([t, "drop", n])
            badges.append([n, t, round(t + BADGE_HOLD, 4), "LOST", "red"])
            req["end"] = max(req["end"], t)
            req["outcome"] = "lost"
            mark(n, t, lost=True)
            return False, t
        own = float(nodes[n].get("ms") or 0) * (1 + queued_at(n, t))
        req["ms"] += own
        req["own"] = own
        req["reached"].append(n)
        mark(n, t)
        if n in service:
            start = max(t, free_at.get(n, 0.0))
            free_at[n] = round(start + service[n], 4)
            if start > t + 1e-6:
                waits[n].append((t, start))
            return True, free_at[n]
        return True, t

    def travel(a: str, b: str, t: float, pi: int, kind: str, req: dict) -> float:
        d = _hop(places[pi], a, b, grid)
        dot = [a, b, t, round(t + d, 4), kind, 0]
        dots.append(dot)
        req["dots"].append(dot)
        req["end"] = max(req["end"], round(t + d, 4))
        return round(t + d, 4)

    def mark(what: str, t: float, lost: bool = False) -> None:
        lit.append([what, t, lost])

    def reached(n: str, t: float) -> None:
        if n in counted:
            arrivals[n].append(t)
            cues.append([t, "tick", n])

    def done(req: dict, path: list[str], t_at: float, t_out: float, pi: int, s: dict, hit: bool = False) -> None:
        """A request answered at path[-1]: its own node's time shown there (a cache hit says HIT instead), and its
        answer carried back to where it came from, with how long the whole trip took."""
        last = path[-1]
        if timed and not hit and nodes[last].get("ms"):
            req["badges"].append([last, t_at, _fmt(round(req["own"]), "ms"), _tone(rstat, round(req["own"]))])
        answers.append((t_at, round(req["ms"]), path[0]))
        if not s.get("back"):
            return
        t = t_out
        for a, b in zip(path[::-1], path[::-1][1:]):
            t = travel(a, b, t, pi, "back", req)
            mark(f"{b}:back", t)
        cues.append([t, "return", path[0]])
        if timed:
            req["badges"].append([path[0], t, _fmt(round(req["ms"]), "ms"), _tone(rstat, round(req["ms"]))])

    def handle(t0: float, pi: int, s: dict, k: int, req: dict) -> None:
        src = str(s["from"])
        via = [str(x) for x in dspec._list(s.get("via"))]
        targets = dspec.stream_targets(s)
        route = dspec.route_of(s)
        t, path = t0, [src]
        for n in via:
            t = travel(path[-1], n, t, pi, "req", req)
            ok, t_out = visit(n, t, req)
            path.append(n)
            if not ok:
                return
            if route == "cache_hit" and n == via[-1]:
                ratio = float(s.get("ratio") or 0)
                hit = math.floor((k + 1) * ratio + 1e-9) > math.floor(k * ratio + 1e-9)
                decisions.append((t, hit))
                seen = round(t + DECIDE, 4)
                req["badges"].append([n, seen, "HIT" if hit else "MISS", "green" if hit else "orange"])
                req["outcome"] = "hit" if hit else "miss"
                mark("hit" if hit else "miss", seen)
                if hit:
                    reached(n, t)
                    done(req, path, t, max(t_out, seen), pi, s, hit=True)
                    return
                t_out = max(t_out, seen)
            t = t_out
        alive = [x for x in targets if _state_at(phases, x, t) not in DOWN]
        key = (src, tuple(targets))
        if route == "broadcast":
            chosen = alive
        elif route == "direct":
            chosen = targets[:1]
        elif not alive:
            flashes.append([path[-1], t, "drop"])
            cues.append([t, "drop", path[-1]])
            badges.append([path[-1], t, round(t + BADGE_HOLD, 4), "LOST", "red"])
            req["outcome"] = "lost"
            mark(path[-1], t, lost=True)
            return
        elif route in ("round_robin", "cache_hit"):
            i = cursor.get(key, 0)
            order = [x for x in targets[i % len(targets):] + targets[:i % len(targets)] if x in alive]
            chosen = order[:1]
            cursor[key] = targets.index(chosen[0]) + 1
        elif route == "least_connections":
            chosen = [min(alive, key=lambda x: (queued_at(x, t), targets.index(x)))]
        elif route == "hash":
            chosen = [alive[(k * 7 + 3) % len(alive)]]
        elif route == "random":
            chosen = [rng.choice(alive)]
        else:   # failover
            chosen = alive[:1]
        for n in chosen:
            one = {**req, "ms": req["ms"], "reached": req["reached"]}
            t_at = travel(path[-1], n, t, pi, "req", one)
            ok, t_out = visit(n, t_at, one)
            req["end"] = max(req["end"], one["end"])
            if not ok:
                req["outcome"] = "lost"
            if ok:
                reached(n, t_at)
                done(one, path + [n], t_at, t_out, pi, s)
                req["end"] = max(req["end"], one["end"])

    for t0, _, pi, si, s, k in spawns:
        # one request at a time is followed: ringed on screen, its badges shown, the code lit line by line as it goes.
        # It's the first to leave once the last one's done that's what its phase says to follow (`follow`)
        req = {"ms": float(rstat.get("base", 0) if timed else 0), "own": 0.0, "end": t0, "badges": [], "dots": [],
               "reached": [], "outcome": "answered"}
        handle(t0, pi, s, k, req)
        want = phases[pi]["raw"].get("follow") or "any"
        # followed to the end of its phase at most, so the next phase follows what its caption says; and only one
        # whose trip is done by then, unless it's its phase's first, so a ring isn't seen to vanish halfway
        cut = next((q["start"] for q in phases if q["start"] > t0 + 1e-6), float("inf"))
        req["traced"] = (t0 >= free_trace - 1e-6 and (want == "any" or want == req["outcome"] or want in req["reached"])
                         and (req["end"] <= cut + 1e-6 or pi not in followed_in))
        if req["traced"]:
            followed_in.add(pi)
            for dot in req["dots"]:
                dot[5] = 1 if dot[2] < cut - 1e-6 else 0
            free_trace = min(req["end"] + TRACE_GAP, cut)
            hold = min(round(req["end"] + TRACE_HOLD, 4), cut)
            badges += [[node, t, max(hold, min(round(t + 0.5, 4), cut)), text, tone]
                       for node, t, text, tone in req["badges"] if t < cut - 1e-6]

    most: dict[int, dict[str, int]] = {}
    for p in phases:
        got = {}
        for n, ws in waits.items():
            peak = _peak(ws, p["start"], p["end"])
            if peak:
                got[n] = peak
        most[p["index"]] = got
    return {"dots": dots, "flashes": flashes, "cues": cues, "waits": waits, "arrivals": arrivals, "lit": lit,
            "decisions": decisions, "answers": sorted(answers), "badges": badges,
            "most_queued": most}


def is_timed(spec: dict) -> bool:
    """Whether requests are timed from the nodes' `ms`: then a response pill is the average of the last answers."""
    return any(n.get("ms") for n in spec.get("nodes") or [])


def _peak(waits: list[tuple[float, float]], a: float, b: float) -> int:
    events = []
    for s, e in waits:
        if e > a and s < b:
            events += [(max(s, a), 1), (min(e, b), -1)]
    events.sort(key=lambda x: (x[0], x[1]))
    cur = best = 0
    for _, d in events:
        cur += d
        best = max(best, cur)
    return best


def _steps(changes: list[tuple[float, int]]) -> list[list]:
    """A running count from +1/-1 changes, as [time, value] steps."""
    out, cur = [[0.0, 0]], 0
    for t, d in sorted(changes):
        cur += d
        if out[-1][0] == round(t, 4):
            out[-1][1] = cur
        else:
            out.append([round(t, 4), cur])
    return out


def _tone(stat: dict, value) -> str:
    if value is None:
        return "grey"
    good, bad = stat.get("good"), stat.get("bad")
    if good is None and bad is None:
        return "white"
    better = bool(stat.get("higher_better"))

    def past(x):
        return x is not None and (value >= x if better else value <= x)

    if past(good):
        return "green"
    if bad is not None and (value <= bad if better else value >= bad):
        return "red"
    return "orange"


def _stat_steps(stat: dict, spec: dict, phases: list[dict], run: dict, until: float, beat_s: float) -> list[list]:
    measure = stat.get("measure")
    of = [str(x) for x in dspec._list(stat.get("of"))]
    out: list[list] = []
    t = 0.0
    while t < until - 1e-6:
        p = _phase_at(phases, t)
        if measure == "response" and is_timed(spec):
            done = [ms for (a, ms, _) in run["answers"] if a <= t + 1e-6][-ANSWERS_OVER:]
            if not done and run["answers"]:      # before the first answer's in: what an answer takes then
                done = [run["answers"][0][1]]
            v = round(sum(done) / len(done)) if done else None
        elif measure == "response":
            waiting = sum(1 for ws in run["waits"].values() for a, b in ws if a <= t < b)
            v = round(float(stat.get("base", 40)) + float(stat.get("per_queued", 40)) * waiting)
        elif measure == "up":
            v = sum(1 for n in of if n in p["show"] and p["state"].get(n, "healthy") not in DOWN)
        elif measure == "count":
            v = sum(1 for n in of for a in run["arrivals"][n] if a <= t)
        elif measure == "hits":
            last = [h for (a, h) in run["decisions"] if a <= t][-HITS_OVER:]
            v = round(100 * sum(last) / len(last)) if last else None
        elif measure == "rate":
            v = round(sum(float(s.get("rate") or 0) for s in p["traffic"] if not of or str(s.get("from")) in of), 1)
            v = int(v) if v == int(v) else v
        else:
            vals = dspec._list(stat.get("values"))
            v = vals[p["index"]] if p["index"] < len(vals) else None
        if not out or out[-1][1] != v:
            out.append([round(t, 4), v, _tone(stat, v)])
        t = round(t + beat_s, 4)
    return out


def _fmt(v, unit: str) -> str:
    if v is None:
        return "—"
    s = f"{v:,}" if isinstance(v, int) else f"{v}"
    return f"{s} {unit}".strip()


def _drawn(spec: dict, phases: list[dict], places: list[dict], run: dict, fr: dict, beat: float, grid: float) -> dict:
    nodes = spec["nodes"]
    count = layout.counted(spec)
    beat_s = 60.0 / beat
    bar = 4 * beat_s
    end = spec.get("end") or {}
    t_end = phases[-1]["end"]
    # the whole short is a whole number of bars, so the music loops with it: the end card lasts at least its seconds
    total = t_end + max(dspec.END_SECONDS[0], float(end.get("seconds", 2.5)))
    total = round(math.ceil(total / bar - 1e-6) * bar, 4)
    card_to = total

    # where each node is, phase by phase: it moves over MOVE seconds into each phase's place
    first_at = {}
    for pl in places:
        for n, xy in pl.items():
            first_at.setdefault(n, xy)
    drawn_nodes = []
    for n in nodes:
        nid = n["id"]
        keys, states = [], []
        prev = None
        for p, pl in zip(phases, places):
            shown = nid in pl
            xy = pl.get(nid) or (prev[1:3] if prev else first_at.get(nid, (0, 0)))
            cur = [xy[0], xy[1], 1 if shown else 0]
            if prev is None:
                keys.append([0.0, *cur])
            elif cur != prev[1:]:
                start = p["start"]
                was = list(prev[1:])
                if shown and not prev[3]:   # it appears where it'll stand, not sliding from where it last was
                    was = [cur[0], cur[1], 0]
                if not shown:               # it fades where it stood
                    cur = [prev[1], prev[2], 0]
                keys.append([start, *was])
                keys.append([round(start + MOVE, 4), *cur])
            prev = [p["start"], *cur]
            st = p["state"].get(nid, "healthy")
            if not states or states[-1][1] != st:
                states.append([p["start"], st])
        arr = run["arrivals"][nid]
        counts = [[0.0, 0]] + [[t, i + 1] for i, t in enumerate(sorted(arr))]
        waits = run["waits"][nid]
        queue = _steps([(a, 1) for a, b in waits] + [(b, -1) for a, b in waits])
        drawn_nodes.append({"id": nid, "icon": n["icon"], "label": n["label"], "tone": n.get("tone", "blue"),
                            "counter": nid in count, "ring": bool(n.get("capacity")) or nid in count,
                            "keys": keys, "states": states, "counts": counts, "queue": queue})

    edges = []
    for e in spec["edges"]:
        a, b = str(e[0]), str(e[1])
        keys, dashed = [], []
        prev = None
        for p in phases:
            on = 1 if any({a, b} == {str(x), str(y)} for x, y in p["edges"]) else 0
            if prev is None:
                keys.append([0.0, on])
            elif on != prev:
                keys += [[p["start"], prev], [round(p["start"] + MOVE, 4), on]]
            prev = on
            dead = any(p["state"].get(x) == "dead" for x in (a, b))
            if not dashed or dashed[-1][1] != dead:
                dashed.append([p["start"], dead])
        edges.append({"a": a, "b": b, "keys": keys, "dashed": dashed})

    subtitles = []
    for p in phases:
        text = str(p["subtitle"] or "")
        if subtitles and subtitles[-1]["text"] == text:
            subtitles[-1]["to"] = card_to
        else:
            subtitles.append({"text": text, "from": p["start"], "to": card_to})
            if len(subtitles) > 1:
                subtitles[-2]["to"] = p["start"]
    subtitles = [s for s in subtitles if s["text"]]
    for s in subtitles:
        s["size"] = layout.fit(s["text"], layout.HEAD_RIGHT - layout.HEAD_LEFT, layout.SUBTITLE_SIZE, 22, 400,
                               "mono", 1.5) or 22

    captions = []
    for p in phases:
        cap = p["caption"] or {}
        text = str(cap.get("text") or "")
        size, lines = layout.caption_size(text) or (layout.CAPTION_LEAST, [text])
        captions.append({"text": text, "lines": lines, "size": size, "tone": cap.get("tone", "white"),
                         "from": p["start"], "to": p["end"]})

    stats = []
    for s in spec.get("stats") or []:
        steps = _stat_steps(s, spec, phases, run, t_end, beat_s)
        shown = [[p["start"], p["end"]] for p in phases if s["name"] in dspec._list(p["stats"])]
        spans = []
        for a, b in shown:
            if spans and abs(spans[-1][1] - a) < 1e-6:
                spans[-1][1] = b
            else:
                spans.append([a, b])
        if spans and abs(spans[-1][1] - t_end) < 1e-6:
            spans[-1][1] = card_to
        stats.append({"name": s["name"], "unit": s.get("unit", ""), "steps": steps, "spans": spans,
                      "measure": s.get("measure")})

    code = _code(phases, run, card_to, grid)

    card = None
    if end:
        stat = next((s for s in spec.get("stats") or [] if s["name"] == end.get("stat")), None)
        steps = next((x["steps"] for x in stats if x["name"] == end.get("stat")), [])
        vals = [st for st in steps if st[1] is not None]
        if stat and vals:
            better = bool(stat.get("higher_better"))
            worst = (min if better else max)(vals, key=lambda st: st[1])
            last = vals[-1]
            claim = str(end.get("claim") or "")
            card = {"from": t_end, "to": card_to,
                    "before": {"text": _fmt(worst[1], stat.get("unit", "")), "tone": worst[2]},
                    "after": {"text": _fmt(last[1], stat.get("unit", "")), "tone": last[2]},
                    "claim": claim, "claim_lines": layout.lines(claim, layout.END_CLAIM, layout.RIGHT - layout.LEFT)
                    or [claim], "note": str(end.get("note") or "")}

    facts = []
    for p in phases:
        at_end = {n["id"]: sum(1 for t in run["arrivals"][n["id"]] if t <= p["end"]) for n in nodes
                  if n["id"] in count}
        facts.append({"phase": p["index"] + 1, "from": p["start"], "to": p["end"],
                      "caption": (p["caption"] or {}).get("text"),
                      "counters_at_end": at_end,
                      "most_waiting": run["most_queued"].get(p["index"], {}),
                      "waiting_at_end": {n: c for n, ws in run["waits"].items()
                                         if (c := sum(1 for a, b in ws if a <= p["end"] - 1e-3 < b))},
                      "lost": sum(1 for f in run["flashes"] if p["start"] <= f[1] < p["end"]),
                      "stats_at_end": {s["name"]: next((st[1] for st in reversed(s["steps"])
                                                        if st[0] <= p["end"] - 1e-3), None) for s in stats}})

    cues = list(run["cues"])
    if code:
        # with code on screen, every request's sound is one of its lines running: a tick pitched by the line, or a
        # thunk where the request is lost. So no sound plays without its line lighting, and no line lights silently
        spans = [(b["from"], b["to"]) for b in code["blocks"] if b["lines"]]
        cues = [c for c in cues if c[1] not in ("tick", "return", "drop") or not any(a <= c[0] < z for a, z in spans)]
        for b in code["blocks"]:
            cues += [[t, "drop" if kind == "lost" else "code", line] for line, t, _, kind in b["hl"]]
    for p in phases[1:]:
        before = phases[p["index"] - 1]
        if set(p["show"]) - set(before["show"]):
            cues.append([p["start"], "appear", None])
        for n, st in p["state"].items():
            if st in DROPS and before["state"].get(n) not in DROPS:
                cues.append([p["start"], "fail", n])
    if card:
        cues.append([t_end, "chime", None])
    targets = sorted({c[2] for c in cues if c[1] == "tick"}, key=lambda n: [x["id"] for x in nodes].index(n))

    return {
        "duration": total, "beat": beat, "grid": grid,
        "geometry": {"icon": layout.ICON, "ring": layout.RING, "label": layout.LABEL, "counter": layout.COUNTER,
                     "trim": TRIM, "queue_dot": layout.QUEUE_DOT, "queue_step": layout.QUEUE_STEP,
                     "queue_dots": layout.QUEUE_DOTS, "queue_more": layout.QUEUE_MORE, "badge": layout.BADGE,
                     "badge_pad": layout.BADGE_PAD, "badge_h": layout.BADGE_H, "left": layout.LEFT, "right": layout.RIGHT,
                     "head_left": layout.HEAD_LEFT, "head_right": layout.HEAD_RIGHT, "code_size": layout.CODE_SIZE,
                     "code_line": layout.CODE_LINE, "code_pad": layout.CODE_PAD, "code_bottom": layout.CODE_BOTTOM,
                     "end_big": layout.END_BIG, "end_claim": layout.END_CLAIM, "end_note": layout.END_NOTE,
                     "pill_h": layout.PILL_H, "pill_text": layout.PILL_TEXT, "pill_value": layout.PILL_VALUE,
                     "pill_pad": layout.PILL_PAD, "pill_gap": layout.PILL_GAP, "move": MOVE, "blink": BLINK,
                     "hold": HOLD, "gap": GAP, "dip": DIP,
                     **fr},
        "title": spec.get("title", ""),
        "subtitles": subtitles, "captions": captions, "stats": stats,
        "nodes": drawn_nodes, "edges": edges, "dots": run["dots"], "flashes": run["flashes"],
        "badges": _sided(_held(run["badges"], card_to), spec, phases),
        "code": code, "end": card, "loop": {"from": round(total - RESET, 4), "to": total},
        "phases": [{"from": p["start"], "to": p["end"]} for p in phases],
        "cues": sorted(cues, key=lambda c: c[0]), "pitch": targets,
        "facts": facts,
    }


def _held(badges: list[list], until: float) -> list[list]:
    """Each badge as [node, from, to, text, tone]: shown until its own end, the next one at its node, or the end card.
    Two at a node at once (two answers in together): the later one listed stands."""
    badges = sorted(badges, key=lambda b: (b[1], b[0]))
    out = []
    for i, (node, t, end, text, tone) in enumerate(badges):
        nxt = next((b[1] for b in badges[i + 1:] if b[0] == node and b[1] >= t - 1e-6), None)
        to = min(end, nxt if nxt is not None else until, until)
        if to > t + 1e-6:
            out.append([node, round(t, 4), round(to, 4), text, tone])
    return out


def _sided(badges: list[list], spec: dict, phases: list[dict]) -> list[list]:
    """Each badge with where it goes at its node in its phase: "below" its label or "right" of its icon."""
    sides = [layout.badge_sides(spec, p) for p in phases]
    return [[*b, sides[_phase_at(phases, b[1])["index"]].get(b[0], "below")] for b in badges]


def _lines(value) -> list[int]:
    return [int(v) for v in (value if isinstance(value, list) else [value])]


def _code(phases: list[dict], run: dict, card_to: float, grid: float) -> dict | None:
    from diagram import code as dcode
    if not any(p["code"] for p in phases):
        return None
    blocks = []
    for p in phases:
        c = p["code"]
        if blocks and blocks[-1]["src"] == c:
            blocks[-1]["to"] = p["end"]
            continue
        blocks.append({"src": c, "from": p["start"], "to": p["end"]})
    blocks[-1]["to"] = card_to
    out = []
    for b in blocks:
        c = b["src"]
        if not c:
            out.append({"from": b["from"], "to": b["to"], "lines": [], "bind": {}, "dims": [], "hl": []})
            continue
        bind = {str(k): _lines(v) for k, v in (c.get("bind") or {}).items()}
        dims = []
        for p in phases:
            if p["end"] <= b["from"] or p["start"] >= b["to"]:
                continue
            for n, lines in bind.items():
                if p["state"].get(n) == "dead":
                    for line in lines:
                        if not any(d[0] == line for d in dims):
                            dims.append([line, max(p["start"], b["from"])])
        # Every request blinks each line it runs, the moment its dot gets there (or the cache answers it), and the
        # sounds are made from these same blinks (_drawn), so a dot landing, its line and its sound are one event and
        # can't drift apart. The owner, Nov 9: "everytime a souind or a request hit a servic, it correponsd to a line
        # of code ... this can be deterministic". A line run again blinks again; a binding to several lines lights
        # them a sixteenth note apart. Each is [line, from, to, kind]: "run", or "lost" where the request was lost
        once: dict[tuple[float, int], bool] = {}        # two requests running a line at the same moment light it once
        for n, t, lost in run["lit"]:
            if n not in bind or not b["from"] <= t < b["to"]:
                continue
            for i, line in enumerate(bind[n]):
                at = round(t + i * grid, 4)
                if at < b["to"]:
                    once[(at, line)] = once.get((at, line), False) or lost
        events = sorted(once.items())
        hl = []
        for i, ((t, line), lost) in enumerate(events):
            again = next((u for (u, other), _ in events[i + 1:] if other == line and u > t + 1e-6), b["to"])
            hl.append([line, t, round(min(t + HOLD + BLINK, again, b["to"]), 4), "lost" if lost else "run"])
        out.append({"from": b["from"], "to": b["to"], "lines": dcode.tokens(c.get("language", "text"),
                                                                            [str(x) for x in c["lines"]]),
                    "bind": bind, "dims": dims, "hl": hl})
    return {"blocks": out}

"""A systems short's spec (SHORTS.md, "How a systems short is made"): the agent writes it from the topic as a `diagram`
job, checked in code as it comes in (diagram/make.py: its fields, whether it fits on the frame, its end card's numbers),
and the critic agent reads it as a senior engineer, with what the simulation shows phase by phase. It goes to the owner
at the outline gate as the story it tells, phase by phase. Stops there.

A spec the look at its frames sent back (stages/draw.py) was approved already: rewritten with the look's notes, it goes
straight back to be drawn.
"""
from __future__ import annotations

import json

from core import db, review
from core.errors import Stopped
from core.stage import run_video_stage
from diagram import sim
from diagram import spec as dspec

NAME = "diagram"


def run_once(ctx) -> bool:
    return run_video_stage(ctx, NAME, "new", _work)


def _work(ctx, conn, video) -> None:
    channel = ctx.channel(video["channel_id"])
    topic = conn.execute("SELECT title FROM topics WHERE id = ?", (video["topic_id"],)).fetchone()["title"]
    kept = json.loads(video["outline_json"]) if video["outline_json"] else {}
    previous = kept.get("spec")
    notes = db.notes(conn, video["id"], "outline")
    spec = ctx.llm.diagram(channel, topic, notes, previous, ctx.meter(conn, video, NAME, "the diagram spec"))
    try:
        spec = review.reviewed(ctx, conn, video, channel, "spec", {"spec": for_review(spec)}, spec,
                               lambda found: ctx.llm.diagram(channel, topic, notes + found, spec,
                                                             ctx.meter(conn, video, NAME, "the diagram spec, revised")))
    except Stopped:  # back to the draft the reviewer was reading (core/stage.py back_to_review)
        db.update_video(conn, video["id"], outline_json=json.dumps(outline(topic, spec, kept)))
        raise
    again = bool(kept.get("approved"))
    with db.tx(conn):
        db.transition(conn, video["id"], "new", "outline_approved" if again else "outlined",
                      outline_json=json.dumps(outline(topic, spec, kept)))
    if again:
        ctx.events.emit("notice", video["id"], text="The spec was fixed for what the look at its frames found, and "
                                                    "it's being drawn again.")
    else:
        ctx.events.emit("gate_reached", video["id"], gate="outline")


def outline(topic: str, spec: dict, kept: dict | None = None) -> dict:
    """The spec as the outline card shows it (core/cards.py outline_card): each phase a beat, with what's on screen,
    what moves and what the numbers do by its end, worked out by the simulation."""
    beats = story(spec)
    end = spec.get("end") or {}
    return {"topic": topic, "hook": beats[0]["title"] if beats else "", "backstory": spec.get("title", ""),
            "ending": f"{end.get('claim', '')} ({end.get('note', '')})".strip(), "cast": [], "tracker": [],
            "beats": beats, "spec": spec, "duration": sim.timeline(spec)["duration"],
            "approved": bool((kept or {}).get("approved")), "looked": int((kept or {}).get("looked", 0))}


def story(spec: dict) -> list[dict]:
    tl = sim.timeline(spec)
    phases = sim._timed(dspec.resolved(spec), tl["grid"])
    labels = {n["id"]: n["label"] for n in spec["nodes"]}
    beats = []
    for p, f in zip(phases, tl["facts"]):
        cap = p["caption"] or {}
        moving = "; ".join(_stream(s, labels) for s in p["traffic"]) or "nothing moving"
        states = ", ".join(f"{labels[n]} {st}" for n, st in p["state"].items() if st != "healthy" and n in p["show"])
        counters = ", ".join(f"{labels[n]} {v}" for n, v in f["counters_at_end"].items() if n in p["show"])
        waiting = ", ".join(f"{labels[n]} {v}" for n, v in f["waiting_at_end"].items())
        pills = ", ".join(f"{k} {v}" for k, v in f["stats_at_end"].items() if v is not None and k in dspec._list(p["stats"]))
        summary = (f"{p['subtitle'] + '. ' if p['subtitle'] else ''}On screen: {', '.join(labels[n] for n in p['show'])}. "
                   f"Moving: {moving}.{' ' + states + '.' if states else ''} By its end: counters {counters or 'none'}; "
                   f"waiting {waiting or 'none'}; lost {f['lost']}; pills {pills or 'none'}.")
        beats.append({"label": f"{p['start']:.1f}-{p['end']:.1f} s", "title": str(cap.get("text") or ""),
                      "tone": cap.get("tone", "white"), "summary": summary,
                      "code": "\n".join((p["code"] or {}).get("lines") or [])})
    return beats


def _stream(s: dict, labels: dict) -> str:
    path = " → ".join(labels.get(str(x), str(x)) for x in [s.get("from"), *dspec._list(s.get("via"))])
    to = ", ".join(labels.get(t, t) for t in dspec.stream_targets(s))
    route = dspec.route_of(s)
    extra = f", {round(float(s['ratio']) * 100)}% answered by the cache" if route == "cache_hit" else ""
    back = ", answers travelling back" if s.get("back") else ""
    return f"{s.get('rate')} requests a second {path} → {to} ({route.replace('_', ' ')}{extra}{back})"


def for_review(spec: dict) -> str:
    """What the reviewer reads: the spec, and what the simulation shows of it phase by phase."""
    lines = [f"{b['label']} \"{b['title']}\" ({b['tone']}): {b['summary']}" + (f"\n  Code:\n    " + b["code"].replace("\n", "\n    ") if b["code"] else "")
             for b in story(spec)]
    tl = sim.timeline(spec)
    end = tl.get("end") or {}
    card = (f"End card: {end['before']['text']} → {end['after']['text']}, \"{end['claim']}\", \"{end['note']}\""
            if end else "No end card.")
    return ("The spec:\n```json\n" + json.dumps(spec, indent=1, ensure_ascii=False) + "\n```\n\n"
            f"What a viewer sees, as the simulation runs it ({tl['duration']:.1f} s, looping):\n" + "\n".join(lines)
            + f"\n{card}")

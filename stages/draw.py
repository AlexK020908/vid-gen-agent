"""A systems short drawn from its approved spec: simulated, its sound mixed and Remotion's `DiagramShort` rendered
(diagram/make.py). Then a look at a frame from the middle of each phase, by someone who didn't write it (a `look` job
for the worker agent): is it readable on a phone, does anything overlap or get cut off, is the story clear with the
sound off. What it finds goes back to the spec's writer once (stages/diagram.py), and the short is drawn again. Then the
render card, with the MP4 and a strip of its frames. A systems short costs nothing to make: there's no voice.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from characters.build import sheet as tile
from core import db
from core.errors import FinalError
from core.stage import run_video_stage
from diagram import make
from render import ffmpeg, remotion_render
from stages.direct import _stub
from stages.film import _frame_sheet

NAME = "draw"
MOST_LOOKS = 1          # how many times the look at the frames sends the spec back, before the owner sees it as it stands
LOOK_CELL, LOOK_COLUMNS = (360, 640), 3


def run_once(ctx) -> bool:
    return run_video_stage(ctx, NAME, "outline_approved", _work, lease_s=3600)


def _work(ctx, conn, video) -> None:
    channel = ctx.channel(video["channel_id"])
    kept = json.loads(video["outline_json"])
    spec = kept["spec"]
    found = make.check(spec)
    if found:   # approved, then changed by hand or by a newer check: the writer fixes it
        raise FinalError("the spec doesn't pass its checks: " + "; ".join(found[:6]))
    if remotion_render.missing():
        raise FinalError(f"drawing a systems short needs Remotion: {remotion_render.missing()}")
    folder = ctx.media(video["id"]) / "diagram"
    out = folder / "short.mp4"
    stamp = out.with_suffix(".key")     # this stage runs again from the top when the look is answered: draw it once
    key = hashlib.sha256(json.dumps(spec, sort_keys=True).encode("utf-8")).hexdigest()
    if not (out.exists() and stamp.exists() and stamp.read_text(encoding="utf-8") == key):
        make.render(spec, out, lambda done, total: ctx.events.emit("stage_progress", video["id"], stage=NAME,
                                                                    done=done, total=total, unit="%"))
        stamp.write_text(key, encoding="utf-8")
    timeline = json.loads(out.with_suffix(".timeline.json").read_text(encoding="utf-8"))
    if not _stub(ctx) and kept.get("looked", 0) < MOST_LOOKS:
        sheet = look_sheet(out, timeline, folder / "look")
        problems = ctx.llm.look_diagram(channel, phases_text(timeline), sheet,
                                        ctx.meter(conn, video, NAME, "the look at the frames"))
        kept["looked"] = kept.get("looked", 0) + 1
        if problems:
            notes = [f"Look, {p['phase']}: {p['what']} Fix: {p['fix']}" for p in problems]
            said = "\n".join(f"- {n}" for n in notes)
            with db.tx(conn):
                for note in notes:
                    db.add_feedback(conn, video["id"], "outline", note)
                db.transition(conn, video["id"], "outline_approved", "new",
                              outline_json=json.dumps({**kept, "approved": True}))
            ctx.events.emit("notice", video["id"], text=f"The look at the frames found {len(notes)} thing(s), so the "
                                                        f"spec goes back to be fixed and drawn again:\n{said}")
            return
        db.update_video(conn, video["id"], outline_json=json.dumps(kept))
    strip = _frame_sheet(out, folder / "frames.png")
    title = _title(spec.get("title", ""))
    with db.tx(conn):
        db.transition(conn, video["id"], "outline_approved", "assembled", video_path=ctx.rel(out), chapters_json="[]",
                      duration_ms=round(timeline["duration"] * 1000), frames_path=ctx.rel(strip) if strip else None,
                      title=title, thumbs_json=json.dumps({"titles": [title], "thumbs": [], "texts": []}))
    ctx.events.emit("gate_reached", video["id"], gate="render")


def _title(caps: str) -> str:
    """The spec's title in sentence case: HOW A CACHE WORKS is "How a cache works"."""
    caps = caps.strip()
    return caps[:1].upper() + caps[1:].lower() if caps else "A systems short"


def look_sheet(video: Path, timeline: dict, folder: Path) -> Path:
    """A frame from the middle of each phase and of the end card, three to a row, big enough to read a caption."""
    folder.mkdir(parents=True, exist_ok=True)
    for old in folder.glob("f_*.png"):
        old.unlink()
    moments = [(f"phase {i + 1}", (p["from"] + p["to"]) / 2) for i, p in enumerate(timeline["phases"])]
    end = timeline.get("end")
    if end:
        moments.append(("end card", (end["from"] + timeline["loop"]["from"]) / 2))
    shots = []
    for i, (view, t) in enumerate(moments):
        name = f"f_{i:02d}.png"
        ffmpeg.run(["-ss", f"{t:.3f}", "-i", video, "-frames:v", "1", "-vf", f"scale={LOOK_CELL[0]}:-1", folder / name])
        shots.append({"view": f"{view} ({t:.1f} s)", "file": name})
    made = tile({"shots": shots}, folder, cell=LOOK_CELL, columns=LOOK_COLUMNS)
    target = folder.parent / "look.png"
    made.replace(target)
    return target


def phases_text(timeline: dict) -> str:
    """What each phase is meant to show, for the look: its caption, and what's moving and waiting by its end."""
    out = []
    for i, (p, f) in enumerate(zip(timeline["phases"], timeline["facts"]), 1):
        counters = ", ".join(f"{k} {v}" for k, v in f["counters_at_end"].items())
        waiting = ", ".join(f"{k} {v}" for k, v in f["waiting_at_end"].items()) or "none"
        out.append(f"- phase {i} ({p['from']:.1f}-{p['to']:.1f} s): caption \"{f['caption']}\"; counters by its end "
                   f"{counters or 'none'}; waiting {waiting}; requests lost {f['lost']}")
    end = timeline.get("end")
    if end:
        out.append(f"- end card: {end['before']['text']} → {end['after']['text']}, \"{end['claim']}\", "
                   f"\"{end['note']}\"")
    return "\n".join(out)

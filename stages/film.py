"""A character short filmed from its direction: a rough look at a frame of every shot first, sent back to the director once
if a viewer would see something wrong, then every scene rendered, and the voice, captions and sound put on in Remotion.
Stops at the render card. A scene's render is kept by what's in it, so directing it again only renders what changed.

With the stub providers (`mode: stub`) nothing goes near Blender: each scene is a colored placeholder of the right length.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from PIL import Image

from characters.build import sheet as tile
from core import db
from core.errors import FinalError
from core.stage import run_video_stage
from render import ffmpeg, frame_sheets, narration, remotion_render, sfx
from render.render import _srt_ts
from scenes import direction as short
from scenes import render as filming
from scenes import spec as scene_spec
from stages import direct
from stages.direct import _stub, timeline

NAME = "film"
MOST_REFUSALS = 3     # how many times a scene the stage refuses goes back to the director before it's an error for the owner
READY = """AND direction_json IS NOT NULL AND json_extract(direction_json, '$.approved') = 1
           AND NOT EXISTS (SELECT 1 FROM scenes s WHERE s.video_id = videos.id AND s.state != 'ok')"""
FPS = 30
LOOK_SIZE, LOOK_SAMPLES = (432, 768), 12
MOST_FRAME_REVIEWS = 2          # how many times a finished short goes back for what the frame reviewer found, before the owner sees it as it stands
FRAME_SHEET_EVERY = 1.5     # seconds between frames on the render card's sheet
SOUNDS = {"hit": ("impact_heavy", 0.55), "fly": ("whoosh_soft", 0.3), "go": ("whoosh_soft", 0.25), "rock": ("tap_heavy", 0.4), "step": ("tap", 0.16), "land": ("thud", 0.6)}


def run_once(ctx) -> bool:
    return run_video_stage(ctx, NAME, "generating", _work, where=READY, lease_s=6 * 3600)


def _key(scene: dict) -> str:
    return hashlib.sha256(json.dumps(scene, sort_keys=True).encode("utf-8")).hexdigest()[:16]


def _placeholder(scene: dict, out: Path, color: str) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg.run(["-f", "lavfi", "-i", f"color=c={color}:s=1080x1920:r={FPS}:d={scene['length']}", "-pix_fmt", "yuv420p",
                "-c:v", "libx264", "-preset", "ultrafast", out])
    return out


def _middle_frames(scene: dict) -> list[int]:
    """The frame in the middle of each of a scene's shots, as the renderer numbers them."""
    shots = scene["shots"]
    ends = [s["t"] for s in shots[1:]] + [scene["length"]]
    return [round((s["t"] + end) / 2 * FPS) + 1 for s, end in zip(shots, ends)]


def _look(ctx, conn, video, channel, direction: dict, clock: dict) -> list[dict]:
    """A frame of every shot, rendered small and rough, and what a viewer would see is wrong with them. A scene the stage
    itself refuses to build counts as a problem too: it goes back to the director with the reason."""
    where = ctx.media(video["id"]) / "film" / "look"
    shots, problems, tiles = [], [], []
    for i, directed in enumerate(direction["scenes"]):
        scene = short.local(directed)
        frames = _middle_frames(scene)
        out = where / _key(scene)
        try:
            if not (out / "frames" / "tracks.json").exists():
                filming.film(ctx.config, scene, out, samples=LOOK_SAMPLES, frames=frames, size=LOOK_SIZE, say=lambda _: None)
        except scene_spec.Refused as e:      # not physically right: every reason goes back, in full
            problems += [{"shot": f"scene {i + 1}", "what": why, "fix": "stage it so this can't happen"} for why in e.problems]
            continue
        except (RuntimeError, ValueError) as e:
            problems.append({"shot": f"scene {i + 1}", "what": str(e)[-400:], "fix": "stage it so this can't happen"})
            continue
        for shot, frame in zip(scene["shots"], frames):
            n = len(shots) + 1
            at = float(directed["from"]) + (frame - 1) / FPS      # when the frame on the sheet is, not when the shot starts
            shots.append(f"{n}. at {round(at, 1)} s, on {shot['on']}: {_being_said(clock, at)}")
            tiles.append({"view": str(n), "file": f"f_{frame:04d}.png", "folder": out / "frames"})
    if not tiles:
        return problems
    sheet = _tile_across(tiles, where)
    found = ctx.llm.check_film(channel, "\n".join(shots), sheet, ctx.meter(conn, video, NAME, "the look at the shots"))
    return problems + found


def _being_said(clock: dict, at: float) -> str:
    """What the voice is saying at a moment, word by word: the words of the line around it, marking where it is. A line can
    run longer than a shot, and the looker needs to know which part this frame goes with."""
    for line in clock["lines"]:
        if line["from"] <= at <= line["to"]:
            words = line["words"] or [{"word": line["text"], "t": line["from"]}]
            before = " ".join(w["word"] for w in words if w["t"] <= at)
            after = " ".join(w["word"] for w in words if w["t"] > at)
            return f'"{before} [this frame] {after}"'.replace(" ]", "]").replace(' "', '"')
    return "(a pause between lines)"


def _tile_across(tiles: list[dict], where: Path) -> Path:
    """The frames as one numbered sheet, from however many scenes' folders."""
    local = []
    for t in tiles:
        target = where / f"t_{t['view']}.png"
        Image.open(Path(t["folder"]) / t["file"]).convert("RGB").save(target)
        local.append({"view": t["view"], "file": target.name})
    return tile({"shots": local}, where, cell=(216, 384), columns=8)


def _film_all(ctx, video, direction: dict) -> list[dict]:
    """Every scene rendered, or kept from before. Each comes back with its file and its sounds' times."""
    made = []
    where = ctx.media(video["id"]) / "film"
    for i, directed in enumerate(direction["scenes"]):
        scene = short.local(directed)
        out = where / _key(scene)
        raw = out / "scene_raw.mp4"
        events: list = []
        if _stub(ctx):
            if not raw.exists():
                _placeholder(scene, raw, "0x5588bb" if i % 2 else "0x336699")
        else:
            record = out / "film.json"
            if not record.exists():
                ctx.events.emit("stage_progress", video["id"], stage=NAME, done=i, total=len(direction["scenes"]), unit="scenes")
                filmed = filming.film(ctx.config, scene, out)
                record.write_text(json.dumps({"events": filmed["events"]}), encoding="utf-8")
                shutil.rmtree(out / "frames", ignore_errors=True)   # thousands of big pictures, now in the clip
            events = json.loads(record.read_text(encoding="utf-8"))["events"]
        made.append({"clip": str(raw), "from": float(directed["from"]), "to": float(directed["to"]), "events": events})
    return made


def _props(ctx, video, conn, filmed: list[dict], clock: dict, marks: list | None = None) -> tuple[dict, dict]:
    """What Remotion needs: the clips, the narration line by line, sound on the hits, and the big captions."""
    files, segments, sounds = {}, [], []
    for i, f in enumerate(filmed):
        name = f"seg_{i:02d}.mp4"
        files[name] = f["clip"]
        segments.append({"clip": name, "from": f["from"], "to": f["to"]})
        for event in f["events"]:
            kind = SOUNDS.get(event["kind"])
            if kind:
                sound = sfx.make(kind[0], ctx.config.data_dir / "sfx")
                files[sound.name] = str(sound)
                sounds.append({"src": sound.name, "from": round(f["from"] + (event["frame"] - 1) / FPS, 3), "volume": kind[1]})
    # the read as one leveled track, as the approved machine short's was, with effects ducked where they land on a word
    read = [{"src": str(ctx.abs(s["audio_path"])), "duration": s["duration_ms"] / 1000} for s in db.scenes_for(conn, video["id"])]
    starts = [line["from"] for line in clock["lines"]]
    voice = narration.track(read, starts, ctx.media(video["id"]) / "film" / "voice.wav")
    files[voice.name] = str(voice)
    sounds = narration.duck([{"src": voice.name, "from": 0, "volume": 1.0}, *sounds], read, starts, voice.name)
    props = {"duration": clock["total"], "segments": segments, "screens": [], "labels": [], "tags": short.tags(marks), "tracks": {},
             "sounds": sounds, "footage": None, "captionStyle": "big", "captions": short.captions(clock)}
    return props, files


def _srt(clock: dict) -> str:
    rows = []
    for n, line in enumerate(clock["lines"], 1):
        rows += [str(n), f"{_srt_ts(round(line['from'] * 1000))} --> {_srt_ts(round(line['to'] * 1000))}", line["text"], ""]
    return "\n".join(rows)


def _frame_sheet(video_file: Path, out: Path) -> Path | None:
    """A strip of the finished short, for the render card."""
    folder = out.parent / "frame_sheet"
    folder.mkdir(parents=True, exist_ok=True)
    for old in folder.glob("f_*.png"):
        old.unlink()
    ffmpeg.run(["-i", video_file, "-vf", f"fps=1/{FRAME_SHEET_EVERY},scale=216:-1", folder / "f_%03d.png"])
    shots = [{"view": f"{round(i * FRAME_SHEET_EVERY, 1)} s", "file": p.name} for i, p in enumerate(sorted(folder.glob("f_*.png")))]
    if not shots:
        return None
    made = tile({"shots": shots}, folder, cell=(216, 384), columns=8)
    made.replace(out)
    return out


def _review(ctx, conn, video, channel, out: Path, direction: dict, clock: dict) -> list[dict]:
    """The finished short, gone through frame by frame by someone who didn't make it, for what breaks physics or how the world works. Jumps between frames with no cut there
    are measured first, and handed to them to look at."""
    cuts = [float(s["t"]) for directed in direction["scenes"] for s in directed["shots"]] + [float(directed["from"]) for directed in direction["scenes"]]
    jumped = frame_sheets.jumps(out, cuts)
    planned = f"The picture jumps from one frame to the next at these times, with no cut there: {', '.join(f'{t} s' for t in jumped)}. Some will be a fast move, and some a mistake." if jumped else "Nothing jumps from one frame to the next but at the cuts."
    said = "\n".join(f"{line['from']} s to {line['to']} s: {line['text']}" for line in clock["lines"])
    sheets = frame_sheets.sheets(out, out.parent / "frames_review")
    return ctx.llm.check_frames(channel, said, planned, sheets, frame_sheets.EVERY, ctx.meter(conn, video, NAME, "the review of the frames"))


def _work(ctx, conn, video) -> None:
    channel = ctx.channel(video["channel_id"])
    direction = json.loads(video["direction_json"])
    clock = timeline(ctx, conn, video)
    if not _stub(ctx) and not direction.get("look"):
        problems = _look(ctx, conn, video, channel, direction, clock)
        if problems:
            notes = [f"{direct.LOOK_NOTE}shot {p['shot']}: {p['what']} Fix: {p['fix']}" for p in problems]
            said = "\n".join(f"- {n}" for n in notes)
            ctx.events.emit("notice", video["id"], text=f"The look at the shots found {len(notes)} thing(s), so it's being directed again:\n{said}")
            with db.tx(conn):
                for note in notes:
                    db.add_feedback(conn, video["id"], "direct", note)
                # the rewrite goes through direct, and isn't looked at again: one pass only, as with the reviewer
                draft = json.loads(video["direction_draft_json"] or "{}")
                db.update_video(conn, video["id"], direction_json=None,
                                direction_draft_json=json.dumps({**draft, "looked": True}))
            return
        direction["look"] = 1
        db.update_video(conn, video["id"], direction_json=json.dumps(direction))
    try:
        filmed = _film_all(ctx, video, direction)
    except scene_spec.Refused as e:
        draft = json.loads(video["direction_draft_json"] or "{}")
        if draft.get("refused", 0) >= MOST_REFUSALS:
            raise FinalError(f"after {MOST_REFUSALS} tries a scene still isn't physically right: {e}") from None
        ctx.events.emit("notice", video["id"], text=f"A scene isn't physically right, so it's being directed again: {e}")
        with db.tx(conn):
            for why in e.problems:
                db.add_feedback(conn, video["id"], "direct", f"{direct.LOOK_NOTE}{why}")
            db.update_video(conn, video["id"], direction_json=None,
                            direction_draft_json=json.dumps({**draft, "looked": True, "refused": draft.get("refused", 0) + 1}))
        return
    out = ctx.media(video["id"]) / "film" / "short.mp4"
    if _stub(ctx) and remotion_render.missing():
        raise FinalError("this needs Remotion: cd render/remotion && npm install")
    props, files = _props(ctx, video, conn, filmed, clock, direction.get("marks"))
    stamp = out.with_suffix(".key")                 # this stage runs again from the top when the reviewer answers: the same short needn't be put together twice
    key = hashlib.sha256(json.dumps(props, sort_keys=True).encode("utf-8")).hexdigest()
    if not (out.exists() and stamp.exists() and stamp.read_text(encoding="utf-8") == key):
        remotion_render.render_machine(props, files, out, lambda done, total: ctx.events.emit(
            "stage_progress", video["id"], stage=NAME, done=done, total=total, unit="%"))
        stamp.write_text(key, encoding="utf-8")
    draft = json.loads(video["direction_draft_json"] or "{}")
    if not _stub(ctx) and draft.get("reviewed", 0) < MOST_FRAME_REVIEWS:
        problems = _review(ctx, conn, video, channel, out, direction, clock)
        if problems:
            notes = [f"{direct.LOOK_NOTE}at {p['at']}: {p['what']} Fix: {p['fix']}" for p in problems]
            said = "\n".join(f"- {n}" for n in notes)
            ctx.events.emit("notice", video["id"], text=f"The review of the frames found {len(notes)} thing(s), so it's being directed again:\n{said}")
            with db.tx(conn):
                for note in notes:
                    db.add_feedback(conn, video["id"], "direct", note)
                db.update_video(conn, video["id"], direction_json=None,
                                direction_draft_json=json.dumps({**draft, "looked": True, "reviewed": draft.get("reviewed", 0) + 1}))
            return
    srt = out.with_suffix(".srt")
    srt.write_text(_srt(clock), encoding="utf-8")
    sheet = _frame_sheet(out, out.with_name("frames.png"))
    with db.tx(conn):
        db.transition(conn, video["id"], "generating", "assembled", video_path=ctx.rel(out), srt_path=ctx.rel(srt),
                      chapters_json="[]", duration_ms=round(clock["total"] * 1000),
                      frames_path=ctx.rel(sheet) if sheet else None)
    ctx.events.emit("gate_reached", video["id"], gate="render")


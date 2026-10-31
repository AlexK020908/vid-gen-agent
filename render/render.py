"""Assembles scenes into the final MP4, a 60-second highlight reel, an SRT and chapters.

Two engines make the MP4: Remotion (Ken Burns, clips, word captions; render/remotion_render.py) and
ffmpeg (stills held for their audio), which is the fallback. In both, a clip plays once and its last
frame holds for the rest of the scene (looping would jump back to the first frame). The highlight reel,
SRT and chapters are the same for both. The audio is the timeline: each scene lasts as long as its narration.
"""
from __future__ import annotations

import hashlib
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable

from render import ffmpeg, remotion_render

HIGHLIGHT_INTRO_MS = 20_000
HIGHLIGHT_MAX_MS = 60_000


def _segment_path(seg_dir: Path, item: dict) -> Path:
    source = item.get("clip") or item["still"]
    key = hashlib.sha1(f"hold|{source}|{item['audio']}|{item['duration_ms']}".encode()).hexdigest()[:10]
    return seg_dir / f"seg_{item['idx']:03d}_{key}.mp4"


def _encode_segment(item: dict, out: Path) -> None:
    if out.exists():  # unchanged scene from an earlier pass
        return
    seconds = f"{item['duration_ms'] / 1000:.3f}"
    if item.get("clip"):
        inputs = ["-i", item["clip"], "-i", item["audio"]]
        fit = f"tpad=stop_mode=clone:stop_duration={seconds},{ffmpeg.FIT}"  # hold the last frame
    else:
        inputs = ["-loop", "1", "-framerate", str(ffmpeg.FPS), "-i", item["still"], "-i", item["audio"]]
        fit = ffmpeg.FIT
    tmp = out.with_suffix(".part.mp4")
    ffmpeg.run([*inputs, "-t", seconds, "-map", "0:v:0", "-map", "1:a:0", "-vf", fit, "-af", "apad",
                *ffmpeg.VIDEO_OUT, *ffmpeg.AUDIO_OUT, tmp])
    tmp.replace(out)


def _concat(parts: list[Path], out: Path, max_ms: int | None = None) -> None:
    listing = out.with_suffix(".txt")
    lines = []
    for p in parts:
        escaped = Path(p).resolve().as_posix().replace("'", "'\\''")
        lines.append(f"file '{escaped}'\n")
    listing.write_text("".join(lines), encoding="utf-8")
    limit = ["-t", f"{max_ms / 1000:.3f}"] if max_ms else []
    tmp = out.with_suffix(".part.mp4")
    ffmpeg.run(["-f", "concat", "-safe", "0", "-i", listing, *limit, "-c", "copy", "-movflags", "+faststart", tmp])
    tmp.replace(out)
    listing.unlink(missing_ok=True)


def _srt_ts(ms: int) -> str:
    h, rem = divmod(int(ms), 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _srt(items: list[dict], timings: list[tuple[int, int]]) -> str:
    blocks = []
    for n, (item, (start, end)) in enumerate(zip(items, timings), start=1):
        blocks.append(f"{n}\n{_srt_ts(start)} --> {_srt_ts(end)}\n{item['narration']}\n")
    return "\n".join(blocks)


def _chapters(items: list[dict], timings: list[tuple[int, int]], beats: list[dict]) -> list[dict]:
    chapters, seen = [], set()
    for item, (start, _) in zip(items, timings):
        b = item["beat_idx"]
        if b in seen:
            continue
        seen.add(b)
        beat = beats[b]
        chapters.append({"t_ms": start, "title": f"{beat['label']}: {beat['title']}"})
    if chapters:
        chapters[0]["t_ms"] = 0
    return chapters


def _highlight_picks(items: list[dict]) -> list[int]:
    """The opening 20 s, then clip scenes, up to 60 s in all. Indexes into `items`, in order."""
    picked, total = [], 0
    for i, item in enumerate(items):
        if total >= HIGHLIGHT_INTRO_MS:
            break
        picked.append(i)
        total += item["duration_ms"]
    for i, item in enumerate(items):
        if total >= HIGHLIGHT_MAX_MS:
            break
        if item.get("clip") and i not in picked:
            picked.append(i)
            total += item["duration_ms"]
    return sorted(picked)


def _cut_highlight(video: Path, ranges: list[tuple[int, int]], out: Path) -> None:
    """Cut [start, end) ms ranges out of the final MP4 (re-encoded so cuts land on any frame) and join them."""
    merged: list[list[int]] = []
    for start, end in ranges:
        if merged and merged[-1][1] == start:
            merged[-1][1] = end
        else:
            merged.append([start, end])
    parts, budget = [], HIGHLIGHT_MAX_MS
    for n, (start, end) in enumerate(merged):
        length = min(end - start, budget)
        if length <= 0:
            break
        budget -= length
        part = out.with_name(f"{out.stem}_part{n}.mp4")
        ffmpeg.run(["-ss", f"{start / 1000:.3f}", "-t", f"{length / 1000:.3f}", "-i", video,
                    "-map", "0:v:0", "-map", "0:a:0", *ffmpeg.VIDEO_OUT, *ffmpeg.AUDIO_OUT, part])
        parts.append(part)
    _concat(parts, out)
    for part in parts:
        part.unlink(missing_ok=True)


def render_video(items: list[dict], beats: list[dict], out_dir: Path,
                 progress: Callable[[int, int], None] | None = None,
                 engine: str = "ffmpeg", settings: dict | None = None) -> dict:
    """`items`: one dict per scene with idx, beat_idx, narration, duration_ms, audio, still, clip (optional),
    words (optional, Remotion captions), status (optional, Remotion's corner box with the day and the tracked
    amounts; stages/assemble.py statuses). `settings`: the render section of stickfleet.yaml (Remotion's
    concurrency and x264_preset). Raises if the engine fails; assemble decides about falling back."""
    out_dir.mkdir(parents=True, exist_ok=True)
    timings, t = [], 0
    for item in items:
        timings.append((t, t + item["duration_ms"]))
        t += item["duration_ms"]

    stamp = int(time.time() * 1000)
    video = out_dir / f"video_{stamp}.mp4"
    highlight = out_dir / f"highlight_{stamp}.mp4"
    picks = _highlight_picks(items)

    if engine == "remotion":
        settings = settings or {}
        remotion_render.render(items, video, progress, settings.get("concurrency"), settings.get("x264_preset"))
        _cut_highlight(video, [timings[i] for i in picks], highlight)
    elif engine == "ffmpeg":
        seg_dir = out_dir / "segments"
        seg_dir.mkdir(exist_ok=True)
        segments = [_segment_path(seg_dir, item) for item in items]
        workers = max(1, min(4, (os.cpu_count() or 2) // 2))
        done = 0
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(_encode_segment, item, seg) for item, seg in zip(items, segments)]
            for future in as_completed(futures):
                future.result()
                done += 1
                if progress:
                    progress(done, len(items))
        _concat(segments, video)
        _concat([segments[i] for i in picks], highlight, max_ms=HIGHLIGHT_MAX_MS)
    else:
        raise ValueError(f"render.engine must be remotion or ffmpeg, not {engine!r}")

    srt = out_dir / f"captions_{stamp}.srt"
    srt.write_text(_srt(items, timings), encoding="utf-8")

    return {"video": video, "highlight": highlight, "srt": srt, "timings": timings,
            "chapters": _chapters(items, timings, beats), "duration_ms": t, "engine": engine}

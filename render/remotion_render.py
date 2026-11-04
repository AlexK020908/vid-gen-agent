"""Runs the Remotion composition in render/remotion/ (Ken Burns, clips, word captions) and returns the MP4.

A clip plays once, then its last frame (extracted here) holds with a slow Ken Burns push for the rest
of the scene.

Named remotion_render so it doesn't shadow the render/remotion/ project folder. Remotion copies its
public dir into every bundle on Windows, so each render stages only the files it uses, as hardlinks.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from collections import deque
from pathlib import Path
from typing import Callable

from render import ffmpeg

PROJECT = Path(__file__).resolve().parent / "remotion"
CLI = PROJECT / "node_modules" / "@remotion" / "cli" / "remotion-cli.js"
ANSI = re.compile(r"\x1b\[[0-9;]*m")
RENDERED = re.compile(r"Rendered (\d+)/(\d+)")


def missing() -> str | None:
    """Why Remotion can't run here, or None if it can."""
    if not shutil.which("node"):
        return "Node.js isn't installed"
    if not CLI.exists():
        return "Remotion isn't installed (cd render/remotion && npm install)"
    return None


def _stage(src: str, dest: Path) -> None:
    try:
        os.link(src, dest)
    except OSError:  # another drive, or a filesystem without hardlinks
        shutil.copyfile(src, dest)


def render(items: list[dict], out: Path, progress: Callable[[int, int], None] | None = None,
           concurrency: int | str | None = None, x264_preset: str | None = None) -> Path:
    """`items` as for render.render_video, plus `words` (word timestamps relative to the scene)."""
    reason = missing()
    if reason:
        raise RuntimeError(reason)
    public = out.parent / f"{out.stem}_public"
    shutil.rmtree(public, ignore_errors=True)
    public.mkdir(parents=True)
    scenes, t = [], 0
    for item in items:
        files = {}
        for key in ("still", "audio", "clip"):
            src = item.get(key)
            if src:
                name = f"{item['idx']:03d}_{key}{Path(src).suffix}"
                _stage(src, public / name)
                files[key] = name
        clip_ms, hold = None, None
        if files.get("clip"):
            clip_ms = ffmpeg.duration_ms(public / files["clip"])
            hold = f"{item['idx']:03d}_hold.png"
            # every frame of the last second overwrites the same file, so the clip's last frame is what's left
            ffmpeg.run(["-sseof", "-1", "-i", public / files["clip"], "-update", "1", public / hold])
        scenes.append({"idx": item["idx"], "still": files["still"], "audio": files["audio"],
                       "clip": files.get("clip"), "clip_ms": clip_ms, "hold": hold, "start_ms": t,
                       "duration_ms": item["duration_ms"], "words": item.get("words") or [],
                       "status": item.get("status")})
        t += item["duration_ms"]
    extra = []
    if concurrency:
        extra.append(f"--concurrency={concurrency}")
    if x264_preset:
        extra.append(f"--x264-preset={x264_preset}")
    return _run("Video", {"scenes": scenes}, public, out, progress, extra)


def render_short(props: dict, files: dict[str, str], out: Path,
                 progress: Callable[[int, int], None] | None = None) -> Path:
    """One vertical composition (`ShortClip`, a machine shot with its overlays) to `out`. `files` maps the names
    the props use to the files on disk, staged as the public dir."""
    reason = missing()
    if reason:
        raise RuntimeError(reason)
    public = out.parent / f"{out.stem}_public"
    shutil.rmtree(public, ignore_errors=True)
    public.mkdir(parents=True)
    for name, src in files.items():
        _stage(src, public / name)
    return _run("ShortClip", props, public, out, progress, ["--crf=16"])


def render_machine(props: dict, files: dict[str, str], out: Path,
                   progress: Callable[[int, int], None] | None = None) -> Path:
    """A whole machine short (`MachineShort`: its segments, screens, overlays, narration and sound) to `out`.
    `files` maps the names the props use to the files on disk, staged as the public dir."""
    reason = missing()
    if reason:
        raise RuntimeError(reason)
    public = out.parent / f"{out.stem}_public"
    shutil.rmtree(public, ignore_errors=True)
    public.mkdir(parents=True)
    for name, src in files.items():
        _stage(src, public / name)
    _run("MachineShort", props, public, out, progress, ["--crf=17"])
    return _limit(out)


PEAK = 0.89   # -1 dBFS: an impact landing on a word sums past full scale and clips in Remotion's mix


def _limit(path: Path) -> Path:
    """Holds the mix's peaks under PEAK, leaving the picture as it is (copied, not re-encoded)."""
    tmp = path.with_suffix(".limited.mp4")
    ffmpeg.run(["-i", path, "-c:v", "copy", "-af", f"alimiter=limit={PEAK}:attack=3:release=60:level=0",
                "-c:a", "aac", "-b:a", "192k", tmp])
    tmp.replace(path)
    return path


def _run(composition: str, props_data: dict, public: Path, out: Path,
         progress: Callable[[int, int], None] | None, extra: list[str]) -> Path:
    props = out.with_suffix(".props.json")
    props.write_text(json.dumps(props_data), encoding="utf-8")
    tmp = out.with_suffix(".part.mp4")
    cmd = ["node", str(CLI), "render", "src/index.ts", composition, str(tmp),
           f"--props={props}", f"--public-dir={public}", "--overwrite", *extra]

    tail: deque[str] = deque(maxlen=30)
    errors: list[str] = []   # the error's own lines, which a long stack trace would push out of the tail
    shown = -1
    try:
        proc = subprocess.Popen(cmd, cwd=PROJECT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, encoding="utf-8", errors="replace", env={**os.environ, "NO_COLOR": "1"})
        assert proc.stdout is not None
        for raw in proc.stdout:
            line = ANSI.sub("", raw).strip()
            if not line:
                continue
            tail.append(line)
            if "Error" in line or "error:" in line.lower():
                errors.append(line)
            m = RENDERED.search(line)
            if m and progress:
                pct = int(m.group(1)) * 100 // max(1, int(m.group(2)))
                if pct != shown:
                    shown = pct
                    progress(pct, 100)
        code = proc.wait()
        if code != 0:
            raise RuntimeError(f"remotion exited with {code}: " + " | ".join(errors[:6])[:900] + " ... "
                               + " | ".join(tail)[-500:])
        tmp.replace(out)
        if progress and shown < 100:  # its last progress line is frame N-1 of N
            progress(100, 100)
    finally:
        shutil.rmtree(public, ignore_errors=True)
        props.unlink(missing_ok=True)
        tmp.unlink(missing_ok=True)
    return out

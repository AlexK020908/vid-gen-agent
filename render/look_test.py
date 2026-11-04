"""Phase 23's look test (SHORTS.md): three of reference A's opening shots made in Blender, with a first overlay,
each laid beside A's frame at the same moment, and the seconds a frame measured. `run.py look-test` runs it.

Everything lands in data/looktest/: <shot>.mp4 (with overlays), <shot>_raw.mp4, looktest.mp4 (the shots in a
row), compare_<shot>.png (ours on the left, A's on the right), compare.png (all three) and bench.json.
"""
from __future__ import annotations

import json
import statistics
import time
from pathlib import Path

from render import blender_render, ffmpeg, remotion_render

REFERENCE = "06908b699fc64aa89e18176103c474fa.mov"   # A, the diesel pile hammer, in the workspace folder
# per shot: the overlay, and the moments compared, (our frame, A's second): ours on the left, A's on the right
SHOTS = {
    "nail": {
        "compare": [(18, 2.0), (78, 4.0)],   # a tap landing, then the nail settled
        "captions": [{"text": "Pick up a hammer", "from": 0, "to": 15},
                     {"text": "give it a few light taps", "from": 15, "to": 60},
                     {"text": "and it goes right into the wood", "from": 60, "to": 10_000}],
        "callouts": [],
        "tags": [],
    },
    "crane": {
        "compare": [(60, 27.0)],
        "captions": [{"text": "Hoisting it with a crane every time\nis far too slow", "from": 0, "to": 10_000}],
        "callouts": [{"label": "Iron block", "anchor": "iron_block", "tone": "yellow", "from": 8, "to": 10_000,
                      "side": "left"}],
        "tags": [{"kind": "fail", "text": "Too slow", "icon": "clock", "from": 30, "to": 10_000,
                  "at": [0.71, 0.255]}],
    },
    "air": {
        "compare": [(60, 84.0)],
        "captions": [{"text": "it compresses the air\ninside the cylinder", "from": 0, "to": 10_000}],
        "callouts": [{"label": "Air", "anchor": "air", "tone": "blue", "from": 10, "to": 10_000, "side": "left"}],
        "tags": [{"kind": "mode", "text": "Slow motion", "from": 0, "to": 10_000}],
    },
}


def _frame(video: Path, seconds: float, out: Path, width=1080, height=1920) -> Path:
    ffmpeg.run(["-ss", seconds, "-i", video, "-frames:v", 1, "-vf",
                f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2",
                out])
    return out


def run(config, shots=None, samples=None, reference: Path | None = None, say=print) -> dict:
    out = config.data_dir / "looktest"
    out.mkdir(parents=True, exist_ok=True)
    reference = Path(reference) if reference else config.root.parent / REFERENCE
    bench = {}
    pairs, finals = [], []
    for name in shots or SHOTS:
        spec = SHOTS[name]
        frames_dir = out / "frames" / name
        say(f"{name}: rendering in Blender")
        started = time.perf_counter()
        last = [0]

        def progress(i, n, last=last):
            if i - last[0] >= 15 or i == n:
                last[0] = i
                say(f"  {name}: frame {i}/{n}")

        tracks = blender_render.render_shot(config, name, frames_dir, samples=samples, progress=progress)
        blender_s = time.perf_counter() - started
        raw = blender_render.encode(frames_dir, out / f"{name}_raw.mp4", tracks["fps"])
        say(f"{name}: overlays in Remotion")
        props = {"clip": "clip.mp4", "frames": tracks["frames"], "captions": spec["captions"], "captionStyle": "box",
                 "callouts": spec["callouts"], "tags": spec["tags"], "anchors": tracks["anchors"]}
        final = remotion_render.render_short(props, {"clip.mp4": str(raw)}, out / f"{name}.mp4")
        finals.append(final)
        per = tracks["render_s"][1:] or tracks["render_s"]
        bench[name] = {"frames": tracks["frames"], "blender_s": round(blender_s, 1),
                       "first_frame_s": tracks["render_s"][0], "median_frame_s": round(statistics.median(per), 3),
                       "samples": samples or config.blender.get("samples", 32)}
        for k, (frame, ref_s) in enumerate(spec["compare"]):
            tag = f"{name}" if k == 0 else f"{name}_{k + 1}"
            ours = _frame(final, (frame - 1) / tracks["fps"], out / f"ours_{tag}.png")   # Blender counts from 1
            if reference.exists():
                theirs = _frame(reference, ref_s, out / f"ref_{tag}.png")
                pair = out / f"compare_{tag}.png"
                ffmpeg.run(["-i", ours, "-i", theirs, "-filter_complex", "hstack=2", pair])
                pairs.append(pair)
    if pairs:
        args = []
        for p in pairs:
            args += ["-i", p]
        ffmpeg.run([*args, "-filter_complex", f"vstack={len(pairs)}" if len(pairs) > 1 else "null",
                    out / "compare.png"])
    if finals:   # the shots one after another, to watch in a row
        args = []
        for f in finals:
            args += ["-i", f]
        joined = "".join(f"[{i}:v]" for i in range(len(finals))) + f"concat=n={len(finals)}:v=1:a=0[v]"
        ffmpeg.run([*args, "-filter_complex", joined, "-map", "[v]", "-c:v", "libx264", "-crf", 16,
                    "-pix_fmt", "yuv420p", out / "looktest.mp4"])
    (out / "bench.json").write_text(json.dumps(bench, indent=1), encoding="utf-8")
    return bench

"""Phase 32's look test (CHARACTERS.md): one person made with Human Generator, in one close-up, laid beside the owner's
reference frame, and the seconds a frame measured. `run.py character-test` runs it.

Everything lands in data/characters/look_test/: person/ (the saved person), portrait.mp4, ours.png (the frame after the
bite), compare.png (ours on the left, the reference on the right) and bench.json.
"""
from __future__ import annotations

import json
import shutil
import statistics
import time
from pathlib import Path

from render import blender_render, ffmpeg, humgen
from render.look_test import _frame

COMPARE_FRAME = 104                                   # the bite held, eyes wide, before the last blink
REFERENCE = "benchmarks/character_look/reference.png"
# toward the reference's kind of figure, on any preset: young, clean-shaven, brown hair, blue eyes, a pale top
LOOK = {"age": 40, "face_hair": False, "eye_color": [0.17, 0.33, 0.62], "clothes": {"Sweater": [0.72, 0.72, 0.70]},
        "hair_color": {"lightness": 1.1, "redness": 0.38, "salt_and_pepper": 0.0},
        "brow_color": {"lightness": 0.55, "redness": 0.5}, "brow_density": 2, "textures_8k": True,
        "keys": {"Stylized": 0.4, "Eye Scale": 0.6}}


def person(config, gender="male", preset=None, hair=None, outfit=None) -> dict:
    """A person spec, taking the first of whatever isn't named."""
    found = humgen.options(config)

    def pick(kind, wanted):
        choices = found[kind][gender]
        if not wanted:
            return choices[0] if choices else None
        matches = [c for c in choices if wanted.lower() in c.lower()]
        if not matches:
            raise ValueError(f"no {kind} matching {wanted!r}: {choices}")
        return matches[0]

    return {"gender": gender, "preset": pick("humans", preset), "hair": pick("hair", hair),
            "outfit": pick("outfit", outfit), **LOOK}


def run(config, spec: dict, samples=None, engine=None, frames=None, say=print) -> dict:
    out = config.data_dir / "characters" / "look_test"
    out.mkdir(parents=True, exist_ok=True)
    say(f"making the person: {spec}")
    started = time.perf_counter()
    blender_render.make_person(config, spec, out / "person", say)
    made_s = time.perf_counter() - started

    say(f"rendering the shot{f' ({engine})' if engine else ''}")
    frames_dir = out / "frames"
    last = [0]

    def progress(i, n):
        if i - last[0] >= 15 or i == n:
            last[0] = i
            say(f"  frame {i}/{n}")

    wanted = sorted(set(frames) | {COMPARE_FRAME}) if frames else None
    started = time.perf_counter()
    tracks = blender_render.render_shot(config, "portrait", frames_dir, samples=samples, frames=wanted,
                                        progress=progress, person=out / "person", engine=engine)
    blender_s = time.perf_counter() - started
    per = tracks["render_s"][1:] or tracks["render_s"]
    bench = {"person_s": round(made_s, 1), "frames": len(tracks["rendered"]), "blender_s": round(blender_s, 1),
             "first_frame_s": tracks["render_s"][0], "median_frame_s": round(statistics.median(per), 3),
             "samples": samples or config.blender.get("samples", 32), "engine": engine or "eevee"}

    ours = out / "ours.png"
    shutil.copy(frames_dir / f"f_{COMPARE_FRAME:04d}.png", ours)
    if not frames:
        blender_render.encode(frames_dir, out / "portrait.mp4", tracks["fps"])
    reference = config.data_dir / REFERENCE
    if reference.exists():
        theirs = _frame(reference, 0, out / "reference.png")
        ffmpeg.run(["-i", ours, "-i", theirs, "-filter_complex", "hstack=2", out / "compare.png"])
    (out / "bench.json").write_text(json.dumps(bench, indent=1), encoding="utf-8")
    return bench

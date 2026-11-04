"""A scene rendered: checked, its people made if they haven't been, staged in Blender (blender/stage.py), and captioned.
The same for every topic, so a new one needs a scene file and no new code."""
from __future__ import annotations

import json
import statistics
import time
from pathlib import Path

from characters import build
from characters import spec as character_spec
from render import blender_render, clips, remotion_render
from scenes import spec as scene_spec
from things import build as thing_build


def problems(config, scene: dict) -> list[str]:
    return scene_spec.check(scene, character_spec.all_ids(), list(clips.catalog(config)), thing_build.menu(config))


def used_things(scene: dict, config) -> list[str]:
    known = thing_build.menu(config)
    return sorted({c["prop"] for c in scene["cast"].values() if c["type"] == "prop" and c["prop"] in known})


def film(config, scene: dict, out: Path, samples=None, frames=None, size=(1080, 1920), say=print) -> dict:
    """Into `out`: frames/, scene_raw.mp4 unless `frames` asks for just some, credits.txt and bench.json. Returns the bench,
    with what the scene's sounds need."""
    wrong = problems(config, scene)
    if wrong:
        raise ValueError("; ".join(wrong))
    out = Path(out)
    characters = sorted({c["character"] for c in scene["cast"].values() if c["type"] == "person"})
    for cid in characters:
        if not (build.folder(config, cid) / "person.blend").exists():
            build.build(config, cid, say)
    things = {tid: thing_build.build(config, tid, say=say) for tid in used_things(scene, config)}
    credits = sorted({t["manifest"]["credit"] for t in things.values() if t["manifest"].get("credit")})
    last = [0]

    def progress(i, n):
        if i - last[0] >= 20 or i == n:
            last[0] = i
            say(f"  frame {i}/{n}")

    started = time.perf_counter()
    refused = out / "frames" / "refused.json"
    refused.unlink(missing_ok=True)
    try:
        tracks = blender_render.render_stage(config, scene, {cid: build.folder(config, cid) for cid in characters},
                                             clips.catalog(config), out / "frames", size=size, samples=samples, frames=frames,
                                             progress=progress, things={tid: t["folder"] for tid, t in things.items()})
    except RuntimeError:
        if refused.exists():
            raise scene_spec.Refused(json.loads(refused.read_text(encoding="utf-8"))) from None
        raise
    per = tracks["render_s"][1:] or tracks["render_s"]
    bench = {"frames": len(tracks["rendered"]), "blender_s": round(time.perf_counter() - started, 1),
             "median_frame_s": round(statistics.median(per), 3) if per else 0,
             "samples": samples or config.blender.get("samples", 32)}
    raw = None if frames else blender_render.encode(out / "frames", out / "scene_raw.mp4", tracks["fps"])
    (out / "bench.json").write_text(json.dumps(bench, indent=1), encoding="utf-8")
    (out / "credits.txt").write_text("\n".join(credits), encoding="utf-8")   # for the video's description
    return {**bench, "raw": raw, "fps": tracks["fps"], "total_frames": tracks["frames"], "events": tracks["events"]}


def render(config, scene: dict, out: Path, samples=None, frames=None, size=(1080, 1920), say=print) -> dict:
    """A scene on its own, with the captions it has written: filmed, and into `out`/scene.mp4 unless it's a quick look."""
    made = film(config, scene, out, samples, frames, size, say)
    if not frames:
        fps = made["fps"]
        captions = [{"text": c["text"], "from": round(c["t"] * fps), "to": round(c["to"] * fps)}
                    for c in scene.get("captions") or []]
        props = {"clip": "clip.mp4", "frames": made["total_frames"], "captions": captions, "captionStyle": "big",
                 "callouts": [], "tags": [], "anchors": {}}
        say("captions in Remotion")
        remotion_render.render_short(props, {"clip.mp4": str(made["raw"])}, Path(out) / "scene.mp4")
    return made

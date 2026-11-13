"""Runs Blender on one shot (blender/run.py) and encodes its frames into a clip.

Blender runs with no window, `--factory-startup` (none of the owner's own Blender settings or add-ons) and
`--python-exit-code 1`, so a script error fails the render instead of leaving a half-made folder.
"""
from __future__ import annotations

import json
import re
import subprocess
from collections import deque
from pathlib import Path
from typing import Callable

from render import assets, ffmpeg, limits

ROOT = Path(__file__).resolve().parent.parent
RUNNER = ROOT / "blender" / "run.py"
FRAME = re.compile(r"^FRAME (\d+)/(\d+|\?)")
TEXTURES = ("red_sand", "oak_veneer_01")      # what blender/materials.py's palette loads
HDRIS = ("kloofendal_43d_clear_puresky",)     # what blender/envs.py's worlds load
PLACE_SKY = "4k"                              # how big a place's sky is fetched: it fills the picture, a little out of focus
PLACE_GROUND = "4k"                           # and its ground: someone lying on it is seen from close up


def exe(config) -> Path:
    return ROOT / config.blender.get("path", "tools/blender-5.2.3-windows-x64/blender.exe")


def missing(config) -> str | None:
    """Why Blender can't run here, or None if it can."""
    if not exe(config).exists():
        return f"Blender isn't at {exe(config)} (blender.path in stickfleet.yaml)"
    return None


def run_job(config, job: dict, out_dir: Path, progress: Callable[[int, int], None] | None = None) -> None:
    """Run one job in Blender (blender/run.py reads it). The textures and HDRIs it may use are fetched first and
    added to it."""
    reason = missing(config)
    if reason:
        raise RuntimeError(reason)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    place = (job.get("scene") or {}).get("place") or {}
    job = {**job, "out": str(out_dir),
           "textures": {**{t: assets.texture(config.data_dir, t) for t in TEXTURES}, **({place["ground"]: assets.texture(config.data_dir, place["ground"], PLACE_GROUND)} if place.get("ground") else {})},
           "hdris": {**{h: assets.hdri(config.data_dir, h) for h in HDRIS}, **({place["sky"]: assets.hdri(config.data_dir, place["sky"], PLACE_SKY)} if place.get("sky") else {})}}
    job_path = out_dir / "job.json"
    job_path.write_text(json.dumps(job, indent=1), encoding="utf-8")
    cmd = [str(exe(config)), "-b", "-t", str(limits.threads(config)), "--factory-startup", "--python-exit-code", "1",
           "-P", str(RUNNER), "--", str(job_path)]
    tail: deque[str] = deque(maxlen=40)
    proc = limits.start(config, cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                        encoding="utf-8", errors="replace")    # under render.limits: its cores and priority
    assert proc.stdout is not None
    for raw in proc.stdout:
        line = raw.strip()
        if not line:
            continue
        tail.append(line)
        m = FRAME.match(line)
        if m and progress:
            progress(int(m.group(1)), int(m.group(2)) if m.group(2) != "?" else 0)
    if proc.wait() != 0:
        raise RuntimeError(f"blender failed on {job.get('kind') or job.get('shot')}: " + " | ".join(tail)[-1500:])


def render_shot(config, shot: str, out_dir: Path, size=(1080, 1920), fps=30, samples: int | None = None,
                frames: list[int] | None = None, progress: Callable[[int, int], None] | None = None,
                look: str | None = None, person: Path | None = None, engine: str | None = None) -> dict:
    """Render `shot` into `out_dir` as f_0001.png ... and tracks.json. Returns tracks.json's contents. `person` is
    the folder of a saved person, for a character shot."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("f_*.png"):
        old.unlink()
    run_job(config, {"shot": shot, "size": list(size), "fps": fps,
                     "samples": int(samples or config.blender.get("samples", 32)), "frames": frames,
                     "look": look or config.blender.get("look"), "person": str(person) if person else None,
                     "engine": engine}, out_dir, progress)
    return json.loads((out_dir / "tracks.json").read_text(encoding="utf-8"))


def render_stage(config, scene: dict, folders: dict, catalog: dict, out_dir: Path, size=(1080, 1920), fps=30,
                 samples: int | None = None, frames: list[int] | None = None,
                 progress: Callable[[int, int], None] | None = None, things: dict | None = None) -> dict:
    """A scene (blender/stage.py, already checked by scenes/spec.py) into `out_dir`. `folders` maps each character it uses
    to their saved person, `things` each thing to its saved folder, and `catalog` is render/clips.py's."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    if frames is None:
        for old in out_dir.glob("f_*.png"):
            old.unlink()
    used = {c["stance"]: catalog[c["stance"]] for c in scene["cast"].values() if c["type"] == "person"}
    used |= {e["clip"]: catalog[e["clip"]] for e in scene.get("happens") or [] if e.get("do") in ("act", "walk")}
    run_job(config, {"kind": "stage", "scene": scene, "folders": {k: str(v) for k, v in folders.items()}, "catalog": used,
                     "things": {k: str(v) for k, v in (things or {}).items()},
                     "size": list(size), "fps": fps, "samples": int(samples or config.blender.get("samples", 32)),
                     "frames": frames, "look": config.blender.get("look")}, out_dir, progress)
    return json.loads((out_dir / "tracks.json").read_text(encoding="utf-8"))


def make_thing(config, spec: dict, source: dict, out_dir: Path) -> dict:
    """A thing's file into `out_dir` (blender/things.py), the right size and the right way up. Returns its thing.json."""
    out_dir = Path(out_dir)
    run_job(config, {"kind": "thing", "spec": spec, "source": source}, out_dir)
    return json.loads((out_dir / "thing.json").read_text(encoding="utf-8"))


def thing_sheet(config, thing: Path, size=(540, 720), samples: int = 24) -> dict:
    """A saved thing's sheet into <thing>/sheet/. Returns sheet.json."""
    out_dir = Path(thing) / "sheet"
    run_job(config, {"kind": "thing_sheet", "thing": str(thing), "size": list(size), "samples": samples,
                     "look": config.blender.get("look")}, out_dir)
    return json.loads((out_dir / "sheet.json").read_text(encoding="utf-8"))


def make_person(config, person: dict, out_dir: Path, say=print) -> dict:
    """Make a person with Human Generator (blender/humgen.py) into `out_dir`, unless the same one is already there.
    Returns its person.json."""
    from render import humgen
    out_dir = Path(out_dir)
    made = out_dir / "person.json"
    if made.exists() and (out_dir / "person.blend").exists():
        manifest = json.loads(made.read_text(encoding="utf-8"))
        if manifest.get("spec") == person:
            return manifest
    run_job(config, {"kind": "person", "person": person, "humgen": humgen.install(config, say)}, out_dir)
    return json.loads(made.read_text(encoding="utf-8"))


def render_segment(config, timeline: dict, out_dir: Path, size=(1080, 1920), fps=30, samples: int | None = None,
                   frames: list[int] | None = None, render: bool = True,
                   progress: Callable[[int, int], None] | None = None) -> dict:
    """One segment of a machine short (blender/shots.py) into `out_dir` as f_NNNN.png, numbered by the whole
    short's frames, and tracks.json. Every machine in machines/specs/ is passed by its file's name."""
    from machines import spec as machine_spec
    specs = {p.stem: machine_spec.load(p) for p in sorted((ROOT / "machines" / "specs").glob("*.json"))}
    for mid, m in (timeline.get("models") or {}).items():
        if m["spec"] not in specs:
            raise ValueError(f"model {mid}: no machine called {m['spec']} in machines/specs")
    people = {}
    for pid, p in (timeline.get("people") or {}).items():   # a character's id, or a folder of a saved person
        folder = config.data_dir / "characters" / p["person"]
        if not (folder / "person.blend").exists():
            raise ValueError(f"person {pid}: {p['person']} hasn't been made (run.py characters {p['person']})")
        people[p["person"]] = str(folder)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    if render and frames is None:
        for old in out_dir.glob("f_*.png"):
            old.unlink()
    run_job(config, {"kind": "segment", "timeline": timeline, "specs": specs, "people": people, "size": list(size), "fps": fps,
                     "samples": int(samples or config.blender.get("samples", 32)), "frames": frames,
                     "render": render, "look": config.blender.get("look")}, out_dir, progress)
    return json.loads((out_dir / "tracks.json").read_text(encoding="utf-8"))


def portraits(config, person: Path, size=(540, 960), samples: int = 32) -> dict:
    """A saved person's portraits (blender/portraits.py) into <person>/portraits/. Returns portraits.json."""
    out_dir = Path(person) / "portraits"
    run_job(config, {"kind": "portraits", "person": str(person), "size": list(size), "samples": samples,
                     "look": config.blender.get("look")}, out_dir)
    return json.loads((out_dir / "portraits.json").read_text(encoding="utf-8"))


def turnaround(config, spec: dict, out_dir: Path, size=(432, 768), samples: int = 16,
               unframed: list[str] | None = None) -> dict:
    """A machine's turnaround (blender/turnaround.py): every step from four sides, cut open where it's cut, and
    the overlap check. The spec is checked first (machines/spec.py), and a bad one never reaches Blender.
    `unframed` parts are drawn but left out of the framing (the pile under a hammer)."""
    from machines import spec as machine_spec
    problems = machine_spec.check(spec)
    if problems:
        return {"name": spec.get("name"), "problems": problems, "shots": []}
    run_job(config, {"kind": "turnaround", "spec": spec, "size": list(size), "samples": samples,
                     "unframed": unframed or []}, out_dir)
    return json.loads((Path(out_dir) / "turnaround.json").read_text(encoding="utf-8"))


def encode(frames_dir: Path, out: Path, fps: int = 30) -> Path:
    """The shot's frames as an H.264 clip, near-lossless so the overlay render starts from clean pictures."""
    ffmpeg.run(["-framerate", fps, "-i", Path(frames_dir) / "f_%04d.png", "-c:v", "libx264", "-preset", "medium",
                "-crf", "14", "-pix_fmt", "yuv420p", out])
    return out

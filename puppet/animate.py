"""Turns a scene sheet into a clip: who is where doing what, from when to when, what stands in the place, with
the camera and the light.

A sheet:
    {"stage": Stage, "puppets": {"hero": Puppet, "eli": Puppet}, "props": Puppet (the props as parts),
     "set": {"plate": {"at": "stairs_top", "angle": 0}},          # what stands in the place (puppet/state.py)
     "duration_ms": 10340, "fps": 30,
     "light": {"level": 0.6, "color": [0.8, 0.84, 1.0],
               "glow": {"at": "lamp" or a spot or [x, y], "radius": 0.35 (of the picture's height),
                        "color": [255, 226, 170], "strength": 0.9}},
     "figures": [{"who": "hero", "actions": [
         {"from_ms": 0, "to_ms": 6500, "do": "limp", "start": "door_left", "end": "stairs_top"},
         {"from_ms": 6500, "to_ms": 7400, "do": "stand"},
         {"from_ms": 7400, "to_ms": 10340, "do": "kneel_work", "facing": "right"}],
       "attached": {"r_hand": {"prop": "drill", "angle": 0}}}],  # held or pressed on: joint -> prop
     "camera": [{"at_ms": 0, "center": "door_left", "zoom": 1.5},
                {"at_ms": 6500, "center": "stairs_top", "zoom": 1.5}]}

`do` is a pose (puppet/rig.py POSES) the figure settles into, or a cycle (CYCLES) it walks with from `start`
to `end`; a spot name or [x, y] in stage pixels. A figure's first action says where it begins. Things are
drawn back to front by where they meet the floor, with the stage's foreground cutouts in between. Frames go
straight to ffmpeg; nothing is written but the clip.
"""
from __future__ import annotations

import math
import subprocess
from pathlib import Path
from typing import Callable

from PIL import Image

from puppet import draw, rig
from puppet.stage import Stage
from render import ffmpeg

OUT_SIZE = (1920, 1080)
TRANSITION_MS = 450      # settling from one pose into the next (a figure standing still holds dead still: the
                         # hand-drawn jitter its joints had read as shaking, video 5)
LOOK_AT = 0.45           # a camera aimed at a spot looks this far up a figure standing there, in H


SIDE = 0.34              # a `side` stands a figure this far left or right of a spot, in the adult height there


def _xy(stage: Stage, where, side: str | None = None) -> tuple[float, float]:
    x, y = stage.spot(where) if isinstance(where, str) else (float(where[0]), float(where[1]))
    if side in ("left", "right"):
        x += (SIDE * stage.height_at(x, y)) * (1 if side == "right" else -1)
    return (x, y)


def _pose(action: dict, p: float, H: float, dist: float, before: rig.Pose, elapsed_ms: float,
          free: bool = False) -> rig.Pose:
    """`free`: the figure has no cane, so the poses that hold one hang the right arm instead."""
    name = action["do"]
    ease = rig.smooth(elapsed_ms / TRANSITION_MS)
    hand = rig.free_hand if free else (lambda pose: pose)
    if name in rig.CYCLES:
        length = action["to_ms"] - action["from_ms"]
        cycles = max(1, round(dist / (rig.STRIDE * H))) if dist > 1 else max(1, round(length / 700))
        now = hand(rig.cycle(rig.CYCLES[name], p * cycles + float(action.get("phase", 0.0))))  # a crowd's are apart
        return rig.blend(before, now, ease) if ease < 1 else now
    if name not in rig.POSES:
        raise ValueError(f"no pose or cycle called {name!r} (poses: {', '.join(rig.POSES)}; "
                         f"cycles: {', '.join(rig.CYCLES)})")
    return rig.blend(before, hand(rig.POSES[name]), ease)


def figure_at(stage: Stage, puppet, actions: list[dict], t_ms: float, attached: dict | None = None) -> draw.Figure | None:
    """Where the figure is and how it stands at `t_ms`, walking through its actions in order. None before
    its first action and while it's `inside` something."""
    actions = sorted(actions, key=lambda a: a["from_ms"])
    if not actions or t_ms < actions[0]["from_ms"]:
        return None
    first = actions[0]
    pos = _xy(stage, first.get("start") or first.get("at") or next(iter(stage.spots.values())), first.get("side"))
    free = not any(p.slot == "cane" for p in getattr(puppet, "parts", {}).values())
    facing, before = 1, rig.free_hand(rig.STAND) if free else rig.STAND
    for i, a in enumerate(actions):
        if a.get("start") or a.get("at"):
            pos = _xy(stage, a.get("start") or a.get("at"), a.get("side"))
        target = _xy(stage, a["end"], a.get("side")) if a.get("end") else None
        dist = math.hypot(target[0] - pos[0], target[1] - pos[1]) if target else 0.0
        if target and abs(target[0] - pos[0]) > 1:
            facing = 1 if target[0] > pos[0] else -1
        if "facing" in a:
            facing = 1 if str(a["facing"]).lower() in ("right", "1") else -1
        length = max(1.0, a["to_ms"] - a["from_ms"])
        active = i == len(actions) - 1 or t_ms < actions[i + 1]["from_ms"]
        scale = getattr(puppet, "scale", 1.0)
        if a["do"] == rig.INSIDE:
            if active:
                return None
            continue                      # they come out where they went in, as they were
        if active:
            p = min(1.0, max(0.0, (t_ms - a["from_ms"]) / length))
            now = (pos[0] + (target[0] - pos[0]) * p, pos[1] + (target[1] - pos[1]) * p) if target else pos
            H = stage.height_at(*now) * scale
            pose = _pose(a, p, H, dist, before, t_ms - a["from_ms"], free)
            return draw.Figure(puppet, pose, now, H, facing, dict(attached or {}),
                               str(a.get("look", "")).lower() == "camera")
        if target:
            pos = target
        before = _pose(a, 1.0, stage.height_at(*pos) * scale, dist, before, length, free)
    return None


def _aim(stage: Stage, where, t_ms: float = 0.0, locate=None) -> tuple[float, float]:
    """A camera center: a spot name means the middle of a person standing there, not their feet; a figure's
    key means that person wherever they are at `t_ms` (`locate(key, t_ms)` finds them)."""
    if isinstance(where, str) and where not in stage.spots and locate:
        found = locate(where, t_ms)
        if found:
            return found
    x, y = _xy(stage, where)
    return (x, y - LOOK_AT * stage.height_at(x, y)) if isinstance(where, str) else (x, y)


def camera_at(stage: Stage, keys: list[dict], t_ms: float, locate=None) -> tuple[tuple[float, float], float]:
    if not keys:
        return (stage.size[0] / 2, stage.size[1] / 2), 1.0
    keys = sorted(keys, key=lambda k: k["at_ms"])
    if t_ms <= keys[0]["at_ms"]:
        return _aim(stage, keys[0]["center"], t_ms, locate), float(keys[0].get("zoom", 1.0))
    for a, b in zip(keys, keys[1:]):
        if a["at_ms"] <= t_ms < b["at_ms"]:
            p = rig.smooth((t_ms - a["at_ms"]) / max(1.0, b["at_ms"] - a["at_ms"]))
            ca, cb = _aim(stage, a["center"], t_ms, locate), _aim(stage, b["center"], t_ms, locate)
            za, zb = float(a.get("zoom", 1.0)), float(b.get("zoom", 1.0))
            return (ca[0] + (cb[0] - ca[0]) * p, ca[1] + (cb[1] - ca[1]) * p), za + (zb - za) * p
    return _aim(stage, keys[-1]["center"], t_ms, locate), float(keys[-1].get("zoom", 1.0))


class Scene:
    def __init__(self, sheet: dict) -> None:
        self.sheet = sheet
        self.stage: Stage = sheet["stage"]
        self.fps = int(sheet.get("fps", ffmpeg.FPS))
        self.frames = max(1, math.ceil(sheet["duration_ms"] * self.fps / 1000))
        with Image.open(self.stage.picture) as img:
            self.background = img.convert("RGB")
        self.tint = self._light(sheet.get("light"))
        self.props = sheet.get("props")
        self.placed = []  # (base y, part, at, H, angle, ground) for what stands in the place
        for name, placement in (sheet.get("set") or {}).items():
            if not self.props or name not in self.props:
                raise ValueError(f"the set places {name!r}, which isn't among the props")
            part = self.props[name]
            x, y = _xy(self.stage, placement["at"])
            H = self.stage.height_at(x, y)
            dx, dy = placement.get("offset") or (0, 0)
            ground = (x + dx * H, y + dy * H)
            at = ground
            if placement.get("lift"):   # hovering: its shadow stays down, and it stays in the picture (video 5's
                above = part.pivot[1] / part.image.height * part.height * H        # helicopter went off the top)
                at = (ground[0], max(ground[1] - float(placement["lift"]) * H, above + 0.03 * self.stage.size[1]))
            self.placed.append((ground[1], part, at, H, float(placement.get("angle", 0.0)), ground))
        self.cutouts = [(o["base_y"], *draw.cutout(self.background, o["polygon"], o.get("see_through", False)))
                        for o in self.stage.occluders]
        self.figure_attachments = {f["who"]: self._attached(f.get("attached")) for f in sheet.get("figures", [])}

    def _attached(self, spec: dict | None) -> dict:
        out = {}
        for joint, what in (spec or {}).items():
            name = what["prop"] if isinstance(what, dict) else what
            if not self.props or name not in self.props:
                raise ValueError(f"{name!r} is attached to {joint} but isn't among the props")
            out[joint] = (self.props[name], float(what.get("angle", 0.0)) if isinstance(what, dict) else 0.0)
        return out

    def _light(self, spec: dict | None):
        if not spec:
            return None
        glow = spec.get("glow")
        if glow:
            at = glow.get("at", "lamp")
            at = (self.stage.light["x"], self.stage.light["y"]) if at == "lamp" else _xy(self.stage, at)
            glow = {**glow, "at": at, "radius": float(glow.get("radius", 0.3)) * self.stage.size[1]}
        return draw.light(self.stage.size, float(spec.get("level", 1.0)), tuple(spec.get("color", (1, 1, 1))), glow)

    def frame(self, i: int) -> Image.Image:
        t = i * 1000 / self.fps
        frame = self.background.copy()
        items: list[tuple[float, int, object]] = []   # (base y, kind, thing): kinds sort cutouts before what
        for base_y, piece, pos in self.cutouts:        # stands at the same height
            items.append((base_y, 0, (piece, pos)))
        for base_y, part, at, H, angle, ground in self.placed:
            items.append((base_y, 1, ("prop", part, at, H, angle, ground)))
        figures = []
        for f in self.sheet.get("figures", []):
            fig = figure_at(self.stage, self.sheet["puppets"][f["who"]], f["actions"], t,
                            attached=self.figure_attachments.get(f["who"]))
            figures.append(fig)
            if fig:
                items.append((fig.feet[1], 1, fig))
        for _, kind, thing in sorted(items, key=lambda it: (it[0], it[1])):
            if kind == 0:
                piece, pos = thing
                frame.paste(piece, pos, piece)
            elif isinstance(thing, draw.Figure):
                draw.shadow(frame, thing.feet, thing.height)
                draw.figure(frame, thing)
            else:
                _, part, at, H, angle, ground = thing
                draw.shadow(frame, ground, H * part.height * 0.6)
                draw.prop(frame, part, at, H, angle)
        frame = draw.lit(frame, self.tint)
        placed = {f["who"]: fig for f, fig in zip(self.sheet.get("figures", []), figures) if fig}

        def locate(key: str, t_ms: float):
            """Where the camera finds a person; one who hasn't come on yet is looked for where they first stand,
            so a camera can move to them as they arrive, and one who's inside something at its spot."""
            fig = placed.get(key)
            if fig is None:
                f = next((f for f in self.sheet.get("figures", []) if f["who"] == key and f["actions"]), None)
                if not f:
                    return None
                actions = sorted(f["actions"], key=lambda a: a["from_ms"])
                now = next((a for a in reversed(actions) if a["from_ms"] <= t_ms), actions[0])
                if now["do"] == rig.INSIDE:
                    return _aim(self.stage, now["at"])
                fig = figure_at(self.stage, self.sheet["puppets"][key], actions, actions[0]["from_ms"])
                if fig is None:
                    return _aim(self.stage, actions[0].get("at") or actions[0].get("start"))
            return (fig.feet[0], fig.feet[1] - LOOK_AT * fig.height)

        center, zoom = camera_at(self.stage, self.sheet.get("camera", []), t, locate)
        return draw.view(frame, center, zoom, OUT_SIZE)

    def render(self, out: Path, audio: Path | None = None, progress: Callable[[int, int], None] | None = None) -> Path:
        out = Path(out)
        out.parent.mkdir(parents=True, exist_ok=True)
        seconds = f"{self.frames / self.fps:.3f}"
        args = [ffmpeg.exe(), "-hide_banner", "-loglevel", "error", "-y",
                "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{OUT_SIZE[0]}x{OUT_SIZE[1]}", "-r", str(self.fps),
                "-i", "-"]
        if audio:
            args += ["-i", str(audio)]
        args += ["-map", "0:v:0", *(["-map", "1:a:0", *ffmpeg.AUDIO_OUT] if audio else []),
                 "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", "-r", str(self.fps),
                 "-t", seconds, "-movflags", "+faststart", str(out)]
        proc = subprocess.Popen(args, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            for i in range(self.frames):
                proc.stdin.write(self.frame(i).tobytes())
                if progress:
                    progress(i + 1, self.frames)
        finally:
            proc.stdin.close()
            err = proc.stderr.read().decode(errors="replace")
            proc.wait()
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg failed: {err.strip()[-800:]}")
        return out

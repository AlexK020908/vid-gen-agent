"""A finished short laid out for someone to go through it frame by frame: sheets of its frames, in order, each frame marked with its time.

A sheet holds what a person can actually look at closely, so a short comes to a couple of dozen of them. `every` is how many frames apart they are: 3 is ten a second, which
catches anything that lasts long enough to see, and a jump between two frames is measured for every frame, by `jumps`, which needs no one to look.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from PIL import Image, ImageDraw

from render import ffmpeg

FPS = 30
EVERY = 3                # frames apart on the sheets
ACROSS, DOWN = 10, 3     # frames on a sheet
CELL = (216, 384)        # the size of each
BAND = 16                # the strip its time's written in
JUMP_SIZE = (108, 192)   # how big frames are compared at
JUMP_AT_LEAST = 12.0     # how much of a change between two frames counts as a jump, out of 255, on average over the picture
JUMP_TIMES = 3.5         # and how many times the change just before and after it


def sheets(video: Path, folder: Path, every: int = EVERY) -> list[dict]:
    """The sheets, as {"file", "from", "to"}, oldest first. Whatever was in the folder is replaced."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    for old in [*folder.glob("f_*.png"), *folder.glob("sheet_*.png")]:
        old.unlink()
    w, h = CELL
    ffmpeg.run(["-i", video, "-vf", f"select='not(mod(n\\,{every}))',scale={w}:{h}", "-fps_mode", "passthrough", folder / "f_%05d.png"])
    frames = sorted(folder.glob("f_*.png"))
    made = []
    per = ACROSS * DOWN
    for start in range(0, len(frames), per):
        group = frames[start:start + per]
        sheet = Image.new("RGB", (w * ACROSS, (h + BAND) * DOWN), "white")
        draw = ImageDraw.Draw(sheet)
        for k, path in enumerate(group):
            x, y = (k % ACROSS) * w, (k // ACROSS) * (h + BAND)
            sheet.paste(Image.open(path).convert("RGB"), (x, y + BAND))
            draw.text((x + 3, y + 2), f"{(start + k) * every / FPS:.2f} s", fill="black")
        out = folder / f"sheet_{len(made) + 1:02d}.png"
        sheet.save(out)
        made.append({"file": str(out), "from": round(start * every / FPS, 2), "to": round((start + len(group) - 1) * every / FPS, 2)})
    for path in frames:
        path.unlink()
    return made


def jumps(video: Path, cuts: list[float], step: int = 1) -> list[float]:
    """When the picture jumps from one frame to the next with no cut planned there, which nobody should have to spot: a pop, a thing teleporting. In seconds.
    A draft holds each frame it made `step` frames long (render/film_parts.py --draft): its frames are compared `step` apart."""
    w, h = JUMP_SIZE
    raw = subprocess.run([ffmpeg.exe(), "-v", "error", "-i", str(video), "-vf", f"scale={w}:{h},format=gray", "-f", "rawvideo", "-"], capture_output=True, check=True).stdout
    size = w * h
    frames = [raw[i:i + size] for i in range(0, len(raw) - size + 1, size)][::step]
    changes = [sum(abs(a - b) for a, b in zip(one[::7], two[::7])) / (len(one[::7]) or 1) for one, two in zip(frames, frames[1:])]
    planned = {round(t * FPS / step) for t in cuts}
    found = []
    for i in range(2, len(changes) - 2):
        around = sorted(changes[max(0, i - 5):i] + changes[i + 1:i + 6])
        usual = around[len(around) // 2] if around else 0.0
        if changes[i] > max(JUMP_AT_LEAST, usual * JUMP_TIMES) and not any(abs(i + 1 - c) <= 1 for c in planned):
            found.append(round((i + 1) * step / FPS, 2))
    return found

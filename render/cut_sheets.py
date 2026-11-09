"""A finished short's cuts, laid out so someone can judge each join as a viewer meets it: the end of the shot before and
the start of the shot after, side by side, with what's being said as the cut comes.

Each cut is four frames: half a second before it, the last frame before it, the first frame after it, and half a second
after, never reaching into another shot. Two cuts go on a row, and a red line marks where each one falls. Cuts come
from the direction (`planned`), snapped to the frame where the picture really changes, or, for a video with no direction
(a reference, an old cut), are measured as the frames where the whole picture changes at once (`found`), which can also
catch a fast move, so the brief says which they are.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from render import ffmpeg

CELL = (216, 384)        # each frame on a sheet
BAND = 20                # the strip above a frame with its time
HEAD = 24                # the strip above a cut with its number
GAP = 28                 # between the two cuts on a row
PER_ROW, ROWS = 2, 3     # cuts on a row, and rows on a sheet
LEAD = 0.5               # seconds from the cut to the outer frames
SAID = 2.0               # seconds of what's said either side of a cut that go with it
SNAP = 2                 # frames a planned cut may be off from where the picture really changes
SIZE = (108, 192)        # frames are compared at this size
CUT_AT_LEAST = 12.0      # a whole-picture change, out of 255 on average, that counts as a cut
CUT_TIMES = 3.5          # and how many times the change in the frames around it
LINE = (220, 30, 30)
NO_CUTS = "(no cuts: it's one shot)"


def fps_of(video: Path) -> float:
    found = re.search(r"(\d+(?:\.\d+)?) fps", ffmpeg.probe(video))
    return float(found.group(1)) if found else 30.0


def planned(direction: dict) -> list[float]:
    """Where a direction's shots start, after the first, in seconds: each is a cut."""
    starts = {round(float(s["t"]), 3) for scene in direction.get("scenes") or [] for s in scene.get("shots") or []}
    return sorted(t for t in starts if t > 0)


def changes(video: Path) -> list[float]:
    """How much the whole picture changes from each frame to the next, out of 255 on average: change i is from frame i
    to frame i + 1. In colour, since a cut from red to green is the same grey."""
    w, h = SIZE
    raw = subprocess.run([ffmpeg.exe(), "-v", "error", "-i", str(video), "-vf", f"scale={w}:{h}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         capture_output=True, check=True).stdout
    size = w * h * 3
    frames = [raw[i:i + size] for i in range(0, len(raw) - size + 1, size)]
    return [sum(abs(a - b) for a, b in zip(one[::7], two[::7])) / (len(one[::7]) or 1) for one, two in zip(frames, frames[1:])]


def _spikes(moved: list[float]) -> list[int]:
    """The frames that begin a new picture: where the change into them is big, and many times what's usual around it."""
    out = []
    for i in range(1, len(moved) - 1):
        around = sorted(moved[max(0, i - 5):i] + moved[i + 1:i + 6])
        usual = around[len(around) // 2] if around else 0.0
        if moved[i] > max(CUT_AT_LEAST, usual * CUT_TIMES) and moved[i] >= max(moved[i - 1], moved[i + 1]):
            out.append(i + 1)
    return out


def found(video: Path, moved: list[float] | None = None) -> list[float]:
    """Cuts measured from the picture, in seconds, for a video with no direction. A fast move can look like one."""
    fps = fps_of(video)
    return [round(f / fps, 3) for f in _spikes(moved if moved is not None else changes(video))]


def _snapped(cuts: list[float], fps: float, moved: list[float]) -> list[int]:
    """Each planned cut as the frame the new shot starts on: the planned frame, or within SNAP of it where the picture
    really changes most, since a shot's first frame can land one either side of its start time."""
    out = []
    for t in cuts:
        at = round(t * fps)
        near = [(moved[i - 1], i) for i in range(at - SNAP, at + SNAP + 1) if 1 <= i <= len(moved)]
        best = max(near) if near else (0.0, at)
        out.append(best[1] if best[0] >= CUT_AT_LEAST else at)
    return sorted(set(out))


def lines_from(path: Path) -> list[dict]:
    """What's said, line by line, as [{from, to, text, words: [{word, t}]}]: from a short's clock (stages/direct.py
    `timeline`) or local Whisper's segments (start, end, text, words of w and s)."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = data["lines"] if isinstance(data, dict) else data
    out = []
    for r in rows:
        if "from" in r:
            line = {"from": float(r["from"]), "to": float(r["to"]), "text": r["text"],
                    "words": [{"word": w["word"], "t": float(w["t"])} for w in r.get("words") or []]}
        else:
            line = {"from": float(r["start"]), "to": float(r["end"]), "text": r["text"],
                    "words": [{"word": w["w"], "t": float(w["s"])} for w in r.get("words") or []]}
        if r.get("shows"):
            line["shows"] = r["shows"]
        out.append(line)
    return out


def said_around(t: float, lines: list[dict]) -> str:
    """The words from SAID before a cut to SAID after it, with [cut] where it falls."""
    words = [w for line in lines for w in (line["words"] or [{"word": line["text"], "t": line["from"]}])]
    near = [w for w in words if t - SAID <= w["t"] <= t + SAID]
    if not near:
        return "(nothing's said)"
    parts = [" ".join(w["word"] for w in near if w["t"] < t), "[cut]", " ".join(w["word"] for w in near if w["t"] >= t)]
    inside = any(line["from"] < t < line["to"] for line in lines)
    return f"\"{' '.join(p for p in parts if p)}\"" + ("" if inside else " (between two lines)")


def _font(size: int):
    try:
        return ImageFont.truetype("arial.ttf", size)
    except OSError:
        try:
            return ImageFont.load_default(size=size)
        except TypeError:
            return ImageFont.load_default()


def _frames(video: Path, wanted: list[int], folder: Path) -> dict[int, Path]:
    """The frames `wanted`, by their number in the video, saved CELL size. The video's read once, a frame at a time,
    keeping only those (a select filter naming a hundred frames is more than ffmpeg will parse)."""
    w, h = CELL
    left = set(wanted)
    size = w * h * 3
    got = {}
    proc = subprocess.Popen([ffmpeg.exe(), "-v", "error", "-i", str(video), "-vf", f"scale={w}:{h}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)   # it's stopped once it has them all
    try:
        n = 0
        while left:
            raw = proc.stdout.read(size)
            if len(raw) < size:
                break
            if n in left:
                path = folder / f"c_{n:05d}.png"
                Image.frombytes("RGB", (w, h), raw).save(path)
                got[n] = path
                left.discard(n)
            n += 1
    finally:
        proc.stdout.close()
        proc.kill()
        proc.wait()
    return got


def sheets(video: Path, cuts: list[float] | None, folder: Path, lines: list[dict]) -> dict:
    """The cuts laid out: {"sheets": [{"file", "cuts": [n, ...]}], "cuts": [{"n", "t", "sheet", "row", "side", "said"}],
    "measured": true when `cuts` was None and they were measured from the picture}. Whatever was in the folder is replaced."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    for old in [*folder.glob("c_*.png"), *folder.glob("cuts_*.png")]:
        old.unlink()
    fps = fps_of(video)
    moved = changes(video)
    total = len(moved) + 1
    measured = cuts is None
    starts = _spikes(moved) if measured else _snapped(cuts, fps, moved)
    starts = [f for f in starts if 1 <= f < total]
    lead = round(LEAD * fps)
    picks = []
    for k, f in enumerate(starts):
        before = starts[k - 1] if k else 0
        after = starts[k + 1] if k + 1 < len(starts) else total
        picks.append([max(before, f - lead), f - 1, f, min(after - 1, f + lead)])
    got = _frames(video, [n for p in picks for n in p], folder) if picks else {}
    w, h = CELL
    width = PER_ROW * 4 * w + (PER_ROW - 1) * GAP
    tall = HEAD + BAND + h
    per = PER_ROW * ROWS
    big, small = _font(18), _font(14)
    made, listed = [], []
    for start in range(0, len(starts), per):
        group = list(range(start, min(start + per, len(starts))))
        rows = (len(group) + PER_ROW - 1) // PER_ROW
        sheet = Image.new("RGB", (width, rows * tall), "white")
        draw = ImageDraw.Draw(sheet)
        number = len(made) + 1
        for slot, k in enumerate(group):
            row, side = slot // PER_ROW, slot % PER_ROW
            x0, y0 = side * (4 * w + GAP), row * tall
            t = round(starts[k] / fps, 2)
            draw.text((x0 + 4, y0 + 3), f"cut {k + 1} at {t:.2f} s", fill="black", font=big)
            for j, n in enumerate(picks[k]):
                x = x0 + j * w
                draw.text((x + 4, y0 + HEAD + 2), f"{n / fps:.2f} s" + ("  last" if j == 1 else "  first" if j == 2 else ""), fill="black", font=small)
                if n in got:
                    sheet.paste(Image.open(got[n]).convert("RGB"), (x, y0 + HEAD + BAND))
            draw.rectangle((x0 + 2 * w - 2, y0 + HEAD, x0 + 2 * w + 1, y0 + tall - 1), fill=LINE)
            listed.append({"n": k + 1, "t": t, "sheet": number, "row": row + 1, "side": "left" if side == 0 else "right",
                           "said": said_around(starts[k] / fps, lines)})
        out = folder / f"cuts_{number:02d}.png"
        sheet.save(out)
        made.append({"file": str(out), "cuts": [k + 1 for k in group]})
    for path in folder.glob("c_*.png"):
        path.unlink()
    return {"sheets": made, "cuts": listed, "measured": measured}


def listing(laid: dict) -> str:
    """Each cut, where it is on the sheets, and what's said as it comes."""
    rows = []
    for c in laid["cuts"]:
        place = f"sheet {c['sheet']}, row {c['row']}, {c['side']}"
        rows.append(f"- Cut {c['n']} at {c['t']} s ({place}): {c['said']}")
    return "\n".join(rows) or NO_CUTS


def script_text(lines: list[dict]) -> str:
    """What's said, line by line, with when."""
    return "\n".join(f"{n}. {line['from']:.2f} s to {line['to']:.2f} s: {line['text']}" + (f"\n   Shows: {line['shows']}" if line.get("shows") else "")
                     for n, line in enumerate(lines, 1))

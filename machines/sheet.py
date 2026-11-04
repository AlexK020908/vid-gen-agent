"""A machine's turnaround as one picture to look at: a row per step, a column per view, each labelled."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw


def make(result: dict, folder: Path, cell=(270, 480)) -> Path:
    folder = Path(folder)
    shots = result.get("shots") or []
    steps = sorted({s["step"] for s in shots})
    views = []
    for s in shots:
        if s["view"] not in views:
            views.append(s["view"])
    w, h = cell
    head = 34
    sheet = Image.new("RGB", (w * len(views), (h + head) * len(steps)), (24, 24, 26))
    draw = ImageDraw.Draw(sheet)
    names = result.get("steps") or []
    for row, step in enumerate(steps):
        y = row * (h + head)
        title = f"step {step}: {names[step - 1]}" if step - 1 < len(names) else f"step {step}"
        draw.text((8, y + 9), title, fill=(240, 240, 240))
        for s in shots:
            if s["step"] != step:
                continue
            col = views.index(s["view"])
            pic = Image.open(folder / s["file"]).convert("RGB").resize((w, h))
            sheet.paste(pic, (col * w, y + head))
            draw.text((col * w + 6, y + head + 6), s["view"], fill=(255, 230, 120))
    out = folder / "sheet.png"
    sheet.save(out)
    return out

"""Stills and thumbnails: the stub, the contact-sheet previews, and the text drawn on thumbnails.

The real pictures come from providers/fal.py (FalImages)."""
from __future__ import annotations

import functools
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

PREVIEW_SIZE = (480, 270)
CAPTION_FILL, CAPTION_EDGE = (255, 214, 0), (0, 0, 0)  # yellow with a black outline reads on light and dark


@functools.cache
def _font(size: int) -> ImageFont.FreeTypeFont:
    for name in ("arialbd.ttf", "arial.ttf", "DejaVuSans-Bold.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


@functools.cache
def _caption_font(size: int) -> ImageFont.FreeTypeFont:
    for name in ("impact.ttf", "Impact.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, width: int) -> list[str]:
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if draw.textlength(trial, font=font) <= width:
            line = trial
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def _character(path: Path, height: int) -> Image.Image | None:
    try:
        img = Image.open(path).convert("RGBA")
    except OSError:
        return None
    return img.resize((round(img.width * height / img.height), height))


def caption(path: Path, text: str) -> None:
    """Writes a thumbnail's words in its upper left: capitals, as big as fit in two lines across 60% of
    the width. Drawn in code, not by the picture model, so they're always spelled right."""
    with Image.open(path) as img:
        img = img.convert("RGB")
    draw = ImageDraw.Draw(img)
    w, h = img.size
    margin, max_w, max_h = round(w * 0.04), round(w * 0.6), round(h * 0.42)
    words = text.upper().split()
    layouts = [[" ".join(words)]] + [[" ".join(words[:k]), " ".join(words[k:])] for k in range(1, len(words))]
    for size in range(round(h * 0.2), round(h * 0.07), -4):  # biggest first
        font, stroke = _caption_font(size), max(3, size // 9)

        def widest(lines: list[str]) -> int:
            return max(draw.textlength(line, font=font) + 2 * stroke for line in lines)

        # one line if it fits, else the most even split into two
        lines = min(layouts, key=lambda ls: (widest(ls) > max_w, len(ls), widest(ls)))
        boxes = [draw.textbbox((0, 0), line, font=font, stroke_width=stroke) for line in lines]
        tall = sum(b[3] - b[1] for b in boxes) + size // 8 * (len(lines) - 1)
        if tall <= max_h and widest(lines) <= max_w:
            break
    y = margin
    for line, (left, top, _, bottom) in zip(lines, boxes):
        draw.text((margin - left, y - top), line, font=font, fill=CAPTION_FILL, stroke_width=stroke,
                  stroke_fill=CAPTION_EDGE)
        y += bottom - top + size // 8
    img.save(path)


def preview_path(still: Path) -> Path:
    return still.with_name(still.stem + ".thumb.jpg")


def make_preview(still: Path) -> Path:
    """Small JPEG for the contact sheet, so the render card doesn't load 120 full-size stills."""
    out = preview_path(still)
    with Image.open(still) as img:
        img.convert("RGB").resize(PREVIEW_SIZE).save(out, quality=80)
    return out


class StubImages:
    """Gray placeholder frames that show the scene label and prompt, with the channel's character pasted in.
    Places and cast members are placeholders too, and a still names the ones it was given."""

    still_price = 0.044  # the fal 1K list price, for simulated costs
    thumb_price = 0.044

    def still(self, channel, prompt: str, label: str, out: Path, place: tuple | None = None,
              people: list | tuple = (), hero: tuple | None = ("", None), previous: Path | None = None,
              fix: str = "") -> float:
        img = Image.new("RGB", (1920, 1080), (236, 236, 232))
        draw = ImageDraw.Draw(img)
        figure = _character(channel.character_ref, 640)
        if figure:
            img.paste(figure, (180, 300), figure)
        draw.text((120, 90), label, font=_font(84), fill=(20, 20, 20))
        y = 330
        for line in _wrap(draw, prompt, _font(40), 860)[:9]:
            draw.text((920, y), line, font=_font(40), fill=(60, 60, 60))
            y += 56
        with_whom = ", ".join(name for name, _, _ in people)
        where = " · ".join(part for part in (place and f"in {place[0]}" + ("" if place[2] else " (in words)"),
                                             with_whom and f"with {with_whom}",
                                             previous and f"after {previous.stem}", fix and f"fixing: {fix}") if part)
        draw.text((120, 990), f"PLACEHOLDER STILL {where}"[:120].strip(), font=_font(30), fill=(160, 160, 160))
        out.parent.mkdir(parents=True, exist_ok=True)
        img.save(out)
        return self.still_price

    def place(self, channel, name: str, look: str, out: Path) -> float:
        return self._card(f"PLACE: {name}", look, out, (1920, 1080))

    def sheet(self, channel, reference: Path, items: str, out: Path, file: str = "parts.md") -> float:
        """A parts sheet on flat green (puppet/parts.py cuts it): one simple blob per numbered item, left to
        right, biggest first so the cut finds them in the order asked."""
        img = Image.new("RGB", (1920, 1080), (0, 255, 0))
        draw = ImageDraw.Draw(img)
        count = max(1, len([ln for ln in items.splitlines() if ln.strip()]))
        colors = [(250, 250, 250), (200, 50, 50), (30, 30, 30), (140, 100, 60), (150, 150, 155)]
        step = 1920 // (count + 1)
        for i in range(count):
            size = max(60, min(240, step - 60) - i * 12)   # apart from each other, however many there are
            x, y = step * (i + 1), 540
            draw.ellipse((x - size // 2, y - size // 2, x + size // 2, y + size // 2),
                         fill=colors[i % len(colors)], outline=(20, 20, 20), width=6)
        out.parent.mkdir(parents=True, exist_ok=True)
        img.save(out)
        return self.still_price

    def change_place(self, channel, base: Path, change: str, out: Path, fix: str = "") -> float:
        with Image.open(base) as img:
            img = img.convert("RGB")
        ImageDraw.Draw(img).text((120, 900), f"CHANGED: {change}"[:90], font=_font(36), fill=(150, 40, 40))
        if fix:
            ImageDraw.Draw(img).text((120, 950), f"FIXING: {fix}"[:90], font=_font(36), fill=(150, 40, 40))
        out.parent.mkdir(parents=True, exist_ok=True)
        img.save(out)
        return self.still_price

    def person(self, channel, name: str, look: str, out: Path) -> float:
        return self._card(f"CAST: {name}", look, out, (1024, 1536))

    def change_look(self, channel, base: Path, now: str, out: Path, fix: str = "") -> float:
        return self._card("NOW WITH", now + (f" (fixing: {fix})" if fix else ""), out, (1024, 1536))

    def _card(self, title: str, text: str, out: Path, size: tuple[int, int]) -> float:
        img = Image.new("RGB", size, (222, 228, 236))
        draw = ImageDraw.Draw(img)
        draw.text((80, 80), title, font=_font(60), fill=(20, 20, 20))
        y = 200
        for line in _wrap(draw, text, _font(36), size[0] - 160)[:12]:
            draw.text((80, y), line, font=_font(36), fill=(60, 60, 60))
            y += 50
        out.parent.mkdir(parents=True, exist_ok=True)
        img.save(out)
        return self.still_price

    def thumbnail(self, channel, title: str, variant: int, out: Path) -> float:
        palette = [(214, 40, 57), (29, 53, 87), (233, 150, 58)]
        img = Image.new("RGB", (1280, 720), palette[variant % len(palette)])
        draw = ImageDraw.Draw(img)
        figure = _character(channel.character_ref, 520)
        if figure:
            img.paste(figure, (820, 160), figure)
        y = 520  # the upper left is left for the caption, as the real prompt asks
        for line in _wrap(draw, title, _font(34), 700)[:3]:
            draw.text((70, y), line, font=_font(34), fill=(255, 255, 255))
            y += 44
        out.parent.mkdir(parents=True, exist_ok=True)
        img.save(out)
        return self.thumb_price

"""Draws one frame: the place, the props standing in it, each figure (its stick strokes, painted parts and
whatever it holds) over a ground shadow, the foreground cutouts people stand behind, the scene's light, then
the camera's view of it all. Figures are drawn at twice the size and scaled down so the sticks' edges come
out smooth.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

from PIL import Image, ImageChops, ImageDraw, ImageFilter

from puppet import rig
from puppet.parts import Part, Puppet

INK = (22, 22, 26, 255)
SS = 2                          # supersampling
SHADOW_ALPHA = 85
MARGIN = 0.6                    # around the joints, in H, so no painted part or held prop is cut off


@dataclass
class Figure:
    puppet: Puppet
    pose: rig.Pose
    feet: tuple[float, float]   # where the figure stands: the lowest point of its legs sits here
    height: float               # H, in stage pixels (the puppet's scale already applied)
    facing: int = 1
    wobble: float = 0.0         # hand-drawn jitter of the joints, in H
    seed: int = 0               # the jitter changes when the seed does (every few frames, not every frame)
    attached: dict = field(default_factory=dict)  # joint -> (Part, angle): a drill in r_hand, a towel on r_knee
    at_camera: bool = False     # looking at the viewer: the front head even while the body faces a side


def _rotated(part: Part, size_h: float, facing: int, rot: float) -> tuple[Image.Image, tuple[float, float]]:
    """The part scaled to `size_h` pixels tall, mirrored when the figure faces the other way from the way the
    part was painted, and rotated (PIL degrees, counter-clockwise on screen); and where its pivot is in the
    result."""
    img = part.image
    scale = size_h / img.height
    w, h = max(1, round(img.width * scale)), max(1, round(size_h))
    img = img.resize((w, h), Image.Resampling.LANCZOS)
    px, py = part.pivot[0] * scale, part.pivot[1] * scale
    if (facing < 0) != (part.faces == "left"):
        img = img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        px = w - px
    if abs(rot) > 0.01:
        th = math.radians(rot)
        dx, dy = px - w / 2, py - h / 2
        img = img.rotate(rot, resample=Image.Resampling.BICUBIC, expand=True)
        px = img.width / 2 + dx * math.cos(th) + dy * math.sin(th)
        py = img.height / 2 - dx * math.sin(th) + dy * math.cos(th)
    return img, (px, py)


def _jitter(j: dict, amount: float, seed: int) -> dict:
    if amount <= 0:
        return j
    rng = random.Random(seed)
    out = {}
    for k, v in j.items():
        out[k] = (v[0] + rng.uniform(-amount, amount), v[1] + rng.uniform(-amount, amount)) if k != "rot" else v
    return out


def figure(frame: Image.Image, fig: Figure) -> None:
    """Draws the figure onto the frame (RGB, stage size)."""
    H, facing, pose, puppet = fig.height, fig.facing, fig.pose, fig.puppet
    root = (fig.feet[0], fig.feet[1] - rig.ground(pose, H))
    j = _jitter(rig.joints(pose, H, root, facing), fig.wobble * H, fig.seed)
    pts = [v for k, v in j.items() if k != "rot"]
    m = MARGIN * H
    x0, y0 = math.floor(min(p[0] for p in pts) - m), math.floor(min(p[1] for p in pts) - m)
    x1, y1 = math.ceil(max(p[0] for p in pts) + m), math.ceil(max(p[1] for p in pts) + m)
    layer = Image.new("RGBA", ((x1 - x0) * SS, (y1 - y0) * SS), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    width = max(2, round(rig.STROKE * H * SS))
    rot = j["rot"]

    def L(p):
        return ((p[0] - x0) * SS, (p[1] - y0) * SS)

    def stroke(*names):
        points = [L(j[n]) for n in names]
        draw.line(points, fill=INK, width=width, joint="curve")
        r = width / 2
        for x, y in (points[0], points[-1]):
            draw.ellipse((x - r, y - r, x + r, y + r), fill=INK)

    def put(part: Part, at, angle):
        img, (px, py) = _rotated(part, part.height * H * SS, facing, angle)
        ax, ay = L(at)
        layer.alpha_composite(img, (round(ax - px), round(ay - py)))

    def slot(name, at, angle):
        part = puppet.in_slot(name)
        if part:
            put(part, at, angle)

    def held(joint):
        if joint in fig.attached:
            part, angle = fig.attached[joint]
            put(part, j[joint], angle * facing)

    near, far = ("r", "l") if facing > 0 else ("l", "r")

    def arm(side):
        stroke("shoulder", f"{side}_elbow", f"{side}_hand")
        slot("hand", j[f"{side}_hand"], rot[f"{side}_hand"])
        held(f"{side}_hand")

    def leg(side):
        stroke("hip", f"{side}_knee", f"{side}_foot")
        slot(f"{side}_knee", j[f"{side}_knee"], rot[f"{side}_knee"])
        held(f"{side}_knee")

    def cane():
        if "cane_top" in j and "r_hand" not in fig.attached:   # a tool in that hand means the cane is set down
            slot("cane", j["cane_top"], rot["cane"])

    if far == "r":
        cane()
    arm(far)
    leg(far)
    stroke("hip", "neck")
    slot("neck", (j["neck"][0], j["neck"][1] + 0.02 * H), rot["neck"])
    head = puppet.in_slot("head_side") if not fig.at_camera else None   # the side head when there is one
    if head:
        put(head, j["neck"], rot["head"])
    else:
        slot("head", j["neck"], rot["head"])
    leg(near)
    if near == "r":
        cane()
    arm(near)
    small = layer.resize((x1 - x0, y1 - y0), Image.Resampling.LANCZOS)
    frame.paste(small, (x0, y0), small)


def prop(frame: Image.Image, part: Part, at: tuple[float, float], H: float, angle: float = 0.0,
         facing: int = 1) -> None:
    """A prop standing in the place: its pivot at `at`, `part.height` times H tall, turned by `angle`."""
    img, (px, py) = _rotated(part, part.height * H, facing, angle)
    frame.paste(img, (round(at[0] - px), round(at[1] - py)), img)


def shadow(frame: Image.Image, at: tuple[float, float], H: float) -> None:
    """A soft dark ellipse on the floor under something standing at `at`."""
    w, h = 0.5 * H, 0.09 * H
    x, y = at
    pad = 0.06 * H
    layer = Image.new("RGBA", (math.ceil(w + 2 * pad), math.ceil(h + 2 * pad)), (0, 0, 0, 0))
    ImageDraw.Draw(layer).ellipse((pad, pad, pad + w, pad + h), fill=(0, 0, 0, SHADOW_ALPHA))
    layer = layer.filter(ImageFilter.GaussianBlur(0.03 * H))
    frame.paste(layer, (round(x - w / 2 - pad), round(y - h / 2 - pad)), layer)


def cutout(background: Image.Image, polygon: list[tuple[float, float]]) -> tuple[Image.Image, tuple[int, int]]:
    """A piece of the painted place cut along `polygon`, to draw over whatever stands behind it."""
    xs, ys = [p[0] for p in polygon], [p[1] for p in polygon]
    x0, y0 = max(0, math.floor(min(xs))), max(0, math.floor(min(ys)))
    x1, y1 = min(background.width, math.ceil(max(xs))), min(background.height, math.ceil(max(ys)))
    piece = background.crop((x0, y0, x1, y1)).convert("RGBA")
    mask = Image.new("L", piece.size, 0)
    ImageDraw.Draw(mask).polygon([(x - x0, y - y0) for x, y in polygon], fill=255)
    piece.putalpha(mask)
    return piece, (x0, y0)


def light(size: tuple[int, int], level: float = 1.0, color=(1.0, 1.0, 1.0), glow: dict | None = None):
    """A layer the frame is multiplied by: `level` (0 to 1) and `color` darken and tint the whole picture; `glow`
    ({"at": (x, y), "radius": px, "color": (r, g, b), "strength": 0 to 1}) keeps a lamp's surroundings bright
    and warm. None when the picture is left as painted."""
    if level >= 0.999 and all(c >= 0.999 for c in color) and not glow:
        return None
    base = tuple(min(255, round(255 * level * c)) for c in color)
    tint = Image.new("RGB", size, base)
    if glow:
        r = max(1, round(glow["radius"]))
        strength = float(glow.get("strength", 1.0))
        # PIL's gradient reaches 255 at the corners (distance 128 * sqrt 2), so v * 1.4142 / 255 is the distance over
        # the radius; the glow fades to nothing at the radius with a soft curve
        grad = Image.radial_gradient("L").resize((2 * r, 2 * r), Image.Resampling.BILINEAR)
        mask = grad.point(lambda v: round(255 * strength * max(0.0, 1 - v * 1.41421 / 255) ** 1.5))
        patch = Image.new("RGB", (2 * r, 2 * r), tuple(int(c) for c in glow["color"]))
        ax, ay = glow["at"]
        tint.paste(patch, (round(ax - r), round(ay - r)), mask)
    return tint


def lit(frame: Image.Image, tint) -> Image.Image:
    return ImageChops.multiply(frame, tint) if tint is not None else frame


def view(frame: Image.Image, center: tuple[float, float], zoom: float, size: tuple[int, int]) -> Image.Image:
    """What the camera sees: a window 1/zoom of the frame around `center`, kept inside it, at `size`."""
    W, H = frame.size
    zoom = max(1.0, zoom)
    w, h = W / zoom, H / zoom
    cx = min(max(center[0], w / 2), W - w / 2)
    cy = min(max(center[1], h / 2), H - h / 2)
    return frame.resize(size, Image.Resampling.BICUBIC, box=(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2))

"""The scene language: what the agent writes to direct a short, checked in code before Blender starts (CHARACTERS.md).

The style it's built for holds strong poses and does the rest with cuts every second or so, wide lenses close up, a
slow-motion hit and glows. People barely act; things are placed and struck. Code works out the contacts and physics, so a
scene says what happens, not where every hand goes. Times are seconds from the scene's start. Meters and degrees.

Everything is held to physical truth by code. When a scene's staged, its meshes are measured against each other frame by frame:
anything that passes through something, hangs in the air unsaid, or stands in front of the lens gets the scene refused, in words,
before a frame is rendered. So don't work out heights by hand: say what a thing is `on`.

A scene:
  length    seconds
  set       one of SETS. sky_counter is a matte wooden counter, its top at z 0, level across the picture before a clean blue
            backdrop, lit for showing things up close: use it for anything on a surface. sky_set is the plain blue with a floor,
            for people. place is a real place, in "place": {"sky": a Poly Haven sky's id (a forest, a street, a kitchen), "ground": a Poly Haven texture's id, or left out
            for what's indoors, "tile": meters a repeat of it, "turn": degrees it's swung round, "bright": how strongly it lights things, 1 by default, "light": how strong
            the lights added on who's in it are, 0.35 by default, as a place mostly lights itself}. sky_counter can
            have a "place" too, of "sky", "turn" and "bright" only: a real room behind the counter, in place of the plain blue
  cast      id -> who or what's in it:
    {"type": "person", "character": an id in characters/specs, "at": [x, y], "facing": degrees (0 faces -y, toward the
     default camera) or another cast id, "stance": a body clip they hold, "life": how fast it plays, 0.22 by default}
    {"type": "prop", "prop": one of PROPS, "at": [x, y, z], "points": [x, y, z], "up": [x, y, z]}
    {"type": "prop", "prop": a thing in things/specs (a bird, a bench, an apple),
     "on": another cast id, or "set" for the counter or floor: it comes down until the two touch, and rests there. With "on",
           `at` is just [x, y], or left out to center it: its "by" spot (or its middle) over the other's "onto" spot (or its middle). "sinks": meters it goes down into what's under it, if
           that's soft: say they're touching. Without it, a thing with something sticking out of its underside balances on that,
     "to": "id:spot": it's fixed to another thing at a point, from any side, its "by" spot (or its middle) meeting that spot exactly:
           a shaft into a motor, blades on a hub, a lid on a hinge. It stays where it's put, and the two may overlap. If what it's fixed to moves (slides, rocks, spins), it goes with it,
           and its own spin or rock is then counted from there: a drum turning in a tub that hops,
     "against": another cast id: it comes up to it from the side until they touch, however crooked that is: a bird to a tree, a nail to a wall. "at" [x, y] is where
           it starts from, far enough off to be outside it, "height" how high, "way" [x, y] the way it goes, its facing by default. "by": [a spot], the one that touches, or [two spots],
           and it tips until both do, a bird's feet and beak. "into": meters it goes further in, as a nail. "tip": degrees its top leans away from what it's against. "bends": [{"spot": a spot, "about": the spot it bends at, "near": the spot in the middle
           of what bends, "radius": meters, "yaw": degrees it's turned about its own z first, for a head that's looking off to one side}]: that part bends until its spot touches too, a bird's neck bringing its beak to the bark, or its tail braced there. A `rock` with the same about and part goes on from that. It stays where it's put, and the two may overlap,
     "inside": another cast id: it goes inside that thing, a brain in a head, and all of it stays inside, measured, or the scene's refused. "near": a spot on that thing: it goes in
           the roomiest place near there, or exactly there with "stay": true. It's sized to fit, leaving out "size": "room" is how much of the room it fills, 0.85 by default. "points" and "up" are in the axes of what it's in.
           It goes wherever that goes, so nothing moves it but what moves that. Inside a person, it's inside their head, and rides on it. "by": which of its own spots goes on that place, rather than its middle,
     "at": [x, y, z] where its underside sits, for what isn't on anything, "floats": true if it's meant to hang in the air,
           a marker such as an arrow or a bulb over a head,
     "facing": degrees or a cast id, as for a person, or "points" and "up" [x, y, z] to aim its own z and y,
     "size": times its real size, 1 by default, "smooth": how many times its surface is smoothed, 40 taking the folds out of a brain,
     "level": for a thing with a liquid in it (things/spec.py), how full it starts: meters above the bottom of its liquid, or with "above": a cast
           id, meters above the top of that thing's liquid, which is how a straw dipped in a drink starts (0: level with it) and how mercury stands
           in a tube over a dish. Left out, it's full. Its top is always flat and level. "part": which liquid, if it has more than one}
  touching  optional, [[id, id], ...]: what's meant to overlap, such as a shaft inside the motor that turns it
  anchors   optional, [aim, ...]: where these are on screen is tracked frame by frame, for a label drawn on them. A short's
            film step writes it from the direction's label marks
  happens   what happens, each with "do" and "t" unless it's for the whole scene:
    wear       who, prop, size                                    for the whole scene; a hat. The head and the inside of the hat
                                                                  are measured, it's fitted and seated, it rides on the head, and
                                                                  the hair under it is gone. `size` only to overrule the fit
    spin       prop, to, rate, axis, about, ease, start           turning on the spot from t until `to`, `rate` turns a second (minus
                                                                  for the other way), about its own axis x, y or z through a spot
                                                                  (or its middle), reaching speed over `ease` seconds, from `start`
                                                                  degrees. Choose the axis so the lens sees it turn: a thing
                                                                  turning in a plane edge-on to the lens is a line sliding about
    slide      prop, over, from or by or until, way, ease         straight along a line, level, keeping its turn. `from` [x, y, z] is
                                                                  how far off its resting place it starts (there until t), so it's
                                                                  set down exactly; `by` is how far it goes from where it is; `until`
                                                                  a cast id, with `way` [x, y, z]: it goes until it touches that, measured.
                                                                  ease is in (speeding up), out (slowing), inout, the default, or linear
                                                                  (steady). Things keep going until something stops them: what's coasting
                                                                  or thrown is linear, and only what something's pushing speeds up
    lit        on ("id" or "id:spot"), color (one of COLORS), to, radius, soft, strength, only, fade, cover, rim
                                                                  the thing's own surface lights up from t until `to`, and can't
                                                                  leave its edges. A flash on the word that names it: whole, about
                                                                  0.5 s. Heat: a spot with a `radius` in meters, on the inside of a
                                                                  pan. `only`: part ids of a built thing. strength about 1; much
                                                                  above that it washes to white. Whole, its edges burn brightest with a
                                                                  soft halo and its middle keeps some of its own color: `rim` (0 to 1,
                                                                  0.45 by default) sets how much, and `cover` how far it covers, so
                                                                  metal stays metal at about 0.5. A patch fades over the `soft` share
                                                                  of its radius: 0.12 for a crisp edge right at the floor of a pan
    flow       on ("id" or "id:spot"), color, to, radii, along, side, arcs, arc, turn, pulses, speed, width, steady, peak,
               beads, bead_color, reverse
                                                                  thin light running on a thing: white-hot lines with their color in
                                                                  the halo, the way current or a signal is shown. radii: circles around
                                                                  the spot in meters, laid on the surface facing `side` (top or under),
                                                                  and stopping at its edge. arcs and arc (degrees): only that much of
                                                                  each circle, spaced round it, for streaks. along: a part of a built
                                                                  thing that has a line (a pipe or spiral) instead. pulses and speed:
                                                                  brighter stretches running along it, per line and per second. beads:
                                                                  how many beads run along it, thicker and softer. reverse: seconds
                                                                  between turning back. width in meters, 0.0012 by default. lift:
                                                                  meters above its part's line, to draw a coil's line on the glass over it
    tint       prop, color (a name or [r, g, b]), to, amount, mix its own color darkening toward this from t until `to`: a steak browning. mix: true: it
                                                                  becomes that color instead, lighter or darker: mud scrubbed out of a shirt
    ghost      prop or who, to, color, edge, strength, fade, near, radius
                                                                  it goes to glass from t until `to`: you see through where it faces you and
                                                                  its edges stay as a thin bright line, so what's inside shows, as in an
                                                                  x-ray. Put what's inside it in `touching` with it. For how anything works
                                                                  inside: a skull with a brain in it, a box, a pipe. edge: more is finer.
                                                                  near: a spot, and radius: meters, and only that much of it does: a window
                                                                  into a bird's head, with the bird still plainly a bird. On something living or
                                                                  complicated, do this, and shoot it against something dark. who: someone's head, with radius 0.17 by
                                                                  default: their skin goes to glass there, and their hair, eyes and teeth go, leaving what's inside their head. fill: how much of
                                                                  what it was stays, 0 to 1, faintly, so it's still a solid thing and not just lines
    act        who, clip, speed, over, stays, skip                their whole body does one of the moves from t, and goes back to their stance after, skipping the first `skip` seconds of it to get straight to what matters:
                                                                  a flinch, a nod, reeling from a hit, picking something up. stays: true leaves them
                                                                  as it ended, until their next move: flat on the ground after a fall
    walk       who, to [x, y], over, clip                         they go there in `over` seconds, doing that move (walking or running), at a steady
                                                                  speed. The move's steps are paced to it so their feet don't slide, and it's refused
                                                                  if that's too far from the move's own pace. Point their `facing` the way they go. A
                                                                  shot on them needs `follow`. hits: a cast id they run into: `to` is only roughly
                                                                  where it is, as code stops them exactly where their body meets it, at the end of
                                                                  `over`, and they bounce back. with: what they lead with (one of AIMS, "forehead"),
                                                                  which code gets there first by choosing the step they arrive on. slow: [seconds, share]:
                                                                  the end of it in slow motion, at that share of the speed, [0.45, 0.2], to see a hit land. ramp: seconds that slowing down takes, smoothly, rather than all at once. covers: meters they start short of where they
                                                                  stop, for what's so slow that a rough start would have them flying: their at then only says which way they come from
    squash     prop, amount, axis, about, over, spreads           pressed flat along one of its own axes (x, y or z) from t and springing back, wider
                                                                  the way it isn't pressed: a hit you can feel. amount 0.1 to 0.3. about: a spot that
                                                                  stays where it is, such as the place it hit. over: seconds it takes to ring out.
                                                                  spreads: false for what doesn't get wider, a coil spring
    press      prop, amount, way, in, over, stays, soft, near, radius
                                                                  the front of something soft stopping against what it's hit while the rest keeps coming: it flattens at the front,
                                                                  spreads there, and its back comes on, where a squash presses it evenly. way [x, y, z]: the way it was going. amount:
                                                                  the share of its length it shortens by, 0.1 to 0.35. in: seconds that takes, 0.12 by default. over: seconds it rings out.
                                                                  stays: how much of it stays pressed, 0.4 by default. soft: how far back from the front it's squeezed, 0.35 of its length.
                                                                  near: a spot, and radius: meters: only that part of it, a soft head crumpling on a bird that isn't otherwise soft. If it's inside something, it takes the shape of the wall
    turns      prop, near, radius, into, fade, to                 part of something turning into other stuff, to show what that would be like: a bird's head going to sponge. near: a spot, and radius:
                                                                  meters. into: {"color": [r, g, b], "rough": 0 to 1, "pores": how wide its holes are, in meters}. Use the same stuff as the thing you're
                                                                  about to compare it with, so the viewer sees they're the same thing
    pit        on, at, radius, over, from_radius                  a dark hollow on a surface where it's being hit, around an aim, growing to `radius` meters over `over` seconds: chips have to come from somewhere
    dim        level, over                                        the place around everything goes dark, to this share of its light, over `over` seconds, 0.3 by default: an x-ray
                                                                  reads best against something dark. Only in a place. Every scene starts as bright as it is
    hold       who, prop, hand (R or L), grip (one of GRIPS)      for the whole scene; the arm follows the prop
    bite       who, prop, yaw                                     for the whole scene; held in the teeth, turned by yaw
    move       prop, grip, over (seconds)                         a held prop goes to another grip
    strike     who, prop, target, along, over (seconds it falls)  lands at t on a prop, `along` meters from its origin, or on one of its spots ("nail:head"),
                                                                  or on a person ("id:forehead"). They draw back for half a second first, their whole body going into it, unless
                                                                  it's too early in the scene. Code ends the arc on the surface, and whoever holds a struck prop reels, more the
                                                                  further out it's hit; a struck person reels too. sparks: false and rings: false for a soft
                                                                  hit, where nothing's meant to happen. gives: meters a soft tool gives in where it lands, and
                                                                  radius: how wide that is, 0.04 by default: it dents round what it hit and springs back. slow: the
                                                                  share of real speed that runs at, to see it: 0.5 takes twice as long
    fly        prop, from, to, over, hits, slow                   thrown, on gravity's arc, arriving at t + over. from and
                                                                  to are aims or [x, y, z]. If it `hits` a person they
                                                                  reel and it bounces away, falling to the floor. `slow`
                                                                  is the share of real time, for slow motion
    go         prop, through, over, move, then, speed, lands, hits,   under its own power, nose first, through these places
               ends_facing                                        (aims or [x, y, z]) from wherever it is, leaning into
                                                                  turns. `move` plays on the way, `then` once it's there.
                                                                  If it `lands` it slows down, flares and stops on the last
                                                                  place, and rides on it if that's a person. If it `hits` a
                                                                  person they reel and it falls. Otherwise it flies on
    play       prop, move, to, speed                              a thing's clip from t until `to`, looping; speed below 1
                                                                  is slow motion. run.py thing lists a thing's moves
    rock       prop, over, times, degrees, axis, about            a whole thing tipping about a place on it, for what has no
                                                                  clip: it draws back `degrees`, 20 by default, and snaps to
                                                                  where it stood, `times` times in `over` seconds, so each
                                                                  snap lands at t + over x k / times. Place it so where it
                                                                  stands is the contact. axis is pitch (draws its nose up),
                                                                  roll or yaw. about is one of its spots, or its underside.
                                                                  part {"near": a spot, "radius": meters}: only what's near that spot moves, fading
                                                                  out to nothing at the radius, so it bends there and the rest stays still: a bird's
                                                                  head on its neck, with `about` at the neck. wobble: true: instead of drawing back and
                                                                  snapping, it swings both ways, dying away, for what's soft being set going. gentle: true: it comes home slowing
                                                                  down, as if something's taking it up. back: the share of it that's drawing back, for a slow peck with a long snap. toward: a spot: it draws that spot back and up along its own line, rather than about an axis: a beak pecks the way it points
    expression who, name (one of EXPRESSIONS or null), amount
    face       who, keys {face shape: value}, over
    gaze       who, x, y                                          -1 to 1: their left, and up
    glow       who, on (one of GLOW_PLACES), color (one of COLORS), to (seconds), radius, strength
                                                                  on a person's skin. strength 0 to 1, 1 by default: about 0.5 keeps
                                                                  the skin showing, and full is flat paint in a close shot
    rings      on ("id:along"), color, reach, over, count, width  thin clean circles spreading from a point to `reach` meters and
                                                                  fading over `over` seconds, facing the shot's lens: a force going
                                                                  out, a hit, a field
    sparks     on ("id:along"), kind, count, slow, away, life     `count` of them, 26 by default: a bird's peck wants about 6, or a close
                                                                  shot fills with them. Bright sparks for metal on metal, or kind "chips": what
                                                                  flies off wood or stone, or kind "drops": water flung off something wet or
                                                                  spinning, flying on close to `away`. life: seconds each lasts, so they stop
                                                                  where a wall would take them. size: times a drop's usual few millimeters, for a wide shot. A strike's own come with its
                                                                  "sparks": false, true or "chips". slow: the share of real speed they fly at, 0.3 by default: 1 unless the shot's in slow motion, or they drift as if they weighed nothing. away: [x, y, z], the way the surface they come off faces, -y by default
    knock      who, size (degrees), axis [x, y, z]                a blow: head, neck and chest ring down together
    fill       prop, level, over, ease, part                      its liquid's top goes to `level` (as the cast's level counts it) from t, over `over`
                                                                  seconds: up as it's poured into or pushed up, down as it drains or the push on it
                                                                  drops. A level only moves for a reason the picture shows: a pour, air being drawn off, a pump
    pour       from ("id:spot"), into, to, width, speed           a stream straight down from that spot, from t until `to`, into what's in `into`, which
                                                                  has to be right under it with nothing solid in the way, and has to fill while it pours.
                                                                  It falls under gravity, narrowing as it speeds up: its front falls from the spout at t
                                                                  and its tail after `to`. width: meters across at the spout, 0.006 by default. speed:
                                                                  how fast it leaves, 0.3 m/s
    air        box, count, radius, speed, color, to, thins, leave, walled, glow, inside
                                                                  the air in a box ([[x, y, z], [x, y, z]], its low and high corners, in meters) as `count` balls
                                                                  going every way at once at a spread of speeds about `speed` m/s (0.4), from t until `to`, the way
                                                                  a gas's molecules do. They bounce off everything solid and off the top of every liquid, and that
                                                                  is the push air gives, so show it there. radius: meters, 0.01. The box is open air going on past
                                                                  its sides, so what leaves one side comes in at the other: make it reach past the picture. Its top
                                                                  and bottom are unseen lids, also out of the picture, or on what the air's resting on. walled: true
                                                                  for air shut in a box you can see. thins: meters: there's half as much this much higher up, as the
                                                                  sky thins, with the box's bottom for its floor and no top. leave: [{"t", "through" (an aim or [x, y, z]), "share" of them, "from": a box,
                                                                  "over": seconds}]: drawn off out through a point, as a pump or a mouth draws air, and gone once they're
                                                                  through, or once they leave the box, so make the box reach past what holds them. A ball only starts
                                                                  one and a half times its radius from anything solid: in a tube, keep it under a third of the bore. Up to 600 of them. inside: a cast id: they only start in its hollow, the air in a tube,
                                                                  a bottle or a column, rather than anywhere in the box that's clear
  shots     cuts, in order, the first at 0:
    {"t": when, "on": what it's aimed at (see `aim`), "frame": meters of picture top to bottom, "angle": [round them,
     up], 0 being in front of them, "square": true: `round` counts from the set rather than from the way a thing faces, so
     [0, up] looks straight across the counter and its edges stay level, "lens": mm (20 to 30 is the style, close and wide), "fstop",
     "shift": [across, up]: what it's on goes this far from the middle of the picture, as shares of its width and height: [0, -0.2] puts someone on the
     ground in the ground of the picture, "push": how much nearer it ends up, as a share of the distance, "drift": [x, y, z] meters it slides, "shows": cast ids, if only
     some are in this shot: something near the lens is cleared this way, "follow": true: it moves with a moving prop, "ahead": seconds:
     it aims at where its subject will be this long after the shot starts, for a close-up of a landing,
     "to": {"on", "frame", "angle", "shift", "ease", "ahead"}: the camera glides there over the length of the shot, swinging round its subject and easing in and
     out: pull back from a detail to show where it is, rush in on the word that matters, swing round what's happening, or travel from one
     thing to another. Anything it leaves out stays as it was. ease is inout by default, or in, out or linear. At most MOST_ZOOM_PER_SECOND
     times the size and MOST_SWING_PER_SECOND degrees a second}
    A cut is a clear change: the same angle at a clearly different size, or a clearly new angle. A small swing between two
    shots of about the same size reads as the screen wobbling, and is refused. So is a push or a drift fast enough to see as
    a move rather than feel: at most PUSH_PER_SECOND of the distance a second
  captions  [{"t", "to", "text"}]

`aim` is a person's "id:" plus one of AIMS, or a prop's "id:along" in meters, or one of a thing's spots ("id:head"). "id:touch" is where someone running into something first touched it: rings go there. A shot
on a thing is relative to the way it's heading then, so angle [0, 0] sees its face.
"""
from __future__ import annotations

import difflib
import json
import math
from pathlib import Path

SETS = ("gym", "sky_set", "sky_counter", "desert_lot", "studio", "workbench", "engine_void", "place")
PROPS = ("katana", "long_sword", "stick", "ball")
EXPRESSIONS = ("happy", "smile", "surprised", "shocked", "scared", "angry", "yelling", "sad", "disgusted", "thinking",
               "curious", "out_cold")
ROCK_AXES = ("pitch", "roll", "yaw")
SPARKS = ("sparks", "chips", "drops")
GRIPS = ("low_cross", "ready", "raised", "overhead", "at_side", "forward")
GLOW_PLACES = ("jaw", "forehead", "chest", "stomach", "neck")
COLORS = ("green", "red", "blue", "yellow", "white", "orange", "cream", "cyan", "salmon", "gold", "ice")
AIMS = ("eyes", "mouth", "forehead", "jaw", "neck", "chest", "stomach", "hips", "body", "crown", "shoulder_r", "shoulder_l",
        "hand_r", "hand_l", "touch")
EVENTS = {
    "fill": ("t", "prop", "over", "level"),
    "pour": ("t", "to", "from", "into"),
    "air": ("t", "box", "count"),
    "hold": ("who", "prop", "hand", "grip"),
    "bite": ("who", "prop"),
    "move": ("t", "prop", "grip", "over"),
    "strike": ("t", "who", "prop", "target"),
    "fly": ("t", "prop", "from", "to", "over"),
    "go": ("t", "prop", "through", "over"),
    "play": ("t", "prop", "move"),
    "rock": ("t", "prop", "over"),
    "expression": ("t", "who", "name"),
    "face": ("t", "who", "keys"),
    "gaze": ("t", "who"),
    "glow": ("t", "who", "on", "color", "to"),
    "aura": ("t", "on", "color", "to"),     # what `lit` was called: kept so a short directed before still films
    "lit": ("t", "on", "color"),
    "flow": ("t", "on", "color"),
    "tint": ("t", "prop", "color"),
    "ghost": ("t",),
    "act": ("t", "who", "clip"),
    "walk": ("t", "who", "to", "over", "clip"),
    "squash": ("t", "prop", "amount"),
    "press": ("t", "prop", "amount", "way"),
    "dim": ("t", "level"),
    "turns": ("t", "prop", "near", "radius", "into"),
    "pit": ("t", "on", "at", "radius"),
    "wear": ("who", "prop"),
    "spin": ("t", "prop"),
    "slide": ("t", "prop", "over"),
    "rings": ("t", "on"),
    "sparks": ("t", "on"),
    "knock": ("t", "who", "size"),
}
DEFAULT_FSTOP = 3.0      # what a shot gets if it doesn't say: the stage's own default
GLASS_BLUR_MOST = 8.0    # lens / (fstop x frame): how shallow a shot's focus can be on something gone to glass. Measured: 7 is sharp, 17 has its outline in a blur
LONGEST_SHOT = 4.0    # the style cuts about every second; anything held longer than this has lost it
ROCK_DEGREES = 18.0   # a cut that swings less than this, between shots of about the same size, reads as the screen wobbling
SAME_SIZE = 1.3       # shots within this ratio of each other's size count as about the same size
PUSH_PER_SECOND = 0.05      # how fast a plain push can be: a faster one throbs from cut to cut. For more, a shot glides with `to`
MOST_ZOOM_PER_SECOND = 3.5  # how fast a glide can change size: fast enough to rush in, slow enough to follow
MOST_WALK_ASIDE = 25       # degrees someone can go from the way they face, before their steps are visibly going the wrong way
MOST_SWING_PER_SECOND = 160 # and how fast it can swing round, in degrees
AXES = ("x", "y", "z")
EASES = ("in", "out", "inout")
MOST_BALLS = 600            # air drawn as balls: more than this is a fog, and slow to stage


class Refused(ValueError):
    """A scene the stage wouldn't build, because it isn't physically right. `problems` says what's wrong, each in words."""

    def __init__(self, problems: list[str]):
        super().__init__("; ".join(problems))
        self.problems = problems


def load(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _num(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _named(label: str, value, choices) -> list[str]:
    if value in choices:
        return []
    close = difflib.get_close_matches(str(value), [str(c) for c in choices], n=3, cutoff=0.5)
    hint = f"; did you mean {', '.join(close)}?" if close else f"; the choices are {', '.join(map(str, choices))}"
    return [f"{label}: no {value!r}{hint}"]


def _aim(label: str, value, cast: dict, things: dict | None = None) -> list[str]:
    who, _, part = str(value).partition(":")
    if who not in cast:
        return [f"{label}: nothing called {who!r} in the cast"]
    if cast[who].get("type") == "person":
        return _named(label, part, AIMS)
    if part == "" or _num(_float(part)):
        return []
    spots = (things or {}).get(cast[who].get("prop"), {}).get("spots") or []
    if part in spots:
        return []
    return [f"{label}: {part!r} isn't meters along {who}" + (f" or a spot on it: {', '.join(spots)}" if spots else "")]


def _float(text: str):
    try:
        return float(text)
    except ValueError:
        return None


def _resting_problems(cid: str, c: dict, cast: dict, things: dict) -> list[str]:
    """What's wrong with how a thing says it's resting on another."""
    out = []
    if c.get("prop") not in things:
        out.append(f"cast {cid}: only a thing from the library can be `on` something")
        return out
    under = c["on"]
    if under != "set" and under not in cast:
        out.append(f"cast {cid}: it's on {under!r}, who isn't in the cast")
    elif under == cid:
        out.append(f"cast {cid}: it can't be on itself")
    elif under != "set" and cast[under].get("prop") not in things:
        out.append(f"cast {cid}: it's on {under!r}, which isn't a thing from the library")
    if "at" in c and not (isinstance(c["at"], list) and len(c["at"]) == 2 and all(_num(v) for v in c["at"])):
        out.append(f"cast {cid}: with `on`, its at is just [x, y], or left out to center it")
    if "by" in c and c["by"] not in things[c["prop"]].get("spots", []):
        out.append(f"cast {cid}: by {c['by']!r} isn't a spot on it")
    if "onto" in c and (under == "set" or c["onto"] not in things.get(cast.get(under, {}).get("prop"), {}).get("spots", [])):
        out.append(f"cast {cid}: onto {c['onto']!r} isn't a spot on {under}")
    return out


def _against_problems(cid: str, c: dict, cast: dict, things: dict) -> list[str]:
    """What's wrong with how a thing says it comes up to another."""
    if "on" in c or "to" in c:
        return [f"cast {cid}: it comes up against something, or it's on or fixed to something, not both"]
    if c.get("prop") not in things:
        return [f"cast {cid}: only a thing from the library can come up against something"]
    out = []
    if c["against"] == cid or cast.get(c["against"], {}).get("prop") not in things:
        out.append(f"cast {cid}: against {c['against']!r} has to be another thing in the cast")
    if not (isinstance(c.get("at"), list) and len(c["at"]) == 2 and all(_num(v) for v in c["at"])):
        out.append(f"cast {cid}: with `against`, its at is the [x, y] it starts from")
    if not _num(c.get("height")):
        out.append(f"cast {cid}: with `against`, height says how high it comes up to it, in meters")
    by = c.get("by", [])
    if not (isinstance(by, list) and len(by) <= 2 and all(spot in things[c["prop"]].get("spots", []) for spot in by)):
        out.append(f"cast {cid}: with `against`, by is a list of one or two of its spots: {', '.join(things[c['prop']].get('spots', [])) or 'it has none'}")
    if "way" in c and not (isinstance(c["way"], list) and len(c["way"]) == 2 and all(_num(v) for v in c["way"]) and any(c["way"])):
        out.append(f"cast {cid}: way is the [x, y] it goes, to come up against it")
    if "into" in c and not (_num(c["into"]) and 0 <= c["into"]):
        out.append(f"cast {cid}: into is how many meters further in it goes")
    if "tip" in c and not (_num(c["tip"]) and abs(c["tip"]) <= 60):
        out.append(f"cast {cid}: tip is degrees, 60 at most")
    for bend in c.get("bends") or []:
        spots = things[c["prop"]].get("spots", [])
        if not (isinstance(bend, dict) and all(bend.get(key) in spots for key in ("spot", "about", "near")) and _num(bend.get("radius")) and bend["radius"] > 0 and bend.get("toward", bend.get("spot")) in spots):
            out.append(f"cast {cid}: a bend has spot, about and near, each one of its spots, and radius in meters: it has {', '.join(spots) or 'no spots'}")
    return out


def _place_problems(place, kind: str) -> list[str]:
    """What's wrong with a scene's place. A counter has its own ground, and its own light on what's on it."""
    if not (isinstance(place, dict) and isinstance(place.get("sky"), str) and place["sky"]):
        return ["place: says which sky, a Poly Haven sky's id"]
    known = {"sky", "turn", "bright"} | ({"ground", "tile", "reach", "shade", "light"} if kind == "place" else set())
    out = [f"place: there's no {key} for a {kind}" for key in place if key not in known]
    out += [f"place: {key} has to be a number above 0" for key in ("tile", "reach", "bright", "shade", "light") if key in place and not (_num(place[key]) and place[key] > 0)]
    if "turn" in place and not _num(place["turn"]):
        out.append("place: turn is in degrees")
    return out


def _inside_problems(cid: str, c: dict, cast: dict, things: dict) -> list[str]:
    """What's wrong with how a thing says it goes inside another."""
    if any(way in c for way in ("on", "to", "against")):
        return [f"cast {cid}: it goes inside something, or it's on or fixed to or against something, not both"]
    if c.get("prop") not in things:
        return [f"cast {cid}: only a thing from the library can go inside something"]
    out = []
    other = cast.get(c["inside"], {}).get("prop")
    if cast.get(c["inside"], {}).get("type") == "person":
        pass                 # their head
    elif c["inside"] == cid or other not in things:
        out.append(f"cast {cid}: inside {c['inside']!r} has to be another thing in the cast, or a person")
    elif "near" in c and c["near"] not in things[other].get("spots", []):
        out.append(f"cast {cid}: near {c['near']!r} isn't a spot on {c['inside']}: {', '.join(things[other].get('spots', [])) or 'it has none'}")
    if "room" in c and not (_num(c["room"]) and 0 < c["room"] <= 1):
        out.append(f"cast {cid}: room is the share of the room inside it that it fills, up to 1")
    if "by" in c and c["by"] not in things[c["prop"]].get("spots", []):
        out.append(f"cast {cid}: by {c['by']!r} isn't a spot on it")
    return out


def _fixed_problems(cid: str, c: dict, cast: dict, things: dict) -> list[str]:
    """What's wrong with how a thing says it's fixed to another."""
    if "on" in c:
        return [f"cast {cid}: it's on something or fixed to something, not both"]
    if c.get("prop") not in things:
        return [f"cast {cid}: only a thing from the library can be fixed `to` something"]
    other, _, spot = str(c["to"]).partition(":")
    out = []
    if other == cid:
        out.append(f"cast {cid}: it can't be fixed to itself")
    elif cast.get(other, {}).get("prop") not in things:
        out.append(f"cast {cid}: it's fixed to {other!r}, which isn't a thing in the cast")
    elif spot not in things[cast[other]["prop"]].get("spots", []):
        out.append(f"cast {cid}: to {c['to']!r} needs a spot on {other}: {', '.join(things[cast[other]['prop']].get('spots', [])) or 'it has none'}")
    if "by" in c and c["by"] not in things[c["prop"]].get("spots", []):
        out.append(f"cast {cid}: by {c['by']!r} isn't a spot on it")
    return out


def _cast_problems(cast: dict, characters: list[str], clips: list[str], things: dict) -> list[str]:
    out = []
    for cid, c in cast.items():
        kind = c.get("type")
        if kind == "person":
            out += _named(f"cast {cid}: character", c.get("character"), characters)
            out += _named(f"cast {cid}: stance", c.get("stance"), clips)
            at = c.get("at", [0, 0])
            if not (isinstance(at, list) and len(at) == 2 and all(_num(v) for v in at)):
                out.append(f"cast {cid}: at needs [x, y]")
            facing = c.get("facing", 0)
            if not _num(facing) and facing not in cast:
                out.append(f"cast {cid}: facing {facing!r} is neither degrees nor in the cast")
        elif kind == "prop":
            if "sinks" in c and not (_num(c["sinks"]) and 0 <= c["sinks"] and c.get("on")):
                out.append(f"cast {cid}: sinks is how many meters it goes down into what it's on, so it needs an on")
            out += _named(f"cast {cid}: prop", c.get("prop"), (*PROPS, *things))
            if "size" in c and not (_num(c["size"]) and c["size"] > 0):
                out.append(f"cast {cid}: size {c['size']!r} isn't a number above 0")
            if "on" in c:
                out += _resting_problems(cid, c, cast, things)
            if "to" in c:
                out += _fixed_problems(cid, c, cast, things)
            if "against" in c:
                out += _against_problems(cid, c, cast, things)
            if "inside" in c:
                out += _inside_problems(cid, c, cast, things)
            facing = c.get("facing", 0)
            if not _num(facing) and facing not in cast:
                out.append(f"cast {cid}: facing {facing!r} is neither degrees nor in the cast")
            if any(key in c for key in ("level", "above", "part")):
                out += _level_problems(cid, c, cast, things)
        else:
            out.append(f"cast {cid}: type {kind!r} isn't person or prop")
    return out


def _liquids(cid: str, cast: dict, things: dict) -> list:
    return (things.get((cast.get(cid) or {}).get("prop")) or {}).get("liquids") or []


def _part_problems(label: str, cid: str, part, cast: dict, things: dict) -> list[str]:
    """Which liquid in a thing: it has to have one, and say which if it has more."""
    liquids = _liquids(cid, cast, things)
    if not liquids:
        return [f"{label}: {cid} has no liquid in it. A thing that holds one is built with a part marked liquid (things/spec.py)"]
    if part is None:
        return [] if len(liquids) == 1 else [f"{label}: {cid} has more than one liquid: say which part, one of {', '.join(liquids)}"]
    return [] if part in liquids else [f"{label}: part {part!r} isn't a liquid in {cid}: {', '.join(liquids)}"]


def _level_problems(cid: str, c: dict, cast: dict, things: dict) -> list[str]:
    out = _part_problems(f"cast {cid}", cid, c.get("part"), cast, things)
    if "level" in c and not (_num(c["level"]) and c["level"] >= 0):
        out.append(f"cast {cid}: level is meters, 0 or more")
    if "above" in c:
        if "level" not in c:
            out.append(f"cast {cid}: above needs a level: meters above the top of {c['above']}'s liquid")
        if c["above"] == cid or not _liquids(c["above"], cast, things):
            out.append(f"cast {cid}: above {c['above']!r} has to be another thing in the cast with a liquid in it")
        seen, at = {cid}, c["above"]
        while at in cast and cast[at].get("above"):
            if at in seen:
                out.append(f"cast {cid}: its level is counted above another's that's counted above it")
                break
            seen.add(at)
            at = cast[at]["above"]
    return out


def _event_problems(e: dict, i: int, scene: dict, things: dict) -> list[str]:
    cast, length = scene["cast"], scene["length"]
    kind = e.get("do")
    if kind not in EVENTS:
        return _named(f"happens {i}: do", kind, tuple(EVENTS))
    label = f"happens {i} ({kind})"
    out = [f"{label}: missing {key}" for key in EVENTS[kind] if key not in e]
    if out:
        return out
    if "t" in e and not (_num(e["t"]) and 0 <= e["t"] <= length):
        out.append(f"{label}: t {e['t']!r} is outside the scene")
    for key in ("who",):
        if key in e and cast.get(e[key], {}).get("type") != "person":
            out.append(f"{label}: {e[key]!r} isn't a person in the cast")
    if "prop" in e and cast.get(e["prop"], {}).get("type") != "prop":
        out.append(f"{label}: {e['prop']!r} isn't a prop in the cast")
    if kind == "strike":
        if cast.get(e["target"], {}).get("type") == "prop":
            if not _num(e.get("along")):
                out.append(f"{label}: say how far along {e['target']} it lands, in meters")
        else:
            out += _aim(f"{label}: target", e["target"], cast, things)
        if "gives" in e:
            spots = things.get(cast.get(e["prop"], {}).get("prop"), {}).get("spots") or []
            if "end" not in spots or "grip" not in spots:
                out.append(f"{label}: only a tool with a grip and an end spot can give where it lands")
            if not (_num(e["gives"]) and 0 < e["gives"] <= 0.2):
                out.append(f"{label}: gives is how many meters it gives in, up to 0.2")
            if "radius" in e and not (_num(e["radius"]) and 0 < e["radius"] <= 0.5):
                out.append(f"{label}: radius is how wide the dent is, in meters")
            if "slow" in e and not (_num(e["slow"]) and 0 < e["slow"] <= 1):
                out.append(f"{label}: slow is the share of real speed, above 0 and up to 1")
    if kind == "fly":
        for key in ("from", "to"):
            if not (isinstance(e[key], list) and len(e[key]) == 3):
                out += _aim(f"{label}: {key}", e[key], cast, things)
        if not (_num(e["over"]) and e["over"] > 0):
            out.append(f"{label}: over needs seconds")
        if "hits" in e and cast.get(e["hits"], {}).get("type") != "person":
            out.append(f"{label}: hits {e['hits']!r}, who isn't a person in the cast")
    if kind == "go":
        through = e["through"]
        if not (isinstance(through, list) and through):
            out.append(f"{label}: through needs a list of places")
        else:
            for stop in through:
                if not (isinstance(stop, list) and len(stop) == 3):
                    out += _aim(f"{label}: through", stop, cast, things)
        if not (_num(e["over"]) and e["over"] > 0):
            out.append(f"{label}: over needs seconds")
        if "hits" in e and cast.get(e["hits"], {}).get("type") != "person":
            out.append(f"{label}: hits {e['hits']!r}, who isn't a person in the cast")
        if "ends_facing" in e and not _num(e["ends_facing"]) and e["ends_facing"] not in cast:
            out.append(f"{label}: ends_facing {e['ends_facing']!r} is neither degrees nor in the cast")
    if kind == "squash":
        entry = things.get(cast.get(e["prop"], {}).get("prop"))
        if entry is None:
            out.append(f"{label}: {e['prop']} isn't a thing from the library")
        elif "about" in e and e["about"] not in entry.get("spots", []):
            out.append(f"{label}: about {e['about']!r} isn't a spot on it: {', '.join(entry.get('spots', [])) or 'it has none'}")
        out += _named(f"{label}: axis", e.get("axis", "y"), ("x", "y", "z"))
        if not (_num(e["amount"]) and 0 < e["amount"] <= 0.6):
            out.append(f"{label}: amount is above 0, and 0.6 at most")
    if kind == "rock":
        entry = things.get(cast.get(e["prop"], {}).get("prop"))
        if entry is None:
            out.append(f"{label}: {e['prop']} isn't a thing from the library")
        elif "about" in e and e["about"] not in entry.get("spots", []):
            out.append(f"{label}: about {e['about']!r} isn't a spot on it: {', '.join(entry.get('spots', [])) or 'it has none'}")
        if "part" in e:
            part = e["part"] if isinstance(e["part"], dict) else {}
            if entry is not None and part.get("near") not in entry.get("spots", []):
                out.append(f"{label}: part needs near, one of its spots: {', '.join(entry.get('spots', [])) or 'it has none'}")
            if not (_num(part.get("radius")) and part["radius"] > 0):
                out.append(f"{label}: part needs a radius, in meters")
            if "about" not in e:
                out.append(f"{label}: part needs about, the spot it bends at")
        out += _named(f"{label}: axis", e.get("axis", "pitch"), ROCK_AXES)
        if entry is not None and "toward" in e and e["toward"] not in entry.get("spots", []):
            out.append(f"{label}: toward {e['toward']!r} isn't a spot on it: {', '.join(entry.get('spots', [])) or 'it has none'}")
        if not (_num(e["over"]) and e["over"] > 0):
            out.append(f"{label}: over needs seconds")
        if not (isinstance(e.get("times", 1), int) and e.get("times", 1) > 0):
            out.append(f"{label}: times has to be a whole number above 0")
        if not (_num(e.get("degrees", 20)) and 0 < e.get("degrees", 20) <= 120):
            out.append(f"{label}: degrees has to be above 0, and 120 at most")
    if kind in ("go", "play"):
        moves = things.get(cast.get(e["prop"], {}).get("prop"), {}).get("moves") or []
        for key in ("move", "then"):
            if key in e:
                out += _named(f"{label}: {key}", e[key], moves) if moves else [f"{label}: {e['prop']} has no moves"]
        if "speed" in e and not (_num(e["speed"]) and e["speed"] > 0):
            out.append(f"{label}: speed {e['speed']!r} isn't a number above 0")
    if kind == "hold":
        out += _named(f"{label}: hand", e["hand"], ("R", "L"))
    if kind in ("hold", "move"):
        out += _named(f"{label}: grip", e["grip"], GRIPS)
    if kind == "expression" and e["name"] is not None:
        out += _named(f"{label}: name", e["name"], EXPRESSIONS)
    if kind == "glow":
        out += _named(f"{label}: on", e["on"], GLOW_PLACES)
        out += _named(f"{label}: color", e["color"], COLORS)
        if not (_num(e["to"]) and e["t"] < e["to"]):
            out.append(f"{label}: to must come after t")
    if kind in ("rings", "sparks"):
        out += _aim(f"{label}: on", e["on"], cast, things)
    if kind == "sparks" and "kind" in e:
        out += _named(f"{label}: kind", e["kind"], SPARKS)
    if kind == "sparks" and "life" in e and not (_num(e["life"]) and 0.05 <= e["life"] <= 3):
        out.append(f"{label}: life is seconds each lasts, 0.05 to 3")
    if kind == "strike" and isinstance(e.get("sparks"), str):
        out += _named(f"{label}: sparks", e["sparks"], SPARKS)
    if kind in ("aura", "lit", "flow"):
        who, _, part = str(e["on"]).partition(":")
        entry = things.get(cast.get(who, {}).get("prop"))
        if entry is None:
            out.append(f"{label}: {who!r} isn't a thing from the library: a person's is `glow`")
            return out
        if part and part not in entry.get("spots", []):
            out.append(f"{label}: {part!r} isn't a spot on {who}: {', '.join(entry.get('spots', [])) or 'it has none'}")
        out += _named(f"{label}: color", e["color"], COLORS)
        if "to" in e and not (_num(e["to"]) and e["t"] < e["to"]):
            out.append(f"{label}: to must come after t")
        if kind == "flow":
            if "along" in e and e["along"] not in entry.get("lines", []):
                out.append(f"{label}: along {e['along']!r} isn't a line on {who}: {', '.join(entry.get('lines', [])) or 'it has none'}")
            elif "along" not in e and not (isinstance(e.get("radii"), list) and e["radii"] and all(_num(r) and r > 0 for r in e["radii"])):
                out.append(f"{label}: needs radii, a list of meters, or along, a line on {who}")
            if "side" in e and e["side"] not in ("top", "under"):
                out.append(f"{label}: side is top or under")
        if kind == "lit" and "radius" in e and not part:
            out.append(f"{label}: a radius needs a spot to be around: on \"{who}:a spot\"")
    if kind == "wear":
        if e["prop"] in cast and cast[e["prop"]].get("prop") not in things:
            out.append(f"{label}: only a thing from the library can be worn")
    if kind == "ghost":
        if ("prop" in e) == ("who" in e):
            out.append(f"{label}: says which prop, or who: one of them")
        elif "prop" in e and e["prop"] in cast and cast[e["prop"]].get("prop") not in things:
            out.append(f"{label}: only a thing from the library can go to glass")
        if "color" in e:
            out += _named(f"{label}: color", e["color"], COLORS)
    if kind == "press":
        if things.get(cast.get(e["prop"], {}).get("prop")) is None:
            out.append(f"{label}: {e['prop']} isn't a thing from the library")
        elif "near" in e and (e["near"] not in things[cast[e["prop"]]["prop"]].get("spots", []) or not (_num(e.get("radius")) and e["radius"] > 0)):
            out.append(f"{label}: near is one of its spots, with radius in meters")
        if not (_num(e["amount"]) and 0 < e["amount"] <= 0.5):
            out.append(f"{label}: amount is the share of its length it shortens by, above 0 and 0.5 at most")
        if not (isinstance(e["way"], list) and len(e["way"]) == 3 and all(_num(v) for v in e["way"]) and any(e["way"])):
            out.append(f"{label}: way is the [x, y, z] it was going")
    if kind == "turns":
        entry = things.get(cast.get(e["prop"], {}).get("prop"))
        if entry is None:
            out.append(f"{label}: {e['prop']} isn't a thing from the library")
        elif e["near"] not in entry.get("spots", []):
            out.append(f"{label}: near {e['near']!r} isn't a spot on it: {', '.join(entry.get('spots', [])) or 'it has none'}")
        if not (_num(e["radius"]) and e["radius"] > 0):
            out.append(f"{label}: radius is in meters")
        into = e["into"]
        if not (isinstance(into, dict) and isinstance(into.get("color"), list) and len(into["color"]) == 3 and all(_num(v) and 0 <= v <= 1 for v in into["color"])):
            out.append(f"{label}: into has a color, [r, g, b], each 0 to 1")
    if kind == "pit":
        if cast.get(e["on"], {}).get("prop") not in things:
            out.append(f"{label}: on {e['on']!r} has to be a thing from the library")
        out += _aim(f"{label}: at", e["at"], cast, things)
        if not (_num(e["radius"]) and e["radius"] > 0):
            out.append(f"{label}: radius is in meters")
    if kind == "dim":
        if scene.get("set") != "place":
            out.append(f"{label}: only a place can go dark")
        if not (_num(e["level"]) and 0 < e["level"]):
            out.append(f"{label}: level is the share of its light it goes to, above 0")
    if kind == "tint":
        if not (e["color"] in COLORS or (isinstance(e["color"], list) and len(e["color"]) == 3 and all(_num(v) and 0 <= v <= 1 for v in e["color"]))):
            out.append(f"{label}: color is one of {', '.join(COLORS)}, or [r, g, b], each 0 to 1")
    if kind == "spin":
        entry = things.get(cast.get(e["prop"], {}).get("prop"))
        if entry is None:
            out.append(f"{label}: {e['prop']} isn't a thing from the library")
        else:
            if "about" in e and e["about"] not in entry.get("spots", []):
                out.append(f"{label}: about {e['about']!r} isn't a spot on it: {', '.join(entry.get('spots', [])) or 'it has none'}")
            out += _named(f"{label}: axis", e.get("axis", "z"), AXES)
        if "rate" in e and not _num(e["rate"]):
            out.append(f"{label}: rate is turns a second")
        if "to" in e and not (_num(e["to"]) and e["t"] < e["to"]):
            out.append(f"{label}: to must come after t")
    if kind == "fill":
        out += _part_problems(label, e["prop"], e.get("part"), cast, things)
        if not (_num(e["level"]) and e["level"] >= 0):
            out.append(f"{label}: level is meters, 0 or more, as the cast's level counts it")
        if not (_num(e["over"]) and e["over"] > 0):
            out.append(f"{label}: over needs seconds")
        out += _named(f"{label}: ease", e.get("ease", "inout"), EASES + ("linear",))
    if kind == "pour":
        who, _, spot = str(e["from"]).partition(":")
        spots = (things.get((cast.get(who) or {}).get("prop")) or {}).get("spots") or []
        if who not in cast or spot not in spots:
            out.append(f"{label}: from is the spot it pours from, on a thing in the cast: " + (f"{who} has {', '.join(spots)}" if spots else f"{who!r} has no spots"))
        if e["into"] not in cast:
            out.append(f"{label}: into {e['into']!r} isn't in the cast")
        else:
            out += _part_problems(label, e["into"], e.get("part"), cast, things)
            filling = [f for f in scene.get("happens") or [] if isinstance(f, dict) and f.get("do") == "fill" and f.get("prop") == e["into"] and _num(f.get("t")) and _num(f.get("over"))
                       and _num(e.get("to")) and f["t"] < e["to"] and f["t"] + f["over"] > e["t"]]
            if not filling:
                out.append(f"{label}: what's poured into {e['into']} has to fill it: give {e['into']} a fill while it pours")
            else:
                fills = sorted((f for f in scene.get("happens") or [] if isinstance(f, dict) and f.get("do") == "fill" and f.get("prop") == e["into"] and _num(f.get("t"))), key=lambda f: f["t"])
                earlier = [f for f in fills if f["t"] < filling[0]["t"]]
                before = earlier[-1].get("level") if earlier else cast[e["into"]].get("level")
                if before is None:
                    out.append(f"{label}: {e['into']} starts full, with no room to pour into: give it a level to start at")
                elif _num(before) and _num(filling[0].get("level")) and filling[0]["level"] <= before:
                    out.append(f"{label}: what's poured into {e['into']} raises it, but its fill takes it from {before} to {filling[0]['level']} m")
        if not (_num(e["to"]) and e["to"] > e["t"]):
            out.append(f"{label}: to is when it stops, after t")
        if "width" in e and not (_num(e["width"]) and 0 < e["width"] <= 0.2):
            out.append(f"{label}: width is meters across at the spout, up to 0.2")
        if "speed" in e and not (_num(e["speed"]) and 0 <= e["speed"] <= 5):
            out.append(f"{label}: speed is how fast it leaves the spout, up to 5 m/s")
    if kind == "air":
        out += _air_problems(label, e, cast, things)
    if kind == "slide":
        if sum(key in e for key in ("from", "by", "until")) != 1:
            out.append(f"{label}: says from or by or until, one of them")
        if "until" in e and (e["until"] not in scene["cast"] or not (isinstance(e.get("way"), list) and len(e["way"]) == 3 and all(_num(v) for v in e["way"]) and any(e["way"]))):
            out.append(f"{label}: until is who it goes until it touches, in the cast, with way [x, y, z] the way it goes")
        for key in ("from", "by"):
            if key in e and not (isinstance(e[key], list) and len(e[key]) == 3 and all(_num(v) for v in e[key])):
                out.append(f"{label}: {key} is [x, y, z] meters")
        if not (_num(e["over"]) and e["over"] > 0):
            out.append(f"{label}: over needs seconds")
        out += _named(f"{label}: ease", e.get("ease", "inout"), EASES + ("linear",))
    return out


def _box(value) -> bool:
    return (isinstance(value, list) and len(value) == 2 and all(isinstance(v, list) and len(v) == 3 and all(_num(x) for x in v) for v in value)
            and all(value[0][i] < value[1][i] for i in range(3)))


def _air_problems(label: str, e: dict, cast: dict, things: dict) -> list[str]:
    out = []
    if not _box(e["box"]):
        out.append(f"{label}: box is [[x, y, z], [x, y, z]], its low corner and its high one, in meters")
    if not (isinstance(e["count"], int) and not isinstance(e["count"], bool) and 1 <= e["count"] <= MOST_BALLS):
        out.append(f"{label}: count is how many balls, a whole number from 1 to {MOST_BALLS}")
    if "radius" in e and not (_num(e["radius"]) and 0.0005 <= e["radius"] <= 0.3):
        out.append(f"{label}: radius is meters, from 0.0005 to 0.3")
    if "speed" in e and not (_num(e["speed"]) and 0 < e["speed"] <= 30):
        out.append(f"{label}: speed is m/s, above 0 and up to 30")
    if "thins" in e and not (_num(e["thins"]) and e["thins"] > 0):
        out.append(f"{label}: thins is meters: how much higher there's half as much")
    if "color" in e:
        out += _named(f"{label}: color", e["color"], COLORS)
    if "to" in e and not (_num(e["to"]) and e["to"] > e["t"]):
        out.append(f"{label}: to must come after t")
    if "inside" in e and e["inside"] not in cast:
        out.append(f"{label}: inside {e['inside']!r} isn't in the cast")
    for i, g in enumerate(e.get("leave") or []):
        part = f"{label}: leave {i + 1}"
        if not isinstance(g, dict) or not _num(g.get("t")) or g["t"] < e["t"]:
            out.append(f"{part}: t is when they start to go, not before the air's there")
            continue
        through = g.get("through")
        if not (isinstance(through, list) and len(through) == 3 and all(_num(v) for v in through)):
            out += _aim(f"{part}: through", through, cast, things)
        if "share" in g and not (_num(g["share"]) and 0 < g["share"] <= 1):
            out.append(f"{part}: share is how many of them go, above 0 and up to 1")
        if "over" in g and not (_num(g["over"]) and g["over"] > 0):
            out.append(f"{part}: over is seconds")
        if "from" in g and not _box(g["from"]):
            out.append(f"{part}: from is the box they go from, [[x, y, z], [x, y, z]]")
    return out


def _way(shot: dict) -> tuple[float, float, float]:
    around, up = (math.radians(v) for v in shot.get("angle", (0, 0)))
    return math.sin(around) * math.cos(up), -math.cos(around) * math.cos(up), math.sin(up)


def _shift_problems(label: str, shift) -> list[str]:
    if isinstance(shift, (list, tuple)) and len(shift) == 2 and all(_num(v) and abs(v) <= 0.45 for v in shift):
        return []
    return [f"{label} shift is [across, up], each a share of the picture from its middle, from -0.45 to 0.45"]


def _glass_in_focus(shot: dict, scene: dict, ends: float, label: str, things: dict | None = None) -> list[str]:
    """Glass has no depth of its own for a camera to focus on, so depth of field blurs it as if it were as far off as whatever's behind it, and an x-ray's outline goes soft while the bark beside it stays sharp.
    A thing made with glass in it, a tube or a dish, is the same."""
    shown = shot.get("shows") or list(scene.get("cast") or {})
    glass = any((things or {}).get(((scene.get("cast") or {}).get(cid) or {}).get("prop"), {}).get("glass") for cid in shown)
    if not glass and not any(e.get("do") == "ghost" and _num(e.get("t")) and e["t"] < ends for e in scene.get("happens") or []):
        return []
    frames = [shot.get("frame"), (shot.get("to") or {}).get("frame", shot.get("frame"))]
    lens, fstop = shot.get("lens", 28), shot.get("fstop", DEFAULT_FSTOP)
    if not all(_num(v) and v > 0 for v in (*frames, lens, fstop)):
        return []
    closest = min(frames)
    if lens / (fstop * closest) <= GLASS_BLUR_MOST:
        return []
    return [f"{label}: something's gone to glass here, and glass has no depth for the camera to focus on, so at fstop {fstop} it blurs with what's behind it. This shot needs an fstop of at least {math.ceil(lens / (GLASS_BLUR_MOST * closest))}"]


def _glide_problems(shot: dict, length: float, label: str, cast: dict, things: dict) -> list[str]:
    """A shot that travels: where it's going, and that it isn't going so fast nobody can follow it."""
    to = shot.get("to")
    if not isinstance(to, dict):
        return [f"{label}: to is what the camera glides to: on, frame, angle"]
    out = _aim(f"{label}: to on", to["on"], cast, things) if "on" in to else []
    frame = to.get("frame", shot.get("frame"))
    if not (_num(frame) and 0.05 <= frame <= 40):
        out.append(f"{label}: to's frame {frame!r} isn't how many meters of picture")
    angle = to.get("angle", shot.get("angle", (0, 0)))
    if not (isinstance(angle, (list, tuple)) and len(angle) == 2 and all(_num(v) for v in angle)):
        out.append(f"{label}: to's angle is [round them, up]")
    out += _named(f"{label}: to's ease", to.get("ease", "inout"), EASES + ("linear",))
    if "shift" in to:
        out += _shift_problems(f"{label}: to's", to["shift"])
    if out or not (_num(shot.get("frame")) and shot["frame"] > 0 and length > 0):
        return out
    size = max(frame, shot["frame"]) / min(frame, shot["frame"])
    if size ** (1 / length) > MOST_ZOOM_PER_SECOND:
        out.append(f"{label}: it goes {size:.1f}x in {length:.1f} s, too fast to follow: at most {MOST_ZOOM_PER_SECOND}x a second. Make it travel less, or for longer")
    start = shot.get("angle", (0, 0))
    swing = abs((angle[0] - start[0] + 180) % 360 - 180)
    if "on" not in to and swing / length > MOST_SWING_PER_SECOND:
        out.append(f"{label}: it swings {swing:.0f} degrees in {length:.1f} s, too fast to follow: at most {MOST_SWING_PER_SECOND} degrees a second")
    return out


def _ending(shot: dict) -> dict:
    """A shot as it stands when it ends, which is what the next one cuts from."""
    to = shot.get("to")
    if not isinstance(to, dict):
        return shot
    return {**shot, **{key: to[key] for key in ("on", "frame", "angle") if key in to}}


def _walk_problems(scene: dict) -> list[str]:
    """Someone going somewhere other than the way they're facing: their steps only go forward. Each walk goes on from where the last one ended."""
    out, where = [], {}
    cast = scene.get("cast") or {}
    walks = [e for e in scene.get("happens") or [] if isinstance(e, dict) and e.get("do") == "walk" and _num(e.get("t")) and isinstance(e.get("to"), list) and len(e["to"]) == 2]
    for e in sorted(walks, key=lambda e: e["t"]):
        c, who = cast.get(e.get("who")), e.get("who")
        if not (isinstance(c, dict) and c.get("type") == "person" and isinstance(c.get("facing", 0), (int, float))):
            continue
        here = where.get(who, c.get("at", (0, 0)))
        across, along = e["to"][0] - here[0], e["to"][1] - here[1]
        far = math.hypot(across, along)
        turn = math.radians(c.get("facing", 0))
        if far > 0.05 and (across * math.sin(turn) - along * math.cos(turn)) / far < math.cos(math.radians(MOST_WALK_ASIDE)):
            out.append(f"{who} walks from {list(here)} to {e['to']}, and that isn't the way they're facing ({c.get('facing', 0)} degrees): "
                       f"point their facing the way they go, or start them somewhere else")
        where[who] = e["to"]
    return out


def _cut_problems(shots: list[dict], cast: dict) -> list[str]:
    """Shots of one subject that cut with too small a swing, and pushes fast enough to throb."""
    out = []
    for i, (before, b) in enumerate(zip(shots, shots[1:]), 1):
        a = _ending(before)
        if str(a.get("on")).partition(":")[0] != str(b.get("on")).partition(":")[0] or bool(a.get("square")) != bool(b.get("square")):
            continue
        if not (_num(a.get("frame")) and _num(b.get("frame")) and a["frame"] > 0 and b["frame"] > 0):
            continue
        across = sum(x * y for x, y in zip(_way(a), _way(b)))
        swing = math.degrees(math.acos(max(-1.0, min(1.0, across))))
        size = max(a["frame"], b["frame"]) / min(a["frame"], b["frame"])
        if 0.5 < swing < ROCK_DEGREES and size < SAME_SIZE:
            out.append(f"shot {i}: it swings only {swing:.0f} degrees from the last at about the same size, which reads as the screen "
                       f"wobbling. Keep the angle and change the size by more than {SAME_SIZE}x, or swing at least {ROCK_DEGREES:.0f} degrees")
    return out


def check(scene: dict, characters: list[str], clips: list[str], things: dict | None = None, moves: list[str] | None = None) -> list[str]:
    """Everything wrong with a scene, in words. `things` is things/build.py's menu: each thing's moves and spots."""
    things = things or {}
    if not isinstance(scene, dict):
        return ["a scene is a JSON object"]
    out = [f"{key}: missing" for key in ("length", "set", "cast", "shots") if key not in scene]
    if out:
        return out
    if not (_num(scene["length"]) and 0.5 <= scene["length"] <= 180):
        out.append(f"length: {scene['length']!r} isn't between 0.5 and 180 seconds")
        return out
    out += _named("set", scene["set"], SETS)
    out += _cast_problems(scene["cast"], characters, clips, things)
    if out:
        return out
    for i, e in enumerate(scene.get("happens") or []):
        out += _event_problems(e, i, scene, things)
    held = {e["prop"] for e in scene.get("happens") or [] if e.get("do") in ("hold", "bite") and "prop" in e}
    for e in scene.get("happens") or []:
        if e.get("do") == "strike" and e.get("prop") not in held:
            out.append(f"strike: {e.get('who')} has to hold {e.get('prop')} to strike with it")
    shots = scene["shots"]
    if not shots or shots[0].get("t") != 0:
        out.append("shots: the first has to start at 0")
    times = [s.get("t", -1) for s in shots] + [scene["length"]]
    for i, s in enumerate(shots):
        label = f"shot {i}"
        out += _aim(f"{label}: on", s.get("on"), scene["cast"], things)
        if not (_num(s.get("frame")) and 0.05 <= s["frame"] <= 40):
            out.append(f"{label}: frame {s.get('frame')!r} isn't how many meters of picture")
        if not (_num(s.get("lens", 28)) and 12 <= s.get("lens", 28) <= 135):
            out.append(f"{label}: lens {s.get('lens')!r} isn't in mm")
        subject = scene["cast"].get(str(s.get("on")).partition(":")[0]) or {}
        size = float(subject.get("size", 1.0)) if _num(subject.get("size", 1.0)) else 1.0
        sharp = (things.get(subject.get("prop")) or {}).get("sharp_from", 0) * size
        if _num(s.get("frame")) and s["frame"] < sharp:
            out.append(f"{label}: at a frame of {s['frame']} m its texture is stretched until it's blurry: {subject['prop']} is only sharp from {round(sharp, 2)} m. "
                       f"Pull back, or get a more detailed model")
        out += _glass_in_focus(s, scene, times[i + 1], label, things)
        if times[i + 1] <= times[i]:
            out.append(f"{label}: starts after the next one")
        elif times[i + 1] - times[i] > LONGEST_SHOT:
            out.append(f"{label}: {times[i + 1] - times[i]:.1f} s is too long: this style cuts about every second")
        elif "to" in s:
            out += _glide_problems(s, times[i + 1] - times[i], label, scene["cast"], things)
        elif abs(s.get("push", 0)) > PUSH_PER_SECOND * (times[i + 1] - times[i]) + 1e-6:
            out.append(f"{label}: a push of {s['push']} over {times[i + 1] - times[i]:.1f} s moves fast enough to see, and throbs from cut to "
                       f"cut. At most {PUSH_PER_SECOND} a second, or hold still")
        if "shift" in s:
            out += _shift_problems(label, s["shift"])
        for cid in s.get("shows") or []:
            if cid not in scene["cast"]:
                out.append(f"{label}: shows {cid!r}, who isn't in the cast")
    out += _cut_problems(shots, scene["cast"])
    for i, e in enumerate(scene.get("happens") or []):
        if isinstance(e, dict) and e.get("do") in ("act", "walk"):
            out += _named(f"happens {i}: clip", e.get("clip"), clips if moves is None else moves)
            if e["do"] == "walk" and not (isinstance(e.get("to"), list) and len(e["to"]) == 2 and all(_num(v) for v in e["to"])):
                out.append(f"happens {i}: to is where they walk to, [x, y]")
            if e["do"] == "walk" and "hits" in e and e["hits"] not in scene["cast"]:
                out.append(f"happens {i}: hits {e['hits']!r}, who isn't in the cast")
            if e["do"] == "walk" and "with" in e:
                out += _named(f"happens {i}: with", e["with"], AIMS)
            if e["do"] == "walk" and "ramp" in e and not ("slow" in e and _num(e["ramp"]) and e["ramp"] > 0):
                out.append(f"happens {i}: ramp is the seconds slow motion takes to come on, so it needs a slow")
            if e["do"] == "walk" and "covers" in e and not (_num(e["covers"]) and e["covers"] > 0):
                out.append(f"happens {i}: covers is how many meters they start short of where they stop")
            if e["do"] == "walk" and "slow" in e:
                slow = e["slow"]
                if not (isinstance(slow, list) and len(slow) == 2 and all(_num(v) for v in slow) and 0 < slow[0] < e.get("over", 0) and 0 < slow[1] < 1):
                    out.append(f"happens {i}: slow is [how many seconds of it, the share of its speed], such as [0.45, 0.2], and shorter than its over")
    out += _walk_problems(scene)
    if scene.get("set") == "place" or "place" in scene:
        if scene.get("set") not in ("place", "sky_counter"):
            out.append("place: only the place set and sky_counter have one")
        else:
            out += _place_problems(scene.get("place"), scene["set"])
    for pair in scene.get("touching") or []:
        if not (isinstance(pair, list) and len(pair) == 2 and all(cid in scene["cast"] for cid in pair)):
            out.append(f"touching: {pair!r} is a pair of cast ids")
    for i, aim in enumerate(scene.get("anchors") or []):
        out += _aim(f"anchors {i}", aim, scene["cast"], things)
    for i, c in enumerate(scene.get("captions") or []):
        if not (isinstance(c.get("text"), str) and _num(c.get("t")) and _num(c.get("to")) and c["t"] < c["to"]):
            out.append(f"caption {i}: needs text, t, and a later to")
    return out

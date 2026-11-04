# Directing a short

You direct one vertical 3D short for {channel_name} (premise: {scenario_family}), by writing it in the scene language. You write data, and fixed code stages it, works out contacts and physics, and renders it. Nothing you write runs as code, and there's no writing new abilities: if the language can't do something, show the idea another way.

## The manner

It's built on a few things done well, not on acting:

- **People hold strong poses and barely move.** Don't try to act out long actions: nobody walks across a room or wrestles. A person holds a stance, reacts with an expression and their eyes, and things are placed, thrown and struck around them.
- **Cut about every 1 to 2.5 seconds,** and on the words. Each line usually gets a new shot, and a long line two. No shot may run over 4 seconds.
- **The camera stays level and still.** On a set with a surface, every shot is `square: true` with its `angle` round at 0, so the counter's edge runs dead level across the picture, shot after shot. A cut is a clear change: the same angle at a clearly different size (wide, then close), or a clearly different height (side-on, then from above). A small swing between two shots of about the same size reads as the screen wobbling, and the check refuses it. Hold still, or creep: a `push` of at most 0.05 a second. Anything faster throbs from cut to cut.
- **Wide lenses close up.** `lens` 20 to 30, `frame` small: 0.4 to 0.9 m on a face, 0.1 to 0.3 m on a detail, 1 m or so for the shot that shows where things are.
- **One moment it all leads to,** in slow motion: a thrown or flying thing has `slow` 0.2 to 0.5, with the close shot starting just before it lands. Red `rings` and `sparks` where it hits, `knock` on who's hit, and a `glow` on the place that takes it. A big `expression` right after.
- **Stillness before the hit.** The half second before that moment is the quietest of the short: a held face, no drift, so that the hit lands.
- **One thing to look at in each shot,** and keep direction across a cut: what leaves going left comes in going left, and the camera stays on one side of the people, unless the cut means to surprise.
- **A glow belongs to something, and never floats.** There are no balls of light. A word that names a thing flashes that thing: `lit` on it, whole, for about half a second, its edges burning and its middle keeping some of its color. Heat is `lit` on a spot with a `radius`, on the surface that's hot. Current, a signal, anything running is `flow`: thin white-hot lines on the surface, with its color in the halo. A force going out is `rings`. Red for heat, force or pain; green or blue for what's working or being explained. Keep it fine: thin lines and one lit thing at a time look expensive, and a lot of glow looks cheap.
- **Clean sets.** `sky_counter`, a level wooden counter before plain blue, for anything that's on a surface. `sky_set`, the plain blue, for people. Things are few and big in frame.
- **Show the mechanism.** If something spins, something visibly drives it: a shaft, a motor. Choose its axis so the lens sees it turn: a magnet turning flat, seen from the side, is only a line sliding about.

## Keep it physically true

- **Code measures all of this, and refuses what's wrong.** When a scene's staged, its meshes are checked against each other frame by frame. If anything passes through something, hangs in the air unsaid, or stands in front of the lens, the scene comes back with the reason, and you fix it. So stage it right the first time:
- **Say what a thing is `on`,** and it comes down until it touches: `"on": "set"` for the counter, `"on": "stand", "by": "base", "onto": "top"` for a pan on a stand. Don't work out heights by hand. A thing fixed to another at a point, from any side, says `"to": "motor:mouth", "by": "tail"`, and the two spots meet exactly. A thing that hangs on purpose, an arrow or a bulb over a head, says `"floats": true`. A thing set down during the scene is `slide` with `from`, so it lands exactly where it rests; never use `go` or `lands` for it, since those are for what flies, and flare like a bird. What else is meant to overlap goes in `touching`.
- **A hat is `wear`.** Code measures the head and the inside of the hat, seats it, and it rides on the head. Never place one by numbers.
- A person's `at` and things' places are in meters, and +z is up. People stand on the floor. Things in a thing's `at` sit on their underside.
- Whoever strikes has to stand within reach; the check says so if not. Thrown things `fly` on a real arc. Things with wings `go`, with `lands` when they arrive and `then` a resting move. A thing with no clips that has to strike something `rock`s: place it touching what it hits, since where it stands is the contact, and put `rings` or `sparks` on each snap.
- People can't change stance within a scene, so choose the stance for the whole scene, or start a new scene. Keep arms below the shoulder: an arm overhead tears a single-layer top.
- Don't film a thing from where it can't be seen: when a shot is on a person and something would block the lens, list `shows`.

## How the short fits together

Times are seconds of the whole short, and the voice comes first: the word times are below. For a number worth seeing, add `marks`, what's drawn over the picture: {"kind": "count", "from": s, "to": s, "start": 12000, "end": 40000, "text": "TIMES A SECOND", "at": [0.5, 0.42]} counts up, big and burning, on the short's clock. Write `scenes` in order, each with `from` and `to` (the first from 0, each starting where the last ended, the last ending at the short's end) and the scene language's `set`, `cast`, `happens` and `shots`. Every `t` is in the short's time, so a shot or a hit lands on its word by using that word's time. Use one scene for as long as one set and one stance will do. **Don't write `length` or `captions`:** code works out the length, and draws the captions from the voice.

<!-- user turn: new -->
The outline:

{outline}

The narration, line by line, with what each line shows and when each word is said:

{lines}

The short ends at {total} s.

Who's in it:

{people}

The things you have, with their sizes, moves and spots:

{things}

Body stances you can use for `stance`:

{stances}

The scene language:

{language}

Two worked examples, each a single scene in its own time (yours are in the short's time, and have `from` and `to` instead of `length`):

{example}

The owner's notes, if any:

{notes}

Direct it.

<!-- user turn: revise -->
The outline:

{outline}

The narration, line by line, with what each line shows and when each word is said:

{lines}

The short ends at {total} s.

Who's in it:

{people}

The things you have, with their sizes, moves and spots:

{things}

Body stances you can use for `stance`:

{stances}

The scene language:

{language}

Your last draft:

{previous}

What has to change, oldest first:

{notes}

Direct it again with those changes, and keep what they don't touch.

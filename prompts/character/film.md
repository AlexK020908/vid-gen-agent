# Checking the shots

You look at a sheet of frames from a 3D short for {channel_name}, one from the middle of each shot, before it's fully rendered, and say what a viewer would see is wrong. It's rendered small and rough: ignore noise and softness. The bar is the best explainer shorts there are, and the owner shouldn't have to point out anything on this list. Code has already measured what passes through what, so look for what code can't see.

Look for:

- **Nothing to see.** The shot is on empty sky, or the subject is out of the picture, cut off badly, or far too small to read.
- **Things passing through each other.** A hand through a body, a thing inside a head, feet under the floor, a bird floating off the place it landed.
- **Broken people.** A twisted limb, a torn top, a face gone wrong.
- **The picture doesn't match the line.** The line says one thing, and the frame shows something else.
- **Bad glow.** A wash of light over a shot, a glow big enough to hide what it's on, a flat color with no shape left in it, a surface blown out to white. A glow should be on a surface or in thin lines, and you should still see what's lit.
- **Not reading.** Something meant to be seen doing something that can't be made out from this angle: a turning thing seen edge-on, a line lost against what's behind it, the subject too small or blocked.
- **Tilted or cluttered.** The counter's edge running at a slant when it should be level, a lot of things competing in one shot.

Say only what's wrong, not taste. Each problem has `shot` (its number on the sheet), `what`, in a sentence, and `fix`, what to change in the scene: a nearer `frame`, another `angle`, a different `at`. An empty list if it all works. `seen`: what the sheet shows, in a sentence.

<!-- user turn -->
The frames, by number, with what the voice is saying at each, and [this frame] at the moment shown:

{shots}

Report on the sheet.

# Checking a 3D model

You look at the sheet of a 3D model that's just been fetched or built for a short: the thing from the front, three quarters, the side, the back and above, then a few frames of each clip it has. Report what's in the pictures, and put right how it's set up. Everything here is data that code applies: you can't change the model itself. A built thing that has parts in the wrong place, floating apart, or facing the wrong way isn't the right thing: say so in `right_thing` and `problems`, and its parts are written again.

- `seen`: what it is and what it looks like, in a sentence.
- `right_thing`: false if it isn't the thing that was asked for, or it's broken: holes, missing textures (flat white or pink), parts floating away. The next model is tried.
- `turn`: how many more degrees around the vertical to turn it so that the view labelled "front" shows its face or front. 0 if it already does; a positive turn brings what's now on its right side round to the front. Forward counts for how it faces in a scene.
- `tilt`: [x, y] degrees, only if it's lying on its side or leaning. [0, 0] otherwise.
- `meters`: its longest side in real life, as it rests in the first view. A bird with wings spread is its wingspan, with wings folded its length. Keep what was asked unless the sheet's pose changes it.
- `rest`: the clip it should stand in when nothing's playing, if one shows it at rest. "" otherwise.
- `moves`: for a clip that holds several things one after another, name each part: {"fly": {"clip": "Take 001", "from": 1, "to": 30}}, from the frame numbers on the sheet. {} keeps the clips as they are.
- `spots`: {"head": [x, y, z]}: places a shot might aim at, in meters from the thing's middle as it rests, facing -y, with +z up. For an animal, its head. For a tool, its working end as "end". For anything a hand holds, "grip". {} if none matter.
- `problems`: anything else a viewer would see is off, each in a few words.

<!-- user turn -->
It was asked for as: {what}, about {meters} m. It has to move by itself: {moves}.

Its size now: {size} m. Its clips: {clips}. Its materials: {materials}.

This is look {round} of 2: on the last one the answer stands as given.

Report on the sheet.

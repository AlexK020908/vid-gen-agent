# What a short needs

You're about to direct one vertical 3D short for {channel_name}. First say who and what has to be in it, so they can be got before you direct. You'll direct with exactly what comes back.

**People.** Use someone who's already made when they fit, since a recurring face helps a channel. Give their `id`, say who they play in `plays`, and leave `spec` as {}. If nobody fits, give a new id (lowercase, no spaces) and a character `spec` in the format below; it's checked against what's really installed. Invented people only. On a meme channel, the famous person is an invented face given their hair, clothes and things, never one made from photos of them. Most shorts need one person, and none needs more than three.

**Things.** Anything else in the picture: an animal, a tool, food, furniture. Use what's in the library, by its `id`, when it fits. Otherwise there are two ways to get it, and the choice matters to how the short looks:

- **Build anything simple and geometric,** to the millimeter: a magnet, a pan, a stand, a coil, a sign, an arrow, a hat, an appliance. It comes out far sharper and truer than a download, it can be exactly the shape and color the idea needs, and you know its size and where everything on it is. Give a new `id`, `what` it is, `parts` in the format below, `spots` for the places a shot or effect will use, in the same meters as its parts, and leave `search` as "" and `meters` as 0. Make it chunky and readable: it'll be seen close up, in a short, on a phone. Real proportions, rounded edges (`bevel`), plain strong colors. Anything with a liquid in it is built: what holds it in `clear_glass` so it shows, and the liquid as a part of its own, marked `liquid`, shaped as it is when full and a fraction of a millimeter inside the glass. The scene says how full it is.
- **Look up what can't be drawn:** food, animals, faces, anything organic. Give a new `id`, `what` it is in a few words, `search`, the one or two words to look it up by ("seagull", "raw steak"), `meters`, its longest side in real life, as it would rest (a bird with its wings spread is its wingspan), and `moves`, true if it has to move by itself, such as a bird that flaps. Leave `parts` as [] and `spots` as {}.

Ask only for what the picture truly needs: every extra thing costs time, and a few things held well look better than a crowded set. Don't ask for what's built in: those are listed below.

<!-- user turn -->
The outline:

{outline}

The narration, with what each line shows:

{lines}

The people already made:

{people}

The things in the library:

{things}

Built in, so never asked for: {built_in}

The character spec's format:

{character_format}

A built thing's parts, and the shapes they can be:

{thing_format}

The owner's notes, if any:

{notes}

Say who and what this short needs.

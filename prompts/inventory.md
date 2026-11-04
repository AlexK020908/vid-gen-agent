# Props and people

You prepare a narrated stick-figure story ({channel_name}: {scenario_family}) for animation by code. Each character is a puppet made from painted parts, and the things they use or build are props painted once and moved by code. Before the scenes are staged, the pipeline needs the list of props the script uses and how big each cast member is.

A prop is an object a scene shows being used, carried, placed or built: a steel plate, a drill, a towel, a rifle, a flashlight, a cot, a jerrycan. It is not a place, not furniture that is part of a place's own picture, not a person, not an animal, not a thing only mentioned in passing, and not part of someone's look: what a character wears or always carries (a cane, a knee brace, a cap, a jacket, body armor) is painted with their puppet, not as a prop. Each prop gets:

- `name`: one or two lowercase words, the same every time the script means it ("plate", "drill", "towel").
- `draw`: 10 to 25 words for the painter: the object alone, seen from the side or face on, its material and color, and for a tool, "its business end pointing to the right".
- `height`: how tall it is drawn against a standing adult, as a fraction of their height (a door-sized plate 1.1, a drill 0.17, a towel 0.1, a rifle seen from the side 0.14 tall and long).
- `stands`: `bottom` for something that stands on the floor (a plate, a cot, a can), `center` for something small that is held or lies (a towel, a wrench), `grip` for a tool held by its handle (a drill, a rifle, a flashlight).

A thing the story moves or uses somewhere else than the one place whose picture shows it is a prop, even though that picture shows it: a car in the garage's picture that is rolled down to the gate, a boat at the dock's picture that is rowed out. A place's picture shows it only in that place. So are vehicles that arrive or leave (a truck that rams the gate, a helicopter that lands), drawn from the side.

Reuse a prop from the list of ones already painted when the script means the same thing, with its exact name, and don't list it again. Keep the list to the props scenes actually show, usually 4 to 12.

`people`: every cast member from the outline with `scale`: their standing height against the main character's, 1.0 for an adult, about 0.6 for a child, 0.8 for a teenager.

<!-- user turn: script -->
The cast:
{cast}

The script, one scene per line (its place, the people in it, the line, what it shows, what it builds or changes):
{script}

Props already painted (reuse these names): {have}

List the props and the people.

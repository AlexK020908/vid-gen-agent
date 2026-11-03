You measure pictures for a cutout-animation pipeline that draws stick-figure people into painted places. Positions are percentages of the picture: x from 0 at the left edge to 100 at the right, y from 0 at the top to 100 at the bottom. Every picture you get has a red grid drawn over it with its lines labelled every 10, so read positions off the grid and be exact: a figure's feet go precisely where you say, and a figure drawn standing in the wrong place, floating above the floor or the wrong size for its depth looks absurd.

<!-- user turn: stage -->
Image 1 is "{name}", a place in the cartoon, seen from the fixed camera every scene there uses. Stick-figure people will be drawn standing in it, and the pipeline needs to know where they can stand and how big they are there.

Give `seen` first: one sentence saying what the picture shows and where the camera is.

Then `floor`: the walkable floor as 3 to 6 points from the nearest place anyone stands to the farthest (a person's size is read off them by how far down the picture the feet are, so they should cover every spot's depth), in the order a person would walk them, each with x, y (where the feet go) and `height`: how tall a standing adult would be at that point, as a percentage of the picture's height (nearer the camera is taller; judge it against the doors and furniture there). Points on a different level (a step up, a stair) belong to the floor only if people walk them.

Then `spots`: the places a person would stand at or things they would use, each named in a few lowercase words joined with underscores (door_left, stairs_top, window, table), with the x, y where feet go to be there and `what` it is in a few words. Include every door, the top and the bottom of every stairway that's in the picture, every window, and the main furniture.

Then `occluders`: solid things nearer the camera than the floor behind them, which a person standing behind would be partly hidden by (a table, a counter, a car, a sofa's back, a wall's near edge, an open door panel), each with a `name`, a `polygon` of 4 to 8 points around it, and `base_y`: the y where it meets the floor. Only solid shapes: never a banister, railing, fence, plant or anything with gaps, since the whole polygon is cut out and would hide people behind its gaps too. Leave the list empty when nothing in the picture is like that. A spot is where feet go to be seen, so no spot lies inside an occluder above its base: a person "at the door" stands in the doorway or beside an open door panel, never behind the panel.

Then `light`: the x, y of the main light source and `warm` true for a lamp, candle or fire, false for daylight or moonlight.

<!-- user turn: parts -->
Image 1 is a sheet of painted parts of a cartoon character, each separate blob inside a red box with a number. Which box holds each of these parts? {names}

Give `seen` first: what each numbered box holds, a few words each. Then `parts`: one entry per name above with the number of its box, 0 when that part isn't on the sheet at all, and `faces`: which way it is painted facing: `left` or `right` (a cap faces the way its visor points, a hand the way its thumb points, a tool the way its business end points, a scarf away from the way its tail hangs), or `front` when it is symmetrical or looks straight out of the picture.

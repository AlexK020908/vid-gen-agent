# Shorts: machines in 3D, systems in 2D

The plan for two new kinds of vertical shorts, built into Stick Fleet. BUILD.md tracks the phases as they're done; this file is their spec. The reference videos are in the workspace folder above this repo.

- **Machine shorts:** a narrated "how it works" short. A machine is built piece by piece in Blender, cut open, and animated. The references are `06908b699fc64aa89e18176103c474fa.mov` (the diesel pile hammer) and `589597173f524142ab9544d79a727e83.mov` (the house drain).
- **Systems shorts:** a tech concept drawn as a live diagram in Remotion, with traffic moving, counters, a code panel and an end card, usually without a voice. The reference is `ScreenRecording_11-03-2026 11-52-37_1.mov` (load balancing).

## What the references do

### Machine shorts

**A, the diesel pile hammer.** 1:58 at 24 fps, 720×1280, about 45 caption lines (2.6 s each).
- **The story invents the machine with you:**
  - "Pick up a hammer, and it goes right into the wood."
  - Scale it up: "It becomes a steel pile, tens of meters long, weighing dozens of tons."
  - The obvious idea fails: "Make the hammer a hundred times bigger? ✗ TOO HEAVY TO SWING."
  - The next idea: drop an iron block from a crane, and each strike drives the pile DEEPER. But hoisting it every time is ✗ TOO SLOW.
  - Split the block into a RAM and an ANVIL, with explosives between them, plus GUIDE RODS so it lands true. Loading explosives every time is ✗ TOO RISKY.
  - An idea borrowed from another machine: a car engine, shown in CUTAWAY. Gasoline works but needs an ignition system. Diesel self-ignites in hot, compressed air.
  - The working cycle in // SLOW MOTION: AIR compressed, DIESEL injected, IGNITE, PRESSURE, EXHAUST, RISE, the cycle repeats, ≈ 40 blows per minute.
  - The reveal: "You've just invented THE DIESEL PILE HAMMER."
  - It ends on real footage of one at work, credited "Wikimedia Commons, CC BY-SA 4.0".
- **The look:**
  - clean PBR 3D: an orange sand lot under a hazy sky HDRI, a fence and bridge in the distance, a lattice crane;
  - soft sun shadows and shallow depth of field;
  - safety yellow, blue-grey painted steel and yellow-black hazard stripes;
  - cutaways whose cut faces are orange with dark diagonal hatching, like an engineering section;
  - air as small blue-white balls that crowd together as the ram comes down;
  - the diesel spray, an ignition flash and a dark exhaust puff.
- **The overlays:**
  - the narration line as a caption: white sentence-case text in a dark rounded box, lower middle;
  - part labels: bold uppercase in yellow, white or red, with a thin leader line to a dot on the part, which follow the part as it moves;
  - red ✗ tags for failures;
  - a big ? when the story asks a question, and a ×6 multiplier;
  - "// SLOW MOTION" in the top left, and section tags ("CAR ENGINE · CUTAWAY", "EXPLODED VIEW");
  - a small stat line;
  - the title reveal at the end.

**B, the house drain.** 1:09 at 30 fps.
- **The story:** why a house's drain is built the way it is, one problem and fix at a time:
  - the pipe slopes 1/4 IN PER FT;
  - SEWER GAS floats up the drain;
  - a plug blocks it, then the P-TRAP holds water, but the trap goes dry;
  - the VENT STACK;
  - in a storm, sewage flows back, so a BACKWATER VALVE.
- **The look:**
  - a suburban yard whose ground is cut open to show the soil and the pipe, with a house, an excavator and a person standing in the yard;
  - a house cut open to show the sink, the toilet and a vent through the roof;
  - green gas bubbles, rain, orange flow arrows, and a "DAY 1" / "DAY 7" calendar tag.
- **The overlays:** one big word at a time in the middle of the screen (white with a dark outline), big yellow 3D-style labels, and small labels.

**C, the cow hoof.** Made with a video diffusion model, and the second half is an ad for an AI tool. It's not a target for the look. Its story shape (a problem, how it's fixed, healed) is one more shape the outline can use.

### Systems shorts

**D, load balancing.** About 18 s, then it loops seamlessly. The layout, top to bottom:
- **The header:**
  - the title in bold white caps ("HOW LOAD BALANCING WORKS");
  - a grey monospace subtitle that changes with the phase ("one server · all the traffic", then "one entry point · three identical servers");
  - stat pills: RESPONSE in ms, colored by how good it is (80, 200, 280, 400, then 173, 147, 107, 80, 40), and SERVERS 1, then 3, then 2.
- **The diagram:**
  - CLIENTS (green), LOAD BALANCER (blue) and Server 1 to 3 (orange), each a line icon;
  - blue dots run along the lines, and each server's counter goes up when one arrives;
  - waiting requests stack above the server ("Requests start piling up");
  - a dead server turns red, gets a cross, its line goes dashed, and its counter stops.
- **The caption:** one short line, colored by its tone: white for the setup, orange for trouble, blue for an action, green for good, red for a failure.
- **The code panel:**
  - an nginx `upstream backend { server app1; ... }` block;
  - the line of the server taking a request lights up as the request lands;
  - the dead server's line dims;
  - the block goes from 1 server to 3 when the balancer is added.
- **The end card:** "480 ms → 40 ms" (red to green), "one server down · still 40 ms", and a small grey note. Then it loops back to the first frame.
- **The sound:** no voice. There's music the whole way, and ticks when requests land.

The phone's own buttons and the post's caption cover the right side and the bottom of the screen (D is a screen recording, so they show). Everything we draw stays out of those areas.

## Decisions made

- **The same repo, in new folders.** The jobs in this chat, the critic and worker agents, the voice stage, the Remotion project, cards, topics, publishing and metrics are all reused. A fix to a shared stage reaches every channel.
  - `blender/` is the Python that runs inside Blender (`bpy`): the parts kit, the builder, the shot animator and the exporter.
    - It runs as `blender -b --factory-startup --python-exit-code 1 -P blender/run.py -- <job.json>` and talks to the app only through files: a job JSON in, frames and a tracks JSON out.
    - Blender has its own Python, so `blender/` imports nothing from the app.
    - Its pure checks are tested in the app's venv. Tests that need Blender are marked `blender` and skip without it, as the Remotion test does without `node_modules`.
  - `render/remotion/src/shorts/` holds the vertical compositions: `MachineShort` (the rendered clips with overlays) and `DiagramShort` (the whole systems short drawn in React). It's the same pinned Remotion project, with new composition ids.
  - `diagram/` is the systems shorts' simulation and checks, in Python.
- **A `format:` per channel:** `story` (today's videos, the default), `machine` or `diagram`. Each new format is its own channel, with its own YAML, YouTube channel, topics, competitors, voice and budget. The stages pick their work by format.
- **Claude never writes Blender Python or React.** In this chat Claude writes JSON (a model spec, a shot sheet per scene, a diagram spec), and fixed code reads it and checks it before anything renders, as the puppet sheets were. That means:
  - a bad spec is refused with the reasons, and never becomes a broken render;
  - nothing runs that Claude made up;
  - a re-render costs nothing;
  - a fix in the kit improves every video.

  The analysis you pasted has the LLM write the `bpy` script and the React components. This is the same blueprint with that one part made safer.
- **No API spend.** Every Claude step is a job in this chat, as today: the outline, script, model, shots, diagram spec, reviews and picture checks. The analysis's GPT-4o and Sonnet calls, and Whisper, aren't used, because ElevenLabs already gives word times with the voice.
- **Blender 5.2 LTS** (released July 14, 2026, supported until July 2028), as the portable zip in `tools/blender-5.2/` (gitignored), with `blender.path` in `stickfleet.yaml`. It renders with EEVEE on the RTX 5080 (16 GB).
- **1080×1920 at 30 fps** for both formats. The safe area keeps text out of the top 8%, the right 14% and the bottom 22%, the parts Shorts' and Reels' own buttons and captions cover.
- **Our own channel names, handle and look.** Their watermarks, names and wording are never copied.

## Decisions for you

My defaults are in brackets. None of these block phase 23.

1. **The narrator for machine shorts.** Open again (Nov 3, 2026). It has to sound engaging and enthusiastic and read a question as a question. The owner's clone, zach D, has the energy but reads questions flat (it was made from 30 seconds of speech); Ryan Wells, the zombie channel's calm narrator, came out bland on the rebuild. Decided (Nov 3, 2026): the clone, zach D, on `eleven_v4`, where its questions lift (each ending measured, a flat one retaken, since v4 varies from take to take). The owner on the read: "IT SOUNDS AMAZING". Phase 28 needs the voice model per channel, as the zombie channel stays on `eleven_multilingual_v2`. Systems shorts have no voice.
2. **Where they're posted.** [YouTube Shorts first: the upload code exists, and a vertical video under 3 minutes is a Short automatically. Instagram Reels in phase 30, which needs an Instagram Business account linked to a Facebook Page and a Meta developer app, set up on your side.]
3. **Channels.** Two new YouTube channels, or the shorts on an existing one? [Two new brand channels: the zombie audience isn't an engineering audience. You name them.]
4. **Music.** [SFX from Kenney's free CC0 packs (impacts, clanks, UI ticks), downloaded once. Music: a handful of loops you pick once from the YouTube Audio Library into `assets/music/` (each with its BPM noted, so systems shorts tick on the beat). Before posting to Instagram, check each track's license allows it.]
5. **Real footage at the end** (as A ends). [Yes, when Wikimedia Commons has a freely licensed clip of the real thing: credited on screen and in the description, and checked by the worker agent to show the right machine.]

## How a machine short is made

The video states don't change: `new` → `outlined` (outline card) → `outline_approved` → `scripted` (optional script card) → `generating` → `assembled` (render card) → `render_approved` → `publishing` → `scheduled` → `live`. An optional `model` gate (the model card) sits inside `generating`.

1. **Topic.** "How does X work" ideas, from competitors' Shorts (the topics stage gets `max_seconds` per channel, so it keeps Shorts instead of skipping them) and a topic job in this chat (`prompts/machine/topic.md`). A topic must be a built thing made of parts: machines, tools, building systems, plumbing, locks, engines, pumps. Anything that needs organic modelling, like the cow hoof, is out.
2. **Outline** (a job, then the critic agent as a practical engineer). It's the invention chain as fields, in the order the story needs them:
   - the everyday start;
   - the scale-up;
   - 4 to 8 steps, each with the attempt, why it fails (the red tag, at most 4 words), the fix, and the parts or change the fix adds;
   - optionally, an idea borrowed from another machine;
   - the working cycle's phases;
   - the reveal;
   - one real number;
   - a footage search.

   The checks in code: each failure has its tag; each fix adds a part or changes one; the last fix is the real mechanism; the reveal names the topic; the words fit 60 to 120 s. (Since phase 56 every short runs 30 to 40 s, with at most three rounds of problem and fix: BUILD.md, Short, and hooked all the way.)

   Shape B ("why your house has a P-trap", problem then fix with no invention) is the same fields without the start and scale-up.
3. **Script** (one job). Each problem hands over to its fix with a word that says so ("But...", "So...", "Then..."), and a question is written and read as one (the owner's note on A's rebuild, which reads as a list without them). Each line is a scene: at most about 15 words (a two-line caption box), with what the shot should show and its tags. Its length is checked at 155 words a minute.
4. **Voice.** The existing ElevenLabs stage, with word times. A channel gets its own `speed`. The picture follows the voice, never the reverse: lines are never sped up to fit, and every sentence has room to breathe after it, at least 0.5 s and about 0.9 s after a question or a problem. A read is trimmed to its speech and brought to about 16 characters a second, at most 1.15×, then leveled as one track (`narration.read()`, `narration.track()`). So a script is written to its length at this pace, plus the pauses.
5. **The model** (a job, then built by code). Claude writes the machine once per video in the parts kit (below), with its environment and props.
   - Every part says from which step it's there (`from_step`, `until_step`), so the machine grows as the story does: one iron block, then split into a ram and an anvil, then the cylinder, then the guide rods, then the injector.
   - Code builds it in Blender and checks:
     - every part the script names exists;
     - sizes are in real meters and plausible;
     - no part passes through another at any joint position (Blender's BVH overlap test, sampled across each joint's range);
     - the cutaway shows the parts the steps need.
   - Then it renders a turnaround sheet: 4 angles, whole and cut open, with each joint at both ends. The worker agent checks it ("is this a diesel pile hammer: a ram above an anvil inside a cylinder, guide rods either side?"). With the `model` gate on, you see the sheet before any shot is rendered.
6. **Shots** (a job per scene, in order, by the worker agent, like the puppet sheets). Phase 23 showed the shot checks must also catch a label covering its own part, and a camera looking down into a cutaway whose moving part hides what's labelled. Each sheet sets:
   - **The camera:** the parts to frame; close, medium or wide; the angle; and the move (push in, pull out, orbit, track a part, tilt up, hold). It can start where the last shot ended, so a run of scenes plays as one continuous take, as A's does.
   - **The machine:** which step it's at, the cutaway (off, on, or sliding open), and an exploded view.
   - **Joint moves timed to words** ("the ram drops on 'slams'").
   - **Effects, callouts and tags** (below).
   - **Slow motion:** the machine runs at a fraction of real time.

   The machine's state carries from one scene to the next unless a sheet changes it. The checks in code:
   - the framed parts sit inside the safe area and fill 25 to 70% of the frame's height;
   - every callout's point is visible for as long as it's shown (a ray from the camera that no other part blocks);
   - callouts don't overlap each other or the caption;
   - every word a move is timed to is in the line;
   - the camera is never inside anything;
   - joints stay in range.
7. **Render** (code, $0). Each scene is rendered by Blender (EEVEE, GPU) to frames, then encoded to a clip with `tracks.json`: each callout's place on screen in every frame, and each event's frame (impact, ignition, a scene cut). It's cached by a hash of the model, the shot and the words, so a fixed shot renders only itself.
8. **The look check** (worker jobs). The start, middle and end frame of each scene, with the overlays drawn on (a Remotion still). The checks:
   - does it show what the line says;
   - is any label wrong or covered;
   - does any part clip through another.

   A frame that fails is shot again once, with what was wrong, as the stills are now.
9. **Assemble** (Remotion `MachineShort`):
   - the clips in order, with the overlays placed from the tracks and the captions;
   - the voice, SFX on the events, and music ducked under the voice;
   - at the end, the title reveal, then the real footage and its credit.

   The render card in this chat has the MP4 and a frame sheet. Flagging a scene shoots only that scene again.
10. **Publish.** A YouTube Short:
    - a title, a description (with the footage credit) and tags, and no custom thumbnail (Shorts show a frame);
    - category 27, Education, or 28, Science & Technology;
    - a list of `publish_slot`s, so it can post several a week.

    Metrics work as today.

### The parts kit (`blender/kit/`)

Sizes are in meters. A part has an `id`, a `kind` with its sizes, a `material`, `at`, `rot` and `parent`, an optional `joint`, `from_step` and `until_step`, and `cut` (whether the section cuts it; A's ram stays whole inside its cut-open cylinder). It can also have a default label.

- **Shapes:** box, cylinder, tube (hollow, with a wall), cone, sphere, torus, plate (with holes), rod, beam (an I or H section) and wedge.
- **From a profile:**
  - `lathe` turns a list of (radius, height) points into a solid: pistons, nozzles, valves, bottles, bells;
  - `extrude` lifts a 2D outline into a plate: brackets, cams, levers;
  - `sweep` runs a circle or rectangle along a path: pipes, hoses, rails, cables.

  With booleans between parts, these cover most mechanical shapes.
- **Generators:**
  - `pipe_run` (points, elbows, tees, a P-trap, valves);
  - `gear` (teeth and module; two gears mesh at their ratio);
  - `spring` (a helix that squashes with its joint);
  - `truss` (a lattice boom for cranes and towers);
  - `chain` and `cable`, `thread` (a screw), `fan`, `wheel` and `hook`.
- **Stock props:** whole things the story shows but doesn't open, by name, from free CC0 libraries downloaded once into `data/assets/`:
  - Poly Haven (models, HDRIs and textures, through its public API);
  - Kenney and Quaternius packs (low-poly props, and a rigged person who can stand, point and walk).

  A one-off prop no library has can be made from a picture with one of fal's image-to-3D models. That's an optional later step, priced and asked about first.
- **Materials** (fixed names, each one shader): steel, dark_steel (A's blue-grey pile), safety_yellow, hazard_stripes, rubber, copper, brass, cast_iron, aluminium, chrome, glass, clear_plastic, white_plastic, pvc, ceramic, wood, concrete, brick, soil, sand, grass, water, oil, and `cut` (the orange section face with dark diagonal hatching).
- **Joints:**
  - `slide` (an axis and its range), `hinge` (an axis and its range) and `spin`;
  - couplings: `gear` (a to b at a ratio), `crank` (crank, rod and slider, solved exactly), `follow` and `spring`.

  A shot only ever sets joint values, and every position follows from them, so the mechanics stay true: A's ram stays on its rails.
- **Cutaway:** a section plane with `keep: back`. It's a boolean whose cutter carries the `cut` material, so the cut faces come out hatched. It can slide in during a shot.
- **Effects** are animated by code, not simulated, so a render is the same every time:
  - `particles` in a part's inside: air, fuel or gas, drifting, crowding as the space shrinks, or bursting;
  - `spray` from a nozzle, a `flash` (an ignition light and bloom), and `heat` (a part glowing);
  - `smoke` (a soft puff that grows and fades);
  - `flow` along a pipe run (water, waste or gas, either way);
  - `rain`, and `dust` on an impact;
  - `ghost` (a part made see-through) and `highlight` (a rim glow while its label shows);
  - `scale_up` (growing ×N), and `exploded` (parts moving apart along their joints).
- **Environments:** each is built by a script from CC0 HDRIs and textures:
  - `desert_lot` (A's sand lot, with a crane in the distance);
  - `yard_cutaway` (B's lawn over a soil section, with a house and a fence);
  - `room_cutaway` (B's sink and toilet);
  - `workbench` (A's opening: a wood table in a dark room, under a warm lamp);
  - `studio` (a soft grey sweep);
  - `black` (A's car engine shot).

### Overlays and sound (`render/remotion/src/shorts/`)

- **Captions,** set per channel:
  - `box` is A's: sentence case, white in a dark rounded box, just above the platform's caption area;
  - `word` is B's: one word at a time, big, white with a dark outline, in the middle.
- **Callouts:** a bold uppercase label in its tone's color, with a leader line to a dot on the part. It pops in on its word, follows the part, and leaves on cue.
- **Tags:**
  - fail (red ✗), ok (green ✓), warn (⚠), question (a big ?), multiplier (×100);
  - section ("CAR ENGINE · CUTAWAY"), mode ("// SLOW MOTION"), stat ("≈ 40 blows per minute"), day (a "DAY 7" calendar);
  - the title reveal.
- **The channel's handle,** small, at the middle right.
- **Sound:** SFX on the tracks' events (a clank on an impact, a thump on ignition, a tick when a label pops, a whoosh on a cut), and music 12 dB under the voice.

## How a systems short is made

A systems short is 15 to 45 s, with no voice by default, so it costs $0: there's no voice and no fal.

Built in phase 30 (Nov 9, 2026); BUILD.md's "How a systems short is made" says how. It differs from this plan in four ways:
- Topics come from the tech ideas the owner takes (prompts/ideas/tech.md), not a topic job.
- The look check is one sheet, a frame from the middle of each phase, for the worker agent.
- The diagram, title and pills use the full width above Reels' buttons.
- Narration isn't built.

1. **Topic** (a job): from competitors' Shorts and a starter list (load balancing, caching, CDN, rate limiting, consistent hashing, replication, sharding, queues, circuit breakers, retries with backoff, DNS, the TLS handshake, OAuth, JWT, WebSockets, idempotency keys, blue/green deploys, Bloom filters, LRU).
2. **Spec** (a job; the critic agent reads it as a senior engineer who checks it's correct). It has:
   - the title, and a subtitle per phase;
   - **stats:** each with a name, a unit, a value per phase (or worked out from the traffic) and a tone;
   - **nodes,** from a fixed icon set: client, users, browser, phone, dns, cdn, api_gateway, load_balancer, server, function, worker, queue, cache, database, replica, storage, auth and region;
   - **a layout,** from fixed templates: pipeline, fan_out, fan_in, hub, layers, ring and grid. Claude picks the template and the order; code places everything;
   - **edges;**
   - **phases,** each with:
     - its length, and a caption with its tone;
     - each node's state (healthy, busy, warning, dead, cold);
     - the traffic: a rate, and a route (direct, round_robin, least_connections, hash, failover, cache_hit with a ratio, broadcast, retry_backoff);
     - events (a node killed, added or scaled up);
   - **the code panel:** the language, its lines, and which line lights up when traffic reaches which node;
   - **the end card:** a before and after number, a one-line claim and a small note.

   The last phase leads back to the first, so the short loops.
3. **Simulation** (`diagram/sim.py`, the one source of truth):
   - requests start on the music's beat, are routed by the policy, and travel the edges at a fixed speed;
   - every counter, queue and worked-out stat comes from them, so the numbers always agree with what's on screen;
   - it writes `timeline.json`, and Remotion only draws it;
   - the SFX cues come from the same timeline.
4. **The checks in code:**
   - the graph is whole;
   - every phase changes something;
   - captions are at most 6 words, and code lines at most 32 characters (the panel's width);
   - line bindings name real nodes;
   - nothing overlaps, and everything is inside the safe area;
   - it's 15 to 45 s, and the loop closes.
5. **The look check** (worker jobs): a Remotion still from the middle of each phase. Is it readable, does anything overlap, is the story clear with the sound off?
6. **Assemble** (Remotion `DiagramShort`):
   - a dark background, the title, the subtitle and the pills;
   - the diagram, the caption, the code panel and the end card;
   - a soft tick for each request that lands (pitched by node), a buzz when a node dies, a chime on the end card, and the music loop.
7. **Narration later,** if you want it (`narrator: on`): the voice comes first, and the phases are timed to its words.

## What changes for every format

- `format` in the channel YAML and `core/config.py` `Channel`. Each stage says which formats it runs for; `story` behaves exactly as today.
- Render settings per format (size, fps, safe area), and a Shorts publishing profile (no thumbnail upload, the credit in the description, the category).
- Topics: `max_seconds` for Shorts competitors, and Shorts ranked by views per day.
- Several publish slots a week per channel.
- Cards and `review`:
  - the outline card shows the chain;
  - the render card shows the vertical MP4 and a frame sheet;
  - the model card shows the turnaround sheet.
- **Costs:**
  - a machine short is about $0.15 to $0.35 of voice; the render is $0;
  - a systems short is $0;
  - your Claude plan does the writing and the looking, as now.

## Phases

The riskiest thing goes first: whether Blender can reach A's look at all. The puppets taught that: a whole pipeline was built before the look was judged, and the look was what failed. Each phase ends with BUILD.md updated and a stop, so you can compact.

| Phase | Scope | Done when | Spend |
| --- | --- | --- | --- |
| 23. Blender look test | Blender 5.2 LTS installed (portable), `blender/run.py`, the materials (with the hatched cut), the `workbench` and `desert_lot` environments, EEVEE tuned. Three shots of A's opening built by hand: the nail on the bench, the steel pile on the lot, and the cut-open block and anvil with the air balls. A box caption, a callout and a ✗ tag drawn on them by a first Remotion overlay, and each laid beside A's frame. Seconds a frame measured | **You** look at the side-by-sides and say whether it's close enough to build on | $0 |
| 24. A's storyboard | A broken down beat by beat, with nothing built yet: the narration's word times (local Whisper, free), each caption as shown, and what's on screen in each beat (parts and their state, the camera and its move, cutaways, effects, labels, tags, cuts). Written as `storyboard.json` and `.md` in `data/benchmarks/pile_hammer/` | The storyboard covers all 1:58 of A | $0 |
| 25. The kit and A's models | Shapes, profiles, generators, materials, joints and couplings, the cutaway, step-by-step parts; the model checks (names, sizes, the overlap test, the cutaway); the turnaround sheet. Every model A shows: the nail and hammer; the steel pile and its soil layers; the crane; the giant hammer; the iron block, split into ram and anvil, then the cylinder, explosives, guide rods, injector and fuel tank; the gasoline can; the four-cylinder car engine cut open. Later, the `model` job, the worker's check of the sheet and the `model` gate | All of A's models build, pass their checks, and their turnarounds look right to you | $0 |
| 26. A's shots | The shot sheet; camera framing and moves; A's one continuous take with its two cuts; joints timed to A's word times; the effects (air, the diesel spray, ignition, explosions, exhaust, dust); slow motion; the tracks export; the render cache; the shot checks. Every beat of A as a sheet | All of A renders from sheets and passes its checks | $0 |
| 27. A's overlays and sound, side by side | `MachineShort`: A's captions, the labels on their tracks, every tag (✗, ?, ×100, SLOW MOTION, the section tags), the title reveal; SFX on events and a music bed; the real-footage ending (the same Wikimedia Commons clip, its license read, the credit). Then ours beside A, playing A's audio, for every second. Optionally our own narration (about $0.30 of ElevenLabs, asked first) | **You** watch the side by side | $0 |
| 28. Formats and the vertical short | `format` per channel; stages chosen by format; the 1080×1920 Remotion profile; Shorts publishing; `max_seconds` for topics; publish slots; a stub `machine` channel and a stub `diagram` channel running end to end to the render card | `pytest` green, and the zombie channel unchanged | $0 |
| 29. Writing machine shorts | The `model` and shot-sheet jobs for this chat, with A's rebuild as their worked example; the topic, outline, script and critic prompts and their checks, through to a real short on a new topic | One real short, made in this chat end to end: voice about $0.25, asked first | ~$0.25 |
| 30. Systems shorts | The spec, `diagram/sim.py`, the layout templates, the `DiagramShort` components (icons, edges, requests, counters, queues, pills, a code panel with Prism highlighting, toned captions, the end card, the loop), ticks on the beat, the checks, the jobs, Remotion's agent skills. One real load-balancing short, compared frame by frame with D | You compare it with D | $0 |
| 31. Instagram Reels | Your turn first: an Instagram Business account, a Facebook Page and a Meta app. Then the resumable Reels upload, publish and status, Reels metrics, and posting to both per channel. To check then: one guide says Reels over 90 s can't be posted through the API (A is 1:58) | One Reel posted | $0 |

**Rebuilding A (phases 24 to 27)** was the owner's call after the look test (Nov 3, 2026): "can we try to reproduce the video exactly?"
- It's the acceptance test for the kit: if the kit can remake A second for second, it can make our own shorts.
- **Exactly means:**
  - the same timeline (every narration word at the same second);
  - the same beats, camera path and cuts;
  - the same parts, cutaways, effects, labels and tags.

  It's judged as a side by side, ours beside A, playing A's own audio.
- **It's never published.** A's script and shot design are @abiodun_studio's work, and Content ID would match its audio. A's transcript, frames, storyboard and the rebuild's shot sheets and captions stay in `data/benchmarks/pile_hammer/` (gitignored). What's committed is ours: the kit, the overlay and sound code, and the generic models of the machines.
- The shorts we publish use our own scripts on our own topics (phase 29).

Phase 22 in BUILD.md ("the shorts look") is folded into 23, 27 and 30.

Systems shorts (phase 30) depend only on phase 28. If you'd rather have something posting sooner, they can go right after it, for $0 a video.

## What could go wrong

- **Claude's 3D sense.** A model spec can have wrong proportions or misplaced parts. Each model is made once and used in every shot, so the checking goes there: code checks, the turnaround sheet, the worker's look, your gate, and three hand-built machines in the prompt as examples.
- **Render time.** Measured in phase 23: 0.33 to 0.43 s a frame at 1080×1920 and 32 samples on the RTX 5080, with motion blur, so a 90 s short (2,700 frames) takes about 15 to 20 minutes. If that's ever too slow: fewer samples, then 24 fps (A's rate), then half-resolution shadows.
- **EEVEE without a window on Windows.** Confirmed working in phase 23, on the NVIDIA GPU.
- **Topics that won't fit the kit.** Organic things (bodies, animals, plants) are refused at a machine short's topic step; people have their own format, in [CHARACTERS.md](CHARACTERS.md). The kit grows when a good topic needs a new shape, and every channel's videos get it.
- **Licenses.** Poly Haven, Kenney and Quaternius are CC0. Wikimedia footage needs its license read and credited, and the code refuses anything with a no-derivatives or non-commercial license. Remotion is free for individuals and companies of up to 3 people.

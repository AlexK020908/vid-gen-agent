# Character shorts: people in Blender

The plan for adding 3D people to the Blender line: a character made on demand, performing in a narrated vertical short. BUILD.md tracks the phases as they're done; this file is their spec. It builds on [SHORTS.md](SHORTS.md), and only what differs is here.

The look to judge against is the owner's frame, `data/benchmarks/character_look/reference.png` (gitignored): a head-and-shoulders close-up of a stylized, realistic man with a prop in his mouth, in a clean sky-blue set. It's the target for the kind of figure, not something to copy: the character and its branding are another creator's.

## The tool: Human Generator Ultimate

The owner asked for a paid tool that makes characters on demand and gets them into Blender (Nov 3, 2026), then asked for research on the best option rather than trials. **The research points to Human Generator for making people on demand by code, and the owner agreed (Nov 3, 2026).** No published head-to-head of the look was found, so MetaHuman may well look better in a close-up. Prices below were read that day.

Only `blender/humgen.py` and `render/humgen.py` are tied to Human Generator. `blender/people.py`, the set, the lights and the shot work on any saved rigged person with a `person.json`.

| Tool | Cost | Verdict |
| --- | --- | --- |
| **Human Generator Ultimate** | $68 once (Personal) or $128 (Commercial) | **Recommended; look unjudged.** It runs inside Blender with a Python API, so no import step and no cost per character. A review praises the characters but finds bulk ones too alike and base clothing limited |
| Character Creator 5 | $299 to $479 once | Strong characters and a maintained Blender add-on, but Reallusion's staff said no Python API was planned, and a request for one was still open in Dec 2024, so people are made by hand |
| MetaHuman with Character DNA | Free under $1M revenue, or $79 for Pro | Probably the best close-up, and scriptable in Unreal 5.8. But it needs Unreal as well, nothing confirms hair and clothing come across to Blender cleanly, and Epic's license page needs a login, so its limits weren't read |
| AI video on fal | About $1 per 8 s clip | Not a character tool: less control over timing, and third-party reports of filters blocking violence, which may catch injury topics |
| Avatar SDK Cloud API | $800 a month | The API fits, the price doesn't |
| KeenFace | About €15 a head | A head only |
| Meshy rigging on fal | $0.20 a rig | Rigs a body you already have; it doesn't make the person |

**The license:** the Personal tier ($68) covers public YouTube and Vimeo videos, but its table says no to commercial renders and animations, and Reels aren't named. Its FAQ says a commercial license isn't needed when public YouTube or Vimeo videos are the only commercial activity, so Personal looks enough while we post only to YouTube. Commercial covers the rest, and moving up later costs only the difference. Models and textures can't be shared or sold, even customized, so they stay out of git.

**Read in the add-on's source (v4.0.38, Oct 17, 2026), not yet run:**
- `Human.from_preset()` makes a person, and `human.as_dict()` writes one out as data. Body, face, skin, hair, clothing, age, height, eyes, pose and expression each have their own settings.
- `human.expression.load_facial_rig()` adds a face rig: bones such as `eye_blink_open_L`, `jaw_open_lt_rt_frwd`, `mouth_smile_frown_L`, `mouth_lt_rt_funnel` and `brow_inner_up`, each driving shape keys. The add-on's own tests load through `blender -b`.
- `human.animation.set()` plays clips from its library, retargeted to the rig, and `import_mixamo()` adds Mixamo clips to it.
- Hair is particle hair, with hair cards as an option. The code has Blender 5 branches, and the store lists Blender 3.6 to 5.2.

**Not known until phase 32:**
- Whether it loads under `--factory-startup` with no window: its docs don't mention this, and they call the API "still in development".
- How its skin and hair look under our EEVEE settings, and how long a frame takes.
- Whether a saved character renders without the add-on.

## How it fits

- **Claude still never writes Blender Python.** Claude writes JSON (a character spec, a shot sheet), and fixed code checks it and runs it, as with machines.
- **A character is made once, then reused.** `blender/people.py` runs the add-on from the spec and saves `data/characters/<id>.blend`. Renders append that file, so they should keep running with `--factory-startup` and without the add-on. Only the spec is committed.
- **The add-on stays pinned.** The zip and content packs live in `human_packs/` (gitignored), and it never updates itself.
- **Invented people only.** A spec never aims at a real person's likeness, or at another creator's character, name or logo.
- **The rest is reused:** segments, cameras, tracks, the render cache, `MachineShort` overlays, voice, cards, jobs and publishing.

## How a character short is made

1. **Topic, outline, script** (jobs, then the critic agent). New prompts for `format: character`, with the same pacing rules as machine shorts.
2. **Cast** (a job). A character spec per person: a starting preset, gender, age, height, body, face, skin, eyes, hair and its color, and outfit.
   - Code checks every name against the real option lists, written out by Blender.
   - It builds the person and renders a portrait sheet: the face from three sides, the full body, and a few expressions.
   - The worker agent looks at it. With the `character` gate on, the owner sees it before any shot.
3. **Voice.** The existing stage, with word times. The picture follows the voice.
4. **Shots** (a job per scene). A sheet adds to today's timeline, under `people`:
   - **Body:** a pose or a library clip, where they stand, and which way they face.
   - **Face:** expressions timed to words ("eyes widen on 'sword'"), head turns and gaze. Blinks are added by code, at natural intervals, so nobody writes them.
   - **Props:** held in a hand or placed at the mouth, attached to a bone, so they move with the person.
   - **Lip sync,** only when the person speaks on screen: mouth shapes worked out from the word times by code.

   The checks: names are real, values are in range, the face is in frame and not blocked, and every timed word is in the line.
5. **Render.** The existing segment path, with its tracks and cache.
6. **Look check** (worker jobs). Start, middle and end frames: does it show the line, is the face broken, does a hand or prop pass through the body?
7. **Assemble and publish.** `MachineShort`, then the Shorts profile from phase 28.

There's no cloth or hair simulation at first: clothes follow the rig and hair stays still. It suits close-ups, and it looks stiff on a slow walk, though at a run, with motion blur, it holds up (phase 40). A body move, such as swinging a sword or going down in a fall, is a clip from a free CC0 pack in `data/motion/`, retargeted onto our rig, and looks only as good as that clip. Walking and running take their steps from the clip and their travel from the rig, so feet don't slide: BUILD.md, How it moves. The add-on bought here has no animation library of its own. A single-layer top tears at the shoulder with the arm overhead, so action shots need a layered outfit.

## Phases

The riskiest thing goes first, as with the machines: the puppets failed on look after a whole pipeline had been built. Each phase ends with BUILD.md updated and a stop.

| Phase | Scope | Done when | Spend |
| --- | --- | --- | --- |
| 32. Character look test | The add-on in `human_packs/`, loading with no window. One person built by a script, with hair, outfit and face rig. One 3 to 5 s head-and-shoulders shot on a blue set with a blink, an eye move, the jaw opening and a prop. EEVEE tuned for skin and hair, and tried against Cycles if the skin looks waxy. Seconds a frame measured. Laid beside the reference | **You** look at the clip and say whether it's close enough to build on | $128, the add-on (paid Nov 3, 2026) |
| 33. Characters on demand | The character spec and its checks, the option lists, `blender/people.py`, the saved `.blend`, the portrait sheet, and appending into a segment with the add-on off. Three different people, for a range | Three people build from JSON, and you like their portrait sheets | $0 |
| 34. The scene language | One JSON format the agent directs in, stageable by fixed code, with the contacts and physics worked out. The sword test remade from it, and a new scene with no new code | You watch the new scene | $0 |
| 35. Getting things | Anything a scene needs that we don't have, such as a bird: Poly Haven, Sketchfab, free packs, then a generated 3D model, kept for reuse. One bird scene with no new code | You watch the bird | $0 so far; a generated model is $0.375, asked first |
| 28. Formats (already planned) | `format` per channel, stages by format, 1080x1920, Shorts publishing, with `character` added beside `machine` and `diagram` | `pytest` green, and the zombie channel unchanged | $0 |
| 36. The director | The jobs where the agent turns any topic into a script, a cast and scenes in that language, picks what to source, and is checked by the critic and look checks; the `character` gate | A stub channel runs end to end to the render card | $0 |
| 37. One real short | One short on our own topic, made in this chat end to end, with no code for that video | You watch it | About $0.25 of voice, asked first; it came to $0.096 |

| 38. Precision | The owner's standard after the `pan.mov` test: exact things from data, placement by contact, a real spin, glow only on surfaces and in thin lines, a level camera, and refusals when a scene isn't physically right. BUILD.md, The owner's standard, has it | The owner watches the rebuild | $0; the voice from the first cut was reused |

Phases 29 to 31 don't depend on these. Phase 36 shares its job plumbing with phase 29, so whichever comes first builds it.

## Decisions for you

My defaults are in brackets. None of these block phase 32.

1. **The tool.** Decided (Nov 3, 2026): Human Generator Ultimate, and the owner bought the Commercial license ($128). The store's add-on zip is v4.0.29, older than the v4.0.38 source this plan read, and it was uploaded before Blender 5.2. [MetaHuman only if the look test fails on the face. Character Creator only if a small cast made by hand is acceptable.]
2. **What the shorts are about.** [Short "what if" and "how the body works" facts, one person per short. Injury topics need checking against YouTube's graphic-content rules before the first one.]
3. **The channel.** [A new channel of its own, as with the machine shorts.]
4. **The cast.** [One recurring lead, plus extras made as needed.]

## What could go wrong

- **YouTube's rules.** Since July 16, 2026, channels with too much "off-putting" content, or too much repetitive AI, CGI or template content, can't monetize, whether or not it's AI-made. Injury topics may count, though the reporting doesn't name them, so read the policy before choosing topics.
- **The look.** Faces in close-up are where 3D goes wrong most visibly, and the presets may read as realistic rather than the reference's slightly cartoon look. The add-on has cartoon body settings; phase 32 tries them. If the face fails, stop there.
- **The add-on under our setup.** It may need fixes to run with no window. Its code is open (GPL), so the problem can be read and worked around in our own script, and its content is never touched.
- **Render time.** Skin and hair cost more than painted steel. Machines take 0.4 to 0.5 s a frame on EEVEE. If it takes Cycles to look right, a frame could cost many times that; it isn't measured yet, and shorter shots or lower samples are the first answers.
- **Acting.** A shot sheet can time an expression, but it won't direct a performance. The format should lean on held reactions and short moves, not long acting.
- **Disk.** The content packs need at least 2.5 GB, on top of a saved file per character.
- **Selling this as a product.** This plan is for our own channels. The add-on's license is for one user and forbids sharing models. Its Commercial tier names software and games where the assets can't be extracted, but not a service that makes characters for customers, so ask its makers first if the line ever serves other people.

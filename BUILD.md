# Build log

The spec is [../plan.md](../plan.md). This file tracks what is built, how it deviates from the plan, and what comes next. Update it at the end of every phase.

## Status

| Phase | Scope | Status |
| --- | --- | --- |
| 1. Core | db, engine, stub providers, all 10 stages, ffmpeg render, actions, cards, CLI, tests | **Done** (Oct 29, 2026) |
| 2. Server + chat UI | FastAPI (REST + websocket), React/Vite chat with cards and buttons; works without the agent | **Done** (Oct 29, 2026) |
| 3. Chat agent | Claude Agent SDK harness, tools, confirm cards, path guard, session resume, gate comments | **Done** (Oct 29, 2026) |
| 4. Remotion + YouTube | Remotion Ken Burns render + benchmark, OAuth desktop flow + keyring, day-1 unlisted test upload, live publish | **Done** (Oct 29, 2026) |
| 5. Claude outline + script | Real outline and script stages with `prompts/`, per-provider live/stub switch (plan.md week 1) | **Done** (Oct 29, 2026) |
| 6. Real voice + stills | ElevenLabs voice with word timestamps, fal.ai stills with the character reference (plan.md weeks 1–2) | **Done** (Oct 29, 2026) |
| 7. Real hero clips | fal image-to-video for `motion: clip` scenes from each scene's own still, thumbnail text, budget held for running calls (plan.md week 2) | **Done** (Oct 29, 2026) |
| 8. Topics + metrics | Competitor check and ranking, Claude's topic ideas as cards, the weekly cadence, 48 h / 7 d metrics with the reach report (plan.md week 3) | **Done** (Oct 29, 2026) |
| 9. Own-data loop | Verdicts against the channel's medians, follow-ups for winners, family holds for losers, own-data topic ranking, thumbnail/title swap cards, daily sign-in check (plan.md week 7 on) | **Done** (Oct 29, 2026) |
| 10. YouTube tools + new channels | YouTube read and write tools for the chat (comments, live metadata, privacy, branding), each write behind Claude Code's permission prompt, and adding channels 2–5 | Optional, not started |
| 11. Continuity | Story bible (backstory, cast threads, tracked supplies), places and moves checked in code, reference pictures for every place and cast member with set changes carried forward, the day-and-supplies box on screen. From the first real video's review | **Done** (Oct 31, 2026) |
| 12. Picture checks | Stills drawn in order with the picture before as a reference, every picture looked at by a vision model and redrawn once with what was wrong, looks sent to the animator only for people in the picture, "1 day" in the corner box. From video 3's review | **Done** (Oct 31, 2026) |
| 13. Puppets | Phase 1 of the cutout pipeline: the main character's parts painted once by fal on a green sheet and cut out, a stick-figure rig with poses and a limp cycle, a place mapped into a stage (floor, heights, spots, light), a scene sheet rendered by code with shadow, night light and camera moves, over the real narration | **Phase 1 done** (Nov 1, 2026) |
| 14. Puppets, phase 2 | Props painted once and placed at spots or attached to a joint (a drill in a hand, a towel on a knee), set state carried from scene to scene (the plate stays across the stairs), a second, smaller puppet (Eli), parts that know which way they face, foreground cutouts people stand behind | **Done** (Nov 1, 2026) |
| 15. Puppets, phase 3 | The puppet pictures wired into the pipeline behind `render.pictures: puppet`: an assets stage (places mapped, puppets and props painted once), a sheets stage (Claude stages each scene in order, checked in code against the stage, set state carried forward) and an animate stage (every scene a clip drawn by code); a stub video runs end to end | **Done; live-staged on 3 scenes** (Nov 1, 2026) |
| 16. The reviewer | Every outline and script is read once by Claude as the toughest viewer (would a sensible person do this, could it be done, does it take the time it takes, rules, days, threads, real skills) and rewritten once with its fixes before the owner sees it; the thread says what was fixed | **Done** (Nov 1, 2026) |
| 17. MCP endpoint and jobs | `run.py serve` serves MCP at `/mcp` for the Claude Code session: today's tools, `wait`, `contact_sheet`, and Claude jobs (a stage that needs Claude parks until the session answers), wired for titles first | **Done** (Nov 2, 2026) |
| 18. The chat replaces the browser | Every card action is an MCP tool in the Claude Code chat: approve, publish, swaps, YouTube sign-in, `review` (the waiting card in full, with pictures and file paths), `news`. Anything that spends money or changes YouTube goes through Claude Code's permission prompt. The browser UI, REST API, websocket, in-app chat agent and card comments are deleted | **Done** (Nov 2, 2026) |
| 19. The session writes | Outline, script (in parts, each checked as it arrives), the reviewer (the `critic` agent), flagged-scene rewrites and topic ideas are jobs this chat does; the `stickfleet` skill, the `critic` agent, and the viral-hooks skill with its checklist in the shared outline prompt | **Done** (Nov 2, 2026) |
| 20. The session looks; the API is gone | Puppet assets (place maps, part names, the props list), scene sheets and picture checks are jobs for the `worker` agent; a stage that parks on one never pays fal twice; the API code path, the `anthropic` package, the `claude:` config, `ANTHROPIC_API_KEY` and the live Claude tests deleted | **Done** (Nov 2, 2026) |
| 21. Staging the story | From video 5's render review: people and things outside a gate drawn outside it (see-through occluders, spots beyond them), crowds of the dead and strangers on screen, a cast member who turns drawn as one of the dead, riding inside vehicles and hovering, props the story moves listed, and `restage` to make a finished video's pictures again | **Built** (Nov 2, 2026); puppets then put on hold for painted stills |
| 22. The shorts look | Remotion skills and label and arrow overlays for vertical explainer shorts (the hooks half came in phase 19) | Folded into phases 23, 27 and 30 |
| 23. Blender look test | Blender 5.2 LTS, the materials and two environments, three of reference A's opening shots built by hand with a first overlay, laid beside A's frames; seconds a frame measured. Spec: [SHORTS.md](SHORTS.md) | **Done** (Nov 3, 2026); the nail shot rebuilt after the owner's review, then the look approved ("ok looks good") |
| 24. A's storyboard | Reference A broken down beat by beat (word times from local Whisper, captions, parts, camera, cutaways, effects, labels, tags) into `data/benchmarks/pile_hammer/` | **Done** (Nov 3, 2026): 64 beats, 30 models |
| 25. The kit and A's models | The Blender parts kit, joints, cutaways, the model spec and its checks, the turnaround sheet; every machine A shows | **Built** (Nov 3, 2026): 6 machines, all collision-free; waiting on the owner's look at the sheets |
| 26. A's shots | Shot sheets for all of A: the continuous camera, joints timed to A's word times, effects, tracks, render cache, shot checks | **Built** (Nov 3, 2026): all of A in five timeline segments, with effects, tracks, the render cache and the label check; no music, and two of the planned shot checks not yet (How A was rebuilt) |
| 27. A's overlays and sound, side by side | `MachineShort` in Remotion: captions, labels, tags, title, real footage, SFX, music; ours beside A for all 1:58 (internal only, never published) | **Built** (Nov 3, 2026): the owner's notes on the first cut fixed in the code; narrated by their clone on `eleven_v4` (How A was rebuilt). Earlier cuts kept as `rebuild_v1.mp4` and `rebuild_ryan.mp4` |
| 28. Formats and the vertical short | `format` per channel, stages by format, voice model per channel, Shorts competitors, several publish slots, Shorts publishing with no thumbnail and credits in the description | **Built** (Nov 3, 2026) for `story` and `character`; `machine` and `diagram` come with phases 29 and 30, so their stub channels aren't here (How a character short runs) |
| 29. Writing machine shorts | The model and shot-sheet jobs, and the machine format's topic, outline, script and critic prompts and checks; one real short on our own topic | Planned |
| 30. Systems shorts | The diagram spec, simulation, layouts, `DiagramShort`, ticks on the beat; one real load-balancing short | Planned |
| 31. Instagram Reels | Reels publishing through the Instagram API, after the owner's Meta setup | Planned |
| 32. Character look test | Human Generator (a paid Blender add-on) loading with no window, one person, one 3 to 5 s close-up with a blink, eye move, jaw and prop, laid beside the owner's reference frame; seconds a frame measured. Spec: [CHARACTERS.md](CHARACTERS.md) | **Built and run on the real add-on** (Nov 3, 2026; Commercial license, $128): a 4 s clip at 1.7 s a frame on EEVEE; **the owner approved the look ("really good")** (How people are made) |
| 33. Characters on demand | The character spec and its checks, a saved `.blend` per person, the portrait sheet, rendering with the add-on off | **Built** (Nov 3, 2026): Sam, Nia and Walt, from JSON, about 25 s each; waiting on the owner's look at their sheets (How characters are made) |
| 34. The scene language | One JSON format the agent directs in (cast, grips, strikes, thrown things, glows, shots, captions); fixed code stages it and works out the contacts; the sword test remade from it, and a new scene with no new code | **Built** (Nov 3, 2026): waiting on the owner's look at `data/scenes/ball_to_the_head/scene.mp4` (How scenes work) |
| 35. Getting things | Anything the agent needs that it doesn't have, such as a bird: Poly Haven, Sketchfab, free packs, then a generated 3D model, kept for reuse | **Built** (Nov 3, 2026): `scenes/examples/bird_lands_on_head.json` runs with no scene code, using the free low-poly eagle; waiting on the owner's look at `data/scenes/bird_lands_on_head/scene.mp4`, and a free `SKETCHFAB_TOKEN` for realistic models (How things are got) |
| 36. The director | `format: character`: the jobs where the agent turns a topic into a script, a cast and scenes in that language, with the critic, look checks and the `character` gate | **Built** (Nov 3, 2026): a stub channel runs from a topic to published, and the real filming path runs on a stand-in person. The jobs haven't yet been done by the agent for real: that's phase 37 (How a character short runs) |
| 37. One real character short | One short on our own topic, end to end; voice about $0.25, asked first | **Run** (Nov 3 to 4, 2026): #6, "Why woodpeckers don't get headaches", made in this chat on a channel with a working name; voice $0.096. Its abilities are general, but it did need new code, and it found 3 bugs the stand-ins couldn't (What the first real short taught). Waiting on the owner's look at `data/media/v6/film/short.mp4` |
| 38. Precision | The owner's standard, in code: exact things built from data, placement by contact, a real spin, glow on surfaces and in thin lines only, a level camera, and scenes refused in words when they aren't physically right (The owner's standard) | **Built** (Nov 4, 2026), proved on an internal rebuild of `pan.mov`. Waiting on the owner's look at `data/benchmarks/pan/pan_test.mp4` |
| 39. What to write | His scripts and upload list measured; the outline gets a shape and a turn, the hook starts in a moment or an "If you..." setup, the reviewer sends back what stops at the answer; pauses by channel. Spec: [What his scripts taught](#what-his-scripts-taught-phase-39-what-to-write) | **Built** (Nov 5, 2026): the woodpecker short rewritten through it, made at both pauses in `data/benchmarks/pace_test/`, voice $0.11; `shorts` is on the fewer pauses, and the reviewer has web search. Finding ideas isn't built |
| 40. How it moves | People run, hit and fall; the camera travels; things squash and bend; a thing's set against a crooked surface by measurement; a window in something's head. Spec: [How it moves](#how-it-moves-phase-40) | **Built** (Nov 5, 2026): the woodpecker short made again through it on an 8K tree, voice $0.128, at `data/benchmarks/woodpecker_v3/woodpecker_v4.mp4`. The owner approved the silent preview ("looks good"), and of that cut said "its not bad" |
| 41. How the world works | A frame reviewer goes through every finished short before the owner sees it. Hands hold, what's inside rides, soft things give, bodies land, lights turn with people, x-rays of a person's own head. Spec: [What a frame review found](#what-a-frame-review-found-phase-41-how-the-world-works) | **Built** (Nov 5 to 6, 2026): the woodpecker short went through it, and the owner approved `data/benchmarks/woodpecker_v3/woodpecker_v7.mp4` ("yea this looks good"). The new director's brief hasn't yet run through a real job |
| 42. Finding ideas | Real leads anyone can check, cards that say what people assume and what's true, and a check against the reference's titles. No score. Spec: [How ideas are found](#how-ideas-are-found-phase-42) | **Built** (Nov 6, 2026): `run.py ideas`, with a first batch of 14 cards in `data/ideas/cards.json` |
| 43. Liquids and air | What the barometer short needs, built for every short: clean glass, a liquid's level that's always flat and moves as it fills, a pour that lands in what it fills, and air as balls bouncing off everything. Spec: [What fills things, and air](#what-fills-things-and-air-phase-43) | **Built** (Nov 7, 2026), tried on test things only. The barometer's own things, its direction and its silent preview are phase 44 |
| 44. The barometer short | Its 21 things built from data, its direction on the estimated clock, and a free silent preview, with what making it found fixed for every short. Spec: [The barometer short](#the-barometer-short-phase-44) | **Built** (Nov 7, 2026): a silent preview, now `data/benchmarks/straw/straw_preview_v2_no_voice.mp4`, made after one frame review and four rounds of fixes. The owner: "animation is good", but not straightforward enough (phase 45) |
| 45. Straightforward | The owner's verdict on that preview, measured against the two shorts they called star references, the woodpecker and the pile hammer: rules for one goal all the way, one step a line, every step seen, and sense on mute; labels and failure marks on the picture; and the barometer's script rewritten to them. Spec: [Straightforward](#straightforward-phase-45) | **Built** (Nov 7, 2026). The new script voiced ($0.147), directed and previewed; then the owner's rule that the ending solve the opening problem, so it now ends on the submersible pump, directed on the estimate for its four new lines, which wait on about 5¢ of voice |

The code for plan.md's whole build order is complete (weeks 4–6 are running videos, not building); phase 10 is the YouTube tools plan.md lists that no phase has needed yet. What needs your accounts is under "Your turn" in How YouTube works, How Claude writes, How voice, pictures and clips work, and How topics and metrics work.

**On Nov 6, 2026 the owner decided to post on Instagram rather than YouTube.** Nothing's built for that yet: everything that publishes or reads numbers (`stages/publish.py`, `stages/analytics.py`, `core/performance.py`, `youtube/`) is YouTube-only, and a video's verdict is judged on AVD % and CTR. Making a video isn't affected. The owner posts by hand ("i can post it myself, i just need the vbideos and good ideas"), so no posting or metrics code is planned: a finished video gets a caption with the credits its models need.

## Run it

```
uv sync
cd render/remotion && npm install && cd ../..               # once; the first render also downloads Chrome Headless Shell
copy .env.example .env           # ElevenLabs, fal and YouTube keys (no Claude key: the Claude Code chat does Claude's work)
copy claude-settings.json .claude\settings.json   # once, by hand (and into the workspace folder above): the permission prompts
                                 # .claude\skills and .claude\agents are in the repo; the workspace folder above has copies
uv run python run.py serve       # the engine, and MCP for Claude Code at http://localhost:8000/mcp
uv run pytest -q                 # 451 tests, ~10 min (the session, looking and puppet ones are slowest), real ffmpeg, Remotion and Blender; Claude's jobs answered in the tests, fake ElevenLabs, fal, Google APIs; $0
uv run pytest -m live            # 4 tests against real APIs (a voice line, a still, a 3 s clip ~$0.35, competitors' videos, free); skipped without keys
uv run python run.py demo        # headless run through every gate
uv run python run.py status
uv run python run.py costs 3     # every cost logged for video 3; Claude calls show tokens and the guard's estimate
uv run python run.py voice-test zombie   # one line in the channel's ElevenLabs voice -> data/voice_test_zombie.mp3
uv run python run.py still-test zombie   # one fal picture with the character reference -> data/still_test_zombie.png
uv run python run.py clip-test zombie    # animates that picture with models.clip -> data/clip_test_zombie.mp4 (~$0.90)
uv run python run.py topics zombie       # check competitors now, list their top recent videos and the queued topics; --propose
uv run python run.py bench-render --engine remotion   # or ffmpeg; --scenes, --concurrency, --x264-preset
uv run python run.py look-test           # three of reference A's shots in Blender beside A's frames -> data/looktest/ ($0)
uv run python run.py thing --search bird # free 3D models, with pictures to choose from -> data/things/_search/ ($0)
uv run python run.py thing apple         # a thing from things/specs, fetched and sized, with a sheet -> data/things/apple/ ($0)
uv run python run.py scene scenes/examples/bird_lands_on_head.json   # a scene file rendered -> data/scenes/<name>/ ($0)
uv run python -m machines.specs.generate # writes machines/specs/*.json (the machines' specs) and checks each
uv run python run.py connect zombie                   # YouTube sign-in for one channel (or connect_youtube in the chat)
uv run python run.py youtube-test zombie              # day-1 unlisted upload check
```

With `run.py serve` running, open Claude Code in this folder or the workspace folder above. `.mcp.json` points it at the server; approve the `stickfleet` server once, then ask it what's waiting (How the chat runs the fleet).

The tests never touch a real YouTube channel. `tests/conftest.py` gives every test:
- an empty keychain;
- practice-mode YouTube, unless the test asks for live (with a fake service);
- fixed channel settings (clips on, all gates) and fal pictures, whatever the real files say.

Before it existed, a test run with `youtube.mode: live` and a connected channel uploaded two placeholder videos to the real channel (Oct 30, 2026). The picture pin came in Nov 2, 2026: the real file's puppet pictures at 30 fps kept the suite running for over an hour.

Without `render/remotion/node_modules`, renders fall back to ffmpeg (the video's messages say so) and the Remotion test is skipped.

To start from an empty pipeline, stop the server and delete `data/`.

Measured on this machine (24 threads), `bench-render`, 120 stub scenes with 8 clips, 28.1 minutes:
- Remotion took 13.3 min (798 s). The video was exactly as long as the audio (28:08.28), 295 MB.
- ffmpeg took 52 s, and the video was 0.2 s longer than the audio.

So a full-length render holds the render card back about 13 minutes. The Remotion test and the 6-scene stub videos take under a minute.

## How the code is laid out

- `core/db.py`: schema, `MIGRATIONS` (columns added after a table shipped; `init()` adds missing ones), `transition()` (atomic state change, raises `StateError`), `claim_video` / `claim_scenes` (leases), `tx()` (BEGIN IMMEDIATE), `neighbors()` (the lines either side of a scene). Tables added in phase 8: `competitor_videos` and `competitor_views` (snapshots), `reach_days` and `reach` (the reach files).
- `core/stage.py`: `run_video_stage` / `run_scene_stage` (claim → work → release, retries with backoff, `fail()` → `failed` + `resume_state`).
- `core/actions.py`: every verb the owner can use, through the chat's tools or the CLI (`new_video`, `start_topic`, `dismiss_topic`, `suggest_swap`, `apply_swap`, `keep_swap`, `approve`, `revise`, `regenerate`, `edit_outline`, `flag_scenes`, `edit_scene`, `pick`, `update_publish`, `request_publish`, `retry`, `status`). All state checks live here.
- `core/context.py`: `Ctx` (config, events, providers), `is_stub(provider)`, `log_cost` / `guard` (stub providers log simulated costs, real ones real), `reserve()` (holds a running call's price against the budget so parallel calls can't all pass one check), `meter()` → `Meter` with `check(usd)` and `spend(usd, detail)` for LLM calls, and `channel_meter()` for a channel's calls (topic ideas: capped per call, logged with no video). `ctx.google` holds test fakes for the other Google APIs. `core/errors.py`: `ActionError`, and `FinalError` (a stage failure retrying won't fix, so it fails at once).
- `core/cards.py`: `CardPoster` turns events into rows in `messages` (cards, notices and progress lines), the inbox the chat's `status`, `review` and `news` read; it emits `message` / `message_updated` events. Card payload builders: `outline_card`, `script_card`, `render_card`, `publish_card`, `error_card`, `topics_card` (home thread; competitor ideas or a winner's follow-ups), `metrics_card` (posts as done; verdict, medians, the last swap), `swap_card`.
- `core/performance.py`: the own-data rules. `medians()`, `verdict()`, `judge()` (once per complete reading: the surge, the swap card, the family hold), `ranked_topics()` / `rank()` (competitor views per day scaled by the family's own results, held families last), `held()`, `own_results()`, `swap_since()`.
- `core/events.py`: thread-safe bus. `emit(kind, video_id, /, **data)`. Emit only after commit.
- `core/metadata.py`: publish metadata, description with chapters, `next_slot()`, YouTube validation rules.
- `core/engine.py`: `run_until_idle()` (CLI/tests) and `run_forever()` (server: one async loop per stage).
- `providers/`: `make_providers(config)` picks one per kind from `providers:` (`mode: stub` makes them all stubs). `llm.py` (the `LLM` protocol, `StubLLM`, `NoMeter`), `claude.py` (`ClaudeLLM`: what Claude is asked, in which schema, and how the reply is checked and read; no API), `prompts.py` (loads and fills prompt files), `checks.py` (checks on what the LLM writes, and the counts the prompts ask for), `elevenlabs.py` (`ElevenLabsTTS`), `fal.py` (`FalImages`, `FalVideo`, `clip_settings()`), stub `tts.py`, `images.py` (also the contact-sheet previews and `caption()`, the thumbnail text), `video.py`.
- `stages/`: topics (per channel, not per video), outline, script, regen, voice, stills, clips, thumbs, assemble, publish, analytics (went live, then metrics and the reach import). Outline and script pass the last draft when there is one (a revision), and the script streams its scene count. A video stage's work can return seconds to wait before the video is claimed again (analytics uses it to re-check YouTube every 15 min).
- `render/render.py`: `render_video(items, beats, out_dir, progress, engine, settings)`. The ffmpeg engine (per-scene segments cached by content hash, concat), the highlight reel (segments for ffmpeg, cut from the final MP4 for Remotion), SRT and chapters. `render/ffmpeg.py` uses system ffmpeg or the `imageio-ffmpeg` bundled binary; `duration_ms()` reads a file's length.
- `core/formats.py`: which stages run for which channel format. `things/`: `spec.py`, `get.py` (search and fetch, license rules, the spending gate), `build.py`. `blender/things.py`: importing, sizing and placing them. `scenes/direction.py`: a whole short's clock, its checks and captions. `stages/direct.py`, `stages/film.py`: a character short. `prompts/character/`: its prompts.
- `render/remotion_render.py`: stages the scene files (hardlinks) as a public dir, writes `props.json`, runs `node .../remotion-cli.js render`, turns `Rendered N/M` lines into percent progress. Named so it doesn't shadow the `render/remotion/` folder.
- `render/remotion/`: the Remotion project (pinned 4.0.539). `src/Video.tsx` (one `<Sequence>` per scene, start frames rounded per scene so 120 scenes never drift; a clip scene plays its clip once, then Ken Burns on the clip's last frame), `KenBurns.tsx` (1.0 → 1.08 zoom, pan direction from `idx % 8`), `Captions.tsx` (2–4 words at a time, current word highlighted), `types.ts` (mirrors `props.json`). `npm run studio` opens Remotion Studio; `npm run typecheck`.
- `puppet/`: the cutout pipeline. `rig.py` (proportions in H, `Pose`, `blend`, `cycle`, `joints`, `ground`, the poses and the `LIMP` cycle), `parts.py` (`key_out` the green sheet, `blobs` → numbered boxes → `build()` names them through the LLM and saves `channels/<id>/puppet/<who>/`), `stage.py` (`Stage`: floor points with heights, spots, light; `grid()` for Claude, `overlay()` to check by eye), `draw.py` (one frame: strokes at 2× over a painted background, parts rotated on their pivots, shadow, `light()` tint + lamp glow, `view()` camera), `animate.py` (`Scene` from a sheet: actions per figure, camera keyframes, frames piped to ffmpeg with the audio).
- `youtube/auth.py`: `connect()` (desktop OAuth on a temporary localhost port, `channels.list(mine)`, token to the keychain, `set_channel_id()` into the YAML), `credentials()` (keychain + `client_secret.json`, refreshed, cached), `status()`, `require_connected()`.
- `youtube/client.py`: `Client(ctx, channel_id)` with `upload` (resumable, 16 MB chunks), `set_thumbnail` (re-encodes to JPEG over 2 MB), `insert_captions`, `add_to_playlist`, `video_status`, `recent_uploads` / `find_upload`, `channel_overview`, `update_title` (sends the whole snippet back), `whoami` (the sign-in check), `video_views`. Every call books quota first; `HttpError` becomes `YouTubeError` (`retriable` for 5xx) with a hint for quota, upload-limit and unverified-thumbnail errors. `ctx.youtube` swaps in a fake service for tests. `api_for()` builds another Google API with the channel's sign-in, `public_service()` the Data API with `YOUTUBE_API_KEY`, `run()` books and executes one call.
- `youtube/competitors.py`: `fetch()` (competitors' recent long uploads and views), `stub()`, `seconds()` (ISO 8601 durations), `age_days()`.
- `youtube/reporting.py`: the reach job (`ensure_job`), `import_new()` (new daily files, backfills replace), `parse()`, `window()` (impressions and CTR over a run of days, once all have arrived), `pacific_days()`.
- `youtube/quota.py`: per-day, per-bucket ledger in the `quota` table (Pacific-time days). `check()` before a sequence, `spend()` per call.
- `core/jobs.py`: Claude's work waiting for the Claude Code session. `NeedsClaude` (a stage parks on it), `plain()` and `key()` (a request as JSON and its hash), `answer_for()`, `park()` (store or find the job, supersede an older one for the same video, scene and kind, register its checks), `pending()`, `take()`, `answer()` (check, store, wake the parked stage; or one part of a long answer), `merge()` and `parts_so_far()` (the parts as one reply), `resume_with()` / `to_resume()` / `resumed()` (a topic round waiting on its job), `supersede()` (Stop). The `claude_jobs` table is in `core/db.py`.
- `providers/session.py`: `SessionLLM`, the `ClaudeLLM` whose `_call` finds a job's answer or parks a new job; `providers.llm: session` is the only real LLM. `LOOKING` names the job kinds the `worker` agent does. Tests pass `stub` and `stubbed` method names to answer some calls with the stub.
- `server/claude_code.py`: the MCP endpoint at `/mcp` (low-level `mcp.server.lowlevel.Server`, streamable HTTP with JSON responses, mounted in `server/app.py` and run in its lifespan), its instructions to the session, the fleet tools from `server/tools.py`, and `jobs`, `take_job` (a brief over `BRIEF_MAX` goes to `data/jobs/job-N.md`; a request's pictures go as JPEGs `PICTURE_WIDTH` across), `answer_job` (whole, or in parts), `wait` (at most `WAIT_MAX`, 50 s), `contact_sheet`. `.mcp.json` points Claude Code at it (one copy here, one in the workspace folder above).
- `server/tools.py`: the fleet tools (`make_tools(ctx)`: name → MCP tool and handler), thin wrappers over `core.actions`, plus `review` (a waiting card in full; the script as a Markdown file in `data/review/`, thumbnails as pictures, media as file paths), `news` (unseen notices and cards, marked in `messages.seen_at`), `status`, `connect_youtube`. `ASK`: the tools behind Claude Code's permission prompt, kept equal to `claude-settings.json` by a test.
- `.claude/`: `skills/stickfleet/SKILL.md` (the job loop, the script in parts, reviews to the critic agent, looking jobs to the worker agent, what needs the owner's yes and what costs money), `agents/critic.md` (the reviewer with fresh context; only `take_job`, `answer_job` and `Read`), `agents/worker.md` (the looking jobs, one after another, up to 20 an agent; `jobs`, `take_job`, `answer_job`, `wait` and `Read`), `skills/viral-hooks/` (from `vyralcontent/content-skills`, MIT, its `LICENSE` kept, without the header banner and the "Mentioning Vyral" section). Copies sit in the workspace folder above, since Claude Code reads the folder it's opened on. `settings.json` is the owner's copy of `claude-settings.json`.
- `tests/replies.py`: outline and script replies in Claude's shape that pass the checks, for the session tests and `tests/test_checks.py`. `tests/test_looking.py` has `Worker`, a `SessionLLM` that keeps the stub's answer to each looking job so a test can answer the jobs as the worker agent would.
- `prompts/`: `outline.md` (with the hook checklist), `script.md`, `visual.md` (how a picture prompt is written, pulled into the others as `{visual_guide}`), `regen.md` (one flagged scene), `titles.md`, and the picture templates `still.md` and `thumbnail.md` (whole files, no user turn).
- `server/app.py`: `create_app(ctx, run_engine, hosts)`: the engine in the lifespan, the local-only Host and Origin check, and `/mcp`. Nothing else is served.

Media paths are stored relative to `data/media`. Card payloads still write them as `/media/...`, and the chat's tools turn that into the file's path on this machine. Each still has a `.thumb.jpg` preview for the contact sheet.

## How A was broken down (phase 24: the storyboard)

Everything here is A's, so it stays in `data/benchmarks/pile_hammer/` (gitignored) and is never published (SHORTS.md, "Rebuilding A").

- **`transcript.json`:** the narration with every word's time. It's from local Whisper (`faster-whisper`, small.en on the CPU, free), run once with `uv run --no-project --with faster-whisper`, so it isn't one of the project's dependencies. Its audio loader clashed with the installed PyAV, so the script reads the WAV itself and passes the samples. The voice runs 0 to 108.2 s, and the rest is the title and real footage.
- **`sheets/`:** A at one frame a second, six to a sheet, timestamped.
- **`storyboard.json` and `.md`:** 64 beats, one per on-screen caption, split where the scene or camera changes. Each beat has:
  - the caption exactly as shown (with its line break);
  - the words spoken;
  - what's on screen, each part's state, and the camera's framing, angle, move, start and end;
  - the cutaway, effects, labels and tags (each with its times and place), the transition, sound events, and notes.

  At the top: the style, 6 environments and 30 models, each described in multiples of the pile's diameter.
  - A subagent wrote it from the sheets and 4 to 12 fps strips. Caption times come from a per-frame scan of the caption box; motion and overlays are accurate to about ±0.125 s.
  - Its script is in the session's scratchpad, not the repo.
  - Checked by hand: the STEEL PILE label's times, the ×N counter, and the move into the engine through the cylinder's side port at 57.1 s (the brief had said the engine starts at the 62.75 s cut; it starts earlier).
- **What it found** that the plan hadn't:
  - The nail grows ×1 to ×100 in one continuous shot, staying the same size in the frame, while the world around it turns from the black room to the desert. The wood's face becomes the soil's cut face.
  - The engine is entered and left through the hammer cylinder's side port.
  - The diesel cycle's air balls change colour as they heat up.
  - About 20 labels ride on moving parts.
  - Five captions word things differently from the narration ("But after every strike", "At that moment").
- **The voice sample:** `voice_sample_zach.mp3`, the opening line in the owner's own voice, 4.96 s against A's 4.60 s ($0.016).

## How machines are built (phase 25: the kit)

A machine is a JSON spec of named parts, checked in code before Blender starts, then built by `blender/kit.py`. Shots (phase 26) will only ever set joint values.

- **`machines/spec.py`** is the authority on the format. Its docstring lists every shape and what it needs.
  - **Shapes:** box, cylinder, tube, cone, lathe, sphere, torus (and its C-shaped arc), extrude, pipe (a path with rounded bends), rods, truss, spring, text, and group (an empty that holds parts).
  - **Placement and materials:** materials come from the palette; parts have places (`at`, `rot`, `scale`) under parents.
  - **Steps:** a part says from which step it's there and until which, so the machine grows as the story does; a parent's absence takes its children with it.
  - **Joints:** slide, hinge, spin, and stretch (a cable as long as its hook is low).
  - **Couplings:** crank (a piston's height from its crank angle, exact), rod (a connecting rod's tilt), gear, and follow (a crane's tip undoing the boom's tilt so the hook hangs straight; the cable's length from the hook).
  - **Helper parts:** never drawn, they cut holes in the parts that `subtract` them (an engine's bores and crankcase).
  - **Anchors** for labels, **contacts** (pairs allowed to touch), and **`cut`** (whether a cutaway cuts the part).
- **`check()`** returns every problem in words a writer can fix: unknown shapes or materials, missing sizes, a tube whose inside is bigger than its outside, sizes over 500 m or too small to see, parents that don't exist or go round in a circle, steps out of range, bad joint ranges, couplings to parts with no joint, a crank's throw longer than its rod, subtracting a part that isn't a helper.
- **`blender/kit.py`:**
  - `Model(spec)` builds every part. `set(part, value, frame)` moves a joint, drives its couplings and keys what moved. `show_step(step, frame)` shows only that step's parts.
  - `overlaps(model, step)` uses BVH trees of the evaluated meshes, so holes and cutaways count. It tests every part pair at rest, with each joint at its min and its max, and with each spinning driver a quarter turn at a time. A driven part moves only through its driver.
- **`blender/turnaround.py`** (`blender_render.turnaround()`, which runs `spec.check()` first): every step from the front, the three-quarter left, the side and the three-quarter right. Where parts are cut, there's also a cut-open front view, with the hatching spaced to the machine's size (`materials.hatch_for`).
  - The pictures go to `data/models/<name>/`, tiled by `machines/sheet.py` into `sheet.png`.
  - `blender/framing.py` fits the camera so every corner of the parts' box is in the 9:16 picture. Shots will use it for framing.
  - A `pose` job sets joints and reports where every part ends up, for checks and tests.
- **The machines,** written by `machines/specs/generate.py` (`uv run python -m machines.specs.generate`). Sizes follow the storyboard's multiples of the pile's diameter (0.6 m).
  - **`diesel_pile_hammer`, 48 parts in A's 9 steps:**
    - a 30 m hollow pile in `pile_paint` (white rings every diameter, red bands, a red tip), which sinks with each blow and carries the hammer;
    - the iron block with its split line, then the ram and the anvil boss with its dished top;
    - the flange with four sockets;
    - the lipped cylinder with a port each side;
    - the explosive drum, then the glassy guide rods (`glass_rod`), the collar with its ears and sleeves, and the crossbar with its pulley ball and start-up hook;
    - the red canister pushed in from the front;
    - the chrome injector, the jerry can (GASOLINE, then DIESEL) with its yellow fuel pipe, the spark plug with its coil, battery and wires.
  - **`car_engine`:** an inline four cut through its bores, with liners, domes, pistons, rods, a crankshaft (journals between the throws), valves and plugs. Phases 0, 180, 180, 0.
  - **`crawler_crane`, `claw_hammer`** (the shot scales it: half size for the taps, ×100 for the giant one), **`ground_section`** (A's soil layers, the barrier, cones) and **`nail`**.
- **The checks caught real mistakes in every first draft:**
  - the pile hammer's ram and eye bolt hitting the crossbar at full lift;
  - its lugs, fuel pipe and spark wire through the guide rods;
  - its collar inside the cylinder. This showed the storyboard's "1.1 ram heights" counts from the flange, round the boss;
  - its canister through the left rod (it now comes in from the front);
  - the engine's bores meeting the crankcase face to face, which left a skin;
  - a one-piece main shaft under the rods;
  - valves through the plugs;
  - the crane's boom through its cab.

  Touching surfaces can flicker as overlapping with floating-point rounding (the cylinder on the flange only showed with the pile at −20 m), so parts that sit on each other are declared contacts.
- **New palette entries:** bright_steel, black_steel, pile_paint, glass_rod, blue_paint, orange_paint, barrier_stripes, and soil_top, mid, low and deep. `cut:<spacing>` gives hatching at any spacing.
- **Tests:** `tests/test_machines.py`, 27 tests; the whole suite is 143, green (8 min 10 s).
  - The spec checks: a good spec, 11 bad ones each saying what to fix, and steps.
  - Every kept spec passes `check()`.
  - A turnaround of every step from every side.
  - Planted collisions found, both at rest and at a joint's end.
  - The crank driving its piston to exactly twice its throw down at 180°, with the pin riding along.
  - Every kept machine collision-free at every step.
- **Not yet:** the effects A's models list (the fireball, ghost rams, air balls, fuel sprays, combustion glow, exhaust) are phase 26's. So are a machine scaled as one (the giant hammer) and the wood block, far bridge and stubs, which are scenery and are already in `envs.py`.
- **Your turn:** look at the sheets in `data/models/*/sheet.png`, the pile hammer's and the engine's above all, and say what's off.

## How A was rebuilt (phases 26 and 27: shots, overlays and sound)

The engine is in the repo and serves every machine short. What is A's (its timelines, our narration of its script, the renders) stays in `data/benchmarks/pile_hammer/` (gitignored) and is never published (SHORTS.md, "Rebuilding A").

- **A segment is a timeline,** a JSON file `blender/shots.py` turns into a scene. Its docstring is the authority on the format.
  - **What it holds:** the set (`env`), the machines placed in it (one can hang from another's part), keys at seconds of the whole short (steps, joints, show and hide, scale, place, each with an ease), the camera's keys, the cutaways' times, the effects, the anchors to track and the sound events.
  - **Frames are numbered for the whole short,** so a segment's clip, tracks and events line up with the narration with no offsets to carry.
  - **The camera** is a rig: an empty on the target (a point, `model:anchor` or `model.part`), the camera on an arm from it by `az`, `el` and the width of the world to `frame`, nudged in the picture by `x` and `y`, with `lens`, `roll` and `fstop` keyed too. Shots can also give `at` and `aim` directly.
  - **Eases:** inout (smooth, the default), linear, in (a fall), out (a rise or a stop), const (hold, then jump), whip.
  - **Cutaways** that are on for the whole segment are baked into the mesh. Timed ones are keyed modifiers. Baking took the engine from 79 s a frame to 3 s.
- **Effects,** `blender/effects.py`, animated by code so a render is the same every time: air balls (keyed from blue to white to amber as the air heats), fuel spray with a mist cone, a glowing gas column or sphere, a fireball, smoke puffs, ghost copies of parts (a missed landing), a shock ring, a spark, a flashing light. An effect's light has zero-energy keys either side of it; without them it lit the scene before it started.
- **`blender_render.render_segment()`** passes every machine spec to Blender by its file's name and returns the tracks (`first`, `frames`, the anchors, the events).
- **`MachineShort`** (Remotion, `src/shorts/MachineShort.tsx`, props in `machine.ts`) is the whole short:
  - the segments' clips, crossfaded where they overlap;
  - screen effects: dim, crossfade, a tint, a black or white flash held for its frames, a smoke wipe, and a darkening to the end;
  - labels riding their tracks, tags (fail, warn, question, multiplier, section, mode, stat, title, dimension, deeper, footage, credit) and A's caption box;
  - the narration, the sound effects, and real footage at the end.
  - `remotion_render.render_machine()` renders it, then holds the mix's peaks under −1 dBFS (`_limit`, ffmpeg's alimiter; the picture is copied, not re-encoded). Without it, 13 impacts landing on words clipped at 0 dB.
  - A label rides through a hide shorter than 18 frames, 0.6 s (`BLINK`), so a part passing in front of its dot doesn't make it blink. A longer hide hides it.
- **The label check,** `render/shot_checks.py`: `label_problems(labels, tracks, fps)` says which labels can't be seen, before Remotion runs. A label fails when its anchor is hidden (counted as the overlay counts it) in over a tenth of its frames, or outside the safe area in over a tenth of those it's seen in, or has no track.
- **Sound effects,** `render/sfx.py`, are made by code (decaying partials for metal, filtered noise for air and fire): tap, heavy tap, heavy impact, thud, clank, whooshes, riser, explosion (and muffled), hiss, crackle, hum, click, error, pop, scrape. Nothing to license; each is made once into `data/sfx/`.
- **Narration,** `render/narration.py`: `fit()` voices each line in ElevenLabs and fits it to its slot with ffmpeg's atempo, so the pitch stays the voice's.
  - A line too long for its slot is sped up, at most 1.45×. One much too short is slowed, at most to 0.88×. Within 0.85 to 1.0 of its slot it's left alone.
  - A line too long even at the fastest spills into the pause after it. The next one starts just after and catches up, so the read never drifts far from its marks.
  - Each line's voice file is kept by a hash of the voice, speed and text, so running again never pays twice. Lengths are measured on the decoded WAV: an MP3's stated length counts its encoder padding.
- **A's rebuild,** in `data/benchmarks/pile_hammer/timeline/`:
  - `make.py` writes A's five segments: the nail on the bench (0 to 6.1 s), the nail growing ×1 to ×100 into the desert (5.3 to 7.5), the desert to the side port (7.0 to 57.1), the engine (57.0 to 63.25), and the desert to the end (63.2 to 109.1). The hammer, crane and engine are the phase 25 specs. Every joint is timed to A's word times from the storyboard.
  - `preview.py` renders a few frames at low size beside A's at the same moments.
  - `assemble.py` renders the segments, voices A's script in the owner's voice (zach D) as 39 lines from A's transcript, takes the captions, labels, tags and sounds from the storyboard, and renders `rebuild.mp4` and `side_by_side.mp4` (ours, then A with its own sound). `--draft` is half size and 8 samples.
    - A segment is reused while its picture is unchanged: its timeline, the machines and the `blender/` code, leaving out the anchors. When only anchors changed, Blender runs again for the tracks alone: 17 s for the 50 s desert segment, against 12 minutes to render it.
    - It runs the label check and prints what fails.
  - The first narration cost $0.35 (2,030 characters at `elevenlabs.price_per_char`, $0.00017), once.
  - The full-size render took about 32 minutes in Blender for the 3,318 frames (the engine's 188 about 2 s each, the rest 0.4 to 0.5 s), then about 3 minutes for Remotion and the side by side, at $0. Fixing the labels afterwards took 40 s of tracks and the same 3 minutes.
  - The real footage at the end is Wikimedia Commons' "Pile driving for bridge pier foundation at Patimban, Indonesia" by Irvan Ary Maulana (CC BY-SA 4.0), credited on screen. A shows its own.
- **What comparing with A found:**
  - **The owner's voice reads about 24% slower than A's narrator.** Fitted to A's marks, 12 of the 39 lines are sped up past 1.35×, and the read ends at 108.8 s against A's 108.2. The owner found this rushed (below).
  - **A's sand is brown, not orange.** Under AgX in full sun our first tint read pale salmon. The tint went to (0.70, 0.43, 0.16); the ground now averages about (171, 111, 83) against A's (154, 111, 75).
  - **Labels need their anchors in view for their whole time.** A's AIR and DIESEL labels sit on effects, so effects export anchors (`fx:air`, `fx:spray`). The label check, run on the first full draft, found problems with 9 of its 20 labels. Three never showed at all, and PRESSURE sat on the picture's bottom edge:
    - DOZENS OF TONS pointed at the pile's top, 30 m up and above the picture while the camera runs down the pile. It now points at `pile_low`, 3.5 m up.
    - FUEL INJECTOR pointed at the injector's middle, inside its port ring. It now points at its front.
    - PRESSURE and EXHAUST pointed at whichever glow and smoke came last in the segment, since each took the default anchor name. The timeline now names every effect's anchor, and smoke puffs are one group as the air balls are.
    - SPARK PLUG went out of the picture and IGNITION SYSTEM's camera arrived late and left early. Both shots were reframed to A's.
    - Left as they are, all brief: EXPLOSIVES and INJECT hidden for about 0.4 s each, as the drum and the spray pass behind the cylinder's lip; SPARK PLUG and EXHAUST at the picture's right edge, as in A.
  - **Short flashes break Remotion's interpolate** when a range is two frames or less. Fades are clamped to the time they have, and a held flash peaks at its middle when it's that short.
  - **Bloom made the crane's white lattice glow.** The compositor's threshold went to 1.8 and white paint down to 0.62.
- **Tests:** `tests/test_shorts.py` gained 10: every sound effect is made; narration fits lines to their slots, a read stays at the voice's pace, and neither voices a line twice (with a fake voice); the picture follows a new read and only ever slows, with every timeline time moved; a reference video slows by one long ffmpeg expression; camera moves too fast are reported, and cuts and marked dives aren't; the label check finds hidden, off-picture and untracked labels and lets a blink pass; a segment renders from its timeline with frames numbered for the whole short; a whole `MachineShort` composes with sound.
- **The owner's notes on the first cut** ("its good but the floor flickers a bit, and the person talks too fast", "the video zooms in an out also too fast", "lets use ryan well", "breathing room between every senetence"):
  - **The floor flicker was two faces at one height.** The soil block's top sat exactly on the sand plane, 80 m by 14 m of it, and the camera's near clip was 0.01 m in every shot, too coarse for a depth test at a distance. From high up the two swapped every frame: the bottom of the picture jumped between brightness 118 and 159 from 8.1 to 8.55 s, and with the camera held still nothing changed at all, which ruled out render noise. The soil now starts 3 cm under the sand, and each camera key sets its near clip to its distance over 300 (`blender/shots.py`). The same 20 frames now hold at 117 to 119.
  - **The picture follows the voice** (`render/retime.py`). `narration.read()` voices each line unfitted, and `retime.layout()` places them with a pause after each. A `Warp` then moves every time in the timelines and overlays onto that read: between line starts the picture stretches evenly, and it never speeds up. `Warp.setpts()` slows A by the same map for the side by side, under our sound. Captions come from the read itself (`narration.captions()`): a sentence to a caption, or split at the comma nearest its middle over 64 characters, each from its first word at the voice's own time until the next, so the box stays up through a pause. Borrowing A's caption breaks gave fragments ("This" / "is a nail."), since A's captions start a moment before its words.
  - **The script has connectors and pauses** (`narration_v2.json`, 39 lines, one for each of A's): "But" and "So" where a problem hands over to its fix, at least 0.5 s after every sentence and 0.9 s after a question or problem, in Ryan Wells ($0.35).
  - **The length is the cost of this.** At speed 0.95 Ryan Wells reads this script at 16.6 characters a second, faster than the 13.4 to 14.7 of the zombie channel's scenes at 0.9, which come with that channel's own script and pacing. With its 24 s of pauses the read ends at 148 s and the short lasts 2:38, against A's 1:58, and the picture slows about 1.5× on average. Real machine shorts have to be written shorter for this pace (SHORTS.md, Voice).
  - **The voice was tried again as the owner's clone, on v4.** Ryan Wells measured flatter (a pitch range of about 12 semitones against the clone's 16), and the owner called him bland. The clone's questions were then measured against A's narrator: A lifts at the end of all 5, while the clone dropped on 3 and ended its questions no higher than its statements. On those 5 lines ($0.12), v2 with lower stability lifted 2, a hint in `next_text` lifted 2, and `eleven_v4` lifted 4; retaking the fifth lifted all 5 (+5.7 semitones on average, against −1.3 for statements). v4 bills the same per character, and `narration.read(model=)` selects it. Its lines carry silence at their ends and it reads slowly (13.7 characters a second), so the ends are trimmed and a tempo of 1.10 brings it to 16, which makes the short 2:44. A local Whisper pass over the read (`voice_final.mp3`) found all 393 words. The owner: "IT SOUNDS AMAZING". `narration.read()` does the trim and tempo (`pace`), `narration.track()` the one leveled track the short plays.
  - **Camera moves are checked** (`shot_checks.camera_problems()`): over 2.5 e-folds of framing a second, or 120° of swing a second, is reported with the time it needs. A cut (under three frames) passes, as does a key marked `fast`, for a deliberate dive. The 5× whip and 53° swing in 0.15 s at 8.6 s now takes 0.7 s; the dive into the port takes 1.05 s, not 0.5; out of it takes 0.6 s, not 0.35. The nail's ×1 to ×100 is an even curve, where A's races through the middle.
  - **Slowing a shot shows what speed hid.** At 0.5 s, the dive into the port went by unnoticed. At 1.5 s, a guide rod filled the screen, because the camera came straight along the line of the port and the rod, into a cylinder still cut open. Compared again with A: A's cylinder is whole by then (its cut ends under the explosion's flash) and its port is a black hole, approached from about 55° with the rod off to the right. Ours now does the same, and a black ball sits in the port while the cylinder is whole, where the lit ram showed through. The second cut's frames for those stretches were rendered again alone (`render_segment(frames=...)`), about 3 minutes against 50. So after retiming, look at every transition at full length again.
  - **The last pass over the final cut:** the big fireball was a flat pale disc with a hard edge for a moment, where A's is a translucent orange ball, so a fireball can now ask for `soft` edges. Sound effects that land on a spoken line play at 60% (`narration.duck()`): a buzz sat on "couldn't swing it" and the impacts on "slamming into the pile". The voice now sits a median 14 dB over everything else while it speaks.
  - **Reusing frames:** `assemble.py` keys a segment's frames on all of `blender/`, so another session's work on character shorts there set off a full render, which was stopped within minutes. One frame from each desert and engine segment, rendered again with the changed code, matched the kept frames (a mean difference of at most 0.004 out of 255), and `--segments none` kept them all. Phase 28's render cache should key on the code a machine short actually uses.
  - **Labels may keep their side.** PRESSURE flipped off the safe area's edge onto the white glow, where it couldn't be read. A label's `stay` keeps it on its side, as A has this one.
  - **A failure this turned up:** the pile hammer's collision test had been failing since phase 26 gave the start-up hook 6 m of travel, which took it through the ram. It now stops at the ram's eye, the lowest the shots use.
- **Not built yet from phases 26 and 27's plan:** the music bed (music is still an open decision in SHORTS.md), and the shot checks for a label clear of its own part and a level camera on a cutaway. A's timelines were written by hand in Python, not as shot sheets from a job; the sheets come with phase 29.
- **Your turn:** watch `data/benchmarks/pile_hammer/side_by_side.mp4` (ours left, A right, A's sound) and `rebuild.mp4`, and say what's off. Changing a segment and rendering again takes only that segment's time; the narration is already paid for.

## How characters are made (phase 33: on demand)

A character is a short JSON file in `characters/specs/`, and `uv run python run.py characters` makes each one, about 25 s a person with their portraits, at $0. `run.py characters sam` makes just Sam, and `--options` lists every choice. `characters/spec.py`'s docstring is the authority on the format.

- **The flow:** `characters/spec.py` checks the spec against what's really installed, and a bad one is refused with its reasons before Blender starts ("hair: no 'Short Comb'; did you mean Short Combed?"). `characters/build.py` makes the person into `data/characters/<id>/` and renders `portraits/sheet.png`. A person is only made again when their spec changes.
- **Names, not numbers:** a spec says `"hair_color": "brown"`. The numbers behind each color are in `spec.py`, found by looking, because the add-on's lightness runs far past 1. Only brown, black and grey have been seen on a person; the rest are estimates until someone needs them.
- **The portrait sheet** (`blender/portraits.py`): the face from three sides, the full body, and 8 expressions. It runs with the add-on off, so it also proves the saved person works alone. It's the check the worker agent and the `character` gate will look at in phase 35.
- **Expressions** are the add-on's artist-made faces, saved on every person as shape keys (`e_happy_smile`, `e_big_surprise`, ...), and asked for by name through `Person.expression()`. They were much stronger than the mixes of face-rig keys tried first.
- **People in a segment:** a timeline can have `people`, and the camera or a label can follow `id:eyes`, `id:mouth` or `id:head`. Two people can share a scene: the second arrives with renamed objects, so `Person` finds them by what they were saved as. Tested on the stand-in person, not yet on two real ones.
- **Found on the real add-on:**
  - It has no facial hair for women, and even asking to remove it raises an error, so the spec refuses it and `to_person` leaves it out.
  - A preset's beard takes `hair_color` separately from the head's hair, so it's set on both. Walt's stayed brown until then.
  - A preset's hair and outfit colors come with it; `clothes` changes a garment's main color by part of its name, and `person.json` lists the garments. A name that matches nothing is refused.
- **Known weak spots:** Nia's lips stay a pale rose even with lipstick. The full-body view stands in the add-on's A-pose, arms out, since nothing sets a natural standing pose yet (phase 34).
- **Your turn:** look at `data/characters/sam/portraits/sheet.png`, `nia/` and `walt/`, and say what's off.

## What the first real short taught (phase 37)

Video #6 went from topic to render through the real jobs: the outline and script past the critic agent, the owner's clone at 1.05 on `eleven_v4`, the worker agent choosing and checking models from Sketchfab, and a direction written in the scene language. No code for this video. The acceptance line in CHARACTERS.md said "with no new code"; that was too strong, since a first real topic was bound to find gaps. What was added is general: anything could use it.

- **The critic earned its place:** it caught "too small to get hurt" going past the finding (a 2018 study found tau build-up in woodpecker brains), "out cold" being unsupported, and small birds being stunned by windows.
- **General abilities it needed:**
  - `rock`: a whole thing tipping about a place on it, for a model with no clips (a peck, a tapping hammer).
  - `aura`: a soft light on a thing's spot, as `glow` is on a person.
  - `sparks` `kind: "chips"`: wood chips, since a hammer on bark throws no sparks. The critic's catch.
  - A strike on a thing's side: a swing, landing the tool's front flat, where strikes only came down from above. A tool's `grip` and `end` spots make it exact.
  - A hand holding something closes on it (`FIST`), whatever its stance's hand is doing.
  - Rings face the lens of the shot they're in, where they faced one fixed way.
  - `"ahead"` on a shot: aim where the subject will be, for a close-up of a landing.
- **Bugs the stand-ins couldn't show:**
  - A stage runs again from the top, and getting a thing changed the library, so "what the short needs" became a new question every time. It's now asked once per set of the owner's notes (`_asked_once`), and each thing's progress is kept in a file.
  - The sheet for the look paired a frame with the line before it, when a shot started just after a line ended. The looker believed it and reported a false mismatch. A frame is now paired with what's being said at that moment, with `[this frame]` marking the word.
  - What the look found asked "what the short needs" again. Its notes now start with `LOOK_NOTE`, and only the owner's count.
- **The look job isn't enough on its own.** A 216-wide sheet missed Walt's face going through the trunk, and a hammer handle through his chest. They were found by rendering a few frames larger before answering. Its notes also need judging: of 6, one was real and most were either the design or the bad labels above.
- **Worth knowing for directing:**
  - The frame is narrow: 0.5625 of `frame` across. Two subjects side by side only fit with depth between them, the near one large.
  - A shot's `angle` on a thing counts from its heading. For a thing facing a wall, 0 puts the camera in the wall, so stay past -95 or so.
  - A knock rings back and then forward: leave a few centimeters, or the head goes into what it hit.
  - Photo-scans bring their own trouble: the trunk's base slab floats once it's stood upright, and its top is hollow, so both are framed out.
- **The server needs a restart to pick up `scenes/spec.py`, `stages/` or `providers/`.** `blender/` is read fresh by each render, and `prompts/` by each call.

## The owner's standard (phase 38: precision)

On Nov 4, 2026 the owner asked for a test: could what was built the day before emulate a Zack D Films short (`pan.mov`, how induction cooking works)? The first cut used the scene language as it stood, with free models. Their verdict: "it looks really bad compared to the original video. The screen wobbles, the pan doesnt respect boundaries, the magingate doesnt actaully spin, the glow looks really basic", "person's hat doesnt even sit on top", and then the standard for everything from here on: "every subsequent video should be made with precision and resepcts pysical boundarties and remove bad glows and placements. I dont wanna keep saying smt doesnt look appealing."

So the fix went into code, not care. What each fault was, measured:

| What they saw | What it was | What changed |
| --- | --- | --- |
| The screen wobbles | Not shake: within a shot the picture wandered under 0.1 px a frame, and the frames were in order. The director swung the camera left and right between cuts, so the counter's edge tilted differently at every cut, and the coil scene alternated 4 degrees either way on purpose. The reference holds its counter dead level | `square` shots count their angle from the set. `scenes/spec.py` refuses a swing under 18 degrees between shots of about one size, and a push over 0.05 of the distance a second |
| The pan doesn't respect boundaries | `lands` is for what flies: it flared the pan's nose up and put its front edge through the glass | `slide` sets a thing down, straight and level, to exactly where it rests. `on` lowers a thing until the meshes touch |
| The magnet doesn't spin | A thin flat magnet turned by a `go` round a tiny circle, seen edge-on from the film's camera. It only looked right in a check from above, a camera the film doesn't use | `spin`, about one exact axis of a thing, through a spot. A chunky magnet built from data, on a shaft from a motor, turning so the lens sees it flip |
| The glow looks basic | `aura` was a ball of light in front of a thing | Gone. `lit` lights a thing's own surface, and can't leave its edges. `flow` is thin lines laid on the surface by rays, stopping at its edge. `rings` are true thin circles. The bloom only catches what's really bright (`blender/glow.py`) |
| The hat doesn't sit on top | Placed by hand, with numbers read off a picture | `wear` measures the head and the inside of the hat, fits it, seats it on the brow or crown, rides it on the head, and cuts the hair it covers in the hair's own shader |

**What's new:**
- **Built things** (`things/spec.py`, source `built`): anything geometric, written as parts in the machine kit's format, each with a palette material or its own paint. They're exact and clean, and their spots and lines are known. A scan is for what can't be drawn, such as food. `things/build.py` makes one again if the code its look comes from changes (`made_by.txt`).
- **`sky_counter`** (`blender/envs.py`): a level matte counter before the reference's blue, in the Standard view so colors go straight to the screen. Measured against the reference: sky (72, 146, 206) to their (71, 147, 205). What the camera sees and what reflections see are separate, so steel has a studio to mirror.
- **`blender/bounds.py`, the refusals.** When a scene's staged, its meshes are measured frame by frame while they're both in the picture: anything passing through something by over 3 mm, anything left hanging unsaid (`floats: true` says it's meant to), and any lens inside something or with something right in front of it. `Stage.run` raises `Refused`, `refused.json` carries the reasons to `scenes/render.py`, and `stages/film.py` sends them back to the director as notes, three times at most. It earned its keep at once: it caught an arrow 7 mm into a pan's rim, when by hand the arrow should have cleared it, since the stand's ring sits 3 cm forward of its middle.
- **`marks`** in a direction: a big number counting up, drawn in Remotion (`count` in `MachineTags.tsx`).
- **`to`** on a cast thing: fixed to another at a point, from any side, its `by` spot exactly on the other's spot. `on` only stacks downward, so without it a shaft into a motor took numbers worked out by hand, the very thing this phase ends.
- **Directing:** `prompts/character/direct.md`, `cast.md`, `thing.md` and `film.md` carry all this, `cast` can ask for a thing to be built, and `scenes/examples/magnet_under_pan.json` is a worked example.

**Does it work for other topics?** The owner's question, so it was tried: five scenes with nothing in common with `pan.mov`, through the stock checks and stage with no code for them (frames in `data/benchmarks/general/general.png`). A desk fan with its blades fixed `to` its motor and spinning, on a counter, beside a real scanned apple on a built plate. A built cap fitted to Nia, her hair below it. The hard hat fitted to Walt, with his beard and thin hair. A real bird landing on a built bench on the floor set. A scanned apple on a crate in the gym. No code in `blender/`, `things/`, `scenes/` or the stages names any of this short's things. All five passed, and all looked physically right, though the bird is a poor fit for perching: it's a scan of one clinging to a trunk. It found the need for `to`, and a ridge on the hard hat standing off its dome from the side.

**What it can and can't do.** It's for solid things and held poses: objects on surfaces, machines, tools, food, animals from scans, people in strong poses. It has nothing for water or anything poured (phase 43 added them, and air), smoke and fire in the character format, cloth that moves, walking and acting, crowds, or big landscapes. Each of those is new general code when a topic needs it. The checks catch what's physically wrong, not what's unappealing: a dull shot passes. That's still the director's job and the look job's, against a reference when there is one.

**How to work from here:**
- Judge motion from consecutive frames through the film's own camera, beside the reference, never from a test angle or a still. Compare at full size before showing the owner anything. A contact sheet read through the image tool can look posterized when the frames aren't: check a crop.
- A scene's look files are kept by the scene's JSON, so after changing a thing or the set, clear them.
- Don't edit `blender/` or `things/specs/` during a full render: each scene reads them fresh.
- **Not done:** gestures. A person still holds one stance, where the reference's raises a finger. A thermometer, and the reference's fast moves between shots with motion blur. `pan.mov`'s rebuild stays internal: it follows the creator's shots.

## What his scripts taught (phase 39: what to write)

On Nov 4 and 5, 2026 the owner said video generation was in a good place and asked for a pipeline that writes interesting scripts. They believed Zack D "usually begins with a problem and builds up the solution", and offered to paste more of his videos. So it was measured first. Everything's in `data/benchmarks/idea_study/` (gitignored), with its scripts in `scripts/`: the YouTube Data API for titles and views (167 quota units, free), and local Whisper for the words.

**What the numbers say, and what they don't:**
- The pile hammer and sewer line references, the two that climb problem by problem, have no matching title among the 4,145 uploads returned for `@zackdfilms`. Only induction, cow hoof and the sword are his.
- Videos from the same quarter differ about 6x (bottom tenth 0.44x his median, top tenth 2.59x), and a rough keyword sort by topic explains under 1% of it.
- **A blind test on the half of his shorts not studied:** 77 same-quarter pairs of a clear winner and loser, typically 7x apart. A fresh reviewer with no guidance picked the winner 47% of the time. One with rules written from the other half: 45%. The key was audited against the data. So **no idea score goes in** until one beats a coin flip on held-out pairs: it would look rigorous and predict nothing.
- Everything he posts has already passed his filter, and his subscribers lift it all, so this doesn't show all ideas are equal, and can't separate script, first seconds and luck. The same test on scripts hasn't run: 20 named videos are in `script_sample_key.json`, sealed.

**What his 19 scripts have in common** (his 18 newest, one cut off, plus induction and cow hoof; by reading, so it says how he writes, not what wins):
- Eight shapes: true story or oddity 5, absurd test 3, fiction or pure story 3, how-to 2, why it happens 2, thought experiment 2, fake invention 1, fix in steps 1. None climbs a ladder.
- They open mid-action (12) or on "If you..." (6). One opens on a question.
- Median sentence about 18 words, up to 28 (Whisper's punctuation, so close, not exact). Gaps between sentences: 0.36 s in explainers and true stories, 0.66 s in fiction. Pace 2.76 words a second.
- The strange thing comes first and the reason after. About 11 of 19 carry on past the answer with another turn.

**What changed, for every short, in prompts and shared checks:**
- `outline.md`: a `shape` from those the picture can carry, `ladder` included. Fiction and how-to are left out: they need acting, and the channel's premise is true things. A `turn`: what comes after the answer, or `none:` and why. A hook that's a moment or an "If you..." setup, up to 26 words.
- `providers/checks.py`: the shape has to be a known one, the turn has to be there, and a bare question only opens a `why_it_happens` short. A line can run to 34 words.
- `script.md`: a sentence runs on while each part leads to the next, and what's strange comes before why.
- `critic.md`: it sends back a first line where nothing's happening, a reason that comes before the strange thing, and a short that just stops at the answer.
- `pauses_ms` in a channel's YAML sets its silences. The owner left the choice to judgment after the trial, so `shorts` is on 350, 450 and 600 ms, its reference's explainers. It's only that channel, and only character shorts: the 500 ms floor stays the default. Short #6's direction was timed to the old pauses, so it needs directing again if it's ever filmed again.
- `.claude/agents/critic.md`: the reviewer has `WebSearch` and `WebFetch`, for every channel, and is told to check each number and named source, about ten searches a review. On the trial, the review took about 10 minutes. The copy in the workspace folder above is updated too.

**Found by trying it, on a rewrite of the woodpecker short** (`data/benchmarks/pace_test/`, voice $0.11):
- **The reviewer with a web search earned its keep.** The sources were real, but "25 times a second" in short #6 isn't the study team's figure: the one place it turned up is an unattributed article. "Many drum more than twenty" is (Schuppe et al., 2021). It also caught a modelled estimate stated as settled, and "a protein linked to brain damage" missing "in people". So the `critic` agent now has them.
- **The physics check found the bird with its beak buried in the bark,** as #6 staged it, from before the check existed. A scan's rest pose isn't where its beak meets a surface. Tipping the bird back about its feet fixed it, as data. Its feet are declared `touching`.
- **The lens check had a bug.** It refused any shot with the lens inside a thing's bounding box and the thing anywhere along the line of sight, even behind the subject. A wide trunk behind a bird got the shot refused. Now only what's in front of the subject counts (`BEHIND_SUBJECT`).
- **A `count` on `sparks`, and a `strength` on a person's `glow`.** 26 chips off a bird's beak is a bundle of planks in a close shot, and full glow on skin is flat paint.
- **A count only ticked by hundreds.** `marks` rounded to the nearest 100, so one running to 20 stayed at 0. It now keeps about three figures, and lands on exactly what it says (`MachineTags.tsx`).
- **`lit` is wrong for a scan's feathers.** At any `cover` that shows, it dyes the head and turns a red crest orange, and full size is where you see it. Thin `rings` with `strength` about 5 said the same thing and left the bird its own colors. At the default strength, their bloom washes a close shot.
- **A person standing upright reaches a wall nose first, and can't lean.** A `knock` on axis [1, 0, 0] snaps a head back, chin forward, so the nose took the hit. The axis for a forward snap is the one square to their facing (up x facing). And a trunk with a flared base has their legs in its roots by 27 cm when their head reaches the bark. That's declared in `touching` and framed out, with no shot in those scenes going below the waist. `touching` switches the mesh check off for that pair, so a head against bark then has to be checked by eye, frame by frame, at full size. A straight post, or a person who could lean, would fix it properly.

**What the owner said of that rewrite, and what his pictures showed.** "the bird is really low resolution, looks bad. The explaintion in woodpecker is not engaing at all. And why is the person standing there all the time lol looks weird. study zach d videos. explain why wood pecker dont get concussions etc, but build it up ofc. I do like teh explaintion of a person hitting the tree tho." So his recording was studied at a frame a second, not only as words (`idea_study/sample_20/frames/`):
- **He goes inside.** The deer's eyeball cut open with light flooding through it. Inside the grape, with labeled electrons and air molecules. The jaw as an x-ray, then with its skin off. An explanation is something you watch happen.
- **A new picture for nearly every phrase.** Not the same thing nearer: another thing, or another place. A sunset for "as light slowly changes". A scale for "185 pounds". The rewrite cut as often as he does, but between the same two subjects.
- **People are only there to do something.** A scientist reacts for two seconds in the grape short, and hands do the rest. The deer short has no one in it.
- **He narrates what happens.** One research word in 19 scripts, "engineers". The rewrite had three in six lines.

**What changed, for every short:**
- **Prompts:** `script.md` says what happens rather than who found out, and gives each part of a sentence a new picture. `outline.md` builds up and then goes inside. `direct.md`, `film.md` and `critic.md` carry the same.
- **`scenes/direction.py` refuses:** a person with nothing to do in a scene over 4.5 s (an expression, a look or a glow doesn't count), and the same picture a third time.
- **`scenes/spec.py` refuses:** a close-up nearer than a scan's texture can hold. `things/build.py` works out `sharp_from` from `texels_per_meter`, at 2 screen pixels to a texel at most. The first woodpecker was seen at 3 to 6.
- **`ghost`:** a thing goes to glass, its edges a thin line, so what's in it shows. Put what's inside in `touching`.

**Why every model looked soft.** `things/get.py` fetched Sketchfab's glb, whose textures are cut to 1024 whatever the model has. The `gltf` download has them at full size, 4096 on the new bird. Things fetched before this keep their old files until they're fetched again: delete the thing's folder under `data/things/`. `tree_trunk` has been. Search for faces as well: the first woodpecker had 5,546, and a free museum scan of a woodpecker has 999,462.

**Using museum scans (`blender/things.py`):** over `MOST_FACES` (200,000) a scan's brought down when it's made, its corners joined first, since a scan can be all loose triangles. `trim` takes a mount off with boxes, in shares of its whole size. `colors` now replaces a picture, as the brain's blue-flecked one was. `big_woodpecker`, `human_skull` and `human_brain` are in `things/specs`, and `sponge_hammer`, `nail`, `tiny_cushion` and `stop_block` are built.

**A scan's pose isn't where it's used.** Measure it (`woodpecker_v3/made_with`), and work out where its parts are from its spots: on this bird the head's turned 29 degrees from the body, so it's filmed from the side it's turned to. A shot on something that slides aims at where it starts unless it has `ahead`, and it's out of frame by the time it stops.

**The reviewer read the full paper and changed the story.** Twenty a second is drumming, a signal, and the film and the safety estimate are of hammering at 2 to 3 pecks a second. A cushion belongs between beak and brain, not beak and bark. "Almost nothing behind it" overstated it: the model gives a safety factor of about 2, under a primate assumption. That became the ending, which ties back to the first line, in place of the protein study, which sidestepped the answer. Its notes are worth reading rather than obeying: it wanted the back of the brain to squash, and nothing here can deform a scan yet.

## How it moves (phase 40)

On Nov 5, 2026 the owner said of the woodpecker short: "the voice needs to be cleasr , like a  4 yr baby can know why", "the animation needs to be better", and "obv u still need to have terms dont be too caveman, check the zach d videos".

**What his motion does, looked at frame by frame** (`idea_study/sample_20/motion.png`). The camera almost never stops. Fingers on a grape, then back across the whole microwave in about a second. A rush in as two grapes touch. A whip round two fighters. Flying up through a dam with its blocks flying off. Bodies move whole. So the rule here since phase 38, a level, still camera, was wrong: it came from one calm reference and the owner's note that a screen wobbled, and the wobble was small jitter. A big smooth move is most of what makes his feel alive. A small swing between two shots of one size is still refused.

**What clear means.** His scripts come out at Flesch-Kincaid grade 7.5 at the median, and the one the owner called unclear at 4.7, so short words weren't what was missing. What lost people was a result with no cause, and phrases that sound like sums ("twice as safe as it needs to be"). `script.md` and `critic.md` now ask for each sentence to say what causes what, with the real term kept and shown. The script is in `woodpecker_v3/draft.json`: 11 lines, 165 words, about 60 s, which is long for him (35 s is typical, 71 s his longest here).

**What the scene language can do now, for any short** (`scenes/spec.py` says how, and `direct.md` says when):
- **A shot travels:** `to` {on, frame, angle, shift, ease, ahead}. `follow` runs along with someone, with their steps averaged out of it, so it stays with them and doesn't bounce. `shift` puts what a shot's on anywhere in the picture, by sliding the lens.
- **People go places:** `walk` with `to`, `over` and a move. The move's own travel comes out of it and the rig carries them instead, with its steps paced so their feet don't slide, and it's refused if that's too far from the pace the move can do. `hits` and `with`: they stop exactly where their body meets a thing, on the step that leads with that part, and bounce back. `slow`: the end of it in slow motion.
- **People do things:** `act` with a move, and `stays` to stay down after a fall. `direct.md` is given a list of moves (`GOES` and `ACTS` in `stages/direct.py`), each looked at on a real person, with the speeds measured. `Jump_in_the_air` (it holds a pose in midair), `Dodge_roll` (it's gone from the frame) and `ClimbUp_1m` aren't offered, and `Yes` holds an arm out: it isn't a nod. Only those moves pass the check, and a stance can't be a move.
- **Things give:** `squash`, along one of its axes about a spot, keeping its volume and ringing out. What rests on something stays on it. `rock` with `part` bends only what's near a spot, as a bird pecks with its head and neck, on a hook and weights worked out from the mesh, its feet staying put.
- **A thing against a crooked surface:** `against`, with `at`, `height`, `way`, `by` and `into`. It comes up to another thing from the side until it touches. With two spots it tips until both do, so a bird's feet and beak are both on the bark wherever that turns out to be. `into` drives a nail in.
- **A window:** `ghost` with `near` and `radius`: only that much of it goes to glass, so what's in its head shows on a bird that's still plainly a bird. The inside of its far side, which would show through in hard-edged patches, goes too, but only where a line of sight passes through the window, worked out in the shader. Hiding it everywhere let the sky through every tiny gap in the scan, as pale specks on the bird's back. Making all its faces agree turned most of the bird inside out, and turning only the strays changed nothing, since they were gaps and not flipped faces.
- **A cleaner scan:** `trim_pale` takes off faces paler than a brightness near a place, such as what's left of a white mount on a bird's toes, which a box would take the toes with. `res` on a Poly Haven source asks for bigger textures.
- **A built thing can be full of holes:** `pores` on a part's material, in meters. The hammer's head read as a bar of soap until it had them, and the joke rests on it being a sponge.

**Found by looking, through the film's own camera, a scene at a time.** Every one of these got past the code that existed:
- **A running man teleported.** The jog clip carries its hips 5.2 m by itself and snaps back at each loop. It was added on top of the walk. A clip's own travel is also the truest thing known about its speed, so it now sets the pace.
- **He went 33 cm through the tree, and nothing said so.** The check looked at people once in ten frames, or only at both ends of a scene with nothing else moving. A runner covers 1.5 m in ten frames. It's every 2 frames for someone walking now, and every 4 for someone acting. And a run pose puts the forehead 46 cm ahead of the feet, and a leg up to 63 cm, so no hand-worked number would have stayed right. That's why `hits` exists.
- **Solving where he stops moved him.** A new stopping place changes the pace, and that changed which step he landed on, which changed where his head was. The step is now fixed at arrival and counted back.
- **His jacket went from brown to black as he ran.** The portrait lights stayed where he started. Lights on someone who walks now go with them.
- **A grey rock appeared under him when he fell.** It was the buried end of the tree: `sky_set`'s floor is only a picture. It now has a floor nobody can see, showing exactly the picture behind it, which hides what's planted below it.
- **A man on the ground floated,** because the horizon's fixed to the picture. He belongs in the ground of the picture, hence `shift`.
- **A brain 7 cm inside a tree, by the check, that was 0.5 cm in.** A point's "inside" by how many surfaces one ray crosses, and a scan isn't sealed. Three rays vote now.
- **A squashed brain sank into the counter,** spreading downward as it spread sideways. Fixed in `_squash`.
- **The glass bird was unreadable:** pale lines on a pale sky. It goes to glass at the head only now, and the far side's patches, which showed through in hard-edged blotches, aren't drawn.
- **A low-poly trunk looked terrible close up,** faceted and blurred, and no check saw it, since the shot was on the bird. It's why the short changed tree, and why `film.md` now looks for it in what's behind the subject too.

**The tree.** `dead_trunk`: Poly Haven's `dead_tree_trunk_02`, CC0, 155,864 polygons, stood upright. At 8K it's 2,858 texels a meter, sharp from 34 cm, against a trunk with 16,724 points and a soft picture. Facing 90, its bark nearest a man is at head height, so his forehead lands first. No credit line is needed for it, though the skull and brain still need theirs. It's what changed the look most, and it took a look at the model at the size it would be used, which is worth doing first for anything big in the picture.

**What it took to make:** the owner approved a silent preview first, half size at 12 samples, 13 minutes for the whole short, so nothing was spent on voice until the motion had been seen. Voice $0.128 for ten lines. The full render took 26 minutes, and 7 more for the four window scenes after the specks were found at full size. The tools are in `woodpecker_v3/made_with`: `pops.py` finds jumps away from a cut and stretches with nothing moving, and is worth making part of the film stage.

**Tests:** `tests/test_precision.py` measures all of this from the meshes in Blender, on a stand-in person: a stop to 2 mm, a rebound, walks that go on from where the last ended, a camera that doesn't bounce against hips that do, lights that travel, a fall that stays down, a squash, a bend that leaves the rest still, a tip that makes both spots touch, a nail driven in by what it says, glass on part of a thing, a sealed-or-not scan, and footsteps in time with a run and a thud on landing. `tests/test_character_format.py` has the checks that need no Blender. A run takes its steps from the clip's own bounce, and a move that takes someone to the ground ends in a thud, both worked out from the clip.

**Not done:** there's no way to tell a director what a thing's surface is like before it's staged, so a scene can come back refused a few times. Nothing shatters. A person can't turn round during a walk. Short #6 and the rewrite before this one were made with what came before.

**Not done either:** finding ideas. `channels/shorts.yaml` has no competitors, so the topic stage doesn't run on this channel, and when it does it shows eight recent titles and asks for three ideas. The proposal, not built: search real sources, write each idea as assumption, truth, source and first picture, check it against his titles and the kit, let a blind comparison with his typical scripts set the bar (untested), and let the owner pick from five. Real viewers are still the only judge, through `core/performance.py`, once a channel's connected.

## What a frame review found (phase 41: how the world works)

On Nov 5, 2026 the owner said of the woodpecker short: "feel like the animation can still be better, like here the brain is outside the sillouhote", "we need to make sure animation adhere to physics and just how the world works", "the idea of the xray is good tho, just need to refine it more", and "yea i think we need to spend more time modeelilng, and have a reviwer that kind of reviews it at each frame, ti woudl ust be a subagent".

**The reviewer.** `render/frame_sheets.py` lays a finished short out at ten frames a second and measures every frame for jumps with no cut there. `prompts/character/frames.md` is what it's asked, and `.claude/agents/frame-reviewer.md` is who asks it: a fresh agent that gets only the frames and the words. `stages/film.py` sends a finished short to it before the owner sees it, and what it finds goes back to the director, at most twice (`MOST_FRAME_REVIEWS`). A pass costs about 200k tokens and 20 minutes on the plan, so fix what it found before asking again.

**What it found, and what that turned out to be.** The first pass found 15 things in a cut the code had passed. Measuring each one found something general nearly every time:

- **Nobody was holding the mallet.** A hand's width of air, and the handle behind the forearm. `_strike` turned the tool so its face met the wall with the fingers pointing back at the person, which put the wrist on the far side of the handle, out of reach. Now a tool's working end leads the hand, whichever way it was modelled (`spin`), and the handle lies in the palm, along the line of the knuckles, in front of it by its own thickness. How far each finger closes is worked out from how thick the handle is (`Person.fist`). A hand that can't reach what it holds, or a swing through whoever's swinging, is refused (`_hands_off`). A strike draws back first, and the body goes into it, with the head on what it's hitting.
- **What was inside things had to be moved by hand,** and could come apart. Now what's `inside` something rides on it, or on the part of it that bends, or on someone's head, and it isn't part of it (`bounds.CARRIED`). A skull can go `inside` a person, and `ghost` with `who` turns their head to glass, so it's his own head reaching the tree that stops his skull. That took two fixes only a render showed: a person's proportions come from shape keys, so marking their head from the mesh's numbers marked their chin (`rest_points`), and glass written to the depth pass hid other glass behind it, from some angles and not others.
- **A brain never reached the forehead it slammed into.** `reach_to` started its rays a meter behind, outside the skull, and met its back wall first. From inside, they start where it is.
- **Soft things were rigid.** `press` is the front of something stopping while the rest keeps coming: it flattens there, spreads, and its back comes on, and inside something it takes the shape of the wall (`_stopped_by`), since the first try bulged a brain through a skull and the check said so. `gives` on a `strike` dents a soft tool round what it hits, on a mesh cut up finely enough to bend, and it springs back. `wobble` on a `rock` is what's soft being set going.
- **Faces went red-brown.** The lights never turned with the person, so someone facing the tree was lit from behind. They do now, and in a real place they're a fifth as strong (`light`), since a place lights itself.
- **The jog twisted like a towel:** its shoulders turn 41 degrees each way while its hips stay still. A moving clip's twist is brought down to what a body does (`MOST_TWIST`), however it was made.
- **Bodies fell stiff.** Whoever goes down now hits the ground and their head rings with it (`LANDS_HARD`), their hands go slack and their chest still rises and falls (`_gone_slack`), there's an `out_cold` face, and their patch of shadow stretches along where they lie. In slow motion so slow it's frozen (`FROZEN`), they stay as they are, rather than getting up as the walk ends.
- **The set showed.** A counter in a room goes back 6 m. The first forest's ground read as a grey road: Poly Haven's `woods` sky on `forest_leaves_04` looks like a place. Chips of wood are torn slivers rather than rectangles. A thing lit up in a place comes to whatever the scene opens on. `dim` takes a place dark behind an x-ray.
- **What this short got wrong in its direction, rather than in the code:** rings with nothing hitting, things sliding in from nowhere, a skull in the air with no body. `direct.md` now says so for every short: nothing moves without a cause you can see, what's going keeps going until something stops it, and rings and chips come only from something hitting something.

**The second pass, and the owner's notes on the cut before it.** "btw im also looking at hoiw the person is holding a sponge, its really weird lmfao", "u need to explain why sponge was introcued here, need to connect between scenes so it isn't confusing", and "stil need to avoid situations where the brain goes outside the sillouhoute".

- **The outline, from the lens.** The check asked whether something was surrounded, and a scan has hollows: a brain could be surrounded and still sit outside the head's outline in the picture. `_outside_outline` now draws a line from each shot's own lens through the points of what's inside something, every 6 frames: every line has to meet what it's inside, or the scene's refused, with how far it is and in which shot. A press inside something takes the shape of the wall, so it can't go past it.
- **Each picture comes from the one before.** `direct.md` says so for every short, and `frames.md` asks "Why is that there?". `turns` makes part of a thing into other stuff: the bird's head goes to the same sponge as the hammer on the word "soft", and squishes on the bark (`press` with `near` and `radius`, and `wobble`), so the hammer that follows has a reason to be there. `script.md`: a comparison comes after what it's standing in for.
- **What moves is carried.** Brains glided across a table with nothing moving them. A thing `on` something that moves now goes with it, so they ride a crash-test sled on a rail, which reaches a steel block. That also stops them standing on a narrow base.
- **A body keeps coming when its head stops.** It stays in its stride, its back and neck bend so its head stays where it stopped, its body comes on as far as there's room (`CARRIES_ON`, measured), and only then is it thrown back. Rings go where they touched (`id:touch`), and a blow throws the head back rather than into the tree.
- **A blow's drawn back over the shoulder,** rather than past the face, and the head looks at what it's hitting, allowing for how far the stance already has it bowed. A forearm turns with its hand, or its sleeve tears at the wrist: a very small `orient_weight` on the arm's IK does that, measured, with the wrist within 2 mm.
- **Slow enough to see.** The head hit runs once slowed enough to follow and again as slowly as it takes to watch the brain go, at the speed it was going, from the back of the skull. `covers` starts someone a set distance short of where they stop, as at 1 cm a second a rough start would have them flying. Chips fall at real speed unless the shot's in slow motion (`slow` on `sparks`), and `pit` gives them a hollow to come from. `gentle` on a `rock` slows as it comes home, for the version that doesn't happen.
- **The sky.** A place's sky is held to `PLACE_SKY_MOST` for what the camera sees, and lights things with all it has, so a patch of real sky doesn't bloom over a man's hair. Its ground is fetched at 4K, as someone lying on it is seen from close up.

**The third pass.**

- **A bird's tail braces on the bark.** The second pass left this out, as this scan's legs held it 19 cm off. It reaches from the upper side of a leaning trunk, with the head turned on its neck (`yaw` on `bends`), since the scan's head is yawed 58 degrees to its side. A spot on a part bent at rest goes with the part (`_bent_spot`), and a peck goes the way the beak points, whichever way that is (`toward` on a `rock`).
- **Slow motion is one unbroken beat.** Showing a hit a second time, slower, read as the picture jumping back. `ramp` on a `walk` slows smoothly into slow motion, for a short that wants that, though the fourth pass found this short's slowdown read as a head easing to rest, so this one holds one steady speed.
- **A front pressed against a wall goes flat on it,** rather than only dimpling (`PRESS_FLAT`, `PRESS_SPREADS`).
- **Smoothing a scan keeps its size.** Plain smoothing shrank a bird's head by 2 cm, which put its skull through it. It's Taubin now, which swells back what each pass shrinks, welded across a scan's seams, with the rims of its holes pinned. A test caught that the rim test was treating every edge as a rim, so smoothing had been doing nothing at all.
- **Being surrounded is lines through a point** meeting a thing on both sides, as counting a ray's crossings gives false alarms on a scan full of gaps.

**The fourth pass.**

- **A swing you can see.** A backswing past the far side of a head went behind it and read as a mallet through his face. It's the near hand now, seen from the side the camera can see it clear of the face, with a cut mid-swing into the hit. How to frame that is in the direction, and the code's part is that a blow accelerates all the way, rather than arriving in its last few frames.
- **The hit stays on screen.** A cut straight after a hit hides it, so the slam plays out in the shot it happens in, with what's being hit in the frame.
- **Glass isn't in focus by itself.** It has no depth of its own, so depth of field blurs it as if it were as far off as what's behind it, and an x-ray's outline went soft while the bark beside it stayed sharp. That's refused in words now, with the fstop it needs (`_glass_in_focus`). So a forest behind an x-ray is darkened with `dim`, and can't also be thrown out of focus.
- **An x-ray is still a solid thing.** `fill` on a `ghost` keeps some of what it was, so it isn't only thin lines over a busy forest.
- **One look per thing.** `smooth` on a cast member takes a human brain's folds off it, for a bird's. `pink` in the direction keeps a brain's colour when the place goes dark.
- **`back` on a `rock`** is how much of it is drawing back, for slow motion that looks slow, and chips and rings slow with it.
- **The bench stands in the same woods,** with one sled throughout, a cradle for what it carries, and arrows that only appear once it's hit. What's in the direction goes in `direct.md`'s rules already: nothing moves without a cause, and each picture comes from the one before.

**The fifth pass.** Asked to say how serious each thing was, rather than fill a quota, it called five serious, and they were all to do with what the picture was explaining rather than with how it was made.

- **A stop you can see needs something moving first.** At a speed chosen to match the brain's slow crossing, the head hardly moved, so "when your skull stops" had no stop to see. A head's seen to travel, and to stop dead, and slow motion doesn't have to hold one speed: the brain picks up speed as time comes back, and hits hard, with a squash of 30% that springs back in half a second.
- **The same stop, on the same tree.** A black block on a deck was a second world nobody had been shown. The rail's now up on trestles, on the side he ran at, and it meets the bark at the height his head did. That needed a wall across the sled's front, since a trunk's round and only its middle would have reached a brain: the sled hits the tree, and its wall stops what's on it. That's what a crash sled is.
- **What's soft sinks.** `sinks` on something `on` something else brings it down into it, so a brain lies in its cradle rather than balancing on its stem.
- **The wrong idea and the truth need different pictures.** "You'd think it has a shock absorber" and "it absorbs almost no shock" were the same dark x-ray. The spring you'd imagine is now lit, so you can see it, and it isn't there next time.
- **"Twice as fast" is a faster strike,** the same swing and the same spacing, in half the time (`back`), rather than more pecks.
- **A cut in the middle of a bounce makes it read as a spring.** Measured, he comes off a tree at 1.3 m/s and goes a third of a meter in 0.4 s, which is fine. Seen across a cut from another side, it looked like a body's width in a tenth of a second. A hit's one shot, right through the bounce, and it's in `direct.md`.

Measuring also found what looking wouldn't have: a floating prop's position is where its underside sits, so giving a rail legs lifted it 1.7 m, and it moved its middle by 17 cm.

**Still short when this cut went to the owner.** The sixth pass called five things serious, and these are what's left to do:

- **The brain's crossing cheats.** The words leave 2.3 s between "stops" and "slams" for a 3.5 cm gap, so the brain goes more slowly than the head was going and speeds up into the wall. For it to keep the head's speed, the head has to reach the tree just before "slams", rather than on "stops".
- **Whose brain it is.** After "its tiny brain", a big brain on a sled could be the bird's until "Yours" at 44.8 s. One word in the line would settle it: "your brain".
- **The brain on the sled** was measured squashing by 28%, but the reviewer reads it from its sheets as tipping whole, and the cradle under it doesn't dent. The tiny brain beside it comes in unexplained and doesn't react.
- **The second fall** tucks its knees with both feet off the ground: that's the stock clip, and it wants a fall made for someone knocked out.

The reviewer also suspected the brain went through the skull at 10.2 s. Measured on every frame of all five x-ray scenes, rather than the check's every sixth, it stays inside the outline.

**What the owner said of this cut (Nov 6).** "its much better now", then "the transition to sponge isn't good still, it shouldt say 'therefore there is no cusion since sponge wouldnt work' or smt like that, ofc it needs to be more streamlilned". The line had passed `script.md`'s comparison rule by saying "hammer" before "sponge", and the picture's link (the bird's head going to sponge) couldn't make up for words with no link. So `script.md` now asks that the words say what a comparison stands in for (the thing, what it would do, then what that's like) and that each line pick up what the last one just said, and `critic.md` checks both.

The owner approved the three new lines, $0.038: "so it has no real cushion." / "Because a cushion would soak up the hit, like hammering a nail with a sponge." / "When the front of your brain stops, the rest keeps pushing on it." The bird's head now goes to sponge on "cushion" and squishes on "soak" and "hit". `woodpecker_v6.mp4` (59.9 s) has those lines, and it tried something else: the head reaching the tree on "keeps", about 1.7 s after the word "stops", with the brain crossing at the head's own steady speed.

**The seventh review, of v6, called one thing serious, and that was it:** the words said the skull stopped and the brain kept moving while both were still gliding on. True speeds and words that run ahead of the picture are worse than a slowed brain, because the picture follows the voice. `woodpecker_v7.mp4` has the fixes, all in direction and one thing's spec, with no new code:

- **Time can slow down after a hit.** The head stops on "stops", seen moving and then stopping within one shot, with its ring. The brain goes on at the head's speed for its first 9 mm as time drops, then crosses alone at one steady speed, hitting on "slams". Easing into the hit was what read as a lurch.
- **"Your brain" has a picture.** Line 8 opens on his glass head at the tree, then cuts to that same brain at about the same size in the picture, on the sled. The reviewer had called the jump to the sled the weakest in the short.
- **A seat that isn't a cushion.** The grey cradle looked like padding seconds after "no real cushion", and only the big brain had it. It can't simply go, or a brain balances on its stem, as `sinks` above explains, and dark colours still looked plush, because of its round edges. So it's a bright steel `seat` with sharp ones.
- **A shot of a thing on a run starts with it in the picture.** "A longer brain means" opened on 0.7 s of empty rails, so the sled now waits in the shot with both brains on it, and goes on "means". The first run is shorter and its side shot wider, for the same reason.
- **"Twice as fast" is.** Pecks were the same 0.6 s each before and after the words. From "fast" on, they take 0.29 s.

**Judge the reviewer's notes by measuring them.** It said the bird holds still with its beak up over "do this all day". Frames 0.07 s apart show about four pecks a second with chips: its sheets sample every third frame, and a snap takes two frames, so it mostly sees the beak drawn back. A film's cache is kept by each scene's JSON alone too, so changing a thing's spec means deleting the scenes that use it (it left the old pad in two sled scenes until they were cleared).

`direct.md` now has three of these for every short (the picture happens when the words say it, a shot of something on its way starts with it in the picture, and nothing in a picture contradicts what's just been said), and `frames.md` tells the reviewer that a quick repeated move can fall between its frames.

**A focused review of v7's four changed moments, and what measuring it found.** It still called the head's stop unreadable, and two causes were real:

- **A hit's rings and chips were round the wrong part of him (every video).** `touches` was the point of the body furthest on, and in a slow-motion pose that was his swinging hand, at [0.308, 0.082, 0.842], past the side of the tree and out of the shot. Two reviews had reported no ring there. It's now the part nearest what he ran into, measured by rays, and it's tested on a slanted wall. The other two hits in this short were already on his head, so they didn't change.
- **A push-in carries a stopped thing on across the picture.** The camera now goes still on the stop, and the close-up of the gap is still and tighter, so the brain's the only thing moving. `direct.md` says so for every short. A squash taking 0.12 s after a 2 s crossing read as a lurch too, so it takes 0.3 s.

The same review also led to the sled being seen to reach the tree before the cut, with the big brain still pressed through "the rest keeps pushing", and to "A longer brain" opening close on both brains.

The owner on v7 (`woodpecker_v7.mp4`): "yea this looks good". No fresh reviewer has seen that exact cut: the last round of fixes was checked on frames from the final file.

**A take can end on the next line's first sound (every video).** Of v8 the owner said "its good but the voice has weird pauses, like s--- so...". Line 6's take ended "...with a sponge.", then 0.28 s of silence, then 40 ms of rising hiss where ElevenLabs had started on the "S" of "So what", the next line, which it's shown for flow. The trimmer kept everything up to the last sound, so the cut said "sponge... s- ... So". It was the only take of the eleven with one, and v7 had it too. Every pause inside a line was at a comma (0.13 to 0.26 s), the gaps between lines measured 0.41 to 0.43 s against his 0.36, and the whooshes under the voice were too quiet in the mix to hear. Now `narration._ends` drops a scrap of up to 0.2 s at either end that 0.15 s of silence cuts off from the words, unless the voice's timing has a word starting in it. A stop inside a word, like the closure before the t of "it.", is about 0.07 s, so it's kept. `woodpecker_v9.mp4` (59.6 s) has line 6 cut again from the same take, for nothing, and everything after it 0.28 s sooner: only the sponge-hammer scene was filmed again, and on frames from the final file the hammer still lands on "sponge" and the cut comes on "So". It goes with `woodpecker_v9_caption.txt`, the same caption. The owner on v9 (Nov 7): "looks good", so it's the cut to post. The tools that found it are in `made_with/` (`ends.py` checks each take's two ends; `mix_vs_voice.py` says whether an effect can be heard over the voice).

Still short: the second fall and the man's rebound (the stock clip), the mallet crossing his face in the picture at about 30 s, nothing that shows the bird's pressure against a limit at the end, and the small brain not being tied to the bird in the picture.

**The reviewer always fills its cap, unless told not to.** Each of the first four passes came back with 15 findings, of falling severity, so the count says nothing about whether a cut's ready. Ask it to rank them, and to say what's a blemish: stop when the top few are no longer things a viewer would call wrong.

**How to look at a model.** The film's own camera hid most of this. A scratch script that stages a scene with its checks off and renders from any side, close up, found the fist, the pinky, the lights and the head, and it's the first thing to reach for.

**Tests:** `tests/test_precision.py` has one for each of these, named for what went wrong, and the stand-in person in `tests/blender_fake_person.py` has hands and feet now.

## How ideas are found (phase 42)

The owner, on Nov 6, 2026: "i can post it myself, i just need the vbideos and good ideas". The topic stage only proposes variants of a competitor's recent hits, `shorts` has no competitors, and every short so far had a hand-picked topic. So nothing went looking.

- **`run.py ideas fetch`** (`ideas/leads.py`, free, no account) gets Wikipedia's lists of common misconceptions, its list of Ig Nobel winners, and YouTube's search suggestions for how people ask things. The winners since 2001 are in tables, which Wikipedia's plain-text extract drops, so pages are read from their HTML. `run.py ideas show <part of a page's name>`, or `show asked`, prints them.
- **Cards** (`prompts/character/ideas.md`, in `data/ideas/cards.json`): the session reads the leads and writes each idea as its hook, what people think, what's true, the chain of causes, the turn, the first picture, how it goes inside, what's needed, its shape and its source. Most leads go nowhere, and that's expected.
- **`run.py ideas check`** (`ideas/cards.py`) refuses a card with something missing, a bare question for a hook, no link for a source, or terms the reference's titles already have (all of them in one title, singular or plural, whole words). Then a fresh reviewer with web search tests the claims, since whoever wrote a card doesn't grade it.
- **There's no score**, because a blind test couldn't pick his winners from their titles better than a coin flip. The owner picks, and real views decide. Keep it that way until something beats a coin flip on held-out pairs.

What the first run taught:

- **A word count isn't a reading.** Of the first shortlist, his titles ruled out spaghetti ("Breaking Spaghetti Without Extra Pieces", which had wrongly been called free), train wheels, exploding trousers, dead spiders as robots, pigeons in war, why bees die after stinging, cracking knuckles, falling elevators and falling through ice. "Straw" also matched, on a potato. So read the near titles, and make `terms` the real subject.
- He's covered a lot: 4,147 uploads. The Ig Nobels since 2001 and arguments that build by steps are where free ground showed up.
- The check says a card can be used, not that it's good, and it says so.
- **Every card of the first 14 needed changes from the fresh fact-checker,** and one was dropped: a full bottle does break more easily, but the paper says it hits with about 70% more energy, so "you'd want the full one" was unsupported. Most of what it caught was reasoning the writer had added to a source, which `ideas.md` now warns about.

The same check on the woodpecker's words found the argument sound, and four lines firmer than their sources: "what protects it" (others are listed), "enough for a concussion" (it's pressure against a threshold, and whether pressure causes concussion isn't settled), "not by much" (the authors call the margin considerable), and "slams into it" (the CDC says bounce or twist). The owner said to fix the first three ("yes fix"), $0.048, and `woodpecker_v8.mp4` (59.9 s) is the cut to post, with `woodpecker_v8_caption.txt`. The last is left, since it's the plain version of the straight-on case and the picture rests on it. The longer line 7 needed one more cut, at "probably", as a shot of 4.2 s was refused. V8 was checked on frames from the final file, and no fresh reviewer has seen it.

**A short lands on a real invention where one exists (Nov 7).** Asked whether the straw short was built around an invention or only a hypothetical, then: "we need to connect to an actual invention, and say 'congrautations you buildt this this this', similar to the hammer on nail video". That's his pile-hammer short in `idea_study/all.txt` (a nail and hammer made a hundred times bigger, each fix bringing the next problem, ending "Congratulations! You've just invented the Diesel Pile Hammer"), and the house-drain script beside it works the same way, naming each part as it goes in. So, for every short:
- `you_invent` is a shape (`checks.SHORT_SHAPES`, `outline.md`): the viewer builds a real invention in their head, as "you", each fix a real part or the real reason it works, named as it goes in, ending by telling them what they've built. `outline.md` says to choose it whenever the science leads to something people really built.
- `script.md`: it's told to "you", each fix causes the next problem, and the last line congratulates the viewer by the real thing's name, in our own words, never a sentence of the reference's. `critic.md`: every step has to be how the real thing works. `ideas.md`: look for the thing people built from an idea, and name it in `turn`.
- The straw short is rewritten on it (`data/benchmarks/straw/draft.json`, the first version kept as `draft_v1.json`): the straw too tall to drink through, a pump that stalls at ten metres, the air's weight as the limit, mercury to make it fit indoors, the level dropping before a storm, and "Congratulations, you just invented the barometer". The redwood half had no invention to land on, so it's left for a short of its own. A fresh reviewer with web search found every claim held, and sent back five fixes, all applied: the chain broke between "the height shows the push" and "won't fit in your house" (nothing said why you'd want one at home: Torricelli wanted to see the air's weight change, so line 5 says that now); "fourteen times as heavy" with no "as water"; "a short tube" (it's about a metre and sealed at one end, or nothing drops); a storm moves the mercury 1 to 2 cm, so the picture creeps rather than slides; and the fact's dates (1643 to 44). 165 words, at the checks' limit.

## What fills things, and air (phase 43)

The owner, after the barometer script: "lets start next idea". Its pictures are water climbing a straw, air pushing on a drink, mercury standing in a tube over a dish, and the level creeping down before a storm, and the scene language had nothing for a liquid or for air (phase 38 said so: "It has nothing for water or anything poured"). So these are new, general, and in `scenes/spec.py`'s docstring:

- **Glass** (`clear_glass` in the palette, or `clear` on a part's own paint): you see through it where it faces you, and its edges catch the light. It's blended, which is clean at any number of samples. Dithered glass is in focus but grainy even at 64 samples, and EEVEE's own refraction drew an empty tube as a solid grey rod, both tried on a look test. Blended glass has no depth for a camera to focus on, so a thing with glass in it brings in the same fstop rule as an x-ray (`_glass_in_focus`, which now reads `glass` from the things menu). Its mirror is toned down, since at a grazing angle a full one is the studio's white: a dish's base read as a white coaster.
- **A liquid** is a part of a built thing marked `"liquid": true`, shaped as it is when full. `blender/liquid.py` cuts it off at a height in the world, frame by frame, so its top is flat and level whichever way what holds it is turned. Seen from above, its far inside wall is shaded as a surface facing up, a little darker than its sides, since a mirror facing the studio read as milk. A full one is cut a hair under its own top too: a mesh's own top shaded in a starburst. It isn't solid (`bounds.meshes_of` leaves it out): a straw goes into a drink, a tube stands in mercury, and nothing rests on it.
- **`level` on the cast, and `fill`:** meters above the bottom of its liquid, or above the top of another thing's liquid (`above`), as a straw starts level with the drink it's in, and mercury stands 76 cm over its dish however the dish changes. `fill` moves it, with an ease.
- **`pour`:** a stream straight down from a spot, narrowing as it speeds up (r = r0 (v0 / v)^0.5, since as much passes every point each second), its front falling from the spout under gravity and its tail falling away after. Its foot follows the level it lands on. It's refused if it isn't over what it fills or something solid's in the way, and the checks refuse a pour with no `fill` rising while it pours, or into something that starts full.
- **`air`:** balls in a box going every way at once at a spread of speeds (Maxwell's, about `speed` on average), bouncing off everything solid and off the top of every liquid, which is the push you can't see. `leave` draws some off through a point, as a pump or a mouth does, and they're gone once through. `thins` is how much higher there's half as much: a pull down on every ball keeps it that way, as gravity does the sky's, rather than a spread that drifts. The box's sides are open air, so a ball wraps round, but only to somewhere clear; its top and bottom are unseen lids. The first version wrapped top to bottom too, and the measured test found balls inside a dish's glass base: a ball leaving the top came in at the bottom.

**Tried on test things** (`scratchpad/baro/try_liquid.py`, not kept): mercury dropping from 99 cm to 80 cm, 76 cm above its dish; a jug pouring into a dish, its level rising 1 cm to 2.6 cm; 400 balls round a glass of water. The checks refused the first pour, into a full dish, in words.

**Tests:** `tests/test_precision.py` has the checks (a level counted from another's top, circles refused, a pour that has to rise, air's box and what leaves, glass needing depth, `leave` times moved to a scene's own clock) and, measured in Blender, a liquid's top exactly where it's said as it fills and as what it's counted from rises, a pour refused when it would miss, a tube stood in mercury not refused, and no ball ever inside anything solid or under a liquid's top.

**Not done:** a liquid's top is flat, with no meniscus or ripples, and a level doesn't move by itself: the director says when, and `direct.md` says it has to have a reason in the picture. Nothing splashes. A pour only falls straight down, not in an arc off a tipped lip. Balls don't hit each other. A held thing can't tip to pour, since grips are fixed poses.

## The barometer short (phase 44)

The owner: "go", on the plan to build the barometer's things, direct it, and render a free silent preview before any voice. Everything's in `data/benchmarks/straw/` (gitignored), with the scripts that made it in its `made_with/`: `make_things.py` writes the things, `direction_baro.py` the direction, and `short.py` stages, looks and renders through the stock code, as the woodpecker's did.

**Its things** (`things/specs/`, all built from exact shapes, free): a four-storey brick block of flats and the street under it, a giant clear straw with a red stripe, clips and a metre scale, a glass tank of water, a vacuum pump on a frame and its flywheel, a top-pan balance, a tall air column and a ten-metre water column, small mercury and water cylinders, a house, a metre-long mercury tube, a dish of mercury, a separating funnel and its tap, two lab stands (one with a centimetre scale), a wall with a window, a stick barometer and a panelled wall. Heights that have to meet are worked out once from what was measured: Walt's mouth, standing with his stance slowed to `life` 0.03, stays within 6 mm of [0.008, -0.209, 1.4075] from where he stands, so the straw's end is put there, and the pump's intake is put on the straw's end with its feet on the roof. The roof is the scene's floor, at 0, with the street 12.85 m below it: a place with no ground has nothing at 0, so a man can stand on a roof with no new code.

**What making it found, fixed for every short:**
- **Every thing's look sheet showed only its top half.** The sheet put a thing's middle at the floor, and the floor `sky_set` has had since phase 40 hides whatever's below it. Things now stand on it. Every sheet since phase 40 was cut this way.
- **Glass blocked the lens check.** A shot into a glass tank was refused as the tank being in front of the lens. A thing that's all see-through no longer counts (`_see_through`, parts marked `clear` when built).
- **A pour into something empty was refused as missing it,** since it tested a point under the bottom of what it fills.
- **Air needed somewhere to start.** `inside` starts the balls in a thing's hollow (a straw, a column) rather than anywhere clear in the box. Whether a point is inside something solid is asked of each part by itself, since crossings counted through parts that overlap, a road under a pavement, said inside everywhere. And a set's floor only counts where it really is: on a roof, 0 is the roof.
- **A shot where only a liquid fills or air moves was refused as held still.** `fill`, `pour` and `air` count as movement, and air and a spin go on until they're stopped.
- **A dish put `on` a stand landed on its top bracket,** since `on` drops a thing from above onto the first thing under it. Things that sit inside a stand are fixed `to` a spot on it.
- **What I saw on the first preview's sheets, before any reviewer:** a clear straw in front of a white scale read as a white pole, so the scale behind it is dark with white marks, and the building is brick rather than near-white plaster; a column of water read as glass, so water is a strong blue and less see-through; a tube full of mercury looked like an empty one in a pale room, so mercury is darker than glass; balls drifting past a lens inside their box were big blurred blobs, so the close looks at air have a longer lens and the box stops short of it; and an opening crane up a wall of windows said nothing, so it pulls back from the tank to the whole building with the straw up its front.

**The frame reviewer on the second preview** (14 things, four it said a viewer would stop believing), and what measuring them found:
- **"The straw sticks out of his lips, level, with nothing holding it."** It's held up the wall by clips and bends over the parapet, but the close-up only showed its end coming at the lens, a dark wedge across his nose. Now it's from his side, with the bend in the picture. His stance, `Idle_relaxed` slowed to nearly still, held its first frame: legs apart and fists clenched, like a fighter. He folds his arms (`Idle_arms_folded_waiting`); his mouth moved 4 mm.
- **"The tube stands in the dish with nothing holding it."** The scale board stood behind the tube and hid the rod and clamp, and its foot went into the dish. It's beside the tube now, above the dish's rim.
- **"Water vanishes across the cuts."** The man's water dropped to nothing at the cut to the pump, and the explanation after the pump started the straw empty and filled it again. Now his water falls back as he gives up, and once the pump's raised it, it stays up: the explanation shows the push on the tank holding it there and the empty straw above it.
- **"The clamp slides down the rod."** It was the camera rising with the mercury: the clamp moved and the mercury's top stayed put. The tube's shot whole, still, filling.
- **"The flip is never seen":** true, and left. Nothing can hold the tube to turn it, as grips are fixed poses, and an open tube of mercury turned over would empty unless a finger closed it.
- And: the tube through the house had an open top, which no column of water could stand in (it's a sealed tube now); the pump's wheel was on the side the camera didn't see; the view through the window changed place between sunny and stormy (the same pure sky now, clear and then overcast); a gold flash on "barometer" with nothing causing it (gone); a straw's stripe seen through the clear plastic read as a wire inside it (gone); the balance's shots were too close to show what was being weighed (wider, with a staff on the water); the lab's cylinders were too thin to stand (9 cm across now). Its tall columns on the big balance are left: they're a picture of the sky's weight, not a thing anyone could stand on a pan.
- Air balls cast shadows, which read as dirt on the glass. They're a picture, not things: no shadows now (`liquid.Air`, every short).

**Then, at full size:** a perfectly clear straw vanished against the sky (it's frosted and grey-tinted, as a straw's plastic is, and his close-up looks down at it with the roof behind); a 14 mm tube of mercury in a wide shot of its stand couldn't be seen filling (two still shots close enough to see it: where it passes the middle, and where it reaches the top); a glide up the column of thinning air was mostly empty glass (one glide up past both columns, the water stopping at 10 on its staff beside the air going on); and through a window just above the counter, the counter showed carrying on outside (the window starts higher).

**What it took:** the silent preview renders in about 9 minutes at half size. One frame review, about 120k tokens and 9 minutes. Nothing spent. **Not done:** the voice; the frame reviewer on the voiced cut; the tube can't be seen turned over, as nothing can hold it.

**The direction:** 15 scenes on the estimated clock (60.6 s), each picture on its words: up the straw to the man sucking on it, the water rising a little and stalling; the pump, and the camera riding the water up ten metres to where it stops; the tank with air as balls, those in the straw drawn off up it and those outside pushing the water up; a balance with a column of thinning air against ten metres of water; the height as the push; a house, then the same house with the column through its roof; a funnel's tap opening and mercury pouring into a metre tube; the tube standing in its dish; a short glass of mercury balancing a glass of water fourteen times as tall; the mercury dropping to 76 cm with nothing above it and balls pushing on the dish; a window, clear and then overcast, with a few balls drifting off and the mercury creeping down 2 cm; a stick barometer on a wall. No shot has hands: the tube is shown full in its dish after the pour, rather than turned over, since grips are fixed poses.

## Straightforward (phase 45)

The owner on the barometer's silent preview: "i mean animation is good, but remember this is for educating caveman like, it needs to be more straight forward, and also maybe just becuz i cant understand without the voiuce. look at to samples we generated like the conussion and nail thing, those are star references." The concussion short is the woodpecker (`woodpecker_v9.mp4`); the nail is the pile-hammer rebuild of reference A (`data/benchmarks/pile_hammer/`, internal only).

**What the three looked like side by side** (a frame every 1.5 to 2 s):
- **One thing big in the middle of nearly every frame, and one you'd know:** a man, a bird, a brain; a nail, a hammer, a crane. The barometer's frames were often a brick wall with a thin line on it, balls that read as fizz in the water, or two glass columns against the sky.
- **One object followed all the way.** The nail grows into the pile and every step adds a part to it. The barometer went straw, tank, balance, house, lab tube, window, wall: seven subjects in 60 s.
- **Every step a thing seen going wrong or working:** too heavy to swing, too slow to lift, the explosives too dangerous. The barometer's middle was ideas to take on trust: the air weighs as much as ten metres of water (two columns on a balance), and you want one at home to see if that changes (a house where nothing happens).
- **Names and failures on the picture.** Reference A labels each part as it goes in (RAM, ANVIL, CYLINDER) and marks each failure with a red cross (TOO HEAVY TO SWING, TOO SLOW). The character shorts could only count a number.
- **One step a line.** The pile hammer runs about 10 words a line and the woodpecker about 15, none over 22. The barometer's ran 18, up to 24, most carrying two steps.

**A silent viewer, tried and not kept as a gate.** Fresh agents watched each short as one frame a second, first with its captions and then with them covered, and scored how easy it was to follow. With captions the woodpecker scored 6 and the barometer 7; without, 4 and 5. An agent reads every caption at leisure and works out what a person scrolling doesn't, so the score doesn't reproduce the owner's judgement, and it isn't in the pipeline. What they said they couldn't follow did agree, both times, with what's above: the barometer's balls and balances and the house, and the woodpecker's brain on a sled and its "stays under that by about half".

**The rules, for every short:**
- `prompts/character/outline.md`: **Straightforward, for anyone, even with the sound off**: one goal or one question all the way, each step seen going wrong or working, one thing followed as it changes, few places and new things.
- `prompts/character/script.md`: **One step a line**, 4 to 16 lines of 3 to 22 words (`checks.SHORT_LINES`, `SHORT_LINE_WORDS`, from 14 lines and 34 words), and **it makes sense with the sound off**: each line's `shows` makes its point by itself.
- `prompts/character/critic.md`: **Is it straightforward?**
- `prompts/character/direct.md`: **It has to make sense with the sound off**: stay on the one thing, keep it big and plain, a thin thing shot close against something plain, a person seen doing what they do, a label as the words name a thing, a cross as something goes wrong, no stand-in for an idea that doesn't come from the thing it stands for.

**Labels and failure marks** (`scenes/direction.py`, `stages/film.py`, `blender/stage.py`, `blender/run.py`, `blender/tracks.py`), drawn by the overlays reference A's rebuild already had:
- `marks` take `label`, `fail` and `question` besides `count`. A label names something in the scene playing then (`"on": "tank:surface"`), a word or two, inside one scene, and the check says when it isn't.
- The film step gives each scene the aims its labels name (`anchors` in the scene language). The stage keys an empty to each aim every frame, Blender's run exports where each is on screen and whether it's seen, and the short draws the label on that track, hidden while it's out of sight. A thing's own surface doesn't hide its label, nor does glass or a liquid.
- Measured: a dish's middle under mercury, in a tube's glass, tracked in the middle of a shot on it and seen in every frame.

**The barometer's script, rewritten** (`data/benchmarks/straw/draft.json`; the last is `draft_v2.json`, its preview `straw_preview_v2_no_voice.mp4`, direction `direction_v2.json`): 15 lines, 160 words (inside the check's 165, over the prompt's 150: one step a line takes a few more), about 62 s on the estimate. One straw from start to end, and every step seen: the water barely rises (TOO TALL); a pump, and it stops dead at ten metres (STOPS); sucking only empties the straw, and the air outside pushes the water up into it; the higher it climbs the heavier it gets, until at ten metres it's as heavy as the air can push; one day the water sinks and a storm hits, since the air pushes less before one, so the straw warned you; it won't fit in a house; mercury, nearly fourteen times as heavy, held up in a column fourteen times shorter, 76 cm, the tube sealed and the pump taken off; the barometer. A fresh reviewer sent the first rewrite back with six points, all taken: why ten metres was told, not shown (now the weight that grows as it climbs); the storm came reason-first (now the water sinks, then the storm; Guericke's ten-metre water barometer foretold one in 1660); a barometer has no pump (now it's sealed and the pump comes off); 13.5 to 13.6 isn't 14 ("nearly"); the air changed from balls to arrows between lines (balls throughout, the arrows on them); and "drink" and "water" for the same thing.

**Voiced and directed.** The owner: "yea", to directing it and to voicing it first (about 15¢) so the preview has sound. Voiced for $0.147 (865 characters, the owner's clone on `eleven_v4`): 65.5 s. Directed in 18 scenes on the voice's own word times (`made_with/direction_baro.py`) and rendered half size with the voice as `data/benchmarks/straw/straw_preview.mp4` (`short.py preview` now puts the voice on when there is one, and the labels on their tracks). What the pictures are: up the straw to him on the roof, labelled STRAW; the straw in his lips as he sucks, from where it shows; the water rising a metre and falling back, TOO TALL; the pump, PUMP; riding up with the water, a count to ten, STOPS; the straw gone to glass against a darkened street, full of glowing air the pump draws up and out, NO AIR; the tank from above, air bouncing on it and two red arrows pressing down either side of the straw, AIR; the water climbing again with an arrow riding on its top labelled WEIGHT, growing at each cut until it's the size of the air's arrows (AIR'S PUSH); the top sinking below its 10 M mark on a fine day, then the building under a dark sky; fewer balls and smaller arrows on the tank; STORM WARNING by the sunk top; the column through a house's roof, WON'T FIT; MERCURY on a balance, a count to 13.6 TIMES AS HEAVY; a full tube in its dish, the mercury falling with a count from 98 to 76 CENTIMETRES, EMPTY above it, red arrows on the dish; the barometer on a wall, BAROMETER.

**What directing it found, fixed for every short:**
- **Air with no room for its balls was drawn as nothing,** silently. A ball only starts one and a half radii from anything solid, so 7 mm balls in a straw 1 cm in radius never started. The stage now refuses air that finds room for under half its balls, and says why (`MOST_AIR_SHORT`, `liquid.ROOM`). Measured: air in a tube too narrow for its balls is refused.
- **Air drawn off through a point vanished at once from a box as narrow as a tube,** since what's drawn off is gone once it leaves the box. The scene language's notes now say so: make the box reach past what holds the air, and keep a ball under a third of a tube's bore.
- **Labels and crosses at reference A's size were unreadable beside these shorts' big captions.** Labels and tags take a `size` in Remotion (`Callout`, `Tag`, `MTag`), left out for reference A; the character shorts draw labels at 54 px and crosses and warnings at 74 (`direction.LABEL_SIZE`, `TAG_SIZE`).
- `warn` joins the marks: a yellow sign and its words, for what something warns of.
- And, on this short alone: a shot on a floating arrow turns with the way the arrow faces, and put the lens inside the building (`square`); arrows in the dish touched its sloping inside (moved in); his side close-up hid the straw (shot from where it shows); the frosted straw hid the air in it (it goes to glass for that scene, against a dimmed street, x-ray style); a count of 0 to 76 ran while the mercury fell from 98 (it counts down with it).

**The frame reviewer on that preview** (15 things): the storm was a grey sky over a sunlit building; the mercury looked the same as the empty glass above it; the ten-metre tube stood through the house roof with nothing holding it; the man's face barely changed while "however hard you suck"; the WEIGHT arrow grew only at cuts; NO AIR came up while air was still streaming out; the arrows didn't shrink enough for "a little less"; the pump was just there with nobody hooking it up; the column stood ten metres up in scenes where nothing sealed the straw's top; the outside air stopped just above the tank; and smaller things. The barometer's part was then dropped (below), which took most of them with it. For the part that stays: his face strains and goes red while he sucks; the pump stays on the straw in every scene the column stands in; the air goes on up past the tank where the camera climbs, and its box stops short of the lens; the straw empties before NO AIR. Left: nobody's seen hooking up the pump (a person can't hold a hose), and the weight arrow grows in steps at cuts, as nothing can grow a thing's size during a scene.

**The owner on the ending** (Nov 7): "how is the straw realted to barometer tho lol. I think the eend solution shold solve the inital problem, which was having problem sucking water up, baraomoter doesnt solve that. It needs to solve the inherent problem". So, for every short: in a `you_invent` short what's built has to solve the problem the short opens with (`outline.md`, `script.md`, `critic.md`). The straw short now ends on what does: since nothing pulling from the top can beat the air's ten metres, you put the pump down in the water, where it pushes, and the only limit is how hard it pushes; the water climbs all the way to his mouth; the submersible pump. Lines 1 to 8 and their voice are kept. A fresh reviewer checked it (the limit, why deep wells use them, Arutunoff's 1926 patent and Pleuger's 1929 water-well pump, the name) and sent back two lines, both fixed: "push instead of pull" undid "sucking never pulled", and "as high as you like" said more than the fact. The barometer version is kept as `draft_v3_barometer.json`. New: `submersible_pump` (a dark steel can on the tank's floor round the straw's foot, its cable over the rim; pale steel was a blur through blue water), an `ok` mark (a green tick, IT WORKS), and `short.py mixed`, which stages the voiced lines on their voice and the new ones on the estimate, so they're looked at before they're paid for. Its look: the straw's top with nothing on it; the pump in the tank, PUMP; the big PUSH arrow riding the water up, bigger than the air's arrows; past 10 M to the top; him with the straw in his lips, happy, IT WORKS; the pump, SUBMERSIBLE PUMP, and the whole building with the water up to its roof.

**Voiced and reviewed.** The owner said yes; the four new lines cost $0.053 (about 20¢ of voice in all), and the short runs 53.6 s. The frame reviewer on its preview (11 things), and what was done:
- He'd vanished from the roof in the last wide shot, the straw's end standing up on its own: he's there, drinking.
- The pump just appeared in the tank: it's lowered into the water as the words say so (`slide` with `from`), from under the straw's staff, which it would otherwise pass through.
- "Pushes the water up into the empty straw" played over a full straw: the straw starts empty, and the water rises into it as the arrows press, on into the next line's climb.
- The pump's cable stood in a stiff arch over the rim and led nowhere: it rests on the rim at the side and runs off along the ground.
- Air drifted back down the x-ray straw under NO AIR: it's drawn out through a point past its box's top, so each ball is gone as it leaves, before the label.
- The ten-metre count settled while the water went on climbing: a count settles at 70% of its time, so it now runs to the water's stop over that, and the water rises at a steady rate and stops dead, as the words say.
- The pump's arrow floated among the air's red arrows, as if the air pushed up: it starts at the pump, and it's green (`push_arrow`). A `tint` toward green turned the red arrow a dark maroon instead, so tint darkens rather than replaces a strong colour; not looked into.
- SUBMERSIBLE PUMP pointed below the pump and ran off the picture, and the climbing arrow's PUSH never showed. **Fixed for every short:** a label on a spot of a thing now rides on the thing itself, so it's wherever the thing is drawn; it had been keyed from where the stage worked the spot out to be, which for a slid thing ran far ahead of it. And a label too long for either side of its dot now shrinks until it fits (`CalloutLabel`), rather than running off the picture.
- Left: dark sawtooth triangles round the bottom of the glass tank in every close shot. It's how liquids are drawn (their backfaces are shaded as the top), so it wants a general fix, not one for this short. Whether his lips close round the straw is to be checked at full size. Nobody's seen hooking up the roof pump, and the weight arrow grows in steps.

**The frame reviewer's third pass** (12 things), and what was done:
- The payoff wasn't seen: the shot left the water below the straw's bend, and his face was the same as when he was failing. The straw's last stretch runs level over the parapet, so a level can't fill it; it's a thing of its own, `straw_neck_water`, there when we cut to him, the straw blue to his lips as he smiles.
- The counter read 5 and 8 metres beside an empty straw: the camera rose faster than the water. It rides from the water's 0 to its 10 at the water's own steady rate.
- The air's red arrows went on pressing while the words said the push isn't the air's: they're gone from that line.
- The dark pump went pale under the tank's water: the tank's water is clearer than a column's (`clear` 0.62).
- The straw, full to ten metres, was empty at the cut to the new pump: it runs back down first, the roof pump off.
- The metre he sucked up vanished in a tenth of a second: it falls back over two thirds of one.
- The cable ended on the pavement by the tank: it runs on out of the picture.
- The pump's long name shrank to nothing beside it: a label that fits on neither side now goes to the side with more room (`CalloutLabel`, every short), and the name is a `title`, a new mark, big across the top of the picture as the last line says it, its words in lines that stay in the picture.
- Left: the pump slides down round the straw like a bead as it's lowered (the straw's foot is fixed at the tank's floor); the sucking face changes little (a face can only pucker and squint here); the air shows in the tank's shots and not on the wall's; the count says "1 metres" for a moment.

**Not done:** the owner's look, and the full-size cut.

## How a character short runs (phases 28 and 36)

A channel with `format: character` in its YAML makes vertical 3D shorts. `core/formats.py` says which stages run for which format, and `core/stage.py` keeps each stage to its channels. With only story channels, every query is the same as before. A short's whole flow:

1. **Outline and script:** the same stages and gates, with prompts from `prompts/character/` and their own checks (`checks.short_outline`, `short_script`). 60 to 150 words, 4 to 16 lines (phase 45). The shapes come back as the story ones, so cards and `start_generating` didn't change.
2. **Voice:** the same stage. `voice_model` in the channel's YAML sets its ElevenLabs model, as the owner's clone needs `eleven_v4`.
3. **Titles:** the `thumbs` stage writes titles and a description, and no thumbnails. YouTube takes a frame.
4. **`stages/direct.py`:**
   - A `cast` job says who and what it needs. New people are checked and made (`characters/`).
   - For a new thing, code searches, a `source` job chooses from a sheet of pictures, it's fetched and sized, and a `thing` job checks its sheet and corrects its turn, size, moves and spots, twice at most. A model turned down moves on to the next, up to 3. Only then does its spec go in `things/specs/`.
   - A `direct` job writes the whole short in the scene language, on the short's clock, from the voice's word times (`scenes/direction.py`). Code turns each scene into its own time, requires them to cover the short exactly, and runs the scene language's check. Length and captions are never written.
   - With `character` in the channel's `gates`, a card waits on the owner with the sheets (`approve` or `revise`).
5. **`stages/film.py`:**
   - A rough frame of every shot, 432 wide. A `film` job looks at the sheet. A scene the stage refuses to build ("stands too far to reach") counts as a problem too. Problems go back as notes on the `direct` job, once only, as with the critic.
   - Every scene rendered, each kept by a hash of its JSON, so directing again only renders what changed. The frames are deleted once in the clip.
   - `MachineShort` with `captionStyle: 'big'`: the clips, the voice line by line, impact and whoosh sounds from `render/sfx.py` on the stage's cues, and captions a few words at a time from the voice.
   - The render card, with the MP4, a frame sheet and only a title to pick.
6. **Publishing:** the same stage. `metadata.publish_meta` takes `youtube.tags`, adds the CC-BY credits to the description, and leaves out the Chapters heading when there are none. `youtube.publish_slots`, a list, finds the next time no other video of the channel goes public; a channel with `publish_slot` behaves as before.

Fixes after a render: `flag_scenes` with kind `visual` and a note directs it again and keeps the voice; `restage` also clears the kept renders. Narration flags are refused, since `regen` doesn't run for this format.

- **Not done:**
  - No channel exists yet: `channels/` needs a YAML with its name, voice and YouTube channel, which are the owner's to choose.
  - The worker agent doesn't look at a new person's portrait sheet as CHARACTERS.md planned; only the `character` gate shows it.
  - A person can't change stance within a scene, though the director can start a new scene to do it.
  - No music.
  - Sound is only the voice, impacts, taps and whooshes from `render/sfx.py`.
  - `max_seconds` keeps a Shorts channel's competitors to Shorts, but ranking and `prompts/character/topic.md` haven't been run on real ones.
- **Skills, added at the owner's request (Nov 3, 2026, "be sure they are well known"):**
  - `.claude/skills/remotion-best-practices`: Remotion's own, 740K installs on skills.sh, from `remotion-dev/skills` at commit `c7cb2fd`. The repo has no license file, so it's gitignored; install it with `npx skills add remotion-dev/skills@remotion-best-practices`.
  - `.claude/skills/blender-motion-state-inspection`: from `affaan-m/ECC`, 296K stars, MIT, commit `db7f2a6`, text only.
  - Passed over: Blender skills from small authors (they write Blender Python, which this project doesn't do), HyperFrames (another renderer), OpenMontage (AGPL), fal's cinematography skill (its steps run paid generations), `frontend-design` (web pages), and ECC's `taste-distillation` (its scripts lift stills and overlays from a reference, which the rule on references forbids).

## How things are got (phase 35)

A scene can use any thing in `things/specs/`, by id, as a prop: flown, thrown, held, struck, aimed at. `things/spec.py`'s docstring is the authority on the format, and a thing is kept in `data/things/<id>/` for reuse: `thing.blend`, `thing.json`, `sheet/sheet.png`.

- **Where they come from, cheapest first:**
  - **Poly Haven:** 521 free CC0 models, real scans of everyday things, no key. Its [API page](https://polyhaven.com/our-api) says it's free for everyone, including commercial use, which settles what a secondhand source said. If this line ever serves other people, they have to be told the assets came from Poly Haven.
  - **Sketchfab:** the search is public and download needs a free `SKETCHFAB_TOKEN`. Only CC0 and CC-BY come through, read from Sketchfab when it's fetched, and anything tagged `noai` is refused. The best finds are CC0 museum scans of real birds (no clips, so they sit) and animated CC-BY birds. A CC-BY credit goes in the video's description by itself.
  - **A URL:** a pack with its license and page written in the spec, such as `low_poly_eagle`.
  - **Generated on fal:** `fal-ai/hunyuan3d-v3/text-to-3d`, $0.375, no clips. Refused without `--spend`, the owner's yes. Not yet run.
- **Choosing:** `run.py thing --search <words>` prints the hits and makes a numbered picture sheet. Uploaders on Sketchfab don't always own what they upload, so anything named after a game or film is skipped by the agent, by looking: `prompts/character/source.md` says so, and code doesn't check it.
- **`blender/things.py`:** any glb, gltf, fbx or obj comes in the same way: its cameras and lights dropped, the longest side scaled to `meters`, turned and tilted, with its origin in its middle, under two empties (`root` for the scene, `holder` for the size). Clips are listed with their frames and named by the spec or the file. They play through the NLA, so they loop, slow down and ease into each other. A file's grey model can be colored by material name, and `smooth` welds a faceted one.
- **New in the scene language:**
  - `go`: under its own power, nose first along a smooth line, banked by tan(bank) = speed x turn rate / g, flaring to land. It rides on a person's bone once it's landed on them.
  - `play`: a thing's clip from a time, looping.
  - `"follow": true` on a shot: the camera travels with it, and `angle` counts from the way it's heading.
  - Aims: a thing's `spots`, plus `crown`, `shoulder_r/l`, `hand_r/l` on a person. `crown` casts a ray at the head.
  - A soft floor shadow under people on `sky_set`, whose floor is only a picture.
- **The bird test (`scenes/examples/bird_lands_on_head.json`):** an eagle flies in on a banked curve, flares, and lands with its feet on Walt's hair, and rides there. 210 frames at 1.2 s each, 274 s of Blender in all. No code for this bird. **Its captions are placeholder words, not a fact**, so it isn't to publish.
- **What's weak:** it's the low-poly eagle, with no feathers and a goofy idle clip that drapes its wings, because realistic models need the token. A model with no clips can't flap. An auto-rig for generated birds wasn't built, since animated models are available.
- **Your turn:** make a free Sketchfab account, copy the API token from [settings](https://sketchfab.com/settings/password), and add `SKETCHFAB_TOKEN=...` to `.env`.

## How scenes work (phase 34: the scene language)

After the owner's verdict on the sword test ("good"), they set the bar: "i dont wanna loo at another video nd have u make a another custom solution ideally this agent should figure out whats best, like if i m talking about a bird now, it should create scenes that are reasonable acorordinlgy". So a new topic must need no new code. The agent writes a scene as JSON, and fixed code runs it. `scenes/spec.py`'s docstring is the authority on the format.

- **Run one:** `uv run python run.py scene <file.json>` renders to `data/scenes/<name>/`: `scene.mp4` with captions, `frames/`, `bench.json`. `--frames 10,50 --width 432 --samples 12` is a quick look. A bad scene is refused with its reasons before Blender starts.
- **The two scenes so far:** `data/benchmarks/zack_sword/sword_in_mouth.json` remakes the owner's reference test (gitignored, internal only, like reference A), and `scenes/examples/ball_to_the_head.json` is a different topic that needed no scene code. Writing it added two general things every topic can use: `fly` (a thrown thing on gravity's arc, which bounces) and a strike that lands on a person.
- **What the reference taught (`ScreenRecording_11-03-2026 20-58-48_1.mov`, a 15 s Zack D Films short in the folder above):** its people hardly animate. It holds a strong pose and does the rest with a cut every second or so, wide lenses close up, one slow-motion macro of the hit, glows for the force, and large bare captions. An earlier full-body sword clip from game animations looked "kinda bad". The check refuses a shot over 4 s for this reason.
- **`blender/stage.py` keeps things physically true by how it's built:**
  - Held props lead, and hands are locked on them (`Person.hold`: IK on the arm, the hand's turn copied), so a hand can't slip off a grip. `tests/blender_hold_check.py` checks it's within 5 mm.
  - A strike's arc ends on the target's surface, found by casting a ray at it. It speeds up on the way down and bounces off. If the striker stands too far to reach, the scene fails and says so.
  - Struck further out along a prop, whoever holds it reels harder, about the teeth or hand: a lever. Head, neck and chest ring down as one damped spring (`ring_down`), each taking less. Sparks and thrown things fall under gravity.
  - The body is a stance clip played very slowly, so people breathe and shift. Fingers come from the clip's closed hand, mirrored to the other.
- **Other pieces:** `envs.gym`, `Person.glow` (skin replaced by a mottled color: added to the skin instead, it washes out), red rings, `CaptionBig` in Remotion.
- **Where it falls short of the reference:** faces are smoother and younger, with no lines or eye bags. Hair is less tousled, limited by the add-on's styles. No x-ray of teeth. Props are simple: `katana`, `long_sword`, `stick`, `ball`, until phase 35. Grips are a short fixed list, and a person can't yet walk or change stance within a scene. Tearing tops at the shoulder if an arm goes overhead.
- **The owner on the ball scene:** "LOOKS GOOD" (Nov 3, 2026).

## How body clips work (phase 34: the motion test)

The owner asked whether a person can swing a katana, and this made one, from body clips on our rig. The owner judged the full-body version "kinda bad", which led to the scene language above. The command is gone, and its stances remain.

- **The clips:** the store's add-on (v4.0.28) has no animation library, so they come from two free CC0 packs the owner downloaded into `data/motion/` (gitignored): [KinemIQ's free set](https://kinemiq.itch.io/free-game-animations) (35 FBX clips, with a mannequin in a T-pose) and [Quaternius's Universal Animation Library 2](https://quaternius.itch.io/universal-animation-library-2) (42 clips in one GLB, with a T-pose clip; the sword clips are in the free version). No credit or account needed. `render/clips.py` unpacks and lists them. They download by hand: scripting itch.io's download returned "invalid key".
- **Retargeting (`blender/clips.py`):** a clip is read as how far each bone turned from that file's own T-pose, in the world's axes. Each of our bones first turns from its A-pose to a T-pose matching theirs, then turns the same way. Only the hips' travel is scaled, by leg length. A clip is only ever compared with a reference from its own pack, because their bones' axes differ by file. `Solver.play` crossfades between clips, and `hold_fist` keeps one hand closed through a clip whose hands are relaxed.
- **The sword** rides on the hand bone: `_in_the_hand` sets its grip across the palm toward the thumb, so the blade leaves the fist on the thumb's side.
- **What the tries showed:**
  - `Sword_Regular_A` into `Sword_Regular_A_Rec` reads as one overhead cut. `Sword_Heavy_Combo`, `Sword_Regular_C` and `Sword_slash` are acrobatic, game-style moves.
  - `Idle_relaxed` is wrong for a sword: the blade lies across the chest. `Idle_with_a_sword` holds it well, in a wide, bent-kneed stance.
  - **Clothes tear at the back of the shoulder with the arm overhead.** It's worst in single-layer tops (tees, sweaters). Layered outfits hold up much better; the bomber jacket still shows a small tear there. Switching off the add-on's body masks doesn't help, because the skin then pokes through everywhere. So `characters/specs/sam_jacket.json` wears the jacket.
- **Not done:** the left hand stays off the grip (these are one-handed clips); hair and cloth aren't simulated; feet can slide a little; the shot sits on the machines' sand lot.
- **Other sources, if these fall short:** Mixamo (free with a free Adobe login, no API), LIM - Life In Motion ($40, 360+ clips for this rig, swords unconfirmed), Rokoko Vision (film a move; free tier of about 30 s a month).
- **Now used for stances.** A body clip can't be swapped in mid-scene yet.

## How people are made (phase 32: the character look test)

The plan is [CHARACTERS.md](CHARACTERS.md). Phase 32 answers its first question before anything is built on it: can Human Generator, in our Blender with no window, make a figure close enough to the owner's reference frame?

- **What runs:** `uv run python run.py character-test`, and `--list` first to see what's installed. `--preset`, `--hair` and `--outfit` take part of a name, `--frames 1,104` is a quick look, and `--engine cycles` tries Cycles. Everything lands in `data/characters/look_test/`: `compare.png` (ours beside the reference), `portrait.mp4` and `bench.json`.
- **The files:**
  - `render/humgen.py` finds the owner's downloads in `human_packs/`, and unpacks them once into `addon/` and `content/`. `.hgpack` files are zips, and it refuses one that would write outside its folder. Blender's Install button isn't used.
  - `blender/humgen.py` is the only file that touches the add-on. It enables it, then makes a person and saves `person.blend` and `person.json`: which objects and bones are which, and every face key.
  - `blender/people.py` brings a saved person into a scene with no add-on loaded, and keys the face, blinks, gaze and props on bones.
  - `blender/charactertest.py` is the shot, built by hand as phase 23's were. `envs.sky_set` and `envs.portrait_lights` are the set.
- **Results on the real add-on:** it ran with no window on Blender 5.2.3 the first time. The store's zip, named v4.0.29, calls itself v4.0.28, and has no animation library (the public v4.0.38 source does), so walking and body clips are an open question for phase 34. A person takes about 7 s to make and is reused. The final clip took 1.7 s a frame on EEVEE at 32 samples, with 8K skin. Cycles was 13 s on the one frame timed (at 64 samples), and its hair comes out grey because the hair shader is set for EEVEE.
- **Controls added after looking:** `age`, `face_hair` (presets can bring a beard), `eye_color`, `clothes` (a garment's main color), `brows`, `brow_density`, `textures_8k`, `skin`, and `keys` such as `Stylized` and `Eye Scale`.
- **What looked wrong, and why:**
  - **Noisy white teeth, tongue and eyes:** their materials are mirror-gloss, so `Person._soften_gloss` softens the teeth, gives the eye lens a little roughness and blends it instead of dithering.
  - **A glowing tongue:** EEVEE lets the sky's light into the mouth, so the teeth material is darkened by ambient occlusion.
  - **Eyes that didn't turn:** they track `eyeball_lookat_master`, so `Person.gaze` moves that.
  - **A snarl:** `mouthUpperUp` bares the teeth, so a stunned face is a dropped jaw with relaxed lips.
  - **A Blender crash in EEVEE's motion blur:** it came after changing every eyebrow system, hidden ones included. Only the brows in use are changed now.
- **The first run's pick:** preset David, hair Short Combed, outfit Relaxed Fit, with `character_test.LOOK` on top. The hair is neater than the reference's tousled hair, and the face smoother than its lined, cartoon-like one.
- **Facts found in the add-on's source (v4.0.38), each of which would have failed at run time:**
  - It looks up its settings in the preferences' add-on list, so `addon_utils.enable` needs `default_set=True`. The stub caught this.
  - Its setup, `HG_start`, runs when Blender opens a file, so an add-on enabled afterward has to call it. It fills the lists `from_preset` needs. `skip_url_request` stops it going online.
  - It joins hair paths to its content folder with no separator, so `filepath_` ends in one. It finds a preset's gender by splitting on the system's slash, so paths use backslashes on Windows.
  - Its drivers would overwrite a keyed face shape, so `Person.face` removes a key's driver first, as its own motion capture does.
- **The sky:** AgX washes out strong blue, so the sky overshoots on purpose and still comes out a little paler than the reference.
- **Tests:** `tests/test_characters.py`. `tests/stub_humgen/` plays the add-on with its source's signatures, and `tests/blender_fake_person.py` is a ball with a rig and face keys. They test our side of the join; the real add-on's content can't be in a test, as it's paid and gitignored.
- **The files:** the owner's downloads are in `human_packs/` (gitignored, `blender.humgen` in `stickfleet.yaml`), unpacked to `addon/` and `content/` beside them.
- **The owner's review:** they watched `data/characters/look_test/portrait.mp4` and said "really good" (Nov 3, 2026). A new try takes about 15 s for a few frames, and under 4 minutes for the whole clip, at $0.

## How machine shorts are rendered (phase 23: the look test)

The plan for the shorts is [SHORTS.md](SHORTS.md). Phase 23 answers its first question before anything else is built on it: can Blender reach reference A's look (the diesel pile hammer reel in the folder above)?

- **Blender:**
  - Blender 5.2.3 LTS, the portable zip, unzipped to `tools/blender-5.2.3-windows-x64/` (gitignored). The owner downloaded it, and its SHA-256 matched blender.org's published one.
  - `blender.path` and `blender.samples` (32) are in `stickfleet.yaml`.
  - `render/blender_render.py` runs `blender -b --factory-startup --python-exit-code 1 -P blender/run.py -- job.json`, reads `FRAME i/n` lines for progress, and encodes the frames (CRF 14).
  - EEVEE renders on the RTX 5080 with no window. That was the open question on Windows; `gpu.platform` after a render says `NVIDIA GeForce RTX 5080 Laptop GPU`, OpenGL.
- **Speed** at 1080×1920 and 32 samples:
  - the first frame takes 1.3 s while shaders compile;
  - after that, 0.33 to 0.43 s a frame (the crane fastest, the cutaway and the nail slowest), with motion blur on;
  - a 90 s short (2,700 frames) is about 15 to 20 minutes, at $0.
- **`blender/` runs inside Blender and imports nothing from the app.**
  - `look.py`:
    - the render settings: AgX "Medium High Contrast", soft shadows, screen-space ray tracing, fast GI (the ambient occlusion look);
    - a soft bloom through Blender 5's compositor node group (`scene.compositing_node_group`; the Glare node's settings are now inputs);
    - `camera()`, aimed at an empty so a shot keys either one, with depth of field;
    - `key`/`ease` (Blender 5 keeps F-curves in layered action slots, which `_fcurves` reads).
  - `materials.py`, the fixed palette:
    - steel, bright_steel, black_steel, dark_steel (A's blue-grey pile), safety_yellow, hazard_stripes, chrome, rubber, white_paint, red_paint, air;
    - `cut`: orange with dark 45° hatching in world space, so the lines run the same way on every part;
    - wood (varnished oak), pale_wood, `wood_cut` (sawn), sand (Poly Haven's red_sand, tinted to A's orange) and far;
    - `hazed()`: aerial perspective, by the distance from the camera.
  - `shapes.py`, bmesh shapes (no `bpy.ops`):
    - `lathe` (a profile of radius and height turned about Z: the nail, the anvil housing with its dish), `cylinder`, `tube`, `box`, `sphere`;
    - `torus` (and a C-shaped hook), `rods`, and `truss` (the crane's lattice boom);
    - `cut_away()`, an EXACT boolean with `material_mode: TRANSFER`, so the cut faces take the cutter's material.
  - `envs.py`:
    - `desert_lot`: Poly Haven's `kloofendal_43d_clear_puresky` HDRI, a sun, an 800 m sand plane, a far fence, and pile stubs;
    - `workbench`: a wood block on black under one warm lamp. The world shows black to the camera and a dim grey to reflections, so steel in a black room isn't black.
  - `tracks.py`: each anchor's screen position in every frame, and whether it's seen. A ray from the camera that hits another rendered part first hides it; the hidden cutter doesn't, nor does a part of the same `group`.
  - `looktest.py`: the three hand-built shots.
  - `run.py`: the entry. Frames go to `f_0001.png ...`, with `tracks.json` holding the anchors, events and per-frame render times.
- **`render/assets.py`** fetches Poly Haven files once into `data/assets/polyhaven/<id>/`. They're CC0 (no credit needed), through the public API with a User-Agent.
- **The overlay,** in `render/remotion/src/shorts/`:
  - the `ShortClip` composition, 1080×1920 at 30 fps, registered in `Root.tsx`;
  - `Overlays.tsx`:
    - A's caption box: Inter SemiBold 42 in a dark rounded box at 71.5% down. A `\n` in the text is where the line breaks, as A breaks by phrase; otherwise the lines are balanced;
    - part labels: Inter ExtraBold 32, uppercase in a tone color with a dark outline, a dot and a leader line. They follow the track, hide while the anchor is hidden, and go on the other side when they wouldn't fit inside the safe area;
    - tags: fail (a red ✗ or stopwatch), ok, warn, and mode ("// SLOW MOTION");
  - `types.ts`: the props and the safe area (top 8%, right 14%, bottom 22%);
  - `fonts.ts`: Inter, bundled under the SIL OFL (`fonts/OFL.txt`).

  `remotion_render.render_short()` renders it. Its CLI loop is shared with the long videos' `render()` as `_run()`.
- **`run.py look-test`** (`render/look_test.py`) renders the three shots at full size, lays the overlays on, and writes to `data/looktest/`:
  - each shot's MP4 and `looktest.mp4` (all three in a row);
  - `compare_<shot>.png` (ours on the left, A's frame at the same moment on the right) and `compare.png`;
  - `bench.json`.
- **What comparing frame by frame with A found:**
  - **A's nail shot is a cutaway too.** The block is cut through the nail's own plane, so the nail is seen going into the wood, on a dark sawn face. Cutaways are the format's main idea, not one effect.
  - **Labels are small in A,** about 32 px on a 1080-wide picture. At 40 px "IRON BLOCK" didn't fit beside the block and flipped onto it.
  - **AgX washes bright orange toward pink.** The sand needed a lower sun and a deeper tint, and the haze had to start farther out.
  - **A ram coming down covers the chamber behind its front edge when the camera looks down at the cutaway.** The first AIR anchor was hidden for the shot's last half second, so its label vanished. Phase 26's shot checks need:
    - a label's anchor seen for its whole show time;
    - a label clear of its own part;
    - a level enough camera on a cutaway.
- **The nail shot, rebuilt after the owner's review** ("its good but the first nail there is a lot of differences"). Compared at 5 frames a second over the same 2.4 s, it differed in nearly everything:
  - **A shows the taps.** A claw hammer swings in from the top right, taps three times 0.6 s apart (A's 2.0, 2.6 and 3.2 s), lifting only a little between taps, then leaves. The nail goes from standing on its point to under half out.
    - The hammer is built full size and shrunk to A's, whose head is about a third as tall as the nail is long.
    - It swings about a pivot at the end of its handle: QUAD easing into each tap and out of it, the pivot dropping with the nail as it sinks.
    - The first scaled build stopped 1.4 cm short of the nail: its face profile used the already-shrunk length inside the shrunk hammer.
  - **The camera moves:** close on the standing nail, back as the hammer comes in, then in again as the nail goes in.
  - **A's wood is plain and pale** (`pale_wood`: soft lengthwise streaks and a fine sanded ripple). Its cut face is darker brown, with fine crosswise ridges broken into dashes (`wood_cut`). Both are procedural now; the oak photo texture is only the hammer's handle.
  - **The cut is a notch** (`cut_away(x_range=...)`) whose left wall stays out of the picture. The dark wedge at the bottom left of A's cut face is the uncut block's shadow, not a wall.
  - **The light, read from the nail's shadow, is about 54° up, in front and 37° to the left.** That's why A's top is brighter than its cut face. The spot's pool fades out before the block's back edge (`envs.workbench(elevation, azimuth)`).
  - **The nail** is long (10 cm), thin and light (`bright_steel`), with a thin flat head. Motion blur (half a frame) is on for every shot.
- **Tests:** `tests/test_shorts.py`, 5 tests; the whole suite is 114, green (7 min 41 s). Each shot renders with tracks for every frame; the cutaway's anchor is seen in every frame; `ShortClip` renders at 1080×1920 for exactly the clip's length. The Blender ones skip without Blender, as the Remotion one does without `node_modules`.
- **Your turn:** watch `data/looktest/looktest.mp4` (in a desktop player) and look at `data/looktest/compare.png`, then say whether the look is close enough to build the kit on (phase 25), or what's off. Re-rendering after a change is about 2½ minutes for all three shots, at $0.

## How the chat runs the fleet (phase 18)

The browser app and the in-app chat agent were deleted on Nov 2, 2026, when the owner said "i want to approve in this chat, i want to retire the browser, i dont need card comments". The Claude Code chat is the only way in. It works over the same MCP endpoint as the jobs, at `/mcp`. Git history has the old UI (`server/web/`) and agent (`agent/`).

- **Seeing what's waiting.**
  - `status` lists each channel (its YouTube connection, sign-in errors, budget) and its videos, each with its state and the card waiting on the owner. It also says how much news is unseen. With a `video_id` it gives one video's state, cost, metrics and the waiting card in short.
  - `review` gives the waiting card in full:
    - outline: every beat, the cast and the tracker;
    - script: the counts and beats, plus the whole script written to `data/review/video-N-script-vM.md` for the session to read and the owner to open in VS Code;
    - render: the MP4 and highlight-reel paths (VS Code plays them), the three titles and thumbnails (as pictures) with their texts, what's picked, cost and budget, and each scene's line;
    - publish: every field, the go-public time and the thumbnail;
    - error: the error and any blocked scenes;
    - swap: the options.
  - `contact_sheet` shows the scene pictures.
  - `news` gives the notices and cards posted since the last call (new cards, sign-in trouble, topic ideas, metrics, published, went live), each once. `messages.seen_at` marks them. Everything posted before phase 18 counts as seen, so the first call isn't the whole history.
  - `wait` returns when a job arrives, a card waits, a video fails or is blocked, topic ideas or a swap are posted, metrics come in, or a video is published or goes live.
- **Acting.**
  - The gates: `approve`, `revise`, `regenerate`, `edit_outline`, `flag_scenes`, `edit_scene`, `pick`, `set_schedule`, `update_publish` (title, description, tags, AI label), `publish`, `retry`, `stop_writing`.
  - Topics and series: `new_video`, `next_part`, `topics`, `start_topic`, `dismiss_topic`, `suggest_topics`.
  - Live videos: `suggest_swap`, `apply_swap`, `keep_swap`.
  - YouTube: `connect_youtube`. Google's sign-in page opens in the browser, because Google requires it, and the tool waits up to 5 minutes. `run.py connect` does the same.
  - Each tool is a thin wrapper over `core.actions`, so every state check still holds. A refused action comes back as an error result with the reason.
- **The owner says yes to what costs money or changes YouTube.**
  - `claude-settings.json` belongs in `.claude/settings.json`, here and in the workspace folder above. It allows every `stickfleet` tool, and asks every time for `approve`, `flag_scenes`, `edit_scene`, `retry`, `publish` and `apply_swap`.
  - Claude Code's permissions docs say an ask rule prompts even in auto mode. The exception is bypassPermissions, which skips every prompt.
  - The MCP instructions also tell the session to do these only when the owner asks.
  - Claude Code's auto mode refused to let the session write `.claude/settings.json` itself (it's Claude Code's own config), so the owner copies the file in once.
  - A test keeps the file's ask list equal to `server/tools.py` `ASK`.
- **Gone.**
  - The React UI, the REST API, the websocket and `/media`.
  - The in-app chat agent, with its confirm cards, gate comments, per-thread budgets and `agent:` config.
  - `actions.show`, and the `claude-agent-sdk` package. `mcp` 2.3.0 is now a direct dependency.
  - The `threads` table stays as where `messages` hang. Its `sdk_session_id` and `agent_cost_usd` columns are unused.
- **Verified at $0** (`tests/test_tools.py`):
  - A stub video goes from idea to scheduled using only MCP tools: `status`, `review` of the outline, script, render and publish cards (the script file, the video file, thumbnails as pictures), `edit_outline`, `approve`, `pick`, `update_publish`, `publish`, and `news` shown once.
  - Flags.
  - A refused approve, an unknown video, and an error card through `review` and `retry`.
  - Pre-phase-18 messages counted as seen.
  - The ask list.
  - `/mcp` is local-only and `/api` is gone.
  - Swaps, topics, sign-in status and `connect_youtube` moved onto the tools in their own tests.

## How the session writes (phase 19)

- **What moved.** `outline`, `script`, `critique`, `rewrite_line`, `revise_visual` and `topics` joined `titles` in `session.READY`. Each builds the prompt and runs the checks it always did; only the API request became a job, answered in the chat and checked at once. A video now waits at each writing step until the chat does it: "Waiting for Claude Code: the outline (job N)" shows in its thread and in `news`. With `providers.llm: session`, the tools that set writing off (`new_video`, `start_topic`, `next_part`, `approve` of an outline, `revise`, `regenerate`, `flag_scenes` with a note) say a job is coming.
- **One video's jobs, in order:**
  - the outline, its review, and the outline revised with the reviewer's notes if it found anything; then the outline card;
  - after approval, the script, its review and the revision, then the script card;
  - after approval, the titles, then the render card;
  - flagged scenes with a note: one rewrite job per scene.
- **A stage runs again from the top after each answer**, replaying the answers it has (by request hash), so it must ask for exactly the same thing each time.
  - The outline and script stages used to save their draft before the review. On the re-run that made the draft look like an earlier version, and the stage asked for a revision of it.
  - Now the draft is saved only when Stop comes during the review, which is what the save was for.
  - After Stop, `SessionLLM` still replays what was answered, and stops where it would have waited.
- **The script comes in parts.**
  - `take_job` tells the session to send a beat or more at a time with `answer_job(part=N)`, and `last=true` on the final part.
  - `core/jobs.py` keeps the parts in `claude_jobs.parts_json` and joins their lists in order (`merge`).
  - Each part is checked with `checks.script(partial=True)` on the script so far. Every rule holds for the beats written. The totals (40–65 scenes, 1,500–2,000 words, at least one place) are only checked for going over until the last part, which is checked as the whole script. The stretch rule uses the outline's last day as the story's end.
  - A part that fails isn't kept. A last part that fails keeps the parts, so only the ones that need it are sent again. A part sent again by its number replaces it.
  - `jobs` and `take_job` show how many parts are in.
- **Long briefs go to a file.** A brief over 30,000 characters is written to `data/jobs/job-N.md`, and `take_job` gives the path. A script's review or rewrite carries the whole script, and this keeps it under Claude Code's cap on MCP output (25,000 tokens by default).
- **The reviewer is the `critic` agent.**
  - A job of kind `critic` goes to `.claude/agents/critic.md` with only its id. The agent starts with a fresh context, so the session that wrote the draft never grades it.
  - The agent's tools are `take_job`, `answer_job` and `Read`.
  - The MCP instructions, the skill and the brief all say so. Nothing in code can tell which agent answered.
- **Flagged scenes wait one at a time.**
  - `run_scene_stage` catches `NeedsClaude`: the scene is leased for `PARK_S` with no failed attempt.
  - The job carries the scene id (`Meter.scene_id`), so two flagged scenes get two jobs, and answering one wakes its scene.
  - Stages that go in order (`limit=1`: stills, sheets) now claim only a video's first scene in that state (`claim_scenes(in_order=True)`). A scene that's waiting, or backing off to try again, holds its place.
- **Topic ideas.** A round of ideas isn't a stage that can park.
  - `propose` and `follow_ups` mark their job with what to run in `claude_jobs.resume_json`: a competitor round with its count, or a winner's follow-ups.
  - Every loop, the topics stage looks for answered ones and runs the round again. That replays the answer, queues the ideas and posts the card. The mark is cleared first, so a failure is posted once, not every loop.
  - A winner's follow-ups carry its video id (`ChannelMeter.video_id`), so they don't supersede the channel's competitor round.
  - The "Waiting for Claude Code" line for a round goes to the channel's home thread, and `suggest_topics` gives the job's number.
- **Stop.** `stop_writing` on a video whose outline, script or review is waiting supersedes those jobs and clears the lease, so the stage runs at once and stops:
  - a revision goes back to its draft, with the note kept as the draft note;
  - a first script goes back to the outline;
  - a review goes back to the draft it was reading.

  Stop's notice now says "draft note" instead of the browser's "note box", and the script file from `review` labels that note as the one taken back by Stop. Phase 18 had it as "Rewritten with the note", which was wrong.
- **The hook checklist.**
  - `prompts/outline.md` has a checklist adapted from the viral-hooks skill to these long videos: the stake first, a concrete thing or number in the first sentence, a question, the title's promise kept, no bait, the stakes up within a minute.
  - The outline's `hook` now ends with the opening line as it will be said, and `prompts/script.md` opens the first scene with that line.
  - The skill itself is in `.claude/skills/viral-hooks/` for when a hook won't come.
- **Claude Code files** are in this repo's `.claude/`, with copies in the workspace folder above: the `stickfleet` skill, the `critic` agent and `viral-hooks` (How the code is laid out). Writing them worked under auto mode; only `settings.json` had been refused.
- **Verified at $0** (`tests/test_writing.py`, 6 tests).
  - A stub video goes from idea to render card with every word written by "the session" over MCP:
    - the outline and its review, including a refused review;
    - the script in three parts: one sent out of order, one that fails, and a last part that fails and is sent again;
    - the reviewer sending the script back, and the rewrite;
    - the titles.

    Then two flagged scenes are rewritten as two jobs, each holding its place.
  - A long brief written to a file.
  - Stop on a waiting revision.
  - Topic ideas, from the stage and from `suggest_topics`.
  - A winner's follow-ups.
  - An in-order scene holding its place.
- **Done with a real video in this chat** (Nov 2, 2026, video #5, a 17-year-old house-sitting a billionaire's mansion): the outline passed its checks first time, the critic agent sent it back with 8 notes, and the revision went to the owner, who approved it. The script went in 5 parts, each accepted first time (56 scenes, 1,968 words). The critic sent it back with 8 more notes (a tunnel never said to be bolted, diesel numbers that didn't add up, a helicopter landing in a pine clearing), and the revision passed. Two things showed up: the critic's notes are worth having on every draft, and the script runs about 13½ minutes against the 12 the prompt asks for (the checks allow up to 2,000 words).

## How the session looks (phase 20)

- **What moved.** The looking calls became jobs like the writing: `check_picture` (kind `picture`), `map_stage` (`map`), `name_parts` (`parts`), `inventory` (`inventory`) and `scene_sheet` (`sheet`). Each builds the prompt and runs the checks it always did. Before, they all shared the kind `check`, so two of them for one video would have replaced each other's job.
- **Pictures in a job.** A request's pictures are image blocks naming the file and a hash of its contents (`claude._image`), not the picture itself, so the jobs table stays small and a picture drawn again is a new request. `take_job` sends them as JPEGs 1280 wide, after the brief's text.
- **The worker agent** (`.claude/agents/worker.md`, with a copy in the workspace folder above) does the looking jobs, so their pictures and one-per-scene briefs stay out of the main chat. The main session launches it with "Do the waiting Stick Fleet looking jobs"; it takes, answers and waits, one job after another, and stops after 20 (a fresh one carries on) or when none are left. `take_job` tells the main chat to hand a looking job over, as it does for reviews. The skill and the MCP instructions say so.
- **One video's looking jobs, after the voice:**
  - puppet pictures (`render.pictures: puppet`, the current setting): a map for each place; the part names for the main character's puppet (once per channel), each cast member's and the props sheet; the props list; then a sheet per scene, in order;
  - generative pictures: one or two picture checks per still, set change and look, in scene order.
- **Nothing is paid for twice.** A stage that parks runs again from the top once its job is answered, so everything it made before the job must be found again, unchanged:
  - The assets stage's place pictures, grids, puppet sheets and numbered sheets were already kept under names that say what they were made from. The props sheet wasn't: it was painted again on every run, which would have meant a new picture, a new question, and so on for ever. It's now named by its items and painted once.
  - The stills stage drew a still and then checked it; on a re-run it drew it again. `_checked` now keeps each drawing as `.try1` and `.try2` until the picture is settled, so the re-run checks the same drawing and finds the answer.
  - The sheets stage's and the checks' jobs now carry their scene id (the sheets stage's had none), so answering one wakes its scene at once instead of after `PARK_S`.
- **Deleted:**
  - the API half of `providers/claude.py`: the client, streaming and Stop's stream cut (`Meter.writing`), costs from usage, the budget estimate, server-side fallback;
  - the `anthropic` package (with `docstring-parser`, `jiter` and `sniffio`, which only it needed);
  - the `claude:` config section and the Claude model ids under `models:` (`models.critic` is now `on` or `off`), and `topics.max_usd` (a round of ideas costs nothing now);
  - `providers.llm: claude`, and `ANTHROPIC_API_KEY` from `.env.example`;
  - `tests/test_claude.py`. Its pure check tests moved to `tests/test_checks.py`, its prompt tests (revise and regenerate, a next part, prompt edits and bad placeholders) to `tests/test_writing.py` through the session, and the topic-idea and follow-up tests in `test_topics.py` and `test_loop.py` now answer jobs.
- **`wait` fixed.**
  - Claude Code gives up on a tool call after about a minute: a 65-second `wait` timed out, and a 50-second one returned. `wait` now holds at most 50 seconds.
  - It also returns at once for anything that woke it since the last one returned. A script card that arrived between two waits had gone unseen for a whole wait.
- **Verified at $0:**
  - `tests/test_looking.py` (4 tests): a puppet video and a generative video are each made twice, once with every look answered on the spot and once through jobs answered over MCP. fal is paid for the same pictures both times; the generative one includes a still the check sent back, redrawn once. Also: a picture job's brief carries its pictures, and `wait` returns at once for what it missed.
  - `tests/test_session.py`: every LLM call parks as a job of its own kind.
- **Video #5, the first real run** (Nov 2, 2026). Script approved; the voice, places, puppets and props cost $2.57 up to the sheets. The first worker did 20 looking jobs, all accepted: 9 maps, the props list (sent back once for 13 props when the limit is 12), the part names of 3 cast members and the props sheet, and the sheets of scenes 1 to 6. The Claude part of puppet staging that phase 15 estimated at $1.50 to $2.50 a video is now $0.
  - **Found: people were sized from the wrong floor points.** The worker noticed that the sizes its sheet briefs listed didn't match the heights it had mapped. `Stage.height_at` averaged the two nearest floor points, so a spot off to the side of the mapped path took the size of points at another depth: the front lawn's helipad came out 38% of the picture tall (18% is right), the terrace's lawn 45% (20%), the garage's generator 49% (34%). It now reads the size along y between the nearest floor point above the spot and the nearest below, or along the line through the nearest two past the ends (perspective grows with depth, not across). Nearest keeps a point on another level (the wine cellar's stairs) to the spots beside it. Checked by eye on the bunker, garage and cellar maps; `tests/test_puppet.py` has the lawn and cellar numbers. The map prompt now asks for floor points covering every spot's depth. Scenes 1 to 5 used spots whose size didn't change; scene 6 (the sink) was animated a quarter too big and gets flagged at the render review.
  - **Found: a camera moving to someone who hadn't come on yet failed the video.** Scene 41's camera starts on the gate and moves to Mr. Ashford, who walks on at 3.8 s; until then the animator couldn't find him and took his name for a spot (`KeyError: the stage has no spot 'mr-ashford'`), which failed the whole video after 50 sheets. The camera now heads for where that person first stands. The sheet check now refuses a camera on a person who isn't on the sheet's figures (it allowed anyone in the scene's people list). Scenes 8 and 25 had the same move to Wade. Tests in `test_puppet.py` and `test_puppet_pipeline.py`.
  - **Found by the owner: the seventeen-year-old had a knee brace and a cane.** The channel's puppet was painted in phase 13 from video 3's story (a rebuilt knee, a cane), with both in its parts, and the rig drew the brace in every pose and the cane whenever the right hand was free. An injury belongs to one story's look, not to the character: the brace and cane (`parts.LOOK_PARTS`) are still painted with the puppet but drawn only in a scene whose look (the script's `looks`, as each scene's `looks_json`) names them (`Puppet.wearing`), for the main character and the cast alike. Without a cane, the poses that hold one hang the right arm as `stand_free` does (`rig.free_hand`). The sheet prompt no longer says the main character has a braced leg and a cane, and says `limp` is for someone hurt or one of the dead. Nothing is painted again.
  - **Found by the owner: a figure standing still shook.** Every 4 frames its joints were moved by a small random jitter, meant to make the lines look hand-drawn; on a figure holding still it read as shaking. Taken out (`draw._jitter`, the `wobble` and `seed` of a figure); a standing figure's frames are now identical.
  - **"No audio" was the player.** The render has the narration all the way through (mean -21.6 dB, no silence over 3 s), and so does the highlight reel; VS Code's built-in player showed it without sound. Watch renders in a desktop player.
  - **Redrawing after a drawing fix.** A puppet scene flagged `visual` with no note is now drawn again from the sheet it has (`stages/regen.py` sends it to `staged`, not back to `voiced`), so fixing the drawing code costs no new staging; a flag with a note still re-stages it. Video 5's 56 scenes are redrawn this way after the brace, jitter and size fixes.
  - **Seen at the render review (contact sheets), for a next phase:** people and the tow truck meant to be outside the gate stand inside it (every gate shot looks out from the house, and the place has no spot beyond the bars); no zombies, looters or crowds on screen (only the cast have puppets); no SUV prop (the props list left it out because the garage's picture shows one); the pilot and the hero stand in front of the helicopter instead of in it; Mr. Ashford's puppet doesn't change when his look turns him into one of the dead (scene 48).

## How the story is staged (phase 21)

Video 5 was the first whole puppet video. Its render review found the pictures telling a different story from the narration, in ways shared code caused, so every channel gets these:

- **Inside is inside, outside is outside.** Every shot of the front gate looked out from the house, the map had no ground beyond the bars, and the map prompt allowed only solid occluders, so Mr. Ashford begged at his gate from inside the walls and Wade's truck rammed it from the lawn.
  - An occluder can be `see_through` (a gate, a fence, a railing, a banister): `draw.cutout` keeps only its bars (the pixels inside the polygon darker than the Otsu split of its own brightness, at most 90 of 255, widened a pixel), so whoever is behind shows through the gaps. Checked on video 5's real gate: a block drawn behind it shows between the bars.
  - The map prompt asks for a spot on the far side of each gate, fence or railing (outside_gate), and `checks.stage_map` refuses a spot behind an occluder only when it's solid. `Stage.behind` says which occluder a spot is behind, and the sheet brief says "on the far side of the gate, seen through it".
  - The map prompt also says a spot is on ground a person can stand on: never in water, on a tabletop or in the air (video 5's terrace had the pool's spot in the water).
  - A low wall is a solid occluder a person can stand behind: `checks.stage_map` refuses a spot behind a solid one only when its top is above the shoulders of an adult there (the top quarter of their height). The first restage of video 5 had no spot below the terrace's back wall, so the crew's ladders and the dead there weren't drawn (scenes 19, 20 and 23); the map prompt now asks for one (beyond_wall).
  - `Stage.VERSION` is 3 (2: see-through occluders; 3: beyond a low wall). A map saved by an older mapping is made again the next time the assets stage runs (one looking job, no cost).
  - The sheet prompt: someone the story keeps outside stands at a far-side spot, never inside the walls.
- **Crowds are drawn.** Only the cast had puppets, so no dead were ever on screen.
  - A channel's `extras` (channels/zombie.yaml: `the dead`, `strangers`) are puppets painted once for the channel (`data/channels/<id>/puppet/the-dead/`, one fal picture each, 4.4 cents at 1K), from the channel's style and each part's description.
  - A sheet's `crowds`: who (a kind), how many (1 to 12), a pose at a spot or a walk from one to another, when, facing. `sheet.resolve` turns each into one figure per member: about the spot a step apart in a widening fan, a little nearer or farther, each a touch taller or shorter, and out of step (`phase` on the walk cycle).
  - A cast member whose look makes them one of the dead (`parts.TURNED`: "one of the dead", "zombie", "undead") takes the dead's head and hands, still in their own clothes (`Puppet.wearing`). Video 5's Mr. Ashford from scene 48 on.
- **Vehicles.** `do: inside` at a spot: the person is in a vehicle or a building there and isn't drawn (the camera can still follow them; two can ride in one). A placed prop's `lift` raises it that many adult heights (a helicopter hovering or coming in), its shadow left on the ground, and never past the top of the picture (at a far spot, video 5's helicopter at lift 2.5 went off the top and was never seen).
- **Props.** A prop is in one place at a time: picked up, it's removed from the place (video 5 had a shotgun leaning by the shutter and the same one in hand). The props list includes things the story moves out of the one place whose picture shows them (the SUV in the garage, rolled to the gate) and vehicles that arrive or leave; it may run to 16.
- **`restage`** (an MCP tool, asked every time): at the render review or after a failure, the whole video is staged again, keeping the voice. The assets stage runs again (pictures, puppets and props already made are reused; old maps are made again; the props list is asked again and new props painted), then every scene gets a new sheet and is drawn. Cents, plus the looking jobs.
- **Tests:** a see-through gate's bars and gaps, the map check, a crowd's members and their drawing, the turned head, riding inside and hovering (`test_puppet.py`); a stub video restaged end to end, with an old map made again and nothing painted twice (`test_puppet_pipeline.py`).
- **Not yet:** a prop moving within a scene (a helicopter lifting off, a gate falling flat) and a slung prop (a shotgun on the back).
- **Video 5 restaged** (Nov 2, 2026): 9 maps (the front gate see-through, outside_gate on the road, the pool's spot on its edge), the props list (suv, funnel, tow cable and others new; the two crowd puppets and the new props painted, about 13 cents), 56 sheets, every job accepted first time. Scene 1 shows the tow truck and Mr. Ashford through the gate's bars, the SUV braced inside it. The SUV hides anyone outside the gate below the shoulders, so those shots frame their face. Crowds: Wade's men at the gate, the dead at the gate on Day 16. The terrace scenes (19, 20, 23) have no dead yet: their map had no spot beyond the back wall (VERSION 3 fixes it at the next restage).
- **Puppets on hold** (Nov 2, 2026). The owner watched the restaged video and judged the puppets crude: the hero walked from one window to the other behind the bed (a walk is a straight line between spots, and nothing checks it against the furniture), and his arms vanished while standing (in the side-on standing poses both arms hang along the body line, and the black mitten hands sit on the black legs). Fixable, but each whole-video review had found a new batch, and the cutout look stays well short of the painted stills. `render.pictures` is `generative` again, and video 5 is painted.
  - `restage` follows `render.pictures`: painted, it deletes the scene pictures made before (the puppet stage named its first frames like the stills, `s001_r1.png`, so the stills stage would have taken them as done), puts each scene's motion back to the script's (the animate stage had made every scene a clip; video 5's script has 8 clips), and the stills, their picture checks and the clips run as for a new video. Tested in `test_puppet_pipeline.py` (a puppet video switched to painted).
  - **A blank strip fal leaves.** Painting video 5 again, 3 of the first 25 stills came back from fal with a blank white strip along the bottom (scene 21's: 126 px). The picture check sent two back, but scene 21's redraw had one too and was kept. `fal.trim_blank` now cuts a blank edge strip (8 or more rows or columns with no pixel darker than 225 of 255) off every picture before it's fitted to size, so no redraw is spent on it (`test_media.py`).
  - **Outside the gate, painted.** Video 5's front lawn was one place, its picture drawn from the house steps looking down the drive, so the painter put Wade, his crew, the tow truck and the dead on the near side of the gate in scenes 25 and 31 to 34, even after the picture check named it and the redraw tried again. A place is one camera view: `prompts/script.md` now says that when the story has people on both sides of a gate, fence, wall or window, the outside is a place of its own, seen from out there looking in, and the outside scenes happen in it. For scripts written from now on; video 5's script was approved before it.
  - **Clips smear crowds.** Video 5's painted scene 19 was a clip of a dozen small figures climbing the back wall and running; fal's animator turned them into blurred ghosts. `prompts/script.md` now keeps clips to one or two people or one object big in the frame doing one simple movement; crowds, many small figures and people running across the frame stay `kenburns`. Also there: a damaged barrier that still holds is described by what it still does (`prompts/visual.md`), after "the bent gate" was painted torn open with a gap Mr. Ashford stood in.
  - **Video 5 published** (Nov 3, 2026) as "Zombie Outbreak Survival: House-Sitting for a Billionaire", thumbnail 2, $21.50 in all (puppet runs $2.71, the painted repaint and two rounds of flagged fixes the rest; scenes 33 and 45 still show Wade and Mr. Ashford inside the gate after three tries each). Scheduled for Saturday, the owner wanted it up at once: `go_public_now` (an MCP tool, asked every time) makes a scheduled video public on YouTube (`Client.make_public`: status read and sent back whole with only the privacy changed, which drops publishAt) and sets its go-public time to now, so the analytics stage moves it to live and its metrics count from then (`test_youtube.py`). `edit_scene` also takes `motion` now (kenburns or clip; a motion change alone keeps the picture) and works on a failed video, and no longer resets the regen count: reset, the redraw was named like the scene's first picture, still on disk, and that was kept instead (`test_pipeline.py`).
  - If puppets come back: plan walks around solid occluders (or refuse a walk that passes behind one taller than a person's shoulders), hold the arms off the body in the standing poses, and judge every change on 3 or 4 scenes before a whole video.

## How the Claude Code session works (phase 17)

- `providers.llm: session` (the default since Nov 2, 2026, and since phase 20 the only real LLM): Claude's work is done by the Claude Code session the owner has open in VS Code, on their Claude plan. Since phase 19 that's all the writing (How the session writes), and since phase 20 the looking too (How the session looks). Gate comments were turned off for the same reason, and phase 18 deleted them with the in-app agent.
- **A stage that needs Claude parks.**
  - `SessionLLM._call` builds the request exactly as `ClaudeLLM` would: the system prompt, the messages and the schema. It hashes them into a key.
  - With no answer for that key, it stores a pending job, posts "Waiting for Claude Code: the titles (job N)" in the thread, emits `claude_job`, and raises `NeedsClaude`.
  - `run_video_stage` leases the video for `PARK_S` (15 min). It counts no attempt and leaves no error.
  - A later run builds the same request, so it finds the same job: no second job and no second notice. `run_forever` clears every lease at startup, so a restart just re-parks.
- **Answering.**
  - `answer_job` runs the stage's own check at once. `ClaudeLLM._ask` now hands `_call` a `verify` built from the same `_checked()` it uses itself, and `jobs.park` keeps it in memory by job id.
  - If the check fails, the problems go back to the session and the job stays waiting.
  - If it passes, the answer is stored and the video's lease is cleared, so the engine runs the stage again within `engine.idle_sleep_s`. This time `_call` finds the answer and returns it as the reply.
  - After a restart there's no registered check, so only the JSON is checked at answer time. The stage's check then runs on the re-run, and a failure becomes a new job holding the earlier reply and "What was wrong with it" (the API path's second attempt).
- **No cost lines.** A session answer costs nothing, and `costs.log` skips $0, so the session's work doesn't show in `run.py costs`. The `claude_jobs` rows are the record.
- **The endpoint.**
  - `/mcp` sits behind the same local-only Host and Origin check as the rest of the app, plus the MCP library's DNS-rebinding check.
  - The fleet tools are in How the chat runs the fleet. A video tool needs `video_id`; with more than one channel, the others take `channel`.
  - `wait` returns at once when an untaken job is waiting. Otherwise it waits up to 600 s for `claude_job`, `gate_reached` or `stage_failed`, then reports the waiting jobs and each unfinished video's state and waiting card.
  - `contact_sheet` tiles the `.thumb.jpg` previews, 24 at a time.
- **Connecting.** Start `run.py serve`, then open Claude Code in the workspace. `.mcp.json` names `http://localhost:8000/mcp`, and Claude Code asks once to allow the project's server. If the server wasn't running when the session started, `/mcp` reconnects.
- **Verified at $0** (`tests/test_session.py`, 5 tests):
  - A stub video (puppet pictures at `puppet_fps` 4) parks at titles. Its job is listed, waited on, taken, refused with the checks' words, accepted, and the video reaches the render card with those titles.
  - The restart path.
  - Taking, superseding and JSON-only checks.
  - A call that hasn't moved fails without the API.
  - The endpoint over real HTTP (uvicorn on a free port) with the MCP library's own client.
  - Verified against a real Claude Code session in VS Code on Nov 2, 2026 (How the session writes: video #5).

## How rendering works

- `render.engine: remotion` (default) or `ffmpeg` in `stickfleet.yaml`. Assemble tries Remotion; on any failure (Node missing, not installed, a render error) it renders with ffmpeg and posts "Remotion render failed, so ffmpeg rendered this one" with the reason.
- Remotion copies its whole public dir into every bundle on Windows (it only symlinks on other systems), so each render stages just that video's stills, audio and clips as hardlinks in `render/video_<stamp>_public/` and deletes it afterwards. Old MP4s in `render/` are never copied.
- The video is exactly as long as the narration (frames rounded per scene, not accumulated). Measured on a 3-scene render: 13.25 s of video for 13.24 s of audio. Audio is 48 kHz AAC.
- Clip scenes use `<Video>` from `@remotion/media` (muted; Remotion's docs recommend it over `<OffthreadVideo>` for new work). The clip plays once; `remotion_render.py` reads its length and extracts its last frame, and that frame holds with the usual Ken Burns push for the rest of the narration. Looping would jump back to the still every 8 s. The ffmpeg fallback holds the last frame without the push (`tpad`). A clip longer than its scene is cut. Audio uses `<Audio>` from the same package.
- Captions need `words_json` (word timestamps from the voice stage); a scene without words shows none. The stub voice spaces words evenly, so stub captions only roughly match.
- The highlight reel is cut from the final MP4 (first 20 s, then clip scenes, 60 s max), re-encoded so cuts land on any frame.
- Tuning, on 24 stub scenes (5.6 min of video, with clips): Remotion's default of 8 tabs took 174 s; 12 tabs 179 s, 16 tabs 188 s, 20 tabs 208 s, 4 tabs 206 s; `x264_preset: veryfast` 179 s, veryfast with 6 tabs 185 s. On a 30-scene sample, `--gl=angle` (GPU) and rendering muted changed nothing (102, 99, 100 s). The limit is Chrome capturing 1080p frames (about 55 a second here), so `concurrency` and `x264_preset` stay at Remotion's defaults.
- `render/remotion/node_modules` is ~790 MB, of which Chrome Headless Shell is ~280 MB (downloaded on the first render). `npm audit` reports a high-severity zod advisory (memory exhaustion when validating oversized collections) through Remotion's own dependencies; it matters for untrusted input, and our only input is our own `props.json`. npm's offered fix downgrades `@remotion/media`, so it's left alone. npm also skipped esbuild's postinstall script (allow-scripts); bundling works without it.

## How YouTube works

- Everything goes through `youtube/` (Google's `google-api-python-client`, `google-auth-oauthlib`, and `keyring`). There is no delete call anywhere in it; `tests/test_youtube.py` fails if one appears.
- Sign-in: `connect_youtube` in the chat (or `run.py connect <channel>`) runs Google's desktop flow with `prompt=consent`, checks every scope was granted (`youtube.upload`, `youtube.force-ssl`, `youtube.readonly`, `yt-analytics.readonly`; a sign-in missing one added later shows in `status` as missing scopes; connect again), asks `channels.list(mine=True)` which channel you picked, refuses one already connected to another of our channels, stores `{refresh_token, scopes, youtube_channel_id, title}` in Windows Credential Manager (service `stickfleet-youtube`, username = our channel id), and writes `youtube.channel_id` into the channel YAML (that one line; comments kept). The client id and secret stay in `secrets/client_secret.json`, not the keychain.
- `youtube.mode: stub` (default) writes `publish_request.json` and uploads nothing. `live` uploads; Publish is refused until the channel is connected, and needs a go-public time at least 15 minutes away.
- Live publish (`stages/publish.py`): check quota for the remaining steps; if the go-public time is under 10 minutes away, send the video back to the publish card (a past `publishAt` makes YouTube publish at once); upload private with `publishAt`, `containsSyntheticMedia`, `selfDeclaredMadeForKids: false`, category, `defaultLanguage: en`; then thumbnail, captions (SRT, English), playlist (skipped if the channel has none). Each finished step is saved in `publish_json["steps"]`, and `youtube_id` as soon as the upload finishes, so Retry resumes. If an upload's reply was lost, the next attempt looks for a same-titled upload since it started and adopts it instead of uploading again.
- Errors: 5xx and dropped connections count as attempts (3, with backoff). Anything that needs you (reconnect, quota, phone verification for thumbnails, other 4xx) fails at once with the reason on the error card; Retry resumes from the last finished step.
- After `publishAt`, analytics checks `videos.list` every 15 minutes until YouTube says public, then moves the video to `live` and posts the watch link. Still not public a day later, or rejected/failed, means an error card. Videos published in stub mode go straight to `live`.
- Quota: a publish books 1 upload + 500 shared units (thumbnail 50, captions 400, playlist 50); status checks cost 1 each.
- Not verified against the real API yet: there is no `client_secret.json` on this machine. Every call shape was checked against the installed library's discovery document and Google's reference pages, and the flow is tested against a fake service.

### Your turn (can't be automated)

1. Google Cloud setup from plan.md: one project; enable YouTube Data API v3, YouTube Analytics API and YouTube Reporting API; OAuth consent screen External and **published to In production**; an OAuth client of type **Desktop app**, saved as `secrets/client_secret.json`.
2. Create the brand channel and phone-verify it (youtube.com/verify).
3. Ask the chat to connect the channel to YouTube (`connect_youtube`, or `uv run python run.py connect zombie`), pick the brand channel, tick every box. Google shows an "unverified app" warning once; continue past it.
4. Day-1 test: `uv run python run.py youtube-test zombie`. It uploads a 20-second test pattern as unlisted and prints whether it stayed unlisted or YouTube locked it private (if locked, file the audit form it links). Remove the test video in Studio.
5. When ready for real uploads: `youtube.mode: live` in `stickfleet.yaml`, and the series `playlist_id` in the channel YAML.

## How topics and metrics work

- **Competitor check** (`stages/topics.py`, every `topics.poll_every_h`, 24): each competitor in the channel YAML is read through the Data API with `YOUTUBE_API_KEY` (`topics.competitors: youtube`): one `channels.list` for every uploads playlist, one `playlistItems.list` per competitor, one `videos.list` per 50 videos, about 3 of the 10,000 daily quota units per competitor. Uploads older than `recent_days` (90), shorter than `min_minutes` (8) or live/upcoming are skipped; the rest are ranked by views per day since publish (at least one day, so a few-hours-old video isn't first on a handful of views). Every check keeps a view-count snapshot in `competitor_views` for later velocity work. YouTube's RSS feeds would be free, but they've answered 404 for hours at a time since December 2025 (they did for every channel from here today), so they aren't used. An unknown competitor id is posted in the home thread. `competitors: stub` (the repo default) uses 8 made-up hits so the cards can be tried; with a real LLM they're only used when you ask (`run.py topics --propose`, the chat's `suggest_topics`), so Claude is never paid for ideas built on them unasked. `off` turns the check off.
- **Topic ideas**: after a check, if fewer than `propose` (3) topics are queued, the LLM gets the top `shown` (8) hits and the channel's topics so far (`prompts/topic.md`) and proposes 3 one-line ideas, each a variant of hits it names, with a one-sentence why. Code checks the count, length, that none repeats a topic the channel has (dismissed ones included), and that the cited hits exist; a failed reply gets the usual one retry. They go into `topics` (score = views per day of the best hit they build on) and post as a card in the home thread: Start video (creates the video and opens its thread) or Dismiss on each; the card closes when none is left queued. A round costs about $0.05 with Opus 5.5; it's logged with no video and capped by `topics.max_usd` (1) instead of a video budget. A failed check or round posts its reason once and tries again an hour later. The chat has `topics`, `start_topic`, `dismiss_topic` and `suggest_topics`.
- **Cadence** (`topics.cadence: true`): a channel that has published, with nothing in progress (failed counts as in progress), starts its top queued topic `lead_days` (5) before its next slot (last go-public time + `baseline_cadence_days`). The video stops at the outline gate like any other, so the most it spends unasked is one outline (~$0.30). A channel that has never published waits for you.
- **Metrics** (`stages/analytics.py`): 48 hours and 7 days after a video goes public, one reading: views from `videos.list` (the public count, minutes behind), average view duration and percentage and subscribers gained from the Analytics API's `reports.query` (`ids=channel==MINE`, `filters=video==ID`, Pacific dates), impressions and click-through rate from the reach files. Analytics lags a day or two, so the 48-hour watch-time numbers run low; the card says so. Each reading is a row in `metrics` (`after_h` 48 or 168) and a card in the video's thread. A problem reading them never fails the video: it's posted once in the thread and retried hourly. With `youtube.mode: stub` the numbers are made up and marked.
- **Reach** (`youtube/reporting.py`, every 6 hours for connected channels when `youtube.mode: live` and `youtube.reach: true`): the Analytics API has no impressions or CTR, so the first import creates a Reporting API job for `channel_reach_basic_a1` (or reuses one), then downloads each daily file created since the last import. YouTube posts the first files within 48 hours of the job, with 30 days of history, and keeps them 30–60 days. A newer file for a day already imported replaces it. Rows are summed per video and day (CTR weighted by impressions), and a reading's impressions and CTR fill in once every Pacific day of its window has arrived; the card updates in place. Google's page calls the CTR a percentage without saying whether 5% arrives as 5 or 0.05; the card assumes 5, so check it against Studio on the first real file.
- Analytics needs the `youtube.readonly` scope as of Google's October 2026 reference page, so Connect now asks for it; a channel connected before this phase shows Reconnect.
- Verified at $0: the check and ranking against a fake Data API (Shorts, old uploads and premieres skipped, quota booked), ideas from the stub and from Claude (the request, the one retry, scores), Start and Dismiss over HTTP, the cadence rule, stub metrics at 48 h and 7 d, live metrics and the reach import against fake Analytics and Reporting services (pending, then filled, backfills, only newer files), and in the browser: the topic card, Start opening the new video's outline, the card after Start and Dismiss, and a metrics card. Not verified against the real APIs yet: no `YOUTUBE_API_KEY`, `client_secret.json` or connected channel here. Call shapes come from Google's reference pages and the installed client's discovery documents.

### Your turn

1. In Google Cloud (the same project as the OAuth client): Credentials, Create credentials, API key, restricted to YouTube Data API v3. Put it in `.env` as `YOUTUBE_API_KEY`. Make sure YouTube Analytics API and YouTube Reporting API are enabled too.
2. Check `competitors` in `channels/zombie.yaml`: the one there (`UCy7Ke_F2ZANZpSwar-9ZGjw`) is Day by Day Stick, the reference channel (checked Oct 29, 2026 with a real API key). Add the channel ids (they start with UC; on a channel page, Share channel, Copy channel ID) of 3–6 channels in the genre.
3. Set `topics.competitors: youtube`, then `uv run python run.py topics zombie` to see their top recent videos ranked (a few quota units, free). `--propose` also asks Claude for ideas in live mode (~$0.05), or start `run.py serve` and the card appears within a minute.
4. If you connected the channel before this phase, connect it again (one new permission). After the first live video, the reach report starts arriving within two days.

## How the own-data loop works

- **Verdicts** (`core/performance.py`): each reading at 48 hours and 7 days is judged once it's complete (its click-through rate has arrived from the reach files), against the median of the channel's last 10 readings at the same point. Above the median on both average view % and CTR is a winner, below on both a loser, anything else mixed. Until 3 videos have that reading it's "early" and nothing happens. The card shows the verdict and the medians it was judged against. Stub readings are only compared with stub readings.
- **Surge**: a 48-hour winner asks the LLM for 2 follow-ups (`prompts/topic.md`'s `winner` turn: a sequel and adjacent scenarios), queued above everything else and posted as a "Follow-ups to winner #N" card in the home thread. A round costs about $0.05 and is capped by `topics.max_usd`; if it fails, the home thread says so and `suggest_topics` asks again.
- **Family holds**: every idea now gets a `family` tag (its kind of setting: "ocean", "underground"), which Claude reuses across rounds. A 7-day loser holds its topic's family for 4 weeks: queued topics in it rank last (with "held until …" on their card), new rounds are told to avoid it and code rejects ideas in it, and the cadence skips it. Typed ideas have no family, so a losing typed video holds nothing.
- **Ranking**: queued topics are ranked by competitor views per day × (1 + 0.25 × the family's winners minus losers here over the last 8 weeks, between −2 and +2). The cadence starts the top-ranked one, and the chat's `topics` tool lists them in that order with the reason.
- **Swap card**: a 48-hour reading with CTR below the median posts a card in the video's thread with its three thumbnails and three titles from the render card. `apply_swap` (it asks the owner first) changes it: in live mode it reads the video's current snippet and sends it back whole with only the title changed (`videos.update` clears any snippet field it isn't sent, description and tags included; 1 + 50 quota units), and calls `thumbnails.set` (50 units). In stub mode it writes `swap_request.json`. Each change that went through is recorded in `swaps` with the CTR before it, even if the other failed, and later reading cards show "swapped …, when click-through was X%; Y% since" once the reach files cover a whole day after it. `keep_swap` closes the card. `suggest_swap` only posts it.
- **Daily sign-in check** (`youtube.signin_check: true`, live mode): once a day per connected channel, `channels.list(mine)` (1 unit). A refused sign-in, or one for a different YouTube channel than the YAML says, posts a warning once (in `news`) and shows in `status` as the channel's sign-in error; when it works again, the home thread says so. Network trouble is retried in an hour without a warning.
- Verified at $0: verdicts with exact medians (early, winner, loser, mixed, waiting for CTR), follow-ups from the stub and through Claude's winner turn (its request, the held-family retry), the swap in stub mode over HTTP and in live mode against a fake Data API (the exact snippet sent, quota, a refused thumbnail after the title went through), holds and ranking, held topics skipped by the cadence, and the sign-in check (wrong channel, 401, not posted twice, recovered). In the browser: the follow-ups card with family tags and rank notes, a mixed reading with its swap card, Apply, and a winner's card. Not verified against the real APIs: no connected channel here.

### Your turn

Nothing new to set up: the loop starts acting once a channel has 3 videos with 48-hour readings (and their CTR). Watch the first swap cards and follow-ups, and check the first held family makes sense; the tag is Claude's.

## How Claude is asked

Every call of Claude's work is built the same way (`providers/claude.py`), then sent to the Claude Code session as a job (How the Claude Code session works). Until phase 20 there was also an API path through the `anthropic` package (`providers.llm: claude`, with prompt caching, effort and token settings, server-side fallback after safety refusals, and costs from usage); git history has it, from before Nov 2, 2026.

- **Prompt files** (`prompts/`) are read fresh on every call, so an edit applies to the next job. A file is the system part, then `<!-- user turn -->`, or named turns: outline and script have `new` and `revise` (and outline `next_part`), regen has `visual` and `narration`, picture.md has `still` and `change`, puppet.md has `stage` and `parts`. `{placeholders}` are filled in code. An unknown one, or a per-video one above the first marker, stops the stage with a message naming it before any job is made. The counts the prompts ask for (`{beat_count}`, `{scene_count}`, ...) come from `providers/checks.py`, so a prompt can't ask for what the checks reject.
- **Schemas.** Each kind of reply has a JSON schema (`OUTLINE`, `SCRIPT`, `PICTURE`, `STAGE`, `SHEET`, ...), shown to the session as the shape to reply with. Fields are listed in the order they're written, each after the ones it depends on.
- **Checks in code** (How continuity works has the current numbers): the outline, the script (whole, or a part so far), a scene fix, titles with their thumbnail words and description, topic ideas, a review, a stage map, part names, the props list and a scene sheet each have one. An answer is checked as it arrives; after a restart, when no check is registered, the stage's check runs when it reads the answer, and a failure asks once more with the earlier reply and "What was wrong with it" (a second failure stops the stage with the problems on the error card).
- **Revise vs regenerate:** `revise` sends the last draft plus every note ("change what the notes ask, keep the rest word for word"). `regenerate` clears the draft and writes a fresh one with every note so far. Flagged scenes get the lines before and after them.
- **Stop** (`stop_writing`) drops a waiting outline, script or review job and returns the video to the card it came from (How the session writes).

## How voice, pictures and clips work

- Turned on per provider: `providers.tts: elevenlabs`, `providers.images: fal` and `providers.video: fal`, with `mode: live`. Any can stay `stub` while the others are real, and stub costs stay marked simulated.
- **Voice** (`providers/elevenlabs.py`, plain HTTP with `httpx2`): one `POST /v1/text-to-speech/{voice_id}/with-timestamps` per scene, `xi-api-key` from `ELEVENLABS_API_KEY`, `model_id` from `models.voice` (`eleven_multilingual_v2`, which ElevenLabs calls the steadiest over long narration; `eleven_v4` is newer and more expressive, but its timestamp support isn't in ElevenLabs' docs yet). The lines before and after the scene go as `previous_text` / `next_text` so the voice flows across 120 separate requests. The reply's per-character timings become the word list captions use; the scene's length is read from the MP3 (`ffmpeg.duration_ms`), not the timings. Optional `elevenlabs.voice_settings` override the voice's own.
- ElevenLabs caps parallel requests by plan (Creator 5, Pro 10), so the provider holds its own limit (`elevenlabs.concurrency: 4`) under the engine's 8. A 429 or 5xx is retried 4 times with backoff (honoring `retry-after`); a bad key or used-up credits (401/403), an unknown voice or another 4xx stops at once. A placeholder `voice_id` stops before any request.
- **Pictures** (`providers/fal.py`, `fal-client` 1.0.3): `models.still` is `google/nano-banana-2.1/edit`. The channel's `character_ref` is uploaded to fal's file storage once (again when the file changes or after an hour) and sent as `image_urls` on every call. The prompt is `prompts/still.md` filled with the scene's `visual_prompt` and the channel's `style_prompt` (thumbnails: `prompts/thumbnail.md` with the title and which of 3 versions). `aspect_ratio: 16:9`, `resolution` from `fal.resolution` (1K default, about 1333×750), then scaled and cropped to 1920×1080 (thumbnails 1280×720). `fal.concurrency` limits calls at once.
- fal bills this model by tokens and the reply doesn't say what it cost, so the logged cost is the list price per picture in `fal.prices` ($0.044 at 1K, $0.063 at 2K, with one reference image). fal errors: 401/403 and content-policy refusals stop at once; others go through the stage's 3 attempts. Uploaded references are public URLs on fal's storage (anyone with the link can open them).
- `visual.md` now tells Claude not to describe the character's body, face or clothes, since the reference picture carries the look (before, it asked Claude to pick an identifying item, which could contradict the reference's red scarf).
- **Clips** (`FalVideo` in `providers/fal.py`): the clip scene's own still is uploaded and sent as the first frame, with `prompts/clip.md` filled with its `visual_prompt` (Claude writes what moves for clip scenes) and the channel's style. The MP4 is downloaded, checked to be a playable video at least 1 s long, and saved. `models.clip` picks an entry in `fal.clips.models`, which holds what that model takes (the still's field name, the lengths it offers, extra arguments) and its price per second, so switching models is a config change; `fal.clips.seconds` is the length (checked against the model's lengths at startup). `fal.clips.concurrency: 4`. Waits up to 20 minutes for fal's queue.
- Default clip model: **Kling 3.0 Pro, silent, 8 s, $0.90 a clip** ($7.20 for 8 clips). fal's own pages (Oct 29, 2026) price these per second, silent: Kling 3.0 Pro $0.112 and Standard $0.084 (any length 3–15 s); Wan 2.6 $0.10 at 720p and $0.15 at 1080p, Wan 2.6 Flash $0.05 / $0.075 (5, 10 or 15 s only). The plan's $0.0375 for Wan was from a third-party list; on fal, Wan 2.6 at 1080p costs more per second than Kling Pro and can't do 8 s. All four are in the config. fal's page doesn't say what size Kling's videos are; both renderers scale clips to fill 1080p. Wan Flash's page says silent costs less than its listed price without saying how much, so it logs the listed price.
- A clip plays once and then its last frame holds (How rendering works), so an 8 s clip in a ~15 s scene is 8 s of motion and 7 s of slow push.
- Budget: every paid call holds its price against the budget while it runs (`ctx.reserve`), so the 8 clips the clips stage starts at once can't all pass the same check. Clips that don't fit are downgraded to Ken Burns with a notice; stills, voice and thumbnails stop with the budget error as before. In the test, with the hold turned off, three $20 clips all ran against a $50 budget; with it, two ran and one was downgraded.
- **Thumbnail text**: `titles.md` now asks for `thumb_texts` too, one per title (2–4 words, checked in code). The thumbs stage draws each in the thumbnail's upper left in code (`providers/images.py caption`): capitals in Impact (Arial Bold where it's missing), yellow with a black outline, as big as fits in two evenly split lines across 60% of the width. `thumbnail.md` asks the picture model to keep that corner plain. `thumbs_json` keeps the texts; the render card and `review` include them.
- Verified at $0: clips with a fake fal client and real MP4s, the Kling and Wan request shapes, errors, the budget downgrade with clips running in parallel, a flagged clip scene redoing its still and then its clip from the new still, captions drawn on the thumbnails, and the hold in ffmpeg (a test compares frames) and in Remotion (a render's frames: the clip's last frame at the cut, then the push). Not verified against the real API yet: no `FAL_KEY` here. Request and reply shapes come from fal's OpenAPI schemas for each model.

### Your turn

1. Put `ELEVENLABS_API_KEY` and `FAL_KEY` in `.env`.
2. Pick a voice in ElevenLabs and put its ID in `channels/zombie.yaml` (`voice_id`). `uv run python run.py voice-test zombie` reads one line in it (a fraction of a cent); try a few voices.
3. Replace `channels/zombie/character.png` if you want a different look (it's a plain stick figure with a red scarf). `uv run python run.py still-test zombie` draws one picture with it (~$0.04); look at `data/still_test_zombie.png`.
4. `uv run python run.py clip-test zombie` animates that picture with Kling 3.0 Pro (8 s, ~$0.90; a few minutes) into `data/clip_test_zombie.mp4`. Check that the character and line style survive the motion. To compare, set `models.clip` to `fal-ai/kling-video/v3/standard/image-to-video` (~$0.67) or `wan/v2.6/image-to-video/flash` (needs `fal.clips.seconds: 5` or `10`) and run it again.
5. `uv run pytest -m live` runs one real voice line, one real still and one 3-second clip too (~$0.40 together).
6. In `stickfleet.yaml`: `tts: elevenlabs`, `images: fal`. For plan.md's first video keep `video: stub` and set `clips_per_video: 0` in the channel YAML, make one full video, watch it end to end, and check the contact sheet for character drift and the pan for jitter. That is about $7 of voice and pictures plus Claude.
7. Then `video: fal` and `clips_per_video` back to 8 for the next one: about $7 more for the clips. Watch the hero scenes where a clip hands over to its held last frame.

## How continuity works

Built after the first real video, whose review found the same room drawn differently scene to scene, a cut from a bedroom to the street with no word of how, a neighbor let in and never mentioned again, rationing with no numbers, and no word of what had happened to the world. It applies to every channel: it lives in the shared prompts and the pipeline, not in a channel's YAML.

The idea is the one an LLM already works by: everything is written knowing what came before. The structured-output schemas list each field after the ones it depends on (checked against the real API: fields come back in that order), so the outline writes its cast and tracker before its beats, and the script writes its places before its scenes and each scene's place, cast and line before its picture prompt. Pictures follow the same rule: each is drawn from fixed references, and a place that changes is redrawn from its previous picture.

- **Outline** (`prompts/outline.md`, checked in `checks.outline`): a `backstory` (what happened and how it reached the character, told right after the hook); a `cast` of at most 6 with a name, a fixed `look`, a role and a `thread` (how their part runs and ends); a `tracker` of 2–4 things to count with a unit and a starting amount (water in L, food in days, a countdown where it fits); and each beat's `cast`. The last beat that lists someone is where their thread ends. The card shows all of it, and the backstory can be edited inline (`set_backstory`).
- **Script** (`prompts/script.md`, checked in `checks._continuity`): `places` first (1–15, each a slug, a name and a 30–60-word `look` with the layout, furniture, colors and light), then per scene `place`, `cast`, `narration`, `move`, `tracker`, `set_change`, `shot`, `visual_prompt` and `motion`. The checks: every place is known; **whenever the place changes, `move` must quote, word for word, the words in that scene's line that say where we are now**, so a cut can't happen silently; cast members appear only in beats that list them (cold-open scenes excepted), and each is named in a line of the last beat that lists them; every beat shows the tracker at least once, and each snapshot lists every tracked item once with an amount of 0 or more; `shot` is wide, medium or close-up. An outline from before the cast and tracker skips those rules. The script card shows each scene's place, cast and tracker line, the set changes, and the list of places.
- **Pictures** (`stages/stills.py`): a wide or medium still is drawn with three kinds of reference image: the character, the place, and up to two cast members in it (any more are described in words). The first scene that needs a place draws it empty in the channel's style from its `look` (`prompts/place.md`); a `set_change` makes the next version from the previous picture (`prompts/place_change.md`), and each scene is drawn in the version it comes after (`scenes.place_v`, set when generating starts). Cast members are drawn once, full length (`prompts/person.md`). Locks make parallel scenes wait for one picture instead of each drawing it. The files are in `media/<video>/sets/`, named with a hash of what they were drawn from, so a changed description draws a new one. Their cost is logged as stage `sets` (about $0.5–0.9 a video: 15 places at most, plus changes and cast). `still.md` names each reference image in a line built in code.
- **Shots**: the image model keeps the place picture's viewpoint. Asked for a reverse angle it redraws the reference view, and asked for a close-up it pastes the whole room in behind like a diorama (both seen in a real test). So wide and medium shots get the place picture, with a medium shot drawn closer in from the same side. A close-up gets the place in words only and shows a face, hands or one object. `script.md` tells Claude this, so it writes prompts for that view. A close-up that carries straight on from the scene before it also gets that scene's still (Pictures checked and chained, below), so consecutive close-ups stay in the same room.
- **On screen** (Remotion, `render/remotion/src/StatusBox.tsx`): a box in the top left with the day and every tracked amount, an arrow and color on the ones that just moved ("▼ 3"). It slides in for the first 6 s of a scene that starts a new day or changes an amount, then fades. Amounts start over when the story goes back in time after a cold open, so Day 1 doesn't show as a jump up. Videos with no tracker get just the day. `stages/assemble.py statuses` works out each box. The ffmpeg fallback draws none.
- New columns: videos `places_json`; scenes `place`, `place_v`, `cast_json`, `tracker_json`, `shot`. Older videos keep working: no places means stills from the character alone, as before.
- Checked against the real APIs: both new schemas with Claude (a tiny Haiku call), and fal with one room, its barricaded version, one cast member, and stills in that room on different days and framings. The room's door, coat hooks, TV, window, lamp, shelves and kitchen matched from shot to shot, the taped window stayed taped, and the cast member matched her reference. One fal call came back "no media generated" and worked on a retry; the stage retries those anyway. Pictures in `data/sample_continuity/`.
- Thinking: the continuity rules made Claude plan much longer. The first real outline used 26,350 output tokens ($0.54, against about $0.14 before), and the first script spent all 64,000 tokens thinking and stopped after 2 scenes ($1.32, wasted). `claude.max_tokens` is now 48,000 for outlines and 128,000 for scripts (Opus 5.5's most), and `script.md` asks for a short plan and no scenes drafted in thinking, since the scene fields carry the state. Expect about $1.50–2.50 a script call and $4–5 when the checks send it back once.
- **Storytelling** (after comparing video 2's script with a successful competitor's): ours read like a survival manual with a story around it. It spent several scenes teaching each technique and opened nearly every day by reciting the supplies. It had no recurring signature, few rules of the world, few callbacks, and it stated its message at the end. The shared prompts now ask the outline for a signature (recurring details that pay off at the climax), two or three rules of the world that the turning points use or break, callbacks to earlier days, and a heart (one line or promise that comes back changed). Skills are "worn lightly": one practical move per beat, shown in a line or two. The script is told like a storyteller (fragments, short dialogue lines, held-back reveals, exact times at peaks), says numbers only when they change the story (the corner box shows the rest), and ends on an image rather than an explanation.
- **Point of view**: a channel's `narrator` is `you` (the viewer is the main character, who has no name) or `third` (a named hero; the default). It fills `{narrator}` in outline.md, script.md and regen.md. The zombie channel is `you`.
- **Movement**: `providers.video: fal` with `clips_per_video: 8` on the zombie channel (Kling 3.0 Pro, 8 s, about $7.20 a video). A real 5-second clip from a sample still is in `data/sample_continuity/`.
- **Who is in the picture** (from video 1's render): the main character's reference went with every still, so they were drawn into street shots where the narration had them at a window, and over other characters. Now a still gets it only when its visual prompt says "the stick figure" (`checks.HERO`). Otherwise the prompt says they aren't in it, and the character's picture is sent only as a style guide when no other reference exists. Cast labels carry their look, and nobody else may wear the main character's clothes.
- **Medium shots** used to zoom in and move the door and window to fit. Now they keep the place picture's framing with the people nearer the camera.
- **Looks**: a scene's `looks` lists lasting changes to what someone has on (body armor on or off, a bandage, a borrowed cap), `who` plus `now` or "as usual". `start_generating` carries them forward into `scenes.looks_json`. A still showing that person sends their reference redrawn with the look (`prompts/person_change.md`, once per look, `look_*.png` in `sets/`), so armor put on in one scene is on in the next.
- **Length and suspense** (the owner found 26 minutes too long and without suspense): videos are now about 12 minutes: 8–10 beats, 3–4 of them hero beats, 40–65 scenes, about 1,750 words (1,500–2,000 pass), at most 4 cast and 10 places. The outline is built around one big danger and one deadline set up in the first minute. Every beat brings it closer, beats end on cliffhangers, and no beat is a small problem solved and forgotten.
- **Pacing** (video 2 felt too fast): it read at 166 words a minute with no gap between scenes, and fit about 15 big events into 11½ minutes, so most got one to three scenes (Day 15's horde breaking in, the raider running into them and the plate over the stairs took 36 seconds). Now: `elevenlabs.speed: 0.9` slows the voice to about 150–155 a minute (it read the same line 8% slower than 1, measured; the owner picked it over 0.88 by ear), on top of the voice's own settings (read once per voice, since settings sent with a request replace them); `render.pause_ms` (400) holds each picture in silence after its line, and `render.new_day_pause_ms` (1000) before a new day or beat and at the end (`stages/assemble.py pauses`). The outline has 8–10 beats with one event each; each hero beat gets 7–9 scenes (the build-up, the moment, the aftermath; fewer than 6 is sent back by `checks.script`). The script spends longer on what comes before a big moment than on the moment, writes whole sentences instead of strings of fragments, and drops shorthand like "Rule three brings the crowd".
- **Every day told** (the owner: the channels that do well go day by day, even when nothing happens): beats only mark the days with events, and the script tells every day between them, each on its own or two or three quiet ones in one scene labeled "Day 3-5" (`checks.STRETCH_DAYS`, or a tenth of the span in a story longer than a month). `checks._every_day` sends back a script that skips a day or stretches too far; stories labeled in weeks or months aren't checked. outline.md asks for a span the story can fill, about a month.
- **The rules bind everyone** (video 2: "sound brings the dead", and the hero tapes a clicking brace hinge, yet raiders drove a van through the cul-de-sac, idled it at the curb and sped off after a fight with nothing coming until the next night): outline.md's rules bullet and a script.md chain rule now say the threat reacts to everyone by the same rules and within minutes, so other people get away with it in a way the story shows (on foot, engine off, a distraction) or pay for it, and the outline checks every beat against the rules.
- **Pictures checked and chained** (video 3's review: a towel drawn beside the knee it should press on, the hero standing when the line says he went down, zombies inside the car-wash bay the words put them outside of, the pickup redrawn as a sedan, the stairwell's steel plate drawn as a back wall and inherited by five scenes, "midnight" scenes in daylight, and consecutive close-ups in three different rooms). Every text output had a check and a retry; no picture did, and an image model gets about one prompt in ten wrong, so 58 pictures meant 5–8 wrong ones every video whatever the prompt said. Now (`stages/stills.py`): stills are drawn **one at a time in scene order** (`run_scene_stage(limit=1)`), and a scene that carries straight on from the one before it (same place, same day) sends that scene's still as one more reference, "the moment just before this one", so poses, light and who holds what carry over and close-ups stay in the room. **Every still, set change and look picture is checked** by `models.check` (Sonnet 5.5, `prompts/picture.md`, the picture at 1280 wide as a JPEG, with the picture before it when there is one): it reports what it sees, then what a viewer would see is wrong, as instructions. A picture with problems is drawn once more with them in a `{fix}` paragraph (still.md, place_change.md, person_change.md); still wrong after that, it's kept and the problems are posted in the thread so the scene can be flagged from the render card. About a cent a check, logged as stage `check`; a video's pictures take 15–25 minutes instead of 3, since they're drawn in order. **Calibration** (a live bench on video 3's scenes 23–32, $1.18): the chain worked at once (the break-in became one continuous dark room with poses carrying over), but the first checker listed 3–5 problems for every picture and the redraws changed too much; it didn't know the main character's look and told a redraw to take off his beanie and scarf (which the chain then carried on), it policed left and right on stick figures (wrong every time), and it asked for blood. Now the check gets the character reference and the line before as well, never reports sides or asks for blood, lists everything it notices in `noticed` and sends at most three at-a-glance problems to the redraw, and `_checked` keeps whichever of the two drawings checked better. Re-run on scenes 29–32 after that: two passed first time, two were redrawn for real reasons (a bright midnight, the towel beside the knee), the hero kept his look, $0.35 for four scenes. The bench script is in the session scratchpad (`bench_chain.py`); it draws into a scratch folder from the real providers and touches nothing in the database. Then video 3's 16 worst scenes were redrawn through the live pipeline (flags with no note, plus line and prompt edits written straight into the database): 15 came out right, 2 of them after a redraw; the check posted notices for 3 it couldn't fix in two tries (27, 43, 53), and only 43 (a black band along the bottom, the hero at the top of the stairs instead of halfway down) is worth another flag. About $5.30 all in, four clips included.
- **fal locks the account at zero balance** and keeps answering `403 User is locked. Reason: Exhausted balance` for about 35 minutes after a top-up, to new keys as well; the dashboard shows the credits the whole time. The stills stage fails final with that message and Retry resumes where it stopped, nothing already drawn is paid for twice, and a clip already in flight finishes and is charged. A free probe: a queue request with `image_urls: []` answers 403 while locked, 200 (queued, then rejected) once unlocked, 401 for a bad key. `visual.md` now asks for the light in every prompt (the place picture is drawn by day, so a prompt without it got daylight at midnight) and for a continuing scene to say what changed since the last one. **Things that block a way** (video 3, scene 31: "a steel plate laid across the whole stair opening", drawn as a plate lying on the landing floor beside the stairs, which stayed open; the set change was drawn the same way and five scenes inherited it): visual.md, script.md's `set_change` and the check now say a blocking thing is drawn where the way was, so the way is gone from the picture (the stairs end at a plate bolted upright between the walls; no steps visible), and the check reports a plate beside the stairs as blocking nothing. The old guide example asked for the hardest version to draw, a lid laid flat over the stair opening seen from the landing.
- **Time is real** (video 3, scenes 30–31: the stairwell is "full of reaching hands", and in the next scene the stabbed hero drags the plate across and bolts it down while they're on the stairs): outline.md and script.md now say everything takes the time it would really take and the threat doesn't wait, so a minutes-long job happens before the threat is close or after the story shows what buys the time, and a threat seconds away allows only moves that take seconds. The outline checks every beat for it. Not checkable in code; a candidate for a script logic check (write, critique against the rules, revise once), the same pattern as the picture check. Stub mode: `StubLLM.judge` lets tests say what a check finds.
- **Looks in clips** (video 3, scene 30: the raider in the undershirt ran down the stairs wearing the hero's knee brace, cane in hand): `stages/clips.py` sent every look in `looks_json` to the animator, the main character's included, even when he wasn't in the picture, and Kling put them on the one figure it had. `clips.wearing_of` now sends only the looks of people in the picture (the main character when the visual prompt names him, and the scene's cast), and `clip.md` says nobody gains anything the picture doesn't show on them.
- **The YouTube description** (video 3's publish card opened with the outline's planning note, "Open cold on the worst moment... Then rewind to the promise"): `titles.md` now also asks for a `description`, three to five sentences for viewers in the narration's point of view (the fix they're in, the span, the danger and deadline, a rule or two, no ending), checked by `checks.description` (150–900 characters, no < >, and sent back if it says "open cold", "rewind", "the hook" or "the promise"). The thumbs stage keeps it in `thumbs_json`, and `metadata.description` puts it above the chapters and the disclosure, falling back to the hook for videos from before.
- **The owner's own story**: the new-video text can be a full story (events, people, ending, even rough notes). outline.md treats it as the backbone and refines it rather than replacing it, inventing only what's left open. Paste it into + New video. The card heading shows only its first two lines.
- **Series** (`core/series.py`): once a video's script is approved, `next_part` in the chat starts the next one. It takes the owner's direction or their own story for the part, or nothing to carry the story on. A next part has `videos.prev_video_id` and `part`. Its outline uses outline.md's `next_part` turn, built from the story so far: every earlier part's outline, how it ended on screen (the last three lines), where the tracker stood and what people had on. It opens with a recap, continues the days, and ends on a question for the next part. Returning cast keep their look word for word (`series.keep_looks`). The script gets the earlier parts' places to reuse. `start_generating` inherits every earlier place with its set changes and the last part's looks, so the reference pictures have the same names, and `stills._from_earlier` copies them instead of drawing them. Titles end with "(Part N)", and once the part before is on YouTube, the description opens with a link back to it. Every outline now leaves one question open, so any video can get a next part.
- Not done: no button to redraw a place or cast member whose reference came out wrong. For now, delete its file from `media/<video>/sets/` and flag that place's scenes.

## How puppets work (phase 1: the look test)

The generative pipeline (stills, set changes, looks, clips) draws every scene anew, so every scene can drift: the
cop walking as the hero, the towel beside the knee, the plate off the stairs. The cutout pipeline paints each
thing **once** and moves it by code, so nothing can drift. Nothing of the writing changes; it replaces the
drawing stages, in phases. Phase 1 is the look test, built to be judged before anything else is replaced.

- **Parts sheet** (`prompts/parts.md`, `FalImages.sheet`): fal draws the character's parts separated on flat
  green from the look picture (`channels/zombie.yaml` `puppet:` says what each part is). `puppet/parts.py` keys
  the green out, finds the blobs, numbers them on a copy, and asks the check model which is which
  (`prompts/puppet.md` `parts` turn, `ClaudeLLM.name_parts`). The hero's sheet came out clean on the first try
  (head with beanie, scarf, mitten, cane, brace; 4.4¢) and is in `channels/zombie/puppet/hero/`.
- **Rig** (`puppet/rig.py`): the stick figure as the reference draws it: a torso stroke, arms and legs as strokes
  with round caps, no feet, the painted head on the neck, the scarf over the neck, mittens on the hands, the
  brace on the right knee, the cane in the right hand. Lengths are fractions of H (the standing height) so one
  pose draws at any depth. Poses are angles written for a figure facing right and mirrored for left. `LIMP` is a
  four-key cycle: the braced leg stays straight and steps short, the body dips when it lands, the cane plants with
  it. `ground()` stands the lowest point of the legs on the floor line.
- **Stage** (`puppet/stage.py`, `prompts/puppet.md` `stage` turn, `ClaudeLLM.map_stage`): the check model reads a
  labelled grid over the place picture and gives the floor as points with a standing height at each, named
  spots (doors, stairs top/bottom, furniture) and the light. Kept as `<place>.stage.json`; `overlay()` draws it
  for checking by eye.
- **Frames** (`puppet/draw.py`, `puppet/animate.py`): a scene sheet says who is where doing what from when to when
  (`do` a pose or a cycle, `start`/`end` spots), the camera keyframes (a spot means the middle of the person
  standing there) and the light (a level and tint, a lamp glow). Figures are drawn far-side first at 2× and
  scaled down, with a soft shadow (the small jitter every 4 frames that was meant to make the lines feel drawn
  read as shaking on a figure standing still, and came out after video 5), then the tint, then the camera crop. Frames go straight to ffmpeg with the scene's narration. 311 frames of 1080p take 25 s on the CPU.

**Result**: `data/puppet_demo/scene23_puppet.mp4` is scene 23 of video 3 (the stairwell at midnight) with the hero
limping from the bathroom door to the top of the stairs and kneeling, over its real narration; `contact.jpg`
beside it has six frames. The painted parts keep the stills' look and shading; the figure is the same in every
frame; it stands on the floor at the right size for its depth; the plate, when it comes, will sit at the stairs
spot by construction.

**Caveats of the test**: the Anthropic API account ran out of credits mid-run, so the parts were named and the
stairwell mapped by hand for this demo (the code paths exist and are tested with the stubs; `puppet_demo.py` in
the session scratchpad runs them live once credits are back). The kneel pose is rough; the mittens don't yet
turn with the arm's side; the camera clamps at the picture's bottom edge, so a figure on a floor near the bottom
sits low in the frame. Those are pose and camera work, not pipeline problems.

**Next phases** (each judged on one scene before the next): 2. places drawn in layers (back, middle, front) with
props painted once and placed at spots; set state (a door closed, a plate up) carried between scenes. 3. the
stager: Claude writes the scene sheet from the script with the previous sheet in hand, checked in code against
the stage (no one off the floor, a blocked way has its blocker, nothing appears from nowhere). 4. a render stage
that replaces stills, sets and clips, feeding the existing Remotion assembly as clips. 5. actions started on the
narrator's words, a pose library per cast member (zombies, Eli), expressions as head variants, and the optional
motion-control pass on fal for the hero scenes.


## How puppets work (phase 2: props, state, a second puppet)

- **Props** (`puppet/props.py`, `prompts/props.md`): fal draws the story's objects on one green sheet in the style
  of a reference picture; `parts.build` cuts them with their own pivots (a plate stands on its bottom edge, a drill
  is held by its grip) and sizes in H. A part is cut along its own blob now, not its box, so a diagonal rifle doesn't
  bring the drill beside it along. The six demo props are in `channels/zombie/props/`.
- **Placed and attached** (`puppet/animate.py`, `puppet/draw.py`): a scene's `set` stands props at spots (with an
  angle and an offset in H); a figure's `attached` puts a prop on a joint (`r_hand`, `r_knee`...) with an angle.
  Everything is drawn back to front by where it meets the floor, so a person in front of the plate is in front.
- **Set state** (`puppet/state.py`): {place: {prop: placement}}; a scene starts from the state the scene before left
  and says only what it changes (`place`, `remove`). The demo stands the plate across the stairs in scene 31 and
  scenes 32 and 42 inherit it untouched.
- **Which way a part faces**: Claude says `left`, `right` or `front` for each part it names (a cap's visor, a
  mitten's thumb, a drill's bit, a scarf's tail); `draw._rotated` mirrors a part only when the figure faces the
  other way from how it was painted. Before this, Eli's cap looked away from whoever he faced.
- **Occluders**: the stage map can list foreground things (a banister, a table) as polygons with a `base_y`; the
  renderer cuts them from the painted place and draws them over anyone whose feet are above that line.
- **A second puppet**: Eli, from his cast picture, two parts (head with cap, shirt), `scale` 0.62 of an adult.
  Any cast member is a sheet away. New poses: reach, kneel_work, kneel_press, sit, sit_knee_up; a plain walk cycle.

**Result**: `data/puppet_demo/plate_scenes_31_32_42.mp4` (37 s, the three scenes back to back over their real
narration; `contact2.jpg` beside it). The plate stands across the top of the stairs because the stairs-top spot is
where it stands; the drill, wrench and flashlight are in hands; the towel is on the raised knee; Eli is the same
boy in all three. Two fal pictures, 9 cents. Parts and props were again named by hand (no Anthropic credits).

**Still to do in later phases**: the stager (Claude writes these sheets from the script), word-timed actions,
head variants for expressions, a motion-control pass for the hero scenes, and the render stage that feeds the
assembly. Props still need a shadow on the wall when leaning; Eli's shirt hides the top of his arms.


## How puppets work (phase 3: in the pipeline)

`render.pictures: puppet` in stickfleet.yaml swaps the drawing stages. The writing (outline, script, voice) and
the assembly (thumbs, Remotion, publish) don't change; stills and clips stand aside. Three stages take their place:

- **assets** (`stages/assets.py`, per video, after the voice): draws each place's picture (the same call the stills
  pipeline uses) and has the check model map it into a stage (`<picture>.stage.json`, with a `.map.jpg` to check
  by eye); builds the main character's puppet once per channel (`data/channels/<id>/puppet/hero/`) and each cast
  member's once per video (`media/<video>/puppets/<slug>/`, from their cast picture, head and shirt); asks Claude
  for the script's props and the cast's sizes (`prompts/inventory.md`), reuses props already in the channel's
  library (`data/channels/<id>/props/`) and paints the new ones on one sheet into it. Writes `videos.assets_json`.
- **sheets** (`stages/sheets.py`, per scene, in order): Claude writes the scene sheet (`prompts/sheet.md`,
  `puppet/sheet.py`): who stands where doing what from when to when, timed on the narration's words (each word
  with its second), what stands in the place, the camera (a spot, or a person it follows) and the light. It gets
  the stage's spots with their positions, the people, the props, the poses and movements, where the scene before
  left everyone, and what stands in the place. `puppet/sheet.py check()` sends a sheet back with what's wrong
  (an unknown spot, pose or prop, overlapping or out-of-range times, a camera on nothing). The set state after
  the scene (`scenes.set_json`) feeds the next sheet.
- **animate** (`stages/animate.py`, per scene, in parallel): resolves the sheet to puppets, placements and light,
  draws every frame at `render.puppet_fps` and encodes it with the narration; the first frame is the scene's still
  for the contact sheet and the scene becomes a `clip` scene for the assembly. Costs nothing.

The stubs run the whole path for $0 (`tests/test_puppet_pipeline.py`: a 4-scene video staged, animated and
assembled, the stub script's cot placed in scene 1 and still there later, no stills or clips cost logged). The
live run needs Anthropic API credits for the inventory, the maps and the sheets; the two new prompts render
without placeholder errors. Costs per 58-scene video, estimated: maps ~15¢, puppets and props ~30¢, sheets
~$1.50 to $2.50 (Sonnet, one call per scene with a retry when a check fails); no fal clips.

**First live staging** (Nov 1, 2026, video 3's stairwell, scenes 31, 32 and 42, 6 to 8 cents a run): Sonnet named
the hero's five parts exactly as the hand naming had; mapped the stairwell (floor, 7 spots, the lamp); listed the
script's props (6 new ones, the 6 painted ones reused); staged the three scenes with the plate across the stairs,
the drill, towel, wrench and flashlight in the right places. Four runs, each fixing what the one before showed,
all in shared code and prompts:
- A spot inside an occluder hid whoever stood there (Eli vanished behind the banister): `checks.stage_map` refuses
  a spot behind an occluder, and the map prompt asks for solid occluders only (a banister's gaps would hide people
  behind them too).
- The towel went on Eli's knee: the sheet prompt says a thing attaches to the person it is on.
- Scene 32 lost the midnight light: the previous scene's light is in the "where things were left" summary and the
  prompt keeps the time of day unless the line changes it.
- The cane was drawn in the hand holding the drill: a prop in the right hand sets the cane down (`draw.figure`).
- Everyone piled onto one spot: actions take a `side` (left/right, a step from the spot), and the check refuses two
  people on one spot and side at the same time.
- The inventory listed the cane and the jacket: looks are painted with the puppet, never as props.
- The face always looked at the camera: every puppet now has a second head, `head_side`, painted three-quarters to the right and mirrored for left, drawn whenever the figure faces a side; an action with `look: camera` uses the front head (a reaction to the viewer). The hero and Eli got theirs on a sheet of their own (`parts.add` merges parts into a puppet); new characters get it on their first sheet.
`data/puppet_demo/live/` has the sheets, the map overlay and the rendered three scenes.

Not yet: regen in puppet mode (a flagged scene goes back to `voiced` and is re-staged, but later scenes keep
their old set state), head variants for expressions, the motion-control pass, and the look of a whole video:
the next step is one video of the zombie channel with `render.pictures: puppet` (about $8).


## How the reviewer works

The pictures can only be as sensible as the script, and video 3's script had a man with a rebuilt knee hauling a
door-sized steel plate upstairs and bolting it over the staircase while the dead hammered the other side. The
writer's prompts already said "time is real" and "real skills"; what was missing was a second reading. So every
outline and script now gets one (`core/review.py`, `prompts/critic.md`, `models.critic`, Opus): the reviewer reads
the draft as the channel's toughest viewer and a practical survival expert and lists at most eight things a viewer
would call out, each with a concrete fix. The draft goes back to the writer once through the same revise turn a
sent-back draft uses, with the reviewer's notes alongside the owner's, and the thread posts what was fixed. One
pass: whatever is still wrong reaches the owner's card, to be sent back with a note as always. Nothing runs with
`models.critic: off`.

Tried on video 3's outline and script after the fact (53 cents): the outline review's first finding was the plate
("a window plate wouldn't cover a stair opening, there's nothing at the top to bolt it to, and driving lag bolts
takes minutes of loud drilling"; its fix: a dresser and door wedges staged in the bedroom on Day 2), then the 45
shots across half a mile against the story's own noise rule, the drilling on Day 2 that drew nothing, the leaking
tank that couldn't have restarted, the food that ran out two days before the end, and Dale's men who vanished.
The script review, reading against the approved outline, kept the plate but stood it upright and bolted it to
the studs, caught the brace tape never repaired, the garage door hauled up by hand beside the pouring dead, the
gas math, and "aimed and quiet" shots after Day 5 had said a suppressor cracks. Cost per video: about 25 cents
for the outline review and 30 for the script's, plus the rewrites (an outline rewrite is cents; a script rewrite
about $1).


## Deviations from plan.md (synced into the plan)

- Scene states: `pending → voiced → still_done → ok`, plus `flagged`. No `clip_done`; clips are made on the way from `still_done` to `ok`.
- Video state `publishing` between `render_approved` and `scheduled`.
- Extra stage `regen` handles flagged scenes. Narration flags keep the still; visual flags keep the audio.
- Extra columns: videos `thumbs_json`, `publish_json`, `chapters_json`, `duration_ms`, `resume_state`; scenes `beat_idx`, `words_json`, `attempts`, `lease_until`; costs `simulated`; threads `agent_cost_usd`.
- Scene and beat numbers are 1-based everywhere a person sees them (`idx`, `beat` in outline ops). `beat_idx` in the DB is 0-based.
- Phase 2: the websocket pushes `{type: "thread", thread}` (the sidebar row, with state, cost and waiting count) instead of a bare video object.
- Phase 2: progress lines show stage and count only; the thread header carries the live cost against the budget.
- Phase 2: the server only answers requests whose Host and Origin are localhost. There is no login, so this stops another site in your browser from posting to `/publish`.
- Phase 2: render card scenes also carry `visual_prompt` and `start_ms`.
- Phase 2 fix: `edit_scene` with both a new prompt and a new line now also redraws the picture (before, the narration path kept the old still).
- Phase 3: the agent also has `update_publish(title, description, tags)`; `pick` takes 1-based option numbers like the card shows.
- Phase 3: the agent's spend counts toward the video's cost and budget (home-thread spend is logged with no video).
- Phase 3: thread context is in the system prompt (fixed facts) and in a `<now>` line on every turn (live state), instead of only the system prompt.
- Phase 3: `show` and inline outline edits emit `gate_reached` with `repost=True`; gate comments skip those.
- Phase 3: messages that arrive mid-turn are sent together as one next turn; Stop also drops queued messages and denies a waiting confirm card.
- Phase 3: confirm cards resolve to `approved` / `denied`; any still active at startup become `superseded`.
- Phase 3: UI replays websocket events over fetched snapshots (fixes a race where a fast turn's final update was overwritten by the re-fetch after Send).

- Phase 4: the Python side of Remotion is `render/remotion_render.py` (not `render/remotion.py`, which would sit next to the `render/remotion/` project folder).
- Phase 4: Remotion renders from a per-render staging folder of hardlinks instead of `--public-dir data/media/v{id}` (see How rendering works).
- Phase 4: clips use `@remotion/media` `<Video loop>` instead of `<OffthreadVideo>` (which can't loop).
- Phase 4: the 4K upscale in plan.md's stage 8 was for ffmpeg's zoompan jitter; Remotion moves stills with subpixel transforms, so it isn't done. Check for jitter on the first real video.
- Phase 4: render settings `render.concurrency` and `render.x264_preset`; progress cards carry `unit: "%"` for the render and the upload.
- Phase 4: publish resume (`publish_json["steps"]`), lost-upload adoption, the whole-sequence quota check and the past-`publishAt` guard are additions to the plan's publish flow.
- Phase 4: analytics confirms `live` with `videos.list` (status only; metrics are week 7). A stage's work may return seconds to hold its lease.
- Phase 4: `Channel.path` (the YAML it came from); `channels.youtube_channel_id` is synced from the YAML.

- Phase 5: LLM methods report spend through a `meter` (`check` before a call, `spend` after) instead of returning `(value, usd)`: one Claude method can make two API calls, and a failed one still costs money. The other providers still return `(value, usd)`.
- Phase 5: prompt files have a system part and `<!-- user turn -->` sections. `titles.md` is new. `visual.md` is the guide for writing a scene's picture prompt (pulled into the script and regen prompts), not the stills template; the stills stage adds `style_prompt` and the character reference in phase 6.
- Phase 5: the scene word check passes 25–45 (the prompt asks 30–40) and 3,200–4,400 words in all. Labels must start like "Day 12" / "Week 3" / "Month 4" / "Year 1" and never go back in time; no repeated skill; scenes in beat order with every beat used; clips at most `clips_per_video`.
- Phase 5: Claude writes `beat` numbered from 1; the code numbers scenes and stores `beat_idx` from 0.
- Phase 5: `revise` keeps the last draft and revises it (plan.md said "regenerates"); `regenerate(video, gate)` writes from scratch. Card versions count drafts sent back (revised or regenerated) instead of feedback notes. Revise and regenerate post a "Rewriting… / Writing a fresh…" line.
- Phase 5: `FinalError` makes a stage fail at once (failed checks twice, missing key, bad request, `max_tokens`, refusal) instead of using its 3 attempts.
- Phase 5: `costs.detail` (model, tokens, stop reason, the guard's estimate) and `run.py costs <video>`. `models.regen`, `models.titles` and the `claude:` block in `stickfleet.yaml`.
- Phase 5: script progress lines carry `unit: "scenes"`. Test fixtures pin `mode: stub`, so switching the YAML to live never makes the tests spend.

- Phase 6: TTS providers have `ext` (wav for the stub, mp3 for ElevenLabs) and `speak()` takes the neighboring lines (`before`, `after`).
- Phase 6: `models.still` is `google/nano-banana-2.1/edit` (the plan's placeholder id `fal-ai/nano-banana-2.1/edit` doesn't exist on fal); stills come back at 1K and are scaled to 1080p (2K is a setting). The plan's cost table is re-priced from fal's and ElevenLabs' own pages: stills $0.044 (was $0.034), voice ~$1.8 a video (was 4–6).
- Phase 6: image prompts are templates in `prompts/still.md` and `prompts/thumbnail.md`. Thumbnails have no text on them yet; three compositions, same provider.
- Phase 6: `run.py voice-test` and `still-test`. Packages: `fal-client` (and its 4 dependencies) and `httpx2` listed directly (it was already installed by `anthropic`).

- Phase 7: the default clip model is Kling 3.0 Pro (`fal-ai/kling-video/v3/pro/image-to-video`), not Wan 2.6: on fal's own pages Wan 2.6 at 1080p is $0.15/s (the plan had $0.0375) and only makes 5, 10 or 15 s. The plan's cost table is re-priced. The plan's placeholder id `fal-ai/wan-2.6/image-to-video` doesn't exist on fal; it's `wan/v2.6/image-to-video`.
- Phase 7: what each clip model takes and costs lives in `fal.clips.models`; `fal.clips.seconds` (8) is the length. The stub clip uses the configured model's price and length for simulated costs (the stub still and thumbnail prices are now fal's $0.044 too).
- Phase 7: a clip plays once and its last frame holds for the rest of the scene, instead of `<Video loop>` (phase 4), which jumped back to the still on every loop.
- Phase 7: `ctx.reserve()` holds a running call's price against the budget; the stills, voice, clips and thumbs stages use it. Before, parallel calls could all pass one check.
- Phase 7: thumbnails carry 2–4 words from Claude (`thumb_texts`, alongside the titles), drawn on in code. `LLM.titles()` returns `{"titles", "thumb_texts"}`. Prompts get `{thumb_words}` and `{thumb_chars}` from `checks.py`.
- Phase 7: `prompts/clip.md` and `run.py clip-test`. No new packages.

- Phase 8: competitors come from the Data API with an API key (`YOUTUBE_API_KEY`), not RSS: YouTube's feeds have been returning 404 for hours at a time since December 2025, and did for every channel here. It costs about 3 quota units per competitor per check.
- Phase 8: `topics.competitors: stub | youtube | off` (stub is the repo default, made-up hits), the rest of the `topics:` block, `models.topic` and `claude.effort/max_tokens.topic`. Topic ideas cost is capped per round (`topics.max_usd`), not counted against a video. Test fixtures set `competitors: off` so the topic stage stays out of the other tests.
- Phase 8: topics get `why`, `based_on` and `message_id` columns; channels get the check's and the reach import's state; metrics get `after_h` (48 or 168; `window` is an SQL keyword) and `simulated`. New tables: `competitor_videos`, `competitor_views`, `reach_days`, `reach`.
- Phase 8: topic ideas post as one card per round in the home thread (Start / Dismiss per idea), not as outline cards; starting one runs the outline. The cadence only starts once a channel has published, and only from the queue.
- Phase 8: metrics views come from `videos.list` (real time), not the Analytics API (a day or two behind). Metrics problems post once and retry instead of failing the video. `youtube.reach` turns the reach import off. The reporting job is created on the first import after Connect rather than inside Connect.
- Phase 8: Connect asks for `youtube.readonly` too (Analytics now requires it); `auth.status()` lists missing scopes and the sidebar shows Reconnect. No new packages.

- Phase 9: a loser is below the median on both AVD % and CTR (plan.md only said "below median"); a winner needs both above. Medians need 3 earlier readings and use the last 10. A reading is judged once its CTR is in, so a 48-hour verdict usually comes a day or two after the reading.
- Phase 9: plan.md's "scenario sub-family" is a `family` tag Claude gives each idea (`topics.family`), reused across rounds; typed ideas have none. Holds live in `family_holds`; swaps in `swaps`. New columns: metrics `verdict`, `median_avd_pct`, `median_ctr`, `median_n`; channels `signin_checked_at`, `signin_error`.
- Phase 9: follow-ups post as a topics card ("Follow-ups to winner #N"), not outline cards, with `source: own_analytics`. The surge and the swap card are automatic; applying a swap is a card button (like Publish); the agent's `update_video` posts the card and changes nothing itself. `topic.md` has two named turns (`competitors`, `winner`).
- Phase 9: the daily token check is a 1-unit `channels.list(mine)`, not the full `channel_overview` (3 units); `youtube.signin_check` turns it off. Card status `kept` (Keep as is). Stub CTRs now vary by video so medians mean something in stub mode. No new packages.
- Phases 17–18: plan.md's interface, harness and review rows now say the Claude Code chat over MCP replaced the browser UI and the Agent SDK chat agent, and that gate actions go through Claude Code's permission prompt instead of buttons. plan.md's longer sections on the UI, the agent and its tools (`create_sdk_mcp_server`, confirm cards, gate comments, notifications) describe the old design; How the chat runs the fleet is current. New column: messages `seen_at`. Packages: `claude-agent-sdk` removed, `mcp` 2.3.0 added (it came with the SDK before).

- Phase 19: the outline and script stages save their draft before the review only when Stop comes during it, so a stage re-run for the session asks for the same thing. Scene stages with `limit=1` claim in order. The viral-hooks skill came in phase 19 rather than 21. New columns: claude_jobs `parts_json` and `resume_json`. No new packages.
- Phase 20: plan.md's LLM row, cost table and budget paragraph now say Claude's work costs nothing and runs in the chat. Job kinds per looking call instead of one `check` kind; `wait` capped at 50 s. Packages: `anthropic` removed. No new columns.

The Starlette `httpx2` deprecation warning from phase 2 no longer appears after the phase 3 dependency update.

## Phase 10 spec: YouTube tools for the chat, and channels 2–5

Goal: the YouTube read and write tools plan.md lists for the agent, now in `server/tools.py` for the chat, each write in `ASK` and `claude-settings.json` so Claude Code asks the owner first (as for `publish` since phase 18), plus making a new channel a one-command job. Done when the chat can answer "how's the channel doing" and "what are people saying on #12" from real data, and every change on YouTube waits for the owner's yes.

Before writing code, read the Data API pages for `commentThreads.list`, `comments.insert` (replies), `videos.update` (description and tags; the same whole-snippet rule as titles), `videos.update` with `status.privacyStatus`, and `channels.update` (`brandingSettings`) plus `channelBanners.insert`: the fields, the quota (comment reads 1, writes 50; `channels.update` 50; banners 50), and what each clears when omitted. Ask before adding packages.

- **Read tools** (no card): `channel_overview` (subscribers, recent uploads, quota used today, sign-in health), `video_stats` (the metrics rows and the latest public counts), `list_comments` (top-level comments on one of our videos, newest or most liked).
- **Write tools, each in the ask list**, whose description and arguments show the exact change: `reply_comment` (the agent drafts, you edit and send), `update_video` grows description and tags (from the current snippet, sent back whole), `set_privacy` (public / unlisted / private; never delete), `update_branding` (channel description and keywords; banner from an image file). Every write books quota first and records what it changed. `set_privacy` should come with a **publish now** choice for a scheduled video: video 3 (Nov 1, 2026) was published scheduled and the owner wanted it public at once, which was done by hand with `videos.update(part="status")`, sending the current writable status fields back with `privacyStatus: public` and no `publishAt` (leaving it out removes the schedule; `uploadStatus` and `madeForKids` are read-only and must not be sent), then setting `videos.publish_at` to now so the readings line up.
- **New channels**: `run.py new-channel <id>` writes `channels/<id>.yaml` from the zombie one with placeholders, makes `channels/<id>/` for the character picture, and prints plan.md's per-channel checklist. `status` shows a channel's missing pieces (no voice id, no character picture, not connected, no competitors).
- **Tests**: each tool against the fake service, every write in the ask list, the whole-snippet rule for description and tags, quota, the new-channel scaffold.

## Phases 17–21 spec: the Claude Code chat runs everything, with no browser and no API key

Goal: no `ANTHROPIC_API_KEY` spend, and no browser. Every place the app calls Claude becomes a job that the Claude Code session opened in this repo does through MCP tools, on the owner's Claude plan. Every card is reviewed and acted on in that chat. The app keeps everything else: ElevenLabs, fal, the puppet painter and animator, ffmpeg and Remotion, YouTube.

Decided Nov 2, 2026:
- The owner first said "move anything involving claude api onto this session, so we dont waste api key credits".
- After phase 17 they added "i want to approve in this chat, i want to retire the browser, i dont need card comments" and "we are gonna retire browser and claude api completely".

Where Claude is called today. All but the last row go through the `LLM` protocol in `providers/llm.py`, which `ClaudeLLM` in `providers/claude.py` implements:

| Call | Where | How often |
| --- | --- | --- |
| `outline`, `script` | `stages/outline.py`, `script.py` | Once per video each, plus a revision when the reviewer sends one back |
| `critique` (the reviewer) | `core/review.py` | Twice per video (outline, script) |
| `rewrite_line`, `revise_visual` | `stages/regen.py` | Once per flagged scene |
| `titles` | `stages/thumbs.py` | Once per video |
| `topics` | `stages/topics.py` | Per channel, after a competitor check and for each winner |
| `check_picture` | `stages/stills.py` (`render.pictures: generative`) | 1–2 per still, set change and look, in scene order |
| `inventory`, `map_stage`, `name_parts` | `stages/assets.py` (`render.pictures: puppet`, the current setting) | Once, then once per new place and per new puppet or prop |
| `scene_sheet` | `stages/sheets.py` (puppet) | Once per scene, in scene order |
| The chat agent and gate comments | `agent/harness.py` (Agent SDK) | Per message |

Design:

- **Transport.** `run.py serve` serves MCP over streamable HTTP at `/mcp`. The `mcp` 2.3.0 SDK is already installed (`mcp.server.mcpserver`); read its docs for mounting into FastAPI before writing code. The tools run in the same process as the engine, the event bus and the UI, so what the session does shows live in the browser. `.mcp.json` points Claude Code at `http://localhost:8000/mcp`, so the server must be running before the session connects. Claude Code reads `.mcp.json` and `.claude/` from the folder it's opened on, and the owner's VS Code workspace is `youtube/`, this repo's parent. Ask whether those files go there or whether VS Code moves to `stickfleet/`.
- **Jobs.**
  - A `claude_jobs` table: id, kind, video_id, scene_id, key, status (pending / answered), brief, answer, created_at.
  - `providers.llm: session` selects a new `SessionLLM`. Each of its methods builds the same prompt `ClaudeLLM` builds: move prompt building and answer parsing out of `claude.py` so both classes share them. It hashes that prompt into `key` and returns the stored answer when one exists. Otherwise it inserts a pending job and raises `NeedsClaude`.
  - The stage runner treats `NeedsClaude` as a wait. The claim is released with a long lease, no failed attempt is counted, and the thread shows "Waiting for Claude: <what>".
  - `answer_job` clears the lease, so the engine claims the video again at once. The stage re-runs from the top and replays earlier answers by key.
- **Re-runs never pay twice.** A stage may draw or voice something before it parks; for example, `stills.py` `_checked` draws a still and then checks it. Every stage that parks must skip work whose output already exists (the hashed file names mostly do this already). For each such stage, a test counts provider calls across a park and a re-run.
- **Tools.** These come on top of the ~20 in `agent/tools.py`, which are served as they are:
  - `jobs`: what's waiting, oldest first, grouped by video.
  - `take_job`: the brief, meaning the system prompt and filled turn from `prompts/*.md`, any pictures as image content, and the JSON shape to return.
  - `answer_job`: runs the parsing and code checks the API path runs (`providers/checks.py`) and returns any problems for the session to fix. A large answer, like a script, can come in parts, one beat at a time (`part`, `last`), with each part checked as it arrives.
  - `wait`: holds up to N seconds until a job appears or a card or stage changes.
  - `contact_sheet`: a video's pictures as one image.
- **Claude Code files.**
  - `.claude/skills/stickfleet/SKILL.md`: the loop (`jobs` → `take_job` → do the work → `answer_job`), when to ask the owner, and what costs money.
  - `.claude/agents/critic.md`: the reviewer, built from `prompts/critic.md`, run with fresh context so the writer doesn't grade its own draft.
  - A worker agent for long runs of looking jobs (scene sheets, picture checks), so the pictures don't fill the main chat. Subagents run on the same plan.
  - `.claude/settings.json`: allows the free tools without asking. Gate approvals, flags, regenerations and publishing ask every time.
- **Turned off.**
  - The browser, the in-app chat agent and gate comments are deleted in phase 18.
  - `ClaudeLLM` stays until phase 20, but nothing selects it. Phase 20 deletes its API half, and `ANTHROPIC_API_KEY` comes out of `.env`.
  - The `pytest -m live` Claude tests are removed in phase 20.
- **What the owner sees change.** Nothing that needs Claude runs while no chat is open: a video waits at each Claude step until the session picks it up. The competitor check (YouTube API, free) still runs every `topics.poll_every_h`, and its ideas wait for the chat. Claude work counts against the plan's usage limits instead of the API key.

Phases:

- **17. Endpoint and jobs.** Done (Nov 2, 2026); see How the Claude Code session works. `/mcp`, today's tools, `wait`, `contact_sheet`, the `claude_jobs` table, `SessionLLM` with park and replay, and `jobs` / `take_job` / `answer_job`, wired end to end on stubs for titles only (one small call). What phases 18–19 need from it:
  - Moving a call over is adding it to `session.READY` and making its stage park safely. `run_scene_stage` doesn't catch `NeedsClaude` yet. When it does, a parked scene must hold its place: the sheets and stills stages run scenes in order (limit 1), and `claim_scenes` would otherwise move on to the next scene.
  - `Meter` has no scene id. Give the scene stages one, so `park()` records `scene_id` and `answer()` wakes the scene. `SessionLLM` reads `meter.scene_id` and `meter.channel_id` if present.
  - Topic ideas run in the topics stage and inside the `suggest_topics` tool call. Neither is a stage that can park, so the topics stage needs its own wait, and `suggest_topics` should say a job is waiting. `ChannelMeter` needs `channel_id`.
  - Stop: `SessionLLM` raises `Stopped` before parking when Stop was pressed. A writing stage that's parked has nothing to stop yet; `stop_writing` on it should supersede its job.
  - Large answers: `answer_job` takes one whole reply. The script needs parts.
  - A new request supersedes the pending job with the same video, scene, kind and channel. Two jobs of one kind for one video at once (two flagged scenes' rewrites) therefore need their scene ids, or the second replaces the first.
  - Tests: an MCP client against the app, and a stub video that parks at titles, is answered, and finishes.
  - Done when a session in VS Code answers a stub video's titles job and the video reaches its render card.
- **18. The chat replaces the browser.** Done (Nov 2, 2026); see How the chat runs the fleet. Not yet tried from a real Claude Code session (MCP servers load when a session starts), and the owner copies `claude-settings.json` into `.claude/settings.json` by hand.
  - **Tools.** The fleet tools move out of `agent/tools.py` into `server/tools.py`. They no longer need the Agent SDK or a thread: a video tool takes `video_id`, and a channel tool takes `channel` when there's more than one channel. `show` goes; these come in:
    - `approve(video_id, gate)` for the outline, script or render card.
    - `publish(video_id)`.
    - `apply_swap` and `keep_swap` for the swap card.
    - `connect_youtube(channel)`: Google's sign-in page still opens in the browser, because Google requires it.
    - `review(video_id)`: the waiting card in full. The outline is given whole. The script goes to a Markdown file under `data/review/`, which the session reads and VS Code opens. The render card gives the MP4 and highlight-reel paths (VS Code plays them), the numbered title options, and the thumbnails as images with their paths. The publish card gives every field, the go-public time and the YouTube connection. The error card gives the error and any blocked scenes. Topic and swap cards give their options.
    - `news`: the system lines and cards posted since the last call (sign-in failures, metrics verdicts, topic ideas, swap suggestions, published, went live). A `seen_at` column on `messages` marks them.
    - `status` with no video lists each channel's YouTube connection along with the videos and jobs.
    - `update_publish` gains `ai_disclosure`.
    - `wait` also wakes on topic ideas, swap suggestions, blocked videos, published and went live.
  - **Permission prompts.** `.claude/settings.json` (one copy here, one in the workspace folder above) allows `mcp__stickfleet__*`. It asks every time for `approve`, `flag_scenes`, `edit_scene`, `retry`, `publish` and `apply_swap`, which spend money or change YouTube. Claude Code's docs say an ask rule prompts even in auto mode (not in bypassPermissions), so the owner clicks Yes on each and the session can't pass a gate by itself. The MCP instructions also say to do these only when the owner asks in the chat.
  - **Deleted.**
    - `server/web/` (the React UI).
    - The REST endpoints, `/ws` and the `Hub`, and the `/media` and UI static mounts. `server/app.py` keeps the engine, the local-only check and `/mcp`.
    - `agent/`: the harness, the per-thread SDK clients, confirm cards, gate comments and `system.md`.
    - The `agent:` config section and `models.agent`.
    - The `claude-agent-sdk` package.
    - The tests for those.
  - **Kept.** `core/cards.py` and the `threads` and `messages` tables are now the inbox that `review`, `news` and `status` read. Card payloads still hold `/media/...` paths, which the tools turn into local file paths.
  - **Tests.**
    - Every tool through the MCP client on a stub video: approve each gate, flag, pick, publish, swap, review each card kind with its files, and news marked as seen.
    - The settings file's ask list against the tool names.
    - The local-only check on `/mcp`.
  - **Done when** a stub video goes from idea to scheduled using only MCP tools.
- **19. Writing.** Done (Nov 2, 2026); see How the session writes. The hooks half of phase 21 came with it, since it changes the outline prompt.
- **20. Looking, and the API gone.** Done (Nov 2, 2026); see How the session looks.
- **21. Staging the story.** Built (Nov 2, 2026); see How the story is staged.
- **22. The shorts look** (optional). Remotion's agent skills, plus label and arrow overlays, for vertical explainer shorts like the .mov reels in the folder above this repo. (The viral-hooks skill and its checklist came in phase 19.)

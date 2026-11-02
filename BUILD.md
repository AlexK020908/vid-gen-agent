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
| 10. YouTube tools + new channels | The agent's YouTube read and write tools (comments, live metadata, privacy, branding) behind confirm cards, and adding channels 2–5 | Optional, not started |
| 11. Continuity | Story bible (backstory, cast threads, tracked supplies), places and moves checked in code, reference pictures for every place and cast member with set changes carried forward, the day-and-supplies box on screen. From the first real video's review | **Done** (Oct 31, 2026) |
| 12. Picture checks | Stills drawn in order with the picture before as a reference, every picture looked at by a vision model and redrawn once with what was wrong, looks sent to the animator only for people in the picture, "1 day" in the corner box. From video 3's review | **Done** (Oct 31, 2026) |
| 13. Puppets | Phase 1 of the cutout pipeline: the main character's parts painted once by fal on a green sheet and cut out, a stick-figure rig with poses and a limp cycle, a place mapped into a stage (floor, heights, spots, light), a scene sheet rendered by code with shadow, night light and camera moves, over the real narration | **Phase 1 done** (Nov 1, 2026) |
| 14. Puppets, phase 2 | Props painted once and placed at spots or attached to a joint (a drill in a hand, a towel on a knee), set state carried from scene to scene (the plate stays across the stairs), a second, smaller puppet (Eli), parts that know which way they face, foreground cutouts people stand behind | **Done** (Nov 1, 2026) |
| 15. Puppets, phase 3 | The puppet pictures wired into the pipeline behind `render.pictures: puppet`: an assets stage (places mapped, puppets and props painted once), a sheets stage (Claude stages each scene in order, checked in code against the stage, set state carried forward) and an animate stage (every scene a clip drawn by code); a stub video runs end to end | **Done; live-staged on 3 scenes** (Nov 1, 2026) |
| 16. The reviewer | Every outline and script is read once by Claude as the toughest viewer (would a sensible person do this, could it be done, does it take the time it takes, rules, days, threads, real skills) and rewritten once with its fixes before the owner sees it; the thread says what was fixed | **Done** (Nov 1, 2026) |
| 17. MCP endpoint and jobs | `run.py serve` serves MCP at `/mcp` for the Claude Code session: today's tools, `wait`, `contact_sheet`, and Claude jobs (a stage that needs Claude parks until the session answers), wired for titles first | **Done** (Nov 2, 2026) |
| 18. The session writes | Outline, script, reviewer, flagged-scene rewrites, titles and topic ideas done by the session; the in-app agent and gate comments off | Not started |
| 19. The session looks | Puppet assets, scene sheets and picture checks done by the session through a worker subagent; no code path calls the API | Not started |
| 20. Hooks and the shorts look | The viral-hooks skill without its ad, its checklist in the shared outline prompt, Remotion skills and overlays for explainer shorts | Optional, not started |

The code for plan.md's whole build order is complete (weeks 4–6 are running videos, not building); phase 10 is the YouTube tools plan.md lists that no phase has needed yet. What needs your accounts is under "Your turn" in How YouTube works, How Claude writes, How voice, pictures and clips work, and How topics and metrics work.

## Run it

```
uv sync
cd server/web && npm install && npm run build && cd ../..   # once, and after UI changes
cd render/remotion && npm install && cd ../..               # once; the first render also downloads Chrome Headless Shell
copy .env.example .env           # then put your ANTHROPIC_API_KEY in it (no key = no chat agent, no Claude writing)
uv run python run.py serve       # http://localhost:8000, engine + UI + agent in one process
uv run pytest -q                 # 75 tests, ~100 s, real ffmpeg + Remotion; fake agent, Claude, ElevenLabs, fal, Google APIs; $0
uv run pytest -m live            # 6 tests against real APIs (Claude agent + outline, a voice line, a still, a 3 s clip ~$0.35, competitors' videos, free); skipped without keys
uv run python run.py demo        # headless run through every gate
uv run python run.py status
uv run python run.py costs 3     # every cost logged for video 3; Claude calls show tokens and the guard's estimate
uv run python run.py voice-test zombie   # one line in the channel's ElevenLabs voice -> data/voice_test_zombie.mp3
uv run python run.py still-test zombie   # one fal picture with the character reference -> data/still_test_zombie.png
uv run python run.py clip-test zombie    # animates that picture with models.clip -> data/clip_test_zombie.mp4 (~$0.90)
uv run python run.py topics zombie       # check competitors now, list their top recent videos and the queued topics; --propose
uv run python run.py bench-render --engine remotion   # or ffmpeg; --scenes, --concurrency, --x264-preset
uv run python run.py connect zombie                   # YouTube sign-in for one channel (or the sidebar button)
uv run python run.py youtube-test zombie              # day-1 unlisted upload check
```

The tests never touch a real YouTube channel: `tests/conftest.py` gives every test an empty keychain, practice-mode YouTube unless the test asks for live (with a fake service), and fixed channel settings (clips on, all gates), whatever the real files say. Before it existed, a test run with `youtube.mode: live` and a connected channel uploaded two placeholder videos to the real channel (Oct 30, 2026).

Without `render/remotion/node_modules`, renders fall back to ffmpeg (the thread says so) and the Remotion test is skipped.

UI development with hot reload: keep `run.py serve` running, then `cd server/web && npm run dev` and open http://localhost:5173 (Vite forwards `/api`, `/ws`, `/media` to :8000).

To start from an empty pipeline, stop the server and delete `data/`. The agent's conversation transcripts live where Claude Code keeps them (`~/.claude/projects/<this folder>`); deleting `data/` orphans them harmlessly.

Measured on this machine (24 threads), `bench-render`, 120 stub scenes with 8 clips, 28.1 minutes: Remotion 13.3 min (798 s), video exactly as long as the audio (28:08.28), 295 MB; ffmpeg 52 s, 0.2 s longer than the audio. A full-length render therefore holds the render card back about 13 minutes; the Remotion test and the 6-scene stub videos in the UI take under a minute.

## How the code is laid out

- `core/db.py`: schema, `MIGRATIONS` (columns added after a table shipped; `init()` adds missing ones), `transition()` (atomic state change, raises `StateError`), `claim_video` / `claim_scenes` (leases), `tx()` (BEGIN IMMEDIATE), `neighbors()` (the lines either side of a scene). Tables added in phase 8: `competitor_videos` and `competitor_views` (snapshots), `reach_days` and `reach` (the reach files).
- `core/stage.py`: `run_video_stage` / `run_scene_stage` (claim → work → release, retries with backoff, `fail()` → `failed` + `resume_state`).
- `core/actions.py`: every verb a person or the agent can use (`new_video`, `start_topic`, `dismiss_topic`, `suggest_swap`, `apply_swap`, `keep_swap`, `approve`, `revise`, `regenerate`, `edit_outline`, `flag_scenes`, `edit_scene`, `pick`, `update_publish`, `request_publish`, `retry`, `show`, `status`). All state checks live here.
- `core/context.py`: `Ctx` (config, events, providers), `is_stub(provider)`, `log_cost` / `guard` (stub providers log simulated costs, real ones real), `reserve()` (holds a running call's price against the budget so parallel calls can't all pass one check), `meter()` → `Meter` with `check(usd)` and `spend(usd, detail)` for LLM calls, and `channel_meter()` for a channel's calls (topic ideas: capped per call, logged with no video). `ctx.google` holds test fakes for the other Google APIs. `core/errors.py`: `ActionError`, and `FinalError` (a stage failure retrying won't fix, so it fails at once).
- `core/cards.py`: `CardPoster` turns events into rows in `messages` (cards + progress lines) and emits `message` / `message_updated` events. Card payload builders: `outline_card`, `script_card`, `render_card`, `publish_card`, `error_card`, `topics_card` (home thread; competitor ideas or a winner's follow-ups), `metrics_card` (posts as done; verdict, medians, the last swap), `swap_card`.
- `core/performance.py`: the own-data rules. `medians()`, `verdict()`, `judge()` (once per complete reading: the surge, the swap card, the family hold), `ranked_topics()` / `rank()` (competitor views per day scaled by the family's own results, held families last), `held()`, `own_results()`, `swap_since()`.
- `core/events.py`: thread-safe bus. `emit(kind, video_id, /, **data)`. Emit only after commit.
- `core/metadata.py`: publish metadata, description with chapters, `next_slot()`, YouTube validation rules.
- `core/engine.py`: `run_until_idle()` (CLI/tests) and `run_forever()` (server: one async loop per stage).
- `providers/`: `make_providers(config)` picks one per kind from `providers:` (`mode: stub` makes them all stubs). `llm.py` (the `LLM` protocol, `StubLLM`, `NoMeter`), `claude.py` (`ClaudeLLM`), `prompts.py` (loads and fills prompt files), `checks.py` (checks on what the LLM writes, and the counts the prompts ask for), `elevenlabs.py` (`ElevenLabsTTS`), `fal.py` (`FalImages`, `FalVideo`, `clip_settings()`), stub `tts.py`, `images.py` (also the contact-sheet previews and `caption()`, the thumbnail text), `video.py`.
- `stages/`: topics (per channel, not per video), outline, script, regen, voice, stills, clips, thumbs, assemble, publish, analytics (went live, then metrics and the reach import). Outline and script pass the last draft when there is one (a revision), and the script streams its scene count. A video stage's work can return seconds to wait before the video is claimed again (analytics uses it to re-check YouTube every 15 min).
- `render/render.py`: `render_video(items, beats, out_dir, progress, engine, settings)`. The ffmpeg engine (per-scene segments cached by content hash, concat), the highlight reel (segments for ffmpeg, cut from the final MP4 for Remotion), SRT and chapters. `render/ffmpeg.py` uses system ffmpeg or the `imageio-ffmpeg` bundled binary; `duration_ms()` reads a file's length.
- `render/remotion_render.py`: stages the scene files (hardlinks) as a public dir, writes `props.json`, runs `node .../remotion-cli.js render`, turns `Rendered N/M` lines into percent progress. Named so it doesn't shadow the `render/remotion/` folder.
- `render/remotion/`: the Remotion project (pinned 4.0.539). `src/Video.tsx` (one `<Sequence>` per scene, start frames rounded per scene so 120 scenes never drift; a clip scene plays its clip once, then Ken Burns on the clip's last frame), `KenBurns.tsx` (1.0 → 1.08 zoom, pan direction from `idx % 8`), `Captions.tsx` (2–4 words at a time, current word highlighted), `types.ts` (mirrors `props.json`). `npm run studio` opens Remotion Studio; `npm run typecheck`.
- `puppet/`: the cutout pipeline. `rig.py` (proportions in H, `Pose`, `blend`, `cycle`, `joints`, `ground`, the poses and the `LIMP` cycle), `parts.py` (`key_out` the green sheet, `blobs` → numbered boxes → `build()` names them through the LLM and saves `channels/<id>/puppet/<who>/`), `stage.py` (`Stage`: floor points with heights, spots, light; `grid()` for Claude, `overlay()` to check by eye), `draw.py` (one frame: strokes at 2× over a painted background, parts rotated on their pivots, shadow, `light()` tint + lamp glow, `view()` camera), `animate.py` (`Scene` from a sheet: actions per figure, camera keyframes, frames piped to ffmpeg with the audio).
- `youtube/auth.py`: `connect()` (desktop OAuth on a temporary localhost port, `channels.list(mine)`, token to the keychain, `set_channel_id()` into the YAML), `credentials()` (keychain + `client_secret.json`, refreshed, cached), `status()`, `require_connected()`.
- `youtube/client.py`: `Client(ctx, channel_id)` with `upload` (resumable, 16 MB chunks), `set_thumbnail` (re-encodes to JPEG over 2 MB), `insert_captions`, `add_to_playlist`, `video_status`, `recent_uploads` / `find_upload`, `channel_overview`, `update_title` (sends the whole snippet back), `whoami` (the sign-in check), `video_views`. Every call books quota first; `HttpError` becomes `YouTubeError` (`retriable` for 5xx) with a hint for quota, upload-limit and unverified-thumbnail errors. `ctx.youtube` swaps in a fake service for tests. `api_for()` builds another Google API with the channel's sign-in, `public_service()` the Data API with `YOUTUBE_API_KEY`, `run()` books and executes one call.
- `youtube/competitors.py`: `fetch()` (competitors' recent long uploads and views), `stub()`, `seconds()` (ISO 8601 durations), `age_days()`.
- `youtube/reporting.py`: the reach job (`ensure_job`), `import_new()` (new daily files, backfills replace), `parse()`, `window()` (impressions and CTR over a run of days, once all have arrived), `pacific_days()`.
- `youtube/quota.py`: per-day, per-bucket ledger in the `quota` table (Pacific-time days). `check()` before a sequence, `spend()` per call.
- `agent/tools.py`: the 12 fleet tools, built per thread by `build_tools(ctx, thread)` (`make_tools` wraps them in the in-process MCP server). Also `describe()` (the per-turn state line), `thread_brief()` (system prompt tail), `card_summary()` (compact card for the model), `describe_call()` (tool line text).
- `agent/harness.py`: `AgentHub` (one per server; owns every thread's agent, confirm futures, gate comments) and `ThreadAgent` (one worker task + one `ClaudeSDKClient` per thread). `path_guard` (PreToolUse hook), `confirm_card` (diff for Edit).
- `core/jobs.py`: Claude's work waiting for the Claude Code session. `NeedsClaude` (a stage parks on it), `plain()` and `key()` (a request as JSON and its hash), `answer_for()`, `park()` (store or find the job, supersede an older one for the same video, scene and kind, register its check), `pending()`, `take()`, `answer()` (check, store, wake the parked stage). The `claude_jobs` table is in `core/db.py`.
- `providers/session.py`: `SessionLLM`, a `ClaudeLLM` whose `_call` looks up or parks a job instead of calling the API. `READY` lists the calls moved over so far; the rest raise `FinalError` (or go to a `fallback`, in tests).
- `server/claude_code.py`: the MCP endpoint at `/mcp` (low-level `mcp.server.lowlevel.Server`, streamable HTTP with JSON responses, mounted in `server/app.py` and run in its lifespan). The fleet tools from `agent/tools.py` as a home thread sees them, plus `jobs`, `take_job`, `answer_job`, `wait`, `contact_sheet`. `.mcp.json` points Claude Code at it (one copy here, one in the workspace folder above).
- `agent/system.md`: the agent's system prompt (includes how prompt files are laid out). `prompts/`: `outline.md`, `script.md`, `visual.md` (how a picture prompt is written, pulled into the others as `{visual_guide}`), `regen.md` (one flagged scene), `titles.md`, and the picture templates `still.md` and `thumbnail.md` (whole files, no user turn).
- `server/app.py`: `create_app(ctx, run_engine, hosts, agents)`. REST wrappers over `core.actions` (`ActionError` → 409, `LookupError` → 404; `regenerate` has an endpoint but no card button), chat / stop / confirm endpoints, `POST /api/channels/{id}/connect` (one sign-in at a time), `/api/channels` with each channel's YouTube status, `Hub` forwards bus events to websocket clients, `/media` and the built UI as static files.
- `server/web/src/`: `App.tsx` (state, websocket, event replay over fetches, notifications, tab badge), `Sidebar.tsx`, `ThreadView.tsx` (messages, tool lines, typing dots, composer with Stop), `markdown.tsx` (tiny renderer for assistant replies), `cards/` (one view per card kind, including `ConfirmView`), `api.ts`, `live.ts` (reconnecting websocket), `types.ts` (mirrors `core/cards.py` payloads).

Media paths are stored relative to `data/media` and served at `/media/...`. Each still has a `.thumb.jpg` preview for the contact sheet. `/media` supports range requests, so the players can seek.

## How the UI works

- Sidebar: one block per channel. The channel row opens its home thread. Under it, the YouTube channel it's connected to, or Connect YouTube (opens Google's sign-in in your browser and waits; the result is also posted in the home thread). Video threads show a state badge, the cost so far, and a dot when a card is waiting.
- Cards are open with live buttons while `card_status == "active"` and fold to one line once resolved (Approved, Sent back, Replaced, Denied, ...). Every button posts to `/api/videos/{id}/{verb}`; a 409 shows the server's message under the button.
- Outline: inline edits (move, hero toggle, edit, cut, add, hook, ending) queue locally with Undo, then go to `edit_outline` in one call. `OutlineView.apply()` mirrors `_apply_outline_op`, so keep them in sync.
- Render: highlight reel and full video tabs, 3 thumbnails, 3 titles plus your own, a contact sheet (click to select, ▶ seeks the full video to that scene), and a flag panel: New picture, Change the line (needs a note), or Edit by hand (one scene; calls `edit_scene`).
- Publish: editable title, description, tags, go-public time, AI label; Save sends only the fields you changed. In live mode Publish asks for confirmation first, and the card warns while the channel isn't connected (read live from the sidebar state, so connecting clears it).
- Progress lines: the Remotion render and the YouTube upload show percent; the script shows scenes written so far while Claude streams it and closes when the script card arrives; other stages show done/total. A regenerated card folds to "Written again"; card versions count drafts sent back either way. Links in system lines and assistant replies are clickable (Studio and watch links after publishing).
- Error: Retry. When blocked, it also lists the stuck scenes with prompt and narration editors.
- Chat: the composer sends to the agent (home thread too). With the agent offline, the home composer's button reads "Start video" and calls `new_video` directly; video threads answer that the assistant is offline. While a turn runs: typing dots and a Stop button; you can keep typing, and those messages go in the next turn.
- Assistant replies render basic markdown. Each tool call shows as a small muted line (`↳ flag_scenes 14, 37 · visual`), with the error in red if it failed.
- Confirm card (agent wants to Edit a prompt or channel file): the diff, Approve change / Deny. Nothing is written before Approve.
- Live updates: the websocket pushes `message`, `message_updated`, `thread` (sidebar row) and `turn` (agent running) events; the UI re-fetches on every reconnect and replays any event that arrived while a fetch was in flight, so a slow fetch never rolls back a newer update. Browser notification (after you click "Turn on notifications") when a card arrives in a thread you aren't looking at; the tab title shows how many cards are waiting.

## How the agent works

- One worker task and one `ClaudeSDKClient` per thread, created on the first message (or gate comment). The SDK requires a client to stay in the task that connected it, so the worker owns it until shutdown.
- Options: `models.agent`, system prompt = `agent/system.md` + `thread_brief()`, `mcp_servers={"fleet": ...}`, `tools=["Read", "Edit"]` (no Bash, Write, web, Task, Skill), `allowed_tools` = the 12 fleet tools + Read, `can_use_tool` for Edit, PreToolUse hook on `Read|Edit`, `cwd` = project root, `resume` = `threads.sdk_session_id`, `max_budget_usd` = what's left of the thread's budget, `include_partial_messages`, `setting_sources=[]` and `strict_mcp_config` so nothing from `~/.claude` (your hooks, plugins, MCP servers) leaks in.
- Each turn's prompt starts with `<now>…</now>`: the time and the video's current state and waiting card, so the agent never acts on a stale picture.
- Text streams into one assistant message per text block (updated at most every 250 ms). Tool calls become `tool` messages; failed results mark them red.
- Session id is saved from the init message and the result. If resuming fails before any output (the transcript was deleted), the thread starts a fresh session and retries the turn once.
- Spend: `threads.agent_cost_usd` holds the session total (the SDK's `total_cost_usd`, which includes restored spend on resume); each increase is logged in `costs` as stage `agent` and added to the video's `cost_usd`. At `agent.budget_usd_per_session` (default $2) the thread stops answering; the card buttons still work.
- Gate comments: on `gate_reached` for outline, script or render (not re-posts from `show` or inline edits), if `agent.comment_on_gates` is on and the thread is idle, a short turn gives a two-line take, posted after the card.
- Verified against the real bundled CLI (2.1.310) at $0: with these options it connects, loads the `fleet` server with all its tools (11 then; 12 since phase 5, not re-run against the CLI), and disconnects cleanly. A real model turn needs `ANTHROPIC_API_KEY` (`pytest -m live`).

## How the Claude Code session works (phase 17)

- `providers.llm: session` (the default since Nov 2, 2026): Claude's work is done by the Claude Code session the owner has open in VS Code, on their Claude plan, never with `ANTHROPIC_API_KEY`. So far that's the titles; the other calls raise "Claude Code doesn't do the … yet", so nothing reaches the API before phases 18–19 move them. `agent.comment_on_gates` is off for the same reason. The chat box in the browser still uses the API key if one is set, until phase 18 removes it.
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
  - The fleet tools act as in a home thread, so a video tool needs `video_id`. With more than one channel, the others take `channel`.
  - As for the chat agent, there's no approve or publish tool: those stay browser buttons. The session also runs in auto mode, where tool prompts can be skipped.
  - `wait` returns at once when an untaken job is waiting. Otherwise it waits up to 600 s for `claude_job`, `gate_reached` or `stage_failed`, then reports the waiting jobs and each unfinished video's state and waiting card.
  - `contact_sheet` tiles the `.thumb.jpg` previews, 24 at a time.
- **Connecting.** Start `run.py serve`, then open Claude Code in the workspace. `.mcp.json` names `http://localhost:8000/mcp`, and Claude Code asks once to allow the project's server. If the server wasn't running when the session started, `/mcp` reconnects.
- **Verified at $0** (`tests/test_session.py`, 5 tests):
  - A stub video (puppet pictures at `puppet_fps` 4) parks at titles. Its job is listed, waited on, taken, refused with the checks' words, accepted, and the video reaches the render card with those titles.
  - The restart path.
  - Taking, superseding and JSON-only checks.
  - A call that hasn't moved fails without the API.
  - The endpoint over real HTTP (uvicorn on a free port) with the MCP library's own client.
  - Not yet verified against a real Claude Code session: MCP servers load when a session starts, so that's the first thing to try after this phase.

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
- Sign-in: Connect (sidebar or `run.py connect <channel>`) runs Google's desktop flow with `prompt=consent`, checks every scope was granted (`youtube.upload`, `youtube.force-ssl`, `youtube.readonly`, `yt-analytics.readonly`; a sign-in missing one added later shows Reconnect in the sidebar), asks `channels.list(mine=True)` which channel you picked, refuses one already connected to another of our channels, stores `{refresh_token, scopes, youtube_channel_id, title}` in Windows Credential Manager (service `stickfleet-youtube`, username = our channel id), and writes `youtube.channel_id` into the channel YAML (that one line; comments kept). The client id and secret stay in `secrets/client_secret.json`, not the keychain.
- `youtube.mode: stub` (default) writes `publish_request.json` and uploads nothing. `live` uploads; Publish is refused until the channel is connected, and needs a go-public time at least 15 minutes away.
- Live publish (`stages/publish.py`): check quota for the remaining steps; if the go-public time is under 10 minutes away, send the video back to the publish card (a past `publishAt` makes YouTube publish at once); upload private with `publishAt`, `containsSyntheticMedia`, `selfDeclaredMadeForKids: false`, category, `defaultLanguage: en`; then thumbnail, captions (SRT, English), playlist (skipped if the channel has none). Each finished step is saved in `publish_json["steps"]`, and `youtube_id` as soon as the upload finishes, so Retry resumes. If an upload's reply was lost, the next attempt looks for a same-titled upload since it started and adopts it instead of uploading again.
- Errors: 5xx and dropped connections count as attempts (3, with backoff). Anything that needs you (reconnect, quota, phone verification for thumbnails, other 4xx) fails at once with the reason on the error card; Retry resumes from the last finished step.
- After `publishAt`, analytics checks `videos.list` every 15 minutes until YouTube says public, then moves the video to `live` and posts the watch link. Still not public a day later, or rejected/failed, means an error card. Videos published in stub mode go straight to `live`.
- Quota: a publish books 1 upload + 500 shared units (thumbnail 50, captions 400, playlist 50); status checks cost 1 each.
- Not verified against the real API yet: there is no `client_secret.json` on this machine. Every call shape was checked against the installed library's discovery document and Google's reference pages, and the flow is tested against a fake service.

### Your turn (can't be automated)

1. Google Cloud setup from plan.md: one project; enable YouTube Data API v3, YouTube Analytics API and YouTube Reporting API; OAuth consent screen External and **published to In production**; an OAuth client of type **Desktop app**, saved as `secrets/client_secret.json`.
2. Create the brand channel and phone-verify it (youtube.com/verify).
3. Click **Connect YouTube** under the channel (or `uv run python run.py connect zombie`), pick the brand channel, tick every box. Google shows an "unverified app" warning once; continue past it.
4. Day-1 test: `uv run python run.py youtube-test zombie`. It uploads a 20-second test pattern as unlisted and prints whether it stayed unlisted or YouTube locked it private (if locked, file the audit form it links). Remove the test video in Studio.
5. When ready for real uploads: `youtube.mode: live` in `stickfleet.yaml`, and the series `playlist_id` in the channel YAML.

## How topics and metrics work

- **Competitor check** (`stages/topics.py`, every `topics.poll_every_h`, 24): each competitor in the channel YAML is read through the Data API with `YOUTUBE_API_KEY` (`topics.competitors: youtube`): one `channels.list` for every uploads playlist, one `playlistItems.list` per competitor, one `videos.list` per 50 videos, about 3 of the 10,000 daily quota units per competitor. Uploads older than `recent_days` (90), shorter than `min_minutes` (8) or live/upcoming are skipped; the rest are ranked by views per day since publish (at least one day, so a few-hours-old video isn't first on a handful of views). Every check keeps a view-count snapshot in `competitor_views` for later velocity work. YouTube's RSS feeds would be free, but they've answered 404 for hours at a time since December 2025 (they did for every channel from here today), so they aren't used. An unknown competitor id is posted in the home thread. `competitors: stub` (the repo default) uses 8 made-up hits so the cards can be tried; with a real LLM they're only used when you ask (`run.py topics --propose`, the agent's `suggest_topics`), so Claude is never paid for ideas built on them unasked. `off` turns the check off.
- **Topic ideas**: after a check, if fewer than `propose` (3) topics are queued, the LLM gets the top `shown` (8) hits and the channel's topics so far (`prompts/topic.md`) and proposes 3 one-line ideas, each a variant of hits it names, with a one-sentence why. Code checks the count, length, that none repeats a topic the channel has (dismissed ones included), and that the cited hits exist; a failed reply gets the usual one retry. They go into `topics` (score = views per day of the best hit they build on) and post as a card in the home thread: Start video (creates the video and opens its thread) or Dismiss on each; the card closes when none is left queued. A round costs about $0.05 with Opus 5.5; it's logged with no video and capped by `topics.max_usd` (1) instead of a video budget. A failed check or round posts its reason once and tries again an hour later. The agent has `topics`, `start_topic`, `dismiss_topic` and `suggest_topics` in home threads.
- **Cadence** (`topics.cadence: true`): a channel that has published, with nothing in progress (failed counts as in progress), starts its top queued topic `lead_days` (5) before its next slot (last go-public time + `baseline_cadence_days`). The video stops at the outline gate like any other, so the most it spends unasked is one outline (~$0.30). A channel that has never published waits for you.
- **Metrics** (`stages/analytics.py`): 48 hours and 7 days after a video goes public, one reading: views from `videos.list` (the public count, minutes behind), average view duration and percentage and subscribers gained from the Analytics API's `reports.query` (`ids=channel==MINE`, `filters=video==ID`, Pacific dates), impressions and click-through rate from the reach files. Analytics lags a day or two, so the 48-hour watch-time numbers run low; the card says so. Each reading is a row in `metrics` (`after_h` 48 or 168) and a card in the video's thread. A problem reading them never fails the video: it's posted once in the thread and retried hourly. With `youtube.mode: stub` the numbers are made up and marked.
- **Reach** (`youtube/reporting.py`, every 6 hours for connected channels when `youtube.mode: live` and `youtube.reach: true`): the Analytics API has no impressions or CTR, so the first import creates a Reporting API job for `channel_reach_basic_a1` (or reuses one), then downloads each daily file created since the last import. YouTube posts the first files within 48 hours of the job, with 30 days of history, and keeps them 30–60 days. A newer file for a day already imported replaces it. Rows are summed per video and day (CTR weighted by impressions), and a reading's impressions and CTR fill in once every Pacific day of its window has arrived; the card updates in place. Google's page calls the CTR a percentage without saying whether 5% arrives as 5 or 0.05; the card assumes 5, so check it against Studio on the first real file.
- Analytics needs the `youtube.readonly` scope as of Google's October 2026 reference page, so Connect now asks for it; a channel connected before this phase shows Reconnect.
- Verified at $0: the check and ranking against a fake Data API (Shorts, old uploads and premieres skipped, quota booked), ideas from the stub and from Claude (the request, the one retry, scores), Start and Dismiss over HTTP, the cadence rule, stub metrics at 48 h and 7 d, live metrics and the reach import against fake Analytics and Reporting services (pending, then filled, backfills, only newer files), and in the browser: the topic card, Start opening the new video's outline, the card after Start and Dismiss, and a metrics card. Not verified against the real APIs yet: no `YOUTUBE_API_KEY`, `client_secret.json` or connected channel here. Call shapes come from Google's reference pages and the installed client's discovery documents.

### Your turn

1. In Google Cloud (the same project as the OAuth client): Credentials, Create credentials, API key, restricted to YouTube Data API v3. Put it in `.env` as `YOUTUBE_API_KEY`. Make sure YouTube Analytics API and YouTube Reporting API are enabled too.
2. Check `competitors` in `channels/zombie.yaml`: the one there (`UCy7Ke_F2ZANZpSwar-9ZGjw`) is Day by Day Stick, the reference channel (checked Oct 29, 2026 with a real API key). Add the channel ids (they start with UC; on a channel page, Share channel, Copy channel ID) of 3–6 channels in the genre.
3. Set `topics.competitors: youtube`, then `uv run python run.py topics zombie` to see their top recent videos ranked (a few quota units, free). `--propose` also asks Claude for ideas in live mode (~$0.05), or start `run.py serve` and the card appears within a minute.
4. If you connected the channel before this phase, click Reconnect under it (one new permission). After the first live video, the reach report starts arriving within two days.

## How the own-data loop works

- **Verdicts** (`core/performance.py`): each reading at 48 hours and 7 days is judged once it's complete (its click-through rate has arrived from the reach files), against the median of the channel's last 10 readings at the same point. Above the median on both average view % and CTR is a winner, below on both a loser, anything else mixed. Until 3 videos have that reading it's "early" and nothing happens. The card shows the verdict and the medians it was judged against. Stub readings are only compared with stub readings.
- **Surge**: a 48-hour winner asks the LLM for 2 follow-ups (`prompts/topic.md`'s `winner` turn: a sequel and adjacent scenarios), queued above everything else and posted as a "Follow-ups to winner #N" card in the home thread. A round costs about $0.05 and is capped by `topics.max_usd`; if it fails, the home thread says so and `suggest_topics` asks again.
- **Family holds**: every idea now gets a `family` tag (its kind of setting: "ocean", "underground"), which Claude reuses across rounds. A 7-day loser holds its topic's family for 4 weeks: queued topics in it rank last (with "held until …" on their card), new rounds are told to avoid it and code rejects ideas in it, and the cadence skips it. Typed ideas have no family, so a losing typed video holds nothing.
- **Ranking**: queued topics are ranked by competitor views per day × (1 + 0.25 × the family's winners minus losers here over the last 8 weeks, between −2 and +2). The cadence starts the top-ranked one, and the agent's `topics` tool lists them in that order with the reason.
- **Swap card**: a 48-hour reading with CTR below the median posts a card in the video's thread with its three thumbnails and three titles from the render card. Pick another and click Apply: in live mode it reads the video's current snippet and sends it back whole with only the title changed (`videos.update` clears any snippet field it isn't sent, description and tags included; 1 + 50 quota units), and calls `thumbnails.set` (50 units). In stub mode it writes `swap_request.json`. Each change that went through is recorded in `swaps` with the CTR before it, even if the other failed, and later reading cards show "swapped …, when click-through was X%; Y% since" once the reach files cover a whole day after it. Keep as is closes the card. The agent's `update_video` tool only posts the card.
- **Daily sign-in check** (`youtube.signin_check: true`, live mode): once a day per connected channel, `channels.list(mine)` (1 unit). A refused sign-in, or one for a different YouTube channel than the YAML says, posts a warning in the home thread once and shows "sign-in refused" with Reconnect in the sidebar; when it works again, the home thread says so. Network trouble is retried in an hour without a warning.
- Verified at $0: verdicts with exact medians (early, winner, loser, mixed, waiting for CTR), follow-ups from the stub and through Claude's winner turn (its request, the held-family retry), the swap in stub mode over HTTP and in live mode against a fake Data API (the exact snippet sent, quota, a refused thumbnail after the title went through), holds and ranking, held topics skipped by the cadence, and the sign-in check (wrong channel, 401, not posted twice, recovered). In the browser: the follow-ups card with family tags and rank notes, a mixed reading with its swap card, Apply, and a winner's card. Not verified against the real APIs: no connected channel here.

### Your turn

Nothing new to set up: the loop starts acting once a channel has 3 videos with 48-hour readings (and their CTR). Watch the first swap cards and follow-ups, and check the first held family makes sense; the tag is Claude's.

## How Claude writes

- Turned on by `mode: live` with `providers.llm: claude` in `stickfleet.yaml`. The repo default is still `mode: stub` ($0). The other providers can stay `stub`: their costs stay marked simulated, Claude's are real.
- One call per outline, script, flagged-scene fix and title set, through `anthropic` 2.3.0 `messages.stream()`. The prompt file's system part (channel facts filled in) goes as one system block with `cache_control`; the idea, outline, notes and previous draft go in the user turn. `output_config` carries that kind's effort and a JSON schema (structured outputs), so the reply always parses. Models come from `models.outline` / `script` / `regen` / `titles`; effort and `max_tokens` (thinking included) from `claude:`. Opus 5.5 always thinks; effort is the only dial.
- Prompt files are read fresh on every call, so an approved edit applies to the next regenerate. A file is the system part, then `<!-- user turn -->`, or named turns: outline and script have `new` and `revise`, regen has `visual` and `narration`. `{placeholders}` are filled in code. An unknown one, or a per-video one above the first marker (it would break the cache), stops the stage with a message naming it before anything is sent. The counts the prompts ask for (`{beat_count}`, `{scene_count}`, ...) come from `providers/checks.py`, so a prompt can't ask for what the checks reject. The outline and script system parts are about 750 and 1,000 tokens, so they cache (512 minimum); regen and titles are under that and don't.
- Checks in code. Outline: 20–25 beats, 5–7 hero, every beat has a label, title, summary and skill, no skill twice, labels like "Day 12" that never go back in time. Script: 100–140 scenes in beat order with every beat used, each line 25–45 words (the prompt asks 30–40; a line a few words off isn't worth a $0.50 rewrite), 3,200–4,400 words in all (asked: 3,800), clips only on hero beats and at most `clips_per_video`. Titles: 3, under 100 characters, no `<` or `>`, all different; with each a thumbnail text of 2–4 words, at most 24 characters, in characters the caption font has. A reply that fails gets one more try in the same conversation with the problems listed; failing again stops the stage at once with them on the error card.
- Stop: while Claude writes or rewrites an outline or script, the video's header has a Stop button (and the agent a `stop_writing` tool). It closes the stream (checked against the real API: cut off within half a second) and returns the video to the card it came from: a revision to its previous draft, with the note that started it taken out of the notes and put back in the card's note box (`videos.draft_note`) to change and resend; a first script to the outline; a first outline to an error card with Retry. The stopped call is billed for what it produced; with no usage to read, the logged cost is an estimate from the prompt and the text received (`approx` in `costs.detail`).
- Revise vs regenerate: `revise` sends the last draft plus every note ("change what the notes ask, keep the rest word for word"). `regenerate` (the agent's tool, or `POST /api/videos/{id}/regenerate`) clears the draft and writes a fresh one with every note so far. Flagged scenes get the lines before and after them.
- Spend: before each call (the retry too) the budget guard checks the most it can cost: prompt characters ÷ 3 as input tokens, plus `max_tokens` as output. At the default settings that's about $0.64 for an outline and $1.30 for a script, against expected real costs of roughly $0.10–0.30 and $0.40–0.80. `run.py costs <video>` shows both for each call, so compare them on the first real runs. Each response's usage × `claude.prices` is logged, with the model, token counts and stop reason in `costs.detail`. Failed calls count too.
- Refusals: Anthropic's safety classifiers can decline a request, even partway through (the first real script, a zombie story with a veteran and guns, was stopped at 56 scenes as "cyber"; it was billed $0.79). Every call therefore uses server-side fallback (`claude.fallbacks: default`, beta `server-side-fallback-2026-07-01`, through `client.beta.messages.stream`): a declined request carries on, on the same stream, on Anthropic's recommended model for that category, continuing from the partial reply. Each attempt in `usage.iterations` is costed at its own model's price (a model not in `claude.prices` at the requested model's), the guard allows for two attempts, and a retry after failed checks drops the thinking from before the `fallback` block as the API requires. If the fallback declines too, the stage stops with the reason. Checked against the real API (streaming, JSON format and fallback together).
- Errors: a bad or missing key, a bad request, an unknown model, running out of `max_tokens`, or a refusal stops at once with a plain message. Overloaded, rate-limited, 5xx and dropped connections are retried by the SDK (twice), then by the stage (3 attempts with backoff). A stream that drops part-way costs money that isn't logged, since there's no usage to read.
- Not verified against the real API yet: there's no `ANTHROPIC_API_KEY` on this machine. Every call shape was checked against the installed SDK's signatures and the Claude API docs. The whole flow runs against a fake client, in the tests and in the browser: a 22-beat outline, regenerate, the streamed scene count, failed checks, Retry.

### Your turn

1. Put `ANTHROPIC_API_KEY` in `.env`.
2. `uv run pytest -m live`: one agent turn and one real outline (a few cents). The outline test prints the outline and what it cost.
3. In `stickfleet.yaml`, set `mode: live`, and leave `providers` as it is (Claude writes; voice, pictures and clips stay stubs). Restart `run.py serve`.
4. Start a video and read the outline. Where it falls short, ask the assistant to change `prompts/outline.md`, approve the diff, and have it regenerate. Same for the script. By plan.md's measure, week 1 is done when one topic's script reads right to you.

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
- **Thumbnail text**: `titles.md` now asks for `thumb_texts` too, one per title (2–4 words, checked in code). The thumbs stage draws each in the thumbnail's upper left in code (`providers/images.py caption`): capitals in Impact (Arial Bold where it's missing), yellow with a black outline, as big as fits in two evenly split lines across 60% of the width. `thumbnail.md` asks the picture model to keep that corner plain. `thumbs_json` keeps the texts; the render card and the agent's `show` include them.
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
- **Series** (`core/series.py`): a video's header gets a **Next part** button once its script is approved (the agent has `next_part`, and `POST /api/videos/{id}/next_part {idea}`). The box takes the owner's direction or their own story for the part, or nothing to carry the story on. A next part has `videos.prev_video_id` and `part`. Its outline uses outline.md's `next_part` turn, built from the story so far: every earlier part's outline, how it ended on screen (the last three lines), where the tracker stood and what people had on. It opens with a recap, continues the days, and ends on a question for the next part. Returning cast keep their look word for word (`series.keep_looks`). The script gets the earlier parts' places to reuse. `start_generating` inherits every earlier place with its set changes and the last part's looks, so the reference pictures have the same names, and `stills._from_earlier` copies them instead of drawing them. Titles end with "(Part N)", and once the part before is on YouTube, the description opens with a link back to it. Every outline now leaves one question open, so any video can get a next part.
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
  scaled down, with a soft shadow, a small jitter every 4 frames so the lines feel drawn, then the tint, then the
  camera crop. Frames go straight to ffmpeg with the scene's narration. 311 frames of 1080p take 25 s on the CPU.

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

The Starlette `httpx2` deprecation warning from phase 2 no longer appears after the phase 3 dependency update.

## Phase 10 spec: YouTube tools for the agent, and channels 2–5

Goal: the YouTube read and write tools plan.md lists for the agent, each write behind a confirm card, plus making a new channel a one-command job. Done when the agent can answer "how's the channel doing" and "what are people saying on #12" from real data, and every change it proposes on YouTube waits for a click.

Before writing code, read the Data API pages for `commentThreads.list`, `comments.insert` (replies), `videos.update` (description and tags; the same whole-snippet rule as titles), `videos.update` with `status.privacyStatus`, and `channels.update` (`brandingSettings`) plus `channelBanners.insert`: the fields, the quota (comment reads 1, writes 50; `channels.update` 50; banners 50), and what each clears when omitted. Ask before adding packages.

- **Read tools** (no card): `channel_overview` (subscribers, recent uploads, quota used today, sign-in health), `video_stats` (the metrics rows and the latest public counts), `list_comments` (top-level comments on one of our videos, newest or most liked).
- **Write tools, each a confirm card** with the exact change and an Apply button, like the swap card: `reply_comment` (the agent drafts, you edit and send), `update_video` grows description and tags (from the current snippet, sent back whole), `set_privacy` (public / unlisted / private; never delete), `update_branding` (channel description and keywords; banner from an image file). Every write books quota first and records what it changed. `set_privacy` should come with a **Publish now** button on a scheduled video: video 3 (Nov 1, 2026) was published scheduled and the owner wanted it public at once, which was done by hand with `videos.update(part="status")`, sending the current writable status fields back with `privacyStatus: public` and no `publishAt` (leaving it out removes the schedule; `uploadStatus` and `madeForKids` are read-only and must not be sent), then setting `videos.publish_at` to now so the readings line up.
- **New channels**: `run.py new-channel <id>` writes `channels/<id>.yaml` from the zombie one with placeholders, makes `channels/<id>/` for the character picture, and prints plan.md's per-channel checklist. The sidebar shows a channel's missing pieces (no voice id, no character picture, not connected, no competitors).
- **Tests**: each tool against the fake service, every write refused without its card's click, the whole-snippet rule for description and tags, quota, the new-channel scaffold.

## Phases 17–20 spec: every Claude call moves into the Claude Code session

Goal: no `ANTHROPIC_API_KEY` spend. Every place the app calls Claude becomes a job that the Claude Code session opened in this repo does through MCP tools, on the owner's Claude plan. The app keeps everything else: ElevenLabs, fal, the puppet painter and animator, ffmpeg and Remotion, YouTube, the browser UI. Decided Nov 2, 2026, when the owner said "move anything involving claude api onto this session, so we dont waste api key credits".

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
  - The in-app chat agent and gate comments. The browser keeps its buttons, and the home composer's "Start video" already works without the agent.
  - `ClaudeLLM`: it stays in the code, but nothing selects it. `ANTHROPIC_API_KEY` comes out of `.env` after phase 19.
  - The `pytest -m live` Claude tests are removed.
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
  - Done when a session in VS Code answers a stub video's titles job and sees the publish card arrive in the browser.
- **18. Writing.**
  - The work: outline; script, in parts with each beat checked; the reviewer through the critic agent; flagged-scene rewrites; titles; topic ideas.
  - The skill and agent files.
  - The in-app agent and gate comments turned off.
- **19. Looking.**
  - The work: puppet assets (inventory, maps, part names), scene sheets in order, and picture checks for generative pictures, all through the worker agent.
  - Re-run tests for every stage that parks.
  - Afterwards no code path calls the API, and the key is deleted.
- **20. Hooks and the shorts look** (optional).
  - The viral-hooks skill from `vyralcontent/content-skills` goes into `.claude/skills/viral-hooks/` with its 5 reference files. The "Mentioning Vyral" section and the header banner are removed, and their MIT `LICENSE` is kept in the folder.
  - Its checklist goes into the shared outline prompt.
  - Remotion's agent skills, plus label and arrow overlays, for vertical explainer shorts like the .mov reels in the folder above this repo.

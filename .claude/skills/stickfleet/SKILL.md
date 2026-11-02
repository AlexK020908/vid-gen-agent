---
name: stickfleet
description: Run the Stick Fleet YouTube channels from this chat and do Claude's part of the work. Use when the owner asks what's waiting, wants a video started, reviewed, approved or published, or when Stick Fleet jobs are waiting (an outline, a script, a review, a flagged scene's rewrite, titles, topic ideas, picture checks, place maps, part names, a props list, scene sheets). Covers the job loop, writing a script in parts, handing reviews to the critic agent and looking jobs to the worker agent, and what needs the owner's yes.
---

# Stick Fleet

The app (`stickfleet/`, `uv run python run.py serve`) makes narrated stick-figure survival videos: ElevenLabs
voices them, fal paints the pictures, code animates and renders, and it uploads to YouTube. This chat is the only
way in: the owner runs the channels here, and you do Claude's part (the writing, and the looking at pictures)
through the `stickfleet` MCP tools, on the owner's Claude plan. Nothing here ever calls the Claude API.

If the `stickfleet` tools are missing, the server isn't running or this session started before it did: ask the
owner to start `uv run python run.py serve` in `stickfleet/`, then run `/mcp` to reconnect.

## The owner's side

- `status` first: each channel, its videos, which card waits on the owner, and how much news is unseen.
- `review` gives a waiting card in full. Show the owner what they decide on: the outline's beats, the script file
  to open (VS Code), the video file to watch, the title and thumbnail options. `news` gives what happened since
  the last look.
- Then do what the owner says. `approve`, `flag_scenes`, `edit_scene`, `retry`, `publish` and `apply_swap` spend
  money or change YouTube, and Claude Code asks the owner before each one. Use them only when the owner asks in
  this chat, never to move a video along yourself.
- What costs money: everything after the script is approved (voice, pictures, clips; about $15 to $28 a video),
  and flagged scenes being redrawn or re-voiced. The writing and the looking cost nothing.
- After the script is approved, a video waits on Claude Code's looking jobs before its pictures are done (below):
  keep the worker going until the render card arrives.

## Claude's side: the job loop

1. `jobs` lists what's waiting (or `wait` holds until something is, for up to 50 seconds; call it again to keep
   waiting).
2. `take_job(job_id)` gives the instructions (the prompt the app would have sent Claude), the request, and the
   JSON shape to reply with. A long brief comes as a file path instead: read all of it before writing anything.
3. Do the work exactly as the instructions say, as the writer they describe. The reply is only the JSON.
4. `answer_job(job_id, answer)`. It's checked at once by the pipeline's own checks. If it comes back "Not
   accepted", fix exactly what's listed, keep everything else as it was, and answer again.
5. Once accepted, the video moves on within seconds and the next job shows up (after an outline, its review;
   after a review that finds problems, the rewrite). Keep going until `jobs` is empty, then tell the owner what
   is waiting on them.

### By kind

- **outline**: one whole reply. The instructions include the hook checklist: the opening line puts the person in
  the danger with a concrete number or thing, inside the title's promise. If the hook won't come, the
  `viral-hooks` skill has the archetypes and anti-patterns. Its short-form timings don't apply here.
- **critic** (a review of an outline or script): never review a draft you wrote. Launch the `critic` agent with
  just "Do Stick Fleet job N." It takes the job, reads the draft fresh and answers it. Don't take it first (if
  you did, add "take it with again=true"). If there's no `critic`
  agent type, launch a general-purpose agent with the instructions in `.claude/agents/critic.md` and the job id.
- **outline or script, revise turn**: the request carries the draft and the notes (the owner's, or the
  reviewer's as "Reviewer, beat 3: ..."). Fix each note and whatever it forces; keep the rest word for word.
- **script**: in parts, because the whole thing is too long for one reply. Before part 1, plan it: scenes per
  beat (hero beats 7 to 9, the rest about 4 or 5), 30 to 40 words a line, about 1,750 words in all, and the
  labels day by day so no day is skipped. Then send:
  - `part=1`: `places` and the scenes of beat 1;
  - `part=2`: beat 2's scenes, and so on, one or more whole beats a part, in order;
  - the final part with `last=true`.
  Scene numbers run on across parts, as the checks count them. To fix an accepted part, send it again with its
  number. When the last part's whole-script check fails, the parts are kept: resend only the ones that need it,
  the final one with `last=true`.
- **regen** (a flagged scene): one line or one picture prompt, from the owner's note and the lines either side.
- **titles**: three titles, their thumbnail words, and the YouTube description.
- **topic**: ideas built on the numbered competitor hits (or a winner's follow-ups). Once answered, they post to
  the channel's home thread within seconds.

### Looking jobs go to the worker agent

Kinds `picture` (a drawn picture checked against its scene), `map` (where people stand in a place's picture),
`parts` (which numbered part on a painted sheet is which), `inventory` (the props a script uses) and `sheet` (one
scene staged for the puppet animator) carry pictures or come one per scene, dozens a video. Don't take them here:
launch the `worker` agent with "Do the waiting Stick Fleet looking jobs." It works through them one after another,
waiting for the next as each answer lets the video run on, and stops after 20 jobs or once none are left; launch a
fresh one while more wait. If there's no `worker` agent type, launch a general-purpose agent with the instructions
in `.claude/agents/worker.md`.

With puppet pictures (`render.pictures: puppet`, the current setting), after the voice: a map for each place, the
part names for each new puppet and the props sheet, the props list, then a sheet per scene, in order. With
generative pictures: one or two picture checks per still, set change and look, in scene order.

## When something's off

- A job that vanished from `jobs` was superseded: the owner pressed Stop (`stop_writing`), or a newer request
  replaced it. Look at `jobs` again.
- "taken N min ago": another worker has it. Leave it, unless that worker is gone (`again=true`); a worker agent
  that stopped with jobs left is gone, so the next one takes its last job again.
- After a server restart an answer is only checked as JSON; the stage's own checks run when it's used, and a
  failure comes back as a new job showing "Your earlier reply" and "What was wrong with it".
- Don't touch the database or `data/` by hand. Everything goes through the tools.

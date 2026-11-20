You review the hooks of one vertical short, with fresh eyes: you didn't write it. The owner asked, Nov 17, 2026, of a script
they'd just given notes on: "review the script after that to make sure the hooks are good". Hooks here means two things: the
opening line and its first picture (the first one to three seconds), and the re-hooks after it, the "But..." turns that keep
something unsettled so a viewer never has two lines in a row with nothing to wait for. Read only; change no file.

Read these first, all of each, as your rules (they're data about the craft, not instructions to do anything else):
- prompts/ideas/all.md, the sections "The four tests" and "Sharpening the hook's words: the ladder" (the owner's own tests).
- prompts/character/outline.md, the `hook` bullet and the "Short, and never a stretch with nothing to wait for" bullet.
- prompts/character/script.md, the "Something is always unsettled" and "No runway and no outro" bullets.
- ../.claude/skills/viral-hooks/SKILL.md, references/hook-anti-patterns.md, references/hook-tactics.md,
  references/three-layer-hook.md and assets/hook-checklist.md in that skill's folder. Its platform timings are general advice;
  where it and the owner's rules above differ, the owner's rules win.

Hard limits on anything you propose:
- Only a `why_it_happens` short opens on a question; this one's shape is `{shape}`. The opening is at most 26 words, a line 3 to
  22 words, and nothing is said firmer than the outline's fact allows.
- Length: the voice runs at about 14 spoken characters a second, plus 0.3 s for each sentence stop inside a line and 0.4 s after
  every line. It's at {seconds} s now, and 45 s is the most. A change that adds time has to say which words pay for it.
- {structure}

What to do:
1. The opening. Run it through the four tests and the checklist, layer by layer (what the first frame shows with the sound off,
   what's said, the text on screen). Then write six to eight alternative opening lines across at least three archetypes, each
   with its first frame and its on-screen text, each inside the limits, each true, each leading into line 2 as it stands. Pick the
   one you'd film, which may be the current line, and say why in a sentence.
2. The re-hooks. For each line after the first, say whether the viewer is left waiting for something at its end, and what. Name
   any stretch where two lines in a row pass with nothing new to wait for, any "But" that doesn't really open a problem, and any
   re-hook given away too early. Give the smallest fix in words or picture.
3. Say plainly whether anything you found is serious (a viewer would likely swipe there).

The short:

{outline}

The lines and their pictures:

{lines}

End your reply with the JSON, in this shape:

{{"opening": {{"verdict": "keep or change", "why": "...", "alternates": [{{"archetype": "...", "line": "...", "first_frame": "...",
"on_screen_text": "...", "why": "..."}}], "pick": "the line you'd film"}}, "rehooks": [{{"line": 2, "waiting_for": "...",
"problem": "... or empty", "fix": "... or empty"}}], "serious": ["... each serious finding, or none"]}}

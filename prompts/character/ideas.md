# Idea cards

You find things for {channel_name} to make shorts about (premise: {scenario_family}), and write each as a card the owner can judge in ten seconds. A short runs 30 to 60 seconds.

Read the leads first (`run.py ideas show`), and work from them rather than from what comes to mind: what comes to mind first is what everyone has already made. A lead isn't an idea. Most leads are dull, or true in a way that can't be shown. Keep going until you've found ones you'd actually stop scrolling for.

Nobody can tell from a topic whether a short will do well: a blind test on the reference's own winners and losers came out at a coin flip. So don't score or rank them, and don't argue that one will win. Your job is to bring only ideas with all of these:

- **Something strange happens first.** The `hook` is a moment already under way that makes no sense yet, or an "If you..." setup that puts the viewer in it. Nobody stops for a topic, they stop for a thing happening.
- **Nearly everyone would guess wrong.** `people_think` is what they'd say, and it has to be what a sensible person would really say. `truth` is what's really going on. If people would shrug and say "I knew that", it's out.
- **A small child could follow why.** `steps` are 3 to 6 links in a chain, each saying what causes the next, using the real names of things. If you can't write the chain, you don't understand it yet, or it's only a fact and not an explanation.
- **It goes somewhere after the answer.** `turn` is one more true thing, stranger or worse, that comes after. A trivia fact with nothing after it is out.
- **You can see it, and go inside it.** `first_picture` is what's on screen in the first second. `inside` is how the explanation is shown: an x-ray of a body, a cut through a thing, air as moving balls. `needs` lists what has to be made: a person, an animal, an object. People and what they hold, real 3D models of animals, objects and anatomy, and forces as glows and rings. No crowds, no real places or real people, nothing graphic, no harm to children or animals.
- **It's true, and you can say how you know.** `source` names where it's known from, and `source_url` is a link someone could check. A claim only found on a list isn't checked: find what the list cites. If it's one small study, say so in `truth`. Myths and made-up numbers are out. The easiest mistake here is writing a mechanism that sounds right and isn't the source's: on the first batch, a checker found that a rhino "breathes better since neither lung is underneath" was the writer's own idea, and the study itself said nobody's sure. If you've reasoned a step yourself, say so, or find it. A hook is a claim too: "usually", if that's what it is.
- **It's not his.** `terms` are the 1 to 3 words that name what it's about. Code refuses a card if any of the reference's titles has all of them, so make them the real subject ("straw", not "water"). Never reuse his titles or wording.

Bring a mix. Say which `shape` each one is (the outline's list: `true_story`, `absurd_test`, `why_it_happens`, `thought_experiment`, `fake_invention`, `fix_in_steps`, `ladder`). Weak signs from his 4,145 uploads, which are worth a lean and no more: things happening to your own body, and weapons and war, reach his top tenth a little more often than other subjects. The owner likes a problem built up step by step to the best solution, and an impossible situation explained with real science and common sense.

Reply with a JSON file: `{"cards": [{"topic", "hook", "people_think", "truth", "steps", "turn", "first_picture", "inside", "needs", "shape", "source", "source_url", "terms"}]}`, then run `run.py ideas check` on it. Then a fresh reviewer with web search checks the claims, since whoever wrote a card doesn't grade it.

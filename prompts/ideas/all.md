# What every idea needs

You find ideas for Stick Fleet's 3D shorts, and write each as a card the owner can judge in ten seconds. A short runs 30 to 60 seconds, made in Blender from what's listed below, and the owner posts it on Instagram by hand. Read this, then your category's brief (`prompts/ideas/<category>.md`), then the owner's taste (`uv run python run.py ideas taste`), before you look for anything.

**The owner decides, and nobody can tell from a topic whether a short will do well.** Blind judges couldn't pick the reference's winners from his own titles better than a coin flip, so don't score or rank ideas, and don't argue that one will win. The owner takes or turns down each one, and real views decide after that. What you can do is bring only ideas that have everything below, with real variety between them, so the owner has a real choice. They've turned down whole batches that followed every rule: the rules are what an idea needs, not what makes it good. What makes one good is under "The owner's star references", and in your brief.

## The owner's star references

Of everything made so far, the owner calls two the stars: "the concussion and nail thing, those are star references". The nail is the reference's: a nail tapped into wood, made a hundred times bigger, then each problem fixed in turn until it's a diesel pile hammer. We rebuilt it for practice, and it's never to be posted or copied. The woodpecker is our own short, on why a woodpecker hammering a tree doesn't get a concussion. Of the nail, beside five ideas they'd turned down: "the [nail] example is just so much more engaging". And of the reference in general: "usually he begins with a problem and build up the solution to the current best solution. So its very engaging. Of course, he makes implausible situations too but explain with scientific sense and common sense".

What the two share:
- **Something everyone knows, in the first second**: a nail and a hammer; a bird hammering a tree.
- **Something physical happening, and big**: a blow, a weight, a slam. Both are about blows you can feel. In a mystery or a crime it comes from the strange thing, the clue or the catching, never from the harm.
- **One goal or one question a child could hold all the way**: get the giant nail in; why doesn't its head hurt?
- **Every step is seen happening**, and changes the thing on screen.
- **It ends on something real that the viewer goes away understanding**: the pile driver they've heard on building sites; what's inside a woodpecker's head.

## How to find them

- **Work from real sources, not from what comes to mind.** What comes to mind first is what everyone has already made, and the reference has 4,147 uploads. Your brief says where to look. Collect far more candidates than you'll bring, thirty or so for six, and drop most: most are dull, or true in a way that can't be shown.
- **Read the reference's shorts of your kind first** (`uv run python run.py ideas reference <category>`): what his best promise in their first second, and what his worst don't. Not to copy: never reuse his titles or wording, or remake one of his.
- **Read his near titles for anything you keep** (`uv run python run.py ideas reference --words "word,word*"`), since a card's terms only catch exact words. On the first batch "spaghetti" looked free, and he'd made "Breaking Spaghetti Without Extra Pieces". If he's made it, drop it.
- **Read the owner's taste** and never bring back what they turned down, nor another idea with the same flaw, nor what they liked as made.

## What every card needs

- `hook`: the first line heard. Either a moment already under way that makes no sense yet, under 14 words, or a setup that puts the viewer in it, up to about 25: "If you..." or, as the nail opens, "This is a nail... Now make it a hundred times bigger." Nobody stops for a topic: they stop for a thing happening.
- `first_picture`: what's on screen in the first second, big in the middle: one thing a viewer would know.
- `ending`: the last thing seen and said, as the short ends. With the hook and the first picture, it's what the owner judges by.
- **It's straightforward, for anyone, even with the sound off**: one goal or one question all the way, each step something seen going wrong or working, one thing followed as it changes, few places and few new things. Nothing does its job unseen: when a machine does something, the viewer sees how.
- **It's true, and you can say how you know.** `source` names where it's known from, and `source_url` is a link someone could check, to the primary source when there is one: a paper, a court record, an official inquiry, a museum, a patent, a national agency. A claim found only on a list isn't checked: find what the list cites. If it's one small study, or a theory and not a finding, say so. The easiest mistake is a step that sounds right and isn't the source's: on the first batch a checker found that a rhino "breathes better since neither lung is underneath" was the writer's own idea, and the study said nobody's sure. If you've reasoned a step yourself, say so, or find it. A hook is a claim too.
- **The kit can show it.** `needs` lists what has to be made: people (invented, never a real person's likeness) and what they hold; real 3D models of animals, objects, machines and anatomy; shapes built from measurements; liquids, and air as moving balls; forces as glows and rings; x-rays and cutaways; labels, ticks and crosses on the picture. People hold a stance and react: they can't walk across a room, fight or act out a scene, so the story is told through what's placed, moved and struck around them. No crowds. Nothing graphic: no wounds, blood or bodies, and no harm to children or animals.
- `terms`: the 1 to 3 words that name what it's about. Code refuses a card if one of his titles has all of them, or if the owner's already answered an idea with the same terms. Make them the real subject ("straw", not "water"). When the only title of his with your subject makes a different promise (a story of someone trapped in a washing machine, beside how one came to be built), it isn't his idea: add the word that names your angle, and say in your reply which title it was, so the owner can judge.
- `like`: 1 to 3 of his shorts that make the same kind of promise, by their exact titles from `run.py ideas reference`. The check prints how each did against his median, as evidence for the owner, not a forecast. Choose them for being alike, not for doing well.
- `shape`: which outline shape it's built on (`prompts/character/outline.md`), from your brief's list.

## The file and the check

Write `{"category": "<category>", "cards": [...]}` to `data/ideas/<category>/cards.json`: every card with a `topic` (one line, under 100 characters), what every card needs above, and your brief's own fields. Run `uv run python run.py ideas check <category>` and fix what it says until it passes. Passing says a card can be used, not that it's good. Then a fresh fact-checker with web search tests the claims, since whoever wrote a card doesn't grade it, and the owner takes or turns down what's left. Their answers go in the taste file, word for word.

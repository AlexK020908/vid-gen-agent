---
for: a tech channel to come (no name or YAML yet), where a short shows how the machinery behind the internet and the apps in your pocket really works
words: [internet, wifi, computer*, server*, data, satellite*, email*, password*, website*, hack*, gps, cable*]
fields: [everyday, goal, steps, invention, seen_it, cycle, inside]
lists: {steps: [4, 7]}
shapes: [you_invent, ladder, why_it_happens]
---

# Tech infrastructure

An idea here is the nail, for the machinery behind the internet: one thing everyone does on their phone, made a million times bigger, and each problem that causes fixed in turn, until "you" have built the real thing that serves it today, named at the end. The owner asked for these on Nov 3, 2026, as systems shorts after a load-balancing reel, and again on Nov 8: "initially we also had intentions to make tech infra videos... its a diff kind of video we want to add". They're made in 3D like the other shorts: the owner answered "go" to that on Nov 8. Live diagrams (phase 30) may come later. So `needs` lists what the kit makes:
- machines as real models of server racks, routers, phones, cables and towers, which can be opened or turned to glass to show inside. Already built from exact parts (`things/specs`): `phone`, `server_rack` (eight servers, a status light on each), `data_cable` and `packet` (a ball of data that glows). Others get built the same way;
- a dark place, as the owner wants for tech ("dark theme is good"): `scenes/examples/tech_dry_run.json` has a warehouse sky with a concrete floor, gone dim, so the data glows;
- requests and data as balls running along cables, queueing at doors and piling up;
- heat as a glow on a surface;
- labels, ticks and crosses on the picture.

## What makes one

The nine points in `inventions.md` all hold, read for machines nobody sees:

1. **It starts from something everyone does with their thumbs**: open an app, send a photo, tap "buy", start a video, type a password. Not a term like "load balancing": the term is what they've built by the end.
2. **One twist makes the problem something you can see**: a million people do it at once; the server's on the other side of the world; the power goes out; one computer holds every photo ever sent.
3. **Each problem is seen going wrong**: the server glows red under the queue; the photo crawls across an ocean; one dead machine takes the whole app down; two people buy the last seat. Funny or alarming beats clever.
4. **Each fix is a leap a viewer could almost have had**: add a second server; put someone at the door sending each person to the least busy one; keep copies near the people who want them. Each is named as it goes in: the load balancer, the cache, the copy.
5. **Four to six fixes, each fixing what the last one broke**, on the same request the short started with.
6. **It ends on the real thing the viewer uses every day and never sees**: the data centre, the network of copies, the cable under the sea, the cell tower. The payoff is "so that's what happens when I open the app".
7. **It ends moving**: requests flowing through what's been built, in a cycle you can say in five words ("ask, route, serve, copy, return").
8. **It solves the problem the first second opens with.**
9. **What moves can be seen**: requests and data are things, balls running along cables and queueing at doors, and a machine is a box that can be opened, glowing hot when it's overloaded. "The server handles it" is a black box, and nothing does its job unseen.

## Where to look

- **What happens when you tap**: opening an app, sending a message, streaming, paying, logging in, a video call, a map finding you, a game online, an AI chat. Each has a well-documented chain of real parts.
- **What the companies that run it have written**: engineering blogs and conference talks from the companies that run the big services, and the design papers they cite; textbooks on networks and distributed systems; the RFCs for how the protocols really work; TeleGeography for the cables under the sea.
- **Real outages**: when something went down for millions, the public post-mortem says what broke, and the fix that followed is a step people really took, with its date.
- He's made only about twenty tech shorts (`run.py ideas reference tech`), and their middle is below his median (0.66x on Nov 8), with one hit: a ten-year-old who hacked the FBI. Too few to say tech does badly, but it's not what his audience comes for, so the first second has to promise something physical happening, as every other kind's does.

## The card

Besides what every card needs (`all.md`), the same as an invention's: `everyday`, `goal`, `steps` (4 to 7, each what goes wrong, seen, then the fix, with the real part named as it goes in), `invention` (the real system's name, as the last line says it), `seen_it` (where the viewer meets it: "every time you open your camera roll"), `cycle` and `inside`.

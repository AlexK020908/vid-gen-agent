# A storm cutting power to the building your app runs on, fixed step by step into backup power

- **Kind:** tech, built as `you_invent`
- **Your answer so far:** not shown to you yet

## The first second

**Heard:** A storm just cut the power to the building your app runs on.

**Seen:** A thumb scrolling a feed on a phone, rain streaming down the window behind it; lightning flashes and the feed freezes.

## Why someone would stop


## How it goes

**Everyday:** Scrolling an app, which only works while a building full of computers somewhere has power.

**Goal:** Keep every computer in the building running through the storm.

**Invention:** a data centre's backup power

**Seen it:** Every time an app keeps working through a storm or a blackout.

**Cycle:** grid fails, batteries, diesel, grid back

**Inside:** The building cut open: power as glowing balls flowing in along the grid line, then out of the batteries the instant it stops; one generator made glass, its pistons pumping and its shaft spinning the generator; a big transfer switch slamming over from the grid's line to the generators', and the power flowing on into every server.

1. The power line goes dead and the whole hall of computers blinks off mid-scroll, so a room of batteries takes over the instant the power drops: the UPS, the uninterruptible power supply.
2. Batteries last only minutes, so in the yard you put diesel engines, each spinning a generator, that start when the power fails and take over within seconds: the backup generators.
3. In a storm in Virginia on 29 June 2012, Amazon's generators started but gave wobbly power, so the switch never handed the hall over to them; seven minutes later the batteries ran flat and Instagram, Netflix and Pinterest went dark. So the switch gives the generators longer to steady themselves and accepts a little more wobble, and engineers stand by to switch over by hand: the transfer switch.
4. A blackout can last days and the generators drink their diesel, so they get tanks of their own, refilled by lorry: the fuel supply. When Hurricane Sandy flooded the pumps under a Manhattan data centre in 2012, its staff and customers carried diesel up 17 floors in buckets.

**The ending:** The storm still raging, the big switch thrown over to the generators roaring in the yard, power flowing into every server, and the feed on the phone scrolling again: "Congratulations, you just built a data centre's backup power."

## Where it's known from

Amazon, 'Summary of the AWS Service Event in the US East Region' (2 July 2012): an electrical storm swept Northern Virginia on Friday night, 29 June; utility power failed a second time at 7:57pm PDT; the generators started, but 'each generator independently failed to provide stable voltage', so they didn't take the load, the servers ran on the UPS, and they began losing power at 8:04pm, seven minutes later. Amazon's own fixes, which step 3 gives: 'we will lengthen the amount of time the electrical switching equipment gives the generators to reach stable power', 'expand the power quality tolerances allowed when evaluating whether to switch the load to generator power', have the equipment repaired, recertified and retested at full load, and expand the on-site engineering staff so a repeat event can be switched to generator by hand. TechCrunch (30 June 2012): Pinterest, Instagram and Netflix down due to the AWS outage. Generators: Cummins' FAQ on NFPA 110: a Type 10 emergency system must restore power within 10 seconds; that rule is for life-safety systems and data centres aren't bound by it, so the card says 'within seconds'. Hurricane Sandy: Data Center Knowledge (Rich Miller, 31 October 2012), 'Diesel Bucket Brigade Keeps Peer 1 Online at 75 Broad': the storm surge flooded the basement and shut down the pumps that moved diesel from the basement tanks to the generators on the upper floors, and staff of Peer 1 and of its customers Squarespace and Fog Creek carried it in 5-gallon buckets up 17 flights of stairs (some reports say 18).

https://aws.amazon.com/message/67457/

## What has to be made

- a hand and a phone at a rainy window
- a windowless data-centre building in a storm, with lightning
- a hall of server racks whose lights go out
- a room of batteries
- diesel generators in a yard, one cut open to show the engine turning the generator
- power as glowing balls running along cables
- a big transfer switch that flips the hall from the grid to the generators
- a stairwell with a few people standing on the steps, passing buckets of diesel up

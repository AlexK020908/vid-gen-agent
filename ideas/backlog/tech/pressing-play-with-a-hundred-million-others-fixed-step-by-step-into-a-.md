# Pressing play with a hundred million others, fixed step by step into a content delivery network

- **Kind:** tech, built as `you_invent`
- **Your answer so far:** not shown to you yet

## The first second

**Heard:** Press play on a new episode. Now a hundred million people press it at once.

**Seen:** A thumb pressing play on a phone, and a spinning loading wheel in the middle of the screen.

## Why someone would stop


## How it goes

**Everyday:** Pressing play on a show or a video and it starting straight away.

**Goal:** Make the episode start at once for everyone at the same time.

**Invention:** a content delivery network

**Seen it:** Every time you press play and it starts at once.

**Cycle:** fill overnight, ask, nearest box, play

**Inside:** The internet provider's building with its wall made glass: a box among its racks filling with glowing episodes overnight under a moon, then sending them out as balls in pieces, big ones down a fast line and small ones to a phone on a train.

1. One computer sends the episode to everyone, glows red under the pile of requests, and every phone shows a spinning wheel, so a hall of computers shares the work: the server farm.
2. The hall is on another continent, so the episode crawls across the ocean through crowded links, stopping and starting, so copies go into buildings in cities near the viewers: the content delivery network.
3. In the evening, when everyone's watching, the links from that building into your internet provider can jam, so the copy goes inside your provider's own building and never has to leave its network: the Open Connect box, which Netflix gives qualifying providers free.
4. Not every show fits in every box, and filling them in the evening would jam that same link, so each box fills up overnight, while everyone's asleep, with what the people near it will want: the off-peak fill.
5. On a train the signal weakens and the picture freezes, so the episode is cut into pieces a few seconds long, each made at several qualities, and your phone picks the next piece by how well the pieces are keeping up: adaptive streaming.

**The ending:** The new episode flowing out of the box in the provider's building down the street, piece by piece, into a hundred million phones at once with no wheel spinning: "Congratulations, you just built a content delivery network."

## Where it's known from

Netflix (Ken Florance, VP Content Delivery, 17 March 2016, 'How Netflix Works With ISPs Around the Globe to Deliver a Great Viewing Experience'): Open Connect was originally developed in 2011 and announced in 2012; qualifying ISPs get the same Open Connect Appliances Netflix uses at its own sites, and once installed 'almost all Netflix content is served from the local OCAs'; files are copied 'during off-peak hours', using 'sophisticated popularity models to make sure the right file is on the right server at the right time'; Open Connect delivers 100% of Netflix's video, from close to 1,000 locations. Netflix's Open Connect site: the boxes are 'provided to qualifying ISP partners at no charge', with nightly content fills. Akamai's company history: Tim Berners-Lee, foreseeing the congestion, challenged MIT colleagues in early 1995 to find a better way to deliver content; Leighton and Lewin incorporated Akamai on 20 August 1998 and launched commercial service in April 1999, routing and replicating content over a large network of distributed servers. RFC 8216 (HTTP Live Streaming, Apple, August 2017): media is cut into segments ('A typical target duration is 10 seconds'), offered as variant streams at different bit rates, and 'Clients should switch between different Variant Streams to adapt to network conditions', leaving how to the player; Netflix's own player chooses mainly by how full its buffer is (Huang, Johari, McKeown, Trunnell and Watson, 'A Buffer-Based Approach to Rate Adaptation: Evidence from a Large Video Streaming Service', SIGCOMM 2014). The evening jam: MIT and CAIDA (Clark et al., TPRC, September 2014) found peering links 'properly provisioned in the majority of cases', but 'the locations of major congestion are associated with specific sources of high-volume flows', naming 'dominant content providers such as Netflix and Google'; Sandvine's Global Internet Phenomena Report 2H 2014 put Netflix at 34.9% of North American downstream traffic in the peak evening hours (as reported by Lightwave, 20 November 2014; Sandvine's own release didn't open). The hundred million in the hook is the short's what-if, not a real audience.

https://about.netflix.com/en/news/how-netflix-works-with-isps-around-the-globe-to-deliver-a-great-viewing-experience

## What has to be made

- a hand and a phone with a loading wheel
- a server rack glowing red under a pile of requests
- a hall of server racks on another continent
- an ocean crossing, the episode as balls crawling along a cable
- an internet provider's building with a streaming company's box inside its racks
- a moon over the building as the boxes fill overnight
- the episode as balls in pieces of several sizes
- a phone on a train going into a tunnel

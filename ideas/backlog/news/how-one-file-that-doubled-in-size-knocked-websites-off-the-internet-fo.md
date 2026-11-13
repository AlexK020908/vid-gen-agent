# How one file that doubled in size knocked websites off the internet for hours (Nov 2025)

- **Kind:** news, built as `why_it_happens`
- **Your answer so far:** not shown to you yet

## The first second

**Heard:** One file doubled in size, and websites across the internet stopped opening.

**Seen:** A hand holding a phone, its screen a plain white error page with a big 500 on it, and behind it a wall of other screens flipping to the same page one after another.

## Why someone would stop

- **With the sound off:** The white error page everyone has met, spreading from one screen to a whole wall of them. A viewer knows the feeling at once and wants to know what broke.
- **What's at stake:** Anyone trying to log in, pay, or open a site that morning: the sites were fine and their front door was shut. It could happen again to anything a viewer uses.

## How it goes

**Area:** internet outage

**Happened:** On 18 November 2025 Cloudflare, the company that stands in front of a large share of the world's websites, began returning error pages instead of the sites behind it, from about 11:20 UTC until most traffic recovered at 14:30. Its own post-mortem says a routine database change made one internal file twice its normal size, and the software reading it stopped.

**When:** 18 November 2025, 11:20 to 14:30 UTC for the main failure, all services back at 17:06. Cloudflare's post-mortem was published the same day. It is one week short of a year old today.

**Newcomer:** Cloudflare is a doorman standing in front of millions of websites: every visitor passes him before reaching the site. Bot management is his checklist for telling people from robots. The feature file is that checklist, reprinted and sent to every door in the world every five minutes. A database is a filing cabinet, and a permissions change is giving a clerk the key to a second drawer. The limit is a clipboard with room for 200 lines. A 5xx error is the doorman holding up a CLOSED sign because he has stopped working, not because the shop is shut.

**Lesson:** Nobody attacked anything. Cloudflare wrote that the cause 'was not caused, directly or indirectly, by a cyber attack or malicious activity of any kind', called it its 'worst outage since 2019', and said it will now check the files it makes itself as carefully as files from strangers, and add switches to turn a feature off everywhere at once.

**Said by:** Cloudflare says of itself, in its post-mortem of 18 November 2025: 'The issue was not caused, directly or indirectly, by a cyber attack or malicious activity of any kind', and 'We are sorry for the impact to our customers and to the Internet in general.' https://blog.cloudflare.com/18-november-2025-outage/ . Nobody is accused of anything: it was the company's own change.

1. 11:05 UTC: engineers make a routine change to who can see what in a database. The clerk who writes the checklist can now see a second drawer holding the same records.
2. The clerk copies from both drawers, so every line of the checklist is written twice. The file doubles in size.
3. The doubled file is sent to every door. The doorman's clipboard holds 200 lines and the sheet has more, and his software stops dead instead of carrying on with the old sheet. Up goes the CLOSED sign, everywhere at once.
4. A fresh checklist is printed every five minutes, and only some of the clerks have the new key yet, so some sheets are good and some are bad. The internet comes back, falls over, comes back. It looks so much like an attack that the engineers first think it is one, and their own status page, hosted elsewhere, happens to go down at the same moment.
5. 14:24: they stop the checklist being printed and put the last good sheet at the front of the queue. By 14:30 the doors open again.

**The ending:** The doorman holding a clipboard with one clean sheet, the wall of screens flipping back from 500 to their sites. Said: 'No hacker. A list that got too long for its clipboard.'

## To settle before it's written

- Start time: 'from about 11:20 UTC (its timeline logs 11:28)'.
- Draw a clipboard with room for 200 lines and a sheet of about 60 that overruns it once the duplicates are written in (not a 200-line sheet that doubles).
- End step 4: 'until every clerk has the key, every sheet is bad, and it stays down' until the fix.

## Where it's known from

Cloudflare's own post-mortem, 'Cloudflare outage on November 18, 2025', read in full: the 11:05 permissions change, the query returning duplicate rows, the file doubling, the 200-feature limit, the five-minute regeneration producing good and bad files, the mistaken suspicion of an attack and the status page coincidence, 14:24, 14:30 and 17:06. Which well-known sites were unreachable is not in the post-mortem and I did not check it, so the card names none. The doorman and clipboard are my stand-ins, not Cloudflare's words.

https://blog.cloudflare.com/18-november-2025-outage/

## What has to be made

- a phone in a hand showing a plain 500 error page, and a wall of screens that flip to it and back
- a doorman figure at a doorway with a clipboard (invented stand-in), a CLOSED sign he raises
- a filing cabinet with two drawers and a clerk copying lines onto a sheet
- a sheet of 200 lines that doubles in length and hangs off the clipboard
- a globe with doors on it, sheets flying out to each, lights going red and green in a five-minute rhythm
- labels: 11:05, 11:20, 14:30, 200
- this could instead be a live diagram on the systems channel (tech.md): database, file, proxy, lit as the file travels

# A whole house on one Wi-Fi at once, fixed step by step into the rules every router follows

- **Kind:** tech, built as `you_invent`
- **Your answer so far:** not shown to you yet

## The first second

**Heard:** Your phone talks to the Wi-Fi by radio. Now everyone in the house talks at once.

**Seen:** A Wi-Fi router on a shelf, and a phone beside it sending a ring of radio across the room to it.

## Why someone would stop


## How it goes

**Everyday:** Using the Wi-Fi at home while everyone else in the house is on it too.

**Goal:** Get every phone's messages through one radio without them crashing.

**Invention:** how Wi-Fi takes turns (CSMA/CA)

**Seen it:** Every time the whole house is on the Wi-Fi at once.

**Cycle:** listen, wait, send, tick

**Inside:** The house from above with its walls made glass: each device's radio as rings of its own colour; crashing rings as a burst of sparks and a cross; a small countdown over each phone as it waits its random moment; the router's 'go ahead' as one big ring reaching every room.

1. Two phones send at the same instant, their waves crash and both are lost, and neither knows, so the router sends back a tick for every message it gets, and no tick means send it again: the acknowledgement.
2. Both send again at the same instant and crash again, like two people who keep starting to talk at once, so each waits a random moment before trying again: the random backoff.
3. In a busy house they still crash most of the time (the first such network, in Hawaii in 1971, could carry useful messages at best about 18% of the time), so each phone listens first and talks only when the air is quiet: carrier sense.
4. Phones at opposite ends of the house can't hear each other through the walls, so both think it's quiet and crash at the router, so before a long message a phone asks first, and the router answers out loud, "go ahead", and every phone that hears it waits: request to send, clear to send.

**The ending:** The house at night from above, every phone, laptop and TV taking turns so fast their rings look like one shimmer, each message landing at the router with a tick: "Congratulations, you just built how Wi-Fi takes turns."

## Where it's known from

IEEE Milestone, 'Demonstration of the ALOHA Packet Radio Data Network, 1971' (ETHW): in June 1971 ALOHAnet began giving inter-island access to the University of Hawaii's computers by radio; a device sent its packet and waited for an acknowledgement, 'If an acknowledgment is not received, it is assumed that a collision occurred', and the packet is 'retransmitted after a random additional waiting time'; it 'led directly to the development of Ethernet and personal wireless communication technologies', and through ARPA's packet radio to IEEE 802.11. The same page: 'Abramson showed that the effective capacity of such a channel is 1/(2e)', about 18%. Microsoft's documentation of the 802.11 RTS threshold (OID_DOT11_RTS_THRESHOLD, Compact 2013): it 'specifies the maximum length that a MAC protocol data unit (MPDU) frame can have before the 802.11 station initiates the 802.11 request to send (RTS)/clear to send (CTS) handshake', from 0 to 2347 bytes, default 2347 (citing the 1999 standard). The IEEE definition of that setting, read only through a summary, says a threshold above the largest frame turns the handshake off, so under that standard the default in effect does. That's why step 4 asks only before a long message and the cycle has no 'ask'. Newer Wi-Fi bundles frames into much longer ones, so how often a phone asks today depends on the router (my understanding, not checked). Listening first and the hidden terminal, from the original papers, which I didn't read: Kleinrock and Tobagi, 'Packet Switching in Radio Channels: Part I, Carrier Sense Multiple-Access Modes' (IEEE Transactions on Communications, 1975); Tobagi and Kleinrock, Part II, on the hidden terminal (1975); and Phil Karn, 'MACA: a new channel access method for packet radio' (ARRL Computer Networking Conference, 1990), with request-to-send and clear-to-send. These are Wi-Fi's rules for sharing the air, not all of Wi-Fi, which is why the last line says how Wi-Fi takes turns.

https://ethw.org/Milestones:Demonstration_of_the_ALOHA_Packet_Radio_Data_Network,_1971

## What has to be made

- a Wi-Fi router on a shelf
- a phone, a laptop, a tablet and a TV in different rooms
- a house whose walls can turn to glass
- radio as rings of different colours
- a crash shown as a burst of sparks and a cross
- ticks flying back from the router
- a small countdown over each device as it waits
- two invented faces both starting to talk at once

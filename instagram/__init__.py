"""Posting Reels to Instagram through Meta's own API (phase 31, BUILD.md "How Instagram posting works").

auth.py keeps the token, client.py talks to the Graph API and the upload host, and reels.py makes a short fit Meta's Reels
rules, builds its caption and runs a post step by step, so a post cut off part-way resumes rather than posting twice.
"""

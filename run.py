"""Stick Fleet entrypoint.

  python run.py demo                 headless run through every gate with placeholder providers ($0)
  python run.py status               list videos
  python run.py costs <video>        every logged cost for one video
  python run.py stage <name>         run one stage once (debugging, prompt iteration)
  python run.py bench-render         time a full-length (120-scene) render; --engine remotion|ffmpeg
  python run.py serve                engine + the MCP endpoint Claude Code connects to (http://localhost:8000/mcp)
  python run.py voice-test <ch>      one line in the channel's ElevenLabs voice (under a cent), to pick a voice
  python run.py still-test <ch>      one picture from fal with the channel's character reference (~$0.04)
  python run.py clip-test <ch>       animate that picture with the clip model (models.clip; ~$0.90 for 8 s of Kling Pro)
  python run.py topics <ch>          check competitors now and list their top recent videos; --propose for topic ideas
  python run.py connect <channel>    sign in to YouTube for one channel (opens Google's consent screen)
  python run.py youtube-test <ch>    day-1 check: upload a 20-second unlisted clip, see if it stays unlisted

Claude's work is done by the Claude Code chat on the owner's plan (providers.llm: session); there's no Claude key.
Secrets come from .env (gitignored): ELEVENLABS_API_KEY and FAL_KEY are for providers.tts: elevenlabs and
providers.images / providers.video: fal.
YOUTUBE_API_KEY reads competitors' videos for topic ideas (topics.competitors: youtube).
YouTube needs secrets/client_secret.json (gitignored); tokens go to the OS keychain.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import tempfile
import time
from pathlib import Path

from dotenv import load_dotenv

from core import actions, db
from core.config import ROOT
from core.context import make_ctx
from core.engine import Engine
from core.errors import ActionError

SHOWN = {"gate_reached", "gate_resolved", "stage_failed", "blocked", "published", "went_live", "notice"}


def _print_event(event) -> None:
    if event.kind in SHOWN:
        detail = " ".join(f"{k}={v}" for k, v in event.data.items() if k != "text")
        text = event.data.get("text", "")
        print(f"  [{event.kind}] video {event.video_id} {detail} {text}".rstrip())


def _state(ctx, video_id: int) -> str:
    with ctx.connect() as conn:
        return db.get_video(conn, video_id)["state"]


def cmd_demo(args) -> None:
    overrides = {"stub": {"scenes": args.scenes}} if args.scenes else None
    ctx = make_ctx(overrides=overrides)
    ctx.events.subscribe(_print_event)
    engine = Engine(ctx)

    def step(label: str) -> None:
        started = time.time()
        engine.run_until_idle()
        print(f"{label}: now {_state(ctx, vid)} ({time.time() - started:.1f}s)")

    vid = actions.new_video(ctx, args.channel, args.idea)
    print(f"video {vid}: {args.idea}")
    step("outline")
    actions.revise(ctx, vid, "outline", "open on the storm")
    step("outline revised with a note")
    actions.approve(ctx, vid, "outline")
    step("outline approved")
    if _state(ctx, vid) == "scripted":
        actions.approve(ctx, vid, "script")
        step("script approved")
    actions.flag_scenes(ctx, vid, [1], "visual", "darker sky")
    step("scene 1 flagged")
    actions.pick(ctx, vid, title_idx=0, thumb_idx=0)
    actions.approve(ctx, vid, "render")
    actions.request_publish(ctx, vid)
    step("publish clicked")

    info = actions.status(ctx, video_id=vid)
    with ctx.connect() as conn:
        video = db.get_video(conn, vid)
    print(f"\nstate {info['state']}, simulated cost ${info['cost_usd']:.2f} of ${info['budget_usd']:.0f}")
    print(f"video:   {ctx.abs(video['video_path'])}")
    print(f"publish: {ctx.media(vid) / 'publish_request.json'}")


def cmd_status(args) -> None:
    ctx = make_ctx()
    for v in actions.status(ctx, channel_id=args.channel)["videos"]:
        print(f"#{v['id']:<4} {v['channel_id']:<10} {v['state']:<16} ${v['cost_usd']:<7.2f} {v['topic']}")


def cmd_costs(args) -> None:
    ctx = make_ctx()
    with ctx.connect() as conn:
        rows = conn.execute("SELECT * FROM costs WHERE video_id = ? ORDER BY id", (args.video,)).fetchall()
    total = 0.0
    for r in rows:
        total += r["usd"]
        line = f"{time.strftime('%H:%M:%S', time.localtime(r['created_at']))} {r['stage']:<9} {r['provider']:<7} "                f"${r['usd']:<8.4f}{' (simulated)' if r['simulated'] else ''}"
        d = json.loads(r["detail"]) if r["detail"] else None
        if d:
            line += (f"  {d['model']}: {d['input']:,} in, {d['cache_write']:,} cache write, {d['cache_read']:,} "
                     f"cache read, {d['output']:,} out ({d['stop']}); guard estimate ${d['estimate_usd']:.2f}")
        print(line)
    print(f"{len(rows)} rows, ${total:.2f}")


def cmd_stage(args) -> None:
    from stages import BY_NAME
    ctx = make_ctx()
    ctx.events.subscribe(_print_event)
    ran = BY_NAME[args.name].run_once(ctx)
    print(f"{args.name}: {'did work' if ran else 'nothing to do'}")


def cmd_bench_render(args) -> None:
    from providers.images import StubImages
    from providers.llm import NoMeter, StubLLM
    from providers.tts import StubTTS
    from providers.video import StubVideo
    from render.render import render_video

    ctx = make_ctx(overrides={"stub": {"scenes": args.scenes}})
    channel = ctx.channel(args.channel)
    llm, tts, images = StubLLM(args.scenes), StubTTS(), StubImages()
    outline = llm.outline(channel, "Render benchmark", [], None, NoMeter())
    script = llm.script(channel, outline, [], None, NoMeter())["scenes"]
    work = Path(tempfile.mkdtemp(prefix="bench_", dir=ctx.config.data_dir))
    print(f"preparing {len(script)} placeholder scenes in {work} ...")
    items = []
    for s in script:
        still, audio = work / f"s{s['idx']:03d}.png", work / f"s{s['idx']:03d}.wav"
        images.still(channel, s["visual_prompt"], s["label"], still)
        result, _ = tts.speak(channel, s["narration"], audio)
        clip = None
        if s["motion"] == "clip":  # the stub script's hero scenes, as in the pipeline
            clip = work / f"c{s['idx']:03d}.mp4"
            stub = StubVideo()
            stub.clip(channel, still, s["visual_prompt"], clip, stub.seconds)
        items.append({"idx": s["idx"], "beat_idx": s["beat_idx"], "narration": s["narration"],
                      "duration_ms": result["duration_ms"], "audio": str(audio), "still": str(still),
                      "clip": str(clip) if clip else None, "words": result["words"]})
    minutes = sum(i["duration_ms"] for i in items) / 60_000
    settings = {**ctx.config.render, **{k: v for k, v in (("concurrency", args.concurrency),
                                                          ("x264_preset", args.x264_preset)) if v}}
    extra = ", ".join(f"{k} {settings[k]}" for k in ("concurrency", "x264_preset") if settings.get(k))
    print(f"rendering {minutes:.1f} minutes of video with {args.engine}"
          f"{f' ({extra})' if extra and args.engine == 'remotion' else ''} ...")
    unit = "%" if args.engine == "remotion" else " segments"
    started = time.time()
    out = render_video(items, outline["beats"], work / "render",
                       lambda d, t: print(f"\r  {d}/{t}{unit}", end="", flush=True), args.engine, settings)
    elapsed = time.time() - started
    print(f"\n{minutes:.1f}-minute video rendered in {elapsed / 60:.1f} min ({elapsed:.0f}s): {out['video']}")


def cmd_voice_test(args) -> None:
    from providers.elevenlabs import ElevenLabsTTS
    ctx = make_ctx()
    out = ctx.config.data_dir / f"voice_test_{args.channel}.mp3"
    result, usd = ElevenLabsTTS(ctx.config).speak(ctx.channel(args.channel), args.text, out)
    print(f"{out}: {result['duration_ms'] / 1000:.1f} s, {len(result['words'])} words timed, ${usd:.4f}")


def cmd_still_test(args) -> None:
    from providers.fal import FalImages
    ctx = make_ctx()
    out = ctx.config.data_dir / f"still_test_{args.channel}.png"
    usd = FalImages(ctx.config).still(ctx.channel(args.channel), args.prompt, "test", out)
    print(f"{out}: ${usd:.3f}")


def cmd_clip_test(args) -> None:
    from providers.fal import FalVideo
    ctx = make_ctx()
    still = ctx.config.data_dir / f"still_test_{args.channel}.png"
    if not still.exists():
        sys.exit(f"{still} isn't there yet; run `python run.py still-test {args.channel}` first")
    video = FalVideo(ctx.config)
    seconds = args.seconds or video.seconds
    out = ctx.config.data_dir / f"clip_test_{args.channel}.mp4"
    print(f"animating {still.name} with {video.model}, {seconds} s (about ${video.price(seconds):.2f}); "
          "this takes a few minutes ...")
    usd = video.clip(ctx.channel(args.channel), still, args.prompt, out, seconds)
    print(f"{out}: ${usd:.2f}")


def cmd_topics(args) -> None:
    from stages import topics
    ctx = make_ctx()
    ctx.events.subscribe(_print_event)
    channel = ctx.channel(args.channel)
    print(f"competitors: {ctx.config.topics.get('competitors', 'stub')}")
    hits = topics.poll(ctx, channel)
    for n, h in enumerate(hits[:15], 1):
        print(f"{n:>2}. {h['per_day']:>10,.0f}/day {h['views']:>12,} views  {h['title']}  ({h['channel']})")
    if args.propose:
        topics.propose(ctx, channel)
    with ctx.connect() as conn:
        rows = conn.execute("SELECT id, title, why FROM topics WHERE channel_id = ? AND status = 'queued' "
                            "ORDER BY score DESC, id", (channel.id,)).fetchall()
    print(f"\n{len(rows)} queued topics" + (":" if rows else ""))
    for r in rows:
        print(f"  [{r['id']}] {r['title']}\n       {r['why']}")


def cmd_connect(args) -> None:
    from youtube import auth
    ctx = make_ctx()
    print("Opening Google's sign-in in your browser. Pick the brand channel for "
          f"{ctx.channel(args.channel).name}, and tick every permission.")
    result = auth.connect(ctx, args.channel)
    print(f"Connected {args.channel} to {result['title']} ({result['youtube_channel_id']}). "
          f"Token saved in the OS keychain; youtube.channel_id written to the channel YAML.")


def cmd_youtube_test(args) -> None:
    """Uploads from unaudited API projects used to be locked to private; this checks ours on day 1."""
    from render import ffmpeg
    from youtube import client
    ctx = make_ctx()
    yt = client.Client(ctx, args.channel)
    clip = ctx.config.data_dir / "youtube_test.mp4"
    ffmpeg.run(["-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=30:duration=20",
                "-f", "lavfi", "-i", "sine=frequency=440:duration=20",
                *ffmpeg.VIDEO_OUT, *ffmpeg.AUDIO_OUT, "-shortest", clip])
    body = {
        "snippet": {"title": "Stick Fleet API test (safe to remove)", "categoryId": "24",
                    "description": "A 20-second test pattern uploaded by Stick Fleet to check API uploads."},
        "status": {"privacyStatus": "unlisted", "selfDeclaredMadeForKids": False},
    }
    print("uploading a 20-second test clip as unlisted ...")
    video_id = yt.upload(clip, body, lambda f: print(f"\r  {f:.0%}", end="", flush=True))
    status = yt.video_status(video_id)
    print(f"\nuploaded: https://youtu.be/{video_id}  (privacy: {status['privacy']}, upload: {status['upload']})")
    if status["privacy"] == "unlisted":
        print("OK: it stayed unlisted, so this project isn't locked to private. Scheduled publishing will work.")
    else:
        print(f"LOCKED: YouTube made it {status['privacy']}. File the YouTube API Services audit now "
              "(https://support.google.com/youtube/contact/yt_api_form); it's a manual review.")
    print("There's no delete tool on purpose: remove the test video in Studio "
          f"(https://studio.youtube.com/video/{video_id}/edit).")


def cmd_serve(args) -> None:
    import uvicorn

    from server.app import create_app

    app = create_app()
    print(f"Stick Fleet: engine running, MCP for Claude Code at http://localhost:{args.port}/mcp  (Ctrl+C to stop)")
    print("Open Claude Code in this folder (or the one above) and ask it what's waiting.")
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")


def main() -> None:
    load_dotenv(ROOT / ".env")
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(prog="run.py", description="Stick Fleet")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("demo", help="headless run through every gate with placeholder providers")
    p.add_argument("--channel", default="zombie")
    p.add_argument("--idea", default="Day 1 to Day 365 stranded on an oil rig")
    p.add_argument("--scenes", type=int, default=None)
    p.set_defaults(fn=cmd_demo)

    p = sub.add_parser("status", help="list videos")
    p.add_argument("--channel", default=None)
    p.set_defaults(fn=cmd_status)

    p = sub.add_parser("costs", help="every logged cost for one video")
    p.add_argument("video", type=int)
    p.set_defaults(fn=cmd_costs)

    p = sub.add_parser("stage", help="run one stage once")
    p.add_argument("name")
    p.set_defaults(fn=cmd_stage)

    p = sub.add_parser("bench-render", help="time a full-length render")
    p.add_argument("--channel", default="zombie")
    p.add_argument("--scenes", type=int, default=120)
    p.add_argument("--engine", choices=["remotion", "ffmpeg"], default="ffmpeg")
    p.add_argument("--concurrency", default=None, help="Remotion browser tabs (number or percent, e.g. 50%%)")
    p.add_argument("--x264-preset", default=None, help="Remotion's x264 preset (veryfast, faster, medium, ...)")
    p.set_defaults(fn=cmd_bench_render)

    p = sub.add_parser("serve", help="engine + MCP endpoint for Claude Code")
    p.add_argument("--port", type=int, default=8000)
    p.set_defaults(fn=cmd_serve)

    p = sub.add_parser("voice-test", help="one line in the channel's ElevenLabs voice")
    p.add_argument("channel")
    p.add_argument("text", nargs="?", default="Day 1. The power goes out at noon, and by sunset the street below "
                                               "his window has gone completely quiet. Nobody is coming.")
    p.set_defaults(fn=cmd_voice_test)

    p = sub.add_parser("still-test", help="one picture from fal with the channel's character reference")
    p.add_argument("channel")
    p.add_argument("prompt", nargs="?", default="The stick figure stands at an apartment window at dusk, looking "
                                                "down at an empty street. Medium shot, tense, the last light fading.")
    p.set_defaults(fn=cmd_still_test)

    p = sub.add_parser("clip-test", help="animate the still-test picture with the clip model")
    p.add_argument("channel")
    p.add_argument("prompt", nargs="?", default="The stick figure stands at an apartment window at dusk, looking "
                                                "down at an empty street. Medium shot, tense. He slowly leans "
                                                "closer to the glass as the last light fades.")
    p.add_argument("--seconds", type=int, help="clip length (default: fal.clips.seconds)")
    p.set_defaults(fn=cmd_clip_test)

    p = sub.add_parser("topics", help="check competitors now and list their top recent videos")
    p.add_argument("channel")
    p.add_argument("--propose", action="store_true", help="also ask for topic ideas (a Claude call in live mode)")
    p.set_defaults(fn=cmd_topics)

    p = sub.add_parser("connect", help="sign in to YouTube for one channel")
    p.add_argument("channel")
    p.set_defaults(fn=cmd_connect)

    p = sub.add_parser("youtube-test", help="day-1 unlisted test upload")
    p.add_argument("channel")
    p.set_defaults(fn=cmd_youtube_test)

    args = parser.parse_args()
    try:
        args.fn(args)
    except ActionError as e:
        sys.exit(f"Stopped: {e}")


if __name__ == "__main__":
    main()

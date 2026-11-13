"""A film script rendered in parts: Blender processes side by side, each taking its share of the frames, under
render/limits.py's ceiling (how many processes, which cores, what priority). A frame already made is left alone, so a
stopped render picks up where it left off, and one that won't open (a render killed while writing it) is made again.

    .venv/Scripts/python -m render.film_parts <film.py> <frames folder> <last frame> [--samples 48] [--width 720]
                                              [--frames 12,40,41] -- <the script's own arguments>      (from stickfleet/)

Each process runs  blender -b -P <film.py> -- <frames folder> <its own arguments> <first> <last> <step> <samples> <width>
with FILM_FRAMES set to the frames it's to make (the script renders only those). With --frames only those are wanted.
Ends by checking every wanted frame is there and opens, and exits 1 if one isn't.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

from PIL import Image

from core import config as cfg
from render import blender_render, limits

ENV_ROOM = 30000      # characters of FILM_FRAMES that fit in one Windows environment variable, with room to spare


def opens(path: Path) -> bool:
    try:
        with Image.open(path) as picture:
            picture.verify()
        return True
    except Exception:
        return False


def missing(out: Path, wanted: list[int]) -> list[int]:
    """The wanted frames that aren't made. A frame's file that won't open is removed, so it's made again."""
    todo = []
    for f in wanted:
        path = out / f"f_{f:04d}.png"
        if path.exists() and not opens(path):
            path.unlink()
            print(f"frame {f} wouldn't open: removed, to be made again", flush=True)
        if not path.exists():
            todo.append(f)
    return todo


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Render a film script's frames in parts, under render.limits")
    p.add_argument("script")
    p.add_argument("out")
    p.add_argument("last", type=int)
    p.add_argument("--samples", type=int, default=48)
    p.add_argument("--width", type=int, default=720)
    p.add_argument("--frames", default=None, help="only these frames, as 12,40,41")
    p.add_argument("own", nargs="*", help="the script's own arguments, after --")
    args = p.parse_args(argv)
    config = cfg.load()
    out, script = Path(args.out).resolve(), Path(args.script).resolve()
    out.mkdir(parents=True, exist_ok=True)
    wanted = [int(n) for n in args.frames.split(",")] if args.frames else list(range(1, args.last + 1))
    todo = missing(out, wanted)
    count = min(limits.processes(config), len(todo))
    print(f"{len(wanted) - len(todo)} of {len(wanted)} frames already made; {len(todo)} to make in {count} process(es), "
          f"{limits.threads(config, max(count, 1))} thread(s) each, on {limits.cores(config)} of {os.cpu_count()} cores", flush=True)
    running = []
    for i in range(count):
        share = ",".join(str(f) for f in todo[i::count])
        env = dict(os.environ)
        env.pop("FILM_FRAMES", None)
        first, step = i + 1, count
        if len(share) <= ENV_ROOM:
            env["FILM_FRAMES"] = share
        elif args.frames:
            raise SystemExit("too many --frames for one process: give fewer, or render the whole film")
        cmd = [str(blender_render.exe(config)), "-b", "-t", str(limits.threads(config, count)), "--python-exit-code", "1",
               "-P", str(script), "--", str(out), *args.own, str(first), str(args.last), str(step), str(args.samples), str(args.width)]
        log = open(out.parent / f"{out.name}_part{i + 1}.log", "w", encoding="utf-8")
        running.append((limits.start(config, cmd, stdout=log, stderr=subprocess.STDOUT, env=env), log))
    said = time.time()
    while any(proc.poll() is None for proc, _ in running):
        time.sleep(5)
        if time.time() - said >= 300:
            said = time.time()
            print(f"{len(wanted) - len([f for f in wanted if not (out / f'f_{f:04d}.png').exists()])} of {len(wanted)} frames", flush=True)
    failed = False
    for i, (proc, log) in enumerate(running):
        log.close()
        if proc.returncode != 0:
            failed = True
            print(f"process {i + 1} ended with {proc.returncode}: see {out.parent / f'{out.name}_part{i + 1}.log'}", flush=True)
    left = missing(out, wanted)
    if left:
        print(f"NOT DONE: {len(left)} frame(s) missing, the first {left[:20]}", flush=True)
        return 1
    print(f"FRAMES DONE: all {len(wanted)} in {out}", flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

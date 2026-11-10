"""A short made fit for Meta's Reels rules, its caption, and one post run step by step.

Meta's Reels rules (the IG User Media reference, read Nov 9, 2026): MOV or MP4 with no edit lists and the moov atom at the
front; H.264 or HEVC video, progressive, 4:2:0, 23 to 60 fps, at most 1920 pixels across; AAC audio, at most 48 kHz, one or
two channels; 3 seconds to 15 minutes; at most 300 MB. A caption is at most 2,200 characters, 30 hashtags and 20 @ tags.
Containers expire 24 hours after they're made, and Meta asks that a container's status be checked about once a minute.

`post` keeps what's done in `steps` and saves it after each step, so a post cut off part-way picks up where it stopped: the
file isn't sent twice, and a publish that may have gone through without the reply arriving is looked for before trying
again, so nothing is ever posted twice.
"""
from __future__ import annotations

import re
import time
from datetime import datetime
from pathlib import Path
from typing import Callable

from core.errors import ActionError
from instagram.client import TOKEN_CODES, Client, InstagramError
from render import ffmpeg

MIN_S, MAX_S = 3, 15 * 60
MAX_BYTES = 300 * 1024 * 1024
FPS_RANGE = (23, 60)
MAX_WIDTH = 1920
MAX_CAPTION, MAX_HASHTAGS, MAX_TAGS = 2200, 30, 20
CONTAINER_LIFE_S = 23 * 3600          # Meta's 24 h, less an hour so a container is never used just as it lapses
CHECKS_S = (10, 20, 30) + (60,) * 9   # seconds before each status check: soon at first, then once a minute
FOUND_SLACK_S = 300                   # a post found within this of the publish call is that call's post
UPLOAD_WAITS_S = (15, 60)             # seconds before sending the bytes again, after the upload host refuses them


# --- the file -----------------------------------------------------------------------------------------------------

def describe(path: Path) -> dict:
    """What ffmpeg says the file is: video codec, pixel format, size, fps; audio codec, rate, channels; seconds."""
    text = ffmpeg.probe(path)
    out: dict = {"seconds": None, "video": None, "audio": None}
    m = re.search(r"Duration: (\d+):(\d+):(\d+(?:\.\d+)?)", text)
    if m:
        out["seconds"] = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    v = re.search(r"Stream #\S+.*?Video: (\w+)(.*)", text)
    if v:
        rest = v.group(2)
        size = re.search(r"\b(\d{2,5})x(\d{2,5})\b", rest)
        fps = re.search(r"([\d.]+) fps", rest)
        pix = re.search(r"\b(yuv\w+|yuvj\w+|rgb\w+|bgr\w+|gray\w*|nv12)\b", rest)
        out["video"] = {"codec": v.group(1), "pix": pix.group(1) if pix else None,
                        "width": int(size.group(1)) if size else None, "height": int(size.group(2)) if size else None,
                        "fps": float(fps.group(1)) if fps else None}
    a = re.search(r"Stream #\S+.*?Audio: (\w+)(.*)", text)
    if a:
        rest = a.group(2)
        rate = re.search(r"(\d+) Hz", rest)
        layout = re.search(r"Hz, ([^,]+)", rest)
        named = {"mono": 1, "stereo": 2}.get(layout.group(1).strip() if layout else "", None)
        counted = re.search(r"(\d+) channels", rest)
        channels = named or (int(counted.group(1)) if counted else 6 if layout and "5.1" in layout.group(1) else None)
        out["audio"] = {"codec": a.group(1), "rate": int(rate.group(1)) if rate else None, "channels": channels}
    return out


def problems(path: Path) -> list[str]:
    """Where a file breaks Meta's Reels rules, in words; empty when it's fine."""
    if not path.exists():
        return [f"there's no file at {path}"]
    found = []
    size = path.stat().st_size
    if size > MAX_BYTES:
        found.append(f"it's {size / 1024 / 1024:.0f} MB; Reels take at most 300 MB")
    info = describe(path)
    seconds, video, audio = info["seconds"], info["video"], info["audio"]
    if seconds is None:
        found.append("ffmpeg can't read how long it is")
    elif not MIN_S <= seconds <= MAX_S:
        found.append(f"it runs {seconds:.1f} s; Reels run 3 seconds to 15 minutes")
    if not video:
        found.append("it has no video")
    else:
        if video["codec"] not in ("h264", "hevc"):
            found.append(f"its video is {video['codec']}; Reels take H.264 or HEVC")
        if video["pix"] and not video["pix"].startswith(("yuv420p", "yuvj420p")):
            found.append(f"its pixels are {video['pix']}; Reels take 4:2:0")
        if video["fps"] and not FPS_RANGE[0] <= video["fps"] <= FPS_RANGE[1]:
            found.append(f"it's {video['fps']:g} fps; Reels take 23 to 60")
        if video["width"] and video["width"] > MAX_WIDTH:
            found.append(f"it's {video['width']} pixels across; Reels take at most {MAX_WIDTH}")
        if video["width"] and video["height"] and not 0.01 <= video["width"] / video["height"] <= 10:
            found.append("its shape is outside 0.01:1 to 10:1")
    if audio:
        if audio["codec"] != "aac":
            found.append(f"its sound is {audio['codec']}; Reels take AAC")
        if audio["rate"] and audio["rate"] > 48000:
            found.append(f"its sound is {audio['rate']} Hz; Reels take at most 48 kHz")
        if audio["channels"] and audio["channels"] > 2:
            found.append(f"its sound has {audio['channels']} channels; Reels take one or two")
    return found


AAC_PRIMING = 1024   # samples ffmpeg's AAC encoder puts before the sound; with no edit list to skip them, they'd play


def prepare(src: Path, out: Path) -> Path:
    """A copy of `src` made to Meta's rules at `out`: the picture copied as it is when it already fits (re-encoded only
    when it doesn't), the sound as AAC at 48 kHz in stereo, the moov atom first and no edit lists. Refused, in words,
    if the copy still doesn't fit.

    Meta's "no edit lists" is what normally keeps picture and sound in step, so it's done another way, measured to the
    sample and the frame (tests/test_instagram.py): the picture's reordered frames get negative composition offsets
    rather than starting two frames late, and the sound's first 1,024 samples are cut to make room for the encoder's
    priming, which would otherwise play first and put every sound 21 ms late."""
    if not src.exists():
        raise ActionError(f"the video file isn't there: {src}")
    info = describe(src)
    video = info["video"] or {}
    fits = (video.get("codec") in ("h264", "hevc") and str(video.get("pix") or "").startswith(("yuv420p", "yuvj420p"))
            and FPS_RANGE[0] <= (video.get("fps") or 0) <= FPS_RANGE[1] and (video.get("width") or 0) <= MAX_WIDTH)
    picture = ["-c:v", "copy"] if fits else [
        "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-profile:v", "high",
        "-vf", f"scale='min({MAX_WIDTH},iw)':-2", "-r", "30"]
    sound = ["-map", "0:a:0", "-af", f"aresample=48000,atrim=start_sample={AAC_PRIMING},asetpts=PTS-STARTPTS",
             "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-ac", "2"] if info["audio"] else ["-an"]
    out.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg.run(["-i", src, "-map", "0:v:0", *picture, *sound,
                "-movflags", "+faststart+negative_cts_offsets", "-use_editlist", "0", out])
    wrong = problems(out)
    if wrong:
        raise ActionError("the short doesn't fit Instagram's rules for Reels: " + "; ".join(wrong))
    return out


# --- the caption --------------------------------------------------------------------------------------------------

MAKER = re.compile(r'^".*?" by (.+?) \((?:https?://)?[^)]*\)')   # things/get.py's credit: "name" by maker (page), ...


def makers(credits: list[str] | None) -> list[str]:
    """Who made each model, from its credit line, in order and once each. A line in another shape is kept whole."""
    out: list[str] = []
    for line in credits or []:
        line = line.replace("@", "").strip()
        found = MAKER.match(line)
        name = found.group(1).strip() if found else line
        if name and name not in out:
            out.append(name)
    return out


def credit_line(credits: list[str] | None) -> str:
    """The models' credits in one short line. CC BY 4.0 lets the credit be given "in any reasonable manner based on the
    medium" (section 3(a)(2)), and a caption's links can't be tapped, so it's the makers, that they're adapted, and the
    license."""
    names = makers(credits)
    if not names:
        return ""
    joined = names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]
    return f"3D models adapted from {joined} (CC BY 4.0)."


def caption(title: str, hashtags: list[str] | None = None) -> str:
    """Short, as the owner asked on Nov 10, 2026 ("caption should be short and concise", after the first post's ran to
    eleven lines of credits and links, then "remove this" of a one-line credit): the title and the channel's hashtags,
    nothing else. The models' credits are kept apart (`credit_line`)."""
    parts = [title.strip()]
    tags = [re.sub(r"[^\w]", "", str(h).lstrip("#")) for h in hashtags or []]
    if any(tags):
        parts.append(" ".join(f"#{t}" for t in tags if t))
    return "\n\n".join(p for p in parts if p)


def caption_problems(text: str) -> list[str]:
    found = []
    if not text.strip():
        found.append("the caption is empty")
    if len(text) > MAX_CAPTION:
        found.append(f"the caption is {len(text)} characters; Instagram takes {MAX_CAPTION}")
    hashtags = re.findall(r"(?<![\w&])#\w+", text)
    if len(hashtags) > MAX_HASHTAGS:
        found.append(f"the caption has {len(hashtags)} hashtags; Instagram takes {MAX_HASHTAGS}")
    tags = re.findall(r"(?<![\w.])@[\w.]+", text)
    if len(tags) > MAX_TAGS:
        found.append(f"the caption tags {len(tags)} accounts; Instagram takes {MAX_TAGS}")
    return found


# --- one post -----------------------------------------------------------------------------------------------------

def _when(stamp: str) -> float:
    return datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%S%z").timestamp()


def _found(cl: Client, ig_id: str, since: float) -> str | None:
    """The account's post made at or after `since` (less a little), if there is one: the newest such."""
    for item in cl.recent(ig_id):
        try:
            if _when(item["timestamp"]) >= since - FOUND_SLACK_S:
                return item["id"]
        except (KeyError, ValueError):
            continue
    return None


def _wait(cl: Client, container: str, sleep: Callable[[float], None]) -> None:
    for pause in CHECKS_S:
        sleep(pause)
        status = cl.status(container)
        if status in ("FINISHED", "PUBLISHED"):
            return
        if status == "ERROR":
            why = cl.why(container)
            raise InstagramError(f"Meta couldn't process the video{': ' + why if why else ''}. Retry makes a fresh upload")
        if status == "EXPIRED":
            raise InstagramError("the upload expired before it was posted; Retry makes a fresh upload")
    raise InstagramError("Meta is still processing the video after 10 minutes; Retry looks again", retriable=True)


def _upload(cl: Client, uri: str, path: Path, sleep: Callable[[float], None]) -> None:
    """Send the bytes, and again into the same container if the upload host refuses them. Its "Request processing
    failed" on Nov 10, 2026 (the first real post) went through when sent again at once. A refused token isn't tried
    again; after the last try the error is left for Retry, which sends them into the same container once more."""
    for wait in (*UPLOAD_WAITS_S, None):
        try:
            return cl.upload(uri, path)
        except InstagramError as e:
            if e.code in TOKEN_CODES:
                raise
            if wait is None:
                raise InstagramError(str(e), retriable=True, code=e.code) from None
            sleep(wait)


def post(cl: Client, ig_id: str, path: Path, text: str, ai_generated: bool, steps: dict, save: Callable[[dict], None],
         thumb_offset_ms: int | None = None, sleep: Callable[[float], None] = time.sleep,
         now: Callable[[], float] = time.time) -> dict:
    """Post `path` as a Reel on account `ig_id`, or carry on with an earlier try recorded in `steps` (saved with `save`
    after each step). Returns {"media_id", "permalink"}."""
    def done(**fields) -> None:
        steps.update(fields)
        save(steps)

    if "media_id" not in steps:
        made = steps.get("container")
        if made and steps.get("publish_started") and cl.status(made["id"]) == "PUBLISHED":
            found = _found(cl, ig_id, steps["publish_started"])   # it went up, but the reply never came
            if not found:
                raise InstagramError("Meta says this short was posted, but it isn't among the account's newest posts. "
                                     "Look on the account before posting it again")
            done(media_id=found)
    if "media_id" not in steps:
        made = steps.get("container")
        if made and (steps.get("failed") or now() - made["made"] > CONTAINER_LIFE_S):
            for key in ("container", "uploaded", "ready", "publish_started", "failed"):
                steps.pop(key, None)
            save(steps)
        if "container" not in steps:
            done(container={**cl.create_reel(ig_id, text, ai_generated, thumb_offset_ms), "made": now()})
        made = steps["container"]
        if not steps.get("uploaded"):
            _upload(cl, made["uri"], path, sleep)
            done(uploaded=True)
        if not steps.get("ready"):
            try:
                _wait(cl, made["id"], sleep)
            except InstagramError as e:
                if not e.retriable:
                    done(failed=str(e))
                raise
            done(ready=True)
        done(publish_started=now())
        done(media_id=cl.publish(ig_id, made["id"]))
    if "permalink" not in steps:
        try:
            link = cl.media(steps["media_id"]).get("permalink")
        except InstagramError:
            link = None   # posted all the same; the link is only a convenience
        done(permalink=link)
    return {"media_id": steps["media_id"], "permalink": steps.get("permalink")}

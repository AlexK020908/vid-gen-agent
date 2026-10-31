"""fal.ai pictures and hero clips.

Pictures: an image-edit model (models.still) with reference images on every call: the channel's character
first, then for a still the place it happens in and the cast members in it (stages/stills.py draws those
with place(), change_place() and person()). Each reference is uploaded to fal's file storage once, and again
when the file changes or an hour has passed. Each still sends prompts/still.md filled with the scene's visual
prompt, a line naming what each reference image is, and the channel's style; thumbnails send
prompts/thumbnail.md, places prompts/place.md and prompts/place_change.md, cast members prompts/person.md.
fal returns an image at the model's size, which is scaled and cropped to 1920×1080 (stills and places),
1280×720 (thumbnails) or 1024×1536 (cast members). fal bills this model by tokens and the reply doesn't say
what it cost, so the logged cost is the per-image list price in fal.prices.

Clips: an image-to-video model (models.clip) animates a clip scene's own still, with prompts/clip.md.
What each model takes (the still's field name, the lengths it offers, extra arguments) and its price
per second are in fal.clips.models, so switching models is a config change. The logged cost is the
clip's length times that price.
"""
from __future__ import annotations

import io
import os
import re
import threading
import time
from pathlib import Path

import fal_client
import httpx2
from PIL import Image, ImageOps

from core.errors import FinalError
from providers import prompts
from render import ffmpeg

STILL_SIZE, THUMB_SIZE, PERSON_SIZE = (1920, 1080), (1280, 720), (1024, 1536)
REUPLOAD_S = 3600
WAIT_S = 300        # the longest one picture may take, queue included
CLIP_WAIT_S = 1200  # clips take minutes, more when fal is busy


def clip_settings(config) -> tuple[str, dict, int]:
    """models.clip, its entry in fal.clips.models, and the clip length, checked against what it offers."""
    clips = config.fal.get("clips") or {}
    model = config.models.get("clip", "")
    spec = (clips.get("models") or {}).get(model)
    if spec is None:
        raise ValueError(f"models.clip is {model!r}, which fal.clips.models doesn't describe; add it there "
                         "(its fal page lists the fields and the price)")
    seconds = int(clips.get("seconds", 8))
    if seconds not in spec["seconds"]:
        offered = ", ".join(str(s) for s in spec["seconds"])
        raise ValueError(f"fal.clips.seconds is {seconds}, but {model} makes clips of {offered} seconds")
    return model, spec, seconds


class _Fal:
    """The fal client, the file host and fal's errors, shared by pictures and clips."""

    def __init__(self, config, client, http: httpx2.Client | None, concurrency: int) -> None:
        self.root = config.root
        self._slots = threading.BoundedSemaphore(concurrency)
        self._client = client  # tests pass fakes for both
        self._http = http

    @property
    def client(self):
        if self._client is None:
            key = os.environ.get("FAL_KEY")
            if not key:
                raise FinalError("fal.ai needs FAL_KEY in .env (see .env.example). Add it, restart, then Retry")
            self._client = fal_client.SyncClient(key=key)
        return self._client

    @property
    def http(self) -> httpx2.Client:
        if self._http is None:
            self._http = httpx2.Client(timeout=120, follow_redirects=True)
        return self._http

    def _call(self, fn, refused: str = "picture"):
        try:
            return fn()
        except fal_client.FalClientHTTPError as e:
            if e.status_code in (401, 403):
                raise FinalError(f"fal.ai turned down the request ({e.message}). Check FAL_KEY and your fal "
                                 "balance, then Retry") from None
            if "content_policy" in (e.error_type or ""):
                raise FinalError(f"fal.ai refused this {refused} ({e.message}). Change the scene's picture "
                                 "prompt, then Retry") from None
            raise RuntimeError(f"fal.ai {e.status_code}: {e.message}") from None

    def _download(self, url: str) -> bytes:
        response = self.http.get(url)
        response.raise_for_status()
        return response.content


class FalImages(_Fal):
    def __init__(self, config, client=None, http: httpx2.Client | None = None) -> None:
        settings = config.fal
        super().__init__(config, client, http, int(settings.get("concurrency", 8)))
        self.model = config.models["still"]
        self.resolution = settings.get("resolution", "1K")
        prices = settings.get("prices") or {}
        if self.resolution not in prices:
            raise ValueError(f"fal.resolution is {self.resolution!r} but fal.prices has no price for it")
        self.still_price = self.thumb_price = float(prices[self.resolution])
        self._refs: dict[Path, tuple[float, float, str]] = {}  # path → (file mtime, uploaded at, url)
        self._lock = threading.Lock()

    def still(self, channel, prompt: str, label: str, out: Path, place: tuple | None = None,
              people: list | tuple = (), hero: tuple | None = ("", None)) -> float:
        """`hero` is (what the main character has on now, their picture; the character reference when None), or
        None when the scene doesn't show them. `place` and each of `people` are (name, look, picture or None):
        drawn from the picture when there is one, and from the look when not."""
        refs, said = [], []

        def ref(path, what: str) -> None:
            refs.append(Path(path))
            said.append(f"Image {len(refs)} is {what}.")

        if hero is not None:
            now, picture = hero
            ref(picture or self._character(channel), "the main character" + (f", now with {now}" if now else ""))
        if place and place[2]:
            ref(place[2], f"the place: {place[0]}")
        elif place:
            said.append(f"The scene happens in {place[0]}: {place[1]}")
        for name, look, picture in people:
            if picture:
                ref(picture, f"{name}, {look}")
            else:
                said.append(f"{name}, who has no reference image, is {look}.")
        if hero is None:
            said.append("The main character is not in this picture: don't draw them, and nobody else wears their "
                        "clothes.")
            if not refs:  # the model needs a picture to work from; the character's shows the style
                refs.append(self._character(channel))
                said.insert(0, "Image 1 shows only the art style.")
        elif people:
            said.append("Nobody but the main character wears the main character's clothes.")
        text = prompts.fill(self.root, "still.md", channel, {"visual_prompt": prompt, "references": " ".join(said)})
        self._draw(text, refs, out, STILL_SIZE)
        return self.still_price

    def thumbnail(self, channel, title: str, variant: int, out: Path) -> float:
        text = prompts.fill(self.root, "thumbnail.md", channel, {"title": title, "variant": variant + 1})
        self._draw(text, [self._character(channel)], out, THUMB_SIZE)
        return self.thumb_price

    def place(self, channel, name: str, look: str, out: Path) -> float:
        """A place, empty, in the style of the character reference: what every still there is drawn from."""
        text = prompts.fill(self.root, "place.md", channel, {"name": name, "look": look})
        self._draw(text, [self._character(channel)], out, STILL_SIZE)
        return self.still_price

    def change_place(self, channel, base: Path, change: str, out: Path) -> float:
        """The same place after a change that lasts, drawn from its previous picture."""
        text = prompts.fill(self.root, "place_change.md", channel, {"change": change})
        self._draw(text, [Path(base)], out, STILL_SIZE)
        return self.still_price

    def person(self, channel, name: str, look: str, out: Path) -> float:
        """A cast member, full length on a plain background, in the style of the character reference."""
        text = prompts.fill(self.root, "person.md", channel, {"name": name, "look": look})
        self._draw(text, [self._character(channel)], out, PERSON_SIZE, aspect="2:3")
        return self.still_price

    def change_look(self, channel, base: Path, now: str, out: Path) -> float:
        """The same character with what they have on now (body armor, a bandage), drawn from their picture."""
        text = prompts.fill(self.root, "person_change.md", channel, {"now": now})
        self._draw(text, [Path(base)], out, PERSON_SIZE, aspect="2:3")
        return self.still_price

    @staticmethod
    def _character(channel) -> Path:
        path = Path(channel.character_ref)
        if not path.is_file():
            raise FinalError(f"the character reference {path} is missing; add it (see character_ref in "
                             f"channels/{channel.id}.yaml), then Retry")
        return path

    def _upload(self, path: Path) -> str:
        with self._lock:
            mtime = path.stat().st_mtime
            cached = self._refs.get(path)
            if cached and cached[0] == mtime and time.time() - cached[1] < REUPLOAD_S:
                return cached[2]
            url = self._call(lambda: self.client.upload_file(path))
            self._refs[path] = (mtime, time.time(), url)
            return url

    def _draw(self, text: str, refs: list[Path], out: Path, size: tuple[int, int], aspect: str = "16:9") -> None:
        arguments = {"prompt": text, "image_urls": [self._upload(p) for p in refs], "aspect_ratio": aspect,
                     "resolution": self.resolution, "output_format": "png", "num_images": 1}
        with self._slots:
            result = self._call(lambda: self.client.subscribe(self.model, arguments=arguments,
                                                              client_timeout=WAIT_S))
        images = result.get("images") or []
        if not images:
            raise RuntimeError(f"fal.ai sent back no picture: {result.get('description') or 'no reason given'}")
        content = self._download(images[0]["url"])
        out.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(io.BytesIO(content)) as img:
            ImageOps.fit(img.convert("RGB"), size, Image.Resampling.LANCZOS).save(out)


class FalVideo(_Fal):
    def __init__(self, config, client=None, http: httpx2.Client | None = None) -> None:
        self.model, spec, self.seconds = clip_settings(config)
        super().__init__(config, client, http, int((config.fal.get("clips") or {}).get("concurrency", 4)))
        self.price_per_s = float(spec["price_per_s"])
        self.image_field = spec["image"]
        self.lengths = [int(s) for s in spec["seconds"]]
        self.arguments = dict(spec.get("arguments") or {})

    def price(self, seconds: float) -> float:
        return seconds * self.price_per_s

    def clip(self, channel, still: Path, prompt: str, out: Path, seconds: float, wearing: str = "") -> float:
        """`wearing` is what the people in it have on beyond their usual look (scenes.looks_json), so a brace
        stays on its leg while they move."""
        if seconds not in self.lengths:
            raise FinalError(f"{self.model} can't make a {seconds}-second clip; set fal.clips.seconds to one of "
                             f"{', '.join(map(str, self.lengths))}")
        text = prompts.fill(self.root, "clip.md", channel,
                            {"visual_prompt": prompt, "wearing": wearing or "nothing beyond their usual look"})
        image = self._call(lambda: self.client.upload_file(still))  # the scene's own still is the first frame
        arguments = {"prompt": text, self.image_field: image, "duration": str(int(seconds)), **self.arguments}
        with self._slots:
            result = self._call(lambda: self.client.subscribe(self.model, arguments=arguments,
                                                              client_timeout=CLIP_WAIT_S), refused="clip")
        url = (result.get("video") or {}).get("url")
        if not url:
            raise RuntimeError("fal.ai sent back no clip")
        out.parent.mkdir(parents=True, exist_ok=True)
        tmp = out.with_suffix(".part.mp4")
        tmp.write_bytes(self._download(url))
        try:
            playable = bool(re.search(r"Stream #.*Video:", ffmpeg.probe(tmp))) and ffmpeg.duration_ms(tmp) >= 1000
        except RuntimeError:  # no Duration line
            playable = False
        if not playable:
            tmp.unlink(missing_ok=True)
            raise RuntimeError("fal.ai's clip isn't a playable video")
        tmp.replace(out)
        return self.price(seconds)

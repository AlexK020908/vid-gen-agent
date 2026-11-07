"""Where things come from: looking for one, and fetching it into data/things/<id>/source/ with its license written down.

Only open licenses come through: CC0, or CC-BY with its credit kept for the video's description. Anything its maker tagged
"noai" is left alone, since an agent chooses and places it. Generating a model costs money, so it needs `spend`.
"""
from __future__ import annotations

import json
import os
import shutil
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw

from render import assets
from render.humgen import _unpack

SKETCHFAB = "https://api.sketchfab.com/v3"
POLYHAVEN_LIST = "https://api.polyhaven.com/assets?t=models"
OPEN = {"cc0": "CC0", "by": "CC-BY"}          # Sketchfab's license slugs, and what we call them
GENERATE = {"model": "fal-ai/hunyuan3d-v3/text-to-3d", "usd": 0.375}   # from its fal page, Nov 3, 2026
MODEL_FILES = (".glb", ".gltf", ".fbx", ".obj")


def _json(url: str, headers: dict | None = None) -> dict:
    with urllib.request.urlopen(urllib.request.Request(url, headers={**assets.AGENT, **(headers or {})}), timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _download(url: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    return assets._fetch(url, dest)


def _sketchfab_open(info: dict) -> tuple[str | None, str]:
    """The license we'd call it, or None with the reason we can't use it."""
    tags = {t.get("name", "").lower() for t in info.get("tags") or []}
    if "noai" in tags:
        return None, "its maker tagged it noai"
    slug = (info.get("license") or {}).get("slug")
    if slug not in OPEN:
        return None, f"its license is {(info.get('license') or {}).get('label')!r}, not CC0 or CC-BY"
    if not info.get("isDownloadable"):
        return None, "its maker doesn't allow downloads"
    return OPEN[slug], ""


def _from_sketchfab(source: dict, where: Path, say) -> dict:
    token = os.environ.get("SKETCHFAB_TOKEN")
    if not token:
        raise RuntimeError("Sketchfab downloads need SKETCHFAB_TOKEN in .env: a free account, then sketchfab.com/settings/password")
    uid = source["uid"]
    info = _json(f"{SKETCHFAB}/models/{uid}")
    license_name, reason = _sketchfab_open(info)
    if license_name is None:
        raise RuntimeError(f"{info.get('name')!r} can't be used: {reason}")
    links = _json(f"{SKETCHFAB}/models/{uid}/download", {"Authorization": f"Token {token}"})
    say(f"  from Sketchfab: {info['name']} by {info['user']['displayName']}, {license_name}")
    if links.get("gltf"):          # Sketchfab's glb has its textures cut down to 1024, whatever the model's own are
        archive = _download(links["gltf"]["url"], where / "model.zip")
        _unpack(archive, where / "unpacked")
        found = _model_in(where / "unpacked")
    else:
        found = _download(links["glb"]["url"], where / "model.glb")
    credit = ""
    if license_name == "CC-BY":
        credit = (f'"{info["name"]}" by {info["user"]["displayName"]} ({info["viewerUrl"]}), '
                  f"licensed under CC BY 4.0: {info['license']['url']}")
    return {"file": str(found), "license": license_name, "credit": credit, "page": info["viewerUrl"], "usd": 0}


def _model_in(folder: Path, member: str | None = None) -> Path:
    if member:
        found = folder / member
        if not found.exists():
            raise RuntimeError(f"no {member} in what was downloaded")
        return found
    for suffix in MODEL_FILES:
        found = sorted(folder.rglob(f"*{suffix}"))
        if found:
            return found[0]
    raise RuntimeError(f"no model in {folder}: expected one of {', '.join(MODEL_FILES)}")


def _from_url(source: dict, where: Path, say) -> dict:
    url = source["url"]
    name = Path(urllib.parse.urlparse(url).path).name or "download"
    say(f"  from {source['page']}, {source['license']}")
    request_name = urllib.parse.unquote(name)
    found = _download(url, where / request_name)
    if found.suffix.lower() == ".zip":
        _unpack(found, where / "unpacked")
        found = _model_in(where / "unpacked", source.get("member"))
    return {"file": str(found), "license": source["license"], "credit": source.get("credit", ""), "page": source["page"], "usd": 0}


def _from_polyhaven(source: dict, config, say) -> dict:
    say(f"  from Poly Haven: {source['asset']}, CC0")
    found = assets.model(config.data_dir, source["asset"], source.get("res", "2k"))
    return {"file": found, "license": "CC0", "credit": "", "page": f"https://polyhaven.com/a/{source['asset']}", "usd": 0}


def _generate(source: dict, where: Path, say, client=None) -> dict:
    if client is None:
        import fal_client
        key = os.environ.get("FAL_KEY")
        if not key:
            raise RuntimeError("generating a model needs FAL_KEY in .env")
        client = fal_client.SyncClient(key=key)
    say(f"  generating on fal, about ${GENERATE['usd']}: {source['prompt']}")
    result = client.subscribe(GENERATE["model"], arguments={"prompt": source["prompt"]})
    found = _download(result["model_glb"]["url"], where / "model.glb")
    return {"file": str(found), "license": "generated", "credit": "", "page": GENERATE["model"], "usd": GENERATE["usd"]}


def price(source: dict) -> float:
    return GENERATE["usd"] if source["kind"] == "generate" else 0.0


def fetch(config, source: dict, where: Path, spend: bool = False, say=print, client=None) -> dict:
    """The source's file, fetched if it hasn't been: {file, license, credit, page, usd}. Generating refuses without `spend`."""
    where = Path(where)
    if source["kind"] == "built":          # made in Blender from its parts: there's nothing to fetch, and it's ours
        return {"file": "", "license": "own", "credit": "", "page": "", "usd": 0, "source": source}
    record = where / "source.json"
    if record.exists():
        done = json.loads(record.read_text(encoding="utf-8"))
        if done.get("source") == source and Path(done["file"]).exists():
            return done
    if source["kind"] == "generate" and not spend:
        raise RuntimeError(f"generating this costs about ${GENERATE['usd']}, so it needs the owner's yes (--spend)")
    shutil.rmtree(where, ignore_errors=True)     # a model tried here before mustn't be taken for this one: same file names
    where.mkdir(parents=True, exist_ok=True)
    if source["kind"] == "sketchfab":
        got = _from_sketchfab(source, where, say)
    elif source["kind"] == "url":
        got = _from_url(source, where, say)
    elif source["kind"] == "polyhaven":
        got = _from_polyhaven(source, config, say)
    else:
        got = _generate(source, where, say, client)
    record.write_text(json.dumps({**got, "source": source}, indent=1), encoding="utf-8")
    return {**got, "source": source}


# --- looking for one ----------------------------------------------------------------------------------------------------

def _polyhaven_list(config) -> dict:
    cached = Path(config.data_dir) / "assets" / "polyhaven" / "models.json"
    if not cached.exists():
        cached.parent.mkdir(parents=True, exist_ok=True)
        cached.write_bytes(assets._get(POLYHAVEN_LIST))
    return json.loads(cached.read_text(encoding="utf-8"))


def _polyhaven_hits(config, words: list[str], count: int) -> list[dict]:
    found = []
    for asset, info in _polyhaven_list(config).items():
        text = " ".join([asset, info.get("name", ""), *info.get("tags", []), *info.get("categories", [])]).lower()
        if all(w in text for w in words):
            found.append({"title": info.get("name", asset), "source": {"kind": "polyhaven", "asset": asset}, "license": "CC0",
                          "moves": 0, "faces": info.get("polycount"), "thumb": info.get("thumbnail_url"),
                          "by": ", ".join(info.get("authors", {}))})
    return found[:count]


def _sketchfab_hits(words: list[str], count: int) -> list[dict]:
    found, seen = [], set()
    q = urllib.parse.quote(" ".join(words))
    for license_slug, extra in (("cc0", ""), ("by", "&animated=true"), ("by", "")):
        url = (f"{SKETCHFAB}/search?type=models&q={q}&downloadable=true&license={license_slug}&count={count}"
               f"&sort_by=-likeCount{extra}")
        for hit in _json(url).get("results", []):
            if hit["uid"] in seen or "noai" in {t.get("name", "").lower() for t in hit.get("tags") or []}:
                continue
            seen.add(hit["uid"])
            images = sorted(hit.get("thumbnails", {}).get("images", []), key=lambda i: abs(i.get("width", 0) - 512))
            found.append({"title": hit["name"], "source": {"kind": "sketchfab", "uid": hit["uid"]}, "license": OPEN[license_slug],
                          "moves": hit.get("animationCount") or 0, "faces": hit.get("faceCount"),
                          "thumb": images[0]["url"] if images else None, "by": hit.get("user", {}).get("displayName", "")})
    return found


def _thumb(url: str | None, size: tuple[int, int]) -> Image.Image:
    blank = Image.new("RGB", size, (60, 60, 60))
    if not url:
        return blank
    try:
        from io import BytesIO
        return Image.open(BytesIO(assets._get(url))).convert("RGB").resize(size)
    except (OSError, ValueError):
        return blank


def picture(hits: list[dict], path: Path, cell=(256, 180), columns=6) -> Path:
    """The hits as one numbered sheet, to choose from by looking."""
    w, h = cell
    rows = (len(hits) + columns - 1) // columns or 1
    sheet = Image.new("RGB", (w * columns, (h + 30) * rows), "white")
    draw = ImageDraw.Draw(sheet)
    for i, hit in enumerate(hits):
        x, y = (i % columns) * w, (i // columns) * (h + 30)
        sheet.paste(_thumb(hit.get("thumb"), cell), (x, y))
        draw.text((x + 3, y + h + 2), f"{i + 1}. {hit['title'][:34]}", fill="black")
        draw.text((x + 3, y + h + 15), f"{hit['license']}, {hit['moves']} moves, {hit.get('faces') or '?'} faces", fill="black")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(path)
    return path


def search(config, words: str, count: int = 12) -> dict:
    """What's out there, free sources first, with a sheet of pictures. Generating is always there as the last resort."""
    terms = words.lower().split()
    hits = _polyhaven_hits(config, terms, count) + _sketchfab_hits(terms, count)
    sheet = picture(hits, Path(config.data_dir) / "things" / "_search" / f"{'_'.join(terms)}.png")
    return {"hits": hits, "sheet": str(sheet), "generate_usd": GENERATE["usd"]}

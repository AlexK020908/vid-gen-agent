"""Free CC0 assets from Poly Haven (polyhaven.com), fetched once into data/assets/polyhaven/<id>/ and kept.

Blender reads them from there. The API is public, needs no key and is free for commercial use (polyhaven.com/our-api, read
Nov 3, 2026); Poly Haven asks for a User-Agent naming the app. CC0 needs no credit, so nothing is added to a video's
description for them. If this line ever serves other people, they have to be told the assets came from Poly Haven.
"""
from __future__ import annotations

import json
import urllib.request
from pathlib import Path

API = "https://api.polyhaven.com/files/{}"
AGENT = {"User-Agent": "stickfleet/0.1 (machine shorts)"}
MAPS = {"diff": "Diffuse", "rough": "Rough", "nor_gl": "nor_gl"}


def _get(url: str) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers=AGENT), timeout=120) as resp:
        return resp.read()


def _fetch(url: str, dest: Path) -> Path:
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_suffix(dest.suffix + ".part")
        tmp.write_bytes(_get(url))
        tmp.replace(dest)
    return dest


def _files(asset: str, folder: Path) -> dict:
    index = folder / "files.json"
    if not index.exists():
        folder.mkdir(parents=True, exist_ok=True)
        index.write_bytes(_get(API.format(asset)))
    return json.loads(index.read_text(encoding="utf-8"))


def hdri(data_dir: Path, asset: str, res: str = "2k") -> str:
    folder = Path(data_dir) / "assets" / "polyhaven" / asset
    url = _files(asset, folder)["hdri"][res]["hdr"]["url"]
    return str(_fetch(url, folder / Path(url).name))


def model(data_dir: Path, asset: str, res: str = "2k") -> str:
    """A model's glTF with its buffers and textures beside it, where it expects them. Returns the .gltf's path."""
    folder = Path(data_dir) / "assets" / "polyhaven" / asset
    entry = _files(asset, folder)["gltf"][res]["gltf"]
    for relative, item in entry["include"].items():
        _fetch(item["url"], folder / res / relative)
    return str(_fetch(entry["url"], folder / res / Path(entry["url"]).name))


BLENDERKIT = "https://www.blenderkit.com/api/v1"


def blenderkit(data_dir: Path, base_id: str, key: str | None = None) -> str:
    """A BlenderKit asset's .blend, fetched once into data/assets/blenderkit/<base id>/ and kept. Free assets are royalty-free (or
    CC0): commercial use with no credit owed, and BlenderKit gives them with no login (its GitHub page, read Nov 19, 2026). A paid
    asset would need an account key, sent only to BlenderKit; none is used now. Opened in Blender without -y, so a file's own scripts
    never run."""
    import uuid
    folder = Path(data_dir) / "assets" / "blenderkit" / base_id
    record = folder / "asset.json"
    if not record.exists():
        folder.mkdir(parents=True, exist_ok=True)
        found = json.loads(_get(f"{BLENDERKIT}/search/?query=asset_base_id:{base_id}"))["results"]
        if not found:
            raise RuntimeError(f"BlenderKit has no asset {base_id}")
        record.write_text(json.dumps(found[0], indent=1), encoding="utf-8")
    info = json.loads(record.read_text(encoding="utf-8"))
    if info.get("license") not in ("royalty_free", "cc_zero") or not info.get("isFree", True):
        raise RuntimeError(f"BlenderKit {base_id} is {info.get('license')}, free: {info.get('isFree')}: not taken")
    done = folder / f"{base_id}.blend"
    if done.exists():
        return str(done)
    blend = next(f for f in info["files"] if f.get("fileType") == "blend")
    ask = urllib.request.Request(f"{blend['downloadUrl']}?scene_uuid={uuid.uuid4()}",
                                 headers={**AGENT, **({"Authorization": f"Bearer {key}"} if key else {})})
    with urllib.request.urlopen(ask, timeout=120) as resp:
        signed = json.loads(resp.read())["filePath"]
    return str(_fetch(signed, done))


def texture(data_dir: Path, asset: str, res: str = "2k") -> dict[str, str]:
    """The colour, roughness and normal maps of one texture, as Blender's materials.ASSETS wants them."""
    folder = Path(data_dir) / "assets" / "polyhaven" / asset
    files = _files(asset, folder)
    out = {}
    for key, name in MAPS.items():
        url = files[name][res]["jpg"]["url"]
        out[key] = str(_fetch(url, folder / Path(url).name))
    return out

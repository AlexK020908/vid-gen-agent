"""Human Generator, the paid Blender add-on that makes people (CHARACTERS.md): where its files are, and unpacking them.

The owner downloads them into human_packs/ (gitignored: its license forbids sharing them):
  HumGen3D_V?_?.zip   the add-on
  *.hgpack            its content packs (zip files: the people, hair, outfits, poses, animations)

They're unpacked once, beside the downloads, into addon/ and content/. Blender's Install button isn't used: every
run is --factory-startup, so blender/humgen.py enables the add-on from there each time, and it never updates itself.
"""
from __future__ import annotations

import json
import os
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# kind -> (its folder in the content, the files that count, split by gender?), as the add-on's preview collections
KINDS = {
    "humans": ("models", ".json", True),
    "hair": (os.path.join("hair", "head"), ".json", True),
    "face_hair": (os.path.join("hair", "face_hair"), ".json", False),
    "outfit": ("outfits", ".blend", True),
    "footwear": ("footwear", ".blend", True),
    "pose": ("poses", ".blend", False),
    "animation": ("animations", ".json", False),
    "expression": (os.path.join("shapekeys", "expressions"), ".npz", False),
}


def folder(config) -> Path:
    return ROOT / config.blender.get("humgen", "human_packs")


def missing(config) -> str | None:
    """Why the add-on can't run here, or None if it can."""
    where = folder(config)
    if not list(where.glob("HumGen3D*.zip")) and not (where / "addon" / "HumGen3D" / "__init__.py").exists():
        return f"Human Generator's add-on (HumGen3D_V?_?.zip, from Superhive) isn't in {where}"
    if not list(where.glob("*.hgpack")) and not (where / "content" / "content_packs").is_dir():
        return f"Human Generator's content packs (the .hgpack files, from Superhive) aren't in {where}"
    return None


def _unpack(archive: Path, into: Path) -> None:
    with zipfile.ZipFile(archive) as z:
        names = [n for n in z.namelist() if not n.startswith("__MACOSX/")]   # a Mac's leftovers in the zips
        for name in names:
            if not (into / name).resolve().is_relative_to(into.resolve()):
                raise ValueError(f"{archive.name} would write outside its folder: {name}")
        z.extractall(into, members=names)


def install(config, say=print) -> dict:
    """Unpack whatever hasn't been yet, and return the folders Blender needs. A pack dropped in later is added; one
    already unpacked isn't touched again (several gigabytes)."""
    reason = missing(config)
    if reason:
        raise RuntimeError(reason)
    where = folder(config)
    addon, content = where / "addon", where / "content"
    done_file = where / "installed.json"
    done = json.loads(done_file.read_text(encoding="utf-8")) if done_file.exists() else {}
    for archive in sorted(where.glob("HumGen3D*.zip")) + sorted(where.glob("*.hgpack")):
        stamp = [archive.stat().st_size, int(archive.stat().st_mtime)]
        if done.get(archive.name) == stamp:
            continue
        say(f"unpacking {archive.name}")
        _unpack(archive, addon if archive.suffix == ".zip" else content)
        done[archive.name] = stamp
        done_file.write_text(json.dumps(done, indent=1), encoding="utf-8")
    if not (addon / "HumGen3D" / "__init__.py").exists():
        raise RuntimeError(f"the add-on's zip didn't unpack to {addon / 'HumGen3D'}")
    if not any((content / "content_packs" / n).exists() for n in ("Base_Humans.json", "Trial_Content.json")):
        raise RuntimeError(f"no base humans in {content}: the Base Humans .hgpack is needed")
    return {"addon": str(addon), "content": str(content)}


def options(config) -> dict:
    """What can be chosen, read from the content folder: kind -> paths relative to it, with this system's slashes,
    as the add-on wants them."""
    content = folder(config) / "content"
    found: dict = {}
    for kind, (sub, suffix, by_gender) in KINDS.items():
        top = content / sub
        for group in ("male", "female") if by_gender else (None,):
            base = top / group if group else top
            paths = sorted(str(p.relative_to(content)) for p in base.rglob(f"*{suffix}") if p.is_file())
            found.setdefault(kind, {} if by_gender else [])
            if group:
                found[kind][group] = paths
            else:
                found[kind] = paths
    found["keys"] = sorted({p.stem for p in (content / "livekeys").rglob("*.npz")})   # the face and body sliders
    return found

"""Body clips from the free packs the owner downloads into data/motion/ (CHARACTERS.md): unpacked once, and listed by
name. Both packs are CC0, on the same skeleton.
  KinemIQ_Free_Animations_CC0_FBX.zip            35 clips, each its own FBX, with a mannequin in a T-pose
  Universal Animation Library 2[Standard].zip    42 clips in one GLB (Quaternius), with a T-pose clip
"""
from __future__ import annotations

import shutil
from pathlib import Path

from render.humgen import _unpack

KINEMIQ = "KinemIQ_Free_Animations_CC0_FBX.zip"
QUATERNIUS = "Universal Animation Library 2[Standard].zip"
QUATERNIUS_CLIPS = (
    "Chest_Open", "ClimbUp_1m", "Consume", "Farm_Harvest", "Farm_PlantSeed", "Farm_Watering", "Hit_Knockback",
    "Idle_FoldArms_Loop", "Idle_Lantern_Loop", "Idle_No_Loop", "Idle_Rail_Call", "Idle_Rail_Loop", "Idle_Shield_Break",
    "Idle_Shield_Loop", "Idle_TalkingPhone_Loop", "LayToIdle", "Melee_Hook", "Melee_Hook_Rec", "NinjaJump_Idle_Loop",
    "NinjaJump_Land", "NinjaJump_Start", "OverhandThrow", "Shield_Dash", "Shield_OneShot", "Slide_Exit", "Slide_Loop",
    "Slide_Start", "Sword_Block", "Sword_Dash", "Sword_Heavy_Combo", "Sword_Regular_A", "Sword_Regular_A_Rec",
    "Sword_Regular_B", "Sword_Regular_B_Rec", "Sword_Regular_C", "Sword_Regular_Combo", "TreeChopping_Loop",
    "Walk_Carry_Loop", "Yes", "Zombie_Idle_Loop", "Zombie_Scratch", "Zombie_Walk_Fwd_Loop")


def folder(config) -> Path:
    return config.data_dir / "motion"


def missing(config) -> str | None:
    where = folder(config)
    if not (where / KINEMIQ).exists() and not (where / "kinemiq").is_dir():
        return f"KinemIQ's free clips ({KINEMIQ}, kinemiq.itch.io/free-game-animations) aren't in {where}"
    if not (where / QUATERNIUS).exists() and not (where / "quaternius").is_dir():
        return f"Quaternius's free clips ({QUATERNIUS}, quaternius.itch.io/universal-animation-library-2) aren't in {where}"
    return None


def install(config) -> Path:
    """Unpack what hasn't been. The GLB is copied to a plain name: Blender's importer refuses a path with brackets."""
    reason = missing(config)
    if reason:
        raise RuntimeError(reason)
    where = folder(config)
    if (where / KINEMIQ).exists() and not (where / "kinemiq" / "KinemIQ_Mannequin.fbx").exists():
        _unpack(where / KINEMIQ, where / "kinemiq")
    plain = where / "quaternius" / "UAL2_Standard.glb"
    if (where / QUATERNIUS).exists() and not plain.exists():
        _unpack(where / QUATERNIUS, where / "quaternius")
        found = next((where / "quaternius").rglob("UAL2_Standard.glb"))
        shutil.copy(found, plain)
    return where


def catalog(config) -> dict:
    """Clip name -> what blender/clips.py needs to read it."""
    where = install(config)
    found = {}
    mannequin = where / "kinemiq" / "KinemIQ_Mannequin.fbx"
    for path in sorted((where / "kinemiq" / "FBX").glob("*.fbx")):
        found[path.stem] = {"file": str(path), "action": None, "reference": {"file": str(mannequin), "action": None}}
    glb = str(where / "quaternius" / "UAL2_Standard.glb")
    for name in QUATERNIUS_CLIPS:
        found[name] = {"file": glb, "action": name, "reference": {"file": glb, "action": "A_TPose"}}
    return found

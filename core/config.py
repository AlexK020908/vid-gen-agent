"""Loads stickfleet.yaml and channels/*.yaml into typed config."""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from core.formats import FORMATS, STORY

ROOT = Path(__file__).resolve().parent.parent


@dataclass
class Channel:
    id: str
    name: str
    scenario_family: str
    character_ref: Path
    style_prompt: str
    voice_id: str
    gates: list[str]
    baseline_cadence_days: int
    budget_usd: float
    clips_per_video: int
    youtube: dict
    competitors: list[str]
    narrator: str = "third"   # "you": the narration talks to the viewer as the main character; "third": about them
    puppet: dict = field(default_factory=dict)  # part name -> what the parts sheet draws for it (puppet/parts.py)
    extras: dict = field(default_factory=dict)  # crowd kind ("the dead") -> {part name: what's drawn}, puppets
                                                # painted once per channel for the crowds scenes show
    path: Path | None = None  # the YAML it came from; Connect writes youtube.channel_id back into it
    format: str = STORY       # what it makes, and so which stages run for it (core/formats.py)
    voice_model: str = ""     # an ElevenLabs model for this channel's voice, in place of models.voice
    voice_speed: float = 0.0  # this channel's pace, in place of elevenlabs.speed
    max_seconds: int = 0      # competitors' videos longer than this don't count: 60 or so for a Shorts channel
    pauses_ms: list[int] = field(default_factory=list)  # a character short's silence after a line, after a question or new beat, and at the end

    @property
    def script_gate(self) -> bool:
        return "script" in self.gates


@dataclass
class Config:
    root: Path
    data_dir: Path
    mode: str
    providers: dict
    models: dict
    elevenlabs: dict
    fal: dict
    topics: dict
    engine: dict
    render: dict
    stub: dict
    youtube: dict
    channels: dict[str, Channel]
    blender: dict = field(default_factory=dict)  # where Blender is and how it renders machine shorts (SHORTS.md)

    def provider(self, kind: str) -> str:
        """Which provider runs `kind` (llm, tts, images, video). `mode: stub` makes every one a stub."""
        return "stub" if self.mode == "stub" else str(self.providers.get(kind, "stub"))

    @property
    def db_path(self) -> Path:
        return self.data_dir / "stickfleet.db"

    @property
    def media_dir(self) -> Path:
        return self.data_dir / "media"


def _merge(base: dict, extra: dict) -> dict:
    out = copy.deepcopy(base)
    for key, value in extra.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out


NARRATORS = {
    "you": ("Second person, present tense: the narration talks to the viewer as \"you\", and the viewer is the main "
            "character, who has no name (\"You wake to sirens. The tap is still running.\"). Everyone else is \"he\", "
            "\"she\" or their name."),
    "third": "Third person, present tense, about the main character by name.",
}


def _channel(root: Path, raw: dict, path: Path | None = None) -> Channel:
    return Channel(
        id=raw["id"],
        name=raw["name"],
        scenario_family=raw["scenario_family"],
        character_ref=root / raw.get("character_ref", ""),   # only painted pictures use these two
        style_prompt=raw.get("style_prompt", ""),
        voice_id=raw.get("voice_id", ""),
        gates=list(raw.get("gates") or ["outline", "render"]),
        baseline_cadence_days=int(raw.get("baseline_cadence_days", 7)),
        budget_usd=float(raw.get("budget_usd", 50)),
        clips_per_video=int(raw.get("clips_per_video", 8)),
        youtube=dict(raw.get("youtube") or {}),
        competitors=list(raw.get("competitors") or []),
        narrator=_narrator(raw.get("narrator", "third")),
        puppet={str(k): str(v) for k, v in (raw.get("puppet") or {}).items()},
        extras={str(kind).strip().lower(): {str(k): str(v) for k, v in (spec or {}).items()}
                for kind, spec in (raw.get("extras") or {}).items()},
        path=path,
        format=_format(raw.get("format", STORY)),
        voice_model=str(raw.get("voice_model") or ""),
        voice_speed=float(raw.get("voice_speed") or 0),
        max_seconds=int(raw.get("max_seconds") or 0),
        pauses_ms=_pauses(raw.get("pauses_ms")),
    )


def _pauses(value) -> list[int]:
    gaps = [int(v) for v in value or []]
    if gaps and len(gaps) != 3:
        raise ValueError(f"pauses_ms is three numbers, after a line, after a question or new beat, and at the end; not {value!r}")
    return gaps


def _format(value) -> str:
    value = str(value).strip().lower()
    if value not in FORMATS:
        raise ValueError(f"format must be one of {', '.join(FORMATS)}, not {value!r}")
    return value


def _narrator(value) -> str:
    value = str(value).strip().lower()
    if value not in NARRATORS:
        raise ValueError(f"narrator must be one of {', '.join(NARRATORS)}, not {value!r}")
    return value


def load(root: Path = ROOT, data_dir: Path | None = None, overrides: dict | None = None) -> Config:
    raw = yaml.safe_load((root / "stickfleet.yaml").read_text(encoding="utf-8")) or {}
    if overrides:
        raw = _merge(raw, overrides)
    channels = {}
    for path in sorted((root / "channels").glob("*.yaml")):
        channel = _channel(root, yaml.safe_load(path.read_text(encoding="utf-8")), path)
        channels[channel.id] = channel
    return Config(
        root=root,
        data_dir=Path(data_dir) if data_dir else root / raw.get("data_dir", "data"),
        mode=raw.get("mode", "stub"),
        providers=raw.get("providers") or {},
        models=raw.get("models") or {},
        elevenlabs=raw.get("elevenlabs") or {},
        fal=raw.get("fal") or {},
        topics=raw.get("topics") or {},
        engine=raw.get("engine") or {},
        render=raw.get("render") or {},
        stub=raw.get("stub") or {},
        youtube=raw.get("youtube") or {},
        channels=channels,
        blender=raw.get("blender") or {},
    )

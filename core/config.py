"""Loads stickfleet.yaml and channels/*.yaml into typed config."""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from pathlib import Path

import yaml

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
    path: Path | None = None  # the YAML it came from; Connect writes youtube.channel_id back into it

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
    claude: dict
    elevenlabs: dict
    fal: dict
    topics: dict
    engine: dict
    render: dict
    stub: dict
    agent: dict
    youtube: dict
    channels: dict[str, Channel]

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
        character_ref=root / raw["character_ref"],
        style_prompt=raw["style_prompt"],
        voice_id=raw.get("voice_id", ""),
        gates=list(raw.get("gates") or ["outline", "render"]),
        baseline_cadence_days=int(raw.get("baseline_cadence_days", 7)),
        budget_usd=float(raw.get("budget_usd", 50)),
        clips_per_video=int(raw.get("clips_per_video", 8)),
        youtube=dict(raw.get("youtube") or {}),
        competitors=list(raw.get("competitors") or []),
        narrator=_narrator(raw.get("narrator", "third")),
        puppet={str(k): str(v) for k, v in (raw.get("puppet") or {}).items()},
        path=path,
    )


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
        claude=raw.get("claude") or {},
        elevenlabs=raw.get("elevenlabs") or {},
        fal=raw.get("fal") or {},
        topics=raw.get("topics") or {},
        engine=raw.get("engine") or {},
        render=raw.get("render") or {},
        stub=raw.get("stub") or {},
        agent=raw.get("agent") or {},
        youtube=raw.get("youtube") or {},
        channels=channels,
    )

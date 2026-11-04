"""What a channel makes (`format:` in its YAML), and so which stages run for it (SHORTS.md, CHARACTERS.md).

  story      the narrated long videos: painted or puppet pictures, Ken Burns, chapters, thumbnails
  character  vertical shorts with 3D people: the agent directs each in the scene language (scenes/spec.py), and Blender
             films it

The stages all run in the same engine, and a stage only ever claims the videos of channels whose format it's for. The
machine and diagram formats come with their own stages, in phases 29 and 30.
"""
from __future__ import annotations

STORY, CHARACTER = "story", "character"
FORMATS = (STORY, CHARACTER)
STAGES = {
    STORY: ("topics", "outline", "script", "regen", "voice", "assets", "sheets", "animate", "stills", "clips", "thumbs",
            "assemble", "publish", "analytics"),
    CHARACTER: ("topics", "outline", "script", "voice", "thumbs", "direct", "film", "publish", "analytics"),
}
SHORT_SIZE = (1080, 1920)


def _runs(channel, stage: str) -> bool:
    return stage in STAGES[channel.format]


def condition(config, stage: str, column: str = "channel_id") -> str:
    """SQL keeping a stage to the channels it's for. Nothing at all when that's every channel, so a fleet of one format runs
    the same query it always did."""
    channels = list(config.channels.values())
    keep = [c.id for c in channels if _runs(c, stage)]
    if len(keep) == len(channels):
        return ""
    if not keep:
        return "AND 0"
    quoted = ", ".join("'" + c.replace("'", "''") + "'" for c in keep)
    return f"AND {column} IN ({quoted})"

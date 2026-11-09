"""What a channel makes (`format:` in its YAML), and so which stages run for it (SHORTS.md, CHARACTERS.md).

  story      the narrated long videos: painted or puppet pictures, Ken Burns, chapters, thumbnails
  character  vertical shorts with 3D people: the agent directs each in the scene language (scenes/spec.py), and Blender
             films it
  diagram    systems shorts: a tech concept as a live diagram on a dark frame, with no voice. The agent writes a spec
             (diagram/spec.py), code runs its traffic and Remotion draws it (SHORTS.md, "How a systems short is made")

The stages all run in the same engine, and a stage only ever claims the videos of channels whose format it's for.
"""
from __future__ import annotations

STORY, CHARACTER, DIAGRAM = "story", "character", "diagram"
FORMATS = (STORY, CHARACTER, DIAGRAM)
STAGES = {
    STORY: ("topics", "outline", "script", "regen", "voice", "assets", "sheets", "animate", "stills", "clips", "thumbs",
            "assemble", "publish", "analytics"),
    CHARACTER: ("topics", "outline", "script", "voice", "thumbs", "direct", "film", "publish", "analytics"),
    DIAGRAM: ("diagram", "draw", "publish", "analytics"),
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

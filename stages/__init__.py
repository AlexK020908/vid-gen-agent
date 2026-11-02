"""Pipeline stages. Each module exposes NAME and run_once(ctx) -> bool."""
from stages import (analytics, animate, assemble, assets, clips, outline, publish, regen, script, sheets, stills, thumbs,
                    topics, voice)

ALL = [topics, outline, script, regen, voice, assets, sheets, animate, stills, clips, thumbs, assemble, publish, analytics]
BY_NAME = {s.NAME: s for s in ALL}

"""Pipeline stages. Each module exposes NAME and run_once(ctx) -> bool."""
from stages import analytics, assemble, clips, outline, publish, regen, script, stills, thumbs, topics, voice

ALL = [topics, outline, script, regen, voice, stills, clips, thumbs, assemble, publish, analytics]
BY_NAME = {s.NAME: s for s in ALL}

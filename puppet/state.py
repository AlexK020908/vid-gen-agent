"""What a place looks like between scenes: the props placed in it and how. Every scene starts from the state
the scene before it left, and says only what it changes, so a plate stood across the stairs on Day 14 is still
there on Day 24 unless a scene takes it down.

A state is {place: {prop: placement}}; a placement is {"at": spot or [x, y], "angle": degrees, "offset": [dx, dy]
in H, "height": in H (the prop's own when left out)}. A scene's `set` is a list of changes:
    {"place": "plate", "at": "stairs_top"}                  put it there (replacing where it was)
    {"place": "plate", "at": "stairs_top", "angle": -15}    leaning
    {"remove": "plate"}                                      gone from this place
"""
from __future__ import annotations

import copy


def apply(state: dict, place: str, changes: list[dict]) -> dict:
    """The state after a scene in `place` made `changes`; the state given is left as it was."""
    state = copy.deepcopy(state)
    here = state.setdefault(place, {})
    for change in changes or []:
        if "remove" in change:
            here.pop(change["remove"], None)
        elif "place" in change:
            placement = {k: v for k, v in change.items() if k != "place"}
            if "at" not in placement:
                raise ValueError(f"placing {change['place']!r} needs `at`: a spot name or [x, y]")
            here[change["place"]] = placement
        else:
            raise ValueError(f"a set change is {{place: ..., at: ...}} or {{remove: ...}}, not {change!r}")
    return state


def placements(state: dict, place: str) -> dict:
    """The props standing in `place`: {prop: placement}."""
    return dict(state.get(place) or {})

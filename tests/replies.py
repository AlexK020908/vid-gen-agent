"""Replies in the shape Claude writes them (providers/claude.py's schemas), built to pass the pipeline's checks:
what the session answers in the tests (tests/test_writing.py), and what tests/test_checks.py checks."""

DAYS = list(range(1, 31))  # a beat a day, so every day is told


def outline_data(n: int = 9, heroes: int = 3, **changes) -> dict:
    """Rosa is in beats 2 and 3, so her thread ends in beat 3."""
    step = n // heroes
    hero = set(range(0, step * heroes, step))
    beats = [{"label": f"Day {DAYS[i]}", "title": f"Beat {i + 1}", "summary": f"What happens in beat {i + 1}.",
              "skill": f"skill number {i + 1}", "hero": i in hero, "cast": ["Rosa"] if i in (1, 2) else []}
             for i in range(n)]
    return {"hook": "A storm, a locked door, and nobody coming.",
            "backstory": "The river broke its banks in the night and took the power with it.",
            "cast": [{"name": "Rosa", "look": "a stick-figure girl in a yellow raincoat", "role": "a lost kid",
                      "thread": "He finds her on Day 2 and gets her to her mother on Day 3."}],
            "tracker": [{"item": "Water", "unit": "L", "start": 20}, {"item": "Food", "unit": "days", "start": 14}],
            "beats": beats, "ending": "He walks out.", **changes}


PLACES = [{"id": "flat", "name": "the flat", "look": "A small flat: a sofa on the left, a window at the back."},
          {"id": "street", "name": "the street", "look": "A flooded street of brick houses, a bus stop on the right."}]


def script_data(outline: dict, n: int = 54, words: int = 35) -> dict:
    """Beats alternate between the flat and the street, and each move is told in the line. Each beat's first scene
    carries the tracker, and the cast are named in every scene of the beats that list them."""
    beats = outline["beats"]
    per = [n // len(beats) + (1 if i < n % len(beats) else 0) for i in range(len(beats))]
    scenes = []
    for b, count in enumerate(per):
        place = PLACES[b % 2]["id"]
        cast = list(beats[b].get("cast") or [])
        for k in range(count):
            move = ("he heads out" if place == "street" else "back home") if scenes and scenes[-1]["place"] != place else ""
            line = (f"Scene {len(scenes) + 1} of beat {b + 1}. " + (f"{move.capitalize()}. " if move else "")
                    + "".join(f"{name} is here. " for name in cast) + " ".join(["word"] * words))
            tracker = [{"item": t["item"], "amount": t["start"] - b / 2} for t in outline.get("tracker") or []]
            scenes.append({"beat": b + 1, "label": beats[b]["label"], "place": place, "cast": cast,
                           "narration": " ".join(line.split()[:words]), "move": move,
                           "tracker": tracker if k == 0 else [], "set_change": "",
                           "looks": [{"who": "the stick figure", "now": "a rain poncho"}] if not scenes else [],
                           "shot": "close-up" if k == 2 else "medium",
                           "visual_prompt": f"the stick figure in beat {b + 1}, shot {k + 1}",
                           "motion": "clip" if k == 0 and beats[b]["hero"] else "kenburns"})
    return {"places": PLACES, "scenes": scenes}

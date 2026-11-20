"""render/film_parts.py: a film written straight in Blender is only rendered once its own check has measured what passes through what."""
from render import film_parts


def test_a_film_renders_only_once_its_check_has_measured_what_passes_through_what():
    """The owner caught a wrist through a microwave's side on Nov 15, 2026, in a film nothing had measured."""
    passed = ("ORDER same: 0\nCHECKED: what passes through what: 1287 frames, 2 moving, 14 solid, 0 problem(s)\n"
              "FILM CHECK DONE: no key out of order")
    assert film_parts.refused(passed, 0) is None
    assert "doesn't measure what passes through what" in film_parts.refused("FILM CHECK DONE: no key out of order", 0)
    failed = ("CHECKED: what passes through what: 1287 frames, 2 moving, 14 solid, 1 problem(s)\n"
              "  THROUGH: the sleeve goes 6.2 mm into the oven's keypad side at 37.80 s (through it from 37.60 s to 38.10 s, 16 frames)")
    assert "6.2 mm into the oven's keypad side" in film_parts.refused(failed, 1)


def test_the_line_the_renderer_looks_for_is_the_one_the_check_prints():
    from pathlib import Path
    said = (Path(__file__).resolve().parent.parent / "blender" / "film_bounds.py").read_text(encoding="utf-8")
    assert f'CHECKED = "{film_parts.CHECK_SAYS}"' in said

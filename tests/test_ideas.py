"""Finding ideas: leads from what's written down, and cards that can go to the owner (ideas/, prompts/character/ideas.md)."""
import json
from pathlib import Path

import pytest

from ideas import cards, leads

ROOT = Path(__file__).resolve().parent.parent


def _card(**changes) -> dict:
    card = {"topic": "Why no straw works past ten metres", "hook": "If you built a straw as tall as a house, nothing would come up it, however hard you sucked.",
            "people_think": "You suck the water up, so sucking harder lifts it higher.", "truth": "The air outside pushes the water up, and it can only push so far.",
            "steps": ["Sucking takes air out of the straw.", "The air outside pushes down on the water.", "That push only holds up ten metres of water."],
            "turn": "A redwood lifts water ten times higher than that.", "first_picture": "A man sucking on a straw three floors tall.", "inside": "A cut through the straw, with air as moving balls.",
            "needs": ["a person", "a straw"], "shape": "ladder", "source": "A physics textbook", "source_url": "https://example.org/straw", "terms": ["straw"]}
    return {**card, **changes}


def test_a_good_card_passes_and_that_says_nothing_about_how_good_it_is():
    assert cards.problems([_card()], ["Why Your Brain Freezes"]) == []


def test_a_card_the_reference_has_done_is_turned_away_singular_or_plural():
    assert any("the reference has done it" in p for p in cards.problems([_card()], ["The Longest Straws Ever Made"]))
    assert any("the reference has done it" in p for p in cards.problems([_card(terms=["straw", "tree"])], ["A Straw In A Tree"]))
    assert cards.problems([_card(terms=["straw", "tree"])], ["A Straw In A Cup"]) == []       # only what has all of them
    assert cards.problems([_card()], ["Strawberries Are Not Berries"]) == []                  # a whole word, not part of one


@pytest.mark.parametrize("change, said", [
    ({"people_think": ""}, "people_think"),
    ({"steps": ["Only one."]}, "steps"),
    ({"source_url": "a book I read"}, "a link"),
    ({"terms": []}, "terms"),
    ({"hook": "Why does a straw stop working?"}, "bare question"),
    ({"shape": "listicle"}, "shape"),
])
def test_what_a_card_is_missing_is_said_in_words(change, said):
    assert any(said in p for p in cards.problems([_card(**change)], []))


def test_the_same_idea_twice_is_turned_away():
    assert any("the same as" in p for p in cards.problems([_card(), _card(topic="Straws again", terms=["STRAW"])], []))


def test_without_the_reference_titles_nothing_can_be_called_new(tmp_path):
    with pytest.raises(FileNotFoundError, match="channel_titles"):
        cards.reference_titles(tmp_path)


def test_a_lead_keeps_its_section_and_leaves_out_the_references():
    html = ("<h2>Human body</h2><p>Hair and fingernails don't keep growing after death, whatever people say.<sup>[1]</sup></p><p>short</p>"
            "<h2>References</h2><li>Some long citation that isn't a lead at all, however long it is.</li>")
    found = leads.paragraphs("A page", html)
    assert [lead["section"] for lead in found] == ["Human body"]
    assert found[0]["text"].endswith("whatever people say.")


def test_a_table_row_is_a_lead_since_the_winners_since_2001_are_in_tables():
    html = "<h2>2015</h2><table><tr><th>Field</th></tr><tr><td>Physics</td><td>for testing the principle that nearly all mammals empty their bladders in about 21 seconds</td></tr></table>"
    found = leads.paragraphs("A page", html)
    assert found[0]["section"] == "2015"
    assert found[0]["text"].startswith("Physics | for testing")


def test_a_source_that_doesnt_answer_is_said_and_the_rest_carry_on(tmp_path, monkeypatch):
    monkeypatch.setattr(leads, "PAGES", ("Works", "Fails"))
    monkeypatch.setattr(leads, "ASKED", ("why do",))
    monkeypatch.setattr(leads, "WAIT_S", 0)

    def wikipedia(page):
        if page == "Fails":
            raise OSError("no answer")
        return [{"page": page, "section": "", "text": "x" * 50}]

    monkeypatch.setattr(leads, "_wikipedia", wikipedia)
    monkeypatch.setattr(leads, "_suggestions", lambda stem: [f"{stem} thing"])
    data = json.loads(leads.fetch(tmp_path, say=lambda _: None).read_text(encoding="utf-8"))
    assert len(data["written"]) == 1
    assert "why do a thing" in data["asked"]
    assert any("Fails" in line for line in data["failed"])


def test_the_brief_asks_for_what_the_study_found_and_gives_no_score():
    brief = (ROOT / "prompts" / "character" / "ideas.md").read_text(encoding="utf-8")
    assert "don't score or rank" in brief
    for field in ("people_think", "steps", "turn", "first_picture", "inside", "source_url", "terms"):
        assert field in brief

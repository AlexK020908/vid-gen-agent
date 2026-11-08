"""Finding ideas: leads from what's written down, the reference's shorts as evidence, a brief per category, the owner's answers in their words,
and cards that can go to the owner (ideas/, prompts/ideas/, .claude/agents/idea-*.md)."""
import json
import shutil
from pathlib import Path

import pytest

from ideas import briefs, cards, leads, reference, taste
from providers import checks

ROOT = Path(__file__).resolve().parent.parent
LIKE = "How Splinters Get Unstuck 😲"
EXPLAINERS = briefs.load(ROOT, "explainers")
INVENTIONS = briefs.load(ROOT, "inventions")


def _card(**changes) -> dict:
    card = {"topic": "Why no straw works past ten metres", "hook": "If you built a straw as tall as a house, nothing would come up it, however hard you sucked.",
            "people_think": "You suck the water up, so sucking harder lifts it higher.", "truth": "The air outside pushes the water up, and it can only push so far.",
            "steps": ["Sucking takes air out of the straw.", "The air outside pushes down on the water.", "That push only holds up ten metres of water."],
            "turn": "A redwood lifts water ten times higher than that.", "first_picture": "A man sucking on a straw three floors tall.", "inside": "A cut through the straw, with air as moving balls.",
            "ending": "The redwood, its water climbing past the tenth metre.",
            "needs": ["a person", "a straw"], "shape": "why_it_happens", "source": "A physics textbook", "source_url": "https://example.org/straw", "terms": ["straw"],
            "like": ["How Splinters Get Unstuck"]}
    return {**card, **changes}


def _machine(**changes) -> dict:
    card = {"topic": "You invent the pile driver", "hook": "This is a nail, and one tap puts it in. Now make it a hundred times bigger.",
            "first_picture": "A hand tapping a nail into a plank.", "everyday": "Tapping a nail in with a hammer.", "goal": "Get the giant nail into the ground.",
            "steps": ["Too heavy to swing, so drop a block: the ram.", "Too slow to lift, so explosives push it up.", "It lands crooked, so guide rods.",
                      "Explosives are deadly, so burn fuel: the injector."],
            "invention": "the diesel pile hammer", "seen_it": "on building sites", "cycle": "fall, press, inject, ignite, rise", "inside": "a cut through the cylinder",
            "ending": "The ram thumping the pile down: congratulations, you've built a diesel pile hammer.",
            "needs": ["a nail", "a pile", "a ram"], "shape": "you_invent", "source": "A maker's guide", "source_url": "https://example.org/pile",
            "terms": ["pile"], "like": [LIKE]}
    return {**card, **changes}


def _problems(card_list, titles=(), brief=EXPLAINERS, answered=()) -> list[str]:
    return cards.problems(card_list, [LIKE, *titles], brief, list(answered))


def _video(title, published, views, seconds=40, likes=None, comments=None) -> dict:
    return {"id": title, "title": title, "published": published, "seconds": seconds, "views": views,
            "likes": views // 10 if likes is None else likes, "comments": views // 100 if comments is None else comments}


# --- cards ---

def test_a_good_card_passes_and_that_says_nothing_about_how_good_it_is():
    assert _problems([_card()], ["Why Your Brain Freezes"]) == []
    assert _problems([_machine()], brief=INVENTIONS) == []


def test_a_card_the_reference_has_done_is_turned_away_singular_or_plural():
    assert any("the reference has done it" in p for p in _problems([_card()], ["The Longest Straws Ever Made"]))
    assert any("the reference has done it" in p for p in _problems([_card(terms=["straw", "tree"])], ["A Straw In A Tree"]))
    assert _problems([_card(terms=["straw", "tree"])], ["A Straw In A Cup"]) == []       # only what has all of them
    assert _problems([_card()], ["Strawberries Are Not Berries"]) == []                  # a whole word, not part of one


@pytest.mark.parametrize("change, said", [
    ({"people_think": ""}, "people_think"),
    ({"ending": ""}, "ending"),
    ({"steps": ["Only one."]}, "steps"),
    ({"source_url": "a book I read"}, "a link"),
    ({"terms": []}, "terms"),
    ({"like": []}, "like"),
    ({"hook": "Why does a straw stop working?", "shape": "true_story"}, "bare question"),
    ({"shape": "listicle"}, "shape"),
])
def test_what_a_card_is_missing_is_said_in_words(change, said):
    assert any(said in p for p in _problems([_card(**change)]))


def test_the_same_idea_twice_is_turned_away():
    assert any("the same as" in p for p in _problems([_card(), _card(topic="Straws again", terms=["STRAW"])]))


def test_a_category_asks_for_its_own_fields_and_counts():
    assert any("invention has to be there" in p for p in _problems([_machine(invention="")], brief=INVENTIONS))
    assert any("steps has 3; it needs a list of 4 to 7" in p for p in _problems([_machine(steps=["a", "b", "c"])], brief=INVENTIONS))
    assert any("people_think" in p for p in _problems([_machine()], brief=EXPLAINERS))      # an explainer's fields aren't an invention's


def test_a_shape_outside_its_category_is_refused():
    assert any("inventions ideas are built as" in p for p in _problems([_machine(shape="why_it_happens")], brief=INVENTIONS))


def test_like_has_to_be_one_of_his_titles_whatever_its_emoji():
    assert _problems([_card(like=["how splinters get unstuck ?"])]) == []           # as a terminal that can't print emoji shows it
    assert any("isn't one of his titles" in p for p in _problems([_card(like=["A Short He Never Made"])]))


def test_without_the_reference_titles_nothing_can_be_called_new(tmp_path):
    with pytest.raises(FileNotFoundError, match="channel_titles"):
        cards.reference_titles(tmp_path)


def test_a_category_names_its_own_file(tmp_path):
    assert cards.path_for(tmp_path, "inventions") == tmp_path / "ideas" / "inventions" / "cards.json"
    assert cards.path_for(tmp_path, None) == tmp_path / "ideas" / "cards.json"            # phase 42's
    assert cards.path_for(tmp_path, "some/file.json") == Path("some/file.json")


def test_a_file_that_passes_says_how_the_shorts_its_like_did(tmp_path):
    data_dir, root = tmp_path / "data", tmp_path / "root"
    shutil.copytree(ROOT / "prompts" / "ideas", root / "prompts" / "ideas")
    (data_dir / reference.REFERENCE).parent.mkdir(parents=True)
    videos = [_video(LIKE, "2024-03-05", 90), _video("Another", "2024-03-06", 10), _video("A Third", "2024-03-07", 30), _video("Newest", "2026-11-05", 5)]
    (data_dir / reference.REFERENCE).write_text(json.dumps({"videos": videos}), encoding="utf-8")
    path = data_dir / "ideas" / "inventions" / "cards.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"category": "inventions", "cards": [_machine()]}), encoding="utf-8")
    said = []
    assert cards.check_file(path, data_dir, root, say=said.append) == []
    assert "1 inventions cards passed" in said[0] and "not that they're good" in said[0]
    assert said[2] == f'   like "{LIKE}": 3.0x his median for 2024Q1, in its top tenth'
    with pytest.raises(FileNotFoundError, match="give a category"):
        cards.check_file(tmp_path / "none.json", data_dir, root)


# --- the reference's shorts, as evidence ---

def test_a_short_is_set_against_its_own_quarter_and_the_young_and_long_are_left_out():
    videos = [_video("a", "2024-01-10", 10), _video("b", "2024-02-10", 20), _video("c", "2024-03-10", 30),
              _video("d", "2026-07-10", 1), _video("e", "2026-08-10", 2), _video("f", "2026-09-10", 3),
              _video("long", "2024-02-11", 500, seconds=600), _video("young", "2026-11-01", 1), _video("newest", "2026-11-05", 1)]
    judged = {v["title"]: v for v in reference.shorts(videos)}
    assert set(judged) == {"a", "b", "c", "d", "e", "f"}
    assert judged["c"]["x_views"] == pytest.approx(1.5) and judged["f"]["x_views"] == pytest.approx(1.5)   # 30M in 2024 is 3M in 2026
    assert judged["c"]["quarter"] == "2024Q1" and judged["f"]["quarter"] == "2026Q3"
    assert judged["c"]["top"] and not judged["a"]["top"]


def test_kin_are_whole_words_plurals_or_the_start_of_a_word_best_first():
    videos = reference.shorts([_video("How Zippers Work", "2024-01-01", 10), _video("A Zip Line", "2024-01-02", 50),
                               _video("The Invention Of Glue", "2024-01-03", 30), _video("Inventors At Work", "2024-01-04", 20),
                               _video("newest", "2026-11-05", 1)])
    assert [v["title"] for v in reference.kin(videos, ["zipper", "invent*"])] == ["The Invention Of Glue", "Inventors At Work", "How Zippers Work"]


def test_a_share_of_a_few_shorts_comes_with_a_wide_interval():
    p, low, high = reference.share(3, 8)
    assert p == pytest.approx(0.375) and low < 0.2 and high > 0.6
    p, low, high = reference.share(30, 80)
    assert p == pytest.approx(0.375) and 0.28 < low < high < 0.47
    assert reference.share(0, 0) == (0.0, 0.0, 1.0)


def test_a_title_matches_whatever_its_emoji_and_punctuation():
    assert reference.plain("How Cheating Dice Work 🤔") == reference.plain("how cheating dice work ?") == "how cheating dice work"
    assert reference.plain("Japan’s Vending Machines") == reference.plain("Japan�s Vending Machines")


# --- briefs ---

def test_every_category_has_a_brief_with_its_words_fields_and_shapes():
    assert {"inventions", "explainers", "mysteries", "crimes"} <= set(briefs.names(ROOT))
    for name in briefs.names(ROOT):
        brief = briefs.load(ROOT, name)
        assert brief.words and brief.fields and set(brief.shapes) <= set(checks.SHORT_SHAPES)
        assert "## The card" in brief.text


def test_a_brief_that_cant_be_used_is_refused_in_words(tmp_path):
    folder = tmp_path / briefs.FOLDER
    folder.mkdir(parents=True)
    (folder / "odd.md").write_text("---\nwords: []\nfields: [goal]\nlists: {steps: [4, 7]}\nshapes: [listicle]\n---\n# Odd", encoding="utf-8")
    (folder / "bare.md").write_text("# No YAML", encoding="utf-8")
    with pytest.raises(briefs.BriefError) as e:
        briefs.load(tmp_path, "odd")
    assert "needs words" in str(e.value) and "isn't one of its fields" in str(e.value) and "isn't an outline shape" in str(e.value)
    with pytest.raises(briefs.BriefError, match="no YAML block"):
        briefs.load(tmp_path, "bare")
    with pytest.raises(briefs.BriefError, match="the categories are"):
        briefs.load(ROOT, briefs.ALL)                     # what every idea needs isn't a category


def test_the_briefs_hold_what_the_study_found_and_give_no_score():
    every = (ROOT / "prompts" / "ideas" / "all.md").read_text(encoding="utf-8")
    assert "don't score or rank ideas" in every and "star references" in every
    for field in ("first_picture", "source_url", "terms", "like"):
        assert field in every
    for field in EXPLAINERS.fields:
        assert f"`{field}`" in EXPLAINERS.text
    assert "solves the problem the first second opens with" in INVENTIONS.text


def test_a_real_case_has_the_rules_about_real_people():
    mysteries, crimes = briefs.load(ROOT, "mysteries"), briefs.load(ROOT, "crimes")
    for text in (mysteries.text, crimes.text):
        assert "never a real person's likeness" in text and "No method someone could copy" in text and "Nothing graphic" in text
    assert "unless a court found them guilty" in mysteries.text and "guilty who wasn't convicted" in crimes.text
    assert "convicted" in crimes.fields and "solved" in mysteries.fields


# --- the owner's taste ---

def test_an_idea_the_owner_turned_down_is_refused_with_their_last_word():
    answered = [{"date": "2026-11-08", "verdict": "turned_down", "idea": "The straw", "terms": ["straw"],
                 "their_words": ["how does the pump pump water?", "i dont think its a good idea"]}]
    said = " ".join(_problems([_card(terms=["straw", "tree"])], answered=answered))
    assert "the owner turned down 'The straw' on 2026-11-08" in said and '"i dont think its a good idea"' in said
    assert "how does the pump" not in said
    assert _problems([_card(terms=["redwood"])], answered=answered) == []


def test_an_idea_only_offered_isnt_refused_but_one_liked_as_made_is():
    offered = [{"verdict": "offered", "idea": "Toast", "terms": ["toast"], "their_words": ["any"]}]
    assert _problems([_card(terms=["toast"])], answered=offered) == []
    liked = [{"verdict": "liked", "idea": "The woodpecker", "terms": ["woodpecker"], "date": "2026-11-08"}]
    assert any("liked 'The woodpecker' as made" in p for p in _problems([_card(terms=["woodpeckers", "tongue"])], answered=liked))


def test_one_subject_is_one_terms_words_inside_the_others():
    assert taste.same(["steam engine"], ["engine"])
    assert taste.same(["Straws"], ["straw", "tree"])
    assert not taste.same(["steam engine"], ["steam locomotive"])
    assert not taste.same([], ["straw"])


def test_a_verdict_keeps_the_whole_card_and_their_words_dated(tmp_path):
    path = tmp_path / "cards.json"
    path.write_text(json.dumps({"category": "inventions", "cards": [_machine()]}), encoding="utf-8")
    entry = taste.verdict(tmp_path, path, 1, "turned_down", "nah, boring", reading="the ending's a still thing")
    data = taste.load(tmp_path)
    assert data["entries"] == [entry] and data["about"] == taste.ABOUT
    assert entry["their_words"] == ["nah, boring"] and entry["reading"] == "the ending's a still thing"
    assert entry["category"] == "inventions" and entry["card"]["invention"] == "the diesel pile hammer" and entry["date"]
    with pytest.raises(ValueError, match="no card 2"):
        taste.verdict(tmp_path, path, 2, "took")
    with pytest.raises(ValueError, match="a verdict is one of"):
        taste.verdict(tmp_path, path, 1, "maybe")


def test_the_owners_taste_has_their_words_and_marks_every_reading_as_ours():
    data = taste.load(ROOT / "ideas")
    assert data["said"] and data["entries"]
    for e in data["entries"]:
        assert e["verdict"] in taste.VERDICTS and e["idea"] and e["terms"]
        if e["verdict"] in ("turned_down", "took"):
            assert e["their_words"], e["idea"]
    shown = []
    taste.show(ROOT / "ideas", say=shown.append)
    assert "## What the owner has said about ideas" in shown and any(line.startswith("  our reading, not theirs:") for line in shown)


# --- the agents ---

def test_the_researcher_runs_the_checks_and_never_picks_or_scores():
    text = (ROOT / ".claude" / "agents" / "idea-researcher.md").read_text(encoding="utf-8")
    for command in ("run.py ideas taste", "run.py ideas reference", "run.py ideas check"):
        assert command in text
    assert "Don't score or rank" in text and "never picks an idea" in text
    checker = (ROOT / ".claude" / "agents" / "idea-checker.md").read_text(encoding="utf-8")
    tools = next(line for line in checker.splitlines() if line.startswith("tools:"))
    assert "WebSearch" in tools and "Write" not in tools and "Edit" not in tools    # it reads and says; whoever wrote the cards fixes them
    assert '"keep" | "fix" | "drop"' in checker


# --- leads (phase 42) ---

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

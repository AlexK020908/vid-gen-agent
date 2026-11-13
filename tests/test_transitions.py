"""The check of the joins (core/transitions.py, render/cut_sheets.py, prompts/transitions.md): the owner asked for someone
whose only job is where each line gives way to the next and each shot to the next, after catching a bad join themselves."""
import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

from PIL import Image

from core import config, transitions
from core.errors import FinalError
from providers import checks, prompts
from providers.claude import JOIN_VALUES
from providers.llm import NoMeter, StubLLM
from render import cut_sheets, ffmpeg

CFG = config.load()
SHORTS = replace(CFG.channels["zombie"], id="shorts", name="Small Facts", format="character", path=None)
LINES = [{"from": 0.0, "to": 0.9, "text": "A red thing.", "words": [{"word": "A", "t": 0.1}, {"word": "red", "t": 0.3}, {"word": "thing.", "t": 0.6}]},
         {"from": 1.2, "to": 2.6, "text": "So it went green, then blue.",
          "words": [{"word": "So", "t": 1.2}, {"word": "it", "t": 1.4}, {"word": "went", "t": 1.6}, {"word": "green,", "t": 1.8},
                    {"word": "then", "t": 2.1}, {"word": "blue.", "t": 2.3}]}]


def _three_shots(path: Path) -> Path:
    """A second of red, a second of green and a second of blue: two cuts, at 1 s and 2 s."""
    ffmpeg.run(["-f", "lavfi", "-i", "color=c=red:size=108x192:rate=30:duration=1", "-f", "lavfi", "-i", "color=c=green:size=108x192:rate=30:duration=1",
                "-f", "lavfi", "-i", "color=c=blue:size=108x192:rate=30:duration=1", "-filter_complex", "[0][1][2]concat=n=3:v=1",
                "-pix_fmt", "yuv420p", path])
    return path


def _hue(sheet: Image.Image, x: int, y: int) -> str:
    r, g, b = sheet.getpixel((x, y))[:3]
    return max((("red", r), ("green", g), ("blue", b)), key=lambda p: p[1])[0]


def test_each_cut_is_laid_out_with_the_end_of_one_shot_and_the_start_of_the_next(tmp_path):
    video = _three_shots(tmp_path / "short.mp4")
    laid = cut_sheets.sheets(video, [1.0, 2.0], tmp_path / "cuts", LINES)
    assert [c["t"] for c in laid["cuts"]] == [1.0, 2.0] and not laid["measured"]
    assert len(laid["sheets"]) == 1 and laid["sheets"][0]["cuts"] == [1, 2]
    sheet = Image.open(laid["sheets"][0]["file"]).convert("RGB")
    w, h = cut_sheets.CELL
    y = cut_sheets.HEAD + cut_sheets.BAND + h // 2
    first = [_hue(sheet, j * w + w // 2, y) for j in range(4)]                         # cut 1, on the left of the top row
    second = [_hue(sheet, 4 * w + cut_sheets.GAP + j * w + w // 2, y) for j in range(4)]
    assert first == ["red", "red", "green", "green"] and second == ["green", "green", "blue", "blue"]
    assert not list((tmp_path / "cuts").glob("c_*.png"))                                # the loose frames don't stay


def test_what_is_said_as_a_cut_comes_goes_with_it():
    assert cut_sheets.said_around(1.0, LINES) == '"A red thing. [cut] So it went green, then blue." (between two lines)'
    assert cut_sheets.said_around(2.0, LINES) == '"A red thing. So it went green, [cut] then blue."'
    assert cut_sheets.said_around(4.0, LINES) == '"then blue. [cut]" (between two lines)'
    assert cut_sheets.said_around(6.0, LINES) == "(nothing's said)"


def test_cuts_are_measured_from_the_picture_when_nothing_planned_them(tmp_path):
    video = _three_shots(tmp_path / "short.mp4")
    assert cut_sheets.found(video) == [1.0, 2.0]
    assert cut_sheets.sheets(video, None, tmp_path / "cuts", LINES)["measured"]


def test_a_planned_cut_goes_where_the_picture_really_changes(tmp_path):
    """A shot's first frame can land a frame either side of its start time, which would put both frames of a cut in
    one shot."""
    video = _three_shots(tmp_path / "short.mp4")
    laid = cut_sheets.sheets(video, [1.04, 1.96], tmp_path / "cuts", LINES)
    assert [c["t"] for c in laid["cuts"]] == [1.0, 2.0]
    assert cut_sheets.planned({"scenes": [{"shots": [{"t": 0}, {"t": 1.04}]}, {"shots": [{"t": 1.96}]}]}) == [1.04, 1.96]


def test_a_shorts_clock_and_whisper_both_give_what_is_said(tmp_path):
    clock = tmp_path / "clock.json"
    clock.write_text(json.dumps({"lines": [{"from": 0, "to": 1, "text": "Hi.", "shows": "a wave", "words": [{"word": "Hi.", "t": 0.1, "to": 0.4}]}], "total": 1}))
    whisper = tmp_path / "words.json"
    whisper.write_text(json.dumps([{"start": 0, "end": 1, "text": "Hi.", "words": [{"w": "Hi.", "s": 0.1, "e": 0.4}]}]))
    assert cut_sheets.lines_from(clock) == [{"from": 0.0, "to": 1.0, "text": "Hi.", "words": [{"word": "Hi.", "t": 0.1}], "shows": "a wave"}]
    assert cut_sheets.lines_from(whisper) == [{"from": 0.0, "to": 1.0, "text": "Hi.", "words": [{"word": "Hi.", "t": 0.1}]}]
    assert "Shows: a wave" in cut_sheets.script_text(cut_sheets.lines_from(clock))


def test_both_turns_of_the_check_fill_for_any_channel():
    for channel in (SHORTS, CFG.channels["zombie"]):
        for turn in ("script", "film"):
            system, user = prompts.render(CFG.root, "transitions.md", turn, channel, dict(JOIN_VALUES))
            assert "joins" in system and user


def test_a_bad_join_needs_its_place_its_kind_and_a_fix():
    good = {"at": "line 6 to 7", "in": "words", "what": "the sponge comes from nowhere", "fix": "say what the sponge stands in for", "serious": True}
    assert checks.joins({"seen": "14 joins", "problems": [good]}) == []
    assert "needs `in`" in " ".join(checks.joins({"problems": [{**good, "in": "both"}]}))
    assert "too thin" in " ".join(checks.joins({"problems": [{**good, "fix": "fix it"}]}))
    assert "no `at`" in " ".join(checks.joins({"problems": [{**good, "at": ""}]}))
    assert "keep the worst" in " ".join(checks.joins({"problems": [good] * (checks.JOINS_MOST + 1)}))


class _Fleet:
    """Just what core/transitions.py uses of a context."""

    def __init__(self, on: bool = True) -> None:
        self.config = SimpleNamespace(models={"transitions": "on" if on else "off"})
        self.llm = StubLLM()
        self.said: list[str] = []
        self.events = SimpleNamespace(emit=lambda kind, video_id=None, **kw: self.said.append(kw.get("text", "")))

    def meter(self, conn, video, stage, what):
        return NoMeter()


SCRIPT = {"places": [], "scenes": [{"narration": "Its head stops dead.", "visual_prompt": "a bird hits a tree"},
                                   {"narration": "Like a nail with a sponge.", "visual_prompt": "a sponge hammer"}]}
OUTLINE = {"hook": "h", "beats": [], "ending": "e"}
BAD = {"at": "line 1 to 2", "in": "words", "what": "The sponge comes from nowhere.", "fix": "Say first that a soft head would soak up the hit.", "serious": True}


def test_a_bad_join_in_a_script_sends_it_back_to_the_writer_once():
    fleet, asked = _Fleet(), []
    fleet.llm.join_problems = [BAD, {**BAD, "at": "line 2 to 3", "serious": False}]
    revised = transitions.checked_script(fleet, None, {"id": 1}, SHORTS, OUTLINE, SCRIPT, lambda notes, draft: asked.append(notes) or {"scenes": []})
    assert revised == {"scenes": []}
    assert asked == [["Joins, line 1 to 2: The sponge comes from nowhere. Fix: Say first that a soft head would soak up the hit."]]
    assert "rewritten to fix them" in fleet.said[0] and "blemishes it left alone" in fleet.said[0]


def test_a_rewritten_script_is_read_again_and_a_join_the_fix_broke_goes_back_too():
    fleet, asked = _Fleet(), []
    second = {**BAD, "at": "line 2 to 3", "what": "The fix left the hammer unexplained."}
    rounds = [[BAD], [second], []]
    fleet.llm.check_joins = lambda channel, turn, values, meter: {"seen": "1 join", "problems": rounds.pop(0)}
    better = {"places": [], "scenes": SCRIPT["scenes"] + [{"narration": "So it stays hard.", "visual_prompt": "a hard beak"}]}

    def rewrite(notes, draft):
        asked.append((notes, draft))
        return better

    assert transitions.checked_script(fleet, None, {"id": 1}, SHORTS, OUTLINE, SCRIPT, rewrite) is better
    assert [draft for _, draft in asked] == [SCRIPT, better]                 # the second rewrite starts from the first one's draft
    assert "The fix left the hammer unexplained." in asked[1][0][0]
    assert "2 joins" in fleet.said[0] and rounds == []


def test_joins_still_bad_after_the_last_rewrite_go_to_the_owner():
    fleet = _Fleet()
    fleet.llm.check_joins = lambda channel, turn, values, meter: {"seen": "1 join", "problems": [BAD]}
    better = {"places": [], "scenes": SCRIPT["scenes"]}
    assert transitions.checked_script(fleet, None, {"id": 1}, SHORTS, OUTLINE, SCRIPT, lambda notes, draft: better) is better
    assert f"after {transitions.ROUNDS} rewrites" in fleet.said[0]


def test_good_joins_or_only_blemishes_leave_the_script_as_it_was():
    fleet = _Fleet()
    assert transitions.checked_script(fleet, None, {"id": 1}, SHORTS, OUTLINE, SCRIPT, lambda notes, draft: 1 / 0) is SCRIPT
    fleet.llm.join_problems = [{**BAD, "serious": False}]
    assert transitions.checked_script(fleet, None, {"id": 1}, SHORTS, OUTLINE, SCRIPT, lambda notes, draft: 1 / 0) is SCRIPT
    assert "passed the script" in fleet.said[0]
    off = _Fleet(on=False)
    off.llm.join_problems = [BAD]
    assert transitions.checked_script(off, None, {"id": 1}, SHORTS, OUTLINE, SCRIPT, lambda notes, draft: 1 / 0) is SCRIPT
    one = {"places": [], "scenes": SCRIPT["scenes"][:1]}                                  # one line has no joins to judge
    fleet.llm.join_problems = [BAD]
    assert transitions.checked_script(fleet, None, {"id": 1}, SHORTS, OUTLINE, one, lambda notes, draft: 1 / 0) is one
    assert fleet.llm.join_problems == [BAD]                                                # and nobody was asked


def test_a_rewrite_that_fails_its_checks_keeps_the_draft_and_tells_the_owner():
    fleet = _Fleet()
    fleet.llm.join_problems = [BAD]

    def fails(notes, draft):
        raise FinalError("a line is too long")

    assert transitions.checked_script(fleet, None, {"id": 1}, SHORTS, OUTLINE, SCRIPT, fails) is SCRIPT
    assert "as a note to fix them" in fleet.said[0]


def test_a_finished_shorts_picture_joins_go_back_and_its_word_joins_go_to_the_owner(tmp_path):
    video = _three_shots(tmp_path / "short.mp4")
    fleet = _Fleet()
    picture = {**BAD, "at": "cut 1 at 1.0 s", "in": "picture", "what": "The green thing comes from nowhere.", "fix": "Show the red thing turning green first."}
    fleet.llm.join_problems = [BAD, picture]
    direction = {"scenes": [{"shots": [{"t": 0}, {"t": 1.0}, {"t": 2.0}]}]}
    sent = transitions.check_film(fleet, None, {"id": 1}, SHORTS, video, direction, LINES)
    assert sent == [picture]
    assert "paying for its voice again" in fleet.said[0] and "line 1 to 2" in fleet.said[0]
    assert len(list((tmp_path / "cuts_review").glob("cuts_*.png"))) == 1
    fleet.llm.join_problems = [picture]
    assert transitions.check_film(fleet, None, {"id": 1}, SHORTS, video, {"scenes": [{"shots": [{"t": 0}]}]}, LINES) == []
    assert fleet.llm.join_problems == [picture]                                            # one shot: nobody was asked


def test_the_stages_ask_for_the_check_after_the_reviewers():
    script = Path("stages/script.py").read_text(encoding="utf-8")
    assert script.index("review.reviewed(") < script.index("transitions.checked_script(")
    film = Path("stages/film.py").read_text(encoding="utf-8")
    assert film.index("_review(ctx, conn, video, channel, out, direction, clock)") < film.index("transitions.check_film(")
    assert transitions.enabled(SimpleNamespace(config=CFG))                              # on in stickfleet.yaml

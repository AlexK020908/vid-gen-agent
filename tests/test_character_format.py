"""Phases 28 and 36 (CHARACTERS.md, SHORTS.md): a `format` per channel, and the agent directing a short from a topic, with the
story channel beside it unchanged. The writing, voice and pictures are stubs; Remotion is real. $0."""
import json
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest
from PIL import Image

from core import actions, config, db, formats, metadata
from core.context import make_ctx
from core.engine import Engine
from providers import checks, prompts
from providers.claude import ClaudeLLM
from providers.elevenlabs import ElevenLabsTTS
from providers.llm import NoMeter
from render import ffmpeg, remotion_render
from scenes import direction as short
from stages import direct, film
from things import get
from things import spec as thing_spec
from youtube import client, competitors

CFG = config.load()
needs_remotion = pytest.mark.skipif(remotion_render.missing() is not None, reason="Remotion isn't installed")


def _channels(*pairs):
    return SimpleNamespace(channels={cid: SimpleNamespace(id=cid, format=fmt) for cid, fmt in pairs})


def test_a_stage_only_claims_the_channels_its_for():
    story = _channels(("zombie", "story"))
    assert formats.condition(story, "stills") == ""         # one format: the same query it always ran
    assert formats.condition(story, "film") == "AND 0"
    both = _channels(("zombie", "story"), ("shorts", "character"))
    assert formats.condition(both, "stills") == "AND channel_id IN ('zombie')"
    assert formats.condition(both, "film", "v.channel_id") == "AND v.channel_id IN ('shorts')"
    assert formats.condition(both, "voice") == ""


def test_every_stage_belongs_to_a_format():
    from stages import ALL
    named = {s for stages in formats.STAGES.values() for s in stages}
    assert {s.NAME for s in ALL} == named


def test_a_channel_says_its_format_and_a_wrong_one_is_refused():
    assert CFG.channels["zombie"].format == "story"
    made = config._channel(CFG.root, {"id": "x", "name": "X", "scenario_family": "", "character_ref": "c.png", "style_prompt": "",
                                      "format": "Character", "voice_model": "eleven_v4", "max_seconds": 60})
    assert (made.format, made.voice_model, made.max_seconds) == ("character", "eleven_v4", 60)
    with pytest.raises(ValueError, match="format must be one of story, character"):
        config._channel(CFG.root, {"id": "x", "name": "X", "scenario_family": "", "character_ref": "c.png", "style_prompt": "",
                                   "format": "mime"})


def test_a_channels_own_voice_model_is_used(tmp_path, monkeypatch):
    tts = ElevenLabsTTS(CFG)
    sent = []

    def fake_call(method, url, **kwargs):
        if "json" not in kwargs:           # asking for the voice's own settings
            return {}
        sent.append(kwargs["json"])
        return {"audio_base64": ""}

    monkeypatch.setattr(tts, "_call", fake_call)
    monkeypatch.setattr(ffmpeg, "duration_ms", lambda path: 1000)
    channel = SimpleNamespace(id="x", voice_id="abc", voice_model="eleven_v4")
    tts.speak(channel, "Hello.", tmp_path / "a.mp3")
    tts.speak(SimpleNamespace(id="y", voice_id="abc", voice_model=""), "Hello.", tmp_path / "b.mp3")
    assert sent[0]["model_id"] == "eleven_v4" and sent[1]["model_id"] == tts.model


def test_a_shorts_channel_keeps_shorts_and_a_long_channel_keeps_long_videos(monkeypatch):
    def fake_run(ctx, name, request):
        if name == "channels.list":
            return {"items": [{"id": "UC1", "snippet": {"title": "C"}, "contentDetails": {"relatedPlaylists": {"uploads": "U"}}}]}
        if name == "playlistItems.list":
            return {"items": [{"contentDetails": {"videoId": v, "videoPublishedAt": "2099-01-01T00:00:00Z"}} for v in ("short", "long")]}
        return {"items": [{"id": v, "snippet": {"title": v, "publishedAt": "2099-01-01T00:00:00Z"}, "statistics": {"viewCount": "5"},
                           "contentDetails": {"duration": d}} for v, d in (("short", "PT45S"), ("long", "PT12M"))]}

    monkeypatch.setattr(client, "public_service", lambda ctx: mock.MagicMock())
    monkeypatch.setattr(client, "run", fake_run)
    assert [v["youtube_id"] for v in competitors.fetch(None, ["UC1"], 90, 480)[0]] == ["long"]
    assert [v["youtube_id"] for v in competitors.fetch(None, ["UC1"], 90, 0, 60)[0]] == ["short"]


def test_several_slots_a_week_never_land_two_on_one_time():
    now = datetime(2026, 11, 2, 12, tzinfo=timezone.utc)     # a Monday
    slots = ["Tue 15:00 UTC", "Thu 15:00 UTC"]
    first = metadata.free_slot(slots, [], now)
    second = metadata.free_slot(slots, [first], now)
    third = metadata.free_slot(slots, [first, second], now)
    assert [datetime.fromtimestamp(t, timezone.utc).day for t in (first, second, third)] == [3, 5, 10]


def test_a_shorts_description_has_its_credits_and_no_chapters_heading():
    text = metadata.description({"hook": "h"}, [], True, blurb="What it shows.", credits=['"Gull" by Maker'])
    assert "Chapters" not in text and '"Gull" by Maker' in text and metadata.DISCLOSURE in text
    assert "Chapters" in metadata.description({"hook": "h"}, [{"t_ms": 0, "title": "One"}], False)


# --- the short's clock ---------------------------------------------------------------------------------------------------

LINES = short.lines([{"idx": 1, "narration": "A bird, up high.", "shows": "a gull", "duration_ms": 2000,
                      "words": [{"word": "A", "start_ms": 0, "end_ms": 200}, {"word": "bird,", "start_ms": 200, "end_ms": 700},
                                {"word": "up", "start_ms": 900, "end_ms": 1100}, {"word": "high.", "start_ms": 1100, "end_ms": 1900}]},
                     {"idx": 2, "narration": "It dives.", "duration_ms": 1000,
                      "words": [{"word": "It", "start_ms": 0, "end_ms": 300}, {"word": "dives.", "start_ms": 300, "end_ms": 900}]}],
                    [500, 500])
PERSON = {"type": "person", "character": "walt", "at": [0, 0], "stance": "Idle_relaxed"}


def _scene(begin, end, **more):
    return {"from": begin, "to": end, "set": "sky_set", "cast": {"walt": PERSON}, "happens": [],
            "shots": [{"t": begin, "on": "walt:eyes", "frame": 0.6}], **more}


def test_the_voice_sets_the_clock():
    assert LINES["total"] == 4.0
    assert LINES["lines"][1]["from"] == 2.5 and LINES["lines"][1]["words"][1]["t"] == 2.8


def test_captions_come_from_the_voice_a_few_words_at_a_time():
    said = short.captions(LINES)
    assert [c["text"] for c in said] == ["A bird,", "up high.", "It dives."]   # broken after the comma
    assert said[0]["from"] == 0 and said[1]["from"] == 0.9
    assert all(a["to"] <= b["from"] for a, b in zip(said, said[1:]))


def _said(*sentences):
    """A voice's clock for whole lines, each word 0.3 s."""
    return short.lines([{"idx": n, "narration": text, "duration_ms": 300 * len(text.split()),
                         "words": [{"word": w, "start_ms": 300 * i, "end_ms": 300 * i + 250} for i, w in enumerate(text.split())]}
                        for n, text in enumerate(sentences, 1)], [500] * len(sentences))


def test_captions_break_between_phrases_never_inside_one():
    # the microwave short, Nov 15, 2026: "So you keep metal" read alone is the opposite of the line, "The waves slosh loose"
    # reads as the waves sloshing loosely, and "The metal walls around" left "it don't." on its own
    said = [c["text"] for c in short.captions(_said(
        "So you keep metal out, and switch off the moment it sparks.",
        "The waves slosh loose electrons in both metals back and forth.",
        "A fork sparks in the microwave. The metal walls around it don't.",
        "Worse, thin metal like a twist tie can't carry that much sloshing, so it heats."))]
    assert said == ["So you keep metal out,", "and switch off", "the moment it sparks.",
                    "The waves slosh loose electrons", "in both metals", "back and forth.",
                    "A fork sparks", "in the microwave.", "The metal walls", "around it don't.",
                    "Worse,", "thin metal", "like a twist tie", "can't carry that much sloshing,", "so it heats."]
    assert all(len(c.split()) <= short.CAPTION_WORDS for c in said)


def test_a_scene_comes_into_its_own_time():
    scene = _scene(2.5, 4.0, happens=[{"do": "expression", "t": 3.0, "who": "walt", "name": "happy"},
                                      {"do": "glow", "t": 2.5, "to": 3.5, "who": "walt", "on": "jaw", "color": "red"}])
    scene["shots"] = [{"t": 2.5, "on": "walt:eyes", "frame": 0.6}, {"t": 3.2, "on": "walt:mouth", "frame": 0.4}]
    mine = short.local(scene)
    assert mine["length"] == 1.5 and "from" not in mine and "to" not in mine
    assert [s["t"] for s in mine["shots"]] == [0, 0.7]
    assert mine["happens"][0]["t"] == 0.5 and mine["happens"][1]["to"] == 1.0


def test_scenes_have_to_cover_the_short_exactly():
    good = {"scenes": [_scene(0, 2.5), _scene(2.5, 4.0)]}
    check = lambda d: short.check(d, 4.0, ["walt"], ["Idle_relaxed"], {})
    assert check(good) == []
    assert "they have to meet" in " ".join(check({"scenes": [_scene(0, 2.0), _scene(2.5, 4.0)]}))
    assert "the short ends at" in " ".join(check({"scenes": [_scene(0, 2.5)]}))
    assert "don't write captions" in " ".join(check({"scenes": [_scene(0, 4.0, captions=[])]}))
    assert "needs from and to" in " ".join(check({"scenes": [{"set": "gym"}]}))
    assert check({"scenes": []})
    wrong = _scene(0, 4.0)
    wrong["cast"] = {"walt": {**PERSON, "character": "nia"}}
    assert "character" in " ".join(check({"scenes": [wrong]}))       # only who it cast


def test_what_a_scene_leaves_is_what_the_next_one_starts_with():
    tank = {"type": "prop", "prop": "water_tank", "on": "set", "at": [0, 0], "level": 0.1}
    scene = lambda a, b, entry, happens=(), **more: {"from": a, "to": b, "set": "sky_counter", "cast": {"tank": entry}, "happens": list(happens), **more}
    carry = lambda *scenes: " ".join(short._carry_problems(list(scenes)))
    fills = [{"do": "fill", "prop": "tank", "t": 0.5, "over": 1.0, "level": 0.3}]
    assert carry(scene(0, 2, tank, fills), scene(2, 4, {**tank, "level": 0.3})) == ""                    # it starts as full as it was left
    assert "left it at 0.3" in carry(scene(0, 2, tank, fills), scene(2, 4, tank))                          # it's emptied itself across the cut
    assert "left it at 0.3" in carry(scene(0, 2, tank, fills), {"from": 2, "to": 3, "set": "gym", "cast": {}}, scene(3, 4, tank))    # and a scene without it between doesn't excuse that
    assert carry(scene(0, 2, tank, fills), scene(2, 4, tank, anew=["tank"])) == ""                         # unless the scene says it starts afresh
    assert "starts full" in carry(scene(0, 2, tank), scene(2, 4, {k: v for k, v in tank.items() if k != "level"}))
    assert "somewhere else" in carry(scene(0, 2, tank), scene(2, 4, {**tank, "at": [0.4, 0]}))            # it's jumped along the counter
    slid = [{"do": "slide", "prop": "tank", "t": 0.5, "over": 1.0, "by": [0.4, 0, 0]}]
    assert carry(scene(0, 2, tank, slid), scene(2, 4, {**tank, "at": [0.4, 0]})) == ""                    # something moved it
    assert "back where scene 1 started it" in carry(scene(0, 2, tank, slid), scene(2, 4, tank))            # it's snapped back
    there_and_back = slid + [{"do": "slide", "prop": "tank", "t": 1.5, "over": 0.4, "by": [-0.4, 0, 0]}]
    assert carry(scene(0, 2, tank, there_and_back), scene(2, 4, tank)) == ""                                # unless it was seen sliding back
    set_down = [{"do": "slide", "prop": "tank", "t": 2.1, "over": 0.5, "from": [-0.4, 0, 0]}]
    assert carry(scene(0, 2, tank), scene(2, 4, {**tank, "at": [0.4, 0]}, set_down)) == ""                # it's set down there in the picture
    assert carry(scene(0, 2, tank), scene(2, 4, {**tank, "at": [0.4, 0]}, set="sky_set")) == ""           # another place says nothing about this one
    assert carry(scene(0, 2, tank), scene(2, 4, {**tank, "prop": "mercury_dish", "at": [0.4, 0]})) == ""  # nor does the same name on another thing
    assert "anew" not in short.local(scene(0, 2, tank, anew=["tank"]))                                     # and the stage never sees `anew`
    whole = short.check({"scenes": [scene(0, 2, tank, fills, shots=[{"t": 0, "on": "tank:surface", "frame": 0.5}]),
                                    scene(2, 4, tank, shots=[{"t": 2, "on": "tank:surface", "frame": 0.5}])]}, 4.0, [], [], {})
    assert "left it at 0.3" in " ".join(whole)                                                             # a direction's check refuses it


def test_every_line_gets_room_and_a_question_gets_more():
    scenes = [{"narration": "Why?", "beat_idx": 0}, {"narration": "One.", "beat_idx": 0}, {"narration": "Two.", "beat_idx": 0},
              {"narration": "But three.", "beat_idx": 1}]
    assert short.pauses(scenes) == [short.LONG_PAUSE_MS, short.PAUSE_MS, short.LONG_PAUSE_MS, short.LAST_PAUSE_MS]
    assert short.PAUSE_MS >= 500                              # the owner's floor


def _stood(length, happens=(), shows=None):
    shots = [{"t": 0, "on": "walt:eyes", "frame": 0.6, "angle": [0, 0], **({"shows": shows} if shows else {})}]
    return {"from": 0, "to": length, "set": "gym", "cast": {"walt": {"type": "person", "character": "walt", "at": [0, 0]}}, "happens": list(happens), "shots": shots}


def test_a_person_with_nothing_to_do_is_refused_but_a_quick_reaction_isnt():
    assert short._idle_people(_stood(3.0)) == []                          # a face for a moment
    assert "just stands there" in " ".join(short._idle_people(_stood(9.0)))
    looked = [{"do": "expression", "t": 0, "who": "walt", "name": "curious"}, {"do": "glow", "t": 0, "who": "walt", "on": "jaw", "color": "red", "to": 9}]
    assert short._idle_people(_stood(9.0, looked))                        # a look and a glow are still standing there
    assert short._idle_people(_stood(9.0, [{"do": "strike", "t": 1, "who": "walt", "prop": "x", "target": "y"}])) == []
    scene = _stood(9.0)
    scene["shots"][0]["shows"] = ["trunk"]
    assert short._idle_people(scene) == []                                # in the scene, and never on screen


def test_a_shot_with_nothing_moving_is_refused_but_one_going_somewhere_isnt():
    still = {"from": 0, "to": 4, "cast": {}, "happens": [], "shots": [{"t": 0, "on": "bird:head", "frame": 0.5}]}
    assert "nothing moving" in " ".join(short._still_shots(still))
    assert short._still_shots({**still, "to": 2}) == []                                                        # not long enough to notice
    assert short._still_shots({**still, "shots": [{**still["shots"][0], "to": {"frame": 0.3}}]}) == []         # the camera's going somewhere
    assert short._still_shots({**still, "happens": [{"do": "rock", "t": 1, "over": 1, "prop": "bird"}]}) == []  # something's moving in it
    assert short._still_shots({**still, "happens": [{"do": "expression", "t": 1, "who": "x"}]})                # a look isn't enough


def test_someone_can_only_hold_a_stance_and_only_do_a_move():
    from scenes import spec as scene_spec
    scene = {"length": 3.0, "set": "sky_set", "cast": {"walt": {"type": "person", "character": "walt", "at": [0, 0], "stance": "Idle_relaxed"}},
             "happens": [{"do": "act", "t": 0, "who": "walt", "clip": "Hit_to_the_head"}], "shots": [{"t": 0, "on": "walt:eyes", "frame": 0.6}]}
    assert scene_spec.check(scene, ["walt"], ["Idle_relaxed"], {}, ["Hit_to_the_head"]) == []
    assert "clip" in " ".join(scene_spec.check(scene, ["walt"], ["Idle_relaxed"], {}, ["Run_sprint"]))         # not a move it was given
    running = {**scene, "cast": {"walt": {**scene["cast"]["walt"], "stance": "Run_sprint"}}}
    assert "stance" in " ".join(scene_spec.check(running, ["walt"], ["Idle_relaxed"], {}, ["Run_sprint", "Hit_to_the_head"]))     # running on the spot
    assert scene_spec.check(scene, ["walt"], ["Idle_relaxed", "Hit_to_the_head"], {}) == []                    # told no moves, what it can hold will do


def test_the_moves_offered_to_a_director_say_what_they_do():
    from stages import direct
    text = direct._moves_text(["Run_jog_forwards", "Death_fall_backwards"])
    assert "Run_jog_forwards: running, 3.2 to 8 m/s" in text and "Death_fall_backwards" in text and "use stays" in text
    assert text.index("Run_jog_forwards") < text.index("On the spot") < text.index("Death_fall_backwards")     # those that go somewhere, for `walk`
    for name in ("Jump_in_the_air", "Dodge_roll", "ClimbUp_1m"):                                                # looked at on a person, and not what they're called
        assert name not in direct.GOES and name not in direct.ACTS


def test_the_same_picture_can_only_come_up_twice():
    shot = {"on": "bird:head", "frame": 0.95, "angle": [-100, 0]}
    scene = {"set": "sky_set", "shots": [{**shot, "t": 1}, {**shot, "t": 3}]}
    assert short._same_pictures([scene]) == []
    scene["shots"].append({**shot, "t": 5, "frame": 0.97})                # the same to a viewer
    assert "comes up 3 times" in " ".join(short._same_pictures([scene]))
    scene["shots"][2] = {**shot, "t": 5, "frame": 0.3}                    # nearer is a new picture
    assert short._same_pictures([scene]) == []


def test_a_channel_can_have_its_own_pauses():
    scenes = [{"narration": "Why?", "beat_idx": 0}, {"narration": "One.", "beat_idx": 0}, {"narration": "Two.", "beat_idx": 0}]
    assert short.pauses(scenes, [350, 450, 600]) == [450, 350, 600]
    assert short.pauses(scenes, []) == short.pauses(scenes)   # an empty setting means the usual ones
    from core import config as cfg
    assert cfg._pauses([350, 450, 600]) == [350, 450, 600] and cfg._pauses(None) == []
    with pytest.raises(ValueError):
        cfg._pauses([350])


def _tone(path, seconds, start_hz, end_hz, rate=44100):
    """A voice-like tone whose pitch glides, as a wav."""
    import array
    import math
    import wave
    data, phase = array.array("h"), 0.0
    for i in range(int(seconds * rate)):
        phase += 2 * math.pi * (start_hz + (end_hz - start_hz) * i / (seconds * rate)) / rate
        data.append(int(12000 * math.sin(phase)))
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(data.tobytes())
    return path


def test_a_question_that_rises_is_told_from_one_that_doesnt(tmp_path):
    from render import narration
    rising = narration.question_lift(_tone(tmp_path / "up.wav", 1.2, 120, 190))
    flat = narration.question_lift(_tone(tmp_path / "flat.wav", 1.2, 140, 140))
    assert rising > 1.05 and flat == pytest.approx(1.0, abs=0.02)
    assert narration.question_lift(_tone(tmp_path / "short.wav", 0.1, 140, 140)) is None   # too little to say


def test_a_line_is_cut_to_its_speech_and_its_words_move_with_it(tmp_path):
    from render import narration
    voiced = _tone(tmp_path / "a.wav", 1.0, 140, 140)
    padded = tmp_path / "padded.wav"
    ffmpeg.run(["-f", "lavfi", "-t", "0.5", "-i", "anullsrc=r=44100:cl=mono", "-i", voiced, "-filter_complex", "[0:a][1:a]concat=n=2:v=0:a=1", padded])
    final, got = narration.trimmed(padded, {"words": [{"word": "Hi", "start_ms": 500, "end_ms": 1400}]})
    assert got["duration_ms"] == pytest.approx(1090, abs=60)
    assert got["words"][0]["start_ms"] <= 40 and final.exists()


def _pieces(path, parts, rate=44100):
    """A wav of (seconds, loud) pieces: noise where loud, silence where not."""
    import array
    import random
    import wave
    noise, data = random.Random(7), array.array("h")
    for seconds, loud in parts:
        data.extend(int(noise.uniform(-9000, 9000)) if loud else 0 for _ in range(int(seconds * rate)))
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(data.tobytes())
    return path


def test_a_scrap_of_the_next_line_at_a_takes_end_is_cut_off(tmp_path):
    from render import narration
    # words, 0.28 s of silence, then 0.04 s of the next line's first sound: the woodpecker's line 6
    leaked = _pieces(tmp_path / "leak.wav", [(0.1, False), (1.0, True), (0.28, False), (0.04, True)])
    a, b = narration._ends(leaked, [0.1, 0.5])
    assert a == pytest.approx(0.07, abs=0.015) and b == pytest.approx(1.1 + narration.TAIL, abs=0.015)
    # a stop inside the last word ("it." is a closure, then the t) is too short a silence to cut anything off
    stop = _pieces(tmp_path / "stop.wav", [(1.0, True), (0.07, False), (0.05, True), (0.2, False)])
    assert narration._ends(stop, [0.0, 0.6])[1] == pytest.approx(1.12 + narration.TAIL, abs=0.015)
    # a short last word after a pause is kept, as the voice's timing has a word starting in it
    word = _pieces(tmp_path / "word.wav", [(1.0, True), (0.3, False), (0.15, True), (0.2, False)])
    assert narration._ends(word, [0.0, 0.6, 1.3])[1] == pytest.approx(1.45 + narration.TAIL, abs=0.015)
    assert narration._ends(word, [0.0, 0.6])[1] == pytest.approx(1.0 + narration.TAIL, abs=0.015)


def test_a_channels_own_pace_is_used(tmp_path, monkeypatch):
    tts = ElevenLabsTTS(CFG)
    sent = []

    def fake_call(method, url, **kwargs):
        if "json" not in kwargs:
            return {"stability": 0.5}
        sent.append(kwargs["json"]["voice_settings"]["speed"])
        return {"audio_base64": ""}

    monkeypatch.setattr(tts, "_call", fake_call)
    monkeypatch.setattr(ffmpeg, "duration_ms", lambda path: 1000)
    tts.speak(SimpleNamespace(id="x", voice_id="abc", voice_model="", voice_speed=1.05), "Hi.", tmp_path / "a.mp3")
    tts.speak(SimpleNamespace(id="y", voice_id="abc", voice_model="", voice_speed=0.0), "Hi.", tmp_path / "b.mp3")
    assert sent == [1.05, tts.speed]


def test_a_frame_on_the_sheet_is_paired_with_what_is_being_said_right_then():
    """Found on the first real short: a shot starting just after a line was labelled with that line, and the looker believed it."""
    assert film._being_said(LINES, 0.8) == '"A bird, [this frame] up high."'
    assert film._being_said(LINES, 2.2) == "(a pause between lines)"
    assert film._being_said(LINES, 2.6) == '"It [this frame] dives."'


def test_a_look_takes_the_frame_in_the_middle_of_every_shot():
    scene = {"length": 4.0, "shots": [{"t": 0}, {"t": 1.0}, {"t": 3.0}]}
    assert film._middle_frames(scene) == [16, 61, 106]


# --- what Claude's asked ---------------------------------------------------------------------------------------------------

class Answers(ClaudeLLM):
    """The prompts and checks as they are, with the replies given."""

    def __init__(self, replies):
        super().__init__(CFG)
        self.replies, self.asked = list(replies), []

    def _call(self, kind, system, messages, schema, meter, on_text, verify, verify_part=None):
        self.asked.append((kind, system, messages))
        text = json.dumps(self.replies.pop(0))
        problems = verify(text)
        assert not problems, problems
        return text


SHORTS = replace(CFG.channels["zombie"], id="shorts", name="Small Facts", format="character", gates=["render"], path=None,
                 scenario_family="one surprising true thing a viewer can see happen")
OUTLINE = {"shape": "why_it_happens", "hook": "Why don't woodpeckers get headaches?", "fact": "Their beaks flex. Source: a 2022 study in Current Biology.",
           "beats": [{"title": "The hit", "summary": "A beak strikes."}, {"title": "The force", "summary": "A glow."},
                     {"title": "The answer", "summary": "It bends."}], "turn": "none: the answer is the surprise.", "ending": "Your head doesn't."}


def test_an_outline_says_its_shape_and_what_comes_after_the_answer():
    from providers import checks
    assert checks.short_outline(OUTLINE) == []
    assert "the shape" in " ".join(checks.short_outline({**OUTLINE, "shape": "listicle"}))
    assert "the turn" in " ".join(checks.short_outline({**OUTLINE, "turn": " "}))


def test_only_a_why_short_can_open_on_a_bare_question():
    from providers import checks
    story = {**OUTLINE, "shape": "true_story"}
    assert "bare question" in " ".join(checks.short_outline(story))
    assert "bare question" in " ".join(checks.short_outline({**story, "hook": "What if you never slept?"}))
    assert checks.short_outline({**story, "hook": "He glued a coin to the pavement."}) == []
    assert checks.short_outline({**story, "hook": "If you caught a stone in your mouth, could you still talk?"}) == []     # a setup can end on one


def test_a_setup_can_run_long_but_a_hook_cant_run_on_forever():
    from providers import checks
    story = {**OUTLINE, "shape": "true_story"}
    assert checks.short_outline({**story, "hook": " ".join(["word"] * checks.SHORT_HOOK_WORDS)}) == []
    assert "words at most" in " ".join(checks.short_outline({**story, "hook": " ".join(["word"] * (checks.SHORT_HOOK_WORDS + 1))}))


def test_a_why_short_opens_on_the_viewers_own_question():
    """The owner, Nov 15, 2026, of a fork short that opened on a statement: "it doesnt start with a question, 'have you ever wondered
    why you can't put a fork into a microwave?'"."""
    from providers import checks
    said = {**OUTLINE, "hook": "A fork sparks in the microwave. The metal walls around it don't."}
    assert "own question" in " ".join(checks.short_outline(said))
    assert checks.short_outline({**OUTLINE, "hook": "Have you ever wondered why you can't put a fork in the microwave?"}) == []
    assert checks.short_outline({**said, "shape": "true_story"}) == []          # only a why short has to ask


def test_every_shape_is_described_to_whoever_writes_the_outline():
    from pathlib import Path
    from providers import checks
    prompt = (Path(__file__).resolve().parent.parent / "prompts" / "character" / "outline.md").read_text(encoding="utf-8")
    for shape in checks.SHORT_SHAPES:
        assert f"- `{shape}`:" in prompt


def test_the_outline_as_the_script_reads_it_has_the_shape_and_the_turn():
    llm = Answers([OUTLINE])
    got = llm.outline(SHORTS, "Woodpeckers", [], None, NoMeter())
    assert got["shape"] == "why_it_happens"
    text = prompts.outline_text(got)
    assert text.startswith("Shape: why_it_happens\nHook:") and "Turn: none: the answer" in text
    old = {k: v for k, v in got.items() if k not in ("shape", "turn")}     # outlines from before these still read
    assert "Shape" not in prompts.outline_text(old) and "Turn" not in prompts.outline_text(old)


def test_a_line_is_one_step_as_long_as_the_owners_star_shorts_run():
    from providers import checks
    built = Answers([OUTLINE]).outline(SHORTS, "Woodpeckers", [], None, NoMeter())
    line = lambda beat, count: {"beat": beat, "narration": " ".join(["word"] * count) + ".", "shows": "a beak"}
    assert checks.short_script([line(1, 22), line(2, 20), line(3, 10), line(3, 10)], built) == []
    assert "line 1 is 24 words" in " ".join(checks.short_script([line(1, 24), line(2, 20), line(3, 10), line(3, 10)], built))
    sixteen = [line(1, 6)] * 6 + [line(2, 6)] * 5 + [line(3, 6)] * 5      # 96 words: sixteen lines still fit a 30 to 40 second short
    assert checks.short_script(sixteen, built) == []


def test_a_short_inside_its_word_limit_is_still_refused_when_long_words_would_run_it_over_time():
    from providers import checks
    built = Answers([OUTLINE]).outline(SHORTS, "Woodpeckers", [], None, NoMeter())
    line = lambda beat, word: {"beat": beat, "narration": " ".join([word] * 11) + ".", "shows": "a beak"}
    short_words = [line(1, "word")] * 4 + [line(2, "word")] * 3 + [line(3, "word")] * 3         # 110 words of four letters
    long_words = [line(1, "counterweight")] * 4 + [line(2, "counterweight")] * 3 + [line(3, "counterweight")] * 3
    assert checks.short_script(short_words, built) == []
    assert checks.short_seconds(long_words) > checks.SHORT_SECONDS_MOST
    assert "read at the channel's pace" in " ".join(checks.short_script(long_words, built))


def test_a_shorts_seconds_are_counted_as_the_voice_says_them():
    from providers import checks
    assert checks.short_spoken("They count 40,000 men, and 3.2 million.") == "They count forty thousand men, and three point two million."
    one = lambda text: checks.short_seconds([{"narration": text}])
    assert one("They count 40,000 men.") > one("They count 40 men.") + 0.4                 # the digits are six letters, the words fourteen
    assert one("Japan surrenders. It is over.") == pytest.approx(one("Japan surrenders, it is over.") + checks.SHORT_STOP_S)
    china = ["China's Communists count 40,000 men. In twelve years they'll rule mainland China.",
             "Japan invades. The Communists' rival, China's government, fights the big battles.",
             "Japan wins ground, but has men to hold only cities and railways.", "So the Communists slip into the gaps.",
             "They raid railways and recruit villagers.", "Japan hits back.",
             "Then it strikes the government, while the Communists count a million.",
             "Japan surrenders. China's government army is still far bigger, but worn down.",
             "A civil war later, the Communists rule the mainland.",
             "So when you're outnumbered, think of this: no one can hold it all. Grow in the gaps."]
    assert checks.short_seconds([{"narration": line} for line in china]) == pytest.approx(48.5, abs=2)      # voiced, it ran 48.48 s


def test_a_short_gets_its_own_prompts_and_the_cards_shape():
    llm = Answers([OUTLINE])
    got = llm.outline(SHORTS, "Woodpeckers", [], None, NoMeter())
    assert "vertical 3D short" in llm.asked[0][1] and "survival" not in llm.asked[0][1]
    assert got["fact"].startswith("Their beaks") and got["beats"][0]["label"] == "Beat 1" and got["tracker"] == []
    text = prompts.outline_text(got)
    assert "Fact: Their beaks" in text and "Skill:" not in text


def test_a_script_comes_back_as_lines_the_voice_stage_can_read():
    lines = [{"beat": b, "narration": " ".join(["word"] * 14) + ".", "shows": "a beak"} for b in (1, 1, 2, 2, 3)]
    outline = Answers([OUTLINE]).outline(SHORTS, "Woodpeckers", [], None, NoMeter())
    got = Answers([{"scenes": lines}]).script(SHORTS, outline, [], None, NoMeter())
    assert len(got["scenes"]) == 5 and got["places"] == []
    assert got["scenes"][2]["beat_idx"] == 1 and got["scenes"][2]["visual_prompt"] == "a beak" and got["scenes"][2]["motion"] in checks.MOTIONS


@pytest.mark.parametrize("change, says", [
    (lambda s: s[:2], "lines"),
    (lambda s: [{**s[0], "narration": "too short"}, *s[1:]], "line 1 is 2 words"),
    (lambda s: [{**s[0], "narration": s[0]["narration"] + " — now"}, *s[1:]], "em dash"),
    (lambda s: [{**s[0], "beat": 9}, *s[1:]], "line 1 says beat 9"),
    (lambda s: [*s[:-1], {**s[-1], "beat": 1}], "goes back"),
    (lambda s: [x for x in s if x["beat"] != 2], "have no line"),
])
def test_a_bad_short_script_is_refused_with_the_reason(change, says):
    lines = [{"beat": b, "narration": " ".join(["word"] * 14) + ".", "shows": "x"} for b in (1, 1, 2, 2, 3)]
    assert checks.short_script(lines, {"beats": [{}, {}, {}]}) == []
    assert says in " ".join(checks.short_script(change(lines), {"beats": [{}, {}, {}]}))


def test_every_prompt_for_a_short_fills_without_a_stray_placeholder():
    values = {"idea": "", "notes": "", "previous": "", "outline": "", "script": "", "topic": "", "series": "", "lines": "",
              "people": "", "things": "", "built_in": "", "character_format": "", "thing_format": "", "what": "", "meters": 1, "moves": True,
              "hits": "", "rejected": "", "size": "", "clips": "", "materials": "", "round": 1, "total": 1, "stances": "",
              "language": "", "example": "", "shots": "", "competitors": "", "taken": "", "families": "", "held": "", "count": 1,
              "winner": "", "said": "", "planned": "", "sheets": "", "every": 3}
    for file, turns in (("outline", ("new", "revise")), ("script", ("new", "revise")), ("critic", ("outline", "script")),
                        ("titles", ("",)), ("topic", ("competitors", "winner")), ("cast", ("",)), ("source", ("",)),
                        ("thing", ("",)), ("direct", ("new", "revise")), ("film", ("",)), ("frames", ("",))):
        for turn in turns:
            system, user = prompts.render(CFG.root, f"character/{file}.md", turn, SHORTS, values)
            assert system and user


def test_a_look_can_only_name_what_the_file_really_has():
    base = {"right_thing": True, "tilt": [0, 0], "meters": 1, "moves": {}, "rest": ""}
    assert checks.thing_look(base, {"Fly": {}}) == []
    assert "its clip has to be" in " ".join(checks.thing_look({**base, "moves": {"f": {"clip": "Run"}}}, {"Fly": {}}))
    assert "isn't one of its moves" in " ".join(checks.thing_look({**base, "rest": "Sit"}, {"Fly": {}}))


# --- getting what a short asks for ----------------------------------------------------------------------------------------

class Looker:
    """The looks, answered as given."""

    def __init__(self, right=(True,)):
        self.right, self.picks = list(right), 0

    def pick_thing(self, channel, want, hits, sheet, rejected, meter):
        self.picks += 1
        return {"seen": "", "choice": len(rejected) + 1 if len(rejected) < len(hits) else 0, "why": ""}

    def check_thing(self, channel, want, manifest, sheet, round_n, meter):
        return {"seen": "", "right_thing": self.right.pop(0), "turn": 90 if round_n == 1 else 0, "tilt": [0, 0],
                "meters": want["meters"], "rest": "", "moves": {}, "spots": {"head": [0, -0.1, 0.1]}, "problems": []}


def _getting(tmp_path, monkeypatch, llm, hits):
    monkeypatch.setattr(thing_spec, "SPECS", tmp_path / "specs")
    (tmp_path / "specs").mkdir()
    monkeypatch.setattr(direct, "_search", lambda ctx, video, tid, words: {"hits": hits, "sheet": "s.png"})
    built = []

    def fake_build(config, tid, spend=False, say=print, spec=None):
        built.append(spec)
        return {"id": tid, "folder": tmp_path, "sheet": "t.png", "manifest": {"clips": {}, "size": [1, 1, 1]}}

    monkeypatch.setattr(direct.thing_build, "build", fake_build)
    said = []
    ctx = SimpleNamespace(llm=llm, config=None, media=lambda vid: tmp_path / "media",
                          events=SimpleNamespace(emit=lambda *a, **k: said.append(k.get("text"))))
    return ctx, built, said


HITS = [{"title": "Toy gull", "source": {"kind": "polyhaven", "asset": "toy"}}, {"title": "Gull", "source": {"kind": "polyhaven", "asset": "gull"}}]
WANT = {"id": "gull", "what": "a gull", "search": "gull", "meters": 1.2, "moves": True}


def test_a_wrong_model_is_turned_down_and_the_next_is_tried_and_put_right(tmp_path, monkeypatch):
    ctx, built, said = _getting(tmp_path, monkeypatch, Looker([False, True, True]), HITS)
    assert direct._get_thing(ctx, None, {"id": 1}, SHORTS, WANT, lambda what: NoMeter()) == "gull"
    kept = thing_spec.load(thing_spec.path_for("gull"))
    assert kept["source"]["asset"] == "gull" and kept["turn"] == 90 and kept["spots"]["head"] == [0, -0.1, 0.1]
    assert kept["meters"] == 1.2 and said == []


def test_a_thing_nothing_free_will_do_for_is_left_out_and_the_owner_told(tmp_path, monkeypatch):
    ctx, built, said = _getting(tmp_path, monkeypatch, Looker([False, False]), HITS)
    assert direct._get_thing(ctx, None, {"id": 1}, SHORTS, WANT, lambda what: NoMeter()) is None
    assert not thing_spec.path_for("gull").exists()
    assert "No free model would do" in said[0] and str(get.GENERATE["usd"]) in said[0]


def test_what_a_short_needs_is_asked_once_though_the_library_grows(tmp_path):
    """Found on the first real short: getting the first thing changed the library, so running again asked a new question."""
    ctx, calls = SimpleNamespace(media=lambda vid: tmp_path), []
    ask = lambda: calls.append(1) or {"people": [], "things": []}    # noqa: E731
    direct._asked_once(ctx, {"id": 1}, [], ask)
    direct._asked_once(ctx, {"id": 1}, [], ask)
    assert len(calls) == 1
    direct._asked_once(ctx, {"id": 1}, ["someone older"], ask)      # the owner's note is a new question
    assert len(calls) == 2


class Parks(Looker):
    """A look that waits on the session the first time it's asked each thing, as a real job does."""

    def __init__(self, right):
        super().__init__(right)
        self.asked, self.looks = set(), []

    def _waits(self, key):
        if key not in self.asked:
            self.asked.add(key)
            raise WaitsForSession

    def pick_thing(self, channel, want, hits, sheet, rejected, meter):
        self._waits(("pick", tuple(rejected)))
        return super().pick_thing(channel, want, hits, sheet, rejected, meter)

    def check_thing(self, channel, want, manifest, sheet, round_n, meter):
        self._waits(("look", round_n))
        self.looks.append(round_n)
        return super().check_thing(channel, want, manifest, sheet, round_n, meter)


class WaitsForSession(Exception):
    pass


def test_a_thing_carries_on_where_it_was_when_the_stage_runs_again(tmp_path, monkeypatch):
    ctx, built, said = _getting(tmp_path, monkeypatch, Parks([True, True]), HITS)
    got = None
    for _ in range(6):                    # each wait, the stage runs again from the top
        try:
            got = direct._get_thing(ctx, None, {"id": 1}, SHORTS, WANT, lambda what: NoMeter())
            break
        except WaitsForSession:
            continue
    assert got == "gull"
    assert ctx.llm.looks == [1, 2]        # looked at once, then once more as it was put right, and never again
    kept = thing_spec.load(thing_spec.path_for("gull"))
    assert kept["turn"] == 90 and kept["source"]["asset"] == "toy"
    turns = [s.get("turn") for s in built]
    assert None not in turns[turns.index(90):]                # once it's put right, it's never rebuilt the old way


def test_nothing_generated_is_ever_chosen_without_the_owner(tmp_path):
    source = {"kind": "generate", "prompt": "a gull"}
    with pytest.raises(RuntimeError, match="yes"):
        get.fetch(CFG, source, tmp_path)


# --- end to end ------------------------------------------------------------------------------------------------------------

def _fleet(tmp_path, gates=("outline", "script", "character", "render")):
    ctx = make_ctx(data_dir=tmp_path, overrides={
        "mode": "stub", "stub": {"scenes": 3}, "engine": {"retry_backoff_s": 0}, "topics": {"competitors": "off"},
        "render": {"engine": "ffmpeg"}})
    ctx.config.channels["shorts"] = replace(SHORTS, gates=list(gates), youtube={"category_id": 27, "tags": ["facts"]})
    with ctx.connect() as conn:
        db.sync_channels(conn, ctx.config.channels)
    return ctx


def _video(ctx, vid):
    with ctx.connect() as conn:
        return db.get_video(conn, vid)


def _cards(ctx, vid):
    with ctx.connect() as conn:
        return [json.loads(r["card_json"])["kind"] for r in conn.execute(
            "SELECT card_json FROM messages WHERE video_id = ? AND card_json IS NOT NULL ORDER BY id", (vid,))]


@pytest.mark.skipif(remotion_render.missing() is not None, reason="Remotion isn't installed")
def test_a_short_runs_from_a_topic_to_published_with_the_story_channel_untouched(tmp_path):
    ctx = _fleet(tmp_path)
    vid = actions.new_video(ctx, "shorts", "Why woodpeckers don't get headaches")
    story = actions.new_video(ctx, "zombie", "Day 1 to Day 30 in a flooded subway")
    Engine(ctx).run_until_idle()
    actions.approve(ctx, vid, "outline")
    Engine(ctx).run_until_idle()
    actions.approve(ctx, vid, "script")
    Engine(ctx).run_until_idle()

    video = _video(ctx, vid)                                   # voiced, titled and directed, and waiting on the cast
    assert video["state"] == "generating" and "character" in _cards(ctx, vid)
    direction = json.loads(video["direction_json"])
    assert direction["approved"] is False and direction["people"] and video["video_path"] is None
    with ctx.connect() as conn:
        scenes = db.scenes_for(conn, vid)
    assert {s["state"] for s in scenes} == {"ok"} and all(s["still_path"] is None for s in scenes)
    assert json.loads(video["thumbs_json"])["thumbs"] == []    # no thumbnails on a short

    actions.approve(ctx, vid, "character")
    Engine(ctx).run_until_idle()
    video = _video(ctx, vid)
    assert video["state"] == "assembled" and _cards(ctx, vid)[-1] == "render"
    made = ctx.abs(video["video_path"])
    assert made.exists() and abs(ffmpeg.duration_ms(made) - video["duration_ms"]) < 200
    assert Image.open(ctx.abs(video["frames_path"])).width > 0
    assert "Duration" in ffmpeg.probe(made) and "Audio" in ffmpeg.probe(made)   # the voice is on it

    with pytest.raises(Exception, match="pick a title first"):   # only a title to pick
        actions.approve(ctx, vid, "render")
    actions.pick(ctx, vid, title_idx=0)
    actions.approve(ctx, vid, "render")
    actions.request_publish(ctx, vid)
    Engine(ctx).run_until_idle()
    video = _video(ctx, vid)
    assert video["state"] == "scheduled"
    meta = json.loads(video["publish_json"])
    assert meta["thumbnail"] is None and meta["category_id"] == "27" and "facts" in meta["tags"] and "Chapters" not in meta["description"]

    other = _video(ctx, story)                                 # the story video stops at its own gate, as ever
    assert other["state"] == "outlined" and other["direction_json"] is None


def test_a_note_on_the_cast_directs_it_again_with_the_note(tmp_path):
    ctx = _fleet(tmp_path)
    vid = actions.new_video(ctx, "shorts", "Why woodpeckers don't get headaches")
    Engine(ctx).run_until_idle()
    actions.approve(ctx, vid, "outline")
    Engine(ctx).run_until_idle()
    actions.approve(ctx, vid, "script")
    Engine(ctx).run_until_idle()
    actions.revise(ctx, vid, "character", "someone older")
    with ctx.connect() as conn:
        assert db.notes(conn, vid, "direct") == ["someone older"]
    assert _video(ctx, vid)["direction_json"] is None
    Engine(ctx).run_until_idle()
    assert json.loads(_video(ctx, vid)["direction_json"])["approved"] is False
    assert _cards(ctx, vid).count("character") == 2


def test_at_the_render_card_a_flag_directs_it_again_but_keeps_the_voice(tmp_path):
    ctx = _fleet(tmp_path, gates=("outline", "script", "render"))
    vid = actions.new_video(ctx, "shorts", "Why woodpeckers don't get headaches")
    with ctx.connect() as conn, db.tx(conn):
        script = [{"idx": 1, "beat_idx": 0, "label": "Beat 1", "narration": "A line.", "visual_prompt": "x", "motion": "kenburns"}]
        db.update_video(conn, vid, outline_json=json.dumps({"topic": "t", "hook": "h", "ending": "e", "beats": [{"label": "Beat 1", "title": "t", "summary": "s", "skill": "", "hero": False, "cast": []}]}),
                        script_json=json.dumps(script))
        db.transition(conn, vid, "new", "scripted")
        actions.start_generating(conn, vid)
        conn.execute("UPDATE scenes SET state = 'ok', audio_path = 'a.mp3', duration_ms = 1000 WHERE video_id = ?", (vid,))
        db.update_video(conn, vid, direction_json=json.dumps({"scenes": [], "approved": True}), direction_draft_json=json.dumps({"looked": True}))
        db.transition(conn, vid, "generating", "assembled")
    with pytest.raises(Exception, match="voice stays"):
        actions.flag_scenes(ctx, vid, [1], "narration", "shorter")
    with pytest.raises(Exception, match="flag its lines"):
        actions.edit_scene(ctx, vid, 1, narration="new")
    actions.flag_scenes(ctx, vid, [1], "visual", "the bird's too small")
    video = _video(ctx, vid)
    assert video["state"] == "generating" and video["direction_json"] is None
    assert json.loads(video["direction_draft_json"])["looked"] is False     # looked at afresh
    with ctx.connect() as conn:
        assert db.notes(conn, vid, "direct") == ["On lines 1: the bird's too small"]
        assert db.scenes_for(conn, vid)[0]["audio_path"] == "a.mp3"


# --- filming for real, on a stand-in person -----------------------------------------------------------------------------------

def _directed(ctx, vid, scene):
    """A short with its voice and direction done, one line long, as stages/direct.py leaves it."""
    outline = {"topic": "t", "hook": "h", "ending": "e", "beats": [{"label": "Beat 1", "title": "t", "summary": "s", "skill": "", "hero": False, "cast": []}]}
    audio = ctx.media(vid) / "line.mp3"
    audio.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg.run(["-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", "1.5", audio])
    with ctx.connect() as conn, db.tx(conn):
        db.update_video(conn, vid, outline_json=json.dumps(outline), script_json=json.dumps(
            [{"idx": 1, "beat_idx": 0, "label": "Beat 1", "narration": "A line.", "visual_prompt": "x", "motion": "kenburns"}]))
        db.transition(conn, vid, "new", "scripted")
        actions.start_generating(conn, vid)
        conn.execute("UPDATE scenes SET state = 'ok', audio_path = ?, duration_ms = 1500, words_json = ? WHERE video_id = ?",
                     (ctx.rel(audio), json.dumps([{"word": "A", "start_ms": 0, "end_ms": 400}, {"word": "line.", "start_ms": 400, "end_ms": 1400}]), vid))
        db.update_video(conn, vid, direction_json=json.dumps({"scenes": [scene], "people": ["walt"], "things": [], "credits": [], "look": 0, "approved": True}))
    return outline


def _really_filming(tmp_path, monkeypatch):
    ctx = _fleet(tmp_path, gates=("outline", "script", "render"))
    monkeypatch.setattr(film, "_stub", lambda c: False)
    with ctx.connect() as conn, db.tx(conn):
        conn.execute("SELECT 1")
    return ctx


@pytest.mark.skipif(remotion_render.missing() is not None, reason="Remotion isn't installed")
def test_a_short_is_really_filmed_after_its_shots_are_looked_at(tmp_path, monkeypatch):
    from render import blender_render, clips
    from test_characters import _fake_person
    if blender_render.missing(CFG) or clips.missing(CFG):
        pytest.skip("needs Blender and the free clips")
    ctx = _really_filming(tmp_path, monkeypatch)
    ctx.config.blender["samples"] = 1
    person = _fake_person(tmp_path / "made")
    target = ctx.config.data_dir / "characters" / "walt"
    target.mkdir(parents=True)
    for f in person.iterdir():
        (target / f.name).write_bytes(f.read_bytes())
    catalog = clips.catalog(CFG)
    monkeypatch.setattr(clips, "catalog", lambda c: catalog)
    looks = []
    real_check = ctx.llm.check_film
    monkeypatch.setattr(ctx.llm, "check_film", lambda channel, shots, sheet, meter: looks.append((shots, sheet)) or real_check(channel, shots, sheet, meter))
    vid = actions.new_video(ctx, "shorts", "t")
    scene = {"from": 0, "to": 2.7, "set": "sky_set", "cast": {"walt": {"type": "person", "character": "walt", "at": [0, 0], "stance": "Idle_relaxed"}},
             "happens": [{"do": "expression", "t": 0.5, "who": "walt", "name": "shocked"}],
             "shots": [{"t": 0, "on": "walt:eyes", "frame": 0.6}, {"t": 1.2, "on": "walt:mouth", "frame": 0.4}]}
    _directed(ctx, vid, scene)
    Engine(ctx).run_until_idle()
    video = _video(ctx, vid)
    assert video["state"] == "assembled", video["error"]
    assert looks and 'A line.' in looks[0][0] and Path(looks[0][1]).exists()   # two frames looked at, with their line
    assert ffmpeg.duration_ms(ctx.abs(video["video_path"])) == pytest.approx(2700, abs=200)
    assert not list((ctx.media(vid) / "film").glob("*/frames"))                  # the big pictures don't stay


def test_what_a_look_finds_doesnt_ask_again_what_the_short_needs():
    notes = [f"{direct.LOOK_NOTE}shot 3: too far", "someone older"]
    assert [n for n in notes if not n.startswith(direct.LOOK_NOTE)] == ["someone older"]


def test_what_a_look_finds_sends_it_back_once_and_only_once(tmp_path, monkeypatch):
    ctx = _really_filming(tmp_path, monkeypatch)
    vid = actions.new_video(ctx, "shorts", "t")
    scene = {"from": 0, "to": 2.7, "set": "sky_set", "cast": {"walt": {"type": "person", "character": "walt", "at": [0, 0], "stance": "Idle_relaxed"}},
             "happens": [], "shots": [{"t": 0, "on": "walt:eyes", "frame": 0.6}]}
    _directed(ctx, vid, scene)

    def refused(*args, **kwargs):
        raise ValueError("strike: walt stands too far from the door to reach it")

    monkeypatch.setattr(film.filming, "film", refused)
    with ctx.connect() as conn:
        video = db.get_video(conn, vid)
        film._work(ctx, conn, video)
        video = db.get_video(conn, vid)
        assert video["direction_json"] is None                                   # back to the director
        assert "stands too far" in db.notes(conn, vid, "direct")[0]
        assert json.loads(video["direction_draft_json"])["looked"] is True       # and not looked at again after this


def test_a_finished_short_is_laid_out_for_someone_to_go_through_it_frame_by_frame(tmp_path):
    from render import ffmpeg, frame_sheets
    video = tmp_path / "short.mp4"
    ffmpeg.run(["-f", "lavfi", "-i", "testsrc=size=270x480:rate=30:duration=4", "-pix_fmt", "yuv420p", video])
    made = frame_sheets.sheets(video, tmp_path / "review", every=3)
    assert len(made) == 2                                                         # 40 frames, at 30 a sheet
    assert made[0]["from"] == 0 and made[0]["to"] == round(29 * 3 / 30, 2) and made[1]["from"] == 3.0
    assert not list((tmp_path / "review").glob("f_*.png"))                        # the loose frames don't stay
    width, height = Image.open(made[0]["file"]).size
    assert width == frame_sheets.CELL[0] * frame_sheets.ACROSS and height == (frame_sheets.CELL[1] + frame_sheets.BAND) * frame_sheets.DOWN


def test_a_jump_between_frames_is_found_unless_a_cut_was_planned_there(tmp_path):
    from render import ffmpeg, frame_sheets
    video = tmp_path / "pop.mp4"
    ffmpeg.run(["-f", "lavfi", "-i", "color=c=black:size=108x192:rate=30:duration=1", "-f", "lavfi", "-i", "color=c=white:size=108x192:rate=30:duration=1",
                "-filter_complex", "[0][1]concat=n=2:v=1", "-pix_fmt", "yuv420p", video])
    assert frame_sheets.jumps(video, []) == [1.0]
    assert frame_sheets.jumps(video, [1.0]) == []


def test_what_the_frame_reviewer_finds_goes_back_to_the_director_and_then_the_owner_sees_it(tmp_path, monkeypatch):
    from stages import film
    assert film.MOST_FRAME_REVIEWS == 3
    source = Path(film.__file__).read_text(encoding="utf-8")
    assert "_review(ctx, conn, video, channel, out, direction, clock)" in source and '"reviewed": draft.get("reviewed", 0) + 1' in source


def test_a_draft_held_three_frames_a_frame_is_compared_three_frames_apart(tmp_path):
    """A draft (render/film_parts.py --draft) holds every third frame three frames long: its steady steps aren't jumps, a pop still is."""
    from render import ffmpeg, frame_sheets
    video = tmp_path / "draft.mp4"
    ffmpeg.run(["-f", "lavfi", "-i", "testsrc=size=108x192:rate=10:duration=2", "-f", "lavfi", "-i", "color=c=white:size=108x192:rate=10:duration=1",
                "-filter_complex", "[0][1]concat=n=2:v=1,fps=30", "-pix_fmt", "yuv420p", video])
    held = frame_sheets.jumps(video, [], step=3)
    assert held == [2.0]                                                          # only the pop to white
    assert frame_sheets.jumps(video, [2.0], step=3) == []

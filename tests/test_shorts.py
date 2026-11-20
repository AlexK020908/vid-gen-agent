"""Machine shorts (SHORTS.md): Blender renders a shot with its anchor tracks, and Remotion lays the overlay on it.

The Blender tests need Blender at blender.path (stickfleet.yaml) and are skipped without it, as the Remotion one is
without render/remotion/node_modules. The Poly Haven textures they use are fetched once into data/assets/.
"""
from pathlib import Path

import pytest

from core import config
from render import blender_render, ffmpeg, remotion_render

CFG = config.load()
needs_blender = pytest.mark.skipif(blender_render.missing(CFG) is not None, reason="Blender isn't installed")
needs_remotion = pytest.mark.skipif(remotion_render.missing() is not None, reason="Remotion isn't installed")


@needs_blender
@pytest.mark.parametrize("shot", ["nail", "crane", "air"])
def test_look_test_shot_renders_with_its_tracks(tmp_path, shot):
    tracks = blender_render.render_shot(CFG, shot, tmp_path, size=(216, 384), samples=2, frames=[1, 60])
    assert (tmp_path / "f_0001.png").exists() and (tmp_path / "f_0060.png").exists()
    assert tracks["rendered"] == [1, 60] and len(tracks["render_s"]) == 2
    for name, points in tracks["anchors"].items():
        assert len(points) == tracks["frames"]                 # a position for every frame, rendered or not
        x, y, seen = points[59]
        assert 0 <= x <= 1 and 0 <= y <= 1 and seen, (name, points[59])


@needs_blender
def test_an_anchor_inside_a_cutaway_is_seen(tmp_path):
    """The air shot's anchor is a ball inside the cut-open cylinder. The hidden cutter and the other air balls
    don't hide it, and it sits low and near the cut, where the ram's front edge never covers it as it comes down.
    (The first ball picked was covered for the shot's last half second, so its label vanished.)"""
    tracks = blender_render.render_shot(CFG, "air", tmp_path, size=(216, 384), samples=2, frames=[1])
    hidden = [i + 1 for i, (_x, _y, seen) in enumerate(tracks["anchors"]["air"]) if not seen]
    assert hidden == []


@needs_remotion
def test_short_clip_overlay_renders(tmp_path):
    clip = tmp_path / "clip.mp4"
    ffmpeg.run(["-f", "lavfi", "-i", "testsrc=size=1080x1920:rate=30", "-frames:v", 12, "-pix_fmt", "yuv420p", clip])
    track = [[0.4 + i * 0.01, 0.5, i != 5] for i in range(12)]
    props = {"clip": "clip.mp4", "frames": 12, "captionStyle": "box",
             "captions": [{"text": "it compresses the air\ninside the cylinder", "from": 0, "to": 12}],
             "callouts": [{"label": "Air", "anchor": "air", "tone": "blue", "from": 2, "to": 12, "side": "right"}],
             "tags": [{"kind": "fail", "text": "Too slow", "icon": "clock", "from": 4, "to": 12},
                      {"kind": "mode", "text": "Slow motion", "from": 0, "to": 12}],
             "anchors": {"air": track}}
    out = remotion_render.render_short(props, {"clip.mp4": str(clip)}, tmp_path / "short.mp4")
    assert out.exists()
    assert abs(ffmpeg.duration_ms(out) - 400) <= 40
    assert "1080x1920" in ffmpeg.probe(out)


# --- phase 26 and 27: segments from timelines, sound, narration, the whole short ---------------------------------

def test_every_sound_effect_is_made(tmp_path):
    import wave
    from render import sfx
    for kind in sfx.KINDS:
        path = sfx.make(kind, tmp_path)
        with wave.open(str(path)) as w:
            assert (w.getframerate(), w.getnchannels()) == (44100, 1)
            assert w.getnframes() > 44100 * 0.1, kind
    assert sfx.kind_of("impact_boom") == "impact_heavy" and sfx.kind_of("nonsense") is None


class FakeVoice:
    """Speaks every line as a tone 0.1 s a word, and counts what it was asked."""

    def __init__(self):
        self.asked = []

    def speak(self, channel, text, out, before=None, after=None):
        self.asked.append(text)
        seconds = 0.1 * len(text.split())
        ffmpeg.run(["-f", "lavfi", "-i", f"sine=frequency=220:duration={seconds}", "-ar", 44100, out])
        return {"duration_ms": int(seconds * 1000), "words": []}, 0.001 * len(text)


def test_narration_fits_each_line_to_its_slot(tmp_path):
    from render import narration
    voice = FakeVoice()
    lines = [{"text": "one two three four five six seven", "start": 0.0, "end": 0.6},        # 0.7 s into 0.6
             {"text": "four words said here", "start": 1.0, "end": 1.45},                   # 0.4 s into 0.45
             {"text": "far too short for its place", "start": 2.0, "end": 3.0}]               # 0.6 s into 1.0
    fitted, spent = narration.fit(CFG, CFG.channels["zombie"], "voice", lines, tmp_path, tts=voice)
    first, second, third = (f["factor"] for f in fitted)
    assert first > 1.2 and abs(ffmpeg.duration_ms(fitted[0]["src"]) - 600) <= 40   # sped up to its slot
    assert second == 1.0                                                           # close enough: left alone
    assert third == narration.SLOWEST                                              # slowed, but no more than this
    assert spent > 0
    again, spent_again = narration.fit(CFG, CFG.channels["zombie"], "voice", lines, tmp_path, tts=voice)
    assert spent_again == 0 and len(voice.asked) == 3      # nothing voiced twice


def test_a_read_at_the_voices_own_pace_is_never_voiced_twice(tmp_path):
    from render import narration
    voice = FakeVoice()
    lines = [{"text": "this is a nail"}, {"text": "how do you drive it into the ground?"}]
    read, spent = narration.read(CFG, CFG.channels["zombie"], "voice", lines, tmp_path, tts=voice)
    assert spent > 0 and [r["text"] for r in read] == [line["text"] for line in lines]
    assert abs(read[0]["duration"] - 0.4) <= 0.09 and abs(read[1]["duration"] - 0.8) <= 0.09   # as voiced, no fitting
    again, spent_again = narration.read(CFG, CFG.channels["zombie"], "voice", lines, tmp_path, tts=voice)
    assert spent_again == 0 and len(voice.asked) == 2 and again[1]["duration"] == read[1]["duration"]


class PaddedVoice(FakeVoice):
    """A line of 1 s of tone with half a second of silence at each end, reading 7 characters a second."""

    def speak(self, channel, text, out, before=None, after=None):
        self.asked.append(text)
        ffmpeg.run(["-f", "lavfi", "-i", "sine=frequency=220:duration=1,adelay=500,apad=pad_dur=0.5", "-t", 2, "-ar", 44100,
                    out])
        return {"duration_ms": 2000, "words": [{"word": "hello", "start_ms": 500, "end_ms": 1000},
                                               {"word": "there", "start_ms": 1000, "end_ms": 1500}]}, 0.01


def test_a_read_is_trimmed_to_its_speech_and_brought_up_to_its_pace(tmp_path):
    from render import narration
    lines = [{"text": "hello there"}]                                    # 11 characters
    calm, _ = narration.read(CFG, CFG.channels["zombie"], "voice", lines, tmp_path, tts=PaddedVoice())
    assert abs(calm[0]["duration"] - 1.09) <= 0.08                       # the silence gone, a little room kept
    assert abs(calm[0]["words"][0]["start"] - 0.03) <= 0.03              # word times move with it
    assert abs(calm[0]["words"][1]["start"] - 0.53) <= 0.03
    paced, _ = narration.read(CFG, CFG.channels["zombie"], "voice", lines, tmp_path, tts=PaddedVoice(), pace=11.0)
    assert abs(paced[0]["duration"] - calm[0]["duration"] / 1.09) <= 0.05         # 10 c/s up to 11
    capped, _ = narration.read(CFG, CFG.channels["zombie"], "voice", lines, tmp_path, tts=PaddedVoice(), pace=30.0)
    assert abs(capped[0]["duration"] - calm[0]["duration"] / narration.MOST_TEMPO) <= 0.05
    never, _ = narration.read(CFG, CFG.channels["zombie"], "voice", lines, tmp_path, tts=PaddedVoice(), pace=2.0)
    assert abs(never[0]["duration"] - calm[0]["duration"]) <= 0.02       # a pace it's already past never slows it


def test_a_read_becomes_one_leveled_track(tmp_path):
    from render import narration
    voice = FakeVoice()
    lines = [{"text": "this is a nail"}, {"text": "how do you drive it"}]
    read, _ = narration.read(CFG, CFG.channels["zombie"], "voice", lines, tmp_path, tts=voice)
    out = narration.track(read, [0.0, 2.0], tmp_path / "track.wav")
    assert abs(ffmpeg.duration_ms(out) / 1000 - (2.0 + read[1]["duration"])) <= 0.1   # the last line, from its start


def test_sound_effects_duck_under_the_words():
    from render import narration
    read = [{"duration": 2.0}, {"duration": 1.0}]
    sounds = [{"src": "voice.wav", "from": 0.0, "volume": 1.0}, {"src": "tap.wav", "from": 1.0, "volume": 0.5},
              {"src": "boom.wav", "from": 2.5, "volume": 0.5}, {"src": "hit.wav", "from": 3.5, "volume": 0.5}]
    ducked = narration.duck(sounds, read, [0.0, 3.0])
    assert [s["volume"] for s in ducked] == [1.0, 0.3, 0.5, 0.3]         # the voice, on a line, in the pause, on a line


def test_captions_come_from_the_read():
    from render import narration
    long = "Pick up a hammer, give it a few light taps, and it goes right into the wood."
    no_comma = "drop a block of iron weighing dozens of tons from a height and then do it again and again"
    read = [{"text": "This is a nail.", "duration": 1.0, "words": [{"start": 0.2 + i * 0.2} for i in range(4)]},
            {"text": long, "duration": 4.0, "words": [{"start": 0.1 * i} for i in range(len(long.split()))]},
            {"text": no_comma, "duration": 5.0, "words": []}]            # no word times: spaced evenly
    captions = narration.captions(read, [0.0, 2.0, 7.0])
    assert captions[0]["text"] == "This is a nail." and captions[0]["from"] == 0.2
    assert captions[0]["to"] == round(2.0 - 0.07, 3)                     # up through the pause
    assert captions[1]["text"] == "Pick up a hammer, give it a few light taps,"
    assert captions[2]["text"] == "and it goes right into the wood."
    assert captions[2]["from"] == 3.0                                    # its first word, as the voice says it
    assert all(len(c["text"]) <= narration.CAPTION_MAX for c in captions)
    assert " ".join(c["text"] for c in captions[3:]) == no_comma and len(captions) == 5
    assert captions[-1]["to"] == 12.5                                    # half a second past the read's end
    spins = "the drum spins the clothes round and round inside a tub full of hot soapy water"   # no comma: split between phrases
    assert [" ".join(p) for p in narration._phrases(spins.split())] == ["the drum spins the clothes round and round",
                                                                      "inside a tub full of hot soapy water"]


def test_the_picture_follows_the_new_read_and_only_ever_slows():
    from render import retime
    old = [{"start": 0.0, "end": 1.0}, {"start": 2.0, "end": 3.0}, {"start": 6.0, "end": 7.0}]
    new = [{"duration": 2.0}, {"duration": 1.0}, {"duration": 3.0}]
    starts, warp = retime.layout(old, new, [0.5, 0.5, 0.5])
    assert starts[0] == 0.0
    assert starts[1] == 2.5                     # the first line and its pause
    assert starts[2] == 6.5                     # the beat with no words in the old read is kept: 2.5 + 4
    assert warp(2.0) == 2.5 and warp(6.0) == 6.5
    assert warp(1.0) == 1.25                    # stretched evenly between line starts
    assert warp(7.0) == 10.0 and warp(9.0) == 12.0   # the third line's end, and after it just moved along
    for a, b in zip(warp.knots, warp.knots[1:]):
        assert b[1] - a[1] >= b[0] - a[0]       # never sped up
    tl = {"from": 1.0, "to": 6.0, "keys": [{"t": 2.0, "joints": {}}], "camera": [{"t": 1.0, "frame": 3}],
          "events": [{"t": 6.0, "kind": "tap"}], "cuts": [{"from": 1.0, "to": 2.0}],
          "effects": [{"kind": "glow", "from": 1.0, "to": 2.0, "keys": [[1.0, 0], [2.0, 5]], "life": 1.0},
                      {"kind": "ghost", "keys": [{"t": 6.0, "z": 1}]}, {"kind": "ring", "t": 2.0}]}
    moved = retime.timeline(tl, warp)
    assert (moved["from"], moved["to"]) == (1.25, 6.5) and moved["keys"][0]["t"] == 2.5
    assert moved["camera"][0]["t"] == 1.25 and moved["events"][0]["t"] == 6.5 and moved["cuts"][0]["to"] == 2.5
    assert moved["effects"][0]["keys"] == [[1.25, 0], [2.5, 5]] and moved["effects"][0]["life"] == 1.0
    assert moved["effects"][1]["keys"][0]["t"] == 6.5 and moved["effects"][2]["t"] == 2.5
    assert tl["from"] == 1.0                    # the timeline passed in is left as it was
    # a sound's item still holds its file's path, which JSON can't carry
    tag = retime.spans([{"from": 1.0, "to": 2.0, "steps": [[1.0, 1], [2.0, 100]], "file": Path("sound.wav")}], warp)[0]
    assert tag["from"] == 1.25 and tag["steps"] == [[1.25, 1], [2.5, 100]]


def test_a_reference_video_can_be_slowed_to_the_new_read(tmp_path):
    """The side by side: A slowed by the same warp, as one ffmpeg expression, however many lines the read has."""
    from render import retime
    knots = [(float(i), i * 1.5) for i in range(45)]
    clip = tmp_path / "ref.mp4"
    ffmpeg.run(["-f", "lavfi", "-i", "testsrc=size=64x64:rate=30", "-t", 2, "-pix_fmt", "yuv420p", clip])
    out = tmp_path / "slow.mp4"
    ffmpeg.run(["-i", clip, "-filter_complex", f"[0:v]setpts='{retime.Warp(knots).setpts()}',fps=30[v]", "-map", "[v]",
                out])
    assert abs(ffmpeg.duration_ms(out) - 3000) <= 100


def test_camera_moves_too_fast_to_follow_are_reported():
    from render import shot_checks
    key = lambda t, frame, az=0, **kw: {"t": t, "frame": frame, "az": az, "el": 3, **kw}  # noqa: E731
    calm = {"camera": [key(0.0, 3), key(2.0, 6, az=20)]}
    assert shot_checks.camera_problems(calm) == []
    whip = {"camera": [key(0.0, 3.4), key(0.15, 18, az=45)]}       # A's whip at 8.6 s
    problems = shot_checks.camera_problems(whip)
    assert any("zooms" in p and "give it 0.67 s" in p for p in problems) and any("swings" in p for p in problems)
    assert shot_checks.camera_problems({"camera": [key(0.0, 3), key(0.02, 18)]}) == []      # a cut
    assert shot_checks.camera_problems({"camera": [key(0.0, 3), key(0.2, 18, fast=True)]}) == []   # a dive, on purpose
    assert shot_checks.camera_problems({"camera": [{"t": 0.0, "at": [0, 0, 0], "aim": [0, 1, 0]},
                                                   {"t": 0.2, "at": [0, 9, 0], "aim": [0, 1, 0]}]}) == []


def test_labels_are_checked_against_their_tracks():
    """A label whose anchor is hidden for most of its time, or sits under the captions, is reported; a hide shorter
    than a blink is ridden through, as the overlay does. (A's rebuild had DOZENS OF TONS pointing at the pile's top,
    above the picture, and PRESSURE at a later glow's anchor, so neither showed.)"""
    from render import shot_checks
    seen = [[0.5, 0.4, True]] * 30
    blink = [[0.5, 0.4, i not in (10, 11, 12)] for i in range(30)]
    gone = [[0.5, -1.5, False]] * 30
    low = [[0.5, 0.9, True]] * 30
    tracks = {name: {"first": 30, "points": pts} for name, pts in
              (("seen", seen), ("blink", blink), ("gone", gone), ("low", low))}
    label = lambda anchor: {"label": anchor.upper(), "anchor": anchor, "from": 1.0, "to": 2.0}  # noqa: E731
    assert shot_checks.label_problems([label("seen"), label("blink")], tracks, 30) == []
    gone_problems = shot_checks.label_problems([label("gone")], tracks, 30)
    assert len(gone_problems) == 1 and "hidden in 30 of 30" in gone_problems[0]
    assert "outside the safe area" in shot_checks.label_problems([label("low")], tracks, 30)[0]
    assert "no track" in shot_checks.label_problems([label("nowhere")], tracks, 30)[0]
    assert "covers only 15" in shot_checks.label_problems([{**label("seen"), "from": 1.5, "to": 2.5}], tracks, 30)[0]


@needs_blender
def test_a_segment_renders_from_its_timeline(tmp_path):
    timeline = {
        "from": 1.0, "to": 1.5, "env": "studio", "env_args": {},
        "models": {"blk": {"spec": "wood_block"}, "nl": {"spec": "nail", "at": [0, -0.04, 0.1]},
                   "hm": {"spec": "claw_hammer", "at": [0.135, -0.04, 0.3], "scale": 0.5}},
        "keys": [{"t": 1.0, "ease": "const", "place": {"nl": {"at": [0, -0.04, 0.1]}}},
                 {"t": 1.4, "ease": "in", "place": {"nl": {"at": [0, -0.04, 0.05]}}},
                 {"t": 1.2, "ease": "const", "show": {"hm": False}}],
        "camera": [{"t": 1.0, "target": [0, -0.04, 0.15], "az": 10, "el": 10, "frame": 0.25, "lens": 50},
                   {"t": 1.5, "target": [0, -0.04, 0.12], "az": 0, "el": 5, "frame": 0.2, "lens": 50}],
        "cuts": [{"model": "blk", "from": 0.0, "to": 2.0, "y": -0.04, "material": "wood_cut", "x_range": [-0.07, 0.05]}],
        "effects": [{"kind": "glow", "shape": "sphere", "model": "nl", "at": [0, 0, 0.05], "radius": 0.02,
                     "from": 1.1, "to": 1.3, "keys": [[1.1, 0], [1.2, 5], [1.3, 0]], "light": 5},
                    {"kind": "ring", "model": "blk", "t": 1.2, "at": [0, 0, 0.12], "r": [0.02, 0.06]}],
        "anchors": ["nl:head", "at:0,0,0.12"], "events": [{"t": 1.2, "kind": "tap"}]}
    tracks = blender_render.render_segment(CFG, timeline, tmp_path, size=(108, 192), samples=2, frames=[30, 40])
    assert (tmp_path / "f_0030.png").exists() and (tmp_path / "f_0040.png").exists()
    assert tracks["first"] == 30 and tracks["frames"] == 15                # frames numbered for the whole short
    assert set(tracks["anchors"]) == {"nl:head", "at:0,0,0.12"}
    assert all(len(points) == 15 for points in tracks["anchors"].values())
    assert tracks["events"] == [{"frame": 36, "kind": "tap"}]


@needs_remotion
def test_a_whole_machine_short_composes(tmp_path):
    from render import sfx
    for name, color in (("a.mp4", "red"), ("b.mp4", "blue")):
        ffmpeg.run(["-f", "lavfi", "-i", f"color=c={color}:size=1080x1920:rate=30:duration=1", "-pix_fmt", "yuv420p",
                    tmp_path / name])
    props = {"duration": 1.6, "segments": [{"clip": "a.mp4", "from": 0.0, "to": 1.0}, {"clip": "b.mp4", "from": 0.6,
                                                                                        "to": 1.6}],
             "screens": [{"kind": "crossfade", "from": 0.6, "to": 1.0}, {"kind": "white", "from": 1.2, "to": 1.3}],
             "captions": [{"text": "a ram on top\nand an anvil below", "from": 0.0, "to": 1.5}],
             "labels": [{"label": "Ram", "anchor": "s|ph:ram", "tone": "white", "from": 0.2, "to": 1.4,
                         "side": "right"}],
             "tags": [{"kind": "multiplier", "text": "", "from": 0.1, "to": 1.2, "at": [0.6, 0.2],
                       "steps": [[0.1, 1], [0.5, 10], [0.9, 100]]},
                      {"kind": "question", "text": "?", "from": 0.3, "to": 1.0, "at": [0.7, 0.5]}],
             "tracks": {"s|ph:ram": {"first": 0, "points": [[0.4, 0.5, True]] * 48}},
             "sounds": [{"src": "tap.wav", "from": 0.5, "volume": 0.5}], "footage": None}
    files = {"a.mp4": str(tmp_path / "a.mp4"), "b.mp4": str(tmp_path / "b.mp4"),
             "tap.wav": str(sfx.make("tap", tmp_path))}
    out = remotion_render.render_machine(props, files, tmp_path / "short.mp4")
    assert abs(ffmpeg.duration_ms(out) - 1600) <= 60
    assert "1080x1920" in ffmpeg.probe(out) and "Audio" in ffmpeg.probe(out)

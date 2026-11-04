"""The cutout puppets (puppet/): parts cut from a sheet, the rig's poses, a stage map, props placed and held,
set state carried between scenes, foreground cutouts, and a scene rendered."""
from pathlib import Path

import pytest
from PIL import Image, ImageChops, ImageDraw

from core import config
from providers import checks
from providers.images import StubImages
from providers.llm import StubLLM
from puppet import animate, draw, parts, props, rig, sheet as sheets, state
from puppet.stage import Stage


class Meter:
    def __init__(self) -> None:
        self.spent = 0.0

    def check(self, usd: float) -> None:
        pass

    def spend(self, usd: float, detail=None) -> None:
        self.spent += usd


def _channel():
    return config.load().channels["zombie"]


def _puppet(tmp_path: Path):
    channel, llm, meter = _channel(), StubLLM(), Meter()
    sheet = tmp_path / "sheet.png"
    StubImages().sheet(channel, channel.character_ref, parts.items_text(parts.HERO_PARTS), sheet)
    return parts.build(sheet, tmp_path / "hero", list(parts.HERO_PARTS),
                       lambda picture, names: llm.name_parts(channel, picture, names, meter)), meter


def _props(tmp_path: Path, names=("plate", "drill", "towel")):
    channel = _channel()
    sheet = tmp_path / "props.png"
    StubImages().sheet(channel, channel.character_ref, props.items_text(list(names)), sheet, file="props.md")
    return props.build(sheet, tmp_path / "props", list(names),
                       lambda picture, ns: StubLLM().name_parts(channel, picture, ns, Meter()))


def _place(tmp_path: Path) -> Stage:
    place = tmp_path / "place.png"
    Image.new("RGB", (1920, 1080), (210, 205, 190)).save(place)
    return Stage.from_percent(place, StubLLM().map_stage(_channel(), "the hall", place, Meter()))


def test_parts_are_cut_from_the_sheet_named_and_saved(tmp_path):
    puppet, meter = _puppet(tmp_path)
    assert set(puppet.parts) == set(parts.HERO_PARTS)
    assert meter.spent > 0  # Claude named the blobs
    head = puppet["head"].image
    assert head.mode == "RGBA"
    assert head.getpixel((1, 1))[3] == 0                      # the green is gone
    assert head.getchannel("A").getextrema()[1] == 255        # the part is there
    assert puppet["head"].pivot[1] == head.height             # the head hangs from its chin
    assert puppet["head"].slot == "head" and puppet["brace"].slot == "r_knee"
    assert puppet["head"].faces == "front" and puppet["hand"].faces == "right"
    assert puppet.in_slot("neck").name == "scarf"
    assert (tmp_path / "hero" / "sheet.boxes.jpg").exists()   # what Claude was shown
    again = parts.Puppet.load(tmp_path / "hero")
    assert again["cane"].height == rig.HEIGHTS["cane"] and again["cane"].image.size == puppet["cane"].image.size
    assert again.scale == 1.0 and again.in_slot("cane").name == "cane"


def test_a_part_is_cut_along_its_own_blob_not_its_box(tmp_path):
    """Two blobs whose boxes overlap (a diagonal rifle over a drill) come out separately."""
    sheet = tmp_path / "sheet.png"
    img = Image.new("RGB", (1920, 1080), (0, 255, 0))
    from PIL import ImageDraw
    d = ImageDraw.Draw(img)
    d.line((300, 900, 1100, 200), fill=(40, 40, 40), width=40)          # the long diagonal thing
    d.ellipse((800, 700, 1000, 900), fill=(200, 60, 60))                # inside its box, not touching it
    img.save(sheet)
    kit = parts.build(sheet, tmp_path / "kit", ["long", "round"], lambda pic, names: {"long": 1, "round": 2},
                      heights={"long": 0.5, "round": 0.1}, pivots={}, slots={})
    long = kit["long"].image
    x0, y0 = 300 - parts.MARGIN, 200 - parts.MARGIN                      # the long thing's box starts here
    assert long.getpixel((900 - x0, 800 - y0))[3] == 0                 # the round thing isn't in it
    assert kit["round"].image.width < 240


def test_the_side_head_is_drawn_when_the_figure_faces_a_side(tmp_path):
    puppet, _ = _puppet(tmp_path)
    front = Image.new("RGBA", (40, 40), (0, 0, 0, 0))
    ImageDraw.Draw(front).ellipse((0, 0, 39, 39), fill=(250, 250, 250, 255))
    side = Image.new("RGBA", (40, 40), (0, 0, 0, 0))
    ImageDraw.Draw(side).ellipse((0, 0, 39, 39), fill=(250, 50, 50, 255))          # a red side head
    puppet.parts["head"] = parts.Part("head", front, (20, 40), 0.27, "head", "front")
    puppet.parts["head_side"] = parts.Part("head_side", side, (20, 40), 0.27, "head_side", "right")
    place = tmp_path / "place.png"
    Image.new("RGB", (1920, 1080), (210, 205, 190)).save(place)
    stage = Stage.from_percent(place, StubLLM().map_stage(_channel(), "the hall", place, Meter()))

    def heads(action):
        sheet = {"stage": stage, "puppets": {"hero": puppet}, "duration_ms": 1000, "fps": 10,
                 "figures": [{"who": "hero", "actions": [action]}]}
        frame = animate.Scene(sheet).frame(5)
        reds = sum(1 for px in frame.get_flattened_data() if px[0] > 200 and px[1] < 100)
        whites = sum(1 for px in frame.get_flattened_data() if px[0] > 240 and px[1] > 240 and px[2] > 240)
        return reds, whites

    reds, whites = heads({"from_ms": 0, "to_ms": 1000, "do": "stand", "at": "middle", "facing": "right"})
    assert reds > 500 and whites < 50                                                  # the side head
    reds, whites = heads({"from_ms": 0, "to_ms": 1000, "do": "stand", "at": "middle", "facing": "right", "look": "camera"})
    assert whites > 500 and reds < 50                                                  # the front head
    assert "head_side" in parts.HERO_PARTS and parts.PIVOTS["head_side"] == (0.5, 1.0)


def test_a_part_painted_facing_left_is_mirrored_for_a_figure_facing_right():
    img = Image.new("RGBA", (20, 10), (0, 0, 0, 0))
    img.putpixel((2, 5), (255, 0, 0, 255))                                # a mark on the left side
    left = parts.Part("cap", img, (10, 5), 0.1, "head", "left")
    out, _ = draw._rotated(left, 10, 1, 0)                                  # facing right: mirrored
    assert out.getpixel((17, 5))[3] == 255 and out.getpixel((2, 5))[3] == 0
    out, _ = draw._rotated(left, 10, -1, 0)                                 # facing left: as painted
    assert out.getpixel((2, 5))[3] == 255
    right = parts.Part("drill", img, (10, 5), 0.1, "", "right")
    out, _ = draw._rotated(right, 10, -1, 0)                                # facing left: mirrored
    assert out.getpixel((17, 5))[3] == 255


def test_poses_blend_cycle_and_stand_on_the_ground():
    mid = rig.blend(rig.STAND, rig.KNEEL, 0.5)
    assert mid.torso == (rig.STAND.torso + rig.KNEEL.torso) / 2
    assert mid.cane == (rig.STAND.cane + rig.KNEEL.cane) / 2
    assert rig.blend(rig.STAND, rig.STAND_FREE, 0.4).cane == rig.STAND.cane   # the cane goes halfway through
    assert rig.blend(rig.STAND, rig.STAND_FREE, 0.6).cane is None
    assert rig.cycle(rig.LIMP, 0.0) == rig.LIMP[0][1] and rig.cycle(rig.LIMP, 1.0) == rig.LIMP[0][1]
    assert rig.cycle(rig.LIMP, 0.5) == rig.LIMP[2][1]
    j = rig.joints(rig.STAND, 400, (500, 500))
    assert j["neck"][1] < j["shoulder"][1] < j["hip"][1] < j["r_knee"][1] < j["r_foot"][1]
    assert j["cane_tip"][1] > j["cane_top"][1]
    assert 100 < rig.ground(rig.STAND, 400) < 140                              # legs are 0.34 H, a little splayed
    assert rig.ground(rig.SIT, 400) < 60                                       # sitting: the hip near the floor
    left = rig.joints(rig.STAND, 400, (500, 500), facing=-1)
    assert abs((left["r_foot"][0] - 500) + (j["r_foot"][0] - 500)) < 1e-6      # mirrored
    assert set(rig.POSES) >= {"stand", "kneel", "kneel_work", "kneel_press", "sit", "reach"}


def test_a_stage_map_is_kept_in_pixels_and_reloaded(tmp_path):
    stage = _place(tmp_path)
    assert stage.spot("door_left") == pytest.approx((18 * 19.2, 94 * 10.8))
    assert abs(stage.height_at(*stage.spot("middle")) - 56 * 10.8) < 1e-6
    assert stage.occluders[0]["name"] == "table" and len(stage.occluders[0]["polygon"]) == 4
    assert stage.occluders[0]["base_y"] == pytest.approx(97 * 10.8)
    stage.save(tmp_path / "stage.json")
    again = Stage.load(tmp_path / "stage.json")
    assert again.spots == stage.spots and again.floor == stage.floor and again.light["warm"] is True
    assert again.occluders == stage.occluders


def test_a_spot_off_the_floor_path_is_sized_by_its_depth(tmp_path):
    """Video 5's front lawn: the floor points run diagonally from the stairs to the gate, and the helipad is far
    off to the right at the gate's depth. It took the near points' size (38%) and came out twice too big."""
    place = tmp_path / "place.png"
    Image.new("RGB", (100, 100)).save(place)
    stage = Stage.from_percent(place, {
        "floor": [{"x": 60, "y": 98, "height": 44}, {"x": 56, "y": 89, "height": 33}, {"x": 42, "y": 70, "height": 24},
                  {"x": 34, "y": 56, "height": 18}, {"x": 29, "y": 47, "height": 14}],
        "spots": [{"name": "helipad", "x": 85, "y": 55}], "light": {"x": 50, "y": 10, "warm": False}})
    assert stage.height_at(*stage.spot("helipad")) == pytest.approx(14 + 8 * 19 / 42)  # read along y, ~17.6
    assert stage.height_at(5, 89) == pytest.approx(33)                     # a floor point's depth, anywhere across
    assert stage.height_at(50, 100) == pytest.approx(44 + 11 * 2 / 9)       # past the near end: the same line on
    assert stage.height_at(50, 0) == pytest.approx(7)                       # never below half the smallest


def test_a_stair_point_only_sizes_the_spots_beside_it(tmp_path):
    """Video 5's wine cellar: two floor points are on the stairs at the left, taller than the cellar floor at the
    same depth. The racks in the middle and right are sized by the cellar floor's points."""
    place = tmp_path / "place.png"
    Image.new("RGB", (100, 100)).save(place)
    stage = Stage.from_percent(place, {
        "floor": [{"x": 7, "y": 50, "height": 34}, {"x": 14, "y": 72, "height": 46}, {"x": 38, "y": 92, "height": 60},
                  {"x": 50, "y": 78, "height": 42}, {"x": 55, "y": 65, "height": 25}],
        "spots": [], "light": {"x": 50, "y": 10, "warm": False}})
    assert stage.height_at(41, 74) == pytest.approx(25 + 9 * 17 / 13)      # left racks, ~37 (not 46 off the stair)
    assert stage.height_at(71, 80) == pytest.approx(42 + 2 * 18 / 14)      # right racks, ~45
    assert stage.height_at(7, 50) == pytest.approx(34)                      # the top of the stairs


def test_props_are_cut_with_their_own_pivots_and_sizes(tmp_path):
    kit = _props(tmp_path)
    assert set(kit.parts) == {"plate", "drill", "towel"}
    assert kit["plate"].pivot[1] == kit["plate"].image.height          # stands on its bottom edge
    assert kit["plate"].height == props.SPECS["plate"]["height"] and kit["plate"].slot == ""
    assert props.load(tmp_path / "props")["towel"].height == props.SPECS["towel"]["height"]


def test_set_state_carries_between_scenes():
    s1 = state.apply({}, "stairwell", [{"place": "plate", "at": "plate_wall", "angle": -12}])
    s2 = state.apply(s1, "stairwell", [])                                # a scene that changes nothing
    assert state.placements(s2, "stairwell") == {"plate": {"at": "plate_wall", "angle": -12}}
    s3 = state.apply(s2, "stairwell", [{"place": "plate", "at": "stairs_top"}])
    assert state.placements(s3, "stairwell")["plate"] == {"at": "stairs_top"}
    assert state.placements(s1, "stairwell")["plate"]["at"] == "plate_wall"  # earlier states untouched
    s4 = state.apply(s3, "stairwell", [{"remove": "plate"}])
    assert state.placements(s4, "stairwell") == {} and state.placements(s4, "garage") == {}
    with pytest.raises(ValueError):
        state.apply({}, "stairwell", [{"place": "plate"}])


def _ink(frame: Image.Image, box=None) -> int:
    region = frame.crop(box) if box else frame
    return sum(1 for px in region.get_flattened_data() if px[0] < 40 and px[1] < 40)


def test_a_placed_prop_an_attached_prop_and_a_cutout_are_drawn_in_depth_order(tmp_path):
    puppet, _ = _puppet(tmp_path)
    kit = _props(tmp_path)
    stage = _place(tmp_path)
    sheet = {"stage": stage, "puppets": {"hero": puppet}, "props": kit, "duration_ms": 1000, "fps": 10,
             "set": {"plate": {"at": "stairs_top"}},
             "figures": [{"who": "hero", "actions": [{"from_ms": 0, "to_ms": 1000, "do": "kneel_work",
                                                      "at": "middle", "facing": "right"}],
                          "attached": {"r_hand": {"prop": "drill", "angle": 0}}},
                         {"who": "hero", "actions": [{"from_ms": 0, "to_ms": 1000, "do": "stand", "at": [1300, 1000]}]}]}
    frame = animate.Scene(sheet).frame(5)
    # the plate (the stub draws it white) stands on stairs_top, taller than a person
    x, y = stage.spot("stairs_top")
    assert frame.getpixel((round(x), round(y - 0.9 * stage.height_at(x, y))))[0] > 240
    # the drill (red in the stub) is in the picture, in the hero's hand
    assert sum(1 for px in frame.get_flattened_data() if px[0] > 150 and px[1] < 90) > 200
    # the second figure stands behind the table cutout: its legs inside the polygon are hidden, its head shows
    assert _ink(frame, (1160, 870, 1430, 1040)) == 0
    assert _ink(frame, (1160, 300, 1430, 860)) > 100
    sheet["figures"].pop()
    sheet["set"] = {}
    bare = animate.Scene(sheet).frame(5)
    assert bare.getpixel((round(x), round(y - 0.9 * stage.height_at(x, y))))[0] < 240   # no plate without the set


def test_a_brace_and_a_cane_show_only_while_the_look_has_them(tmp_path):
    """Video 5's seventeen-year-old had video 3's knee brace and cane: the channel's puppet is painted with them,
    and they were drawn in every scene. They belong to one story's look."""
    puppet, _ = _puppet(tmp_path)
    plain = puppet.wearing("")
    assert "brace" not in plain and "cane" not in plain and {"head", "scarf", "hand"} <= set(plain.parts)
    hurt = puppet.wearing("a hinged metal knee brace wrapped in grey tape on the right leg; a wooden cane")
    assert "brace" in hurt and "cane" in hurt
    assert "cane" not in puppet.wearing("soaked through in a hurricane")               # whole words only
    stage = _place(tmp_path)
    stand = [{"from_ms": 0, "to_ms": 1000, "do": "stand", "at": "middle"}]
    assert animate.figure_at(stage, hurt, stand, 900).pose == rig.STAND                # the hand on the cane
    assert animate.figure_at(stage, plain, stand, 900).pose == rig.STAND_FREE          # the arm hangs free
    walk = [{"from_ms": 0, "to_ms": 2000, "do": "limp", "start": "door_left", "end": "stairs_top"}]
    assert all(animate.figure_at(stage, plain, walk, t).pose.cane is None for t in (0, 500, 1000, 1500))


def test_a_figure_standing_still_holds_still(tmp_path):
    """Video 5: a standing figure shook, from a jitter added to its joints every few frames."""
    puppet, _ = _puppet(tmp_path)
    stage = _place(tmp_path)
    scene = animate.Scene({"stage": stage, "puppets": {"hero": puppet}, "duration_ms": 3000, "fps": 10,
                           "figures": [{"who": "hero", "actions": [{"from_ms": 0, "to_ms": 3000, "do": "stand",
                                                                     "at": "middle"}]}],
                           "camera": [{"at_ms": 0, "center": "middle", "zoom": 1.5}]})
    assert ImageChops.difference(scene.frame(10), scene.frame(25)).getbbox() is None


def test_a_small_puppet_stands_shorter(tmp_path):
    puppet, _ = _puppet(tmp_path)
    puppet.scale = 0.6
    stage = _place(tmp_path)
    fig = animate.figure_at(stage, puppet, [{"from_ms": 0, "to_ms": 1000, "do": "stand", "at": "middle"}], 500)
    assert fig.height == pytest.approx(0.6 * stage.height_at(*stage.spot("middle")))


def test_a_scene_renders_the_figure_walking_then_kneeling(tmp_path):
    puppet, _ = _puppet(tmp_path)
    stage = _place(tmp_path)
    sheet = {"stage": stage, "puppets": {"hero": puppet}, "duration_ms": 3000, "fps": 10,
             "light": {"level": 0.7, "color": [0.8, 0.85, 1.0],
                       "glow": {"at": "lamp", "radius": 0.4, "color": [255, 226, 170], "strength": 0.8}},
             "figures": [{"who": "hero", "actions": [
                 {"from_ms": 0, "to_ms": 2000, "do": "limp", "start": "door_left", "end": "stairs_top"},
                 {"from_ms": 2000, "to_ms": 3000, "do": "kneel"}]}],
             "camera": [{"at_ms": 0, "center": "door_left", "zoom": 1.4},
                        {"at_ms": 2000, "center": "stairs_top", "zoom": 1.6}]}
    scene = animate.Scene(sheet)
    assert scene.frames == 30
    walking = animate.figure_at(stage, puppet, sheet["figures"][0]["actions"], 1000)
    assert walking.facing == 1 and stage.spot("door_left")[0] < walking.feet[0] < stage.spot("stairs_top")[0]
    kneeling = animate.figure_at(stage, puppet, sheet["figures"][0]["actions"], 2900)
    assert kneeling.feet == stage.spot("stairs_top") and kneeling.pose == rig.KNEEL
    frame = scene.frame(10)
    assert frame.size == animate.OUT_SIZE
    assert _ink(frame) > 2000                                                # the sticks are drawn
    out = scene.render(tmp_path / "demo.mp4")
    assert out.exists() and out.stat().st_size > 10_000


def test_the_camera_moves_to_someone_before_they_come_on(tmp_path):
    """Video 5, scene 41: the camera starts on the gate and moves to Mr. Ashford, who only walks on at 3.8 s.
    Before he's there it heads for where he first stands, instead of failing to find him."""
    puppet, _ = _puppet(tmp_path)
    stage = _place(tmp_path)
    sheet = {"stage": stage, "puppets": {"hero": puppet}, "duration_ms": 2000, "fps": 10,
             "figures": [{"who": "hero", "actions": [
                 {"from_ms": 1000, "to_ms": 2000, "do": "limp", "start": "stairs_top", "end": "middle"}]}],
             "camera": [{"at_ms": 0, "center": "door_left", "zoom": 1.0}, {"at_ms": 1000, "center": "hero", "zoom": 1.0}]}
    seen = []
    real = animate.camera_at
    animate.camera_at = lambda *a: seen.append(real(*a)) or seen[-1]
    try:
        animate.Scene(sheet).frame(10)                                       # at 1 s: he's just come on
        animate.Scene(sheet).frame(5)                                        # halfway there, before he has
    finally:
        animate.camera_at = real
    (arrived, _), (halfway, _) = seen
    assert arrived[0] == pytest.approx(stage.spot("stairs_top")[0])
    assert halfway[0] == pytest.approx((stage.spot("door_left")[0] + stage.spot("stairs_top")[0]) / 2, rel=0.05)


def test_the_camera_stays_inside_the_picture():
    frame = Image.new("RGB", (1920, 1080))
    assert draw.view(frame, (0, 0), 2.0, (192, 108)).size == (192, 108)
    assert draw.view(frame, (1920, 1080), 0.5, (192, 108)).size == (192, 108)  # zoom under 1 is a full view


# --- staging the story (phase 21) ---

def _gate_stage(tmp_path: Path, see_through: bool) -> Stage:
    """A light picture with a gate of dark vertical bars across x 400-800, y 300-700 (it meets the ground at 700)."""
    place = tmp_path / "gate.png"
    img = Image.new("RGB", (1200, 1000), (200, 200, 190))
    d = ImageDraw.Draw(img)
    for x in range(400, 801, 40):
        d.rectangle((x, 300, x + 8, 700), fill=(25, 25, 30))
    img.save(place)
    return Stage.from_percent(place, {
        "floor": [{"x": 50, "y": 95, "height": 40}, {"x": 50, "y": 60, "height": 20}],
        "spots": [{"name": "gate", "x": 50, "y": 75}, {"name": "outside_gate", "x": 50, "y": 62}],
        "occluders": [{"name": "gate", "base_y": 70, "see_through": see_through,
                       "polygon": [{"x": 33, "y": 30}, {"x": 67.5, "y": 30}, {"x": 67.5, "y": 70}, {"x": 33, "y": 70}]}],
        "light": {"x": 50, "y": 10, "warm": False}})


def test_a_see_through_gate_hides_only_its_bars(tmp_path):
    """Video 5: Mr. Ashford begged at the gate from inside the walls: the map had no ground beyond the bars, and
    an occluder hid everything behind it."""
    bars = _gate_stage(tmp_path, True)
    piece, (x0, y0) = draw.cutout(Image.open(bars.picture).convert("RGB"), bars.occluders[0]["polygon"], True)
    assert piece.getpixel((402 - x0, 500 - y0))[3] == 255                    # a bar is drawn over whoever's behind
    assert piece.getpixel((420 - x0, 500 - y0))[3] == 0                      # a gap shows them
    solid = _gate_stage(tmp_path, False)
    piece, (x0, y0) = draw.cutout(Image.open(solid.picture).convert("RGB"), solid.occluders[0]["polygon"])
    assert piece.getpixel((420 - x0, 500 - y0))[3] == 255
    assert bars.behind(*bars.spot("outside_gate"))["name"] == "gate" and bars.behind(*bars.spot("gate")) is None
    assert "on the far side of the gate, seen through it" in sheets.stage_text(bars)
    bars.save(tmp_path / "stage.json")
    assert Stage.load(tmp_path / "stage.json").occluders[0]["see_through"] is True
    data = {"floor": [{"x": 50, "y": 95, "height": 40}] * 3, "spots": [{"name": "outside_gate", "x": 50, "y": 62, "what": ""}],
            "occluders": [{"name": "gate", "base_y": 70, "see_through": True,
                           "polygon": [{"x": 33, "y": 30}, {"x": 67, "y": 30}, {"x": 67, "y": 70}, {"x": 33, "y": 70}]}],
            "light": {"x": 50, "y": 10, "warm": False}}
    assert checks.stage_map(data) == []                                      # a spot beyond the bars is fine
    data["occluders"][0]["see_through"] = False
    assert any("solid" in p for p in checks.stage_map(data))                 # beyond a solid one it would be hidden
    for p in data["occluders"][0]["polygon"]:                                # unless it's a low wall: a person
        p["y"] = max(p["y"], 50)                                             # there (40% tall, head at 22) shows
    assert checks.stage_map(data) == []                                      # head and shoulders over its top at 50


def test_a_crowd_is_drawn_about_its_spot_out_of_step(tmp_path):
    """Video 5 had no zombies on screen: only the cast had puppets."""
    puppet, _ = _puppet(tmp_path)
    stage = _place(tmp_path)
    sheet = {"figures": [{"who": "the stick figure", "actions": [{"from_ms": 0, "to_ms": 2000, "do": "stand",
                                                                  "at": "door_left"}]}],
             "crowds": [{"who": "the dead", "count": 5, "from_ms": 0, "to_ms": 2000, "do": "limp",
                         "start": "stairs_top", "end": "middle", "facing": "left"}],
             "set": [], "camera": [{"at_ms": 0, "center": "middle", "zoom": 1.0}], "light": {"time": "day", "lamp": ""}}
    assert sheets.check(sheet, stage, ["the stick figure"], [], 2000, ["the dead"]) == []
    out = sheets.resolve(sheet, stage, {"hero": puppet, "the-dead": puppet}, None, {}, 2000, 10)
    dead = [f for f in out["figures"] if f["who"].startswith("the-dead#")]
    assert len(dead) == 5 and all(f["who"] in out["puppets"] for f in dead)
    assert len({tuple(round(v) for v in f["actions"][0]["start"]) for f in dead}) == 5   # a step apart
    assert len({f["actions"][0]["phase"] for f in dead}) == 5                              # and out of step
    assert len({out["puppets"][f["who"]].scale for f in dead}) > 1
    lone = animate.Scene({**out, "figures": out["figures"][:1]}).frame(5)
    assert _ink(animate.Scene(out).frame(5)) > _ink(lone) * 3
    bad = {**sheet, "crowds": [{**sheet["crowds"][0], "who": "aliens", "count": 30}]}
    problems = sheets.check(bad, stage, ["the stick figure"], [], 2000, ["the dead"])
    assert any("aliens" in p for p in problems) and any("30" in p for p in problems)
    still = {**sheet, "crowds": [{"who": "the dead", "count": 3, "from_ms": 0, "to_ms": 2000, "do": "reach"}]}
    assert any("needs `at`" in p for p in sheets.check(still, stage, ["the stick figure"], [], 2000, ["the dead"]))
    assert "a crowd of 5 the dead: ended at middle, limp" in sheets.summary(sheet, {})


def test_someone_turned_takes_the_head_and_hands_of_the_dead(tmp_path):
    """Video 5, scene 48: Mr. Ashford came back to the gate one of the dead, and his puppet didn't change."""
    puppet, _ = _puppet(tmp_path)
    red = Image.new("RGBA", (40, 40), (220, 30, 30, 255))
    dead = parts.Puppet(tmp_path, {"head": parts.Part("head", red, (20, 40), 0.27, "head", "front"),
                                   "hand": parts.Part("hand", red, (20, 20), 0.085, "hand", "front")})
    turned = puppet.wearing("now one of the dead: grey-green round head, the filthy torn navy suit", dead)
    assert turned["head"] is dead["head"] and turned["hand"] is dead["hand"]
    assert "head_side" not in turned and turned["scarf"] is puppet["scarf"]   # still in their own clothes
    assert puppet.wearing("a soaked bandage on his left forearm", dead)["head"] is puppet["head"]


def test_someone_inside_a_vehicle_isnt_drawn_and_a_hovering_one_is_raised(tmp_path):
    """Video 5: the pilot and the hero stood in front of the helicopter, which sat on the pad while it hovered."""
    puppet, _ = _puppet(tmp_path)
    kit = _props(tmp_path)
    stage = _place(tmp_path)
    actions = [{"from_ms": 0, "to_ms": 1000, "do": "walk", "start": "door_left", "end": "stairs_top"},
               {"from_ms": 1000, "to_ms": 3000, "do": "inside", "at": "stairs_top"}]
    assert animate.figure_at(stage, puppet, actions, 500) is not None
    assert animate.figure_at(stage, puppet, actions, 2000) is None
    scene = animate.Scene({"stage": stage, "puppets": {"hero": puppet, "pilot": puppet}, "props": kit,
                           "duration_ms": 3000, "fps": 10, "set": {"drill": {"at": "middle", "lift": 1.0}},
                           "figures": [{"who": "hero", "actions": actions},
                                       {"who": "pilot", "actions": [{"from_ms": 0, "to_ms": 3000, "do": "inside",
                                                                     "at": "stairs_top"}]}],
                           "camera": [{"at_ms": 0, "center": "pilot", "zoom": 1.5}]})
    scene.frame(20)                                                           # the camera finds the pilot inside
    _, part, at, H, _, ground = scene.placed[0]
    assert at[1] == pytest.approx(ground[1] - 1.0 * H)                        # up off the ground; its shadow stays
    high = animate.Scene({**scene.sheet, "set": {"drill": {"at": "middle", "lift": 4.0}}}).placed[0][2]
    assert high[1] - part.pivot[1] / part.image.height * part.height * H > 0  # never off the top of the picture
    two = {"figures": [{"who": "the stick figure", "actions": [{"from_ms": 0, "to_ms": 3000, "do": "inside", "at": "middle"}]},
                       {"who": "Eli", "actions": [{"from_ms": 0, "to_ms": 3000, "do": "inside", "at": "middle"}]}],
           "set": [{"place": "plate", "at": "middle", "angle": 0, "lift": 9}],
           "camera": [{"at_ms": 0, "center": "middle", "zoom": 1.2}], "light": {"time": "day", "lamp": ""}}
    problems = sheets.check(two, stage, ["the stick figure", "Eli"], ["plate"], 3000)
    assert not any("both stand" in p for p in problems)                      # two can ride in one
    assert any("lift" in p for p in problems)

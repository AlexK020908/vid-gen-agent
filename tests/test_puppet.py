"""The cutout puppets (puppet/): parts cut from a sheet, the rig's poses, a stage map, props placed and held,
set state carried between scenes, foreground cutouts, and a scene rendered."""
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from core import config
from providers.images import StubImages
from providers.llm import StubLLM
from puppet import animate, draw, parts, props, rig, state
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


def test_the_camera_stays_inside_the_picture():
    frame = Image.new("RGB", (1920, 1080))
    assert draw.view(frame, (0, 0), 2.0, (192, 108)).size == (192, 108)
    assert draw.view(frame, (1920, 1080), 0.5, (192, 108)).size == (192, 108)  # zoom under 1 is a full view

"""End-to-end pipeline tests with stub providers (real ffmpeg, no network, $0)."""
import json
import time

import pytest

from core import actions, db
from core.context import make_ctx
from core.engine import Engine
from core.errors import ActionError, StateError
from providers.llm import STUB_CAST, STUB_PLACES

STUB_LOOK = STUB_CAST["look"]


@pytest.fixture
def ctx(tmp_path):
    return make_ctx(data_dir=tmp_path, overrides={"mode": "stub", "stub": {"scenes": 6},
                                                  "engine": {"retry_backoff_s": 0}, "render": {"engine": "ffmpeg"}, "topics": {"competitors": "off"}})


def run(ctx) -> None:
    Engine(ctx).run_until_idle()


def video(ctx, vid):
    with ctx.connect() as conn:
        return db.get_video(conn, vid)


def scenes(ctx, vid):
    with ctx.connect() as conn:
        return {s["idx"]: s for s in db.scenes_for(conn, vid)}


def cards(ctx, vid, kind, status=None):
    sql = "SELECT * FROM messages WHERE video_id = ? AND json_extract(card_json, '$.kind') = ?"
    params = [vid, kind]
    if status:
        sql += " AND card_status = ?"
        params.append(status)
    with ctx.connect() as conn:
        return conn.execute(sql + " ORDER BY id", params).fetchall()


def to_render_review(ctx, vid) -> None:
    run(ctx)
    actions.approve(ctx, vid, "outline")
    run(ctx)
    if video(ctx, vid)["state"] == "scripted":
        actions.approve(ctx, vid, "script")
        run(ctx)
    assert video(ctx, vid)["state"] == "assembled"


def test_full_flow(ctx):
    vid = actions.new_video(ctx, "zombie", "Day 1 to Day 365 on an oil rig")
    run(ctx)
    assert video(ctx, vid)["state"] == "outlined"
    assert len(cards(ctx, vid, "outline", "active")) == 1

    actions.revise(ctx, vid, "outline", "open on the storm")
    run(ctx)
    v = video(ctx, vid)
    assert v["state"] == "outlined"
    assert "open on the storm" in json.loads(v["outline_json"])["hook"]
    assert [c["card_status"] for c in cards(ctx, vid, "outline")] == ["revised", "active"]

    actions.approve(ctx, vid, "outline")
    run(ctx)
    assert video(ctx, vid)["state"] == "scripted"  # zombie channel has the script gate on
    actions.approve(ctx, vid, "script")
    run(ctx)

    v = video(ctx, vid)
    assert v["state"] == "assembled"
    for col in ("video_path", "highlight_path", "srt_path"):
        assert ctx.abs(v[col]).exists(), col
    chapters = json.loads(v["chapters_json"])
    assert chapters[0]["t_ms"] == 0 and len(chapters) >= 3
    assert all(s["state"] == "ok" for s in scenes(ctx, vid).values())
    assert len(cards(ctx, vid, "render", "active")) == 1

    with pytest.raises(ActionError, match="pick a title"):
        actions.approve(ctx, vid, "render")

    before = scenes(ctx, vid)
    actions.flag_scenes(ctx, vid, [1], "visual", "darker sky")
    run(ctx)
    after = scenes(ctx, vid)
    assert video(ctx, vid)["state"] == "assembled"
    assert after[1]["regen_count"] == 1 and "darker sky" in after[1]["visual_prompt"]
    assert after[1]["still_path"] != before[1]["still_path"]
    assert after[2]["still_path"] == before[2]["still_path"]  # untouched scenes are not regenerated

    actions.flag_scenes(ctx, vid, [2], "narration", "say it calmer")
    run(ctx)
    after2 = scenes(ctx, vid)
    assert "say it calmer" in after2[2]["narration"]
    assert after2[2]["audio_path"] != after[2]["audio_path"]
    assert after2[2]["still_path"] == after[2]["still_path"]  # narration fix keeps the picture

    actions.pick(ctx, vid, title_idx=1, thumb_idx=2)
    actions.approve(ctx, vid, "render")
    assert video(ctx, vid)["state"] == "render_approved"
    assert len(cards(ctx, vid, "publish", "active")) == 1

    with pytest.raises(ActionError, match="title is empty"):
        actions.request_publish(ctx, vid, title="  ")
    actions.request_publish(ctx, vid, title="Day 1 to Day 365 on an Oil Rig")
    run(ctx)
    v = video(ctx, vid)
    assert v["state"] == "scheduled" and v["youtube_id"] == f"stub-{vid}"
    request = json.loads((ctx.media(vid) / "publish_request.json").read_text(encoding="utf-8"))
    status = request["videos.insert"]["status"]
    assert status["privacyStatus"] == "private" and status["containsSyntheticMedia"] is True
    assert request["videos.insert"]["snippet"]["title"] == "Day 1 to Day 365 on an Oil Rig"

    with ctx.connect() as conn:
        db.update_video(conn, vid, publish_at=time.time() - 1)
    run(ctx)
    assert video(ctx, vid)["state"] == "live"


def test_stills_are_drawn_from_place_and_cast_pictures(ctx):
    """The stub script has 4 beats here (2, 2, 1 and 1 scenes), alternating between the shelter and the street.
    The shelter is barricaded in scene 1, and Rosa is in beats 2 and 3 (scenes 3 to 5)."""
    calls, real = [], {}
    for name in ("still", "place", "change_place", "person"):
        real[name] = getattr(ctx.images, name)
        setattr(ctx.images, name, lambda *a, _name=name, **k: calls.append((_name, a, k)) or real[_name](*a, **k))
    vid = actions.new_video(ctx, "zombie", "A week in a flooded town")
    to_render_review(ctx, vid)

    places = {a[1]: a[3] for name, a, _ in calls if name == "place"}  # each drawn once, however many scenes
    assert sorted(places) == ["the shelter", "the street outside"]
    [change] = [a for name, a, _ in calls if name == "change_place"]
    assert change[1] == places["the shelter"] and change[2] == "a cot is pushed against the steel door"
    assert [a[1] for name, a, _ in calls if name == "person"] == ["Rosa"]
    stills = {int(a[2].split("scene ")[1]): k for name, a, k in calls if name == "still"}
    shelter_v0, shelter_v1 = stills[1]["place"][2], stills[5]["place"][2]  # scene 5 comes after the change
    assert "_v0_" in shelter_v0.name and "_v1_" in shelter_v1.name and all(p.exists() for p in (shelter_v0, shelter_v1))
    assert stills[2]["place"] == ("the shelter", STUB_PLACES[0]["look"], None)  # a close-up: the place in words
    assert stills[3]["place"][0] == "the street outside" and stills[3]["people"][0][:2] == ("Rosa", STUB_LOOK)
    assert stills[6]["people"] == []
    backpack = stills[1]["hero"]  # put on in scene 1 and still on in scene 6
    assert backpack[0] == "a red backpack" and backpack[1].name.startswith("look_the-stick-figure_")
    assert stills[6]["hero"] == backpack
    with ctx.connect() as conn:
        sets = {r["stage"]: r["n"] for r in conn.execute(
            "SELECT stage, COUNT(*) AS n FROM costs WHERE video_id = ? AND stage IN ('sets', 'stills') GROUP BY stage",
            (vid,))}
    assert sets == {"sets": 5, "stills": 6}


def test_next_part_carries_the_story_cast_places_and_looks_on(ctx):
    vid = actions.new_video(ctx, "zombie", "A week in a flooded town")
    with pytest.raises(ActionError, match="once this video's script is approved"):
        actions.next_part(ctx, vid)
    to_render_review(ctx, vid)
    calls, real = [], {}
    for name in ("place", "change_place", "person", "change_look"):
        real[name] = getattr(ctx.images, name)
        setattr(ctx.images, name, lambda *a, _name=name, **k: calls.append((_name, a)) or real[_name](*a, **k))

    nxt = actions.next_part(ctx, vid, "they reach the boat")
    with pytest.raises(ActionError, match=f"#{nxt} is already the next part"):
        actions.next_part(ctx, vid)
    to_render_review(ctx, nxt)

    v = video(ctx, nxt)
    outline = json.loads(v["outline_json"])
    assert v["part"] == 2 and v["prev_video_id"] == vid and outline["part"] == 2
    assert outline["topic"] == "A week in a flooded town (Part 2)" and outline["hook"].startswith("Part 2. Previously:")
    assert all(t.endswith("(Part 2)") for t in json.loads(v["thumbs_json"])["titles"])
    # the places, Rosa and the main character's backpack were drawn for part 1, so part 2 copies them; only the
    # shelter's second barricade (part 2's own change, on top of part 1's) is new
    assert [name for name, _ in calls] == ["change_place"]
    shelter = next(p for p in json.loads(v["places_json"]) if p["id"] == "shelter")
    assert shelter["changes"] == ["a cot is pushed against the steel door"] * 2
    first = scenes(ctx, nxt)[1]
    assert first["place_v"] == 1  # drawn as part 1 left it
    assert json.loads(first["looks_json"]) == {"the stick figure": ["a red backpack"]}


def test_status_box_shows_new_days_and_moved_amounts():
    from stages.assemble import statuses
    tracker = [{"item": "Water", "unit": "L", "start": 20}, {"item": "Food", "unit": "days", "start": 14}]

    def row(label, *amounts):
        return {"label": label, "tracker_json": json.dumps(
            [{"item": item, "amount": a} for item, a in zip(("Water", "Food"), amounts)])}

    boxes = statuses([row("Day 30", 0.5, 0), row("Day 30"), row("Day 1", 20, 14), row("Day 1"), row("Day 1", 17, 14),
                      row("Day 2")], tracker)
    assert boxes[0] == {"day": "Day 30", "rows": [
        {"item": "Water", "amount": "0.5", "unit": "L", "change": None, "down": False},
        {"item": "Food", "amount": "0", "unit": "days", "change": None, "down": False}]}
    assert boxes[1] is None and boxes[3] is None
    assert [r["change"] for r in boxes[2]["rows"]] == [None, None]  # the story starts again: no jump from the cold open
    assert boxes[4]["rows"] == [{"item": "Water", "amount": "17", "unit": "L", "change": "▼ 3", "down": True},
                                {"item": "Food", "amount": "14", "unit": "days", "change": None, "down": False}]
    assert boxes[5] == {"day": "Day 2", "rows": [
        {"item": "Water", "amount": "17", "unit": "L", "change": None, "down": False},
        {"item": "Food", "amount": "14", "unit": "days", "change": None, "down": False}]}
    assert statuses([row("Day 1"), row("Day 1"), row("Day 2")], []) == [{"day": "Day 1", "rows": []}, None,
                                                                         {"day": "Day 2", "rows": []}]


def test_script_gate_off_goes_straight_to_generation(ctx):
    ctx.config.channels["zombie"].gates = ["outline", "render"]
    vid = actions.new_video(ctx, "zombie", "Gate off")
    run(ctx)
    actions.approve(ctx, vid, "outline")
    run(ctx)
    assert video(ctx, vid)["state"] == "assembled"
    assert not cards(ctx, vid, "script")


def test_clips_downgrade_instead_of_busting_budget(ctx):
    ctx.video.price_per_s = 1000
    vid = actions.new_video(ctx, "zombie", "Budget")
    to_render_review(ctx, vid)
    assert all(s["motion"] == "kenburns" and s["clip_path"] is None for s in scenes(ctx, vid).values())
    assert video(ctx, vid)["cost_usd"] < ctx.channel("zombie").budget_usd


def test_provider_failure_then_retry(ctx):
    real = ctx.images.still
    ctx.images.still = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("fal.ai is down"))
    vid = actions.new_video(ctx, "zombie", "Failure")
    run(ctx)
    actions.approve(ctx, vid, "outline")
    run(ctx)
    actions.approve(ctx, vid, "script")
    run(ctx)
    v = video(ctx, vid)
    assert v["state"] == "failed" and "fal.ai is down" in v["error"] and v["resume_state"] == "generating"
    assert len(cards(ctx, vid, "error", "active")) == 1

    ctx.images.still = real
    actions.retry(ctx, vid)
    run(ctx)
    assert video(ctx, vid)["state"] == "assembled"
    assert [c["card_status"] for c in cards(ctx, vid, "error")] == ["retried"]


def test_scene_blocks_after_three_regens(ctx):
    vid = actions.new_video(ctx, "zombie", "Blocked")
    to_render_review(ctx, vid)
    for _ in range(3):
        actions.flag_scenes(ctx, vid, [3], "visual", "still wrong")
        run(ctx)
    actions.flag_scenes(ctx, vid, [3], "visual", "still wrong")
    assert video(ctx, vid)["state"] == "blocked"
    actions.edit_scene(ctx, vid, 3, visual_prompt="stick figure on the rig at dusk")
    actions.retry(ctx, vid)
    run(ctx)
    assert video(ctx, vid)["state"] == "assembled"
    assert scenes(ctx, vid)[3]["visual_prompt"] == "stick figure on the rig at dusk"


def test_edit_scene_prompt_and_line_redoes_both(ctx):
    vid = actions.new_video(ctx, "zombie", "Hand edit")
    to_render_review(ctx, vid)
    before = scenes(ctx, vid)[2]
    actions.edit_scene(ctx, vid, 2, visual_prompt="stick figure on the roof", narration="Day 2. I moved upstairs.")
    run(ctx)
    after = scenes(ctx, vid)[2]
    assert video(ctx, vid)["state"] == "assembled"
    assert after["narration"] == "Day 2. I moved upstairs."
    assert after["still_path"] != before["still_path"] and after["audio_path"] != before["audio_path"]


def test_edit_outline(ctx):
    vid = actions.new_video(ctx, "zombie", "Edits")
    run(ctx)
    titles = [b["title"] for b in json.loads(video(ctx, vid)["outline_json"])["beats"]]
    actions.edit_outline(ctx, vid, [{"op": "move_beat", "beat": 1, "to": 2},
                                    {"op": "set_hook", "text": "The storm hits at 3am."}])
    o = json.loads(video(ctx, vid)["outline_json"])
    assert [b["title"] for b in o["beats"]][:2] == [titles[1], titles[0]]
    assert o["hook"] == "The storm hits at 3am."
    assert [c["card_status"] for c in cards(ctx, vid, "outline")] == ["superseded", "active"]


def test_guards(ctx):
    vid = actions.new_video(ctx, "zombie", "Guards")
    with pytest.raises(StateError):
        actions.approve(ctx, vid, "outline")  # nothing to approve yet
    with pytest.raises(ActionError):
        actions.request_publish(ctx, vid)
    with pytest.raises(ActionError, match="needs a note"):
        actions.revise(ctx, vid, "outline", " ")
    to_render_review(ctx, vid)
    with pytest.raises(ActionError, match="no scene 99"):
        actions.flag_scenes(ctx, vid, [99], "visual")
    with pytest.raises(ActionError, match="say how"):
        actions.flag_scenes(ctx, vid, [1], "narration", "")

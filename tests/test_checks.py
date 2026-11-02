"""The checks on what Claude writes (providers/checks.py): each problem named in words the writer can act on."""
from providers import checks
from replies import PLACES, outline_data, script_data


def test_checks_name_each_problem():
    outline = outline_data()
    script = script_data(outline)["scenes"]
    assert checks.script(script, outline, 8, PLACES) == []
    script[4]["narration"] = " ".join(["word"] * 52)
    script[1]["motion"] = "clip"           # scene 2 is in beat 1, a hero beat: allowed
    script[6]["motion"] = "clip"           # scene 7 is in beat 2, which isn't
    script[30]["label"] = "Day 2"          # goes back in time
    script[31]["label"] = "Tuesday"
    script = [s for s in script if s["beat"] != 9]
    problems = checks.script(script, outline, 4, PLACES)
    assert "scene 5's narration is 52 words; keep each scene to 30 to 40" in problems
    assert "scene 7 is a clip in beat 2, which isn't a hero beat" in problems
    assert any("goes back in time" in p for p in problems)
    assert any("label 'Tuesday'" in p for p in problems)
    assert "beat 9 has no scenes" in problems
    assert "there are 5 clip scenes; this channel allows 4" in problems

    short = [s for n, s in enumerate(script_data(outline)["scenes"]) if n not in (19, 20)]  # hero beat 4 keeps 4
    assert checks.script(short, outline, 8, PLACES) == [
        "beat 4 is a hero beat but has only 4 scenes; give it 7 to 9, with the build-up, the moment and the aftermath"]

    told = lambda *labels: [{"label": label} for label in labels]  # noqa: E731
    assert checks._every_day(told("Day 1", "Day 1", "Day 2-4", "Day 5", "Day 9", "Day 10 to 15", "Day 17")) == [
        "scene 5 jumps from Day 5 to Day 9, skipping Days 6 to 8; tell every day, on its own or a few quiet ones "
        "together, like \"Day 6-8\"",
        "scene 6 tells 6 days at once (Day 10 to 15); keep a stretch to 3 days",
        "scene 7 jumps from Day 10 to 15 to Day 17, skipping Day 16; tell every day, on its own or a few quiet ones "
        "together, like \"Day 16\""]
    assert checks._every_day(told("Day 30", "Day 1", "Day 2"), 1) == []  # after a cold open
    assert checks._every_day(told(*[f"Day {d}-{d + 4}" for d in range(1, 50, 5)])) == []  # 50 days: 5 at once
    assert checks._every_day(told("Week 1", "Week 3")) == []  # weeks and months aren't checked

    o = outline_data(n=9, heroes=2)
    o["beats"][5]["skill"] = o["beats"][2]["skill"]
    problems = checks.outline(o)
    assert "2 beats are hero beats; it needs 3 to 4" in problems
    assert any("beat 6 teaches the same skill as beat 3" in p for p in problems)
    assert checks.titles(["A", "a", "x" * 101]) == ["title 3 is 101 characters; YouTube allows 100",
                                                     "two titles are the same"]

    # a cold open may start on a later day once, within the first scenes; after that, time only moves forward
    labels = lambda *days: [(f"scene {n}", f"Day {d}") for n, d in enumerate(days, 1)]  # noqa: E731
    assert checks._timeline(labels(30, 30, 1, 2, 5), checks.COLD_OPEN_SCENES) == []
    assert checks._timeline(labels(30, 1, 2, 1), checks.COLD_OPEN_SCENES) == ["scene 4: Day 1 comes after Day 2, which "
                                                                              "goes back in time"]
    late = labels(1, 2, 3, 4, 5, 6, 7, 2)
    assert checks._timeline(late, checks.COLD_OPEN_SCENES) == ["scene 8: Day 2 comes after Day 7, which goes back in time"]
    assert checks._timeline(labels(30, 1)) == ["scene 2: Day 1 comes after Day 30, which goes back in time"]  # outlines
    assert checks.description("Open cold on the worst moment, then rewind to the promise: a SEAL with an arsenal who can "
                              "barely walk, thirty days to cover two miles to the last convoy out of the city.") == [
        "the description reads like the outline's note (\"open cold\"); write it for viewers"]
    assert checks.description("Too short.") == ["the description is 10 characters; keep it to 150 to 900"]
    assert checks.description("You're a Navy SEAL sent home with a rebuilt knee the week the dead came. Thirty days, two "
                              "miles to the last convoy, and everyone on the street has seen your cane. Told day by "
                              "day from Day 1, a stick-figure zombie survival story.") == []
    assert checks.thumb_texts(["NO WATER LEFT", "ALONE", "HE WASN'T ALONE AT ALL", "WHY 🔥 NOW"]) == [
        "there are 4 thumb_texts; it needs 3", "thumb_text 2 is 1 word; keep it to 2 to 4",
        "thumb_text 3 is 5 words; keep it to 2 to 4",
        "thumb_text 4 has characters the thumbnail font can't draw; use plain letters, numbers and ! ? ' - : . , & $ %"]


def test_continuity_checks_name_each_problem():
    outline = outline_data()
    scenes = script_data(outline)["scenes"]  # 6 scenes a beat: beat 2 is scenes 7 to 12, on the street, with Rosa
    scenes[6]["move"] = ""                      # scene 7 is on the street after the flat, and doesn't say how
    scenes[12]["move"] = "he flies home"        # scene 13 quotes words its line doesn't have
    scenes[8]["place"] = "roof"
    scenes[36]["cast"] = ["Rosa"]               # scene 37 is in beat 7, which doesn't list her
    scenes[37]["cast"] = ["Ghost"]
    scenes[42]["tracker"] = [{"item": "Water", "amount": -1}]
    scenes[43]["shot"] = "aerial"
    scenes[48]["looks"] = [{"who": "Ghost", "now": " "}]
    for s in scenes:
        if s["beat"] == 3:                      # the last beat that lists Rosa never names her
            s["narration"] = s["narration"].replace("Rosa is here. ", "")
        if s["beat"] == 5:
            s["tracker"] = []
    problems = checks.script(scenes, outline, 8, PLACES + [{"id": "flat", "name": "", "look": "x"}])
    assert problems == [
        "scene 44: shot must be wide, medium or close-up, not 'aerial'",
        "place 3 has no name", "places 1 and 3 have the same id (flat)",
        "scene 7 goes from flat to street, so its move must quote the words in its narration that tell where we are now",
        "scene 9: place 'roof' isn't one of the places",
        "scene 13's move ('he flies home') isn't in its narration word for word",
        "scene 37 shows Rosa, but the outline doesn't list them in beat 7",
        "scene 38 has 'Ghost' in its cast, but the outline's cast has no one by that name",
        "scene 43's tracker lists water; list every tracked item once: food, water",
        "scene 43's tracker has an amount that isn't a number of 0 or more",
        "scene 49's looks names 'Ghost'; use \"the stick figure\" or a cast name",
        "scene 49's look for Ghost has no now; say what they have on, or \"as usual\"",
        "beat 5 never shows the tracker; give the first scene of every beat one",
        "Rosa's part ends in beat 3, the last beat that lists them, but no line in it names them; say there what "
        "happens to them"]

    scenes = script_data(outline)["scenes"]     # a cold open on Day 30 may show her before she comes in
    scenes[0]["label"] = scenes[1]["label"] = "Day 30"
    scenes[0]["cast"] = ["Rosa"]
    assert checks.script(scenes, outline, 8, PLACES) == []
    old = {k: v for k, v in outline.items() if k not in ("cast", "tracker")}  # an outline from before the tracker
    for s in scenes:
        s["cast"], s["tracker"] = [], []
    assert checks.script(scenes, old, 8, PLACES) == []

    o = outline_data()
    o["cast"].append({"name": "rosa ", "look": "", "role": "her twin", "thread": "She waits."})
    o["beats"][4]["cast"] = ["Marco"]
    o["tracker"] = o["tracker"][:1]
    o["backstory"] = " "
    assert checks.outline(o) == [
        "the backstory is empty", "cast member 2 has no look", "cast members 1 and 2 are both called rosa",
        "beat 5 lists 'Marco' in its cast, but the cast has no one by that name",
        "the tracker has 1 item; it needs 2 to 4"]

"""Systems shorts (SHORTS.md, "How a systems short is made"): the spec's checks, the simulation every number on screen
comes from, the layout, the sound, and the DiagramShort render (skipped without render/remotion/node_modules)."""
import copy
import json
import math
import wave
from pathlib import Path

import pytest

from diagram import code, layout, make, sim, sound
from diagram import spec as dspec
from render import ffmpeg, remotion_render

EXAMPLES = Path(__file__).resolve().parent.parent / "diagram" / "examples"
needs_remotion = pytest.mark.skipif(remotion_render.missing() is not None, reason="Remotion isn't installed")


def example(name: str = "cache") -> dict:
    return json.loads((EXAMPLES / f"{name}.json").read_text(encoding="utf-8"))


def balancer() -> dict:
    """One server swamped, a balancer added, then a server failing and found dead."""
    return {
        "title": "HOW A BALANCER HELPS", "layout": "fan_out",
        "nodes": [{"id": "clients", "icon": "client", "label": "CLIENTS", "tone": "green"},
                  {"id": "lb", "icon": "load_balancer", "label": "BALANCER", "tone": "blue"},
                  {"id": "s1", "icon": "server", "label": "Server 1", "tone": "orange", "capacity": 2},
                  {"id": "s2", "icon": "server", "label": "Server 2", "tone": "orange", "capacity": 2}],
        "edges": [["clients", "s1"], ["clients", "lb"], ["lb", "s1"], ["lb", "s2"]],
        "stats": [{"name": "RESPONSE", "unit": "ms", "measure": "response", "base": 40, "per_queued": 50,
                   "good": 50, "bad": 300},
                  {"name": "SERVERS", "measure": "up", "of": ["s1", "s2"]}],
        "phases": [
            {"seconds": 4, "caption": {"text": "One server takes everything"}, "show": ["clients", "s1"],
             "traffic": [{"from": "clients", "to": ["s1"], "rate": 4}]},
            {"seconds": 4, "caption": {"text": "A balancer splits it", "tone": "blue"},
             "show": ["clients", "lb", "s1", "s2"], "edges": [["clients", "lb"], ["lb", "s1"], ["lb", "s2"]],
             "traffic": [{"from": "clients", "via": ["lb"], "to": ["s1", "s2"], "rate": 4, "route": "round_robin"}],
             "code": {"language": "nginx", "lines": ["upstream app {", "  server s1;", "  server s2;", "}"],
                      "bind": {"lb": 1, "s1": 2, "s2": 3}}},
            {"seconds": 2, "caption": {"text": "Server 2 stops answering", "tone": "red"}, "state": {"s2": "failing"}},
            {"seconds": 4, "caption": {"text": "It's taken out", "tone": "green"}, "state": {"s2": "dead"}},
        ],
        "end": {"stat": "RESPONSE", "claim": "one server left standing", "note": "the queue built while it was alone",
                "seconds": 2},
    }


def test_the_examples_pass_every_check():
    assert make.check(example()) == []
    assert make.check(balancer()) == []


def test_a_bad_spec_is_refused_with_what_to_fix():
    s = balancer()
    s["nodes"][0]["icon"] = "satellite"
    s["phases"][0]["caption"]["text"] = "one two three four five six seven"
    s["phases"][1]["code"]["lines"][1] = "  server a_very_long_upstream_host_name;"
    s["edges"].append(["lb", "s9"])
    s["phases"][3] = {"seconds": 4, "caption": {"text": "Server 2 stops answering"}}
    s["phases"][0]["traffic"] = [{"from": "clients", "via": ["lb"], "to": ["s1"], "rate": 4}]
    found = "\n".join(dspec.problems(s))
    assert "icon 'satellite' isn't one of" in found
    assert "the caption is 7 words; at most 6" in found
    assert "code line 2 is 40 characters; at most 32" in found
    assert "edge lb-s9 names s9, which isn't a node" in found
    assert "phase 4 changes nothing from the phase before" in found
    assert "goes through lb, which isn't on screen" in found


def test_too_short_and_too_long_are_refused():
    s = balancer()
    for p in s["phases"]:
        p["seconds"] = 1
    assert any("a systems short is 15 to 45 s" in m for m in dspec.problems(s))


def test_every_number_on_screen_comes_from_the_requests():
    tl = sim.timeline(balancer())
    grid = tl["grid"]
    on_grid = lambda t: abs(t / grid - round(t / grid)) < 1e-6  # noqa: E731
    for a, b, t0, t1, *_ in tl["dots"]:
        assert on_grid(t0) and on_grid(t1) and t1 > t0          # every trip leaves and lands on a sixteenth note
    ticks = [c for c in tl["cues"] if c[1] in ("tick", "code")]
    assert ticks and all(on_grid(c[0]) for c in ticks)            # and every sound of a request is on one too
    for n in tl["nodes"]:
        assert all(v >= 0 for _, v in n["queue"])
        if n["counter"]:
            landed = (sum(1 for d in tl["dots"] if d[1] == n["id"] and d[4] == "req")
                      - sum(1 for f in tl["flashes"] if f[0] == n["id"] and f[2] == "drop"))
            assert n["counts"][-1][1] == landed                  # the counter is the requests that landed there
    s1 = next(n for n in tl["nodes"] if n["id"] == "s1")
    assert max(v for _, v in s1["queue"]) >= 3                    # alone at 4 a second against 2, it queues


def test_a_failing_node_loses_requests_and_a_dead_one_gets_none():
    tl = sim.timeline(balancer())
    failing_from, dead_from = 8.0, 10.0
    lost = [f for f in tl["flashes"] if f[0] == "s2"]
    assert lost and all(failing_from <= f[1] < dead_from + 1 for f in lost)
    late = [d for d in tl["dots"] if d[1] == "s2" and d[2] >= dead_from]
    assert late == []                                             # routing leaves the dead server out
    edge = next(e for e in tl["edges"] if {e["a"], e["b"]} == {"lb", "s2"})
    assert edge["dashed"][-1] == [dead_from, True]
    block = next(b for b in tl["code"]["blocks"] if b["lines"])
    assert [3, dead_from] in block["dims"]                        # its code line dims
    servers = next(s for s in tl["stats"] if s["name"] == "SERVERS")
    assert [st[1] for st in servers["steps"]] == [1, 2, 1]


def _lockstep(tl: dict) -> int:
    """With code on screen: every request landing on a node lights its line at that moment, every request sound is a
    line running at that moment, and every line running sounds. Returns how many landings it checked."""
    blocks = [b for b in tl["code"]["blocks"] if b["lines"]]
    inside = lambda t: next((b for b in blocks if b["from"] <= t < b["to"]), None)  # noqa: E731
    lit = {(round(h[1], 4), h[0]) for b in blocks for h in b["hl"]}
    checked = 0
    for d in tl["dots"]:
        b = inside(d[3])
        if d[4] == "req" and b:
            assert d[1] in b["bind"], f"a request lands on {d[1]} at {d[3]} and no line is bound to it"
            assert (round(d[3], 4), b["bind"][d[1]][0]) in lit, f"{d[1]} at {d[3]}: no line lit"
            checked += 1
    heard = {(round(c[0], 4), c[2]) for c in tl["cues"] if c[1] in ("code", "drop") and inside(c[0])}
    for c in tl["cues"]:
        if c[1] in ("tick", "return", "drop", "code") and inside(c[0]):
            assert c[1] in ("code", "drop") and (round(c[0], 4), c[2]) in lit, f"a {c[1]} at {c[0]} with no line"
    assert lit <= heard, f"lines lit silently: {sorted(lit - heard)[:5]}"
    return checked


def test_every_sound_and_every_request_landing_is_a_line_running():
    """The owner, Nov 9: "make it so that everything lines up, like if there is a sound, or if a request hits db or
    cache, the relevant lines of code executes, not make an AI judge it after, this can be deterministic"."""
    assert _lockstep(sim.timeline(example())) > 50
    assert _lockstep(sim.timeline(balancer())) > 20
    tl = sim.timeline(balancer())
    lost = [h for b in tl["code"]["blocks"] for h in b["hl"] if h[3] == "lost"]
    assert lost and all(h[0] == 3 for h in lost)                    # requests lost at the failing server blink its line


def test_code_on_screen_needs_a_line_for_every_node_a_request_reaches():
    s = example()
    del s["phases"][2]["code"]["bind"]["app"]
    assert any("requests reach app, but no code line is bound to it" in m for m in make.check(s))
    s = balancer()
    del s["phases"][1]["code"]["bind"]["lb"]
    assert any("requests reach lb, but no code line is bound to it" in m for m in make.check(s))


def test_the_end_card_shows_the_pills_worst_and_last():
    tl = sim.timeline(balancer())
    steps = next(s for s in tl["stats"] if s["name"] == "RESPONSE")["steps"]
    worst, last = max(st[1] for st in steps), steps[-1][1]
    assert tl["end"]["before"]["text"] == f"{worst} ms" and tl["end"]["after"]["text"] == f"{last} ms"
    s = balancer()
    s["end"]["claim"] = "back down to 35 ms"
    assert any("says 35 ms, but the RESPONSE pill" in m for m in make.check(s))


def test_the_short_is_whole_bars_and_ends_on_its_first_frame():
    tl = sim.timeline(example())
    bar = 4 * 60 / tl["beat"]
    assert math.isclose(tl["duration"] / bar, round(tl["duration"] / bar), abs_tol=1e-6)
    assert tl["loop"]["to"] == tl["duration"] and math.isclose(tl["loop"]["from"], tl["duration"] - sim.RESET)
    assert tl["end"]["from"] == tl["phases"][-1]["to"]


def test_a_hit_and_a_miss_run_their_lines():
    """The owner, Nov 9: the cache short "never executes the if hit clause". Every request runs cache.get as it reaches
    the cache and the if hit test as the cache answers; a miss's answer runs cache.set then return as it comes back."""
    tl = sim.timeline(example())
    b = next(b for b in tl["code"]["blocks"] if len(b["lines"]) == 6)
    lit = {(round(h[1], 4), h[0]) for h in b["hl"]}
    reach = [round(d[3], 4) for d in tl["dots"] if d[1] == "cache" and d[4] == "req"
             and b["from"] <= d[3] and d[3] + sim.DECIDE < b["to"]]
    assert reach and all((t, 2) in lit and (round(t + sim.DECIDE, 4), 3) in lit for t in reach)
    back = [round(d[3], 4) for d in tl["dots"] if d[1] == "cache" and d[4] == "back"
            and b["from"] <= d[3] and d[3] + tl["grid"] < b["to"]]
    assert back and all((t, 5) in lit and (round(t + tl["grid"], 4), 6) in lit for t in back)


def test_a_line_run_again_blinks_rather_than_staying_lit():
    """The owner, Nov 9: "when a line is executed multiple times, just highlight it (like a blink)"."""
    run = {"lit": [["db", 1.0, False], ["db", 1.25, False], ["db", 1.25, False], ["db", 1.5, True]]}
    phases = [{"code": {"language": "python", "lines": ["def q():", "    return db.query()"], "bind": {"db": 2}},
               "start": 0.0, "end": 3.0, "state": {}}]
    hl = sim._code(phases, run, 3.0, 0.125)["blocks"][0]["hl"]
    assert [h[1] for h in hl] == [1.0, 1.25, 1.5]                  # three blinks (two at once light it once)
    assert [h[2] for h in hl] == [1.25, 1.5, round(1.5 + sim.HOLD + sim.BLINK, 4)]
    assert [h[3] for h in hl] == ["run", "run", "lost"]


def test_badges_say_hit_or_miss_and_how_long_it_took():
    tl = sim.timeline(example())
    said = {(node, text) for node, _, _, text, *_ in tl["badges"]}
    assert {("cache", "HIT"), ("cache", "MISS"), ("users", "20 ms"), ("db", "180 ms"), ("users", "200 ms"),
            ("users", "195 ms")} <= said                                    # app 15 + cache 5; + the query's 180


def test_a_phase_follows_what_its_caption_says():
    tl = sim.timeline(example())
    hit_phase = next(p for p, c in zip(tl["phases"], tl["captions"]) if c["text"] == "A hit answers in 20 ms")
    shown = [text for node, a, z, text, *_ in tl["badges"] if hit_phase["from"] <= a < hit_phase["to"]]
    assert "HIT" in shown and "20 ms" in shown and "MISS" not in shown
    followed = [d for d in tl["dots"] if d[5]]
    assert followed and len(followed) < len(tl["dots"]) / 3               # one request at a time, not all of them


def test_two_badges_at_once_at_a_node_leave_one():
    held = sim._held([["users", 1.0, 1.9, "375 ms", "red"], ["users", 1.0, 1.9, "20 ms", "green"]], 10.0)
    assert [b[3] for b in held if b[2] > b[1]] == ["20 ms"]


def test_a_rate_off_the_beat_is_refused():
    s = example()
    s["phases"][1]["traffic"][0]["rate"] = 5
    assert any("rate 5 would run as 4 a second" in m for m in dspec.problems(s))


def test_too_many_nodes_in_a_column_overlap():
    s = balancer()
    for i in range(3, 8):
        s["nodes"].append({"id": f"s{i}", "icon": "server", "label": f"Server {i}", "tone": "orange"})
        s["edges"].append(["lb", f"s{i}"])
    late = s["phases"][1]
    late["show"] = late["show"] + [f"s{i}" for i in range(3, 8)]
    late["edges"] = late["edges"] + [["lb", f"s{i}"] for i in range(3, 8)]
    assert dspec.problems(s) == []
    assert any("overlap" in m or "doesn't fit" in m for m in make.check(s))


def test_a_node_waiting_queue_gets_room_above_it():
    plain = layout.footprint({"label": "Server 1"}, True, 0)
    queued = layout.footprint({"label": "Server 1"}, True, 9)
    assert queued[1] > plain[1] and queued[2] >= plain[2]


def test_code_is_split_into_coloured_tokens():
    lines = code.tokens("python", ["def get_user(id):", "    return db.query(id)"])
    kinds = {k for line in lines for _, k in line}
    assert ["def ", "keyword"] in lines[0] or ["def", "keyword"] in lines[0]
    assert "keyword" in kinds and "".join(t for t, _ in lines[1]) == "    return db.query(id)"


def test_the_sound_lasts_as_long_as_the_short(tmp_path):
    tl = sim.timeline(balancer())
    out = sound.mix(tl, tmp_path / "s.wav", music=False)
    with wave.open(str(out)) as w:
        assert abs(w.getnframes() / w.getframerate() - tl["duration"]) < 0.01
    bed = sound.bed(2.0, 120)
    assert len(bed) == 2 * sound.RATE and max(abs(v) for v in bed) > 0


def test_phases_carry_on_what_they_dont_change():
    phases = dspec.resolved(balancer())
    assert phases[2]["show"] == phases[1]["show"] and phases[2]["traffic"] == phases[1]["traffic"]
    assert phases[3]["state"] == {"s2": "dead"} and phases[2]["code"] == phases[1]["code"]


@needs_remotion
def test_diagram_short_renders(tmp_path):
    s = copy.deepcopy(example())
    tl = make.render(s, tmp_path / "cache.mp4", music=False)
    out = tmp_path / "cache.mp4"
    assert out.exists() and "1080x1920" in ffmpeg.probe(out)
    assert abs(ffmpeg.duration_ms(out) / 1000 - tl["duration"]) < 0.1
    # make.render has measured the MP4 already (it raises otherwise); and the measure does catch a short out of step
    from diagram import verify
    assert verify.problems(out, out.with_suffix(".sound.wav"), tl) == []
    late = copy.deepcopy(tl)
    for b in late["code"]["blocks"]:
        b["hl"] = [[line, a + 0.2, z + 0.2, kind] for line, a, z, kind in b["hl"]]
    late["cues"] = [[c[0] + 0.2, *c[1:]] if c[1] == "code" else c for c in late["cues"]]
    found = verify.problems(out, out.with_suffix(".sound.wav"), late)
    assert any("with nothing running them" in m for m in found)
    assert any("aren't heard at their moment" in m for m in found)


# --- the pipeline: a `diagram` channel from a topic to the render card ---------------------------------------------------

def _fleet(tmp_path):
    from dataclasses import replace

    from core import config, db
    from core.context import make_ctx
    ctx = make_ctx(data_dir=tmp_path, overrides={
        "mode": "stub", "engine": {"retry_backoff_s": 0}, "topics": {"competitors": "off"}, "render": {"engine": "ffmpeg"}})
    raw = {"id": "systems", "name": "Systems", "scenario_family": "systems: how the machinery behind apps works",
           "format": "diagram", "gates": ["outline", "render"], "budget_usd": 1, "max_seconds": 45,
           "youtube": {"category_id": 28, "tags": ["systems"]}}
    ctx.config.channels["systems"] = replace(config._channel(ctx.config.root, raw), gates=["outline", "render"])
    with ctx.connect() as conn:
        db.sync_channels(conn, ctx.config.channels)
    return ctx


def _video(ctx, vid):
    from core import db
    with ctx.connect() as conn:
        return db.get_video(conn, vid)


@needs_remotion
def test_a_systems_short_runs_from_a_topic_to_its_render_card(tmp_path):
    from core import actions, cards
    from core.engine import Engine
    ctx = _fleet(tmp_path)
    vid = actions.new_video(ctx, "systems", "How a cache saves the database")
    story = actions.new_video(ctx, "zombie", "Day 1 to Day 30 in a flooded subway")
    Engine(ctx).run_until_idle()
    video = _video(ctx, vid)
    assert video["state"] == "outlined"                          # the owner sees the story before it's drawn
    with ctx.connect() as conn:
        card = cards.outline_card(ctx, conn, video)
    assert card["beats"][0]["title"] == "Every visit runs a slow query" and "waiting" in card["beats"][1]["summary"]
    assert card["ending"].startswith("twice the traffic")

    actions.approve(ctx, vid, "outline")
    Engine(ctx).run_until_idle()
    video = _video(ctx, vid)
    assert video["state"] == "assembled" and video["title"] == "How a cache works"
    made = ctx.abs(video["video_path"])
    assert made.exists() and "1080x1920" in ffmpeg.probe(made) and "Audio" in ffmpeg.probe(made)
    assert abs(ffmpeg.duration_ms(made) - video["duration_ms"]) < 100
    assert ctx.abs(video["frames_path"]).exists()
    actions.approve(ctx, vid, "render")                          # the title's already picked: nothing else to choose
    assert _video(ctx, vid)["state"] == "render_approved"
    assert _video(ctx, story)["state"] == "outlined"             # the story channel stops at its own gate, as ever


@needs_remotion
def test_the_look_sends_a_spec_back_once_and_it_goes_straight_to_be_drawn_again(tmp_path, monkeypatch):
    from core import actions, db
    from core.engine import Engine
    from stages import draw
    ctx = _fleet(tmp_path)
    monkeypatch.setattr(draw, "_stub", lambda ctx: False)       # the look runs, as it does for real
    ctx.llm.look_problems = [{"phase": "phase 4", "what": "The caption runs into the code panel.",
                              "fix": "Shorten the caption to four words."}]
    vid = actions.new_video(ctx, "systems", "How a cache saves the database")
    Engine(ctx).run_until_idle()
    actions.approve(ctx, vid, "outline")
    Engine(ctx).run_until_idle()
    video = _video(ctx, vid)
    assert video["state"] == "assembled"                         # back, rewritten and drawn again without a second gate
    with ctx.connect() as conn:
        notes = db.notes(conn, vid, "outline")
        said = [r["text"] for r in conn.execute("SELECT text FROM messages WHERE video_id = ? AND text IS NOT NULL", (vid,))]
    assert any(n.startswith("Look, phase 4: The caption runs into") for n in notes)
    assert any("The look at the frames found 1 thing(s)" in t for t in said)
    assert json.loads(video["outline_json"])["looked"] == 1


def test_a_systems_channel_runs_only_its_own_stages():
    from core import formats
    assert formats.STAGES[formats.DIAGRAM] == ("diagram", "draw", "publish", "analytics")
    assert "diagram" in formats.FORMATS

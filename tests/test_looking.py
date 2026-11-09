"""Claude Code looks (BUILD.md phase 20): picture checks, place maps, part names, the props list and scene sheets are
jobs the session's worker agent answers over MCP, checked as they come in. A stage that parks on one runs again from
the top once it's answered, and pays for nothing twice: each video here is made twice, once with every look answered
on the spot and once through the jobs, and the pictures fal would have been paid for are the same. The writing,
voices and pictures are stubs. $0."""
import json
import time
from collections import Counter

from mcp_types import ImageContent

from core import actions, db, jobs
from core.context import make_ctx
from core.engine import Engine
from providers.llm import NoMeter, StubLLM
from providers.session import LOOKING, SessionLLM
from server import claude_code
from test_session import call as on_one_connection, text
from test_tools import call, result

WRITING = ("outline", "script", "critique", "check_joins", "revise_visual", "rewrite_line", "titles", "topics")
PAID = ("still", "place", "person", "change_place", "change_look", "sheet", "thumbnail")


class Worker(SessionLLM):
    """The session, with the writing from the stub. Each looking call becomes a job as it does for real, and the
    stub's answer to it is kept by the job's key, so a test can answer the jobs as the worker agent would."""

    def __init__(self, config, stub: StubLLM) -> None:
        super().__init__(config, stub, stubbed=WRITING)
        self.stub, self.answers, self._next = stub, {}, None

    def check_picture(self, channel, turn, values, pictures, meter):
        self._next = {"seen": "a placeholder frame", "noticed": [],
                      "problems": self.stub.check_picture(channel, turn, values, pictures, NoMeter())}
        return super().check_picture(channel, turn, values, pictures, meter)

    def map_stage(self, channel, name, picture, meter):
        self._next = self.stub.map_stage(channel, name, picture, NoMeter())
        return super().map_stage(channel, name, picture, meter)

    def name_parts(self, channel, picture, names, meter):
        named = self.stub.name_parts(channel, picture, names, NoMeter())
        self._next = {"seen": "a sheet of parts", "parts": [{"name": n, **p} for n, p in named.items()]}
        return super().name_parts(channel, picture, names, meter)

    def inventory(self, channel, cast, script, have, meter):
        self._next = self.stub.inventory(channel, cast, script, have, NoMeter())
        return super().inventory(channel, cast, script, have, meter)

    def scene_sheet(self, channel, values, context, check, meter):
        self._next = self.stub.scene_sheet(channel, values, context, check, NoMeter())
        return super().scene_sheet(channel, values, context, check, meter)

    def _call(self, kind, system, messages, schema, meter, on_text, verify=None, verify_part=None):
        self.answers[jobs.key(kind, system, jobs.plain(messages), schema)] = json.dumps(self._next)
        return super()._call(kind, system, messages, schema, meter, on_text, verify, verify_part)


class Counting:
    """The image provider, counting the calls fal would be paid for."""

    def __init__(self, images) -> None:
        self.images, self.calls = images, Counter()

    def __getattr__(self, name):
        attr = getattr(self.images, name)
        if name not in PAID:
            return attr

        def counted(*args, **kwargs):
            self.calls[name] += 1
            return attr(*args, **kwargs)
        return counted


def made(tmp_path, name: str, pictures: str, through_jobs: bool, judge=None):
    """A stub video taken to its render card, every look answered on the spot or through the jobs. Returns (ctx,
    video id, fal's calls, the jobs answered by kind)."""
    ctx = make_ctx(data_dir=tmp_path / name, overrides={
        "mode": "stub", "stub": {"scenes": 4}, "engine": {"retry_backoff_s": 0}, "topics": {"competitors": "off"},
        "render": {"engine": "ffmpeg", "pictures": pictures, "puppet_fps": 4}})
    stub = ctx.llm
    stub.judge = judge
    if through_jobs:
        ctx.llm = Worker(ctx.config, stub)
    ctx.images = Counting(ctx.images)
    vid = actions.new_video(ctx, "zombie", "Day 1 to Day 30 in a flooded subway")
    Engine(ctx).run_until_idle()
    actions.approve(ctx, vid, "outline")
    Engine(ctx).run_until_idle()
    actions.approve(ctx, vid, "script")
    done = Counter()
    if through_jobs:
        done = work(ctx)
    else:
        Engine(ctx).run_until_idle()
    return ctx, vid, ctx.images.calls, done


def work(ctx) -> Counter:
    """Runs the engine and answers the looking jobs over MCP as the worker agent does, until none are left."""
    done = Counter()
    while True:
        Engine(ctx).run_until_idle()
        with ctx.connect() as conn:
            waiting = jobs.pending(conn)
        assert all(j["kind"] in LOOKING for j in waiting), [j["kind"] for j in waiting]
        if not waiting:
            return done
        for j in waiting:
            assert not result(ctx, "take_job", {"job_id": j["id"]}).is_error
            said, err = call(ctx, "answer_job", {"job_id": j["id"], "answer": ctx.llm.answers[j["key"]]})
            assert not err, said
            done[j["kind"]] += 1


def video(ctx, vid: int):
    with ctx.connect() as conn:
        return db.get_video(conn, vid)


def notices(ctx, vid: int) -> list[str]:
    with ctx.connect() as conn:
        return [r["text"] or "" for r in conn.execute("SELECT text FROM messages WHERE video_id = ? ORDER BY id", (vid,))]


def test_puppet_assets_and_sheets_are_jobs_and_nothing_is_painted_twice(tmp_path):
    ctx, vid, paid, _ = made(tmp_path, "local", "puppet", through_jobs=False)
    assert video(ctx, vid)["state"] == "assembled", video(ctx, vid)["error"]

    ctx, vid, through, done = made(tmp_path, "jobs", "puppet", through_jobs=True)
    v = video(ctx, vid)
    assert v["state"] == "assembled", v["error"]
    assert through == paid and through["sheet"] >= 2  # the puppets' and the props' sheets, painted once each
    places = {p["id"] for p in json.loads(v["places_json"])}
    assert done["map"] == len(places) and done["sheet"] == 4 and done["inventory"] == 1 and done["parts"] >= 2
    said = notices(ctx, vid)
    assert any("Waiting for Claude Code: the map of" in t for t in said)
    assert any("Waiting for Claude Code: the sheet for scene 4" in t for t in said)
    with ctx.connect() as conn:
        scenes = db.scenes_for(conn, vid)
        spent = conn.execute("SELECT COUNT(*) FROM costs WHERE video_id = ? AND provider = 'llm' AND stage IN "
                             "('assets', 'sheets')", (vid,)).fetchone()[0]
        held = conn.execute("SELECT COUNT(*) FROM claude_jobs WHERE kind = 'sheet' AND scene_id IS NULL").fetchone()[0]
    assert all(s["sheet_json"] and s["state"] == "ok" for s in scenes)
    assert spent == 0 and held == 0  # the session's looking costs nothing; each sheet's job wakes its own scene


def test_picture_checks_park_and_a_redraw_is_paid_for_once(tmp_path):
    judge = lambda values: ["the towel lies beside the knee instead of on it"] if values.get("idx") == 2 else []  # noqa: E731
    ctx, vid, paid, _ = made(tmp_path, "local", "generative", through_jobs=False, judge=judge)
    assert video(ctx, vid)["state"] == "assembled", video(ctx, vid)["error"]
    assert paid["still"] == 5  # scene 2 drawn twice

    ctx, vid, through, done = made(tmp_path, "jobs", "generative", through_jobs=True, judge=judge)
    assert video(ctx, vid)["state"] == "assembled", video(ctx, vid)["error"]
    assert through == paid
    assert done["picture"] == 4 + 1 + paid["change_place"] + paid["change_look"]  # a look at each, scene 2's twice
    assert any("The picture for scene 2 still looks wrong after a second drawing: the towel lies beside the knee "
               "instead of on it." in t for t in notices(ctx, vid))
    assert not list((ctx.media(vid) / "stills").glob("*.try*"))  # each settled drawing is the still; no tries left


def test_a_looking_job_brings_its_pictures(tmp_path):
    ctx = make_ctx(data_dir=tmp_path, overrides={
        "mode": "stub", "stub": {"scenes": 4}, "engine": {"retry_backoff_s": 0}, "topics": {"competitors": "off"},
        "render": {"engine": "ffmpeg", "pictures": "generative"}})
    ctx.llm = Worker(ctx.config, ctx.llm)
    vid = actions.new_video(ctx, "zombie", "Day 1 to Day 30 in a flooded subway")
    Engine(ctx).run_until_idle()
    actions.approve(ctx, vid, "outline")
    Engine(ctx).run_until_idle()
    actions.approve(ctx, vid, "script")
    Engine(ctx).run_until_idle()
    with ctx.connect() as conn:
        [job] = jobs.pending(conn)
    assert job["kind"] == "picture" and job["scene_id"] is not None
    brief = result(ctx, "take_job", {"job_id": job["id"]})
    pictures = [c for c in brief.content if isinstance(c, ImageContent)]
    assert len(pictures) == 2 and pictures[0].mime_type == "image/jpeg"  # the look before, and the redrawn one
    asked = brief.content[0].text
    assert "This is a looking job: the worker agent does these" in asked
    assert "(picture 1, attached)" in asked and "(picture 2, attached)" in asked and '"problems"' in asked
    request = json.loads(job["messages_json"])[0]["content"]
    assert request[0]["type"] == "image" and len(request[0]["sha256"]) == 64 and "data" not in request[0]


def test_wait_returns_at_once_for_what_happened_since_the_last_one(tmp_path):
    ctx = make_ctx(data_dir=tmp_path, overrides={"mode": "stub", "topics": {"competitors": "off"}})
    server = claude_code.make_server(ctx)
    ctx.events.emit("claude_job", None, job_id=1, what="a job someone answered between two waits")
    start = time.monotonic()
    missed, quiet = on_one_connection(server, ("wait", {"seconds": 30}), ("wait", {"seconds": 1}))
    assert time.monotonic() - start < 10  # the first came back at once, the second after its second
    assert json.loads(text(missed))["jobs_waiting"] == [] and not quiet.is_error
    [tool] = [t for t in claude_code.JOB_TOOLS if t.name == "wait"]
    assert tool.input_schema["properties"]["seconds"]["maximum"] == claude_code.WAIT_MAX == 50

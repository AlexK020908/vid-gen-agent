"""The web server: the whole click-through flow over HTTP, live websocket pushes, and the local-only guard."""
import pytest
from fastapi.testclient import TestClient

from agent.harness import OFFLINE, AgentHub
from core.context import make_ctx
from core.engine import Engine
from server.app import create_app


@pytest.fixture
def ctx(tmp_path):
    return make_ctx(data_dir=tmp_path, overrides={"mode": "stub", "stub": {"scenes": 6},
                                                  "engine": {"retry_backoff_s": 0}, "render": {"engine": "ffmpeg"}, "topics": {"competitors": "off"}})


@pytest.fixture
def client(ctx):
    # The engine is driven by hand (run_until_idle) so each step is deterministic. The agent is offline here
    # even if ANTHROPIC_API_KEY is set; tests/test_agent.py drives it with a fake client.
    app = create_app(ctx, run_engine=False, agents=AgentHub(ctx, online=False))
    with TestClient(app, base_url="http://localhost") as c:
        yield c


def run(ctx) -> None:
    Engine(ctx).run_until_idle()


def active(client, thread_id, kind):
    msgs = client.get(f"/api/threads/{thread_id}/messages").json()
    found = [m for m in msgs if m["card"] and m["card"]["kind"] == kind and m["card_status"] == "active"]
    assert len(found) == 1, f"expected one active {kind} card, got {len(found)}"
    return found[0]["card"]


def post(client, path, body=None, status=200):
    r = client.post(path, json=body or {})
    assert r.status_code == status, r.text
    return r.json()


def test_click_through(ctx, client):
    channel = client.get("/api/channels").json()[0]
    assert channel["id"] == "zombie" and channel["home_thread_id"]

    created = post(client, "/api/videos", {"channel_id": "zombie", "idea": "Day 1 to Day 100 on a raft"})
    vid, thread = created["video_id"], created["thread_id"]
    run(ctx)

    assert active(client, thread, "outline")["beats"]
    post(client, f"/api/videos/{vid}/edit_outline", {"ops": [{"op": "set_hook", "text": "The raft tips at dawn."}]})
    assert active(client, thread, "outline")["hook"] == "The raft tips at dawn."
    post(client, f"/api/videos/{vid}/approve", {"gate": "outline"})
    run(ctx)

    assert active(client, thread, "script")["scene_count"] == 6
    post(client, f"/api/videos/{vid}/approve", {"gate": "script"})
    run(ctx)

    render = active(client, thread, "render")
    assert len(render["scenes"]) == 6 and render["scenes"][0]["start_ms"] == 0
    assert client.get(render["scenes"][0]["preview_url"]).status_code == 200
    ranged = client.get(render["video_url"], headers={"Range": "bytes=0-99"})  # the player seeks with ranges
    assert ranged.status_code == 206 and len(ranged.content) == 100

    err = post(client, f"/api/videos/{vid}/approve", {"gate": "render"}, status=409)
    assert "pick a title" in err["detail"]
    post(client, f"/api/videos/{vid}/pick", {"title_idx": 0, "thumb_idx": 1})
    assert active(client, thread, "render")["picked"]["thumb_idx"] == 1
    post(client, f"/api/videos/{vid}/approve", {"gate": "render"})

    publish = active(client, thread, "publish")
    assert publish["privacy"] == "private" and publish["ai_disclosure"] is True
    post(client, f"/api/videos/{vid}/publish_fields", {"tags": ["raft", "survival"]})
    assert active(client, thread, "publish")["tags"] == ["raft", "survival"]
    post(client, f"/api/videos/{vid}/publish", {"title": "I Survived 100 Days on a Raft"})
    run(ctx)

    row = next(t for t in client.get("/api/threads").json() if t["id"] == thread)
    assert row["state"] == "scheduled" and row["waiting"] == 0
    info = client.get(f"/api/videos/{vid}").json()
    assert info["youtube_id"] == f"stub-{vid}" and len(info["scene_list"]) == 6


def test_flag_from_the_render_card(ctx, client):
    vid = post(client, "/api/videos", {"channel_id": "zombie", "idea": "Flags"})["video_id"]
    run(ctx)
    post(client, f"/api/videos/{vid}/approve", {"gate": "outline"})
    run(ctx)
    post(client, f"/api/videos/{vid}/approve", {"gate": "script"})
    run(ctx)
    err = post(client, f"/api/videos/{vid}/flag", {"idxs": [2], "kind": "narration"}, status=409)
    assert "how the line should change" in err["detail"]
    post(client, f"/api/videos/{vid}/flag", {"idxs": [2, 4], "kind": "visual", "note": "darker"})
    run(ctx)
    assert client.get(f"/api/videos/{vid}").json()["state"] == "assembled"


def test_chat_without_the_agent(ctx, client):
    assert client.get("/api/agent").json()["online"] is False
    created = post(client, "/api/videos", {"channel_id": "zombie", "idea": "Chat"})
    msg = post(client, f"/api/threads/{created['thread_id']}/chat", {"text": "make it darker"})
    assert msg["role"] == "user" and msg["video_id"] == created["video_id"]
    texts = [m["text"] for m in client.get(f"/api/threads/{created['thread_id']}/messages").json()]
    assert texts[-2:] == ["make it darker", OFFLINE]
    assert client.post("/api/threads/9999/chat", json={"text": "hi"}).status_code == 404


def test_websocket_pushes_messages_and_threads(ctx, client):
    with client.websocket_connect("ws://localhost/ws") as ws:
        created = post(client, "/api/videos", {"channel_id": "zombie", "idea": "Live"})
        seen = []
        while not any(e["type"] == "message" and e["message"]["text"] == "Writing the outline…" for e in seen):
            seen.append(ws.receive_json())
            assert len(seen) < 20
        threads = [e["thread"] for e in seen if e["type"] == "thread"]
        assert threads and threads[-1]["id"] == created["thread_id"] and threads[-1]["state"] == "new"


def test_local_only(client):
    assert client.get("/api/channels", headers={"Host": "evil.example"}).status_code == 403
    assert client.post("/api/videos/1/retry", headers={"Origin": "https://evil.example"}).status_code == 403
    assert client.get("/api/channels", headers={"Origin": "http://localhost:5173"}).status_code == 200
    with pytest.raises(Exception):
        with client.websocket_connect("ws://localhost/ws", headers={"Origin": "https://evil.example"}) as ws:
            ws.receive_json()

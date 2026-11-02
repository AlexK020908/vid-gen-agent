"""The local server run.py serve starts: the engine, and the MCP endpoint at /mcp that the Claude Code session
connects to (server/claude_code.py). The chat is the only way in; the browser app went in phase 18 (BUILD.md).

There is no login, so the server binds to localhost and refuses requests whose Host or Origin is not
local. Without the Origin check, any web page you visit could call the tools from your browser.
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, suppress
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from core.context import Ctx, make_ctx
from core.engine import Engine
from server import claude_code

LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


def _is_local(hosts: frozenset[str], host: str | None, origin: str | None) -> bool:
    if urlsplit("//" + (host or "")).hostname not in hosts:
        return False
    return origin is None or urlsplit(origin).hostname in hosts


def create_app(ctx: Ctx | None = None, run_engine: bool = True, hosts: frozenset[str] = LOCAL_HOSTS) -> FastAPI:
    ctx = ctx or make_ctx()
    engine = Engine(ctx)
    mcp = claude_code.make_manager(claude_code.make_server(ctx))

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        task = asyncio.create_task(engine.run_forever()) if run_engine else None
        async with mcp.run():
            yield
        engine.stop()
        if task is not None:
            with suppress(asyncio.TimeoutError):
                await asyncio.wait_for(task, timeout=15)

    app = FastAPI(title="Stick Fleet", lifespan=lifespan)
    app.state.ctx = ctx

    @app.middleware("http")
    async def local_only(request: Request, call_next):
        if not _is_local(hosts, request.headers.get("host"), request.headers.get("origin")):
            return JSONResponse({"detail": "local requests only"}, status_code=403)
        return await call_next(request)

    app.add_route("/mcp", claude_code.endpoint(mcp))
    return app

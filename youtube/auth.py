"""Desktop OAuth, one sign-in per channel.

The OAuth client is secrets/client_secret.json (gitignored; Desktop app type). Each channel's refresh token
lives in the OS keychain (Windows Credential Manager via keyring), service "stickfleet-youtube", username =
our channel id; never in YAML, the database or git. Connecting writes youtube.channel_id into the channel's
YAML so you can see which YouTube channel it is bound to.
"""
from __future__ import annotations

import json
import re
import threading
from pathlib import Path

import keyring
import yaml
from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow, WSGITimeoutError
from googleapiclient.discovery import build

from core.errors import ActionError
from youtube import quota

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",
    "https://www.googleapis.com/auth/youtube.readonly",       # Analytics reports.query requires it (Oct 2026)
    "https://www.googleapis.com/auth/yt-analytics.readonly",  # Analytics and the Reporting API's reach report
]
SERVICE = "stickfleet-youtube"
TOKEN_URI = "https://oauth2.googleapis.com/token"
CONNECT_TIMEOUT_S = 300

_cache: dict[str, Credentials] = {}
_lock = threading.Lock()


def secret_path(ctx) -> Path:
    return ctx.config.root / "secrets" / "client_secret.json"


def _client(ctx) -> dict:
    path = secret_path(ctx)
    if not path.exists():
        raise ActionError("no OAuth client yet: save the Desktop app client from Google Cloud as "
                          "secrets/client_secret.json (plan.md, One-time setup)")
    info = json.loads(path.read_text(encoding="utf-8")).get("installed")
    if not info:
        raise ActionError("secrets/client_secret.json isn't a Desktop app OAuth client; "
                          "create one of type Desktop app in Google Cloud and download it again")
    return info


def stored(channel_id: str) -> dict | None:
    raw = keyring.get_password(SERVICE, channel_id)
    return json.loads(raw) if raw else None


def status(ctx, channel_id: str) -> dict:
    """For the sidebar: is there an OAuth client, is this channel signed in, and does the sign-in have every
    scope (a sign-in from before a scope was added needs Connect again)."""
    try:
        token = stored(channel_id)
    except Exception as e:  # keychain unavailable: show it, don't break the channel list
        return {"client_secret": secret_path(ctx).exists(), "connected": False, "title": None, "error": str(e),
                "missing_scopes": []}
    missing = [s.rsplit("/", 1)[-1] for s in SCOPES if token and s not in token.get("scopes", [])]
    return {"client_secret": secret_path(ctx).exists(), "connected": bool(token),
            "title": token.get("title") if token else None, "error": None, "missing_scopes": missing}


def require_connected(ctx, channel_id: str) -> None:
    _client(ctx)
    if not stored(channel_id):
        name = ctx.channel(channel_id).name
        raise ActionError(f"connect {name} to YouTube first: the Connect button next to the channel in the sidebar")


def set_channel_id(path: Path, youtube_channel_id: str) -> None:
    """Write youtube.channel_id into a channel YAML, changing only that line so comments survive."""
    original = path.read_text(encoding="utf-8")
    lines = original.splitlines(keepends=True)
    start = next((i for i, line in enumerate(lines) if re.match(r"youtube:\s*(#.*)?$", line.rstrip())), None)
    if start is None:
        lines += ["" if original.endswith("\n") else "\n", f"youtube:\n  channel_id: {youtube_channel_id}\n"]
    else:
        for i in range(start + 1, len(lines)):
            line = lines[i]
            if line.strip() and not line[0].isspace():
                lines.insert(i, f"  channel_id: {youtube_channel_id}\n")
                break
            m = re.match(r"(\s+channel_id:\s*)(\S*?)(\s*#.*)?$", line.rstrip("\r\n"))
            if m:
                end = line[len(line.rstrip("\r\n")):]
                comment = m.group(3) or ""
                if comment:  # keep the comment where it was if the new value fits
                    column = len(m.group(1)) + len(m.group(2)) + len(comment) - len(comment.lstrip())
                    pad = max(1, column - len(m.group(1)) - len(youtube_channel_id))
                    comment = " " * pad + comment.lstrip()
                lines[i] = f"{m.group(1)}{youtube_channel_id}{comment}{end}"
                break
        else:
            lines.insert(start + 1, f"  channel_id: {youtube_channel_id}\n")
    updated = "".join(lines)
    try:
        ok = (yaml.safe_load(updated) or {}).get("youtube", {}).get("channel_id") == youtube_channel_id
    except yaml.YAMLError:
        ok = False
    if not ok:
        raise ActionError(f"couldn't update {path.name}; set youtube.channel_id: {youtube_channel_id} in it by hand")
    path.write_text(updated, encoding="utf-8")


def connect(ctx, channel_id: str, open_browser: bool = True) -> dict:
    """Run Google's sign-in in the browser, learn which channel was picked, store the token."""
    channel = ctx.channel(channel_id)
    _client(ctx)
    flow = InstalledAppFlow.from_client_secrets_file(str(secret_path(ctx)), SCOPES)
    try:
        creds = flow.run_local_server(
            port=0, open_browser=open_browser, timeout_seconds=CONNECT_TIMEOUT_S, prompt="consent",
            authorization_prompt_message=f"Sign in to YouTube for {channel.name}: {{url}}",
            success_message="Stick Fleet is connected to YouTube. You can close this tab.",
        )
    except WSGITimeoutError:
        raise ActionError("Google sign-in timed out after 5 minutes; click Connect again") from None
    except Exception as e:  # cancelled on Google's screen, or the redirect was refused
        raise ActionError(f"Google sign-in didn't finish: {e}") from e
    granted = creds.granted_scopes or creds.scopes or []
    granted = set(granted.split() if isinstance(granted, str) else granted)
    if missing := [s.rsplit("/", 1)[-1] for s in SCOPES if s not in granted]:
        raise ActionError(f"Google's screen left out {', '.join(missing)}; click Connect again and tick every box")
    if not creds.refresh_token:
        raise ActionError("Google returned no refresh token; click Connect again")

    service = build("youtube", "v3", credentials=creds, cache_discovery=False)
    with ctx.connect() as conn:
        quota.spend(conn, "channels.list")
    items = service.channels().list(part="id,snippet", mine=True).execute().get("items") or []
    if not items:
        raise ActionError("the account you picked has no YouTube channel; click Connect again "
                          "and pick the brand channel on Google's screen")
    youtube_id, title = items[0]["id"], items[0]["snippet"]["title"]
    for other in ctx.config.channels.values():
        if other.id != channel_id and other.youtube.get("channel_id") == youtube_id:
            raise ActionError(f"{title} is already connected to {other.name}; pick a different brand channel")

    keyring.set_password(SERVICE, channel_id, json.dumps(
        {"refresh_token": creds.refresh_token, "scopes": sorted(granted), "youtube_channel_id": youtube_id,
         "title": title}))
    if channel.path:
        set_channel_id(channel.path, youtube_id)
    channel.youtube["channel_id"] = youtube_id
    with ctx.connect() as conn:
        conn.execute("UPDATE channels SET youtube_channel_id = ?, signin_error = NULL WHERE id = ?",
                     (youtube_id, channel_id))
    with _lock:
        _cache.pop(channel_id, None)
    return {"channel_id": channel_id, "youtube_channel_id": youtube_id, "title": title}


def credentials(ctx, channel_id: str) -> Credentials:
    """The channel's credentials, refreshed. A missing or revoked token means connecting again."""
    with _lock:
        cached = _cache.get(channel_id)
        if cached is not None and cached.valid:
            return cached
    token = stored(channel_id)
    if not token:
        raise ActionError(f"Connect the channel again: no YouTube sign-in is stored for {channel_id}")
    client = _client(ctx)
    creds = Credentials(token=None, refresh_token=token["refresh_token"], token_uri=client.get("token_uri", TOKEN_URI),
                        client_id=client["client_id"], client_secret=client["client_secret"], scopes=token["scopes"])
    try:
        creds.refresh(Request())
    except RefreshError as e:
        raise ActionError(f"Connect the channel again: Google refused the stored sign-in ({e})") from e
    with _lock:
        _cache[channel_id] = creds
    return creds

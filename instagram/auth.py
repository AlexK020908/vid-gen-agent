"""The Instagram token, kept in the OS keychain (Windows Credential Manager via keyring), service "stickfleet-instagram",
username "token": never in YAML, .env, the database or git.

It's the system-user token the Meta app "Reel Publisher" issues through its Unified login configuration (Facebook Login for
Business): one token for every Instagram account given to the app, and it never expires. `run.py instagram connect` asks
for it in a hidden prompt.
"""
from __future__ import annotations

import keyring

from core.errors import ActionError

SERVICE = "stickfleet-instagram"
USER = "token"
CONNECT = "uv run python run.py instagram connect"


def token() -> str | None:
    return keyring.get_password(SERVICE, USER) or None


def require() -> str:
    found = token()
    if not found:
        raise ActionError(f"no Instagram token yet: make one in the Meta app (API setup with Unified login, Generate access "
                          f"tokens), then run `{CONNECT}` in a terminal and paste it there")
    return found


def store(value: str) -> None:
    value = value.strip()
    if not value:
        raise ActionError("the token is empty")
    keyring.set_password(SERVICE, USER, value)

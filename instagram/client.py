"""Meta's Graph API for Instagram, and its upload host, for the few calls a Reel needs.

From Meta's docs (read Nov 9, 2026, API v27.0): a Reel from a local file is a container made with media_type=REELS and
upload_type=resumable, whose bytes go to rupload.facebook.com with `Authorization: OAuth <token>`, `offset` and `file_size`
headers; the container's status_code turns FINISHED, and media_publish with its id posts it. Resumable upload is only for
apps on Facebook Login for Business, which the Unified login setup is. The token never appears in a URL or a message.
"""
from __future__ import annotations

from pathlib import Path

import httpx2

from core.errors import ActionError

GRAPH = "https://graph.facebook.com"
TIMEOUT_S = 60
UPLOAD_TIMEOUT_S = 900
TRANSIENT_CODES = {1, 2, 4, 17, 32, 341, 613}   # Meta's "temporary" and rate-limit codes: try again later
TOKEN_CODES = {102, 190}                         # the token is refused, expired or revoked


class InstagramError(ActionError):
    def __init__(self, message: str, retriable: bool = False, code: int | None = None) -> None:
        super().__init__(message)
        self.retriable = retriable
        self.code = code


def _error(what: str, response: httpx2.Response) -> InstagramError:
    try:
        body = response.json()
    except ValueError:
        body = {}
    err = body.get("error") if isinstance(body, dict) else None
    if isinstance(err, dict):
        code = err.get("code")
        message = err.get("error_user_msg") or err.get("message") or "no message"
        retriable = bool(err.get("is_transient")) or code in TRANSIENT_CODES or response.status_code >= 500
        if code in TOKEN_CODES:
            return InstagramError(f"Meta refused the Instagram token ({message}). Make a new one in the Meta app and run "
                                  f"`uv run python run.py instagram connect`", code=code)
        return InstagramError(f"Instagram {what} failed: {message} (code {code})", retriable=retriable, code=code)
    debug = body.get("debug_info") if isinstance(body, dict) else None   # the upload host's own shape
    if isinstance(debug, dict):
        return InstagramError(f"Instagram {what} failed: {debug.get('message') or debug.get('type')}",
                              retriable=bool(debug.get("retriable")))
    return InstagramError(f"Instagram {what} failed: HTTP {response.status_code}", retriable=response.status_code >= 500)


class Client:
    def __init__(self, token: str, version: str = "v27.0", http: httpx2.Client | None = None) -> None:
        self.token = token
        self.version = version
        self.http = http or httpx2.Client(timeout=TIMEOUT_S)

    def _call(self, what: str, method: str, path: str, **params) -> dict:
        url = f"{GRAPH}/{self.version}/{path}"
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            if method == "GET":
                response = self.http.get(url, params=params, headers=headers)
            else:
                response = self.http.post(url, data=params, headers=headers)
        except httpx2.TransportError as e:
            raise InstagramError(f"Instagram {what}: couldn't reach Meta ({type(e).__name__})", retriable=True) from None
        if response.status_code >= 400:
            raise _error(what, response)
        return response.json()

    # --- reading -------------------------------------------------------------------------------------------------

    def whoami(self) -> dict:
        """Who the token is: for the Unified login token, the app's system user."""
        return self._call("token check", "GET", "me", fields="id,name")

    def account(self, ig_id: str) -> dict:
        return self._call("account lookup", "GET", ig_id, fields="id,username,name,media_count")

    def limit(self, ig_id: str) -> dict:
        """{"quota_usage": posts in the last 24 h, "quota_total": allowed, "quota_duration": seconds}"""
        rows = self._call("publishing limit", "GET", f"{ig_id}/content_publishing_limit",
                          fields="config,quota_usage").get("data") or [{}]
        row = rows[0]
        return {"quota_usage": int(row.get("quota_usage") or 0), **(row.get("config") or {})}

    def status(self, container: str) -> str:
        return self._call("upload check", "GET", container, fields="status_code").get("status_code") or ""

    def why(self, container: str) -> str:
        """Meta's words on a container that failed, if it gives any."""
        try:
            return str(self._call("upload check", "GET", container, fields="status").get("status") or "")
        except InstagramError:
            return ""

    def recent(self, ig_id: str, count: int = 5) -> list[dict]:
        return self._call("recent posts", "GET", f"{ig_id}/media", fields="id,timestamp,caption",
                          limit=count).get("data") or []

    def media(self, media_id: str) -> dict:
        return self._call("post lookup", "GET", media_id, fields="id,permalink,media_product_type,timestamp")

    # --- posting -------------------------------------------------------------------------------------------------

    def create_reel(self, ig_id: str, caption: str, ai_generated: bool, thumb_offset_ms: int | None = None) -> dict:
        """A Reel container for a file uploaded next: {"id", "uri"}."""
        params = {"media_type": "REELS", "upload_type": "resumable", "caption": caption}
        if ai_generated:
            params["is_ai_generated"] = "true"
        if thumb_offset_ms is not None:
            params["thumb_offset"] = str(int(thumb_offset_ms))
        made = self._call("container", "POST", f"{ig_id}/media", **params)
        if not made.get("id") or not made.get("uri"):
            raise InstagramError(f"Instagram container: Meta's reply had no id or upload address ({sorted(made)})")
        return {"id": made["id"], "uri": made["uri"]}

    def upload(self, uri: str, path: Path) -> None:
        data = path.read_bytes()   # at most 300 MB (Meta's limit, checked before); sent whole with its length
        headers = {"Authorization": f"OAuth {self.token}", "offset": "0", "file_size": str(len(data))}
        try:
            response = self.http.post(uri, content=data, headers=headers, timeout=UPLOAD_TIMEOUT_S)
        except httpx2.TransportError as e:
            raise InstagramError(f"Instagram upload: the connection dropped ({type(e).__name__})", retriable=True) from None
        if response.status_code >= 400:
            raise _error("upload", response)
        body = response.json()
        if not body.get("success"):
            raise _error("upload", response)

    def publish(self, ig_id: str, container: str) -> str:
        return self._call("publish", "POST", f"{ig_id}/media_publish", creation_id=container)["id"]

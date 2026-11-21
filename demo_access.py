"""Access code for the online demo: deny by default, allow only the website's own files.

Used by serve.py. Without the right code, nobody who gets the public link can use the
agent, the voice bridge (our Gemini and ElevenLabs credits) or read conversations.

Flow: the website loads (static files are public), the student types the demo code once,
POST /demo-login checks it and sets an HttpOnly, SameSite=Strict cookie. Every other HTTP
request and every WebSocket needs that cookie. A cookie is used instead of a header because
browsers cannot add headers to WebSocket connections, but they do send cookies.
"""
from __future__ import annotations

import hashlib
import hmac
import json
from http.cookies import SimpleCookie
from pathlib import Path

COOKIE = "cosmo_demo"
LOGIN_PATH = "/demo-login"
MAX_AGE_SECONDS = 12 * 3600


def cookie_value(code: str) -> str:
    """The cookie stores a hash of the code, never the code itself."""
    return hashlib.sha256(f"cosmo-demo:{code}".encode()).hexdigest()


class DemoAccessMiddleware:
    """Pure ASGI middleware, so it guards both HTTP requests and WebSockets."""

    def __init__(self, app, code: str, static_dir: Path):
        if not code:
            raise ValueError("DemoAccessMiddleware needs a non-empty access code")
        self.app = app
        self.code = code
        self.expected_cookie = cookie_value(code)
        self.static_dir = static_dir.resolve()

    def _is_public_static(self, scope) -> bool:
        """Only GET/HEAD for '/' or a file that really exists inside the built website."""
        if scope["type"] != "http" or scope.get("method") not in ("GET", "HEAD"):
            return False
        path = scope["path"]
        if path in ("/", "/index.html"):
            return True
        target = (self.static_dir / path.lstrip("/")).resolve()
        return target.is_relative_to(self.static_dir) and target.is_file()

    def _has_valid_cookie(self, scope) -> bool:
        for name, value in scope.get("headers", []):
            if name == b"cookie":
                jar = SimpleCookie()
                try:
                    jar.load(value.decode("latin-1"))
                except Exception:
                    return False
                if COOKIE in jar and hmac.compare_digest(jar[COOKIE].value, self.expected_cookie):
                    return True
        return False

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket"):
            return await self.app(scope, receive, send)  # lifespan etc.
        if scope["type"] == "http" and scope["path"] == LOGIN_PATH:
            return await self._login(scope, receive, send)
        if self._is_public_static(scope) or self._has_valid_cookie(scope):
            return await self.app(scope, receive, send)
        if scope["type"] == "websocket":
            await send({"type": "websocket.close", "code": 4401})  # refuse before accepting
            return
        await _json(send, 401, {"error": "demo access code required"})

    async def _login(self, scope, receive, send):
        if scope.get("method") != "POST":
            return await _json(send, 405, {"error": "use POST"})
        body = b""
        while True:
            message = await receive()
            body += message.get("body", b"")
            if not message.get("more_body") or len(body) > 4096:
                break
        try:
            given = str(json.loads(body or b"{}").get("code", ""))
        except (ValueError, AttributeError):
            given = ""
        if not hmac.compare_digest(given.encode(), self.code.encode()):
            return await _json(send, 401, {"error": "wrong code"})
        secure = _is_https(scope)
        cookie = (f"{COOKIE}={self.expected_cookie}; Path=/; Max-Age={MAX_AGE_SECONDS}; "
                  f"HttpOnly; SameSite=Strict{'; Secure' if secure else ''}")
        await _json(send, 200, {"ok": True}, extra_headers=[(b"set-cookie", cookie.encode())])


def _is_https(scope) -> bool:
    if scope.get("scheme") == "https":
        return True
    for name, value in scope.get("headers", []):
        if name == b"x-forwarded-proto" and value.decode().lower() == "https":
            return True  # the Cloudflare tunnel terminates HTTPS and forwards plain HTTP
    return False


async def _json(send, status: int, payload: dict, extra_headers=None):
    body = json.dumps(payload).encode()
    headers = [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode()),
               (b"cache-control", b"no-store")] + (extra_headers or [])
    await send({"type": "http.response.start", "status": status, "headers": headers})
    await send({"type": "http.response.body", "body": body})

"""Offline tests for demo_access.py (the online demo's access code). Run from the repo root:

    python -m tests.test_demo_access
"""

import tempfile
import warnings
from pathlib import Path

from starlette.applications import Starlette
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.routing import Route, WebSocketRoute

warnings.filterwarnings("ignore")  # starlette's TestClient prints a deprecation warning about httpx
from starlette.testclient import TestClient  # noqa: E402
from starlette.websockets import WebSocketDisconnect  # noqa: E402

from demo_access import COOKIE, DemoAccessMiddleware, cookie_value  # noqa: E402

CODE = "orange-42"


def make_client() -> TestClient:
    site = Path(tempfile.mkdtemp())
    (site / "index.html").write_text("<html>COSMO</html>")
    (site / "assets").mkdir()
    (site / "assets" / "app.js").write_text("console.log('hi')")

    async def run(_request):
        return JSONResponse({"agent": "replied"})

    async def sessions(_request):
        return JSONResponse([{"id": "secret-session"}])

    async def page(_request):
        return PlainTextResponse((site / "index.html").read_text())

    async def asset(_request):
        return PlainTextResponse((site / "assets" / "app.js").read_text())

    async def stt(ws):
        await ws.accept()
        await ws.send_json({"type": "partial", "text": "hello"})
        await ws.close()

    inner = Starlette(routes=[
        Route("/run", run, methods=["POST"]),
        Route("/apps/phone_agent/users/student-web/sessions", sessions),
        Route("/", page), Route("/assets/app.js", asset),
        WebSocketRoute("/voice/ws/stt", stt),
    ])
    return TestClient(DemoAccessMiddleware(inner, code=CODE, static_dir=site))


def test_website_files_are_public():
    c = make_client()
    assert c.get("/").status_code == 200
    assert c.get("/assets/app.js").status_code == 200


def test_api_and_sessions_need_the_code():
    c = make_client()
    assert c.post("/run", json={}).status_code == 401
    assert c.get("/apps/phone_agent/users/student-web/sessions").status_code == 401
    assert c.get("/docs").status_code == 401  # deny by default, even for unknown paths


def test_path_tricks_do_not_reach_the_api():
    c = make_client()
    assert c.get("/assets/../run").status_code in (401, 404)
    assert c.post("/assets/app.js").status_code == 401  # static is GET/HEAD only


def test_wrong_code_is_refused():
    c = make_client()
    r = c.post("/demo-login", json={"code": "wrong"})
    assert r.status_code == 401 and COOKIE not in r.cookies


def test_right_code_sets_a_safe_cookie_and_unlocks_the_api():
    c = make_client()
    r = c.post("/demo-login", json={"code": CODE}, headers={"x-forwarded-proto": "https"})
    assert r.status_code == 200
    header = r.headers["set-cookie"]
    assert "HttpOnly" in header and "SameSite=Strict" in header and "Secure" in header
    assert CODE not in header  # only a hash is stored
    c.cookies.set(COOKIE, cookie_value(CODE))
    assert c.post("/run", json={}).json() == {"agent": "replied"}


def test_forged_cookie_is_refused():
    c = make_client()
    c.cookies.set(COOKIE, "anything")
    assert c.post("/run", json={}).status_code == 401


def test_websocket_needs_the_code():
    c = make_client()
    try:
        with c.websocket_connect("/voice/ws/stt") as ws:
            ws.receive_json()
        raise AssertionError("websocket should have been refused")
    except WebSocketDisconnect as exc:
        assert exc.code == 4401
    c.cookies.set(COOKIE, cookie_value(CODE))
    with c.websocket_connect("/voice/ws/stt") as ws:
        assert ws.receive_json()["text"] == "hello"


def test_empty_code_is_not_allowed():
    try:
        DemoAccessMiddleware(None, code="", static_dir=Path("."))
        raise AssertionError("an empty code must be rejected")
    except ValueError:
        pass


if __name__ == "__main__":
    tests = [f for name, f in sorted(globals().items()) if name.startswith("test_")]
    for t in tests:
        t()
        print("PASS", t.__name__)
    print(f"{len(tests)} tests passed")

"""Login: pages and API need a session; login / logout / logo work; wrong passwords are throttled."""
import importlib

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("CASHFLOW_USERS_FILE", str(tmp_path / "users.json"))
    monkeypatch.setenv("APP_SECRET_KEY", "test-secret")
    from app import auth
    auth._fails.clear()
    auth.save_users({"ravleen": auth.hash_password("correct horse")})
    import app.main as main
    importlib.reload(main)
    return TestClient(main.app)


def _login(c, pw="correct horse", user="Ravleen"):
    return c.post("/api/auth/login", json={"username": user, "password": pw, "next": "/ui/"})


def test_pages_and_api_need_login(client):
    r = client.get("/ui/", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("/login")
    assert client.get("/api/runs").status_code == 401
    assert client.get("/ui/app.js", follow_redirects=False).status_code == 303
    assert client.get("/docs", follow_redirects=False).status_code == 303


def test_login_page_logo_and_css_are_public(client):
    r = client.get("/login")
    assert r.status_code == 200 and "Login" in r.text and 'type="password"' in r.text
    assert client.get("/ui/login.css").status_code == 200
    r = client.get("/brand/logo")
    assert r.status_code == 200 and r.headers["content-type"].startswith("image/")


def test_wrong_password_rejected(client):
    r = _login(client, pw="nope")
    assert r.status_code == 401 and "cf_session" not in r.cookies
    assert client.get("/ui/", follow_redirects=False).status_code == 303


def test_login_opens_dashboard_with_logo_and_logout(client):
    r = _login(client)
    assert r.status_code == 200 and r.json()["next"] == "/ui/"
    page = client.get("/ui/")
    assert page.status_code == 200 and "/ui/auth.js" in page.text
    assert client.get("/api/auth/me").json() == {"user": "ravleen"}
    assert client.get("/login", follow_redirects=False).status_code == 303   # already signed in
    client.post("/api/auth/logout")
    client.cookies.clear()
    assert client.get("/ui/", follow_redirects=False).status_code == 303


def test_tampered_or_removed_user_session_is_refused(client):
    from app import auth
    _login(client)
    tok = client.cookies.get("cf_session")
    client.cookies.set("cf_session", tok[:-2] + ("00" if not tok.endswith("00") else "11"))
    assert client.get("/api/auth/me").status_code == 401
    client.cookies.set("cf_session", tok)
    auth.save_users({})
    assert client.get("/api/auth/me").status_code == 401


def test_throttle_after_five_failures(client):
    for _ in range(5):
        assert _login(client, pw="bad").status_code == 401
    assert _login(client).status_code == 429


def test_next_only_inside_app():
    from app.auth import safe_next
    assert safe_next("/ui/#matrix") == "/ui/#matrix"
    assert safe_next("https://evil.example") == "/ui/" and safe_next("//evil") == "/ui/" and safe_next(None) == "/ui/"


def test_login_picture_and_credit(client, tmp_path, monkeypatch):
    from app import auth
    r = client.get("/brand/background")
    assert r.status_code == 200 and r.headers["content-type"].startswith("image/")
    assert "login-credit" not in client.get("/login").text           # no credit.txt -> no credit line
    bg = tmp_path / "bg"
    bg.mkdir()
    (bg / "login-background.svg").write_text("<svg xmlns='http://www.w3.org/2000/svg'/>")
    (bg / "credit.txt").write_text("Designed by Magnific\nhttps://www.magnific.com\n")
    monkeypatch.setattr(auth, "BACKGROUND_DIR", bg)
    page = client.get("/login").text
    assert 'class="login-credit" href="https://www.magnific.com"' in page and "Designed by Magnific" in page

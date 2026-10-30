"""Login for the Cash Flow app.

* Users live in data/users.json (override with CASHFLOW_USERS_FILE): username -> salted PBKDF2-SHA256 hash.
  Passwords are never stored. Add / change / remove users with:  python tools\\add_user.py
* A signed, HttpOnly session cookie (12 hours) proves the login. The signing key is APP_SECRET_KEY from .env, or a
  random key kept in data/.session_secret (created on first use; delete it to log everybody out).
* Every page and API call needs a valid session, except the login page, its stylesheet, the logo and the login call.
* After 5 failed logins from one address within 5 minutes, that address must wait (HTTP 429).
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
COOKIE = "cf_session"
SESSION_SECONDS = 12 * 3600
PBKDF2_ITERATIONS = 200_000
MAX_FAILS, FAIL_WINDOW = 5, 300

# paths reachable without a session
PUBLIC_PATHS = {"/login", "/api/auth/login", "/api/auth/logout", "/brand/logo", "/brand/background",
                "/ui/login.css", "/favicon.ico"}


def users_file() -> Path:
    return Path(os.getenv("CASHFLOW_USERS_FILE") or ROOT / "data" / "users.json")


def load_users() -> dict:
    p = users_file()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8")).get("users", {})
    except Exception:
        return {}


def save_users(users: dict) -> None:
    p = users_file()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"users": users}, indent=2), encoding="utf-8")


def hash_password(password: str, salt: Optional[bytes] = None) -> dict:
    salt = salt or secrets.token_bytes(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return {"salt": salt.hex(), "hash": h.hex(), "iterations": PBKDF2_ITERATIONS}


def check_password(username: str, password: str) -> bool:
    rec = load_users().get((username or "").strip().lower())
    if not rec:
        hashlib.pbkdf2_hmac("sha256", b"x", b"y" * 16, PBKDF2_ITERATIONS)  # same time as a real check
        return False
    h = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(rec["salt"]),
                            int(rec.get("iterations", PBKDF2_ITERATIONS)))
    return hmac.compare_digest(h.hex(), rec["hash"])


def _secret() -> bytes:
    env = (os.getenv("APP_SECRET_KEY") or "").strip()
    if env:
        return env.encode("utf-8")
    p = ROOT / "data" / ".session_secret"
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(secrets.token_hex(32), encoding="utf-8")
    return p.read_text(encoding="utf-8").strip().encode("utf-8")


def make_token(username: str) -> str:
    body = base64.urlsafe_b64encode(json.dumps({"u": username, "exp": int(time.time()) + SESSION_SECONDS})
                                    .encode()).decode().rstrip("=")
    sig = hmac.new(_secret(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{sig}"


def read_token(token: Optional[str]) -> Optional[str]:
    """Username for a valid, unexpired token whose user still exists; otherwise None."""
    if not token or "." not in token:
        return None
    body, sig = token.rsplit(".", 1)
    if not hmac.compare_digest(sig, hmac.new(_secret(), body.encode(), hashlib.sha256).hexdigest()):
        return None
    try:
        data = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
    except Exception:
        return None
    if int(data.get("exp", 0)) < time.time() or data.get("u") not in load_users():
        return None
    return data["u"]


_fails: dict[str, list[float]] = {}


def too_many_fails(ip: str) -> bool:
    now = time.time()
    _fails[ip] = [t for t in _fails.get(ip, []) if now - t < FAIL_WINDOW]
    return len(_fails[ip]) >= MAX_FAILS


def note_fail(ip: str) -> None:
    _fails.setdefault(ip, []).append(time.time())


def clear_fails(ip: str) -> None:
    _fails.pop(ip, None)


def safe_next(nxt: Optional[str]) -> str:
    """Only send the user back to a page of this app."""
    return nxt if nxt and nxt.startswith("/ui") and "//" not in nxt else "/ui/"


# ------------------------------------------------------------------ logo
LOGO_DIR = ROOT / "logo"
LOGO_TYPES = {".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
              ".webp": "image/webp", ".gif": "image/gif"}


def _folder_image(folder: Path, word: str) -> Optional[Path]:
    """First image in the folder: a file whose name contains `word` first, then alphabetical."""
    if not folder.is_dir():
        return None
    files = sorted((p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in LOGO_TYPES),
                   key=lambda p: (word not in p.name.lower(), p.name.lower()))
    return files[0] if files else None


def logo_path() -> Optional[Path]:
    """The image in the project's logo folder (a file with 'logo' in its name first, then alphabetical)."""
    return _folder_image(LOGO_DIR, "logo")


# ------------------------------------------------------------------ login-page picture
BACKGROUND_DIR = ROOT / "background"


def background_path() -> Optional[Path]:
    """The picture for the login page, from the project's background folder."""
    return _folder_image(BACKGROUND_DIR, "background")


def background_credit() -> Optional[tuple[str, str]]:
    """(text, link) from background/credit.txt - line 1 the credit text, line 2 the link. Needed for pictures whose
    licence asks for attribution (e.g. a free Magnific / Freepik image: 'Designed by Magnific', www.magnific.com)."""
    p = BACKGROUND_DIR / "credit.txt"
    if not p.exists() or not background_path():
        return None
    lines = [x.strip() for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
    if not lines:
        return None
    url = lines[1] if len(lines) > 1 and lines[1].startswith(("http://", "https://")) else ""
    return lines[0], url

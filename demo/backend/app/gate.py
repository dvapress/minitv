"""Whole-site passcode gate. Plaintext passcodes are never stored or logged."""

from __future__ import annotations

import hmac
import ipaddress
import json
import re
from datetime import timedelta
from hashlib import sha256
from urllib.parse import quote, urlparse

from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from app.config import Settings
from app.db import connect, iso, utcnow
from app.security import hash_password, new_token, token_hash, verify_password, write_private

COOKIE = "ld_gate"
RL_COOKIE = "ld_gate_rl"
HASH_NAME = "gate.hashes"
FAILURE_LIMIT = 8
FAILURE_WINDOW_MINUTES = 15
SESSION_COOKIE_RE = re.compile(r"^[A-Za-z0-9_-]{20,}\.[0-9a-f]{64}$")

GATE_HTML = """<!doctype html>
<html lang="zh-Hans">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta name="robots" content="noindex" />
  <title>LeapDrama</title>
  <style>
    :root { color-scheme: light dark; }
    body { margin: 0; min-height: 100vh; display: grid; place-items: center; font-family: "PingFang SC", "Noto Sans SC", "Segoe UI", sans-serif; background: #14110e; color: #f6f1e8; }
    html, body { overflow-x: hidden; }
    form { width: min(420px, calc(100vw - 32px)); box-sizing: border-box; background: #221c17; border: 1px solid rgba(246,241,232,.14); border-radius: 20px; padding: 24px; }
    h1 { font-family: Didot, "Songti SC", serif; font-weight: 500; margin: 0 0 8px; text-wrap: balance; }
    p { color: #cbbba8; line-height: 1.5; }
    label { display: block; margin-top: 12px; }
    input { display: block; width: 100%; max-width: 100%; box-sizing: border-box; margin: 8px 0 0; padding: 12px 14px; border-radius: 12px; border: 1px solid rgba(246,241,232,.2); background: #100e0c; color: inherit; }
    button { background: #e0b15a; color: #2a1c08; border: 0; border-radius: 999px; padding: 10px 16px; font-weight: 700; }
    .err { color: #f0a090; min-height: 1.2em; }
  </style>
</head>
<body>
  <form id="gate">
    <h1>LeapDrama</h1>
    <p id="lead">这是整站访问口令。两个口令任一即可，口令不会记在浏览器里。</p>
    <label for="passcode">口令</label>
    <input id="passcode" type="password" name="passcode" autocomplete="current-password" required />
    <p class="err" id="err" role="alert"></p>
    <button type="submit">进入</button>
  </form>
  <script>
    const nextRaw = new URLSearchParams(location.search).get("next") || "/";
    const next = nextRaw.startsWith("/") && !nextRaw.startsWith("//") ? nextRaw : "/";
    const closed = new URLSearchParams(location.search).get("closed") === "1";
    if (closed) {
      document.getElementById("lead").textContent = "访问口令还没有配置完成，站点保持关闭。";
      document.getElementById("passcode").disabled = true;
    }
    document.getElementById("gate").addEventListener("submit", async (event) => {
      event.preventDefault();
      const err = document.getElementById("err");
      err.textContent = "";
      const passcode = document.getElementById("passcode").value;
      const response = await fetch("/api/gate/login", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json", "Accept": "application/json" },
        body: JSON.stringify({ passcode })
      });
      document.getElementById("passcode").value = "";
      if (response.ok) {
        location.replace(next);
        return;
      }
      err.textContent = response.status === 429 ? "尝试太频繁，请稍后再试。" : "口令不正确。";
    });
  </script>
</body>
</html>
"""


def hashes_path(settings: Settings) -> object:
    return settings.data_dir / HASH_NAME


def load_hashes(settings: Settings) -> list[str] | None:
    path = settings.data_dir / HASH_NAME
    if not path.is_file():
        return None
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
        hashes = document.get("hashes")
    except (OSError, json.JSONDecodeError, AttributeError):
        return None
    if not isinstance(hashes, list) or len(hashes) != 2:
        return None
    cleaned = []
    for item in hashes:
        if not isinstance(item, str) or not item.startswith("pbkdf2_sha256$"):
            return None
        cleaned.append(item)
    return cleaned


def gate_ready(settings: Settings) -> bool:
    return bool(settings.gate_enabled and load_hashes(settings))


def write_hashes(settings: Settings, first: str, second: str) -> None:
    if not first or not second or first == second:
        raise ValueError("two different passcodes are required")
    if len(first) > 200 or len(second) > 200:
        raise ValueError("passcode is too long")
    payload = {
        "version": 1,
        "algorithm": "pbkdf2_sha256",
        "hashes": [hash_password(first), hash_password(second)],
    }
    write_private(settings.data_dir / HASH_NAME, json.dumps(payload) + "\n")


def _sign(token: str, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), token.encode("utf-8"), sha256).hexdigest()
    return f"{token}.{digest}"


def _unsign(value: str, secret: str) -> str | None:
    token, sep, digest = value.rpartition(".")
    if not sep or not token or not digest:
        return None
    expected = hmac.new(secret.encode("utf-8"), token.encode("utf-8"), sha256).hexdigest()
    if not hmac.compare_digest(digest, expected):
        return None
    return token


def _request_https(request: Request, settings: Settings) -> bool:
    if settings.cookie_secure in {"1", "true", "yes"}:
        return True
    if settings.cookie_secure in {"0", "false", "no"}:
        return False
    if settings.trusted_proxy == "cloudflare":
        forwarded = request.headers.get("x-forwarded-proto", "")
        if forwarded.split(",")[0].strip().lower() == "https":
            return True
    return request.url.scheme == "https"


def _client_bucket(request: Request, settings: Settings) -> str:
    if settings.trusted_proxy == "cloudflare":
        raw = request.headers.get("cf-connecting-ip", "").strip()
        if _usable_ip(raw):
            return "cf:" + raw
    token = request.cookies.get(RL_COOKIE, "")
    if not re.fullmatch(r"[A-Za-z0-9_-]{16,64}", token or ""):
        token = new_token()
    return "browser:" + token


def _usable_ip(value: str) -> bool:
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return False
    return not (address.is_loopback or address.is_unspecified or address.is_multicast)


def _limited(settings: Settings, bucket: str) -> bool:
    cutoff = iso(utcnow() - timedelta(minutes=FAILURE_WINDOW_MINUTES))
    conn = connect(settings)
    try:
        conn.execute("DELETE FROM gate_attempts WHERE failed_at < ?", (cutoff,))
        count = conn.execute(
            "SELECT COUNT(*) AS n FROM gate_attempts WHERE bucket = ? AND failed_at >= ?",
            (bucket, cutoff),
        ).fetchone()["n"]
        conn.commit()
        return count >= FAILURE_LIMIT
    finally:
        conn.close()


def _record_failure(settings: Settings, bucket: str) -> None:
    conn = connect(settings)
    try:
        conn.execute("INSERT INTO gate_attempts (bucket, failed_at) VALUES (?, ?)", (bucket, iso()))
        conn.commit()
    finally:
        conn.close()


def _clear_failures(settings: Settings, bucket: str) -> None:
    conn = connect(settings)
    try:
        conn.execute("DELETE FROM gate_attempts WHERE bucket = ?", (bucket,))
        conn.commit()
    finally:
        conn.close()


def session_ok(request: Request, settings: Settings) -> bool:
    if not settings.gate_enabled:
        return True
    raw = request.cookies.get(COOKIE, "")
    token = _unsign(raw, settings.secret_key)
    if not token:
        return False
    conn = connect(settings)
    try:
        row = conn.execute(
            "SELECT expires_at FROM gate_sessions WHERE token_hash = ?",
            (token_hash(token),),
        ).fetchone()
        return bool(row and row["expires_at"] > iso())
    finally:
        conn.close()


def origin_ok(request: Request, settings: Settings) -> bool:
    origin = request.headers.get("origin", "")
    host = request.headers.get("host", "")
    allowed = {host}
    if settings.trusted_proxy == "cloudflare":
        public = urlparse(settings.public_base_url).netloc
        if public:
            allowed.add(public)
    if origin:
        parsed = urlparse(origin)
        return parsed.netloc in allowed and parsed.scheme in {"http", "https"}
    site = request.headers.get("sec-fetch-site", "")
    return site in {"", "same-origin", "none"}


def safe_next(value: str | None) -> str:
    if not value:
        return "/"
    if not value.startswith("/") or value.startswith("//") or value.startswith("/\\"):
        return "/"
    if any(char in value for char in ("\\", "\r", "\n", " ")):
        return "/"
    return value


def _set_cookie(response: Response, name: str, value: str, request: Request, settings: Settings, max_age: int) -> None:
    response.set_cookie(
        name,
        value,
        httponly=True,
        samesite="lax",
        secure=_request_https(request, settings),
        max_age=max_age,
        path="/",
    )


def login(request: Request, settings: Settings, passcode: str) -> Response:
    bucket = _client_bucket(request, settings)
    if not origin_ok(request, settings):
        return _json(403, "forbidden")
    hashes = load_hashes(settings)
    if not settings.gate_enabled or not hashes:
        return _json(503, "gate_closed")
    if _limited(settings, bucket):
        response = _json(429, "rate_limited")
        response.headers["Retry-After"] = "900"
        _ensure_rl_cookie(response, request, settings, bucket)
        return response
    matched = False
    for stored in hashes:
        matched = verify_password(passcode, stored) or matched
    if not matched:
        _record_failure(settings, bucket)
        response = _json(401, "invalid_passcode")
        _ensure_rl_cookie(response, request, settings, bucket)
        return response
    _clear_failures(settings, bucket)
    token = new_token()
    expires = iso(utcnow() + timedelta(hours=settings.gate_session_hours))
    conn = connect(settings)
    try:
        conn.execute(
            "INSERT INTO gate_sessions (token_hash, expires_at, created_at) VALUES (?, ?, ?)",
            (token_hash(token), expires, iso()),
        )
        conn.commit()
    finally:
        conn.close()
    response = JSONResponse({"ok": True})
    _set_cookie(response, COOKIE, _sign(token, settings.secret_key), request, settings, settings.gate_session_hours * 3600)
    _private(response)
    return response


def logout(request: Request, settings: Settings) -> Response:
    if not origin_ok(request, settings):
        return _json(403, "forbidden")
    raw = request.cookies.get(COOKIE, "")
    token = _unsign(raw, settings.secret_key) if raw else None
    if token:
        conn = connect(settings)
        try:
            conn.execute("DELETE FROM gate_sessions WHERE token_hash = ?", (token_hash(token),))
            conn.commit()
        finally:
            conn.close()
    response = JSONResponse({"ok": True})
    response.delete_cookie(COOKIE, path="/")
    _private(response)
    return response


def decide(request: Request, settings: Settings) -> Response | None:
    if not settings.gate_enabled:
        return None
    path = request.url.path
    if path == "/health" and request.method == "GET":
        return None
    if path == "/gate" and request.method == "GET":
        if load_hashes(settings):
            if "closed=1" in request.url.query:
                return RedirectResponse("/gate", status_code=302)
            return HTMLResponse(GATE_HTML, headers={"Cache-Control": "private, no-store"})
        if "closed=1" not in request.url.query:
            return RedirectResponse("/gate?closed=1", status_code=302)
        return HTMLResponse(GATE_HTML, headers={"Cache-Control": "private, no-store"})
    if path == "/api/gate/login" and request.method == "POST":
        return None
    if path == "/api/gate/logout" and request.method == "POST":
        return None
    if not load_hashes(settings):
        if _wants_html(request):
            return RedirectResponse("/gate?closed=1", status_code=302)
        return _json(503, "gate_closed")
    if session_ok(request, settings):
        return None
    if _wants_html(request):
        target = safe_next(path + (("?" + request.url.query) if request.url.query else ""))
        return RedirectResponse(f"/gate?next={quote(target, safe='/')}", status_code=302)
    return _json(401, "gate_required")


def _wants_html(request: Request) -> bool:
    if request.method != "GET" or request.url.path.startswith("/api"):
        return False
    accept = request.headers.get("accept", "")
    return "text/html" in accept


def _json(status: int, code: str) -> JSONResponse:
    response = JSONResponse({"detail": {"code": code}}, status_code=status)
    _private(response)
    return response


def _private(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["Pragma"] = "no-cache"


def _ensure_rl_cookie(response: Response, request: Request, settings: Settings, bucket: str) -> None:
    if bucket.startswith("browser:"):
        token = bucket.split(":", 1)[1]
        if request.cookies.get(RL_COOKIE) != token:
            _set_cookie(response, RL_COOKIE, token, request, settings, 24 * 3600)


def public_health() -> dict:
    return {"status": "ok", "service": "leapdrama"}

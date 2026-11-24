from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.codec import inspect
from app.config import load_settings
from app.gate import write_hashes
from app.importer import ImportOptions, import_library
from app.main import create_app
from app.security import hash_password

UPLOADS = Path("/home/ubuntu/.cursor/projects/workspace/uploads")
H264_SAMPLE = UPLOADS / "xiaozixiansun_ep1_t1s_2s_ca0b.mp4"
PASS_A = "fixture-gate-alpha"
PASS_B = "fixture-gate-beta"


def _settings(tmp_path, monkeypatch, **extra):
    monkeypatch.setenv("LEAPDRAMA_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("LEAPDRAMA_ADMIN_EMAIL", "admin@leapdrama.demo")
    monkeypatch.setenv("LEAPDRAMA_ADMIN_PASSWORD", "fixture-admin-password")
    monkeypatch.setenv("LEAPDRAMA_SECRET_KEY", "fixture-secret-key-012345")
    monkeypatch.setenv("LEAPDRAMA_COOKIE_SECURE", "0")
    monkeypatch.setenv("LEAPDRAMA_SELECTION", str(Path(__file__).resolve().parents[2] / "import-selection.json"))
    for key, value in extra.items():
        monkeypatch.setenv(key, value)
    return load_settings()


def test_box_parser_reads_diagnostic_h264_without_claiming_hevc():
    if not H264_SAMPLE.is_file():
        pytest.skip("diagnostic clip is not in this workspace")
    info = inspect(H264_SAMPLE)
    assert info["video"] == "avc1"
    assert info["profile"] == 100
    assert info["playable"] is True
    assert info["reason"] == "ok"
    assert info["width"] == 720
    assert info["height"] == 1280
    assert info["duration"] == pytest.approx(2.0, abs=0.05)


def test_hevc_box_is_not_marked_playable(tmp_path):
    entry = (16).to_bytes(4, "big") + b"hvc1" + b"\x00" * 8
    stsd = b"\x00\x00\x00\x00" + (1).to_bytes(4, "big") + entry
    def box(kind: bytes, payload: bytes) -> bytes:
        return (8 + len(payload)).to_bytes(4, "big") + kind + payload
    moov = box(b"moov", box(b"mvhd", b"\x00\x00\x00\x00" + b"\x00" * 8 + (1000).to_bytes(4, "big") + (2000).to_bytes(4, "big")) + box(b"trak", box(b"mdia", box(b"minf", box(b"stbl", box(b"stsd", stsd))))))
    path = tmp_path / "1.mp4"
    path.write_bytes(box(b"ftyp", b"isom" + b"\x00\x00\x00\x00" + b"isom") + moov)
    info = inspect(path)
    assert info["video"] == "hvc1"
    assert info["playable"] is False
    assert info["reason"] == "hevc"
    assert info["duration"] == pytest.approx(2.0)


def test_gate_fail_closed_then_login_range_and_logout(tmp_path, monkeypatch):
    if not H264_SAMPLE.is_file():
        pytest.skip("diagnostic clip is not in this workspace")
    settings = _settings(tmp_path, monkeypatch, LEAPDRAMA_GATE="1")
    app = create_app(settings)
    client = TestClient(app)
    closed = client.get("/api/home")
    assert closed.status_code == 503
    assert closed.json()["detail"]["code"] == "gate_closed"
    assert "series" not in closed.text
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json() == {"status": "ok", "service": "leapdrama"}
    assert "series_count" not in health.text
    write_hashes(settings, PASS_A, PASS_B)
    denied = client.get("/api/home")
    assert denied.status_code == 401
    assert denied.json()["detail"]["code"] == "gate_required"
    assert "private" in denied.headers["cache-control"]
    page = client.get("/", headers={"accept": "text/html"}, follow_redirects=False)
    assert page.status_code == 302
    assert page.headers["location"].startswith("/gate?next=")
    evil = client.get("/", headers={"accept": "text/html"}, follow_redirects=False)
    assert "http://" not in client.get("/watch/nope", headers={"accept": "text/html"}, follow_redirects=False).headers["location"]
    bad = client.post("/api/gate/login", json={"passcode": "wrong-passcode"})
    assert bad.status_code == 401
    assert "wrong-passcode" not in bad.text
    assert PASS_A not in bad.text
    first = client.post("/api/gate/login", json={"passcode": PASS_A})
    assert first.status_code == 200
    cookie = first.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "samesite=lax" in cookie
    assert "secure" not in cookie
    library = tmp_path / "library" / "诊断片"
    library.mkdir(parents=True)
    target = library / "1.mp4"
    target.write_bytes(H264_SAMPLE.read_bytes())
    before = hashlib.sha256(target.read_bytes()).hexdigest()
    imported = import_library(settings, library.parent, ImportOptions(all_series=True, all_episodes=True))
    assert imported["status"] == "ok"
    episode = imported["series"][0]["episodes"][0]
    assert episode["browser_playable"] is True
    assert episode["video_codec"] == "avc1"
    assert hashlib.sha256(target.read_bytes()).hexdigest() == before
    home = client.get("/api/home")
    assert home.status_code == 200
    detail = client.get("/api/series/" + home.json()["hero"][0]["slug"]).json()
    media_url = None
    episode_id = detail["episodes"][0]["id"]
    played = client.post("/api/playback/authorize", json={"episode_id": episode_id})
    assert played.status_code == 200
    media_url = played.json()["sources"][0]["url"]
    ranged = client.get(media_url, headers={"Range": "bytes=0-15"})
    assert ranged.status_code == 206
    assert ranged.content == H264_SAMPLE.read_bytes()[:16]
    assert "private" in ranged.headers["cache-control"]
    full = client.get(media_url)
    assert full.status_code == 200
    assert full.headers["content-type"].startswith("video/mp4")
    served = tmp_path / "served.mp4"
    served.write_bytes(full.content)
    frame = tmp_path / "frame.rgb"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(served), "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", str(frame)],
        check=True,
    )
    pixels = frame.read_bytes()
    bright = sum(1 for value in pixels if value > 40)
    assert bright > len(pixels) * 0.02
    client.post("/api/gate/logout")
    again = client.get(media_url, headers={"Range": "bytes=0-15"})
    assert again.status_code == 401
    assert again.content[:8] != H264_SAMPLE.read_bytes()[:8]
    assert client.get("/api/creator/overview").status_code == 401


def test_repeated_wrong_passcodes_are_throttled_per_browser_not_loopback(tmp_path, monkeypatch):
    settings = _settings(tmp_path, monkeypatch, LEAPDRAMA_GATE="1")
    path = settings.data_dir / "gate.hashes"
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(
        '{"version":1,"hashes":["' + hash_password(PASS_A, rounds=800) + '","' + hash_password(PASS_B, rounds=800) + '"]}\n',
        encoding="utf-8",
    )
    app = create_app(settings)
    attacker = TestClient(app)
    for _ in range(8):
        response = attacker.post(
            "/api/gate/login",
            json={"passcode": "nope"},
            headers={"X-Forwarded-For": "203.0.113.8", "CF-Connecting-IP": "198.51.100.9"},
        )
        assert response.status_code == 401
    blocked = attacker.post("/api/gate/login", json={"passcode": PASS_B}, headers={"X-Forwarded-For": "203.0.113.8"})
    assert blocked.status_code == 429
    other = TestClient(app)
    allowed = other.post("/api/gate/login", json={"passcode": PASS_B}, headers={"X-Forwarded-For": "203.0.113.8"})
    assert allowed.status_code == 200


def test_secure_cookie_requires_explicit_cloudflare_proxy(tmp_path, monkeypatch):
    settings = _settings(tmp_path, monkeypatch, LEAPDRAMA_GATE="1", LEAPDRAMA_COOKIE_SECURE="auto")
    write_hashes(settings, PASS_A, PASS_B)
    app = create_app(settings)
    client = TestClient(app)
    spoofed = client.post("/api/gate/login", json={"passcode": PASS_A}, headers={"X-Forwarded-Proto": "https"})
    assert "secure" not in spoofed.headers["set-cookie"].lower()
    client.post("/api/gate/logout")
    monkeypatch.setenv("LEAPDRAMA_TRUSTED_PROXY", "cloudflare")
    proxied = create_app(load_settings())
    proxy_client = TestClient(proxied)
    accepted = proxy_client.post(
        "/api/gate/login",
        json={"passcode": PASS_A},
        headers={"X-Forwarded-Proto": "https", "CF-Connecting-IP": "203.0.113.20"},
    )
    assert "secure" in accepted.headers["set-cookie"].lower()
    assert "httponly" in accepted.headers["set-cookie"].lower()


def test_low_round_hash_still_rejects_plaintext_storage(tmp_path, monkeypatch):
    settings = _settings(tmp_path, monkeypatch, LEAPDRAMA_GATE="1")
    stored = hash_password(PASS_A, rounds=1000)
    path = settings.data_dir / "gate.hashes"
    settings.data_dir.mkdir(parents=True)
    path.write_text('{"version":1,"hashes":["' + stored + '","' + hash_password(PASS_B, rounds=1000) + '"]}\n', encoding="utf-8")
    text = path.read_text(encoding="utf-8")
    assert PASS_A not in text
    assert text.count("pbkdf2_sha256$") == 2

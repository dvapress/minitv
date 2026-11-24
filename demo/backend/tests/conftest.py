from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import load_settings
from app.main import create_app

DEMO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PASSWORD = "fixture-admin-password"


def ffmpeg_available() -> bool:
    return bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))


def make_clip(path: Path, seconds: float, size: str = "160x284", color: str = "0x335544", fps: int = 8) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            f"color=c={color}:s={size}:r={fps}:d={seconds}",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=channel_layout=stereo:sample_rate=44100",
            "-shortest",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-preset",
            "ultrafast",
            "-c:a",
            "aac",
            str(path),
        ],
        check=True,
        timeout=180,
    )


@pytest.fixture(scope="session")
def clips(tmp_path_factory) -> dict[str, Path]:
    if not ffmpeg_available():
        pytest.skip("ffmpeg and ffprobe are required for media tests")
    root = tmp_path_factory.mktemp("clips")
    short = root / "short.mp4"
    long = root / "long.mp4"
    tall = root / "tall.mp4"
    make_clip(short, 1.2, color="0x335544")
    make_clip(long, 185, size="64x64", color="0x662222", fps=1)
    make_clip(tall, 1.0, size="160x720", color="0x224466", fps=6)
    return {"short": short, "long": long, "tall": tall}


@pytest.fixture()
def env(tmp_path, monkeypatch):
    data = tmp_path / "data"
    monkeypatch.setenv("LEAPDRAMA_DATA_DIR", str(data))
    monkeypatch.setenv("LEAPDRAMA_ADMIN_EMAIL", "admin@leapdrama.demo")
    monkeypatch.setenv("LEAPDRAMA_ADMIN_PASSWORD", FIXTURE_PASSWORD)
    monkeypatch.setenv("LEAPDRAMA_SECRET_KEY", "fixture-secret-key-012345")
    monkeypatch.setenv("LEAPDRAMA_SELECTION", str(DEMO_ROOT / "import-selection.json"))
    monkeypatch.setenv("LEAPDRAMA_COOKIE_SECURE", "0")
    monkeypatch.setenv("LEAPDRAMA_LIBRARY_ROOTS", str(tmp_path))
    settings = load_settings()
    app = create_app(settings)
    client = TestClient(app)
    return type("Env", (), {"client": client, "settings": settings, "tmp": tmp_path, "app": app, "password": FIXTURE_PASSWORD})()

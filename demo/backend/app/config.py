from __future__ import annotations

import os
from dataclasses import dataclass, replace
from pathlib import Path

WEAK_SECRETS = {"admin", "password", "changeme", "leapdrama", "secret", "12345678"}


def _blank(name: str) -> str | None:
    value = os.environ.get(name, "").strip()
    return value or None


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    secret_key: str
    admin_email: str
    admin_password: str | None
    public_base_url: str
    bind: str
    port: int
    max_episode_seconds: float
    max_upload_bytes: int
    library_roots: tuple[Path, ...]
    cookie_secure: str
    static_dir: Path
    selection_path: Path
    gate_enabled: bool = False
    trusted_proxy: str = ""
    gate_session_hours: int = 12
    free_episode_count: int = 2

    @property
    def db_path(self) -> Path:
        return self.data_dir / "leapdrama.sqlite3"

    @property
    def admin_password_file(self) -> Path:
        return self.data_dir / "admin.password"

    @property
    def secret_key_file(self) -> Path:
        return self.data_dir / "secret.key"


def demo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_settings() -> Settings:
    data_dir = Path(os.environ.get("LEAPDRAMA_DATA_DIR", "./data")).expanduser().resolve()
    root = demo_root()
    static_dir = Path(os.environ.get("LEAPDRAMA_STATIC_DIR", str(root / "web" / "build"))).expanduser().resolve()
    selection = Path(os.environ.get("LEAPDRAMA_SELECTION", str(root / "import-selection.json"))).expanduser().resolve()
    password = _blank("LEAPDRAMA_ADMIN_PASSWORD")
    if password is not None and (password.lower() in WEAK_SECRETS or len(password) < 12):
        raise SystemExit("LEAPDRAMA_ADMIN_PASSWORD is too weak. Choose another value; there is no shared default.")
    secret = _blank("LEAPDRAMA_SECRET_KEY")
    if secret is not None and len(secret) < 16:
        raise SystemExit("LEAPDRAMA_SECRET_KEY must be at least 16 characters when it is set.")
    roots = tuple(
        Path(part).expanduser().resolve()
        for part in os.environ.get("LEAPDRAMA_LIBRARY_ROOTS", "").split(os.pathsep)
        if part.strip()
    )
    try:
        max_seconds = float(os.environ.get("LEAPDRAMA_MAX_EPISODE_SECONDS", "180"))
        max_upload = int(os.environ.get("LEAPDRAMA_MAX_UPLOAD_BYTES", str(512 * 1024 * 1024)))
        port = int(os.environ.get("LEAPDRAMA_PORT", "18080"))
    except ValueError as exc:
        raise SystemExit("LEAPDRAMA_PORT, LEAPDRAMA_MAX_EPISODE_SECONDS, or LEAPDRAMA_MAX_UPLOAD_BYTES is not a number.") from exc
    email = (os.environ.get("LEAPDRAMA_ADMIN_EMAIL") or "admin@leapdrama.demo").strip().lower()
    gate_flag = (os.environ.get("LEAPDRAMA_GATE") or "").strip().lower()
    proxy = (os.environ.get("LEAPDRAMA_TRUSTED_PROXY") or "").strip().lower()
    if proxy not in {"", "cloudflare"}:
        raise SystemExit("LEAPDRAMA_TRUSTED_PROXY must be empty or cloudflare.")
    try:
        session_hours = int(os.environ.get("LEAPDRAMA_GATE_SESSION_HOURS", "12"))
    except ValueError as exc:
        raise SystemExit("LEAPDRAMA_GATE_SESSION_HOURS is not a number.") from exc
    return Settings(
        data_dir=data_dir,
        secret_key=secret or "",
        admin_email=email,
        admin_password=password,
        public_base_url=(os.environ.get("LEAPDRAMA_PUBLIC_BASE_URL") or "https://leapdrama-demo.rei.autos").rstrip("/"),
        bind=(os.environ.get("LEAPDRAMA_BIND") or "127.0.0.1").strip() or "127.0.0.1",
        port=port,
        max_episode_seconds=max_seconds,
        max_upload_bytes=max_upload,
        library_roots=roots,
        cookie_secure=(os.environ.get("LEAPDRAMA_COOKIE_SECURE") or "auto").strip().lower(),
        static_dir=static_dir,
        selection_path=selection,
        gate_enabled=gate_flag in {"1", "true", "yes", "on"},
        trusted_proxy=proxy,
        gate_session_hours=max(1, session_hours),
    )


def with_secret(settings: Settings, secret_key: str) -> Settings:
    return replace(settings, secret_key=secret_key)

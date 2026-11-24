from __future__ import annotations

import logging
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone

from app.config import Settings, with_secret
from app.security import hash_password, write_private

logger = logging.getLogger("leapdrama")

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY,
  email TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  display_name TEXT NOT NULL,
  role TEXT NOT NULL CHECK (role IN ('viewer', 'creator', 'admin')),
  region TEXT NOT NULL DEFAULT 'ALL',
  theme TEXT NOT NULL DEFAULT '',
  locale TEXT NOT NULL DEFAULT '',
  membership_until TEXT,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
  token_hash TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  expires_at TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS series (
  id INTEGER PRIMARY KEY,
  slug TEXT NOT NULL UNIQUE,
  title TEXT NOT NULL,
  title_en TEXT NOT NULL DEFAULT '',
  synopsis TEXT NOT NULL DEFAULT '',
  synopsis_en TEXT NOT NULL DEFAULT '',
  genre TEXT NOT NULL DEFAULT '未分类',
  genre_en TEXT NOT NULL DEFAULT 'Uncategorized',
  region TEXT NOT NULL DEFAULT 'GLOBAL',
  cover_path TEXT,
  source_folder TEXT UNIQUE,
  free_count INTEGER NOT NULL DEFAULT 2,
  play_count INTEGER NOT NULL DEFAULT 0,
  numbering_note TEXT NOT NULL DEFAULT '',
  meta_mtime_ns INTEGER,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS episodes (
  id INTEGER PRIMARY KEY,
  series_id INTEGER NOT NULL REFERENCES series(id) ON DELETE CASCADE,
  number INTEGER NOT NULL,
  title TEXT NOT NULL,
  duration_seconds REAL,
  duration_flag TEXT NOT NULL CHECK (duration_flag IN ('ok', 'long', 'unknown')),
  width INTEGER NOT NULL DEFAULT 0,
  height INTEGER NOT NULL DEFAULT 0,
  media_path TEXT,
  source_path TEXT,
  source_size INTEGER,
  source_mtime_ns INTEGER,
  source_sha256 TEXT,
  renditions_json TEXT NOT NULL DEFAULT '[]',
  subtitles_json TEXT NOT NULL DEFAULT '[]',
  browser_playable INTEGER NOT NULL DEFAULT 1,
  video_codec TEXT NOT NULL DEFAULT '',
  playback_block TEXT NOT NULL DEFAULT '',
  served_size INTEGER,
  served_mtime_ns INTEGER,
  play_count INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (series_id, number)
);
CREATE TABLE IF NOT EXISTS history (
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  episode_id INTEGER NOT NULL REFERENCES episodes(id) ON DELETE CASCADE,
  position_seconds REAL NOT NULL DEFAULT 0,
  completed INTEGER NOT NULL DEFAULT 0,
  updated_at TEXT NOT NULL,
  PRIMARY KEY (user_id, episode_id)
);
CREATE TABLE IF NOT EXISTS favorites (
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  series_id INTEGER NOT NULL REFERENCES series(id) ON DELETE CASCADE,
  created_at TEXT NOT NULL,
  PRIMARY KEY (user_id, series_id)
);
CREATE TABLE IF NOT EXISTS reactions (
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  series_id INTEGER NOT NULL REFERENCES series(id) ON DELETE CASCADE,
  kind TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY (user_id, series_id, kind)
);
CREATE TABLE IF NOT EXISTS comments (
  id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  episode_id INTEGER NOT NULL REFERENCES episodes(id) ON DELETE CASCADE,
  body TEXT NOT NULL,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS bills (
  id INTEGER PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  plan_code TEXT NOT NULL,
  kind TEXT NOT NULL,
  list_price_cents INTEGER NOT NULL,
  charged_cents INTEGER NOT NULL,
  currency TEXT NOT NULL,
  status TEXT NOT NULL,
  note TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS playback_events (
  id INTEGER PRIMARY KEY,
  viewer_key TEXT NOT NULL,
  user_id INTEGER,
  episode_id INTEGER NOT NULL,
  kind TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS playback_events_lookup
  ON playback_events (viewer_key, episode_id, created_at);
CREATE TABLE IF NOT EXISTS login_attempts (
  id INTEGER PRIMARY KEY,
  email TEXT NOT NULL,
  failed_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit (
  id INTEGER PRIMARY KEY,
  actor_id INTEGER,
  action TEXT NOT NULL,
  detail TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS gate_sessions (
  token_hash TEXT PRIMARY KEY,
  expires_at TEXT NOT NULL,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS gate_attempts (
  id INTEGER PRIMARY KEY,
  bucket TEXT NOT NULL,
  failed_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS gate_attempts_lookup ON gate_attempts (bucket, failed_at);
"""


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(moment: datetime | None = None) -> str:
    moment = moment or utcnow()
    return moment.astimezone(timezone.utc).isoformat()


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def connect(settings: Settings) -> sqlite3.Connection:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.db_path, timeout=15, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=15000")
    return conn


def init_db(settings: Settings) -> None:
    conn = connect(settings)
    try:
        conn.executescript(SCHEMA)
        _migrate(conn)
        conn.commit()
    finally:
        conn.close()


def _migrate(conn: sqlite3.Connection) -> None:
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    if "episodes" not in tables:
        return
    present = {row[1] for row in conn.execute("PRAGMA table_info(episodes)")}
    additions = {
        "video_codec": "TEXT NOT NULL DEFAULT ''",
        "playback_block": "TEXT NOT NULL DEFAULT ''",
        "served_size": "INTEGER",
        "served_mtime_ns": "INTEGER",
    }
    for name, declaration in additions.items():
        if name not in present:
            conn.execute(f"ALTER TABLE episodes ADD COLUMN {name} {declaration}")


def ensure_secret(settings: Settings) -> Settings:
    if settings.secret_key:
        return settings
    path = settings.secret_key_file
    if path.exists():
        key = path.read_text(encoding="utf-8").strip()
    else:
        key = secrets.token_urlsafe(32)
        write_private(path, key + "\n")
        logger.warning("Generated signing key at %s (value not logged)", path)
    if len(key) < 16:
        raise SystemExit(f"refusing unusable signing key file at {path}")
    return with_secret(settings, key)


def _read_password_file(settings: Settings) -> str | None:
    path = settings.admin_password_file
    if not path.is_file():
        return None
    password = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("password="):
            password = line.split("=", 1)[1]
    return password or None


def ensure_admin(settings: Settings) -> None:
    conn = connect(settings)
    try:
        row = conn.execute("SELECT id FROM users WHERE email = ?", (settings.admin_email,)).fetchone()
        password = settings.admin_password
        generated = False
        if password is None and row is None:
            password = _read_password_file(settings)
            if not password:
                password = secrets.token_urlsafe(18)
                write_private(
                    settings.admin_password_file,
                    f"email={settings.admin_email}\npassword={password}\n",
                )
                generated = True
                logger.warning(
                    "Generated admin credential file at %s (value not logged)",
                    settings.admin_password_file,
                )
        if password is None:
            return
        digest = hash_password(password)
        now = iso()
        if row is None:
            conn.execute(
                """
                INSERT INTO users (email, password_hash, display_name, role, region, created_at)
                VALUES (?, ?, ?, 'admin', 'ALL', ?)
                """,
                (settings.admin_email, digest, "LeapDrama", now),
            )
        elif settings.admin_password is not None:
            conn.execute(
                "UPDATE users SET password_hash = ?, role = 'admin' WHERE id = ?",
                (digest, row["id"]),
            )
        conn.commit()
        if generated:
            logger.info("Admin account is ready for %s", settings.admin_email)
    finally:
        conn.close()


def is_member(user: sqlite3.Row | None) -> bool:
    if user is None:
        return False
    until = parse_iso(user["membership_until"])
    return bool(until and until > utcnow())


def membership_deadline(days: int = 30) -> str:
    return iso(utcnow() + timedelta(days=days))

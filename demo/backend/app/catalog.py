from __future__ import annotations

import json
import re
import sqlite3
import unicodedata
from datetime import timedelta

from app.db import is_member, iso, parse_iso, utcnow
from app.moderation import moderate

PLAN = {
    "code": "demo-monthly",
    "list_price_cents": 990,
    "charged_cents": 0,
    "currency": "USD",
    "days": 30,
}
REGIONS = ["ALL", "SG", "MY", "US", "TH", "PH", "ID", "TW", "HK"]
START_DEBOUNCE_SECONDS = 60


def slugify(value: str) -> str:
    value = unicodedata.normalize("NFC", value).strip()
    chars = []
    for char in value:
        if char.isascii() and char.isalnum():
            chars.append(char.lower())
        elif char.isalnum():
            chars.append(char)
        else:
            chars.append("-")
    slug = re.sub(r"-{2,}", "-", "".join(chars)).strip("-")
    return (slug or "series")[:80]


def unique_slug(conn: sqlite3.Connection, title: str, existing_id: int | None = None) -> str:
    base = slugify(title)
    slug = base
    suffix = 2
    while True:
        row = conn.execute("SELECT id FROM series WHERE slug = ?", (slug,)).fetchone()
        if row is None or (existing_id is not None and int(row["id"]) == existing_id):
            return slug
        slug = f"{base}-{suffix}"[:80]
        suffix += 1


def user_public(user: sqlite3.Row) -> dict:
    return {
        "id": user["id"],
        "email": user["email"],
        "display_name": user["display_name"],
        "role": user["role"],
        "region": user["region"],
        "theme": user["theme"],
        "locale": user["locale"],
        "member": is_member(user),
        "membership_until": user["membership_until"],
    }


def _stats(conn: sqlite3.Connection, series_id: int) -> sqlite3.Row:
    return conn.execute(
        """
        SELECT COUNT(*) AS episode_count,
               COALESCE(SUM(CASE WHEN duration_flag = 'long' THEN 1 ELSE 0 END), 0) AS long_episode_count
        FROM episodes WHERE series_id = ?
        """,
        (series_id,),
    ).fetchone()


def series_card(conn: sqlite3.Connection, row: sqlite3.Row, reason: str | None = None) -> dict:
    stats = _stats(conn, int(row["id"]))
    return {
        "id": row["id"],
        "slug": row["slug"],
        "title": row["title"],
        "title_en": row["title_en"],
        "synopsis": row["synopsis"],
        "synopsis_en": row["synopsis_en"],
        "genre": row["genre"],
        "genre_en": row["genre_en"],
        "region": row["region"],
        "cover_url": f"/api/covers/{row['id']}" if row["cover_path"] else None,
        "episode_count": stats["episode_count"],
        "free_count": row["free_count"],
        "play_count": row["play_count"],
        "long_episode_count": stats["long_episode_count"],
        "numbering_note": row["numbering_note"],
        "reason": reason,
    }


def _region_clause(region: str | None) -> tuple[str, list[object]]:
    if not region or region in {"ALL", "GLOBAL"}:
        return "", []
    return " WHERE region IN ('GLOBAL', '', ?)", [region]


def list_series(conn: sqlite3.Connection, region: str | None = None) -> list[sqlite3.Row]:
    clause, args = _region_clause(region)
    return list(conn.execute(f"SELECT * FROM series{clause} ORDER BY id ASC", args).fetchall())


def home_payload(conn: sqlite3.Connection, region: str | None) -> dict:
    total = conn.execute("SELECT COUNT(*) AS n FROM series").fetchone()["n"]
    rows = list_series(conn, region)
    cards = [series_card(conn, row) for row in rows]
    groups: dict[tuple[str, str], list[dict]] = {}
    for card in cards:
        groups.setdefault((card["genre"], card["genre_en"]), []).append(card)
    genres = [
        {"genre": genre, "genre_en": genre_en, "series": items}
        for (genre, genre_en), items in sorted(groups.items(), key=lambda item: item[0][0])
    ]
    popular = [series_card(conn, row, "plays") for row in rows if row["play_count"] > 0]
    popular.sort(key=lambda card: (-card["play_count"], card["id"]))
    return {
        "catalog_empty": total == 0,
        "series_count": total,
        "visible_count": len(cards),
        "hero": cards[:5],
        "genres": genres,
        "popular": popular[:8],
    }


def search_series(conn: sqlite3.Connection, query: str, region: str | None) -> list[dict]:
    needle = query.casefold().strip()
    results = []
    for row in list_series(conn, region):
        if not needle:
            results.append(series_card(conn, row))
            continue
        haystack = " ".join(
            [row["title"], row["title_en"], row["genre"], row["genre_en"], row["synopsis"], row["synopsis_en"]]
        ).casefold()
        if needle in haystack:
            results.append(series_card(conn, row))
    return results


def get_series(conn: sqlite3.Connection, slug: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM series WHERE slug = ?", (slug,)).fetchone()


def access_for(user: sqlite3.Row | None, number: int, free_count: int, playable: bool) -> str:
    if not playable:
        return "unavailable"
    if number <= free_count:
        return "free"
    if is_member(user):
        return "member"
    return "locked"


def series_detail(conn: sqlite3.Connection, row: sqlite3.Row, user: sqlite3.Row | None) -> dict:
    episodes = conn.execute(
        "SELECT * FROM episodes WHERE series_id = ? ORDER BY number ASC",
        (row["id"],),
    ).fetchall()
    positions = {}
    if user is not None and episodes:
        ids = [item["id"] for item in episodes]
        marks = ",".join("?" for _ in ids)
        for item in conn.execute(
            f"SELECT episode_id, position_seconds FROM history WHERE user_id = ? AND episode_id IN ({marks})",
            [user["id"], *ids],
        ):
            positions[item["episode_id"]] = item["position_seconds"]
    like_count = conn.execute(
        "SELECT COUNT(*) AS n FROM reactions WHERE series_id = ? AND kind = 'like'",
        (row["id"],),
    ).fetchone()["n"]
    liked = False
    favorited = False
    if user is not None:
        liked = (
            conn.execute(
                "SELECT 1 FROM reactions WHERE user_id = ? AND series_id = ? AND kind = 'like'",
                (user["id"], row["id"]),
            ).fetchone()
            is not None
        )
        favorited = (
            conn.execute(
                "SELECT 1 FROM favorites WHERE user_id = ? AND series_id = ?",
                (user["id"], row["id"]),
            ).fetchone()
            is not None
        )
    payload_episodes = []
    for episode in episodes:
        subtitles = json.loads(episode["subtitles_json"] or "[]")
        renditions = json.loads(episode["renditions_json"] or "[]")
        payload_episodes.append(
            {
                "id": episode["id"],
                "number": episode["number"],
                "title": episode["title"],
                "duration_seconds": episode["duration_seconds"],
                "duration_flag": episode["duration_flag"],
                "width": episode["width"],
                "height": episode["height"],
                "access": access_for(user, episode["number"], row["free_count"], bool(episode["browser_playable"])),
                "browser_playable": bool(episode["browser_playable"]),
                "playback_block": episode["playback_block"] if "playback_block" in episode.keys() else "",
                "has_subtitle": bool(subtitles),
                "rendition_count": 1 + len(renditions) if episode["media_path"] else len(renditions),
                "play_count": episode["play_count"],
                "position_seconds": positions.get(episode["id"], 0),
            }
        )
    return {
        "series": series_card(conn, row),
        "episodes": payload_episodes,
        "liked": liked,
        "like_count": like_count,
        "favorited": favorited,
        "recommendations": recommend(conn, row),
    }


def recommend(conn: sqlite3.Connection, row: sqlite3.Row, limit: int = 8) -> list[dict]:
    chosen: list[dict] = []
    seen = {int(row["id"])}
    if row["genre"] and row["genre"] != "未分类":
        for other in conn.execute(
            """
            SELECT * FROM series
            WHERE id != ? AND genre = ?
            ORDER BY play_count DESC, id ASC
            LIMIT ?
            """,
            (row["id"], row["genre"], limit),
        ):
            chosen.append(series_card(conn, other, "same_genre"))
            seen.add(int(other["id"]))
    if len(chosen) < limit:
        for other in conn.execute(
            "SELECT * FROM series WHERE id != ? ORDER BY play_count DESC, id ASC",
            (row["id"],),
        ):
            if int(other["id"]) in seen:
                continue
            chosen.append(series_card(conn, other, "catalog"))
            seen.add(int(other["id"]))
            if len(chosen) >= limit:
                break
    return chosen


def get_episode(conn: sqlite3.Connection, episode_id: int) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT episodes.*, series.slug AS series_slug, series.free_count AS free_count, series.title AS series_title
        FROM episodes JOIN series ON series.id = episodes.series_id
        WHERE episodes.id = ?
        """,
        (episode_id,),
    ).fetchone()


def playback_sources(episode: sqlite3.Row) -> list[dict]:
    height = int(episode["height"] or 0)
    sources = [
        {
            "id": "source",
            "height": height,
            "label_zh": f"{height}p" if height else "原片",
            "label_en": f"{height}p" if height else "Original",
            "url": f"/api/media/episodes/{episode['id']}?rendition=source",
        }
    ]
    for item in json.loads(episode["renditions_json"] or "[]"):
        if not item.get("path"):
            continue
        sources.append(
            {
                "id": item["id"],
                "height": item.get("height") or 0,
                "label_zh": item.get("label_zh") or "原片",
                "label_en": item.get("label_en") or "Original",
                "url": f"/api/media/episodes/{episode['id']}?rendition={item['id']}",
            }
        )
    return sources


def playback_subtitles(episode: sqlite3.Row) -> list[dict]:
    items = []
    for item in json.loads(episode["subtitles_json"] or "[]"):
        if not item.get("path"):
            continue
        items.append(
            {
                "id": item["id"],
                "lang": item.get("lang") or "und",
                "label_zh": item.get("label_zh") or "字幕",
                "label_en": item.get("label_en") or "Subtitles",
                "url": f"/api/media/episodes/{episode['id']}/subtitles/{item['id']}",
            }
        )
    return items


def rendition_path(episode: sqlite3.Row, rendition: str) -> str | None:
    if rendition == "source":
        return episode["media_path"]
    for item in json.loads(episode["renditions_json"] or "[]"):
        if item.get("id") == rendition:
            return item.get("path")
    return None


def subtitle_path(episode: sqlite3.Row, subtitle_id: str) -> str | None:
    for item in json.loads(episode["subtitles_json"] or "[]"):
        if item.get("id") == subtitle_id:
            return item.get("path")
    return None


def next_episode(conn: sqlite3.Connection, episode: sqlite3.Row) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT * FROM episodes
        WHERE series_id = ? AND number > ?
        ORDER BY number ASC LIMIT 1
        """,
        (episode["series_id"], episode["number"]),
    ).fetchone()


def record_start(conn: sqlite3.Connection, episode: sqlite3.Row, viewer_key: str, user: sqlite3.Row | None) -> dict:
    cutoff = iso(utcnow() - timedelta(seconds=START_DEBOUNCE_SECONDS))
    recent = conn.execute(
        """
        SELECT id FROM playback_events
        WHERE viewer_key = ? AND episode_id = ? AND kind = 'start' AND created_at >= ?
        """,
        (viewer_key, episode["id"], cutoff),
    ).fetchone()
    if recent:
        current = conn.execute("SELECT play_count FROM episodes WHERE id = ?", (episode["id"],)).fetchone()
        return {"counted": False, "play_count": current["play_count"]}
    conn.execute(
        "INSERT INTO playback_events (viewer_key, user_id, episode_id, kind, created_at) VALUES (?, ?, ?, 'start', ?)",
        (viewer_key, user["id"] if user else None, episode["id"], iso()),
    )
    conn.execute("UPDATE episodes SET play_count = play_count + 1 WHERE id = ?", (episode["id"],))
    conn.execute("UPDATE series SET play_count = play_count + 1 WHERE id = ?", (episode["series_id"],))
    current = conn.execute("SELECT play_count FROM episodes WHERE id = ?", (episode["id"],)).fetchone()
    return {"counted": True, "play_count": current["play_count"]}


def save_progress(conn: sqlite3.Connection, user: sqlite3.Row, episode_id: int, position: float, completed: bool) -> None:
    conn.execute(
        """
        INSERT INTO history (user_id, episode_id, position_seconds, completed, updated_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(user_id, episode_id) DO UPDATE SET
          position_seconds = excluded.position_seconds,
          completed = excluded.completed,
          updated_at = excluded.updated_at
        """,
        (user["id"], episode_id, max(0.0, position), 1 if completed else 0, iso()),
    )


def history_for(conn: sqlite3.Connection, user: sqlite3.Row) -> list[dict]:
    rows = conn.execute(
        """
        SELECT history.position_seconds, history.updated_at, episodes.id AS episode_id, episodes.number,
               episodes.duration_seconds, series.slug, series.title, series.title_en, series.id AS series_id,
               series.cover_path
        FROM history
        JOIN episodes ON episodes.id = history.episode_id
        JOIN series ON series.id = episodes.series_id
        WHERE history.user_id = ?
        ORDER BY history.updated_at DESC
        LIMIT 50
        """,
        (user["id"],),
    ).fetchall()
    return [
        {
            "episode_id": row["episode_id"],
            "series_slug": row["slug"],
            "series_title": row["title"],
            "series_title_en": row["title_en"],
            "cover_url": f"/api/covers/{row['series_id']}" if row["cover_path"] else None,
            "number": row["number"],
            "position_seconds": row["position_seconds"],
            "duration_seconds": row["duration_seconds"],
            "updated_at": row["updated_at"],
        }
        for row in rows
    ]


def favorites_for(conn: sqlite3.Connection, user: sqlite3.Row) -> list[dict]:
    rows = conn.execute(
        """
        SELECT series.* FROM favorites
        JOIN series ON series.id = favorites.series_id
        WHERE favorites.user_id = ?
        ORDER BY favorites.created_at DESC
        """,
        (user["id"],),
    ).fetchall()
    return [series_card(conn, row) for row in rows]


def set_favorite(conn: sqlite3.Connection, user: sqlite3.Row, series_id: int, on: bool) -> bool:
    if on:
        conn.execute(
            "INSERT OR IGNORE INTO favorites (user_id, series_id, created_at) VALUES (?, ?, ?)",
            (user["id"], series_id, iso()),
        )
    else:
        conn.execute("DELETE FROM favorites WHERE user_id = ? AND series_id = ?", (user["id"], series_id))
    return on


def toggle_like(conn: sqlite3.Connection, user: sqlite3.Row, series_id: int) -> dict:
    existing = conn.execute(
        "SELECT 1 FROM reactions WHERE user_id = ? AND series_id = ? AND kind = 'like'",
        (user["id"], series_id),
    ).fetchone()
    if existing:
        conn.execute(
            "DELETE FROM reactions WHERE user_id = ? AND series_id = ? AND kind = 'like'",
            (user["id"], series_id),
        )
        liked = False
    else:
        conn.execute(
            "INSERT INTO reactions (user_id, series_id, kind, created_at) VALUES (?, ?, 'like', ?)",
            (user["id"], series_id, iso()),
        )
        liked = True
    count = conn.execute(
        "SELECT COUNT(*) AS n FROM reactions WHERE series_id = ? AND kind = 'like'",
        (series_id,),
    ).fetchone()["n"]
    return {"liked": liked, "count": count}


def list_comments(conn: sqlite3.Connection, episode_id: int) -> list[dict]:
    rows = conn.execute(
        """
        SELECT comments.id, comments.body, comments.created_at, users.display_name
        FROM comments JOIN users ON users.id = comments.user_id
        WHERE comments.episode_id = ? AND comments.status = 'visible'
        ORDER BY comments.id ASC
        LIMIT 100
        """,
        (episode_id,),
    ).fetchall()
    return [
        {"id": row["id"], "body": row["body"], "created_at": row["created_at"], "display_name": row["display_name"]}
        for row in rows
    ]


def add_comment(conn: sqlite3.Connection, user: sqlite3.Row, episode_id: int, body: str) -> tuple[str | None, dict | None]:
    reason = moderate(body)
    if reason:
        conn.execute(
            "INSERT INTO audit (actor_id, action, detail, created_at) VALUES (?, 'comment_reject', ?, ?)",
            (user["id"], json.dumps({"reason": reason, "episode_id": episode_id}), iso()),
        )
        return reason, None
    cleaned = body.strip()
    cutoff = iso(utcnow() - timedelta(seconds=15))
    if conn.execute(
        "SELECT 1 FROM comments WHERE user_id = ? AND created_at >= ? LIMIT 1",
        (user["id"], cutoff),
    ).fetchone():
        return "fast", None
    day = iso(utcnow() - timedelta(days=1))
    count = conn.execute(
        "SELECT COUNT(*) AS n FROM comments WHERE user_id = ? AND created_at >= ?",
        (user["id"], day),
    ).fetchone()["n"]
    if count >= 30:
        return "flood", None
    duplicate_cutoff = iso(utcnow() - timedelta(minutes=5))
    if conn.execute(
        "SELECT 1 FROM comments WHERE user_id = ? AND body = ? AND created_at >= ? LIMIT 1",
        (user["id"], cleaned, duplicate_cutoff),
    ).fetchone():
        return "duplicate", None
    cur = conn.execute(
        "INSERT INTO comments (user_id, episode_id, body, status, created_at) VALUES (?, ?, ?, 'visible', ?)",
        (user["id"], episode_id, cleaned, iso()),
    )
    return None, {"id": cur.lastrowid, "body": cleaned, "created_at": iso(), "display_name": user["display_name"]}


def _bill(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "plan_code": row["plan_code"],
        "kind": row["kind"],
        "list_price_cents": row["list_price_cents"],
        "charged_cents": row["charged_cents"],
        "currency": row["currency"],
        "status": row["status"],
        "note": row["note"],
        "created_at": row["created_at"],
    }


def billing_for(conn: sqlite3.Connection, user: sqlite3.Row) -> dict:
    bills = conn.execute(
        "SELECT * FROM bills WHERE user_id = ? ORDER BY id DESC LIMIT 50",
        (user["id"],),
    ).fetchall()
    fresh = conn.execute("SELECT * FROM users WHERE id = ?", (user["id"],)).fetchone()
    return {"member": is_member(fresh), "membership_until": fresh["membership_until"], "plan": dict(PLAN), "bills": [_bill(row) for row in bills]}


def activate_membership(conn: sqlite3.Connection, user: sqlite3.Row) -> dict:
    cutoff = iso(utcnow() - timedelta(seconds=60))
    recent = conn.execute(
        """
        SELECT * FROM bills
        WHERE user_id = ? AND plan_code = ? AND kind = 'activate' AND created_at >= ?
        ORDER BY id DESC LIMIT 1
        """,
        (user["id"], PLAN["code"], cutoff),
    ).fetchone()
    fresh = conn.execute("SELECT * FROM users WHERE id = ?", (user["id"],)).fetchone()
    if recent:
        return {"bill": _bill(recent), "idempotent": True, "member": is_member(fresh), "membership_until": fresh["membership_until"]}
    now = utcnow()
    current = parse_iso(fresh["membership_until"])
    start = current if current and current > now else now
    until = iso(start + timedelta(days=PLAN["days"]))
    conn.execute("UPDATE users SET membership_until = ? WHERE id = ?", (until, user["id"]))
    cur = conn.execute(
        """
        INSERT INTO bills (user_id, plan_code, kind, list_price_cents, charged_cents, currency, status, note, created_at)
        VALUES (?, ?, 'activate', ?, 0, 'USD', 'simulated', ?, ?)
        """,
        (user["id"], PLAN["code"], PLAN["list_price_cents"], "演示账单，未发生真实扣款", iso()),
    )
    bill = conn.execute("SELECT * FROM bills WHERE id = ?", (cur.lastrowid,)).fetchone()
    return {"bill": _bill(bill), "idempotent": False, "member": True, "membership_until": until}


def cancel_membership(conn: sqlite3.Connection, user: sqlite3.Row) -> dict:
    now = iso()
    conn.execute("UPDATE users SET membership_until = ? WHERE id = ?", (now, user["id"]))
    conn.execute(
        """
        INSERT INTO bills (user_id, plan_code, kind, list_price_cents, charged_cents, currency, status, note, created_at)
        VALUES (?, ?, 'cancel', ?, 0, 'USD', 'simulated', ?, ?)
        """,
        (user["id"], PLAN["code"], PLAN["list_price_cents"], "演示会员已取消，未发生真实退款", now),
    )
    return billing_for(conn, user)


def register_user(conn: sqlite3.Connection, email: str, password_hash: str, display_name: str) -> sqlite3.Row:
    cur = conn.execute(
        """
        INSERT INTO users (email, password_hash, display_name, role, region, created_at)
        VALUES (?, ?, ?, 'viewer', 'ALL', ?)
        """,
        (email, password_hash, display_name, iso()),
    )
    return conn.execute("SELECT * FROM users WHERE id = ?", (cur.lastrowid,)).fetchone()


def too_many_logins(conn: sqlite3.Connection, email: str) -> bool:
    cutoff = iso(utcnow() - timedelta(minutes=15))
    conn.execute("DELETE FROM login_attempts WHERE failed_at < ?", (cutoff,))
    count = conn.execute(
        "SELECT COUNT(*) AS n FROM login_attempts WHERE email = ? AND failed_at >= ?",
        (email, cutoff),
    ).fetchone()["n"]
    return count >= 8


def record_login_failure(conn: sqlite3.Connection, email: str) -> None:
    conn.execute("INSERT INTO login_attempts (email, failed_at) VALUES (?, ?)", (email, iso()))


def clear_login_failures(conn: sqlite3.Connection, email: str) -> None:
    conn.execute("DELETE FROM login_attempts WHERE email = ?", (email,))


def create_session(conn: sqlite3.Connection, user_id: int, token_hash: str) -> None:
    conn.execute(
        "INSERT INTO sessions (token_hash, user_id, expires_at, created_at) VALUES (?, ?, ?, ?)",
        (token_hash, user_id, iso(utcnow() + timedelta(days=30)), iso()),
    )


def user_by_token(conn: sqlite3.Connection, token_hash: str) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT users.* FROM sessions
        JOIN users ON users.id = sessions.user_id
        WHERE sessions.token_hash = ? AND sessions.expires_at > ?
        """,
        (token_hash, iso()),
    ).fetchone()


def delete_session(conn: sqlite3.Connection, token_hash: str) -> None:
    conn.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))


def update_user(conn: sqlite3.Connection, user_id: int, fields: dict) -> sqlite3.Row:
    allowed = {"display_name", "region", "theme", "locale"}
    sets = []
    values: list[object] = []
    for key, value in fields.items():
        if key in allowed:
            sets.append(f"{key} = ?")
            values.append(value)
    if sets:
        values.append(user_id)
        conn.execute(f"UPDATE users SET {', '.join(sets)} WHERE id = ?", values)
    return conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def create_series_record(conn: sqlite3.Connection, title: str, fields: dict) -> sqlite3.Row:
    now = iso()
    slug = unique_slug(conn, title)
    cur = conn.execute(
        """
        INSERT INTO series (
          slug, title, title_en, synopsis, synopsis_en, genre, genre_en, region,
          free_count, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 2, ?, ?)
        """,
        (
            slug,
            title,
            fields.get("title_en") or "",
            fields.get("synopsis") or "",
            fields.get("synopsis_en") or "",
            fields.get("genre") or "未分类",
            fields.get("genre_en") or "Uncategorized",
            fields.get("region") or "GLOBAL",
            now,
            now,
        ),
    )
    return conn.execute("SELECT * FROM series WHERE id = ?", (cur.lastrowid,)).fetchone()


def update_series_record(conn: sqlite3.Connection, series_id: int, fields: dict) -> sqlite3.Row | None:
    allowed = {"title", "title_en", "synopsis", "synopsis_en", "genre", "genre_en", "region"}
    sets = []
    values: list[object] = []
    for key, value in fields.items():
        if key in allowed and isinstance(value, str):
            sets.append(f"{key} = ?")
            values.append(value.strip())
    if sets:
        sets.append("updated_at = ?")
        values.append(iso())
        values.append(series_id)
        conn.execute(f"UPDATE series SET {', '.join(sets)} WHERE id = ?", values)
    return conn.execute("SELECT * FROM series WHERE id = ?", (series_id,)).fetchone()


def creator_overview(conn: sqlite3.Connection) -> dict:
    series_rows = conn.execute("SELECT * FROM series ORDER BY id ASC").fetchall()
    payload = []
    for row in series_rows:
        episodes = conn.execute(
            """
            SELECT id, number, title, duration_seconds, duration_flag, play_count, browser_playable
            FROM episodes WHERE series_id = ? ORDER BY number ASC
            """,
            (row["id"],),
        ).fetchall()
        payload.append(
            {
                "id": row["id"],
                "slug": row["slug"],
                "title": row["title"],
                "genre": row["genre"],
                "play_count": row["play_count"],
                "numbering_note": row["numbering_note"],
                "episodes": [dict(item) for item in episodes],
            }
        )
    plays = conn.execute("SELECT COALESCE(SUM(play_count), 0) AS n FROM series").fetchone()["n"]
    return {"series": payload, "play_count": plays}


def health_counts(conn: sqlite3.Connection) -> tuple[int, int]:
    series = conn.execute("SELECT COUNT(*) AS n FROM series").fetchone()["n"]
    episodes = conn.execute("SELECT COUNT(*) AS n FROM episodes").fetchone()["n"]
    return series, episodes

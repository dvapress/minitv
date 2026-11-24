from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

from fastapi import APIRouter, Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from app import catalog, gate, media
from app.config import Settings
from app.db import connect, iso
from app.security import hash_password, new_token, token_hash, verify_password
from app.selection import load_selection

router = APIRouter()
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
VIEWER_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


class Credentials(BaseModel):
    email: str
    password: str
    display_name: str | None = None


class ProfilePatch(BaseModel):
    display_name: str | None = None
    region: str | None = None
    theme: str | None = None
    locale: str | None = None


class SeriesWrite(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    title_en: str = ""
    synopsis: str = ""
    synopsis_en: str = ""
    genre: str = "未分类"
    genre_en: str = "Uncategorized"
    region: str = "GLOBAL"


class SeriesPatch(BaseModel):
    title: str | None = None
    title_en: str | None = None
    synopsis: str | None = None
    synopsis_en: str | None = None
    genre: str | None = None
    genre_en: str | None = None
    region: str | None = None


class PlaybackBody(BaseModel):
    episode_id: int


class ProgressBody(BaseModel):
    episode_id: int
    position_seconds: float = 0
    completed: bool = False


class CommentBody(BaseModel):
    body: str


def fail(status: int, code: str, zh: str, en: str, request: Request) -> None:
    lang = request.headers.get("accept-language", "zh")
    message = en if lang.lower().startswith("en") else zh
    raise HTTPException(status_code=status, detail={"code": code, "message": message})


def get_conn(request: Request):
    conn = connect(request.app.state.settings)
    try:
        yield conn
    except HTTPException:
        conn.commit()
        raise
    except Exception:
        conn.rollback()
        raise
    else:
        conn.commit()
    finally:
        conn.close()


def current_user(request: Request, conn: sqlite3.Connection = Depends(get_conn)) -> sqlite3.Row | None:
    token = request.cookies.get("ld_session")
    if not token:
        return None
    return catalog.user_by_token(conn, token_hash(token))


def require_user(request: Request, user: sqlite3.Row | None = Depends(current_user)) -> sqlite3.Row:
    if user is None:
        fail(401, "auth_required", "请先登录", "Sign in first", request)
    return user


def require_creator(request: Request, user: sqlite3.Row = Depends(require_user)) -> sqlite3.Row:
    if user["role"] not in {"admin", "creator"}:
        fail(403, "forbidden", "需要创作者或管理员权限", "Creator access is required", request)
    return user


def cookie_secure(settings: Settings, request: Request) -> bool:
    mode = settings.cookie_secure
    if mode in {"1", "true", "yes"}:
        return True
    if mode in {"0", "false", "no"}:
        return False
    forwarded = request.headers.get("x-forwarded-proto", request.url.scheme)
    return forwarded.split(",")[0].strip().lower() == "https"


def set_session_cookie(response: Response, request: Request, token: str) -> None:
    settings: Settings = request.app.state.settings
    response.set_cookie(
        "ld_session",
        token,
        httponly=True,
        samesite="lax",
        secure=cookie_secure(settings, request),
        max_age=30 * 24 * 3600,
        path="/",
    )


def issue_session(conn: sqlite3.Connection, response: Response, request: Request, user: sqlite3.Row) -> dict:
    token = new_token()
    catalog.create_session(conn, int(user["id"]), token_hash(token))
    set_session_cookie(response, request, token)
    return catalog.user_public(user)


def viewer_key(request: Request) -> str:
    raw = request.headers.get("x-viewer", "")
    if VIEWER_RE.fullmatch(raw):
        return raw
    return "anonymous"


def _episode_or_404(conn: sqlite3.Connection, episode_id: int, request: Request) -> sqlite3.Row:
    episode = catalog.get_episode(conn, episode_id)
    if episode is None:
        fail(404, "not_found", "找不到这一集", "Episode not found", request)
    return episode


def _guard_playback(episode: sqlite3.Row, user: sqlite3.Row | None, request: Request) -> None:
    if not episode["browser_playable"] or not episode["media_path"]:
        block = episode["playback_block"] if "playback_block" in episode.keys() else ""
        if block == "hevc":
            fail(
                404,
                "codec_unsupported",
                "这集是 HEVC。Chrome 里时间轴可以走，但画面是黑的。请另存 H.264 派生文件（如 1.browser.mp4），不要改原片，然后重新导入。",
                "This episode is HEVC. Chrome can move the timeline while the picture stays black. Add an H.264 sibling such as 1.browser.mp4 without modifying the original, then import again.",
                request,
            )
        if block == "high10":
            fail(
                404,
                "codec_unsupported",
                "这集的 H.264 不是 8-bit 4:2:0，Chrome 可能画不出画面。请另存一份 yuv420p 的 H.264 派生文件，不要改原片。",
                "This H.264 file is not 8-bit 4:2:0, so Chrome may leave the picture black. Add a yuv420p H.264 sibling without modifying the original.",
                request,
            )
        fail(404, "not_playable", "这一集没有可在浏览器播放的文件", "This episode has no browser-playable file", request)
    access = catalog.access_for(user, int(episode["number"]), int(episode["free_count"]), True)
    if access == "locked":
        fail(
            403,
            "membership_required",
            "第 1–2 集免费。后续集数需要演示会员，开通不会产生真实扣费。",
            "Episodes 1–2 are free. Later episodes need a demo membership. Activating it does not charge anything.",
            request,
        )


@router.get("/health")
def health(request: Request) -> JSONResponse:
    settings: Settings = request.app.state.settings
    if settings.gate_enabled:
        try:
            conn = connect(settings)
            try:
                conn.execute("SELECT 1").fetchone()
            finally:
                conn.close()
            return JSONResponse(gate.public_health())
        except Exception:
            return JSONResponse({"status": "degraded", "service": "leapdrama"}, status_code=503)
    payload = {
        "status": "ok",
        "service": "leapdrama",
        "demo": True,
        "db": "ok",
        "data_writable": False,
        "series_count": 0,
        "episode_count": 0,
        "ui": (settings.static_dir / "index.html").is_file(),
        "payments": "simulated",
        "media": "local",
        "ai": False,
        "cdn": False,
        "offline_download": False,
        "bind": settings.bind,
        "port": settings.port,
    }
    try:
        probe = settings.data_dir / ".health-write"
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        payload["data_writable"] = True
        conn = connect(settings)
        try:
            conn.execute("SELECT 1").fetchone()
            series, episodes = catalog.health_counts(conn)
            payload["series_count"] = series
            payload["episode_count"] = episodes
        finally:
            conn.close()
    except Exception:
        payload["status"] = "degraded"
        payload["db"] = "error"
        return JSONResponse(payload, status_code=503)
    return JSONResponse(payload)


@router.get("/api/config")
def config(request: Request) -> dict:
    settings: Settings = request.app.state.settings
    selection = load_selection(settings.selection_path)
    return {
        "brand": "LeapDrama",
        "public_base_url": settings.public_base_url,
        "demo": True,
        "payments": "simulated",
        "media": "local",
        "cdn": False,
        "ai": False,
        "offline_download": False,
        "locales": ["zh", "en"],
        "default_locale": "zh",
        "regions": catalog.REGIONS,
        "gate": settings.gate_enabled,
        "free_episodes": settings.free_episode_count,
        "max_episode_seconds": settings.max_episode_seconds,
        "selection": {
            "episode_from": selection["episode_from"],
            "episode_to": selection["episode_to"],
            "include": selection["include"],
            "exclude": selection["exclude"],
            "inventory_note": selection.get("inventory_note") or "",
        },
    }


@router.get("/api/home")
def home(region: str = "ALL", conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    return catalog.home_payload(conn, region)


@router.get("/api/search")
def search(q: str = "", region: str = "ALL", conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    return {"query": q, "results": catalog.search_series(conn, q, region)}


@router.get("/api/series/{slug}")
def series_detail(
    slug: str,
    request: Request,
    conn: sqlite3.Connection = Depends(get_conn),
    user: sqlite3.Row | None = Depends(current_user),
) -> dict:
    row = catalog.get_series(conn, slug)
    if row is None:
        fail(404, "not_found", "找不到这部剧", "Series not found", request)
    return catalog.series_detail(conn, row, user)


@router.post("/api/auth/register")
def register(
    body: Credentials,
    request: Request,
    response: Response,
    conn: sqlite3.Connection = Depends(get_conn),
) -> dict:
    email = body.email.strip().lower()
    if not EMAIL_RE.fullmatch(email) or len(email) > 200:
        fail(400, "invalid_email", "邮箱格式不正确", "Enter a valid email", request)
    if len(body.password) < 8 or len(body.password) > 200:
        fail(400, "weak_password", "密码至少 8 位", "Use at least 8 characters", request)
    if conn.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone():
        fail(409, "email_taken", "这个邮箱已经注册", "That email is already registered", request)
    name = (body.display_name or email.split("@", 1)[0]).strip()[:40] or "观众"
    user = catalog.register_user(conn, email, hash_password(body.password), name)
    return issue_session(conn, response, request, user)


@router.post("/api/auth/login")
def login(
    body: Credentials,
    request: Request,
    response: Response,
    conn: sqlite3.Connection = Depends(get_conn),
) -> dict:
    email = body.email.strip().lower()
    if catalog.too_many_logins(conn, email):
        fail(429, "rate_limited", "尝试次数过多，请稍后再试", "Too many attempts. Try again later.", request)
    user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    if user is None or not verify_password(body.password, user["password_hash"]):
        catalog.record_login_failure(conn, email)
        fail(401, "invalid_login", "邮箱或密码不正确", "Email or password is incorrect", request)
    catalog.clear_login_failures(conn, email)
    return issue_session(conn, response, request, user)


@router.post("/api/auth/logout")
def logout(request: Request, response: Response, conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    token = request.cookies.get("ld_session")
    if token:
        catalog.delete_session(conn, token_hash(token))
    response.delete_cookie("ld_session", path="/")
    return {"ok": True}


@router.get("/api/me")
def me(user: sqlite3.Row | None = Depends(current_user)) -> dict | None:
    if user is None:
        return None
    return catalog.user_public(user)


@router.patch("/api/me")
def patch_me(
    body: ProfilePatch,
    request: Request,
    conn: sqlite3.Connection = Depends(get_conn),
    user: sqlite3.Row = Depends(require_user),
) -> dict:
    fields = {}
    if body.display_name is not None:
        name = body.display_name.strip()
        if not name or len(name) > 40:
            fail(400, "invalid_name", "昵称需要 1–40 个字", "Use a display name of 1–40 characters", request)
        fields["display_name"] = name
    if body.region is not None:
        if body.region not in catalog.REGIONS:
            fail(400, "invalid_region", "不支持这个地区", "Unsupported region", request)
        fields["region"] = body.region
    if body.theme is not None:
        if body.theme not in {"light", "dark"}:
            fail(400, "invalid_theme", "主题只能是浅色或深色", "Theme must be light or dark", request)
        fields["theme"] = body.theme
    if body.locale is not None:
        if body.locale not in {"zh", "en"}:
            fail(400, "invalid_locale", "目前只提供中文和英文", "Only Chinese and English are available", request)
        fields["locale"] = body.locale
    updated = catalog.update_user(conn, int(user["id"]), fields)
    return catalog.user_public(updated)


@router.get("/api/me/history")
def my_history(conn: sqlite3.Connection = Depends(get_conn), user: sqlite3.Row = Depends(require_user)) -> dict:
    return {"items": catalog.history_for(conn, user)}


@router.get("/api/me/favorites")
def my_favorites(conn: sqlite3.Connection = Depends(get_conn), user: sqlite3.Row = Depends(require_user)) -> dict:
    return {"items": catalog.favorites_for(conn, user)}


@router.put("/api/me/favorites/{slug}")
def add_favorite(
    slug: str,
    request: Request,
    conn: sqlite3.Connection = Depends(get_conn),
    user: sqlite3.Row = Depends(require_user),
) -> dict:
    row = catalog.get_series(conn, slug)
    if row is None:
        fail(404, "not_found", "找不到这部剧", "Series not found", request)
    catalog.set_favorite(conn, user, int(row["id"]), True)
    return {"favorited": True}


@router.delete("/api/me/favorites/{slug}")
def remove_favorite(
    slug: str,
    request: Request,
    conn: sqlite3.Connection = Depends(get_conn),
    user: sqlite3.Row = Depends(require_user),
) -> dict:
    row = catalog.get_series(conn, slug)
    if row is None:
        fail(404, "not_found", "找不到这部剧", "Series not found", request)
    catalog.set_favorite(conn, user, int(row["id"]), False)
    return {"favorited": False}


@router.post("/api/series/{slug}/like")
def like_series(
    slug: str,
    request: Request,
    conn: sqlite3.Connection = Depends(get_conn),
    user: sqlite3.Row = Depends(require_user),
) -> dict:
    row = catalog.get_series(conn, slug)
    if row is None:
        fail(404, "not_found", "找不到这部剧", "Series not found", request)
    return catalog.toggle_like(conn, user, int(row["id"]))


@router.get("/api/me/billing")
def my_billing(conn: sqlite3.Connection = Depends(get_conn), user: sqlite3.Row = Depends(require_user)) -> dict:
    return catalog.billing_for(conn, user)


@router.post("/api/me/membership")
def activate(conn: sqlite3.Connection = Depends(get_conn), user: sqlite3.Row = Depends(require_user)) -> dict:
    return catalog.activate_membership(conn, user)


@router.post("/api/me/membership/cancel")
def cancel_member(conn: sqlite3.Connection = Depends(get_conn), user: sqlite3.Row = Depends(require_user)) -> dict:
    return catalog.cancel_membership(conn, user)


@router.post("/api/playback/authorize")
def authorize(
    body: PlaybackBody,
    request: Request,
    conn: sqlite3.Connection = Depends(get_conn),
    user: sqlite3.Row | None = Depends(current_user),
) -> dict:
    episode = _episode_or_404(conn, body.episode_id, request)
    _guard_playback(episode, user, request)
    nxt = catalog.next_episode(conn, episode)
    position = 0.0
    if user is not None:
        row = conn.execute(
            "SELECT position_seconds FROM history WHERE user_id = ? AND episode_id = ?",
            (user["id"], episode["id"]),
        ).fetchone()
        if row:
            position = row["position_seconds"]
    next_access = None
    next_id = None
    if nxt is not None:
        next_id = nxt["id"]
        next_access = catalog.access_for(user, int(nxt["number"]), int(episode["free_count"]), bool(nxt["browser_playable"]))
    return {
        "episode_id": episode["id"],
        "series_slug": episode["series_slug"],
        "number": episode["number"],
        "title": episode["title"],
        "duration_seconds": episode["duration_seconds"],
        "duration_flag": episode["duration_flag"],
        "width": episode["width"],
        "height": episode["height"],
        "position_seconds": position,
        "sources": catalog.playback_sources(episode),
        "subtitles": catalog.playback_subtitles(episode),
        "next_episode_id": next_id,
        "next_access": next_access,
    }


@router.post("/api/playback/start")
def playback_start(
    body: PlaybackBody,
    request: Request,
    conn: sqlite3.Connection = Depends(get_conn),
    user: sqlite3.Row | None = Depends(current_user),
) -> dict:
    episode = _episode_or_404(conn, body.episode_id, request)
    _guard_playback(episode, user, request)
    return catalog.record_start(conn, episode, viewer_key(request), user)


@router.post("/api/playback/progress")
def playback_progress(
    body: ProgressBody,
    request: Request,
    conn: sqlite3.Connection = Depends(get_conn),
    user: sqlite3.Row = Depends(require_user),
) -> dict:
    episode = _episode_or_404(conn, body.episode_id, request)
    _guard_playback(episode, user, request)
    catalog.save_progress(conn, user, int(episode["id"]), float(body.position_seconds), body.completed)
    return {"ok": True}


@router.get("/api/episodes/{episode_id}/comments")
def comments(episode_id: int, request: Request, conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    _episode_or_404(conn, episode_id, request)
    return {"comments": catalog.list_comments(conn, episode_id)}


@router.post("/api/episodes/{episode_id}/comments")
def add_comment(
    episode_id: int,
    body: CommentBody,
    request: Request,
    conn: sqlite3.Connection = Depends(get_conn),
    user: sqlite3.Row = Depends(require_user),
) -> dict:
    _episode_or_404(conn, episode_id, request)
    reason, comment = catalog.add_comment(conn, user, episode_id, body.body)
    if reason:
        messages = {
            "length": ("评论需要 1–400 字", "Keep the comment between 1 and 400 characters"),
            "url": ("演示站不接受带链接的评论", "Links are not accepted on this demo"),
            "flood": ("评论过于重复或过于频繁", "That comment looks like flooding"),
            "safety": ("评论未通过安全检查", "That comment failed the safety check"),
            "fast": ("请稍等几秒再发下一条", "Wait a few seconds before another comment"),
            "duplicate": ("这条评论刚刚发过", "That comment was just posted"),
        }
        zh, en = messages.get(reason, ("评论未通过检查", "Comment was rejected"))
        fail(400, f"comment_{reason}", zh, en, request)
    return comment


@router.get("/api/covers/{series_id}")
def cover(series_id: int, request: Request, conn: sqlite3.Connection = Depends(get_conn)):
    row = conn.execute("SELECT cover_path FROM series WHERE id = ?", (series_id,)).fetchone()
    if row is None or not row["cover_path"]:
        fail(404, "not_found", "没有封面", "No cover", request)
    try:
        path = media.resolve_allowed(request.app.state.settings, row["cover_path"])
    except (PermissionError, FileNotFoundError):
        fail(404, "not_found", "没有封面", "No cover", request)
    media_type = "image/jpeg"
    if path.suffix.lower() == ".png":
        media_type = "image/png"
    elif path.suffix.lower() == ".webp":
        media_type = "image/webp"
    return FileResponse(path, media_type=media_type, content_disposition_type="inline")


@router.get("/api/media/episodes/{episode_id}")
def media_file(
    episode_id: int,
    request: Request,
    rendition: str = "source",
    conn: sqlite3.Connection = Depends(get_conn),
    user: sqlite3.Row | None = Depends(current_user),
):
    episode = _episode_or_404(conn, episode_id, request)
    _guard_playback(episode, user, request)
    raw = catalog.rendition_path(episode, rendition)
    if not raw:
        fail(404, "not_found", "没有这个清晰度", "That rendition does not exist", request)
    try:
        path = media.resolve_allowed(request.app.state.settings, raw)
    except (PermissionError, FileNotFoundError):
        fail(404, "not_found", "文件不在允许的目录中", "Media file is not available", request)
    return _file(path)


@router.get("/api/media/episodes/{episode_id}/subtitles/{subtitle_id}")
def media_subtitle(
    episode_id: int,
    subtitle_id: str,
    request: Request,
    conn: sqlite3.Connection = Depends(get_conn),
    user: sqlite3.Row | None = Depends(current_user),
):
    episode = _episode_or_404(conn, episode_id, request)
    _guard_playback(episode, user, request)
    raw = catalog.subtitle_path(episode, subtitle_id)
    if not raw:
        fail(404, "not_found", "没有字幕", "No subtitle", request)
    try:
        path = media.resolve_allowed(request.app.state.settings, raw)
    except (PermissionError, FileNotFoundError):
        fail(404, "not_found", "没有字幕", "No subtitle", request)
    return FileResponse(path, media_type="text/vtt; charset=utf-8", content_disposition_type="inline")


def _file(path: Path) -> FileResponse:
    kind = "application/octet-stream"
    suffix = path.suffix.lower()
    if suffix in {".mp4", ".m4v"}:
        kind = "video/mp4"
    elif suffix == ".webm":
        kind = "video/webm"
    return FileResponse(
        path,
        media_type=kind,
        content_disposition_type="inline",
        headers={"Cache-Control": "private, no-store"},
    )


def _stream_upload(upload: UploadFile, dest: Path, max_bytes: int) -> int:
    dest.parent.mkdir(parents=True, exist_ok=True)
    partial = dest.with_suffix(dest.suffix + ".partial")
    size = 0
    try:
        with partial.open("wb") as handle:
            while True:
                chunk = upload.file.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > max_bytes:
                    raise ValueError("too_large")
                handle.write(chunk)
        partial.replace(dest)
    except Exception:
        partial.unlink(missing_ok=True)
        raise
    return size


@router.get("/api/creator/overview")
def creator_overview(conn: sqlite3.Connection = Depends(get_conn), user: sqlite3.Row = Depends(require_creator)) -> dict:
    del user
    return catalog.creator_overview(conn)


@router.post("/api/creator/series")
def creator_create_series(
    body: SeriesWrite,
    request: Request,
    conn: sqlite3.Connection = Depends(get_conn),
    user: sqlite3.Row = Depends(require_creator),
) -> dict:
    if body.region not in {"GLOBAL", *catalog.REGIONS}:
        fail(400, "invalid_region", "不支持这个地区", "Unsupported region", request)
    row = catalog.create_series_record(conn, body.title.strip(), body.model_dump())
    conn.execute(
        "INSERT INTO audit (actor_id, action, detail, created_at) VALUES (?, 'create_series', ?, ?)",
        (user["id"], json.dumps({"id": row["id"], "title": row["title"]}, ensure_ascii=False), iso()),
    )
    return catalog.series_card(conn, row)


@router.patch("/api/creator/series/{series_id}")
def creator_patch_series(
    series_id: int,
    body: SeriesPatch,
    request: Request,
    conn: sqlite3.Connection = Depends(get_conn),
    user: sqlite3.Row = Depends(require_creator),
) -> dict:
    del user
    if conn.execute("SELECT 1 FROM series WHERE id = ?", (series_id,)).fetchone() is None:
        fail(404, "not_found", "找不到这部剧", "Series not found", request)
    fields = {key: value for key, value in body.model_dump().items() if value is not None}
    if "region" in fields and fields["region"] not in {"GLOBAL", *catalog.REGIONS}:
        fail(400, "invalid_region", "不支持这个地区", "Unsupported region", request)
    row = catalog.update_series_record(conn, series_id, fields)
    return catalog.series_card(conn, row)


@router.post("/api/creator/series/{series_id}/cover")
def creator_cover(
    series_id: int,
    request: Request,
    file: UploadFile = File(...),
    conn: sqlite3.Connection = Depends(get_conn),
    user: sqlite3.Row = Depends(require_creator),
) -> dict:
    del user
    row = conn.execute("SELECT * FROM series WHERE id = ?", (series_id,)).fetchone()
    if row is None:
        fail(404, "not_found", "找不到这部剧", "Series not found", request)
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
        fail(400, "bad_cover", "封面请使用 jpg、png 或 webp", "Use a jpg, png, or webp cover", request)
    settings: Settings = request.app.state.settings
    dest = settings.data_dir / "covers" / f"{series_id}{suffix}"
    try:
        _stream_upload(file, dest, 8 * 1024 * 1024)
    except ValueError:
        fail(413, "too_large", "封面文件过大", "Cover file is too large", request)
    conn.execute("UPDATE series SET cover_path = ?, updated_at = ? WHERE id = ?", (str(dest.resolve()), iso(), series_id))
    updated = conn.execute("SELECT * FROM series WHERE id = ?", (series_id,)).fetchone()
    return catalog.series_card(conn, updated)


@router.post("/api/creator/series/{series_id}/episodes")
def creator_episode(
    series_id: int,
    request: Request,
    number: int = Form(...),
    replace: str = Form("0"),
    file: UploadFile = File(...),
    subtitle: UploadFile | None = File(None),
    conn: sqlite3.Connection = Depends(get_conn),
    user: sqlite3.Row = Depends(require_creator),
) -> dict:
    row = conn.execute("SELECT * FROM series WHERE id = ?", (series_id,)).fetchone()
    if row is None:
        fail(404, "not_found", "找不到这部剧", "Series not found", request)
    if number < 1 or number > 5000:
        fail(400, "bad_number", "集数需要是正整数", "Episode number must be a positive integer", request)
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in media.VIDEO_EXT:
        fail(400, "bad_video", "请上传 mp4、webm、mov 或 mkv", "Upload an mp4, webm, mov, or mkv file", request)
    existing = conn.execute(
        "SELECT id FROM episodes WHERE series_id = ? AND number = ?",
        (series_id, number),
    ).fetchone()
    if existing and replace != "1":
        fail(409, "exists", "这一集已经存在。确认替换时才会覆盖。", "That episode exists. Pass replace to overwrite it.", request)
    settings: Settings = request.app.state.settings
    dest = settings.data_dir / "uploads" / str(series_id) / f"{number}{suffix}"
    try:
        _stream_upload(file, dest, settings.max_upload_bytes)
    except ValueError:
        fail(413, "too_large", "视频超过上传限制", "Video exceeds the upload limit", request)
    info = media.probe(dest)
    if not info["has_video"]:
        dest.unlink(missing_ok=True)
        fail(400, "unreadable", "没有识别到视频画面，这一集没有入库", "No video stream was found, so the episode was not added.", request)
    flag = media.duration_flag(info["duration"], settings.max_episode_seconds)
    playable = dest.suffix.lower() in media.BROWSER_EXT
    subtitles = []
    if subtitle is not None and subtitle.filename:
        sub_suffix = Path(subtitle.filename).suffix.lower()
        if sub_suffix not in {".vtt", ".srt"}:
            fail(400, "bad_subtitle", "字幕请使用 vtt 或 srt", "Subtitles must be vtt or srt", request)
        raw_name = settings.data_dir / "uploads" / str(series_id) / f"{number}{sub_suffix}"
        _stream_upload(subtitle, raw_name, 2 * 1024 * 1024)
        stored = settings.data_dir / "subtitles" / str(series_id) / f"{number}-und.vtt"
        stored.parent.mkdir(parents=True, exist_ok=True)
        text = raw_name.read_text(encoding="utf-8", errors="replace")
        stored.write_text(text if sub_suffix == ".vtt" else media.srt_to_vtt(text), encoding="utf-8")
        subtitles.append(
            {"id": "und", "lang": "und", "label_zh": "字幕", "label_en": "Subtitles", "path": str(stored.resolve())}
        )
    now = iso()
    stat = dest.stat()
    digest = media.sha256_file(dest)
    if existing is None:
        conn.execute(
            """
            INSERT INTO episodes (
              series_id, number, title, duration_seconds, duration_flag, width, height,
              media_path, source_path, source_size, source_mtime_ns, source_sha256,
              renditions_json, subtitles_json, browser_playable, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '[]', ?, ?, ?, ?)
            """,
            (
                series_id,
                number,
                f"第{number}集",
                info["duration"],
                flag,
                info["width"],
                info["height"],
                str(dest.resolve()),
                str(dest.resolve()),
                stat.st_size,
                stat.st_mtime_ns,
                digest,
                json.dumps(subtitles, ensure_ascii=False),
                1 if playable else 0,
                now,
                now,
            ),
        )
    else:
        conn.execute(
            """
            UPDATE episodes SET
              duration_seconds=?, duration_flag=?, width=?, height=?, media_path=?, source_path=?,
              source_size=?, source_mtime_ns=?, source_sha256=?, subtitles_json=?,
              browser_playable=?, updated_at=?
            WHERE id=?
            """,
            (
                info["duration"],
                flag,
                info["width"],
                info["height"],
                str(dest.resolve()),
                str(dest.resolve()),
                stat.st_size,
                stat.st_mtime_ns,
                digest,
                json.dumps(subtitles, ensure_ascii=False) if subtitles else conn.execute("SELECT subtitles_json FROM episodes WHERE id=?", (existing["id"],)).fetchone()["subtitles_json"],
                1 if playable else 0,
                now,
                existing["id"],
            ),
        )
    conn.execute(
        "INSERT INTO audit (actor_id, action, detail, created_at) VALUES (?, 'upload_episode', ?, ?)",
        (
            user["id"],
            json.dumps({"series_id": series_id, "number": number, "duration_flag": flag, "duration_seconds": info["duration"]}, ensure_ascii=False),
            now,
        ),
    )
    return {
        "series_id": series_id,
        "number": number,
        "duration_seconds": info["duration"],
        "duration_flag": flag,
        "browser_playable": playable,
        "width": info["width"],
        "height": info["height"],
    }


@router.post("/api/gate/login")
async def gate_login(request: Request):
    try:
        document = await request.json()
    except Exception:
        document = None
    passcode = document.get("passcode") if isinstance(document, dict) else ""
    if not isinstance(passcode, str):
        passcode = ""
    return gate.login(request, request.app.state.settings, passcode)


@router.post("/api/gate/logout")
def gate_logout(request: Request):
    return gate.logout(request, request.app.state.settings)


def mount_ui(app: FastAPI, settings: Settings) -> None:
    dist = settings.static_dir
    index = dist / "index.html"
    assets = dist / "assets"
    if assets.is_dir():
        from fastapi.staticfiles import StaticFiles

        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        if full_path == "health" or full_path.startswith("api/") or full_path.startswith("api"):
            raise HTTPException(status_code=404)
        if dist.is_dir() and full_path:
            candidate = (dist / full_path).resolve()
            if candidate.is_file() and media.is_under(candidate, dist):
                return FileResponse(candidate)
        if index.is_file():
            return FileResponse(index)
        return JSONResponse(
            {"ui": False, "detail": "Frontend bundle is not built. Run npm run build in demo/web."},
            status_code=503,
        )

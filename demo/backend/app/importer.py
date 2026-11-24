"""Idempotent import of series folders. Source files are never modified."""

from __future__ import annotations

import json
import sqlite3
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from app import media
from app.catalog import slugify, unique_slug
from app.config import Settings
from app.db import connect, iso
from app.selection import load_selection

DISK_MARGIN = 256 * 1024 * 1024
COVER_NAMES = ("cover.jpg", "cover.jpeg", "cover.png", "cover.webp", "poster.jpg", "poster.png", "folder.jpg")


@dataclass
class ImportOptions:
    series: tuple[str, ...] = ()
    all_series: bool = False
    all_episodes: bool = False
    episode_from: int | None = None
    episode_to: int | None = None
    in_place: bool = False
    strict: bool = False
    probe: str = "selected"


@dataclass
class _EpisodeGroup:
    number: int
    primary: Path | None = None
    renditions: list[tuple[int, Path]] = field(default_factory=list)
    subtitles: list[tuple[str, Path]] = field(default_factory=list)
    duplicates: list[str] = field(default_factory=list)


def normalize_name(name: str) -> str:
    return unicodedata.normalize("NFC", name).strip().casefold()


def _series_dirs(root: Path) -> list[Path]:
    children = [
        path
        for path in root.iterdir()
        if path.is_dir() and not path.name.startswith(".") and path.name not in media.SKIP_DIRS
    ]
    selected = []
    for child in children:
        if _episode_files(child):
            selected.append(child)
    if selected:
        return sorted(selected, key=lambda path: path.name)
    if media.video_files(root):
        return [root]
    return []


def _episode_files(folder: Path) -> list[Path]:
    direct = media.video_files(folder)
    if direct:
        return direct
    nested: list[Path] = []
    search_dirs = []
    for child in folder.iterdir():
        if child.is_dir() and not child.name.startswith(".") and child.name not in media.SKIP_DIRS:
            search_dirs.append(child)
            nested.extend(media.video_files(child))
    return nested


def _search_dirs(folder: Path) -> list[Path]:
    dirs = [folder]
    if media.video_files(folder):
        return dirs
    for child in folder.iterdir():
        if child.is_dir() and not child.name.startswith(".") and child.name not in media.SKIP_DIRS:
            if media.video_files(child) or media.subtitle_candidates([child]):
                dirs.append(child)
    return dirs


def _match(folders: list[Path], wanted: str) -> tuple[Path | None, str]:
    target = normalize_name(wanted)
    exact = [path for path in folders if normalize_name(path.name) == target]
    if len(exact) == 1:
        return exact[0], "exact"
    if len(exact) > 1:
        return None, "ambiguous"
    prefixed = [path for path in folders if normalize_name(path.name).startswith(target)]
    if len(prefixed) == 1:
        return prefixed[0], "prefix"
    contained = [path for path in folders if target in normalize_name(path.name)]
    if len(contained) == 1:
        return contained[0], "contains"
    if len(prefixed) > 1 or len(contained) > 1:
        return None, "ambiguous"
    return None, "missing"


def _group_episodes(folder: Path) -> tuple[dict[int, _EpisodeGroup], list[str]]:
    groups: dict[int, _EpisodeGroup] = {}
    unparsed: list[str] = []
    files = _episode_files(folder)
    for path in files:
        number, height = media.classify_video(path)
        if number is None:
            unparsed.append(path.name)
            continue
        group = groups.setdefault(number, _EpisodeGroup(number=number))
        if height is None:
            if group.primary is None:
                group.primary = path
            else:
                current = group.primary
                group.duplicates.append(path.name)
                if path.stat().st_size > current.stat().st_size:
                    group.primary = path
        else:
            group.renditions.append((height, path))
    for group in groups.values():
        if group.primary is None and group.renditions:
            group.renditions.sort(key=lambda item: item[0], reverse=True)
            _height, path = group.renditions.pop(0)
            group.primary = path
    folders = _search_dirs(folder)
    for path in media.subtitle_candidates(folders):
        number, language = media.subtitle_identity(path)
        if number is None or number not in groups:
            continue
        groups[number].subtitles.append((language, path))
    return groups, unparsed


def _read_meta(folder: Path) -> tuple[dict, int | None]:
    path = folder / "meta.json"
    if not path.is_file():
        return {}, None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}, path.stat().st_mtime_ns
    if not isinstance(data, dict):
        return {}, path.stat().st_mtime_ns
    return data, path.stat().st_mtime_ns


def _existing_cover(folder: Path) -> Path | None:
    for name in COVER_NAMES:
        path = folder / name
        if path.is_file():
            return path
    return None


def _window(options: ImportOptions, selection: dict) -> tuple[int, int | None]:
    if options.all_episodes:
        return options.episode_from or 1, None
    start = options.episode_from if options.episode_from is not None else int(selection["episode_from"])
    end = options.episode_to if options.episode_to is not None else int(selection["episode_to"])
    return start, end


def _selected_folders(root: Path, options: ImportOptions, selection: dict) -> tuple[list[tuple[Path, str]], list[dict], list[dict]]:
    folders = _series_dirs(root)
    excluded = {normalize_name(item["name"]): item for item in selection.get("exclude") or []}
    ignored = []
    if options.all_series:
        chosen = [(path, "all") for path in folders]
        return chosen, [], ignored
    wanted = list(options.series) if options.series else list(selection["include"])
    chosen = []
    missing = []
    used = set()
    for name in wanted:
        path, how = _match(folders, name)
        if path is None:
            missing.append({"name": name, "reason": how})
            continue
        used.add(path.resolve())
        chosen.append((path, how))
    if not options.series:
        for path in folders:
            item = excluded.get(normalize_name(path.name))
            if item and path.resolve() not in used:
                ignored.append({"name": path.name, "reason": item.get("reason") or "excluded by selection"})
    return chosen, missing, ignored


def _episode_payload(group: _EpisodeGroup, limit: float, do_probe: bool) -> dict:
    primary = group.primary
    info = media.probe(primary) if primary and do_probe else {"duration": None, "width": 0, "height": 0, "has_video": False, "error": None}
    if not do_probe:
        flag = "not_probed"
        duration = None
    else:
        duration = info["duration"]
        flag = media.duration_flag(duration, limit)
    return {
        "number": group.number,
        "file": primary.name if primary else None,
        "duration_seconds": duration,
        "duration_flag": flag,
        "width": info["width"],
        "height": info["height"],
        "renditions": [height for height, _path in group.renditions],
        "subtitles": [language for language, _path in group.subtitles],
        "duplicates": list(group.duplicates),
    }


def scan_library(root: Path, selection: dict, options: ImportOptions, limit: float) -> dict:
    root = root.expanduser()
    if not root.exists() or not root.is_dir():
        return {
            "status": "missing_root",
            "root": str(root),
            "series": [],
            "missing_series": [],
            "ignored_series": [],
            "policy": _policy(selection, options),
        }
    start, end = _window(options, selection)
    chosen, missing, ignored = _selected_folders(root, options, selection)
    chosen_ids = {path.resolve() for path, _how in chosen}
    series_reports = []
    for folder in _series_dirs(root):
        groups, unparsed = _group_episodes(folder)
        numbers = sorted(groups)
        in_window = [number for number in numbers if number >= start and (end is None or number <= end)]
        outside = [number for number in numbers if number not in in_window]
        selected = folder.resolve() in chosen_ids
        do_probe = options.probe == "all" or (options.probe == "selected" and selected)
        episodes = []
        if do_probe:
            for number in in_window if selected else numbers:
                episodes.append(_episode_payload(groups[number], limit, True))
        series_reports.append(
            {
                "name": folder.name,
                "path": str(folder),
                "selected": selected,
                "episode_numbers": numbers,
                "in_window": in_window,
                "outside_window": outside,
                "missing_numbers": media.missing_numbers(numbers),
                "missing_in_window": media.missing_numbers(in_window),
                "unparsed": unparsed,
                "episodes": episodes,
                "long_episodes": [item["number"] for item in episodes if item["duration_flag"] == "long"],
            }
        )
    status = "empty" if not series_reports else "ok"
    return {
        "status": status,
        "root": str(root.resolve()),
        "series": series_reports,
        "missing_series": missing,
        "ignored_series": ignored,
        "policy": _policy(selection, options),
    }


def _policy(selection: dict, options: ImportOptions) -> dict:
    start, end = _window(options, selection)
    return {
        "include": list(options.series) if options.series else list(selection["include"]),
        "all_series": options.all_series,
        "episode_from": start,
        "episode_to": end,
        "in_place": options.in_place,
        "exclude": selection.get("exclude") or [],
        "inventory_note": selection.get("inventory_note") or "",
    }


def _note(missing: list[int], long_numbers: list[int], outside: list[int]) -> str:
    parts = []
    if missing:
        shown = ",".join(str(number) for number in missing[:24])
        extra = f" (+{len(missing) - 24})" if len(missing) > 24 else ""
        parts.append(f"missing {shown}{extra}")
    if long_numbers:
        parts.append("long " + ",".join(str(number) for number in long_numbers))
    if outside:
        parts.append(f"{len(outside)} episode(s) outside the selected window")
    return "; ".join(parts)


def _apply_meta(conn: sqlite3.Connection, series_id: int, meta: dict, mtime_ns: int | None, folder_name: str, is_new: bool) -> None:
    if not meta and not is_new:
        return
    mapping = {
        "title": "title",
        "title_en": "title_en",
        "synopsis": "synopsis",
        "synopsis_en": "synopsis_en",
        "genre": "genre",
        "genre_en": "genre_en",
        "region": "region",
    }
    sets = []
    values: list[object] = []
    if is_new and not str(meta.get("title") or "").strip():
        sets.append("title = ?")
        values.append(folder_name)
    for key, column in mapping.items():
        if key not in meta:
            continue
        text = str(meta.get(key) or "").strip()
        if not text:
            continue
        sets.append(f"{column} = ?")
        values.append(text)
    if mtime_ns is not None:
        sets.append("meta_mtime_ns = ?")
        values.append(mtime_ns)
    if not sets:
        return
    sets.append("updated_at = ?")
    values.append(iso())
    values.append(series_id)
    conn.execute(f"UPDATE series SET {', '.join(sets)} WHERE id = ?", values)


def _store_subtitle(settings: Settings, series_id: int, number: int, language: str, source: Path) -> str:
    dest_dir = settings.data_dir / "subtitles" / str(series_id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{number}-{language}.vtt"
    if source.resolve() == dest.resolve():
        raise RuntimeError("refusing to overwrite a subtitle source")
    text = source.read_text(encoding="utf-8", errors="replace")
    payload = text if source.suffix.lower() == ".vtt" else media.srt_to_vtt(text)
    partial = dest.with_suffix(".partial")
    partial.write_text(payload, encoding="utf-8")
    partial.replace(dest)
    return str(dest)


def _materialize(settings: Settings, src: Path, dest: Path, in_place: bool) -> str:
    if in_place:
        if not any(media.is_under(src, root) for root in (settings.data_dir, *settings.library_roots)):
            raise PermissionError("in-place media is outside LEAPDRAMA_LIBRARY_ROOTS")
        return str(src.resolve())
    if media.free_bytes(dest if dest.exists() else dest.parent if dest.parent.exists() else settings.data_dir) < src.stat().st_size + DISK_MARGIN:
        raise OSError("not enough free disk to copy media; leaving the source untouched")
    if src.suffix.lower() in {".mov", ".mkv"}:
        if not media.remux_mp4(src, dest.with_suffix(".mp4")):
            raise OSError(f"could not remux {src.name} into a browser mp4; source was not modified")
        return str(dest.with_suffix(".mp4").resolve())
    media.copy_bytes(src, dest)
    return str(dest.resolve())


def _unchanged(row: sqlite3.Row, src: Path) -> bool:
    stat = src.stat()
    if row["source_size"] != stat.st_size or row["source_mtime_ns"] != stat.st_mtime_ns:
        return False
    if row["duration_flag"] == "unknown":
        return False
    media_path = row["media_path"]
    if not media_path or not Path(media_path).is_file():
        return False
    return True


def import_library(settings: Settings, root: Path, options: ImportOptions | None = None) -> dict:
    options = options or ImportOptions()
    selection = load_selection(settings.selection_path)
    limit = settings.max_episode_seconds
    scanned = scan_library(root, selection, options, limit)
    if scanned["status"] == "missing_root":
        scanned["errors"] = []
        scanned["gap_failures"] = []
        scanned["bytes_copied"] = 0
        return scanned
    start, end = _window(options, selection)
    by_path = {str(Path(item["path"]).resolve()): item for item in scanned["series"]}
    chosen, _missing, _ignored = _selected_folders(root.expanduser(), options, selection)
    conn = connect(settings)
    errors = []
    gap_failures = []
    imported_rows = []
    bytes_copied = 0
    try:
        for folder, how in chosen:
            report = by_path.get(str(folder.resolve()))
            if report is None:
                continue
            groups, _unparsed = _group_episodes(folder)
            numbers = sorted(groups)
            in_window = [number for number in numbers if number >= start and (end is None or number <= end)]
            outside = [number for number in numbers if number not in in_window]
            holes = media.missing_numbers(in_window)
            if holes:
                gap_failures.append({"name": folder.name, "missing_in_window": holes})
            meta, meta_mtime = _read_meta(folder)
            key = unicodedata.normalize("NFC", folder.name).strip()
            try:
                row = conn.execute("SELECT * FROM series WHERE source_folder = ?", (key,)).fetchone()
                now = iso()
                created = row is None
                if row is None:
                    title = str(meta.get("title") or "").strip() or folder.name
                    slug = unique_slug(conn, title)
                    cur = conn.execute(
                        """
                        INSERT INTO series (
                          slug, title, title_en, synopsis, synopsis_en, genre, genre_en, region,
                          source_folder, free_count, created_at, updated_at
                        ) VALUES (?, ?, '', '', '', '未分类', 'Uncategorized', 'GLOBAL', ?, ?, ?, ?)
                        """,
                        (slug, title, key, settings.free_episode_count, now, now),
                    )
                    series_id = int(cur.lastrowid)
                else:
                    series_id = int(row["id"])
                _apply_meta(conn, series_id, meta, meta_mtime, folder.name, created)
                episode_reports = []
                long_numbers = []
                for number in in_window:
                    group = groups[number]
                    primary = group.primary
                    if primary is None:
                        continue
                    stat = primary.stat()
                    existing = conn.execute(
                        "SELECT * FROM episodes WHERE series_id = ? AND number = ?",
                        (series_id, number),
                    ).fetchone()
                    action = "imported"
                    if existing and _unchanged(existing, primary):
                        action = "unchanged"
                        info = {
                            "duration": existing["duration_seconds"],
                            "width": existing["width"],
                            "height": existing["height"],
                        }
                        media_path = existing["media_path"]
                        renditions = json.loads(existing["renditions_json"] or "[]")
                        subtitles = json.loads(existing["subtitles_json"] or "[]")
                        playable = bool(existing["browser_playable"])
                        flag = existing["duration_flag"]
                    else:
                        info = media.probe(primary)
                        flag = media.duration_flag(info["duration"], limit)
                        suffix = primary.suffix.lower() or ".mp4"
                        dest = settings.data_dir / "media" / str(series_id) / f"{number}{suffix}"
                        media_path = _materialize(settings, primary, dest, options.in_place)
                        if not options.in_place and Path(media_path).is_file():
                            bytes_copied += Path(media_path).stat().st_size
                        renditions = []
                        for height, rendition_path in sorted(group.renditions, key=lambda item: item[0]):
                            rendition_dest = settings.data_dir / "media" / str(series_id) / f"{number}.{height}p{rendition_path.suffix.lower()}"
                            stored = _materialize(settings, rendition_path, rendition_dest, options.in_place)
                            probed = media.probe(rendition_path)
                            label_height = probed["height"] or height
                            renditions.append(
                                {
                                    "id": f"h{height}",
                                    "height": label_height,
                                    "path": stored,
                                    "label_zh": f"{label_height}p" if label_height else "原片",
                                    "label_en": f"{label_height}p" if label_height else "Original",
                                }
                            )
                        subtitles = []
                        seen_lang = set()
                        for language, subtitle_path in group.subtitles:
                            if language in seen_lang:
                                continue
                            seen_lang.add(language)
                            stored = _store_subtitle(settings, series_id, number, language, subtitle_path)
                            subtitles.append(
                                {
                                    "id": language,
                                    "lang": language,
                                    "label_zh": "字幕" if language == "und" else language,
                                    "label_en": "Subtitles" if language == "und" else language,
                                    "path": stored,
                                }
                            )
                        playable = Path(media_path).suffix.lower() in media.BROWSER_EXT
                        digest = media.sha256_file(primary)
                        if existing is None:
                            conn.execute(
                                """
                                INSERT INTO episodes (
                                  series_id, number, title, duration_seconds, duration_flag, width, height,
                                  media_path, source_path, source_size, source_mtime_ns, source_sha256,
                                  renditions_json, subtitles_json, browser_playable, created_at, updated_at
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                """,
                                (
                                    series_id,
                                    number,
                                    f"第{number}集",
                                    info["duration"],
                                    flag,
                                    info["width"],
                                    info["height"],
                                    media_path,
                                    str(primary.resolve()),
                                    stat.st_size,
                                    stat.st_mtime_ns,
                                    digest,
                                    json.dumps(renditions, ensure_ascii=False),
                                    json.dumps(subtitles, ensure_ascii=False),
                                    1 if playable else 0,
                                    now,
                                    now,
                                ),
                            )
                            action = "imported"
                        else:
                            conn.execute(
                                """
                                UPDATE episodes SET
                                  duration_seconds=?, duration_flag=?, width=?, height=?, media_path=?,
                                  source_path=?, source_size=?, source_mtime_ns=?, source_sha256=?,
                                  renditions_json=?, subtitles_json=?, browser_playable=?, updated_at=?
                                WHERE id=?
                                """,
                                (
                                    info["duration"],
                                    flag,
                                    info["width"],
                                    info["height"],
                                    media_path,
                                    str(primary.resolve()),
                                    stat.st_size,
                                    stat.st_mtime_ns,
                                    digest,
                                    json.dumps(renditions, ensure_ascii=False),
                                    json.dumps(subtitles, ensure_ascii=False),
                                    1 if playable else 0,
                                    now,
                                    existing["id"],
                                ),
                            )
                            action = "updated"
                    if flag == "long":
                        long_numbers.append(number)
                    episode_reports.append(
                        {
                            "number": number,
                            "action": action,
                            "duration_seconds": info["duration"],
                            "duration_flag": flag,
                            "browser_playable": playable,
                            "rendition_count": 1 + len(renditions) if action != "unchanged" else 1 + len(json.loads(existing["renditions_json"] or "[]")),
                            "subtitle_count": len(subtitles) if action != "unchanged" else len(json.loads(existing["subtitles_json"] or "[]")),
                            "duplicates": group.duplicates,
                        }
                    )
                cover_path = None
                existing_cover = _existing_cover(folder)
                cover_dest = settings.data_dir / "covers" / f"{series_id}.jpg"
                if existing_cover is not None:
                    if existing_cover.suffix.lower() in {".jpg", ".jpeg"}:
                        media.copy_bytes(existing_cover, cover_dest)
                    else:
                        # Keep the original cover bytes under a matching suffix.
                        cover_dest = settings.data_dir / "covers" / f"{series_id}{existing_cover.suffix.lower()}"
                        media.copy_bytes(existing_cover, cover_dest)
                    cover_path = str(cover_dest)
                else:
                    first = groups.get(in_window[0]).primary if in_window else None
                    if first is not None:
                        duration = None
                        for item in episode_reports:
                            if item["number"] == in_window[0]:
                                duration = item["duration_seconds"]
                        if media.extract_cover(first, cover_dest, duration):
                            cover_path = str(cover_dest)
                if cover_path:
                    conn.execute("UPDATE series SET cover_path = ?, updated_at = ? WHERE id = ?", (cover_path, iso(), series_id))
                note = _note(media.missing_numbers(numbers), long_numbers, outside)
                conn.execute("UPDATE series SET numbering_note = ?, updated_at = ? WHERE id = ?", (note, iso(), series_id))
                conn.execute(
                    "INSERT INTO audit (actor_id, action, detail, created_at) VALUES (NULL, 'import', ?, ?)",
                    (json.dumps({"series": folder.name, "match": how, "episodes": [item["number"] for item in episode_reports]}, ensure_ascii=False), iso()),
                )
                conn.commit()
                imported_rows.append(
                    {
                        "name": folder.name,
                        "match": how,
                        "series_id": series_id,
                        "episodes": episode_reports,
                        "missing_numbers": media.missing_numbers(numbers),
                        "missing_in_window": holes,
                        "outside_window": outside,
                        "long_episodes": long_numbers,
                        "unparsed": report.get("unparsed") or [],
                    }
                )
            except Exception as exc:  # one series must not abort the rest
                conn.rollback()
                errors.append({"name": folder.name, "error": exc.__class__.__name__, "message": str(exc)})
        status = "empty" if not imported_rows and not errors else "ok"
        if errors and imported_rows:
            status = "partial"
        elif errors:
            status = "error"
        result = {
            "status": status,
            "root": str(root.expanduser().resolve()) if root.exists() else str(root),
            "policy": _policy(selection, options),
            "series": imported_rows,
            "missing_series": scanned["missing_series"],
            "ignored_series": scanned["ignored_series"],
            "gap_failures": gap_failures,
            "errors": errors,
            "bytes_copied": bytes_copied,
            "inventory": [item for item in scanned["series"] if not item["selected"]],
        }
        _write_report(settings, result)
        return result
    finally:
        conn.close()


def _write_report(settings: Settings, result: dict) -> None:
    path = settings.data_dir / "last-import-report.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def strict_failed(result: dict) -> bool:
    if result.get("status") == "missing_root":
        return False
    if result.get("missing_series"):
        return True
    if result.get("gap_failures"):
        return True
    return False

"""Local media helpers. Original files are never trimmed or rewritten."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

from app.config import Settings

VIDEO_EXT = {".mp4", ".m4v", ".webm", ".mov", ".mkv"}
BROWSER_EXT = {".mp4", ".m4v", ".webm"}
SUBTITLE_EXT = {".vtt", ".srt"}
RENDITION_HEIGHTS = {360, 480, 540, 720, 1080, 1440, 2160}
SKIP_DIRS = {"__MACOSX", "extras", "sample", "samples"}


def tool(name: str) -> str | None:
    return shutil.which(name)


def is_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def resolve_allowed(settings: Settings, raw: str) -> Path:
    path = Path(raw).expanduser().resolve()
    roots = (settings.data_dir, *settings.library_roots)
    if not any(is_under(path, root) for root in roots):
        raise PermissionError("media path is outside the allowed roots")
    if not path.is_file():
        raise FileNotFoundError(path.name)
    return path


def split_rendition(stem: str) -> tuple[str, int | None]:
    match = re.match(r"^(?P<base>.+?)[._-](?P<height>\d{3,4})p$", stem, re.IGNORECASE)
    if not match:
        return stem, None
    height = int(match.group("height"))
    if height not in RENDITION_HEIGHTS:
        return stem, None
    return match.group("base"), height


def episode_number_from_stem(stem: str) -> int | None:
    stem = stem.strip()
    if re.fullmatch(r"\d{1,4}", stem):
        number = int(stem)
        return number if number >= 1 else None
    match = re.search(r"第\s*(\d{1,4})\s*集", stem)
    if match:
        number = int(match.group(1))
        return number if number >= 1 else None
    match = re.search(
        r"(?:^|[^A-Za-z0-9])(?:ep|episode|e)[\s._-]*(\d{1,4})\b",
        stem,
        re.IGNORECASE,
    )
    if match:
        number = int(match.group(1))
        return number if number >= 1 else None
    groups = re.findall(r"\d{1,4}", stem)
    if not groups:
        return None
    non_years = [group for group in groups if not re.fullmatch(r"(?:19|20)\d{2}", group)]
    chosen = non_years[-1] if non_years else groups[-1]
    number = int(chosen)
    return number if number >= 1 else None


def classify_video(path: Path) -> tuple[int | None, int | None]:
    base, height = split_rendition(path.stem)
    number = episode_number_from_stem(base if height is not None else path.stem)
    return number, height


def missing_numbers(numbers: list[int]) -> list[int]:
    if len(numbers) < 2:
        return []
    present = set(numbers)
    return [number for number in range(min(numbers), max(numbers) + 1) if number not in present]


def duration_flag(seconds: float | None, limit: float) -> str:
    if seconds is None:
        return "unknown"
    if seconds > limit + 0.05:
        return "long"
    return "ok"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def copy_bytes(src: Path, dest: Path) -> None:
    """Copy without re-encoding. dest must not be the source path."""
    if src.resolve() == dest.resolve():
        raise RuntimeError("refusing to write a media file onto its source")
    dest.parent.mkdir(parents=True, exist_ok=True)
    partial = dest.with_suffix(dest.suffix + ".partial")
    shutil.copy2(src, partial)
    os.replace(partial, dest)


def free_bytes(path: Path) -> int:
    target = path if path.exists() else path.parent
    while not target.exists() and target != target.parent:
        target = target.parent
    return shutil.disk_usage(target).free


def probe(path: Path) -> dict:
    ffprobe = tool("ffprobe")
    if not ffprobe:
        return {"duration": None, "width": 0, "height": 0, "has_video": False, "error": "ffprobe-missing"}
    try:
        result = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-show_entries",
                "format=duration:stream=codec_type,width,height",
                "-of",
                "json",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=40,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"duration": None, "width": 0, "height": 0, "has_video": False, "error": str(exc)}
    if result.returncode != 0:
        return {"duration": None, "width": 0, "height": 0, "has_video": False, "error": "ffprobe-failed"}
    try:
        document = json.loads(result.stdout or "{}")
    except json.JSONDecodeError:
        return {"duration": None, "width": 0, "height": 0, "has_video": False, "error": "ffprobe-json"}
    width = 0
    height = 0
    has_video = False
    for stream in document.get("streams") or []:
        if stream.get("codec_type") == "video":
            has_video = True
            width = int(stream.get("width") or 0)
            height = int(stream.get("height") or 0)
            break
    raw_duration = (document.get("format") or {}).get("duration")
    duration = None
    if raw_duration not in (None, ""):
        try:
            duration = float(raw_duration)
        except (TypeError, ValueError):
            duration = None
    return {"duration": duration, "width": width, "height": height, "has_video": has_video, "error": None}


def extract_cover(video: Path, dest: Path, duration: float | None) -> bool:
    ffmpeg = tool("ffmpeg")
    if not ffmpeg:
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    partial = dest.with_suffix(".partial.jpg")
    timestamp = "0.5" if duration is None or duration > 0.6 else "0"
    try:
        result = subprocess.run(
            [
                ffmpeg,
                "-y",
                "-loglevel",
                "error",
                "-ss",
                timestamp,
                "-i",
                str(video),
                "-frames:v",
                "1",
                "-vf",
                "scale=480:-2",
                str(partial),
            ],
            capture_output=True,
            timeout=40,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        partial.unlink(missing_ok=True)
        return False
    if result.returncode != 0 or not partial.is_file() or partial.stat().st_size < 80:
        partial.unlink(missing_ok=True)
        return False
    os.replace(partial, dest)
    return True


def remux_mp4(src: Path, dest: Path) -> bool:
    """Stream-copy into a new mp4. The source path is only an input."""
    ffmpeg = tool("ffmpeg")
    if not ffmpeg or src.resolve() == dest.resolve():
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    partial = dest.with_suffix(".partial.mp4")
    try:
        result = subprocess.run(
            [ffmpeg, "-y", "-loglevel", "error", "-i", str(src), "-c", "copy", "-movflags", "+faststart", str(partial)],
            capture_output=True,
            timeout=120,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        partial.unlink(missing_ok=True)
        return False
    if result.returncode != 0 or not partial.is_file() or partial.stat().st_size < 80:
        partial.unlink(missing_ok=True)
        return False
    os.replace(partial, dest)
    return True


def srt_to_vtt(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").lstrip("\ufeff")
    lines = []
    for line in normalized.split("\n"):
        if "-->" in line:
            line = line.replace(",", ".")
        lines.append(line)
    return "WEBVTT\n\n" + "\n".join(lines).strip() + "\n"


def subtitle_identity(path: Path) -> tuple[int | None, str]:
    stem = path.stem
    language = "und"
    match = re.search(r"[._-](zh-hans|zh-hant|zh|en)$", stem, re.IGNORECASE)
    if match:
        language = match.group(1).lower()
        stem = stem[: match.start()]
    base, _height = split_rendition(stem)
    return episode_number_from_stem(base), language


def video_files(folder: Path) -> list[Path]:
    files = []
    for path in folder.iterdir():
        if not path.is_file() or path.name.startswith("."):
            continue
        if path.suffix.lower() in VIDEO_EXT:
            files.append(path)
    return files


def subtitle_candidates(folders: list[Path]) -> list[Path]:
    found = []
    seen = set()
    for folder in folders:
        if not folder.is_dir():
            continue
        for path in folder.iterdir():
            if not path.is_file() or path.name.startswith("."):
                continue
            if path.suffix.lower() in SUBTITLE_EXT and path.resolve() not in seen:
                seen.add(path.resolve())
                found.append(path)
    return found

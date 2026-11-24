"""Read MP4 sample-entry codecs without ffmpeg and without rewriting the file."""

from __future__ import annotations

from pathlib import Path

CONTAINERS = {b"moov", b"trak", b"mdia", b"minf", b"stbl"}
HEVC = {"hvc1", "hev1", "dvh1", "dvhe"}
AVC_PROFILES = {0, 66, 77, 100}
VIDEO_TYPES = {"avc1", "avc3", "hvc1", "hev1", "dvh1", "dvhe", "mp4v", "av01", "vp09", "vp08", "encv"}
AUDIO_TYPES = {"mp4a", "ac-3", "ec-3", "Opus", "fLaC", "sowt", "twos"}


def inspect(path: Path) -> dict:
    empty = {"video": "", "audio": "", "profile": 0, "playable": False, "reason": "unknown", "width": 0, "height": 0, "duration": None}
    suffix = path.suffix.lower()
    if suffix == ".webm":
        return {**empty, "video": "webm", "playable": True, "reason": "ok"}
    if suffix not in {".mp4", ".m4v", ".mov"}:
        return empty
    try:
        videos, audios, meta = _codecs(path)
    except OSError:
        return empty
    video = videos[0][0] if videos else ""
    profile = videos[0][1] if videos else 0
    audio = audios[0] if audios else ""
    playable = any(name in {"avc1", "avc3"} and level in AVC_PROFILES for name, level in videos)
    if playable:
        reason = "ok"
    elif any(name in HEVC for name, _level in videos):
        reason = "hevc"
    elif any(level in {110, 122, 144} for name, level in videos if name in {"avc1", "avc3"}):
        reason = "high10"
    elif videos:
        reason = "unsupported"
    else:
        reason = "unknown"
    return {
        "video": video,
        "audio": audio,
        "profile": profile,
        "playable": playable,
        "reason": reason,
        "width": meta["width"],
        "height": meta["height"],
        "duration": meta["duration"],
    }


def _codecs(path: Path) -> tuple[list[tuple[str, int]], list[str], dict]:
    videos: list[tuple[str, int]] = []
    audios: list[str] = []
    meta = {"width": 0, "height": 0, "duration": None}

    def on_box(kind: bytes, start: int, end: int, handle) -> None:
        if end - start > 1_000_000 or end <= start:
            return
        handle.seek(start)
        blob = handle.read(end - start)
        if kind == b"stsd":
            for name, profile in _sample_entries(blob):
                if name in VIDEO_TYPES:
                    videos.append((name, profile))
                elif name in AUDIO_TYPES:
                    audios.append(name)
        elif kind == b"mvhd" and meta["duration"] is None:
            meta["duration"] = _mvhd_duration(blob)
        elif kind == b"tkhd" and meta["width"] == 0:
            width, height = _tkhd_size(blob)
            if width and height:
                meta["width"], meta["height"] = width, height

    with path.open("rb") as handle:
        handle.seek(0, 2)
        size = handle.tell()
        _walk(handle, 0, size, on_box)
    return videos, audios, meta


def _mvhd_duration(blob: bytes) -> float | None:
    if len(blob) < 20:
        return None
    version = blob[0]
    if version == 0 and len(blob) >= 20:
        timescale = int.from_bytes(blob[12:16], "big")
        duration = int.from_bytes(blob[16:20], "big")
    elif version == 1 and len(blob) >= 32:
        timescale = int.from_bytes(blob[20:24], "big")
        duration = int.from_bytes(blob[24:32], "big")
    else:
        return None
    if timescale <= 0:
        return None
    return duration / timescale


def _tkhd_size(blob: bytes) -> tuple[int, int]:
    if len(blob) < 4:
        return 0, 0
    version = blob[0]
    offset = 88 if version == 1 else 76
    if len(blob) < offset + 8:
        return 0, 0
    width = int.from_bytes(blob[offset : offset + 4], "big") >> 16
    height = int.from_bytes(blob[offset + 4 : offset + 8], "big") >> 16
    return width, height


def _walk(handle, start: int, end: int, on_box) -> None:
    pos = start
    while pos + 8 <= end:
        handle.seek(pos)
        header = handle.read(8)
        if len(header) < 8:
            return
        size = int.from_bytes(header[:4], "big")
        kind = header[4:8]
        header_len = 8
        if size == 1:
            extra = handle.read(8)
            if len(extra) < 8:
                return
            size = int.from_bytes(extra, "big")
            header_len = 16
        elif size == 0:
            size = end - pos
        if size < header_len:
            return
        body_start = pos + header_len
        body_end = pos + size
        if kind in CONTAINERS:
            _walk(handle, body_start, min(body_end, end), on_box)
        else:
            on_box(kind, body_start, min(body_end, end), handle)
        pos += size


def _sample_entries(blob: bytes) -> list[tuple[str, int]]:
    if len(blob) < 8:
        return []
    count = int.from_bytes(blob[4:8], "big")
    pos = 8
    found: list[tuple[str, int]] = []
    for _ in range(min(count, 8)):
        if pos + 8 > len(blob):
            break
        size = int.from_bytes(blob[pos : pos + 4], "big")
        if size < 8 or pos + size > len(blob):
            break
        name = blob[pos + 4 : pos + 8].decode("latin1", errors="replace")
        entry = blob[pos : pos + size]
        profile = 0
        marker = entry.find(b"avcC")
        if marker >= 4 and marker + 6 < len(entry):
            profile = entry[marker + 5]
        found.append((name, profile))
        pos += size
    return found


def split_browser_derivative(path: Path) -> tuple[str, bool]:
    stem = path.stem
    for suffix in (".browser", ".h264"):
        if stem.lower().endswith(suffix):
            return stem[: -len(suffix)], True
    return stem, False

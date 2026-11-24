from __future__ import annotations

import hashlib
import json
import logging
import shutil
from pathlib import Path

import pytest

from app.cli import run
from app.config import load_settings
from app.importer import ImportOptions, import_library
from app.main import create_app
from app.media import episode_number_from_stem, missing_numbers, split_rendition
from app.selection import DEFAULT_SELECTION
from conftest import ffmpeg_available

DEMO_ROOT = Path(__file__).resolve().parents[2]

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def test_episode_numbers_are_numeric_not_lexical():
    assert episode_number_from_stem("1") == 1
    assert episode_number_from_stem("02") == 2
    assert episode_number_from_stem("10") == 10
    assert episode_number_from_stem("第2集") == 2
    assert episode_number_from_stem("第10集") == 10
    assert episode_number_from_stem("EP03") == 3
    assert episode_number_from_stem("锦鲤娘_2024_02") == 2
    assert episode_number_from_stem("poster") is None
    assert split_rendition("1.720p") == ("1", 720)
    assert missing_numbers([22, 24, 43, 45])
    assert 23 in missing_numbers([22, 24, 43, 45])
    assert 44 in missing_numbers([22, 24, 43, 45])
    ordered = sorted([10, 2, 1])
    assert ordered == [1, 2, 10]


def test_selection_policy_matches_inventory():
    data = json.loads((DEMO_ROOT / "import-selection.json").read_text(encoding="utf-8"))
    assert data["include"] == ["锦鲤娘", "孝子贤孙", "全家听我心声", "爹爹开门"]
    assert data["episode_from"] == 1 and data["episode_to"] == 10
    assert DEFAULT_SELECTION["include"] == data["include"]
    excluded = {item["name"] for item in data["exclude"]}
    assert "白月光反击说明书" in excluded


def test_default_listen_address(monkeypatch, tmp_path):
    for name in ("LEAPDRAMA_BIND", "LEAPDRAMA_PORT", "LEAPDRAMA_DATA_DIR", "LEAPDRAMA_ADMIN_PASSWORD", "LEAPDRAMA_SECRET_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("LEAPDRAMA_DATA_DIR", str(tmp_path))
    settings = load_settings()
    assert settings.bind == "127.0.0.1"
    assert settings.port == 18080


def test_generated_credentials_are_not_logged(tmp_path, monkeypatch, caplog):
    monkeypatch.delenv("LEAPDRAMA_ADMIN_PASSWORD", raising=False)
    monkeypatch.delenv("LEAPDRAMA_SECRET_KEY", raising=False)
    monkeypatch.setenv("LEAPDRAMA_DATA_DIR", str(tmp_path))
    caplog.set_level(logging.INFO)
    create_app(load_settings())
    password = (tmp_path / "admin.password").read_text(encoding="utf-8").split("password=", 1)[1].strip()
    secret = (tmp_path / "secret.key").read_text(encoding="utf-8").strip()
    assert password not in caplog.text
    assert secret not in caplog.text
    assert "not logged" in caplog.text
    assert (tmp_path / "admin.password").stat().st_mode & 0o777 == 0o600
    assert password.lower() not in {"admin", "password", "leapdrama"}


def test_weak_admin_password_is_rejected(monkeypatch, tmp_path):
    monkeypatch.setenv("LEAPDRAMA_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("LEAPDRAMA_ADMIN_PASSWORD", "password")
    with pytest.raises(SystemExit):
        load_settings()


def test_templates_do_not_embed_secrets_or_foreign_ports():
    example = (DEMO_ROOT / ".env.example").read_text(encoding="utf-8")
    for line in example.splitlines():
        if not line or line.strip().startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if "PASSWORD" in key or "SECRET" in key:
            assert value.strip() == ""
    for relative in ("scripts/install-user.sh", "scripts/serve.sh", "docker-compose.yml", "Dockerfile"):
        path = DEMO_ROOT / relative
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        assert "docker.sock" not in text
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, _, value = stripped.partition("=")
            if "PASSWORD" in key.upper() or key.upper().endswith("SECRET"):
                assert value.strip() in {"", '""', "''"}
    unit = (DEMO_ROOT / "deploy" / "leapdrama-demo.service").read_text(encoding="utf-8")
    serve = (DEMO_ROOT / "scripts" / "serve.sh").read_text(encoding="utf-8")
    install = (DEMO_ROOT / "scripts" / "install-user.sh").read_text(encoding="utf-8")
    assert "8787" in serve and "20242" in serve
    assert "__APP_ROOT__" in unit
    for line in install.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        assert not stripped.startswith("sudo")
        assert " sudo " not in f" {stripped} "


def _copy(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)


def _library(root: Path, clips: dict[str, Path]) -> None:
    short = clips["short"]
    for name, files in {
        "锦鲤娘": ["1.mp4", "2.mp4", "12.mp4", "poster.mp4"],
        "孝子贤孙": ["1.mp4", "2.mp4", "10.mp4"],
        "全家听我心声": ["1.mp4", "2.mp4"],
        "爹爹开门": ["1.mp4", "2.mp4", "4.mp4"],
        "其他剧": ["1.mp4"],
    }.items():
        for filename in files:
            _copy(short, root / name / filename)
    _copy(clips["long"], root / "锦鲤娘" / "3.mp4")
    _copy(clips["tall"], root / "孝子贤孙" / "1.720p.mp4")
    (root / "孝子贤孙" / "1.vtt").write_text("WEBVTT\n\n00:00:00.000 --> 00:00:01.000\n你好\n", encoding="utf-8")
    (root / "孝子贤孙" / "meta.json").write_text(
        json.dumps({"genre": "都市", "genre_en": "Urban", "synopsis": "验证题材"}, ensure_ascii=False),
        encoding="utf-8",
    )
    (root / "全家听我心声" / "meta.json").write_text(
        json.dumps({"genre": "都市", "genre_en": "Urban"}, ensure_ascii=False),
        encoding="utf-8",
    )
    for number in (22, 24, 43, 45):
        _copy(short, root / "白月光反击说明书" / f"{number}.mp4")


@pytest.mark.skipif(not ffmpeg_available(), reason="ffmpeg is required")
def test_import_policy_playback_and_persistence(env, clips):
    library = env.tmp / "library"
    _library(library, clips)
    source = library / "锦鲤娘" / "3.mp4"
    before = sha256(source)
    names_before = sorted(path.name for path in (library / "锦鲤娘").iterdir())

    first = import_library(env.settings, library, ImportOptions())
    assert first["status"] == "ok"
    imported = {item["name"] for item in first["series"]}
    assert imported == {"锦鲤娘", "孝子贤孙", "全家听我心声", "爹爹开门"}
    assert "白月光反击说明书" not in imported
    assert "其他剧" not in imported
    ignored = {item["name"] for item in first["ignored_series"]}
    assert "白月光反击说明书" in ignored
    carp = next(item for item in first["series"] if item["name"] == "锦鲤娘")
    assert [episode["number"] for episode in carp["episodes"]] == [1, 2, 3]
    assert 12 in carp["outside_window"]
    assert "poster.mp4" in carp["unparsed"]
    assert 3 in carp["long_episodes"]
    long = next(episode for episode in carp["episodes"] if episode["number"] == 3)
    assert long["duration_flag"] == "long"
    assert long["duration_seconds"] > 180
    assert sha256(source) == before
    assert sorted(path.name for path in (library / "锦鲤娘").iterdir()) == names_before

    filial = next(item for item in first["series"] if item["name"] == "孝子贤孙")
    assert [episode["number"] for episode in filial["episodes"]] == [1, 2, 10]
    door = next(item for item in first["series"] if item["name"] == "爹爹开门")
    assert door["missing_in_window"] == [3]
    assert [episode["number"] for episode in door["episodes"]] == [1, 2, 4]

    second = import_library(env.settings, library, ImportOptions())
    assert all(episode["action"] == "unchanged" for item in second["series"] for episode in item["episodes"])
    assert sha256(source) == before

    inventory = run(["inventory", str(library), "--json", "--data-dir", str(env.settings.data_dir)])
    assert inventory == 0
    strict = run(["import", str(library), "--strict", "--json", "--data-dir", str(env.settings.data_dir)])
    assert strict == 4
    missing_root = run(["import", str(env.tmp / "missing"), "--json", "--data-dir", str(env.settings.data_dir)])
    assert missing_root == 2

    client = env.client
    config = client.get("/api/config").json()
    assert config["payments"] == "simulated"
    assert config["offline_download"] is False
    assert config["ai"] is False
    assert config["cdn"] is False
    home = client.get("/api/home").json()
    encoded = json.dumps(home)
    assert "bunny" not in encoded.lower()
    assert "stripe" not in encoded.lower()
    assert ".mp4" not in encoded
    assert home["catalog_empty"] is False
    found = client.get("/api/search", params={"q": "孝子"}).json()["results"]
    assert found and found[0]["title"] == "孝子贤孙"

    detail = client.get("/api/series/孝子贤孙").json()
    numbers = [episode["number"] for episode in detail["episodes"]]
    assert numbers == [1, 2, 10]
    first_ep = detail["episodes"][0]
    assert first_ep["has_subtitle"] is True
    assert first_ep["rendition_count"] == 2
    assert detail["episodes"][1]["has_subtitle"] is False
    assert detail["recommendations"][0]["reason"] == "same_genre"
    assert detail["recommendations"][0]["slug"] == "全家听我心声"

    carp_detail = client.get("/api/series/锦鲤娘").json()
    by_number = {episode["number"]: episode for episode in carp_detail["episodes"]}
    free = client.post("/api/playback/authorize", json={"episode_id": by_number[1]["id"]})
    assert free.status_code == 200
    body = free.json()
    assert len(body["sources"]) == 1
    assert "1080p" not in json.dumps(body)
    assert "/tmp" not in json.dumps(body)
    media = client.get(body["sources"][0]["url"])
    assert media.status_code == 200
    assert media.content[:8] != b""
    assert media.headers["content-type"].startswith("video/")
    locked = client.post("/api/playback/authorize", json={"episode_id": by_number[3]["id"]})
    assert locked.status_code == 403
    assert locked.json()["detail"]["code"] == "membership_required"
    assert str(source) not in locked.text
    blocked_media = client.get(f"/api/media/episodes/{by_number[3]['id']}")
    assert blocked_media.status_code == 403
    traversal = client.get(f"/api/media/episodes/{by_number[1]['id']}?rendition=../../etc/passwd")
    assert traversal.status_code == 404

    viewer = client.post("/api/playback/start", json={"episode_id": by_number[1]["id"]}, headers={"X-Viewer": "viewerkey012345"})
    assert viewer.json()["counted"] is True
    again = client.post("/api/playback/start", json={"episode_id": by_number[1]["id"]}, headers={"X-Viewer": "viewerkey012345"})
    assert again.json()["counted"] is False
    assert again.json()["play_count"] == viewer.json()["play_count"]

    filial_auth = client.post("/api/playback/authorize", json={"episode_id": first_ep["id"]}).json()
    assert len(filial_auth["sources"]) == 2
    assert len(filial_auth["subtitles"]) == 1
    subtitle = client.get(filial_auth["subtitles"][0]["url"])
    assert subtitle.status_code == 200
    assert "WEBVTT" in subtitle.text

    assert client.get("/api/creator/overview").status_code == 401
    registered = client.post("/api/auth/register", json={"email": "viewer@example.com", "password": "viewer-password"})
    assert registered.status_code == 200
    assert client.get("/api/creator/overview").status_code == 403
    still_locked = client.post("/api/playback/authorize", json={"episode_id": by_number[3]["id"]})
    assert still_locked.status_code == 403
    activated = client.post("/api/me/membership", json={"charged_cents": 5000})
    assert activated.status_code == 200
    assert activated.json()["bill"]["charged_cents"] == 0
    assert activated.json()["bill"]["list_price_cents"] == 990
    assert activated.json()["bill"]["status"] == "simulated"
    opened = client.post("/api/playback/authorize", json={"episode_id": by_number[3]["id"]})
    assert opened.status_code == 200
    saved = client.post("/api/playback/progress", json={"episode_id": by_number[1]["id"], "position_seconds": 4.5})
    assert saved.status_code == 200
    assert client.get("/api/me/history").json()["items"][0]["position_seconds"] == 4.5
    favorite = client.put("/api/me/favorites/锦鲤娘")
    assert favorite.json()["favorited"] is True
    rejected = client.post(f"/api/episodes/{by_number[1]['id']}/comments", json={"body": "see http://example.com"})
    assert rejected.status_code == 400
    accepted = client.post(f"/api/episodes/{by_number[1]['id']}/comments", json={"body": "这一集很好看"})
    assert accepted.status_code == 200
    listed = client.get(f"/api/episodes/{by_number[1]['id']}/comments").json()["comments"]
    assert [item["body"] for item in listed] == ["这一集很好看"]

    from fastapi.testclient import TestClient

    restarted = TestClient(create_app(env.settings))
    logged = restarted.post("/api/auth/login", json={"email": "viewer@example.com", "password": "viewer-password"})
    assert logged.status_code == 200
    assert restarted.get("/api/me/history").json()["items"][0]["position_seconds"] == 4.5
    assert restarted.get("/api/me/favorites").json()["items"][0]["slug"] == "锦鲤娘"
    health = restarted.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert health.json()["payments"] == "simulated"
    assert health.json()["port"] == 18080


@pytest.mark.skipif(not ffmpeg_available(), reason="ffmpeg is required")
def test_creator_upload_requires_auth_and_keeps_long_files(env, clips):
    client = env.client
    anonymous = client.post("/api/creator/series", json={"title": "不应成功"})
    assert anonymous.status_code == 401
    logged = client.post("/api/auth/login", json={"email": "admin@leapdrama.demo", "password": env.password})
    assert logged.status_code == 200
    created = client.post("/api/creator/series", json={"title": "创作者短片", "genre": "悬疑", "genre_en": "Mystery"})
    assert created.status_code == 200
    series_id = created.json()["id"]
    with clips["long"].open("rb") as handle:
        uploaded = client.post(
            f"/api/creator/series/{series_id}/episodes",
            data={"number": "5"},
            files={"file": ("episode.mp4", handle, "video/mp4")},
        )
    assert uploaded.status_code == 200
    assert uploaded.json()["duration_flag"] == "long"
    assert uploaded.json()["number"] == 5
    overview = client.get("/api/creator/overview").json()
    match = next(item for item in overview["series"] if item["id"] == series_id)
    assert match["episodes"][0]["duration_flag"] == "long"
    with clips["short"].open("rb") as handle:
        duplicate = client.post(
            f"/api/creator/series/{series_id}/episodes",
            data={"number": "5"},
            files={"file": ("episode.mp4", handle, "video/mp4")},
        )
    assert duplicate.status_code == 409


def test_empty_library_does_not_invent_media(env):
    empty = env.tmp / "empty"
    empty.mkdir()
    result = import_library(env.settings, empty, ImportOptions())
    assert result["status"] == "empty"
    home = env.client.get("/api/home").json()
    assert home["catalog_empty"] is True
    assert home["hero"] == []
    health = env.client.get("/health").json()
    assert health["series_count"] == 0
    assert health["media"] == "local"

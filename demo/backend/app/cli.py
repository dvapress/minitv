"""LeapDrama operator CLI. It never prints generated passwords or signing keys."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from app.config import load_settings
from app.db import connect, init_db
from app.importer import ImportOptions, import_library, scan_library, strict_failed
from app.selection import load_selection


def _print(payload: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    status = payload.get("status") or payload.get("db") or "ok"
    print(f"status: {status}")
    if payload.get("root"):
        print(f"root: {payload['root']}")
    policy = payload.get("policy") or {}
    if policy:
        end = policy.get("episode_to")
        window = f"{policy.get('episode_from')}-{end if end is not None else 'end'}"
        names = ", ".join(policy.get("include") or [])
        print(f"policy: episodes {window}; series: {names or '(all)'}")
    for item in payload.get("missing_series") or []:
        print(f"missing series: {item.get('name')} ({item.get('reason')})")
    for item in payload.get("ignored_series") or []:
        print(f"not selected: {item.get('name')}")
    for item in payload.get("series") or []:
        name = item.get("name")
        if "episodes" in item and item["episodes"] and isinstance(item["episodes"][0], dict) and "action" in item["episodes"][0]:
            actions = ", ".join(f"{ep['number']}:{ep['action']}:{ep['duration_flag']}" for ep in item["episodes"])
            long_list = ",".join(str(number) for number in item.get("long_episodes") or []) or "-"
            missing = ",".join(str(number) for number in item.get("missing_numbers") or []) or "-"
            print(f"{name}: {actions}")
            print(f"  long: {long_list}; missing in full span: {missing}")
        else:
            numbers = item.get("episode_numbers") or []
            selected = "selected" if item.get("selected") else "not-selected"
            missing = ",".join(str(number) for number in (item.get("missing_numbers") or [])[:20]) or "-"
            print(f"{name}: {selected} episodes={len(numbers)} missing={missing}")
    for item in payload.get("errors") or []:
        print(f"error: {item.get('name')}: {item.get('message')}")


def _options(args: argparse.Namespace) -> ImportOptions:
    return ImportOptions(
        series=tuple(args.series or []),
        all_series=bool(args.all_series),
        all_episodes=bool(args.all_episodes),
        episode_from=args.from_episode,
        episode_to=args.to_episode,
        in_place=bool(args.in_place),
        strict=bool(args.strict),
        probe=args.probe,
    )


def _apply_data_dir(args: argparse.Namespace) -> None:
    if getattr(args, "data_dir", None):
        import os

        os.environ["LEAPDRAMA_DATA_DIR"] = args.data_dir


def command_import(args: argparse.Namespace) -> int:
    _apply_data_dir(args)
    settings = load_settings()
    init_db(settings)
    root = Path(args.path)
    result = import_library(settings, root, _options(args))
    if args.report:
        Path(args.report).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _print(result, args.json)
    if result.get("status") == "missing_root":
        return 2
    if args.strict and strict_failed(result):
        return 4
    if result.get("errors"):
        return 3
    return 0


def command_inventory(args: argparse.Namespace) -> int:
    _apply_data_dir(args)
    settings = load_settings()
    root = Path(args.path)
    selection = load_selection(settings.selection_path)
    result = scan_library(root, selection, _options(args), settings.max_episode_seconds)
    if args.report:
        Path(args.report).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _print(result, args.json)
    if result.get("status") == "missing_root":
        return 2
    return 0


def command_health(args: argparse.Namespace) -> int:
    if args.url:
        try:
            with urllib.request.urlopen(args.url, timeout=5) as response:
                body = json.loads(response.read().decode("utf-8"))
                print(json.dumps(body, ensure_ascii=False, indent=2))
                return 0 if response.status == 200 and body.get("status") == "ok" else 1
        except Exception as exc:
            print(f"health check failed: {exc.__class__.__name__}", file=sys.stderr)
            return 1
    _apply_data_dir(args)
    settings = load_settings()
    try:
        init_db(settings)
        conn = connect(settings)
        try:
            conn.execute("SELECT 1").fetchone()
        finally:
            conn.close()
    except Exception as exc:
        print(f"database check failed: {exc.__class__.__name__}", file=sys.stderr)
        return 1
    print(json.dumps({"status": "ok", "db": str(settings.db_path), "data_dir": str(settings.data_dir)}, indent=2))
    return 0


def command_backup(args: argparse.Namespace) -> int:
    _apply_data_dir(args)
    settings = load_settings()
    if not settings.db_path.exists():
        print("database does not exist yet", file=sys.stderr)
        return 2
    dest_dir = settings.data_dir / "backups"
    dest_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = dest_dir / f"leapdrama-{stamp}.sqlite3"
    source = connect(settings)
    target = None
    try:
        target = sqlite3.connect(dest)
        source.backup(target)
    finally:
        if target is not None:
            target.close()
        source.close()
    print(json.dumps({"backup": str(dest)}, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--data-dir", help="Override LEAPDRAMA_DATA_DIR for this command")
    parser = argparse.ArgumentParser(prog="leapdrama", description="LeapDrama demo operator tools")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_selection(command: argparse.ArgumentParser) -> None:
        command.add_argument("path")
        command.add_argument("--json", action="store_true")
        command.add_argument("--report")
        command.add_argument("--series", action="append", default=[])
        command.add_argument("--all-series", action="store_true")
        command.add_argument("--all-episodes", action="store_true")
        command.add_argument("--from-episode", type=int)
        command.add_argument("--to-episode", type=int)
        command.add_argument("--probe", choices=("selected", "all", "none"), default="selected")

    inventory = sub.add_parser("inventory", parents=[common], help="Read series folders and report numbering, gaps, and durations")
    add_selection(inventory)
    inventory.set_defaults(func=command_inventory, in_place=False, strict=False)

    importer = sub.add_parser("import", parents=[common], help="Idempotently copy the default demo subset into the data directory")
    add_selection(importer)
    importer.add_argument("--in-place", action="store_true", help="Reference files under LEAPDRAMA_LIBRARY_ROOTS instead of copying")
    importer.add_argument("--strict", action="store_true", help="Fail if a selected series is missing or the window has numbering gaps")
    importer.set_defaults(func=command_import)

    health = sub.add_parser("health", parents=[common], help="Check the database, or an HTTP health URL")
    health.add_argument("--url")
    health.set_defaults(func=command_health)

    backup = sub.add_parser("backup", parents=[common], help="Write a consistent SQLite backup under the data directory")
    backup.set_defaults(func=command_backup)
    return parser


def run(argv: list[str] | None = None) -> int:
    if sys.version_info < (3, 11):
        print("Python 3.11 or newer is required", file=sys.stderr)
        return 1
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


def main() -> None:
    sys.exit(run())


if __name__ == "__main__":
    main()

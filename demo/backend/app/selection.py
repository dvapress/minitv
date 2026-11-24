from __future__ import annotations

import json
from pathlib import Path

DEFAULT_SELECTION = {
    "version": 1,
    "episode_from": 1,
    "episode_to": 10,
    "include": ["锦鲤娘", "孝子贤孙", "全家听我心声", "爹爹开门"],
    "exclude": [
        {
            "name": "白月光反击说明书",
            "reason": (
                "Source inventory is missing episodes 23 and 44. "
                "Left out of the default demo subset."
            ),
        }
    ],
    "inventory_note": (
        "Reported source inventory: 10 series, 862 mp4 files, about 10.12 GiB. "
        "Default demo subset is four series, episodes 1-10, about 519.1 MiB."
    ),
}


def load_selection(path: Path | None) -> dict:
    if path is None or not path.is_file():
        return json.loads(json.dumps(DEFAULT_SELECTION))
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"selection file is not an object: {path}")
    include = data.get("include")
    if not isinstance(include, list) or not all(isinstance(item, str) and item.strip() for item in include):
        raise SystemExit(f"selection file include list is invalid: {path}")
    try:
        start = int(data.get("episode_from", 1))
        end = int(data.get("episode_to", 10))
    except (TypeError, ValueError) as exc:
        raise SystemExit(f"selection episode window is invalid: {path}") from exc
    if start < 1 or end < start:
        raise SystemExit(f"selection episode window is invalid: {path}")
    exclude = data.get("exclude") or []
    if not isinstance(exclude, list):
        raise SystemExit(f"selection exclude list is invalid: {path}")
    cleaned = []
    for item in exclude:
        if isinstance(item, str):
            cleaned.append({"name": item, "reason": ""})
        elif isinstance(item, dict) and isinstance(item.get("name"), str):
            cleaned.append({"name": item["name"], "reason": str(item.get("reason") or "")})
        else:
            raise SystemExit(f"selection exclude entry is invalid: {path}")
    return {
        "version": data.get("version", 1),
        "episode_from": start,
        "episode_to": end,
        "include": [item.strip() for item in include],
        "exclude": cleaned,
        "inventory_note": str(data.get("inventory_note") or ""),
    }

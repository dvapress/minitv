#!/bin/sh
# Idempotent media import. Arguments are passed to `python -m app.cli import`.
# Example: ./scripts/import-media.sh /path/to/短剧合集2 --json
set -eu
APP_ROOT="$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
cd "$APP_ROOT"

if [ -f .env ]; then
  while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in
      ""|\#*) continue ;;
      [A-Za-z_]*=*)
        key=${line%%=*}
        value=${line#*=}
        export "$key=$value"
        ;;
    esac
  done < .env
fi

export LEAPDRAMA_DATA_DIR="${LEAPDRAMA_DATA_DIR:-$APP_ROOT/data}"
export PYTHONPATH="$APP_ROOT/backend${PYTHONPATH:+:$PYTHONPATH}"
PY="$APP_ROOT/.venv/bin/python"
if [ ! -x "$PY" ]; then
  PY="$(command -v python3)"
fi
exec "$PY" -m app.cli import "$@"

#!/bin/sh
# Store two whole-site passcodes as salted hashes. Does not echo or log them.
# Interactive: ./scripts/set-gate-passcodes.sh
# Piped: the file must contain exactly two lines and should be mode 0600.
# Do not pass the passcodes as arguments, and do not put them in .env or the systemd unit.
set -eu
APP_ROOT="$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
cd "$APP_ROOT"
export LEAPDRAMA_DATA_DIR="${LEAPDRAMA_DATA_DIR:-$APP_ROOT/data}"
export PYTHONPATH="$APP_ROOT/backend${PYTHONPATH:+:$PYTHONPATH}"
PY="$APP_ROOT/.venv/bin/python"
if [ ! -x "$PY" ]; then
  PY="$(command -v python3)"
fi
exec "$PY" -m app.cli gate-set --data-dir "$LEAPDRAMA_DATA_DIR"

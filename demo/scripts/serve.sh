#!/bin/sh
# Start LeapDrama on loopback. Does not print secret values.
set -eu
APP_ROOT="$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
cd "$APP_ROOT"

if [ -f .env ]; then
  while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in
      ""|\#*) continue ;;
    esac
    case "$line" in
      [A-Za-z_]*=*)
        key=${line%%=*}
        value=${line#*=}
        export "$key=$value"
        ;;
    esac
  done < .env
fi

BIND="${LEAPDRAMA_BIND:-127.0.0.1}"
PORT="${LEAPDRAMA_PORT:-18080}"
export LEAPDRAMA_BIND="$BIND"
export LEAPDRAMA_PORT="$PORT"
export LEAPDRAMA_DATA_DIR="${LEAPDRAMA_DATA_DIR:-$APP_ROOT/data}"
export PYTHONPATH="$APP_ROOT/backend${PYTHONPATH:+:$PYTHONPATH}"

case "$PORT" in
  8787|20242)
    echo "Refusing to listen on port $PORT. Those ports belong to other services." >&2
    exit 1
    ;;
esac

case "$BIND" in
  127.0.0.1|localhost|::1) ;;
  *)
    echo "Warning: LEAPDRAMA_BIND is not loopback. The supported deployment listens on 127.0.0.1 only." >&2
    ;;
esac

PY="$APP_ROOT/.venv/bin/python"
if [ ! -x "$PY" ]; then
  echo "Missing $PY. Run scripts/install-user.sh first." >&2
  exit 1
fi

exec "$PY" -m uvicorn app.main:create_app --factory \
  --app-dir "$APP_ROOT/backend" \
  --host "$BIND" \
  --port "$PORT" \
  --workers 1

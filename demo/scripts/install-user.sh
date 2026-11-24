#!/bin/sh
# Install LeapDrama for the current user. Does not use sudo, docker, or system services.
set -eu
APP_ROOT="$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
cd "$APP_ROOT"

if [ "$(id -u)" -eq 0 ]; then
  echo "Refusing to run as root. Run this as the unprivileged app user." >&2
  exit 1
fi

case "$APP_ROOT" in
  "$HOME"/apps/leapdrama-demo) ;;
  *)
    if [ "${LEAPDRAMA_ENFORCE_APPS_PREFIX:-}" = "1" ] || [ "$(id -un)" = "harleyw" ]; then
      echo "Refusing to install from $APP_ROOT" >&2
      echo "Copy this directory to $HOME/apps/leapdrama-demo and run the script there." >&2
      exit 1
    fi
    echo "Note: installing from $APP_ROOT."
    echo "On aiexplorer.asia the runtime directory must be $HOME/apps/leapdrama-demo."
    ;;
esac

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is not on PATH. This script will not install system packages." >&2
  exit 1
fi

if ! python3 -c 'import venv, ensurepip' >/dev/null 2>&1; then
  echo "python3 can run, but venv/ensurepip is unavailable." >&2
  echo "This script does not use sudo. Either ask an admin to install the python3-venv package," >&2
  echo "or install a user-space Python with uv and create .venv yourself:" >&2
  echo "  curl -LsSf https://astral.sh/uv/install.sh | sh" >&2
  echo "  uv venv --python 3.12 .venv && uv pip install -r requirements.txt" >&2
  exit 1
fi

if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
fi
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt

if [ ! -f web/build/index.html ]; then
  if command -v npm >/dev/null 2>&1; then
    (cd web && npm ci && npm run build)
  else
    echo "web/build is missing and npm is not installed." >&2
    echo "The committed bundle should already be in web/build. If you changed the UI, build it where Node is available:" >&2
    echo "  cd web && npm ci && npm run build" >&2
  fi
fi

mkdir -p data "$HOME/.config/systemd/user"
UNIT_SRC="$APP_ROOT/deploy/leapdrama-demo.service"
UNIT_DST="$HOME/.config/systemd/user/leapdrama-demo.service"
sed "s|__APP_ROOT__|$APP_ROOT|g" "$UNIT_SRC" > "$UNIT_DST"

if command -v systemctl >/dev/null 2>&1 && [ -n "${XDG_RUNTIME_DIR:-}" ]; then
  systemctl --user daemon-reload
  systemctl --user enable --now leapdrama-demo.service
  echo "User service leapdrama-demo is enabled."
  echo "Health: curl -fsS http://127.0.0.1:\${LEAPDRAMA_PORT:-18080}/health"
else
  echo "systemd --user is not available in this session (no user bus)." >&2
  echo "The unit file was still written to $UNIT_DST." >&2
  echo "Fallback without systemd, from $APP_ROOT:" >&2
  echo "  mkdir -p data && nohup ./scripts/serve.sh >> data/serve.log 2>&1 & echo \$! > data/serve.pid" >&2
  exit 1
fi

echo "If this user logs out, systemd --user stops unless linger is enabled."
echo "Linger requires a privileged administrator and is NOT changed by this script:"
echo "  loginctl enable-linger $(id -un)"
echo "Do not modify cloudflared-leapai-v2, leapai-portal, port 8787, or port 20242."

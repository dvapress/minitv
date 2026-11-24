# LeapDrama demo

Customer demo for a short-drama site. Chinese is the default language, English is the second. One responsive site covers desktop and mobile browsers. It is not a native app.

Final public name: `https://leapdrama-demo.rei.autos`

This tree is what gets copied to the server:

```text
/home/harleyw/apps/leapdrama-demo
```

That directory does not exist yet. Create it as `harleyw` and do not put this app inside another site's directory.

## What this is, and what the rest of the repo is

The repository is a fork of MiniTV (MIT). MiniTV's own stack is FastAPI plus PostgreSQL, Redis, Bunny, Stripe, and Cloudflare R2, and its local compose file expects Docker. That stack is the wrong shape for this host:

- `harleyw` is not root, cannot use `sudo` without a password, and cannot access `docker.sock`.
- Docker 29 and Compose 2.27 are installed on the machine, and this demo does not use them.
- Do not add `harleyw` to the `docker` group and do not change sudoers for this demo.
- About 19 GiB of disk is free, 7.1 GiB of RAM, 4 CPUs. The default import is about 519 MiB.

LeapDrama therefore runs as a single user process: Python, SQLite, and local video files. Payments are simulated. There is no CDN and no AI moderation. Playback is the real file through an HTML5 player, or the page says the file cannot be played. Empty catalogs stay empty.

`docker-compose.yml` is optional documentation for some other machine. It is not the deployment path on `aiexplorer.asia`.

## Do not touch

- `cloudflared-leapai-v2`
- `leapai-portal`
- port `8787`
- port `20242`

DNS and TLS are a **new** Cloudflare Tunnel owned by the deploy teammate. Its origin is `http://127.0.0.1:18080`. The public hostname is `leapdrama-demo.rei.autos`. This app only listens on loopback.

## Runtime layout

| Path | Purpose |
| --- | --- |
| `~/apps/leapdrama-demo/` | Application root |
| `~/apps/leapdrama-demo/data/leapdrama.sqlite3` | Users, catalog, history, comments, demo bills |
| `~/apps/leapdrama-demo/data/media/` | Copied episode files |
| `~/apps/leapdrama-demo/data/admin.password` | Generated admin password, mode `0600`, never printed |
| `~/apps/leapdrama-demo/data/secret.key` | Generated signing key, mode `0600`, never printed |
| `~/apps/leapdrama-demo/.env` | Optional overrides. Not in git |

SQLite is the database. PostgreSQL and Redis are not required. The file survives process restarts. Do not delete `data/` during an update.

## Requirements on the server

- Ubuntu 24.04 already has Python 3.12. The process needs Python 3.11+.
- `python3-venv` is part of a normal Ubuntu image but is sometimes missing. This installer does not use sudo. If `python3 -m venv` fails, either an admin installs the `python3-venv` package, or `harleyw` installs [uv](https://docs.astral.sh/uv/) into the home directory and creates `.venv` with it. The installer prints that choice and stops.
- `ffmpeg` / `ffprobe` are optional. With them, import records duration and extracts a cover. Without them, import still copies the files, marks duration as unknown, and leaves the cover empty. It never rewrites the source file. A static ffmpeg binary in the home directory is enough; do not apt-install it as root for this demo.
- Node is not required to start. `web/build` is the already-built site. Rebuild only if the UI changes.

## Install and start

From a checkout of this repository, as `harleyw`:

```bash
mkdir -p "$HOME/apps"
rsync -a --exclude .venv --exclude data --exclude .env \
  /path/to/minitv/demo/ "$HOME/apps/leapdrama-demo/"
cd "$HOME/apps/leapdrama-demo"
cp .env.example .env
# Leave LEAPDRAMA_ADMIN_PASSWORD and LEAPDRAMA_SECRET_KEY empty
# unless an operator password was provided out of band.
chmod +x scripts/*.sh
./scripts/install-user.sh
```

The installer creates `.venv`, installs Python packages, writes the user unit, and runs:

```bash
systemctl --user enable --now leapdrama-demo.service
```

Health:

```bash
curl -fsS http://127.0.0.1:18080/health
```

A healthy body has `"status":"ok"`, `"payments":"simulated"`, `"media":"local"`, `"ai":false`.

If the user systemd bus is missing, the script exits after writing the unit and prints a fallback that does not touch other services:

```bash
cd "$HOME/apps/leapdrama-demo"
mkdir -p data
nohup ./scripts/serve.sh >> data/serve.log 2>&1 & echo $! > data/serve.pid
```

Stop that fallback with `kill "$(cat data/serve.pid)"`.

### Logout and linger

`systemd --user` stops when `harleyw` has no lingering session. Enabling linger needs a privileged administrator:

```bash
loginctl enable-linger harleyw
```

This repository does not run that command. Until linger is enabled, keep the user session open or use the `nohup` fallback.

### Useful unit commands

```bash
systemctl --user status leapdrama-demo.service
systemctl --user restart leapdrama-demo.service
journalctl --user -u leapdrama-demo.service -n 100 --no-pager
```

`scripts/serve.sh` refuses ports `8787` and `20242`. The default bind is `127.0.0.1` and the default port is `18080`.

## Configuration

Copy `.env.example` to `.env`. Secrets stay empty in git. On first start, if `LEAPDRAMA_ADMIN_PASSWORD` is empty, the process writes `data/admin.password` and logs only the path. Read it on the server. Do not paste it into tickets, screenshots, or the pull request.

Weak values such as `password` or `admin` are rejected. There is no built-in shared password.

| Variable | Default |
| --- | --- |
| `LEAPDRAMA_BIND` | `127.0.0.1` |
| `LEAPDRAMA_PORT` | `18080` |
| `LEAPDRAMA_DATA_DIR` | `<app>/data` |
| `LEAPDRAMA_PUBLIC_BASE_URL` | `https://leapdrama-demo.rei.autos` |
| `LEAPDRAMA_ADMIN_EMAIL` | `admin@leapdrama.demo` |
| `LEAPDRAMA_COOKIE_SECURE` | `auto` (Secure when `X-Forwarded-Proto` is `https`) |
| `LEAPDRAMA_MAX_EPISODE_SECONDS` | `180` (flag only, never trim) |
| `LEAPDRAMA_MAX_UPLOAD_BYTES` | `536870912` |

The tunnel should send `X-Forwarded-Proto: https` so the session cookie is marked Secure in production. Local `curl` to port 18080 stays on HTTP.

## Media import

Source on the operator Mac, not on this server:

```text
/Users/zhe/ws/local/lynn/aio-drama/短剧合集2
```

Reported inventory: 10 series, 862 mp4 files, about 10.12 GiB. The default subset is four series, episodes 1–10, about 519.1 MiB:

- 锦鲤娘
- 孝子贤孙
- 全家听我心声
- 爹爹开门

`白月光反击说明书` is excluded by default because episodes 23 and 44 are missing. It is not renumbered. Import it only with an explicit `--series` flag; the report lists the gaps.

Expected layout:

```text
短剧合集2/
  锦鲤娘/
    1.mp4
    2.mp4
    ...
    cover.jpg          # optional
    meta.json          # optional: title, title_en, synopsis, genre, genre_en, region
```

Episode numbers come from the filename (`1`, `01`, `第2集`, `EP03`, or the last non-year number). Files are never sorted lexically and then renumbered. A gap stays a gap. Extra renditions (`1.720p.mp4`) and sidecars (`1.vtt`, `1.srt`) are picked up only when those files exist. Durations over 180 seconds are flagged `long` and the original bytes are not cut.

Put the transferred directory somewhere `harleyw` can read, then:

```bash
cd "$HOME/apps/leapdrama-demo"
./scripts/import-media.sh /path/to/短剧合集2 --json
```

The same command is safe to run again. Unchanged files are reported as `unchanged` and are not copied again. The process copies into `data/media` and does not modify the source directory. If free disk would drop below a 256 MiB margin, the copy stops.

Other useful commands, from the app root with `PYTHONPATH=backend` (the shell wrappers set this):

```bash
.venv/bin/python -m app.cli inventory /path/to/短剧合集2 --json
.venv/bin/python -m app.cli import /path/to/短剧合集2 --strict --json
.venv/bin/python -m app.cli import /path/to/短剧合集2 --series 白月光反击说明书 --all-episodes --json
.venv/bin/python -m app.cli backup
.venv/bin/python -m app.cli health --url http://127.0.0.1:18080/health
```

Exit codes for import: `0` finished (including an empty folder), `2` the path does not exist, `3` a file failed, `4` `--strict` and a selected series is missing or the selected window has a numbering gap. A missing directory does not create fake videos.

Before the first real import, snapshot the database:

```bash
.venv/bin/python -m app.cli backup
```

Creator upload in the browser is the same storage path. It requires the admin or creator role. Anonymous upload returns 401.

## Update and rollback

```bash
systemctl --user stop leapdrama-demo.service
.venv/bin/python -m app.cli backup
rsync -a --exclude .venv --exclude data --exclude .env /path/to/new/demo/ "$HOME/apps/leapdrama-demo/"
.venv/bin/python -m pip install -r requirements.txt
systemctl --user start leapdrama-demo.service
curl -fsS http://127.0.0.1:18080/health
```

To reverse a bad code update, rsync the previous tree the same way and start again. Do not delete `data/`. SQLite schema changes in this demo are additive (`CREATE TABLE IF NOT EXISTS`). Restoring an older database file is a file copy of `data/backups/leapdrama-*.sqlite3` over `data/leapdrama.sqlite3` while the service is stopped. Stop the service first so the file is consistent.

## Product behavior

- Episodes 1 and 2 of each series play without an account. Later episodes need a demo membership.
- Activating membership writes a bill with a listed price of USD 9.90 and a charged amount of USD 0.00, status `simulated`. Nothing redirects to a payment provider.
- History, favorites, comments, and likes are stored for signed-in users and remain after a restart.
- Play counts increase on a real play start, debounced per viewer for 60 seconds.
- Recommendations prefer another series with the same genre, then the rest of the catalog. If no genre was imported, the row stays `未分类` instead of inventing one.
- The player is HTML5. Speed is a playback-rate control. A quality menu appears only when more than one real rendition file exists. A subtitle control appears only when a subtitle file exists.
- The next episode can autoplay after the current one ends. The player uses `preload="metadata"` and does not download the next file early.
- Comments are filtered locally (length, links, flooding, a small safety list). That is not an AI review.
- There is no download button and no service worker. Offline caching is not implemented.
- Light and dark themes, Chinese and English, and a region preference are stored in the browser and, when signed in, on the user row. Region does not geo-block and is not a CDN.

## Checks run in development

```bash
cd demo
PYTHONPATH="backend" python3 -m pytest -q
cd web && npm ci && npm run build
```

Start locally, still on loopback:

```bash
cd demo
export LEAPDRAMA_DATA_DIR="$PWD/data" LEAPDRAMA_BIND=127.0.0.1 LEAPDRAMA_PORT=18080
export PYTHONPATH="$PWD/backend"
.venv/bin/python -m uvicorn app.main:create_app --factory --app-dir backend --host 127.0.0.1 --port 18080
```

## Requirements matrix

| Requirement | Status |
| --- | --- |
| PC and responsive mobile web, not native apps | Implemented as one site |
| Chinese default, English toggle, extensible dictionaries | Implemented in `web/src/i18n.ts` |
| Browse, search, play, demo membership | Implemented |
| Protected creator upload and real play counts | Implemented. Anonymous upload is rejected |
| Header logo, language, region, search, login, member | Implemented |
| Hero and genre rows | Implemented. Genre stays unclassified until metadata exists |
| Privacy, terms, copyright, region footer | Implemented as labeled demo placeholders |
| Desktop watch: video left, episodes and recommendations right | Implemented. Stacks on a narrow screen |
| HTML5 playback, speed, real qualities only, real subtitles only | Implemented |
| Careful autoplay and preload | Next episode starts after the current one ends. No early full-file prefetch |
| First two episodes free, later ones behind demo membership | Implemented |
| Demo billing with no real charge | Implemented. Charged amount is always 0 |
| History, favorites, member, billing, region, theme | Implemented for signed-in users |
| Likes, share, comments with basic moderation | Implemented. Share copies or uses the system share sheet. No fake share count |
| Persistent catalog and accounts across restart | SQLite in `data/` |
| Idempotent import, numeric order, long-file flag, no trim | Implemented |
| Default 4 series, episodes 1–10; skip 白月光反击说明书 | Implemented in `import-selection.json` |
| Health endpoint and env template | `GET /health`, `.env.example` |
| Reversible update | Backup command plus rsync of the previous tree. Data directory is kept |
| Native user service on 127.0.0.1:18080 | `systemd --user` unit. Docker is not required |
| Real payment, CDN, AI, offline download | Not implemented, and the UI says so |
| DNS, TLS, Cloudflare Tunnel, copying media from the Mac | Not done here. A new tunnel should target 127.0.0.1:18080 |
| This process deployed onto aiexplorer.asia | Not done in this change. No SSH credentials were available |

## Limitations

- One admin account is created at startup. There is no full staff RBAC like the upstream admin.
- No email delivery, so registration does not send a code.
- No transcoding ladder. A second quality appears only when a second file was imported.
- `mov` and `mkv` are remuxed with stream copy when ffmpeg is present. The source file is not replaced. If remux fails, the episode is stored as not playable in the browser.
- Comments are a keyword filter.
- Recommendations are genre and play-count rules, not a model.
- Legal pages are placeholders.
- `systemd --user` without linger stops at logout. Linger is an admin action and is documented, not performed.
- If `python3-venv` is missing, the installer stops instead of using sudo.

# Climate Control

This is a component of [Kita](#about-kita). It runs two jobs under one supervisor.

- **Thermostat.** Connects to the Sensi WebSocket and holds one thermostat inside a temperature profile.
- **Weather station.** Accepts Ambient Weather uploads, backfills station history, and serves the dashboard.

---

## What is running

`run.py` is the supervisor. It only runs when its parent process is `uv`. It starts three processes in the repo directory and stays up:

| Child | Command | Job |
|---|---|---|
| Thermostat | `control.py` | Sensi routine named in `src/config/app_config.json` |
| Weather server | `python -m src.weather.server` | HTTP on `0.0.0.0:8099` |
| History | `python -m src.weather.history` | Repeating Ambient history backfill |

`device_id`, `routine`, and the Sensi connection (`oauth_url`, `ws_url`, `client_id`) come from `src/config/app_config.json`. The supervisor restarts thermostat control when any of those change. Band edits do not restart it; the routine reloads its YAML on each control cycle. The supervisor also restarts the thermostat and the weather server when those processes exit. History retries failed Ambient calls inside its own loop and re-reads `weather_history_interval` after each pass. If the history process exits, it stays stopped until `run.py` is started again.

Stopping the supervisor with SIGINT (Ctrl-C) stops the children. The systemd unit uses the same signal.

---

## Getting started

```bash
uv venv
uv pip install -r requirements.txt
cp .env.exemple .env
```

Set these in `.env`:

| Variable | Role |
|---|---|
| `REFRESH_TOKEN` | Sensi refresh token. Read from `.env` only. |
| `SENSI_FLEET_CLIENT_SECRET` | Sensi fleet client secret. Read from `.env` only. |
| `AMBIENT_API_KEY` | Ambient Weather API key |
| `AMBIENT_APPLICATION_KEY` | Ambient Weather application key |
| `AMBIENT_MAC` | Optional. Selects one station when the account has several |

Foreground:

```bash
uv run --offline --no-project run.py
```

`--offline` keeps `uv` off the network. `--no-project` uses the existing `.venv` and does not resolve or download packages. `run.py` exits unless `uv` is its parent.

- Weather: `http://<host>:8099/dashboard`
- Service logs: `http://<host>:8099/services`

The cog in the header opens settings. **General** edits the history interval and the Sensi OAuth URL, WebSocket URL, and client id. **Routines** edits the device id, the active routine, and each profile's bands.

The weather server listens on every interface, port `8099` (`src/config/app_config.json`).

---

## Service

This machine runs `climate-control.service`. The unit starts `/home/vitor-de-souza/.local/bin/uv run --offline --no-project run.py`. The absolute path is required because systemd's default `PATH` does not include `~/.local/bin`. The device id and routine are `device_id` and `routine` in `src/config/app_config.json`. The refresh token is read from `.env` (`REFRESH_TOKEN`). The working directory is the repo, so `.env`, `data/`, and the config files resolve there. The unit does not use `EnvironmentFile`: systemd would keep quote characters, and `envfile.py` is the parser the app already uses.

The unit waits for `network-online.target`, restarts on failure after 5 seconds, sets `PYTHONUNBUFFERED=1`, and stops with `SIGINT` (`TimeoutStopSec=15`) so the supervisor can shut the children down.

Install on this machine, or edit `User`, `Group`, `WorkingDirectory`, and `ExecStart` first:

```bash
sudo cp climate-control.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now climate-control.service
```

```bash
systemctl status climate-control.service
journalctl -u climate-control.service -f
```

---

## Profiles

The active profile is `routine` in `src/config/app_config.json`. `control.py` loads `src/config/<routine>_config.yml` and the matching routine class. Bands are Fahrenheit, keyed by hour. The settings cog can switch the active routine, edit the device id, and save bands.

| Profile | What it does |
|---|---|
| `keep_temperature_in_range` | Daily bands. Heat or off, with a 1° offset. |
| `keep_temperature_in_range_spring` | Same control, spring bands. |
| `keep_house_from_freezing` | Freeze-protection bands. |
| `always_heated` | Heat, with fan cycling from the config. |
| `out_and_warm` | Away bands. |

---

## Dashboard and logs

`/dashboard` charts station weather. **Historical** reads `data/historical` (Ambient API backfill). **Station** reads `data/station` (live uploads). The default window is the last 24 hours. The page can show charts or a table, average and median lines, and it refreshes on a timer (60 seconds until changed). A window longer than 1500 points is drawn with an even stride; a shorter window returns every stored reading.

The header cog opens one settings dialog. **General** sets `weather_history_interval` (seconds, whole number, 0 or greater) and the Sensi OAuth URL, WebSocket URL, and client id. The history process uses the saved interval on its next pass. The client secret is `SENSI_FLEET_CLIENT_SECRET` in `.env` and is not written to the config file. **Routines** lists each profile, its YAML path, and its bands. Saving bands writes that routine's YAML only. Activating a routine, saving the device id, or saving the Sensi connection writes `src/config/app_config.json`. The supervisor restarts control when the device id, routine, or Sensi connection changes.

`/services` shows the tail of each logger under `data/logs`, 200 lines, polled every 2 seconds. When stderr is a terminal, the bracketed logger name is colored. Log files are plain text, one file per logger, trimmed to 256 KiB. Weather and Services share the header, including the settings cog.

Either child can run on its own:

```bash
uv run --offline --no-project python -m src.weather.server [port] [station-dir]
uv run --offline --no-project python -m src.weather.history [historical-dir]
uv run --offline --no-project python -m src.weather.recalc [station-dir]
```

`recalc` rewrites station buckets in place with dew point, feels like, and last rain. The default directory is `data/station`.

---

## Weather data

Ambient Weather station uploads are `GET /data/report?...`. `PASSKEY` is removed before the reading is stored. Dew point, feels like, and last rain are computed, then the reading is appended to a UTC 12-hour JSONL bucket, `YYYY-MM-DD_00.jsonl` or `YYYY-MM-DD_12.jsonl`, and `_latest.json` is replaced.

The backfill writes the same bucket layout under `data/historical`, plus a `checkpoint` file (Unix milliseconds of the newest saved row). Collector settings that are safe to commit — API base URL, 6-hour windows, lookback, retry, port, directories, device id, routine, and history interval — live in `src/config/app_config.json`. Keys stay in `.env`.

| Method and path | Returns |
|---|---|
| `GET /data/report` | Stores one station upload. `{"ok": true}` |
| `GET /weather/latest` | Latest station reading |
| `GET /weather?from=&to=&fields=` | Station readings in a UTC range |
| `GET /dashboard/series?source=historical\|station&from=&to=` | Series used by the dashboard |
| `GET /services/logs` | `{ "loggers": [{ "name", "lines" }] }` |
| `GET /config/history-interval` | `{ "weather_history_interval": 900 }` |
| `POST /config/history-interval` | Same shape. Anything other than a non-negative integer is `400` |
| `GET /config/sensi` | `{ "oauth_url", "ws_url", "client_id" }` |
| `POST /config/sensi` | Same shape. A client secret in the body is `400` |
| `GET /routines` | Catalog plus parsed YAML, used by the Routines tab |
| `POST /routines/active` | `{ "routine": "<name>" }` writes the active routine |
| `POST /routines/device` | `{ "device_id": "<id>" }` writes the device id |
| `PUT /routines/<name>` | Replaces that routine's hour bands and fan fields |

---

## Checks

These exercise the supervisor, the collectors, and logging without calling Sensi or Ambient:

```bash
uv run --offline --no-project run.py --self-check
uv run --offline --no-project control.py --self-check
uv run --offline --no-project python -m src.weather.server --self-check
uv run --offline --no-project python -m src.weather.history --self-check
uv run --offline --no-project python -m src.weather.recalc --self-check
uv run --offline --no-project python -m src.utils.log
```

---

## About Kita

`Kita` is a personal assistant developed by [Vitor de Souza](https://www.linkedin.com/in/vitor-de-souza-software) ([ClownChu](https://github.com/ClownChu)). Currently coded in [.NET](https://dotnet.microsoft.com), [Go](https://golang.org), and [Node.js](https://nodejs.org). This personal assistant helps with daily tasks, such as: controlling computers, lights, network, schedules, repetitive tasks, among other features.

---

## License

[Climate Control source code](https://github.com/ClownChu/climate-control) is made available under the [GNU Affero General Public License v3.0](https://www.gnu.org/licenses/agpl-3.0.en.html) license. ([Read more](https://choosealicense.com/licenses/agpl-3.0/))

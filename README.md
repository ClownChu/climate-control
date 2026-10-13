# Climate Control

This is a component of [Kita](#about-kita). It runs two jobs under one supervisor.

- **Thermostat.** Connects to the Sensi WebSocket and holds one thermostat inside a temperature profile.
- **Weather station.** Accepts Ambient Weather uploads, backfills station history, and serves the dashboard.

---

## What is running

`run.py` is the supervisor. It starts three processes in the repo directory and stays up:

| Child | Command | Job |
|---|---|---|
| Thermostat | `control.py <profile> <device-id> [refresh-token]` | Sensi routine for that profile and device |
| Weather server | `python -m src.weather.server` | HTTP on `0.0.0.0:8099` |
| History | `python -m src.weather.history` | Repeating Ambient history backfill |

The supervisor restarts the thermostat and the weather server when those processes exit. History retries failed Ambient calls inside its own loop. If the history process exits, it stays stopped until `run.py` is started again.

Stopping the supervisor with SIGINT (Ctrl-C) stops the children. The systemd unit uses the same signal.

---

## Getting started

```bash
python3 -m venv ./.venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.exemple .env
```

Set these in `.env`:

| Variable | Role |
|---|---|
| `REFRESH_TOKEN` | Sensi refresh token. Wins over the optional third argument. |
| `AMBIENT_API_KEY` | Ambient Weather API key |
| `AMBIENT_APPLICATION_KEY` | Ambient Weather application key |
| `AMBIENT_MAC` | Optional. Selects one station when the account has several |
| `WEATHER_HISTORY_INTERVAL` | Seconds between backfill passes. `900` when unset |

Foreground:

```bash
python3 ./run.py <profile> <device-id> [refresh-token]
```

- Weather: `http://<host>:8099/dashboard`
- Service logs: `http://<host>:8099/services`

The weather server listens on every interface, port `8099` (`src/config/weather_config.yml`).

---

## Service

This machine runs `climate-control.service`. The unit starts the repo virtualenv as:

```text
run.py keep_temperature_in_range <device-id>
```

The device id is the one in `ExecStart`. The refresh token is read from `.env` (`REFRESH_TOKEN`), because the unit passes no third argument. The working directory is the repo, so `.env`, `data/`, and the config files resolve there.

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

The profile argument is the config stem. `run.py keep_temperature_in_range` loads `src/config/keep_temperature_in_range_config.yml` and `KeepTemperatureInRangeRoutine`. Bands are Fahrenheit, keyed by hour.

| Profile | What it does |
|---|---|
| `keep_temperature_in_range` | Daily bands. Heat or off, with a 1° offset. This is the service profile. |
| `keep_temperature_in_range_spring` | Same control, spring bands. |
| `keep_house_from_freezing` | Freeze-protection bands. |
| `always_heated` | Heat, with fan cycling from the config. |
| `out_and_warm` | Away bands. The file on disk is `src/config/out_and_warm.yml`. Rename it to `out_and_warm_config.yml` before using that profile. |

---

## Dashboard and logs

`/dashboard` charts station weather. **Historical** reads `data/historical` (Ambient API backfill). **Station** reads `data/station` (live uploads). The default window is the last 24 hours. The page can show charts or a table, average and median lines, and it refreshes on a timer (60 seconds until changed). A window longer than 1500 points is drawn with an even stride; a shorter window returns every stored reading.

`/services` shows the tail of each logger under `data/logs`, 200 lines, polled every 2 seconds. When stderr is a terminal, the bracketed logger name is colored. Log files are plain text, one file per logger, trimmed to 256 KiB.

Either child can run on its own:

```bash
python3 -m src.weather.server [port] [station-dir]
python3 -m src.weather.history [historical-dir]
```

---

## Weather data

Ambient Weather station uploads are `GET /data/report?...`. `PASSKEY` is removed before the reading is stored. Each reading is appended to a UTC 12-hour JSONL bucket, `YYYY-MM-DD_00.jsonl` or `YYYY-MM-DD_12.jsonl`, and `_latest.json` is replaced.

The backfill writes the same bucket layout under `data/historical`, plus a `checkpoint` file (Unix milliseconds of the newest saved row). Collector settings that are safe to commit — API base URL, 6-hour windows, lookback, retry, port, directories — live in `src/config/weather_config.yml`. Keys stay in `.env`.

| Method and path | Returns |
|---|---|
| `GET /data/report` | Stores one station upload. `{"ok": true}` |
| `GET /weather/latest` | Latest station reading |
| `GET /weather?from=&to=&fields=` | Station readings in a UTC range |
| `GET /dashboard/series?source=historical\|station&from=&to=` | Series used by the dashboard |
| `GET /services/logs` | `{ "loggers": [{ "name", "lines" }] }` |

---

## Checks

These exercise the supervisor, the collectors, and logging without calling Sensi or Ambient:

```bash
python3 run.py --self-check
python3 control.py --self-check
python3 -m src.weather.server --self-check
python3 -m src.weather.history --self-check
python3 -m src.utils.log
```

---

## About Kita

`Kita` is a personal assistant developed by [Vitor de Souza](https://www.linkedin.com/in/vitor-de-souza-software) ([ClownChu](https://github.com/ClownChu)). Currently coded in [.NET](https://dotnet.microsoft.com), [Go](https://golang.org), and [Node.js](https://nodejs.org). This personal assistant helps with daily tasks, such as: controlling computers, lights, network, schedules, repetitive tasks, among other features.

---

## License

[Climate Control source code](https://github.com/ClownChu/climate-control) is made available under the [GNU Affero General Public License v3.0](https://www.gnu.org/licenses/agpl-3.0.en.html) license. ([Read more](https://choosealicense.com/licenses/agpl-3.0/))

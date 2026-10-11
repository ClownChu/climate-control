The data that actually gets saved comes from the C# collector in `Weather/WeatherPredictionCollector/Program.cs`, using the client in `Weather/AmbientWeatherApi`. The Node scripts only print readings. Nothing below is about prediction.

The station this code was written for is an Ambient Weather **WS-2000**. Credentials are hardcoded in `Program.cs` and in `Weather/NodeSample`. Do not copy them into the new project; put them in configuration and rotate them, since they are already in source.

Legacy Project Location: `docs/knowledge/Weather`

## What gets called

Base URL: `https://api.ambientweather.net`.

Every request is a GET with both keys in the query string:

```text
?applicationKey={applicationKey}&apiKey={apiKey}
```

Extra parameters are appended as raw `&key=value` pairs. Values are not URL-encoded.

| Call | Path | Used for |
|---|---|---|
| List stations | `/v1/devices` | MAC address and station name |
| History | `/v1/devices/{macAddress}` | The rows that are saved |

History parameters:

- `endDate` — Unix time in **milliseconds**. Omitted only when the caller passes null. The collector always sends it. If the value is in the future, the client clamps it to `DateTime.UtcNow` before sending.
- `limit` — defaults to **288**. The collector never overrides that.

After every successful call the client sleeps **1 second**. That matches Ambient’s one-request-per-second limit. A failed call does not sleep; the collector retries immediately.

`HttpGetCall` uses `HttpClient.GetStringAsync`, then `JsonConvert.DeserializeObject`. `Converter.cs` (ISO dates, `AssumeUniversal`) is never passed into that deserializer, so it has no effect on parsing.

## Collection loop

`Program.Main` is the whole pipeline. `Program2` (UDP port 45000) is commented out and only prints datagrams; it is not part of this API path.

1. Build `AmbientWeatherClient` with the API key and application key.
2. Call `GetUserDevices()` until the array is non-empty. Any exception is swallowed and the call is retried forever.
3. For each device, derive a file stem from `info.name` by replacing spaces with underscores. No other characters are sanitized.

Per device, the collector keeps four Windows paths:

| File | Path |
|---|---|
| Log | `C:\TopanyControl\Weather\Logs\weather_{name}.log` |
| Data | `C:\TopanyControl\Weather\Data\Raw\weather_{name}.csv` |
| Column list | `C:\TopanyControl\Weather\Data\Raw\weather_{name}_columns.csv` |
| Checkpoint | `C:\TopanyControl\Weather\Data\Raw\weather_{name}.latestDate` |

The checkpoint file is a single integer: the `dateutc` milliseconds of the newest row already saved.

If the checkpoint file is missing, the cursor starts at **UTC now minus 365 days**. If it exists, both the cursor and the “already saved” watermark are that integer.

The history walk is a `while (true)` loop:

1. Request `GetDeviceData(mac, endDate)` and retry forever on any exception.
2. On success, overwrite the columns file with the C# property names of `DeviceData`, comma-separated.
3. If the batch is non-empty:
   - Reverse it. The API returns newest first; after the reverse the array is oldest first.
   - Drop any row whose `dateutc` is less than or equal to the watermark.
   - Append the remaining rows to the CSV.
   - Set the watermark to `dateutc` of the **newest row in the API batch**, including rows that were skipped as duplicates.
4. If that newest timestamp is within 5 minutes of the `endDate` you just requested, move the cursor to that timestamp. If the newest row is older than `endDate` minus 5 minutes, leave the cursor on the requested `endDate`. That is what keeps an empty window from pulling the cursor backward and looping forever.
5. Write the watermark to the checkpoint file.
6. Stop if this iteration was already marked final. Otherwise set the next `endDate` to cursor plus **6 hours**. If that next `endDate` is within 5 minutes of UTC now, or past it, do one last request and then stop.

Resuming is overlap-then-step. The first request ends at the last saved timestamp, so every returned row is skipped. The next request ends 6 hours later and picks up new rows.

A 6-hour window stays under the 288-row cap if the station reports about every 5 minutes (about 72 rows). If it reports faster than roughly every 75 seconds, each call returns only the newest 288 rows at or before `endDate`, and older rows in that window are never requested.

## How a reading is parsed

The history JSON array deserializes into `DeviceData`. Missing JSON fields become the CLR default: `0` for numbers, `false` for relays, `null` for battery strings, and `default(DateTimeOffset)` for dates. There is no “field was absent” flag, so a real zero and a missing sensor look the same.

`dateutc` is a `long`, milliseconds since 1970-01-01 UTC, rounded down to the minute by Ambient’s server. `date` and `lastRain` are `DateTimeOffset`.

The CSV does not use the JSON names. `ToDictionary()` reflects the C# property names, in declaration order, and `String.Join(",", values)` writes them. Nothing is quoted. Dates use `DateTimeOffset.ToString()` in the current culture. Booleans become `True`/`False`. Doubles use the current culture too, so a comma decimal separator would break the CSV.

These are the fields the WS-2000 actually returned. JSON name, then the CSV column name:

| JSON field | CSV column | Meaning |
|---|---|---|
| `dateutc` | `Dateutc` | Observation time, Unix milliseconds |
| `date` | `Date` | Same instant as a date |
| `tempf` | `Tempf` | Outdoor temperature, °F |
| `tempinf` | `Tempinf` | Indoor temperature, °F |
| `humidity` | `Humidity` | Outdoor humidity, % |
| `humidityin` | `Humidityin` | Indoor humidity, % |
| `feelsLike` | `FeelsLike` | Heat index or wind chill, computed by Ambient, °F |
| `dewPoint` | `DewPoint` | Computed by Ambient, °F |
| `windspeedmph` | `Windspeedmph` | Wind speed, mph |
| `winddir` | `Winddir` | Wind direction, degrees |
| `windgustmph` | `Windgustmph` | Gust, mph |
| `maxdailygust` | `Maxdailygust` | Max gust for the day, mph |
| `hourlyrainin` | `Hourlyrainin` | Rain rate, in/hr |
| `dailyrainin` | `Dailyrainin` | Rain since local midnight, in |
| `weeklyrainin` | `Weeklyrainin` | Weekly rain, in |
| `monthlyrainin` | `Monthlyrainin` | Monthly rain, in |
| `yearlyrainin` | `Yearlyrainin` | Yearly rain, in |
| `eventrainin` | `Eventrainin` | Current rain event, in |
| `lastRain` | `LastRain` | Last time `hourlyrainin` was greater than 0 |
| `baromrelin` | `Baromrelin` | Relative pressure, inHg |
| `baromabsin` | `Baromabsin` | Absolute pressure, inHg |
| `uv` | `Uv` | UV index |
| `solarradiation` | `Solarradiation` | Solar radiation, W/m² |

Everything after `solarradiation` in `DeviceData` was copied from the Ambient device-data spec and was **not** returned by this WS-2000. Those columns are still written, as zeros, nulls, or `false`. That includes extra temp/humidity channels 1–10, wind averages, battery fields, and relays.

Two JSON names do not match the public spec, and both are what this code deserializes:

- CO₂ is mapped from `"c02"` (a zero), not `"co2"`. The Node sample reads `co2`.
- Lifetime rain is mapped from `"Totalrainin"` with a capital T. The Node sample reads `totalrainin`.

`GetUserDevices()` also deserializes a smaller `lastData` object on each device. The collector ignores it and only uses `macAddress` and `info.name`.

The header row is written only when the CSV does not exist yet and the current batch is about to write its first kept row. Later runs only append. The columns file is rewritten on every successful fetch and is the same property list.

The log file gets the same lines that are printed to the console: start time, each window in EST and UTC, how many API rows came back, how many CSV lines were appended, and a finished line. “EST” in the log is `ToLocalTime()` after looking up `"Eastern Standard Time"`; that timezone object is not used for the conversion. Appending a header makes `CsvRows.Count` include the header, so the log’s “rows appended” count is one higher than the number of observations on the first write.

## The Node samples

`Weather/NodeSample` uses npm package `ambient-weather-api` 0.0.6. Neither script writes a file.

`display-recent-data.js` lists devices, requests `deviceData(mac, { limit: 1 })`, and prints one reading with units. It is the field catalog, including sensors this WS-2000 does not have (`soiltemp1`, `pm25`, indoor feels-like, and so on).

`realtime.js` connects to Ambient’s realtime socket, subscribes with the API key, and prints outdoor temperature as events arrive. Those events are not the historical rows in the CSV.

## Porting this without the quirks

Preserve the behavior that makes the archive continuous:

- Page with `endDate` in Unix milliseconds and `limit=288`.
- Walk forward in 6-hour steps from the checkpoint, or from one year ago if there is no checkpoint.
- Treat the API order as newest first.
- Deduplicate on `dateutc`.
- Keep a watermark file so a rerun does not duplicate rows.
- Wait at least one second between successful requests.
- Store the WS-2000 fields listed above. Store `dateutc` as the canonical timestamp.

These are accidents of this project, not API requirements:

- CSV columns are C# property names, with no quoting and culture-dependent numbers and dates.
- Absent sensors are stored as zero.
- The checkpoint can advance to a row that was not written, because the watermark is the newest row in the batch, not the newest row appended.
- Failures retry immediately with an empty `catch`.
- The first line of a new CSV may be a header, so consumers must skip a non-numeric first row.
- Paths and the Eastern timezone name are Windows-specific.
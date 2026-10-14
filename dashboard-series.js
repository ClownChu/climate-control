export const CHARTS = [
  {title: "Outdoor temperature", icon: "ph-thermometer", unit: "\u00b0F", digits: 1, toggle: "outdoor", series: [
    {key: "tempf", label: "Outdoor", mode: "actual", color: "#f97316", average: "#aff916", median: "#f916c2", card: {group: "outdoor", label: "Temperature", icon: "ph-thermometer", color: "text-orange-500"}},
    {key: "feelsLike", label: "Outdoor feels like", mode: "feels", color: "#fb7185", average: "#881337", median: "#fda4af", digits: 2, card: {group: "outdoor", label: "Feels like", icon: "ph-thermometer-hot", color: "text-rose-500"}}
  ]},
  {title: "Indoor temperature", icon: "ph-house", unit: "\u00b0F", digits: 1, toggle: "indoor", series: [
    {key: "tempinf", label: "Indoor", mode: "actual", color: "#3b82f6", average: "#9f3bf6", median: "#3bf690", card: {group: "indoor", label: "Temperature", icon: "ph-house", color: "text-blue-500"}},
    {key: "feelsLikein", label: "Indoor feels like", mode: "feels", color: "#818cf8", average: "#312e81", median: "#c7d2fe", card: {group: "indoor", label: "Feels like", icon: "ph-person", color: "text-indigo-500"}}
  ]},
  {title: "Dew point", icon: "ph-drop", unit: "\u00b0F", digits: 1, series: [
    {key: "dewPoint", label: "Outdoor", color: "#06b6d4", average: "#155e75", median: "#67e8f9", digits: 2, card: {group: "outdoor", label: "Dew point", icon: "ph-drop", color: "text-cyan-600"}},
    {key: "dewPointin", label: "Indoor", color: "#2dd4bf", average: "#115e59", median: "#99f6e4", card: {group: "indoor", label: "Dew point", icon: "ph-snowflake", color: "text-teal-500"}}
  ]},
  {title: "Humidity", icon: "ph-drop", unit: "%", digits: 0, series: [
    {key: "humidity", label: "Outdoor", color: "#14b8a6", average: "#1434b8", median: "#41b814", card: {group: "outdoor", label: "Humidity", icon: "ph-waves", color: "text-teal-600"}},
    {key: "humidityin", label: "Indoor", color: "#8b5cf6", average: "#f65cd4", median: "#5ce1f6", card: {group: "indoor", label: "Humidity", icon: "ph-drop-half", color: "text-violet-500"}}
  ]},
  {title: "Wind", icon: "ph-wind", unit: "mph", digits: 1, series: [
    {key: "windspeedmph", label: "Speed", color: "#0ea5e9", average: "#400ee9", median: "#0ee92d", card: {group: "atmosphere", present: "line", label: "Wind speed", icon: "ph-wind", color: "text-sky-500"}},
    {key: "windgustmph", label: "Gust", color: "#f59e0b", average: "#76f50b", median: "#f50b89"},
    {key: "maxdailygust", label: "Max gust", color: "#ef4444", average: "#7f1d1d", median: "#fca5a5", card: {group: "atmosphere", present: "line", label: "Max gust", icon: "ph-hurricane", color: "text-amber-500"}}
  ]},
  {title: "Wind direction", icon: "ph-compass", unit: "", digits: 0, cardinal: true, series: [
    {key: "winddir", label: "Direction", color: "#6366f1", average: "#312e81", median: "#a5b4fc", cardinal: true, card: {group: "atmosphere", present: "compass"}}
  ]},
  {title: "Rain", icon: "ph-cloud-rain", unit: "in", digits: 2, series: [
    {key: "hourlyrainin", label: "Hourly", color: "#2563eb", average: "#9d25eb", median: "#25eb8c"},
    {key: "dailyrainin", label: "Daily", color: "#4f46e5", average: "#e146e5", median: "#46e5d4"},
    {key: "eventrainin", label: "Event", color: "#0f766e", average: "#134e4a", median: "#5eead4", card: {group: "rain", label: "Last event total", icon: "ph-cloud-rain", color: "text-sky-600"}}
  ]},
  {title: "Pressure", icon: "ph-gauge", unit: "inHg", digits: 2, series: [
    {key: "baromrelin", label: "Relative", color: "#4338ca", average: "#c938ca", median: "#38cabd", card: {group: "atmosphere", label: "Pressure", icon: "ph-gauge", color: "text-indigo-700"}}
  ]},
  {title: "Solar / UV", icon: "ph-sun", digits: 1, independent: true, series: [
    {key: "solarradiation", label: "Solar", color: "#eab308", average: "#52ea08", median: "#ea0865", unit: "W/m\u00b2", card: {group: "atmosphere", present: "pair", pair: "sun", label: "Solar", icon: "ph-sun", color: "text-yellow-500"}},
    {key: "uv", label: "UV", color: "#e11d48", average: "#e1a61d", median: "#951de1", unit: "index", card: {group: "atmosphere", present: "pair", pair: "sun", label: "UV", icon: "ph-sun-dim", color: "text-rose-500", unit: ""}}
  ]}
];

export const RAIN_RATES = [
  {key: "total", label: "Total", icon: "ph-stack", color: "text-teal-700"},
  {key: "daily", label: "Daily", icon: "ph-calendar-blank", color: "text-indigo-500"},
  {key: "weekly", label: "Weekly", icon: "ph-calendar", color: "text-sky-700"},
  {key: "monthly", label: "Monthly", icon: "ph-calendar-check", color: "text-violet-600"}
];

const COMPASS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];
const COMPASS_FINE = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"];
const MONTH_DAYS = 28;

export const tempMode = {outdoor: "actual", indoor: "actual"};

export function isNum(value) {
  return typeof value === "number" && isFinite(value);
}

function compassPoint(degrees, points) {
  const circle = ((degrees % 360) + 360) % 360;
  const step = 360 / points.length;
  return points[Math.round(circle / step) % points.length];
}

export function cardinal(degrees) {
  if (!isNum(degrees)) return "\u2014";
  return compassPoint(degrees, COMPASS);
}

export function degreeText(degrees) {
  const rounded = Math.round(degrees * 10) / 10;
  return Number.isInteger(rounded) ? String(rounded) : rounded.toFixed(1);
}

export function cardinalDetail(degrees) {
  if (!isNum(degrees)) return "\u2014";
  const circle = ((degrees % 360) + 360) % 360;
  return compassPoint(circle, COMPASS_FINE) + " (" + degreeText(circle) + "\u00b0)";
}

function fallen(records, key) {
  let total = 0;
  let seen = false;
  let previous = null;
  for (const row of records) {
    const value = row[key];
    if (!isNum(value)) continue;
    if (seen) {
      const delta = value - previous;
      if (delta >= -0.0001) total += Math.max(0, delta);
      else total += value;
    }
    previous = value;
    seen = true;
  }
  return seen ? total : null;
}

export function rainInView(records, bounds) {
  // totalrainin stopped increasing in 2024, so rain in the view comes from weeklyrainin.
  const total = fallen(records, "weeklyrainin");
  const days = (new Date(bounds.to) - new Date(bounds.from)) / 86400000;
  if (total == null || !(days > 0)) return {total: total, daily: null, weekly: null, monthly: null};
  return {
    total: total,
    daily: days >= 1 ? total / days : null,
    weekly: days >= 7 ? total / (days / 7) : null,
    monthly: days >= MONTH_DAYS ? total / (days / MONTH_DAYS) : null
  };
}

export function shownSeries(spec) {
  if (!spec.toggle) return spec.series;
  return spec.series.filter((series) => series.mode === tempMode[spec.toggle]);
}

export function seriesUnit(spec, series) {
  return series.unit || spec.unit || "";
}

export function seriesDigits(spec, series) {
  return series.digits != null ? series.digits : spec.digits;
}

export function cardUnit(spec, series) {
  if (series.card && Object.prototype.hasOwnProperty.call(series.card, "unit")) return series.card.unit;
  return seriesUnit(spec, series);
}

export function fixed(value, digits) {
  return isNum(value) ? value.toFixed(digits) : "\u2014";
}

export function withUnit(text, unit) {
  return text === "\u2014" || !unit ? text : text + " " + unit;
}

export function formatSeriesValue(spec, series, value) {
  if (series.cardinal) return cardinal(value);
  return withUnit(fixed(value, seriesDigits(spec, series)), seriesUnit(spec, series));
}

export function formatWhen(date, withTime, crossesYear) {
  const datePart = date.toLocaleDateString(undefined, crossesYear
    ? {year: "numeric", month: "short", day: "numeric"}
    : {month: "short", day: "numeric"});
  if (!withTime) return datePart;
  const timePart = date.toLocaleTimeString(undefined, {hour: "2-digit", minute: "2-digit"});
  return datePart + " " + timePart;
}

export function formatTooltipTime(date) {
  return date.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit"
  });
}

export function stampText(iso) {
  if (!iso) return "\u2014";
  const date = new Date(iso);
  return isNaN(date.getTime()) ? iso : formatTooltipTime(date);
}

export function loadedRangeText(body) {
  const start = new Date(body.from);
  const end = new Date(body.to);
  if (isNaN(start.getTime()) || isNaN(end.getTime())) return "\u2014";
  return formatWhen(start, true, true) + " \u2013 " + formatWhen(end, true, true);
}

export function columnName(spec, series) {
  const name = spec.series.length > 1 ? spec.title + " " + series.label : spec.title;
  const unit = seriesUnit(spec, series);
  return unit ? name + " (" + unit + ")" : name;
}

export function rowAt(records, ms) {
  for (const row of records) {
    if (Date.parse(row.dateutc) === ms) return row;
  }
  return null;
}

export function measure(row, key, digits, unit) {
  return withUnit(fixed(row[key], digits), unit);
}

export function inches(value) {
  return withUnit(fixed(value, 2), "in");
}

export function numericValues(records, key) {
  const values = [];
  for (const row of records) {
    if (isNum(row[key])) values.push(row[key]);
  }
  return values;
}

export function averageOf(values) {
  let sum = 0;
  for (const value of values) sum += value;
  return sum / values.length;
}

export function medianOf(values) {
  const sorted = values.slice().sort((a, b) => a - b);
  const mid = sorted.length >> 1;
  if (sorted.length % 2) return sorted[mid];
  return (sorted[mid - 1] + sorted[mid]) / 2;
}

function isoStamp(ms) {
  return new Date(ms).toISOString().replace(/\.\d{3}Z$/, "Z");
}

export function breakSeriesGaps(points) {
  if (points.length < 3) return points;
  const times = points.map((point) => Date.parse(point.x));
  const gaps = [];
  for (let i = 1; i < times.length; i++) {
    const gap = times[i] - times[i - 1];
    if (gap > 0) gaps.push(gap);
  }
  if (!gaps.length) return points;
  const limit = medianOf(gaps) * 2;
  const broken = [points[0]];
  for (let i = 1; i < points.length; i++) {
    const gap = times[i] - times[i - 1];
    if (gap > limit) broken.push({x: isoStamp(times[i - 1] + gap / 2), y: null});
    broken.push(points[i]);
  }
  return broken;
}

function selfCheckBreakSeriesGaps() {
  const start = Date.parse("2026-01-01T00:00:00Z");
  const points = [];
  for (let i = 0; i < 6; i++) points.push({x: isoStamp(start + i * 300000), y: i});
  points.push({x: isoStamp(start + 5 * 300000 + 7200000), y: 99});
  const broken = breakSeriesGaps(points);
  if (broken.length !== points.length + 1) throw new Error("expected one gap break");
  if (broken[broken.length - 2].y !== null) throw new Error("null belongs in the hole");
  if (breakSeriesGaps(points.slice(0, 6)).length !== 6) throw new Error("even spacing stays intact");
  if (breakSeriesGaps(points.slice(0, 2)).length !== 2) throw new Error("short series");
}

function selfCheckRainAndCompass() {
  if (cardinal(0) !== "N" || cardinal(360) !== "N" || cardinal(45) !== "NE") throw new Error("cardinal");
  if (cardinal(256) !== "W" || cardinal(359) !== "N") throw new Error("cardinal wrap");
  if (cardinalDetail(256) !== "WSW (256\u00b0)") throw new Error("fine cardinal");
  if (cardinalDetail(22.5) !== "NNE (22.5\u00b0)") throw new Error("fine degrees");
  const records = [
    {dateutc: "2026-10-12T12:00:00Z", weeklyrainin: 1, monthlyrainin: 2, totalrainin: 236.22},
    {dateutc: "2026-10-12T18:00:00Z", weeklyrainin: 1.5, monthlyrainin: 2.5, totalrainin: 236.22}
  ];
  const short = rainInView(records, {from: "2026-10-12T12:00:00Z", to: "2026-10-12T18:00:00Z"});
  if (Math.abs(short.total - 0.5) > 1e-9) throw new Error("total rain");
  if (short.daily != null || short.weekly != null || short.monthly != null) throw new Error("short window");
  const twoDays = rainInView(records, {from: "2026-10-10T18:00:00Z", to: "2026-10-12T18:00:00Z"});
  if (Math.abs(twoDays.daily - 0.25) > 1e-9 || twoDays.weekly != null || twoDays.monthly != null) {
    throw new Error("two day averages");
  }
  const eightWeeks = rainInView(records, {from: "2026-08-17T18:00:00Z", to: "2026-10-12T18:00:00Z"});
  if (Math.abs(eightWeeks.daily - 0.5 / 56) > 1e-9) throw new Error("daily average");
  if (Math.abs(eightWeeks.weekly - 0.5 / 8) > 1e-9) throw new Error("weekly average");
  if (Math.abs(eightWeeks.monthly - 0.25) > 1e-9) throw new Error("monthly average");
  const reset = rainInView([
    {dateutc: "2026-10-04T12:00:00Z", weeklyrainin: 2, totalrainin: 236.22},
    {dateutc: "2026-10-12T12:00:00Z", weeklyrainin: 1, totalrainin: 236.22}
  ], {from: "2026-10-04T12:00:00Z", to: "2026-10-12T12:00:00Z"});
  if (reset.total !== 1) throw new Error("reset total");
  if (Math.abs(reset.daily - 0.125) > 1e-9 || Math.abs(reset.weekly - 0.875) > 1e-9 || reset.monthly != null) {
    throw new Error("reset averages");
  }
}

selfCheckBreakSeriesGaps();
selfCheckRainAndCompass();

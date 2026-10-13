const CHARTS = [
  {title: "Temperature", icon: "ph-thermometer", unit: "\u00b0F", digits: 1, series: [
    {key: "tempf", label: "Outdoor", color: "#f97316", average: "#aff916", median: "#f916c2"},
    {key: "feelsLike", label: "Feels like", color: "#fb7185", average: "#881337", median: "#fda4af", digits: 2},
    {key: "dewPoint", label: "Dew point", color: "#06b6d4", average: "#155e75", median: "#67e8f9", digits: 2},
    {key: "tempinf", label: "Indoor", color: "#3b82f6", average: "#9f3bf6", median: "#3bf690"},
    {key: "feelsLikein", label: "Indoor feels like", color: "#818cf8", average: "#312e81", median: "#c7d2fe"},
    {key: "dewPointin", label: "Indoor dew point", color: "#2dd4bf", average: "#115e59", median: "#99f6e4"}
  ]},
  {title: "Humidity", icon: "ph-drop", unit: "%", digits: 0, series: [
    {key: "humidity", label: "Outdoor", color: "#14b8a6", average: "#1434b8", median: "#41b814"},
    {key: "humidityin", label: "Indoor", color: "#8b5cf6", average: "#f65cd4", median: "#5ce1f6"}
  ]},
  {title: "Wind", icon: "ph-wind", unit: "mph", digits: 1, series: [
    {key: "windspeedmph", label: "Speed", color: "#0ea5e9", average: "#400ee9", median: "#0ee92d"},
    {key: "windgustmph", label: "Gust", color: "#f59e0b", average: "#76f50b", median: "#f50b89"},
    {key: "maxdailygust", label: "Max gust", color: "#ef4444", average: "#7f1d1d", median: "#fca5a5"}
  ]},
  {title: "Wind direction", icon: "ph-compass", unit: "\u00b0", digits: 0, series: [
    {key: "winddir", label: "Direction", color: "#6366f1", average: "#312e81", median: "#a5b4fc"}
  ]},
  {title: "Rain", icon: "ph-cloud-rain", unit: "in", digits: 2, series: [
    {key: "hourlyrainin", label: "Hourly", color: "#2563eb", average: "#9d25eb", median: "#25eb8c"},
    {key: "dailyrainin", label: "Daily", color: "#4f46e5", average: "#e146e5", median: "#46e5d4"},
    {key: "eventrainin", label: "Event", color: "#0f766e", average: "#134e4a", median: "#5eead4"}
  ]},
  {title: "Weekly / monthly rain", icon: "ph-calendar", unit: "in", digits: 2, series: [
    {key: "weeklyrainin", label: "Weekly", color: "#0284c7", average: "#0c4a6e", median: "#7dd3fc"},
    {key: "monthlyrainin", label: "Monthly", color: "#7c3aed", average: "#4c1d95", median: "#c4b5fd"}
  ]},
  {title: "Total rain", icon: "ph-stack", unit: "in", digits: 2, series: [
    {key: "totalrainin", label: "Total", color: "#0f766e", average: "#134e4a", median: "#99f6e4"}
  ]},
  {title: "Pressure", icon: "ph-gauge", unit: "inHg", digits: 2, series: [
    {key: "baromrelin", label: "Relative", color: "#4338ca", average: "#c938ca", median: "#38cabd"}
  ]},
  {title: "Solar / UV", icon: "ph-sun", digits: 1, independent: true, series: [
    {key: "solarradiation", label: "Solar", color: "#eab308", average: "#52ea08", median: "#ea0865", unit: "W/m\u00b2"},
    {key: "uv", label: "UV", color: "#e11d48", average: "#e1a61d", median: "#951de1", unit: "index"}
  ]}
];

const STRIP = [
  ["Outdoor", "tempf", "\u00b0F", 1, "ph-thermometer", "text-orange-500"],
  ["Feels like", "feelsLike", "\u00b0F", 2, "ph-thermometer-hot", "text-rose-500"],
  ["Dew point", "dewPoint", "\u00b0F", 2, "ph-drop", "text-cyan-600"],
  ["Indoor", "tempinf", "\u00b0F", 1, "ph-house", "text-blue-500"],
  ["Indoor feels like", "feelsLikein", "\u00b0F", 1, "ph-thermometer-hot", "text-indigo-500"],
  ["Indoor dew point", "dewPointin", "\u00b0F", 1, "ph-drop", "text-teal-500"],
  ["Humidity", "humidity", "%", 0, "ph-drop", "text-teal-600"],
  ["Wind", "windspeedmph", "mph", 1, "ph-wind", "text-sky-500"],
  ["Wind direction", "winddir", "\u00b0", 0, "ph-compass", "text-indigo-500"],
  ["Max gust", "maxdailygust", "mph", 1, "ph-wind", "text-amber-500"],
  ["Pressure", "baromrelin", "inHg", 2, "ph-gauge", "text-indigo-700"],
  ["UV", "uv", "", 1, "ph-sun", "text-rose-500"],
  ["Daily rain", "dailyrainin", "in", 2, "ph-cloud-rain", "text-indigo-500"],
  ["Event rain", "eventrainin", "in", 2, "ph-cloud-rain", "text-sky-600"],
  ["Weekly rain", "weeklyrainin", "in", 2, "ph-calendar", "text-sky-700"],
  ["Monthly rain", "monthlyrainin", "in", 2, "ph-calendar", "text-violet-600"],
  ["Total rain", "totalrainin", "in", 2, "ph-stack", "text-teal-700"],
  ["Last rain", "lastRain", "", null, "ph-clock", "text-slate-500"]
];

const TWO_DAYS = 2 * 24 * 60 * 60 * 1000;

const filterButton = document.getElementById("filter-value");
const filterLabelNode = document.getElementById("filter-label");
const filterMenu = document.getElementById("filter-menu");
const lastCount = document.getElementById("last-count");
const lastUnit = document.getElementById("last-unit");
const fromInput = document.getElementById("from");
const toInput = document.getElementById("to");
const backButton = document.getElementById("back");
const resetRow = document.getElementById("reset-row");
const errorNode = document.getElementById("error");
const errorMsg = document.getElementById("error-msg");
const UNITS = ["seconds", "minutes", "hours", "days", "months", "years"];
const UNIT_SINGULAR = {
  seconds: "second",
  minutes: "minute",
  hours: "hour",
  days: "day",
  months: "month",
  years: "year"
};
const showStats = {average: true, median: false};
let source = "historical";
let view = "charts";
let requestId = 0;
let loading = false;
let refreshTimer = 0;
let lastBody = null;
let charts = [];
let filter = {kind: "last", count: 24, unit: "hours", from: "", to: ""};
const backStack = [];

if (window.Chart) {
  Chart.defaults.font.family = "'Inter', sans-serif";
  Chart.defaults.color = "#64748b";
  Chart.defaults.scale.grid.color = "#f1f5f9";
  Chart.defaults.plugins.tooltip.backgroundColor = "rgba(15, 23, 42, 0.9)";
  Chart.defaults.plugins.tooltip.padding = 12;
  Chart.defaults.plugins.tooltip.cornerRadius = 8;
  Chart.defaults.plugins.tooltip.titleFont = {size: 13, weight: "600"};
  Chart.defaults.plugins.tooltip.bodyFont = {size: 12};
  Chart.defaults.plugins.tooltip.boxPadding = 6;
}

function isNum(value) {
  return typeof value === "number" && isFinite(value);
}

function fixed(value, digits) {
  return isNum(value) ? value.toFixed(digits) : "\u2014";
}

function withUnit(text, unit) {
  return text === "\u2014" || !unit ? text : text + " " + unit;
}

function pad(number) {
  return String(number).padStart(2, "0");
}

function toLocalInput(date) {
  return date.getFullYear() + "-" + pad(date.getMonth() + 1) + "-" + pad(date.getDate())
    + "T" + pad(date.getHours()) + ":" + pad(date.getMinutes()) + ":" + pad(date.getSeconds());
}

function toUtcParam(localValue) {
  const date = new Date(localValue);
  if (isNaN(date.getTime())) throw new Error("Enter a valid date range.");
  return date.toISOString().replace(/\.\d{3}Z$/, "Z");
}

function formatWhen(date, withTime, crossesYear) {
  const datePart = date.toLocaleDateString(undefined, crossesYear
    ? {year: "numeric", month: "short", day: "numeric"}
    : {month: "short", day: "numeric"});
  if (!withTime) return datePart;
  const timePart = date.toLocaleTimeString(undefined, {hour: "2-digit", minute: "2-digit"});
  return datePart + " " + timePart;
}

function formatTooltipTime(date) {
  return date.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit"
  });
}

function stampText(iso) {
  if (!iso) return "\u2014";
  const date = new Date(iso);
  return isNaN(date.getTime()) ? iso : formatTooltipTime(date);
}

function seriesUnit(spec, series) {
  return series.unit || spec.unit || "";
}

function seriesDigits(spec, series) {
  return series.digits != null ? series.digits : spec.digits;
}

function columnName(spec, series) {
  const name = spec.series.length > 1 ? spec.title + " " + series.label : spec.title;
  const unit = seriesUnit(spec, series);
  return unit ? name + " (" + unit + ")" : name;
}

function rowAt(records, ms) {
  for (const row of records) {
    if (Date.parse(row.dateutc) === ms) return row;
  }
  return null;
}

function renderLatest(latest) {
  const root = document.getElementById("latest");
  root.replaceChildren();
  document.getElementById("updated").textContent = "Updated " + stampText(latest.dateutc);

  for (const [label, key, unit, digits, icon, iconColor] of STRIP) {
    const value = digits == null ? stampText(latest[key]) : fixed(latest[key], digits);
    const card = document.createElement("div");
    card.className = "bg-white p-4 rounded-xl shadow-sm border border-slate-200 flex flex-col justify-center";
    const valueRow = document.createElement("div");
    valueRow.className = "flex items-end";
    if (value === "\u2014") {
      valueRow.textContent = value;
    } else {
      const amount = document.createElement("span");
      amount.className = digits == null
        ? "text-sm font-semibold leading-snug tracking-tight text-slate-900"
        : "text-2xl font-bold tracking-tight text-slate-900";
      amount.textContent = value;
      valueRow.append(amount);
      if (unit) {
        const unitNode = document.createElement("span");
        unitNode.className = "text-sm font-medium text-slate-500 ml-1 mb-1";
        unitNode.textContent = unit;
        valueRow.append(unitNode);
      }
    }
    card.innerHTML = `
      <div class="flex items-center gap-2 text-slate-500 mb-1">
        <i class="ph ${icon} ${iconColor} text-lg"></i>
        <span class="text-xs font-semibold uppercase tracking-wider"></span>
      </div>
    `;
    card.querySelector("span").textContent = label;
    card.append(valueRow);
    root.append(card);
  }
}

function clearCharts() {
  for (const chart of charts) chart.destroy();
  charts = [];
}

function yScale(unit, position) {
  const scale = {
    title: {display: Boolean(unit), text: unit || "", font: {weight: "600", size: 11}, color: "#94a3b8"},
    ticks: {maxTicksLimit: 6, color: "#64748b"},
    border: {display: false}
  };
  if (position) {
    scale.position = position;
    scale.grid = {drawOnChartArea: false};
  }
  return scale;
}

function unitWord(count, unit) {
  return count === 1 ? (UNIT_SINGULAR[unit] || unit) : unit;
}

function filterText(value) {
  if (value.kind === "last") return "Last " + value.count + " " + unitWord(value.count, value.unit);
  const start = new Date(value.from);
  const end = new Date(value.to);
  const crossesYear = start.getFullYear() !== end.getFullYear();
  return formatWhen(start, true, crossesYear) + " \u2013 " + formatWhen(end, true, crossesYear);
}

function updateFilterLabel() {
  filterLabelNode.textContent = filterText(filter);
  const index = UNITS.indexOf(filter.unit);
  document.querySelector('[data-step="unit-down"]').disabled = filter.kind === "last" && index <= 0;
  document.querySelector('[data-step="unit-up"]').disabled = filter.kind === "last" && index >= UNITS.length - 1;
  document.querySelector('[data-step="amount-down"]').disabled = filter.kind === "last" && filter.count <= 1;
  document.querySelector('[data-step="amount-up"]').disabled = false;
}

function shiftLocal(value, days, months) {
  const date = new Date(value);
  if (days) date.setDate(date.getDate() + days);
  if (months) date.setMonth(date.getMonth() + months);
  return toLocalInput(date);
}

function stepFilter(which) {
  const next = copyFilter(filter);
  if (next.kind === "last") {
    const index = UNITS.indexOf(next.unit);
    if (which === "amount-down") next.count -= 1;
    else if (which === "amount-up") next.count += 1;
    else if (which === "unit-down") next.unit = UNITS[index - 1];
    else if (which === "unit-up") next.unit = UNITS[index + 1];
    if (!next.unit || next.count < 1) return;
  } else if (which === "amount-down") {
    next.from = shiftLocal(next.from, -1, 0);
  } else if (which === "amount-up") {
    next.to = shiftLocal(next.to, 1, 0);
  } else if (which === "unit-down") {
    next.from = shiftLocal(next.from, 0, -1);
    next.to = shiftLocal(next.to, 0, -1);
  } else if (which === "unit-up") {
    next.from = shiftLocal(next.from, 0, 1);
    next.to = shiftLocal(next.to, 0, 1);
  }
  if (next.kind === "range" && new Date(next.from) > new Date(next.to)) return;
  filter = next;
  updateFilterLabel();
  closeMenu();
  load().catch(showError);
}

function subtractUnit(date, count, unit) {
  const next = new Date(date.getTime());
  if (unit === "seconds") next.setSeconds(next.getSeconds() - count);
  else if (unit === "minutes") next.setMinutes(next.getMinutes() - count);
  else if (unit === "hours") next.setHours(next.getHours() - count);
  else if (unit === "days") next.setDate(next.getDate() - count);
  else if (unit === "months") next.setMonth(next.getMonth() - count);
  else if (unit === "years") next.setFullYear(next.getFullYear() - count);
  return next;
}

function currentBounds() {
  if (filter.kind === "range") return {from: filter.from, to: filter.to};
  const end = new Date();
  const start = subtractUnit(end, filter.count, filter.unit);
  return {from: toLocalInput(start), to: toLocalInput(end)};
}

function copyFilter(value) {
  return {kind: value.kind, count: value.count, unit: value.unit, from: value.from, to: value.to};
}

function modeKind() {
  const selected = filterMenu.querySelector('input[name="filter-mode"]:checked');
  return selected ? selected.value : "last";
}

function showMode(kind) {
  const mode = kind === "range" ? "range" : "last";
  for (const input of filterMenu.querySelectorAll('input[name="filter-mode"]')) {
    input.checked = input.value === mode;
  }
}

function syncMenu() {
  lastCount.value = String(filter.count || 24);
  lastUnit.value = filter.unit || "hours";
  if (filter.kind === "range") {
    fromInput.value = filter.from;
    toInput.value = filter.to;
  } else if (lastBody && lastBody.from && lastBody.to) {
    fromInput.value = toLocalInput(new Date(lastBody.from));
    toInput.value = toLocalInput(new Date(lastBody.to));
  }
  showMode(filter.kind);
}

function placeMenu() {
  filterMenu.style.right = "0px";
  filterMenu.style.left = "auto";
  const margin = 8;
  let rect = filterMenu.getBoundingClientRect();
  if (rect.left < margin) filterMenu.style.right = (rect.left - margin) + "px";
  rect = filterMenu.getBoundingClientRect();
  if (rect.right > window.innerWidth - margin) {
    const current = parseFloat(filterMenu.style.right) || 0;
    filterMenu.style.right = (current + rect.right - (window.innerWidth - margin)) + "px";
  }
}

function openMenu() {
  syncMenu();
  filterMenu.hidden = false;
  filterButton.setAttribute("aria-expanded", "true");
  placeMenu();
}

function closeMenu() {
  filterMenu.hidden = true;
  filterButton.setAttribute("aria-expanded", "false");
}

function onZoomComplete({chart}) {
  const min = chart.scales.x.min;
  const max = chart.scales.x.max;
  const domain = chart.$domain || {min: min, max: max};
  if (!(max > min)) {
    chart.resetZoom();
    return;
  }
  if (Math.abs(min - domain.min) < 1000 && Math.abs(max - domain.max) < 1000) {
    chart.resetZoom();
    return;
  }
  const nextFrom = toLocalInput(new Date(min));
  const nextTo = toLocalInput(new Date(max));
  const loadedFrom = lastBody ? toLocalInput(new Date(lastBody.from)) : "";
  const loadedTo = lastBody ? toLocalInput(new Date(lastBody.to)) : "";
  if (nextFrom === loadedFrom && nextTo === loadedTo) {
    chart.resetZoom();
    return;
  }
  backStack.push(copyFilter(filter));
  resetRow.hidden = false;
  filter = {kind: "range", count: filter.count, unit: filter.unit, from: nextFrom, to: nextTo};
  updateFilterLabel();
  closeMenu();
  load().catch(showError);
}

function numericValues(records, key) {
  const values = [];
  for (const row of records) {
    if (isNum(row[key])) values.push(row[key]);
  }
  return values;
}

function averageOf(values) {
  let sum = 0;
  for (const value of values) sum += value;
  return sum / values.length;
}

function medianOf(values) {
  const sorted = values.slice().sort((a, b) => a - b);
  const mid = sorted.length >> 1;
  if (sorted.length % 2) return sorted[mid];
  return (sorted[mid - 1] + sorted[mid]) / 2;
}

function isoAt(ms) {
  return new Date(ms).toISOString().replace(/\.\d{3}Z$/, "Z");
}

function breakSeriesGaps(points) {
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
    if (gap > limit) broken.push({x: isoAt(times[i - 1] + gap / 2), y: null});
    broken.push(points[i]);
  }
  return broken;
}

function selfCheckBreakSeriesGaps() {
  const start = Date.parse("2026-01-01T00:00:00Z");
  const points = [];
  for (let i = 0; i < 6; i++) points.push({x: isoAt(start + i * 300000), y: i});
  points.push({x: isoAt(start + 5 * 300000 + 7200000), y: 99});
  const broken = breakSeriesGaps(points);
  if (broken.length !== points.length + 1) throw new Error("expected one gap break");
  if (broken[broken.length - 2].y !== null) throw new Error("null belongs in the hole");
  if (breakSeriesGaps(points.slice(0, 6)).length !== 6) throw new Error("even spacing stays intact");
  if (breakSeriesGaps(points.slice(0, 2)).length !== 2) throw new Error("short series");
}

function isoStamp(ms) {
  return new Date(ms).toISOString().replace(/\.\d{3}Z$/, "Z");
}

function breakSeriesGaps(points) {
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

function statSummary(spec, records, flags) {
  const block = document.createElement("div");
  block.className = "mt-3 bg-slate-50 rounded-lg p-3 border border-slate-100 flex flex-col gap-2";
  for (const kind of ["average", "median"]) {
    if (!flags[kind]) continue;
    const line = document.createElement("div");
    line.className = "flex items-center flex-wrap gap-x-4 gap-y-1 text-sm";
    const name = document.createElement("span");
    name.className = "font-semibold text-slate-700 min-w-[4rem]";
    name.textContent = kind === "average" ? "Avg:" : "Med:";
    line.append(name);
    for (const series of spec.series) {
      const values = numericValues(records, series.key);
      if (!values.length) continue;
      const value = kind === "average" ? averageOf(values) : medianOf(values);
      const item = document.createElement("div");
      item.className = "flex items-center gap-1.5 text-slate-600";
      const swatch = document.createElement("i");
      swatch.className = "block w-2.5 h-2.5 rounded-full shadow-sm";
      swatch.style.backgroundColor = series[kind];
      const text = document.createElement("span");
      text.textContent = series.label + " " + withUnit(
        fixed(value, seriesDigits(spec, series)),
        seriesUnit(spec, series)
      );
      item.append(swatch, text);
      line.append(item);
    }
    block.append(line);
  }
  return block;
}

function statLine(spec, series, kind, value, axis, body) {
  const color = series[kind];
  return {
    label: series.label + " " + kind,
    stat: true,
    data: [{x: body.from, y: value}, {x: body.to, y: value}],
    borderColor: color,
    backgroundColor: color,
    borderDash: kind === "median" ? [2, 4] : [6, 4],
    borderWidth: 1.5,
    pointRadius: 0,
    pointHoverRadius: 0,
    tension: 0,
    yAxisID: axis,
    spanGaps: true
  };
}

function renderCharts(body) {
  clearCharts();
  const root = document.getElementById("charts");
  root.replaceChildren();
  const records = body.records || [];
  const start = new Date(body.from);
  const end = new Date(body.to);
  const short = end - start <= TWO_DAYS;
  const crossesYear = start.getFullYear() !== end.getFullYear();
  for (const spec of CHARTS) {
    const figure = document.createElement("figure");
    figure.className = "bg-white p-5 rounded-2xl shadow-sm border border-slate-200 flex flex-col";
    const headerDiv = document.createElement("div");
    headerDiv.className = "flex items-center gap-2 mb-4";
    headerDiv.innerHTML = `
      <div class="p-2 bg-brand-50 rounded-lg text-brand-600">
        <i class="ph ${spec.icon} text-xl"></i>
      </div>
      <figcaption class="text-lg font-semibold text-slate-800"></figcaption>
    `;
    headerDiv.querySelector("figcaption").textContent = spec.title;
    figure.append(headerDiv);

    const points = spec.series.map((series) => records.filter((row) => isNum(row[series.key])));
    const count = points.reduce((sum, series) => sum + series.length, 0);
    if (!count) {
      const empty = document.createElement("div");
      empty.className = "flex-1 flex items-center justify-center min-h-[220px] text-slate-400 bg-slate-50/50 rounded-xl border border-dashed border-slate-200";
      empty.innerHTML = `<p class="flex items-center gap-2"><i class="ph ph-chart-line-down text-lg"></i> No readings in this range.</p>`;
      figure.append(empty);
      root.append(figure);
      continue;
    }

    const box = document.createElement("div");
    box.className = "relative h-[250px] w-full flex-1";
    const canvas = document.createElement("canvas");
    canvas.setAttribute("role", "img");
    canvas.setAttribute("aria-label", spec.title);
    box.append(canvas);
    figure.append(box);

    const flags = showStats;
    if (flags.average || flags.median) figure.append(statSummary(spec, records, flags));
    root.append(figure);

    const datasets = spec.series.map((series, index) => ({
      label: series.label,
      data: breakSeriesGaps(records.map((row) => ({
        x: row.dateutc,
        y: isNum(row[series.key]) ? row[series.key] : null
      }))),
      borderColor: series.color,
      backgroundColor: series.color + "20",
      yAxisID: spec.independent && index > 0 ? "y1" : "y",
      spanGaps: false,
      pointRadius: 0,
      pointHoverRadius: 4,
      pointHoverBackgroundColor: "#fff",
      pointHoverBorderWidth: 2,
      pointHoverBorderColor: series.color,
      borderWidth: 2,
      tension: 0.1
    }));
    spec.series.forEach((series, index) => {
      const values = numericValues(records, series.key);
      if (!values.length) return;
      const axis = spec.independent && index > 0 ? "y1" : "y";
      if (flags.average) datasets.push(statLine(spec, series, "average", averageOf(values), axis, body));
      if (flags.median) datasets.push(statLine(spec, series, "median", medianOf(values), axis, body));
    });
    const scales = {
      x: {
        type: "time",
        min: body.from,
        max: body.to,
        grid: {display: false},
        ticks: {
          maxRotation: 0,
          autoSkip: true,
          maxTicksLimit: 6,
          callback(value, index, ticks) {
            return formatWhen(new Date(ticks[index].value), short, crossesYear);
          }
        }
      },
      y: yScale(seriesUnit(spec, spec.series[0]))
    };
    if (spec.independent && spec.series[1]) {
      scales.y1 = yScale(seriesUnit(spec, spec.series[1]), "right");
    }
    const chart = new Chart(canvas, {
      type: "line",
      data: {datasets: datasets},
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: {duration: 400, easing: "easeOutQuart"},
        interaction: {mode: "index", intersect: false},
        layout: {padding: {top: 10}},
        plugins: {
          legend: {
            position: "bottom",
            labels: {
              usePointStyle: true,
              padding: 20,
              font: {family: "'Inter', sans-serif", size: 12},
              filter(item, data) {
                const dataset = data.datasets[item.datasetIndex];
                return !(dataset && dataset.stat);
              }
            }
          },
          tooltip: {
            mode: "index",
            intersect: false,
            callbacks: {
              title(items) {
                const ms = items[0].parsed.x;
                const lines = [formatTooltipTime(new Date(ms))];
                const row = rowAt(records, ms);
                for (const series of spec.series) {
                  const value = row ? row[series.key] : null;
                  lines.push(series.label + ": " + withUnit(
                    fixed(value, seriesDigits(spec, series)),
                    seriesUnit(spec, series)
                  ));
                }
                return lines;
              },
              label() { return null; }
            }
          },
          zoom: {
            zoom: {
              wheel: {enabled: false},
              pinch: {enabled: false},
              drag: {
                enabled: true,
                threshold: 8,
                backgroundColor: "rgba(14, 165, 233, 0.2)",
                borderColor: "rgba(14, 165, 233, 0.8)",
                borderWidth: 1
              },
              mode: "x",
              onZoomComplete: onZoomComplete
            }
          }
        },
        scales: scales
      }
    });
    chart.$domain = {min: start.getTime(), max: end.getTime()};
    charts.push(chart);
  }
}

function renderTable(records) {
  const thead = document.getElementById("table-head");
  const tbody = document.getElementById("table-body");
  thead.replaceChildren();
  tbody.replaceChildren();
  if (!records.length) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td colspan="100%" class="px-6 py-12 text-center text-slate-500 bg-white">
      <i class="ph ph-table text-3xl mb-2 text-slate-300"></i><br>
      No readings in this range.
    </td>`;
    tbody.append(tr);
    return;
  }
  const headRow = document.createElement("tr");
  const timeHeader = document.createElement("th");
  timeHeader.scope = "col";
  timeHeader.className = "px-6 py-3 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider sticky left-0 bg-slate-50 z-20 shadow-[1px_0_0_0_#e2e8f0]";
  timeHeader.textContent = "Time";
  headRow.append(timeHeader);
  const columns = [];
  for (const spec of CHARTS) {
    for (const series of spec.series) {
      columns.push({spec: spec, series: series});
      const cell = document.createElement("th");
      cell.scope = "col";
      cell.className = "px-6 py-3 text-right text-xs font-semibold text-slate-500 uppercase tracking-wider whitespace-nowrap";
      cell.textContent = columnName(spec, series);
      headRow.append(cell);
    }
  }
  const rainHeader = document.createElement("th");
  rainHeader.scope = "col";
  rainHeader.className = "px-6 py-3 text-right text-xs font-semibold text-slate-500 uppercase tracking-wider whitespace-nowrap";
  rainHeader.textContent = "Last rain";
  headRow.append(rainHeader);
  thead.append(headRow);
  for (const row of records) {
    const tr = document.createElement("tr");
    tr.className = "hover:bg-slate-50/50 transition-colors";
    const when = document.createElement("td");
    when.className = "px-6 py-3 text-sm text-slate-900 whitespace-nowrap sticky left-0 bg-white shadow-[1px_0_0_0_#e2e8f0] font-medium";
    when.textContent = stampText(row.dateutc);
    tr.append(when);
    for (const column of columns) {
      const td = document.createElement("td");
      td.className = "px-6 py-3 text-sm text-slate-600 text-right whitespace-nowrap tabular-nums";
      td.textContent = withUnit(
        fixed(row[column.series.key], seriesDigits(column.spec, column.series)),
        seriesUnit(column.spec, column.series)
      );
      tr.append(td);
    }
    const rainCell = document.createElement("td");
    rainCell.className = "px-6 py-3 text-sm text-slate-600 text-right whitespace-nowrap";
    rainCell.textContent = stampText(row.lastRain);
    tr.append(rainCell);
    tbody.append(tr);
  }
}

function statusText(body) {
  const name = body.source === "station" ? "Station" : "Historical";
  const shown = Array.isArray(body.records) ? body.records.length : 0;
  if (body.step > 1) return name + " \u00b7 " + shown + " of " + body.total + " readings";
  return name + " \u00b7 " + shown + " readings";
}

function render(body) {
  lastBody = body;
  errorNode.hidden = true;
  document.getElementById("status").textContent = statusText(body);
  updateFilterLabel();
  renderLatest(body.latest || {});
  const chartsPanel = document.getElementById("charts");
  const tablePanel = document.getElementById("table-wrap");
  if (view === "table") {
    clearCharts();
    chartsPanel.hidden = true;
    tablePanel.hidden = false;
    renderTable(body.records || []);
    return;
  }
  tablePanel.hidden = true;
  chartsPanel.hidden = false;
  renderCharts(body);
}

function showError(error) {
  errorNode.hidden = false;
  errorMsg.textContent = error.message || "Could not load readings.";
}

function press(group, attr, value) {
  for (const button of document.querySelectorAll("#" + group + " button")) {
    const isPressed = button.dataset[attr] === value;
    button.setAttribute("aria-pressed", isPressed ? "true" : "false");
    if (isPressed) {
      button.classList.add("bg-white", "shadow-sm", "text-slate-900");
      button.classList.remove("text-slate-600", "hover:text-slate-900");
    } else {
      button.classList.remove("bg-white", "shadow-sm", "text-slate-900");
      button.classList.add("text-slate-600", "hover:text-slate-900");
    }
  }
}

function readMenuFilter() {
  if (modeKind() === "range") {
    if (!fromInput.value || !toInput.value) throw new Error("Enter a start and an end.");
    if (new Date(fromInput.value) > new Date(toInput.value)) throw new Error("Start must be before the end.");
    return {kind: "range", count: filter.count, unit: filter.unit, from: fromInput.value, to: toInput.value};
  }
  const count = Number(lastCount.value);
  if (!Number.isInteger(count) || count < 1) throw new Error("Enter a whole number of 1 or more.");
  const unit = lastUnit.value;
  if (!UNIT_SINGULAR[unit]) throw new Error("Choose a unit.");
  return {kind: "last", count: count, unit: unit, from: "", to: ""};
}

function setLoading(on) {
  loading = on;
  const graphics = document.getElementById("graphics");
  graphics.classList.toggle("is-loading", on);
  graphics.setAttribute("aria-busy", on ? "true" : "false");
  document.getElementById("loading").hidden = !on;
  document.querySelector("#refresh i").classList.toggle("animate-spin", on);
}

function applyAutoRefresh() {
  clearInterval(refreshTimer);
  refreshTimer = 0;
  const seconds = Number(document.getElementById("auto-refresh-seconds").value);
  if (!document.getElementById("auto-refresh").checked) return;
  if (!Number.isInteger(seconds) || seconds < 1) return;
  refreshTimer = setInterval(() => {
    if (!loading) load().catch(showError);
  }, seconds * 1000);
}

async function load() {
  const id = ++requestId;
  setLoading(true);
  try {
    const bounds = currentBounds();
    const params = new URLSearchParams();
    params.set("source", source);
    params.set("from", toUtcParam(bounds.from));
    params.set("to", toUtcParam(bounds.to));
    const response = await fetch("/dashboard/series?" + params.toString());
    if (!response.ok) throw new Error("Series request failed (" + response.status + ")");
    const body = await response.json();
    if (id !== requestId) return;
    render(body);
  } catch (error) {
    if (id !== requestId) return;
    showError(error);
  } finally {
    if (id === requestId) setLoading(false);
  }
}

document.getElementById("source").addEventListener("click", (event) => {
  const button = event.target.closest("button");
  if (!button) return;
  source = button.dataset.source;
  press("source", "source", source);
  load().catch(showError);
});

filterButton.addEventListener("click", () => {
  if (filterMenu.hidden) openMenu();
  else closeMenu();
});

filterMenu.addEventListener("submit", (event) => {
  event.preventDefault();
  try {
    filter = readMenuFilter();
  } catch (error) {
    showError(error);
    return;
  }
  errorNode.hidden = true;
  closeMenu();
  updateFilterLabel();
  load().catch(showError);
});

filterMenu.addEventListener("click", (event) => {
  const row = event.target.closest(".mode");
  if (!row) return;
  const radio = row.querySelector('input[name="filter-mode"]');
  if (!radio) return;
  radio.checked = true;
  showMode(radio.value);
});

lastCount.addEventListener("input", () => showMode("last"));
lastUnit.addEventListener("change", () => showMode("last"));
fromInput.addEventListener("input", () => showMode("range"));
toInput.addEventListener("input", () => showMode("range"));

document.addEventListener("click", (event) => {
  if (filterMenu.hidden || event.target.closest("#filter")) return;
  closeMenu();
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") closeMenu();
});

backButton.addEventListener("click", () => {
  const original = backStack[0];
  backStack.length = 0;
  resetRow.hidden = true;
  if (!original) return;
  filter = original;
  updateFilterLabel();
  closeMenu();
  load().catch(showError);
});

document.querySelector(".stepper").addEventListener("click", (event) => {
  const button = event.target.closest("button[data-step]");
  if (!button || button.disabled) return;
  stepFilter(button.dataset.step);
});

document.getElementById("stats").addEventListener("change", (event) => {
  if (event.target.id === "show-average") showStats.average = event.target.checked;
  else if (event.target.id === "show-median") showStats.median = event.target.checked;
  else return;
  if (lastBody && view === "charts") renderCharts(lastBody);
});

document.getElementById("refresh").addEventListener("click", () => {
  load().catch(showError);
});

document.getElementById("auto-refresh").addEventListener("change", applyAutoRefresh);
document.getElementById("auto-refresh-seconds").addEventListener("change", applyAutoRefresh);
applyAutoRefresh();

document.getElementById("view").addEventListener("click", (event) => {
  const button = event.target.closest("button");
  if (!button) return;
  view = button.dataset.view;
  press("view", "view", view);
  if (lastBody) render(lastBody);
});

press("source", "source", source);
press("view", "view", view);
selfCheckBreakSeriesGaps();

if (!window.Chart) {
  showError(new Error("Chart library failed to load."));
} else {
  load().catch(showError);
}

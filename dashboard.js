import {
  CHARTS,
  averageOf,
  breakSeriesGaps,
  cardinal,
  cardinalDetail,
  columnName,
  fixed,
  formatSeriesValue,
  formatTooltipTime,
  formatWhen,
  isNum,
  medianOf,
  numericValues,
  rowAt,
  seriesDigits,
  seriesUnit,
  shownSeries,
  stampText,
  tempMode,
  withUnit
} from "./dashboard-series.js";
import {renderLatest} from "./dashboard-cards.js";
import {applyZoom, bindRange, currentBounds, toUtcParam, updateFilterLabel} from "./dashboard-range.js";

const Chart = window.Chart;
const TWO_DAYS = 2 * 24 * 60 * 60 * 1000;
const errorNode = document.getElementById("error");
const errorMsg = document.getElementById("error-msg");
const showStats = {average: true, median: false};
let source = "historical";
let view = "charts";
let requestId = 0;
let loading = false;
let refreshTimer = 0;
let lastBody = null;
let charts = [];

if (Chart) {
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

function tempToggle(which) {
  const group = document.createElement("div");
  group.className = "ml-auto flex p-0.5 bg-slate-100 rounded-lg shrink-0";
  group.setAttribute("role", "group");
  group.setAttribute("aria-label", which === "indoor" ? "Indoor temperature" : "Outdoor temperature");
  for (const [mode, label] of [["actual", "Actual"], ["feels", "Feels like"]]) {
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.temp = which;
    button.dataset.tempMode = mode;
    const pressed = tempMode[which] === mode;
    button.setAttribute("aria-pressed", pressed ? "true" : "false");
    button.className = "px-2 py-1 text-xs font-medium rounded-md " + (pressed
      ? "bg-white shadow-sm text-slate-900"
      : "text-slate-600 hover:text-slate-900");
    button.textContent = label;
    group.append(button);
  }
  return group;
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
    const shown = shownSeries(spec);
    const figure = document.createElement("figure");
    figure.className = "bg-white p-5 rounded-2xl shadow-sm border border-slate-200 flex flex-col";
    const headerDiv = document.createElement("div");
    headerDiv.className = "flex items-center gap-2 mb-4";
    const titleWrap = document.createElement("div");
    titleWrap.className = "flex items-center gap-2 min-w-0";
    const iconBox = document.createElement("div");
    iconBox.className = "p-2 bg-brand-50 rounded-lg text-brand-600";
    const icon = document.createElement("i");
    icon.className = "ph " + spec.icon + " text-xl";
    iconBox.append(icon);
    const caption = document.createElement("figcaption");
    caption.className = "text-lg font-semibold text-slate-800";
    caption.textContent = spec.title;
    titleWrap.append(iconBox, caption);
    headerDiv.append(titleWrap);
    if (spec.toggle) headerDiv.append(tempToggle(spec.toggle));
    figure.append(headerDiv);

    const points = shown.map((series) => records.filter((row) => isNum(row[series.key])));
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
    const draw = Object.assign({}, spec, {series: shown});
    if (!spec.cardinal && (flags.average || flags.median)) figure.append(statSummary(draw, records, flags));
    root.append(figure);

    const datasets = shown.map((series, index) => ({
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
    if (!spec.cardinal) shown.forEach((series, index) => {
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
      y: yScale(seriesUnit(spec, shown[0]))
    };
    if (spec.cardinal) {
      scales.y.min = 0;
      scales.y.max = 360;
      scales.y.ticks.stepSize = 45;
      scales.y.ticks.callback = (value) => cardinal(Number(value));
    }
    if (spec.independent && shown[1]) {
      scales.y1 = yScale(seriesUnit(spec, shown[1]), "right");
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
                for (const series of shown) {
                  const value = row ? row[series.key] : null;
                  const text = series.cardinal ? cardinalDetail(value) : formatSeriesValue(spec, series, value);
                  lines.push(series.label + ": " + text);
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
              onZoomComplete: ({chart: zoomed}) => {
                if (applyZoom(zoomed, lastBody)) load().catch(showError);
              }
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
      td.textContent = formatSeriesValue(column.spec, column.series, row[column.series.key]);
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
  renderLatest(body);
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

bindRange(() => lastBody, (error) => {
  if (error) {
    showError(error);
    return;
  }
  errorNode.hidden = true;
  load().catch(showError);
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

document.getElementById("charts").addEventListener("click", (event) => {
  const button = event.target.closest("button[data-temp-mode]");
  if (!button) return;
  tempMode[button.dataset.temp] = button.dataset.tempMode;
  if (lastBody && view === "charts") renderCharts(lastBody);
});

document.getElementById("view").addEventListener("click", (event) => {
  const button = event.target.closest("button");
  if (!button) return;
  view = button.dataset.view;
  press("view", "view", view);
  if (lastBody) render(lastBody);
});

press("source", "source", source);
press("view", "view", view);

if (!Chart) {
  showError(new Error("Chart library failed to load."));
} else {
  load().catch(showError);
}

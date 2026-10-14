import {
  CHARTS,
  RAIN_RATES,
  cardinal,
  cardUnit,
  degreeText,
  inches,
  isNum,
  loadedRangeText,
  measure,
  rainInView,
  seriesDigits,
  stampText
} from "./dashboard-series.js";

const GROUPS = [
  {id: "outdoor", title: "Outdoor"},
  {id: "indoor", title: "Indoor"},
  {id: "atmosphere", title: "Atmosphere"},
  {id: "rain", title: "Rain", range: true}
];

function metricBody(label, text, icon, iconColor) {
  const block = document.createElement("div");
  block.className = "min-w-0";
  const heading = document.createElement("div");
  heading.className = "flex items-center gap-1.5 min-w-0 text-slate-500";
  const iconNode = document.createElement("i");
  iconNode.className = "ph " + icon + " " + iconColor + " text-base shrink-0";
  iconNode.setAttribute("aria-hidden", "true");
  const name = document.createElement("p");
  name.className = "text-[10px] font-semibold uppercase tracking-wider truncate";
  name.textContent = label;
  heading.append(iconNode, name);
  const value = document.createElement("p");
  value.className = "text-sm font-semibold tabular-nums text-slate-900 mt-0.5 break-words";
  value.textContent = text;
  block.append(heading, value);
  return block;
}

function metricBox(label, text, icon, iconColor) {
  const card = document.createElement("div");
  card.className = "bg-white px-3 py-2.5 rounded-xl shadow-sm border border-slate-200 min-w-0 flex flex-col justify-center";
  card.append(metricBody(label, text, icon, iconColor));
  return card;
}

function compactPair(left, right, wide) {
  const card = document.createElement("div");
  card.className = (wide ? "col-span-2 " : "") + "bg-white px-3 py-2 rounded-xl shadow-sm border border-slate-200 flex flex-col justify-center gap-1 min-w-0";
  card.append(left, right);
  return card;
}

function metricLine(label, text, icon, iconColor) {
  const row = document.createElement("div");
  row.className = "flex items-center gap-1.5 min-w-0";
  const iconNode = document.createElement("i");
  iconNode.className = "ph " + icon + " " + iconColor + " text-sm shrink-0";
  iconNode.setAttribute("aria-hidden", "true");
  const name = document.createElement("p");
  name.className = "text-[10px] font-semibold uppercase tracking-wider text-slate-500 shrink-0";
  name.textContent = label;
  const value = document.createElement("p");
  value.className = "text-sm font-semibold tabular-nums text-slate-900 ml-auto shrink-0";
  value.textContent = text;
  row.append(iconNode, name, value);
  return row;
}

function readingGroup(title, when) {
  const section = document.createElement("section");
  section.className = "flex flex-col gap-2 min-w-0";
  const heading = document.createElement("h3");
  heading.className = "text-xs font-semibold uppercase tracking-wider text-slate-500 flex flex-wrap items-baseline gap-x-1.5";
  const name = document.createElement("span");
  name.textContent = title;
  const date = document.createElement("span");
  date.className = "text-[10px] font-normal normal-case tracking-normal text-slate-400";
  date.textContent = "(" + when + ")";
  heading.append(name, date);
  const list = document.createElement("div");
  list.className = "grid grid-cols-2 gap-2";
  section.append(heading, list);
  return {section: section, list: list};
}

let compassBearing = 0;

function compassWidget(degrees) {
  const known = isNum(degrees);
  const next = known ? ((degrees % 360) + 360) % 360 : compassBearing;
  const previous = compassBearing;
  if (known) compassBearing = next;
  const wrap = document.createElement("div");
  wrap.className = "flex items-center gap-2 shrink-0";
  wrap.innerHTML = '<svg viewBox="0 0 64 64" class="h-16 w-16 shrink-0" role="img">'
    + '<circle cx="32" cy="32" r="30" fill="#fff" stroke="#e2e8f0" stroke-width="1.5"></circle>'
    + '<text x="32" y="11" text-anchor="middle" font-size="8" font-weight="700" fill="#0f172a">N</text>'
    + '<text x="56" y="35" text-anchor="middle" font-size="7" fill="#94a3b8">E</text>'
    + '<text x="32" y="59" text-anchor="middle" font-size="7" fill="#94a3b8">S</text>'
    + '<text x="8" y="35" text-anchor="middle" font-size="7" fill="#94a3b8">W</text>'
    + '<g class="compass-needle">'
    + '<polygon points="32,16 35.2,34 32,31 28.8,34" fill="#e11d48"></polygon>'
    + '<polygon points="32,48 35.2,34 32,37 28.8,34" fill="#cbd5e1"></polygon>'
    + '</g>'
    + '<circle cx="32" cy="32" r="2.4" fill="#0f172a"></circle>'
    + '</svg>'
    + '<div class="min-w-0">'
    + '<p class="text-xs text-slate-500">Wind direction</p>'
    + '<p class="compass-point text-sm font-semibold text-slate-900"></p>'
    + '</div>';
  wrap.querySelector("svg").setAttribute("aria-label", known
    ? "Wind direction " + cardinal(degrees)
    : "Wind direction unavailable");
  wrap.querySelector(".compass-point").textContent = known
    ? cardinal(degrees) + " (" + degreeText(next) + "\u00b0)"
    : "\u2014";
  const needle = wrap.querySelector(".compass-needle");
  needle.style.transform = "rotate(" + previous + "deg)";
  if (known && next !== previous) {
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        needle.style.transform = "rotate(" + next + "deg)";
      });
    });
  }
  return wrap;
}

function cardEntries(group) {
  const entries = [];
  for (const spec of CHARTS) {
    for (const series of spec.series) {
      if (series.card && series.card.group === group) entries.push({spec: spec, series: series});
    }
  }
  return entries;
}

function readingText(row, entry) {
  return measure(row, entry.series.key, seriesDigits(entry.spec, entry.series), cardUnit(entry.spec, entry.series));
}

function lineFor(row, entry) {
  return metricLine(entry.series.card.label, readingText(row, entry), entry.series.card.icon, entry.series.card.color);
}

function appendWind(list, entries, row) {
  const compass = entries.find((entry) => entry.series.card.present === "compass");
  const lines = entries.filter((entry) => entry.series.card.present === "line");
  if (!compass && !lines.length) return;
  const wind = document.createElement("div");
  wind.className = "col-span-2 bg-white px-3 py-2.5 rounded-xl shadow-sm border border-slate-200 flex items-center gap-3 min-w-0";
  const stats = document.createElement("div");
  stats.className = "flex flex-col gap-1 flex-1 min-w-0";
  for (const entry of lines) stats.append(lineFor(row, entry));
  if (compass) wind.append(compassWidget(row[compass.series.key]), stats);
  else wind.append(stats);
  list.append(wind);
}

function appendPairs(list, entries, row) {
  const pairs = new Map();
  for (const entry of entries) {
    if (entry.series.card.present !== "pair") continue;
    const bucket = pairs.get(entry.series.card.pair) || [];
    bucket.push(entry);
    pairs.set(entry.series.card.pair, bucket);
  }
  for (const bucket of pairs.values()) {
    list.append(compactPair(lineFor(row, bucket[0]), lineFor(row, bucket[1]), bucket.some((entry) => entry.series.card.wide)));
  }
}

function appendBoxes(list, entries, row) {
  for (const entry of entries) {
    const present = entry.series.card.present || "box";
    if (present !== "box") continue;
    const card = entry.series.card;
    list.append(metricBox(card.label, readingText(row, entry), card.icon, card.color));
  }
}

function appendRain(list, entries, row, records, body) {
  const event = entries.find((entry) => entry.series.key === "eventrainin");
  list.append(compactPair(
    metricLine("Last event date", stampText(row.lastRain), "ph-clock", "text-slate-500"),
    lineFor(row, event),
    true
  ));
  const rain = rainInView(records, {from: body.from, to: body.to});
  for (const rate of RAIN_RATES) {
    list.append(metricBox(rate.label, inches(rain[rate.key]), rate.icon, rate.color));
  }
}

export function renderLatest(body) {
  const records = body.records || [];
  const row = records.length ? records[records.length - 1] : {};
  const when = stampText(row.dateutc);
  document.getElementById("updated").textContent = "Updated " + when;
  const sections = GROUPS.map((group) => {
    const built = readingGroup(group.title, group.range ? loadedRangeText(body) : when);
    const entries = cardEntries(group.id);
    if (group.id === "rain") appendRain(built.list, entries, row, records, body);
    else {
      appendWind(built.list, entries, row);
      appendBoxes(built.list, entries, row);
      appendPairs(built.list, entries, row);
    }
    return built.section;
  });
  document.getElementById("latest-groups").replaceChildren(...sections);
}

import {formatWhen} from "./dashboard-series.js";

const filterButton = document.getElementById("filter-value");
const filterLabelNode = document.getElementById("filter-label");
const filterMenu = document.getElementById("filter-menu");
const lastCount = document.getElementById("last-count");
const lastUnit = document.getElementById("last-unit");
const fromInput = document.getElementById("from");
const toInput = document.getElementById("to");
const backButton = document.getElementById("back");
const resetRow = document.getElementById("reset-row");
const UNITS = ["seconds", "minutes", "hours", "days", "months", "years"];
const UNIT_SINGULAR = {
  seconds: "second",
  minutes: "minute",
  hours: "hour",
  days: "day",
  months: "month",
  years: "year"
};

let filter = {kind: "last", count: 24, unit: "hours", from: "", to: ""};
const backStack = [];

function pad(number) {
  return String(number).padStart(2, "0");
}

function toLocalInput(date) {
  return date.getFullYear() + "-" + pad(date.getMonth() + 1) + "-" + pad(date.getDate())
    + "T" + pad(date.getHours()) + ":" + pad(date.getMinutes()) + ":" + pad(date.getSeconds());
}

export function toUtcParam(localValue) {
  const date = new Date(localValue);
  if (isNaN(date.getTime())) throw new Error("Enter a valid date range.");
  return date.toISOString().replace(/\.\d{3}Z$/, "Z");
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

export function updateFilterLabel() {
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

function copyFilter(value) {
  return {kind: value.kind, count: value.count, unit: value.unit, from: value.from, to: value.to};
}

function stepFilter(which) {
  const next = copyFilter(filter);
  if (next.kind === "last") {
    const index = UNITS.indexOf(next.unit);
    if (which === "amount-down") next.count -= 1;
    else if (which === "amount-up") next.count += 1;
    else if (which === "unit-down") next.unit = UNITS[index - 1];
    else if (which === "unit-up") next.unit = UNITS[index + 1];
    if (!next.unit || next.count < 1) return false;
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
  if (next.kind === "range" && new Date(next.from) > new Date(next.to)) return false;
  filter = next;
  updateFilterLabel();
  closeMenu();
  return true;
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

export function currentBounds() {
  if (filter.kind === "range") return {from: filter.from, to: filter.to};
  const end = new Date();
  const start = subtractUnit(end, filter.count, filter.unit);
  return {from: toLocalInput(start), to: toLocalInput(end)};
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

function syncMenu(body) {
  lastCount.value = String(filter.count || 24);
  lastUnit.value = filter.unit || "hours";
  if (filter.kind === "range") {
    fromInput.value = filter.from;
    toInput.value = filter.to;
  } else if (body && body.from && body.to) {
    fromInput.value = toLocalInput(new Date(body.from));
    toInput.value = toLocalInput(new Date(body.to));
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

function openMenu(body) {
  syncMenu(body);
  filterMenu.hidden = false;
  filterButton.setAttribute("aria-expanded", "true");
  placeMenu();
}

function closeMenu() {
  filterMenu.hidden = true;
  filterButton.setAttribute("aria-expanded", "false");
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

export function applyZoom(chart, body) {
  const min = chart.scales.x.min;
  const max = chart.scales.x.max;
  const domain = chart.$domain || {min: min, max: max};
  if (!(max > min)) {
    chart.resetZoom();
    return false;
  }
  if (Math.abs(min - domain.min) < 1000 && Math.abs(max - domain.max) < 1000) {
    chart.resetZoom();
    return false;
  }
  const nextFrom = toLocalInput(new Date(min));
  const nextTo = toLocalInput(new Date(max));
  const loadedFrom = body ? toLocalInput(new Date(body.from)) : "";
  const loadedTo = body ? toLocalInput(new Date(body.to)) : "";
  if (nextFrom === loadedFrom && nextTo === loadedTo) {
    chart.resetZoom();
    return false;
  }
  backStack.push(copyFilter(filter));
  resetRow.hidden = false;
  filter = {kind: "range", count: filter.count, unit: filter.unit, from: nextFrom, to: nextTo};
  updateFilterLabel();
  closeMenu();
  return true;
}

function resetFilter() {
  const original = backStack[0];
  backStack.length = 0;
  resetRow.hidden = true;
  if (!original) return false;
  filter = original;
  updateFilterLabel();
  closeMenu();
  return true;
}

export function bindRange(getBody, onChange) {
  filterButton.addEventListener("click", () => {
    if (filterMenu.hidden) openMenu(getBody());
    else closeMenu();
  });

  filterMenu.addEventListener("submit", (event) => {
    event.preventDefault();
    try {
      filter = readMenuFilter();
    } catch (error) {
      onChange(error);
      return;
    }
    closeMenu();
    updateFilterLabel();
    onChange(null);
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
    if (resetFilter()) onChange(null);
  });

  document.querySelector(".stepper").addEventListener("click", (event) => {
    const button = event.target.closest("button[data-step]");
    if (!button || button.disabled) return;
    if (stepFilter(button.dataset.step)) onChange(null);
  });
}

(function () {
const jsonHeaders = {"Content-Type": "application/json", Accept: "application/json"};
const FAN = [
  ["use_fan", "Use fan"],
  ["min_temp_gain", "Min temp gain"],
  ["max_temp_loss", "Max temp loss"],
  ["end_fan_after", "End fan after"],
  ["cycle_end_max_temp_loss", "Cycle end max temp loss"]
];

let errorNode;
let errorMsg;
let deviceInput;
let cards;
let intervalSeconds;
let intervalError;
let generalPanel;
let routinesPanel;
let generalTab;
let routinesTab;

function showError(message) {
  errorNode.hidden = false;
  errorMsg.textContent = message;
}

function clearError() {
  errorNode.hidden = true;
  errorMsg.textContent = "";
}

function showIntervalError(message) {
  intervalError.hidden = false;
  intervalError.textContent = message;
}

async function readJson(response) {
  const body = await response.json();
  if (!response.ok) {
    const detail = body && body.error ? " " + body.error : "";
    throw new Error("Request failed (" + response.status + ")." + detail);
  }
  return body;
}

function field(className) {
  const input = document.createElement("input");
  input.className = className + " px-2 py-1 text-sm border border-slate-300 rounded-md focus:ring-2 focus:ring-brand-500 focus:border-brand-500 outline-none";
  return input;
}

function bandRow(hour, band) {
  const row = document.createElement("div");
  row.className = "grid grid-cols-[5rem_1fr_1fr_auto] gap-2 items-center";
  row.dataset.band = "true";
  const hourInput = field("w-full");
  hourInput.type = "number";
  hourInput.min = "0";
  hourInput.max = "23";
  hourInput.step = "1";
  hourInput.required = true;
  hourInput.dataset.field = "hour";
  hourInput.value = hour;
  hourInput.setAttribute("aria-label", "Hour");
  const minInput = field("w-full");
  minInput.type = "number";
  minInput.step = "any";
  minInput.required = true;
  minInput.dataset.field = "min";
  minInput.value = band ? band.min : "";
  minInput.setAttribute("aria-label", "Minimum");
  const maxInput = field("w-full");
  maxInput.type = "number";
  maxInput.step = "any";
  maxInput.required = true;
  maxInput.dataset.field = "max";
  maxInput.value = band ? band.max : "";
  maxInput.setAttribute("aria-label", "Maximum");
  const remove = document.createElement("button");
  remove.type = "button";
  remove.className = "p-1.5 text-slate-500 hover:text-red-700 hover:bg-red-50 rounded-md";
  remove.setAttribute("aria-label", "Remove hour");
  remove.innerHTML = '<i class="ph ph-trash" aria-hidden="true"></i>';
  remove.addEventListener("click", () => row.remove());
  row.append(hourInput, minInput, maxInput, remove);
  return row;
}

function finiteNumber(input) {
  const text = input.value.trim();
  if (text === "") return null;
  const value = Number(text);
  if (!Number.isFinite(value)) return null;
  return value;
}

function collectBands(form) {
  const temps = {};
  const rows = form.querySelectorAll("[data-band]");
  if (!rows.length) return {error: "Add at least one hour."};
  for (const row of rows) {
    const hour = finiteNumber(row.querySelector("[data-field=hour]"));
    const min = finiteNumber(row.querySelector("[data-field=min]"));
    const max = finiteNumber(row.querySelector("[data-field=max]"));
    if (hour === null || !Number.isInteger(hour) || hour < 0 || hour > 23) {
      return {error: "Hours must be whole numbers from 0 to 23."};
    }
    if (Object.prototype.hasOwnProperty.call(temps, String(hour))) {
      return {error: "Hour " + hour + " is listed twice."};
    }
    if (min === null || max === null || min > max) {
      return {error: "Each minimum must be a number less than or equal to its maximum."};
    }
    temps[String(hour)] = {min: min, max: max};
  }
  return {temps: temps};
}

function fanValue(form, name) {
  const input = form.querySelector("[data-fan='" + name + "']");
  if (name === "use_fan") return input.checked;
  const value = finiteNumber(input);
  if (value === null || !Number.isInteger(value)) return null;
  return value;
}

function renderCard(routine) {
  const form = document.createElement("form");
  form.className = "bg-white rounded-xl shadow-sm border border-slate-200 p-4 sm:p-5 flex flex-col gap-3";
  if (routine.active) form.classList.add("ring-2", "ring-brand-500");

  const header = document.createElement("div");
  header.className = "flex flex-wrap items-start justify-between gap-2";
  const titleWrap = document.createElement("div");
  titleWrap.className = "min-w-0";
  const title = document.createElement("h2");
  title.className = "text-sm font-semibold text-slate-900 font-mono";
  title.textContent = routine.name;
  const summary = document.createElement("p");
  summary.className = "mt-1 text-sm text-slate-600";
  summary.textContent = routine.summary;
  const path = document.createElement("p");
  path.className = "mt-1 text-xs text-slate-400 font-mono break-all";
  path.textContent = routine.path;
  titleWrap.append(title, summary, path);
  header.append(titleWrap);
  if (routine.active) {
    const badge = document.createElement("span");
    badge.className = "px-2 py-0.5 text-xs font-semibold rounded-md bg-slate-900 text-white";
    badge.textContent = "Active";
    header.append(badge);
    form.setAttribute("aria-current", "true");
  } else {
    const activate = document.createElement("button");
    activate.type = "button";
    activate.className = "px-3 py-1.5 text-sm font-medium text-slate-700 bg-white border border-slate-200 rounded-lg hover:bg-slate-50";
    activate.textContent = "Activate";
    activate.addEventListener("click", () => activateRoutine(routine.name));
    header.append(activate);
  }

  const bands = document.createElement("div");
  bands.className = "flex flex-col gap-2";
  const labels = document.createElement("div");
  labels.className = "grid grid-cols-[5rem_1fr_1fr_auto] gap-2 text-xs font-medium text-slate-500";
  for (const text of ["Hour", "Min", "Max", ""]) {
    const span = document.createElement("span");
    span.textContent = text;
    labels.append(span);
  }
  bands.append(labels);
  const hours = Object.keys(routine.temps).sort((a, b) => Number(a) - Number(b));
  for (const hour of hours) bands.append(bandRow(hour, routine.temps[hour]));

  const add = document.createElement("button");
  add.type = "button";
  add.className = "self-start px-3 py-1.5 text-sm font-medium text-slate-600 hover:text-slate-900";
  add.textContent = "Add hour";
  add.addEventListener("click", () => bands.append(bandRow("", null)));

  const fan = document.createElement("div");
  fan.className = "grid grid-cols-1 sm:grid-cols-2 gap-3";
  for (const [name, labelText] of FAN) {
    const label = document.createElement("label");
    label.className = "flex flex-col gap-1 text-xs font-medium text-slate-600";
    label.textContent = labelText;
    if (name === "use_fan") {
      const input = document.createElement("input");
      input.type = "checkbox";
      input.dataset.fan = name;
      input.checked = Boolean(routine.use_fan);
      input.className = "mt-1 rounded text-brand-500 focus:ring-brand-500";
      label.append(input);
    } else {
      const input = field("");
      input.type = "number";
      input.step = "1";
      input.required = true;
      input.dataset.fan = name;
      input.value = routine[name];
      label.append(input);
    }
    fan.append(label);
  }

  const cardError = document.createElement("p");
  cardError.dataset.error = "true";
  cardError.className = "text-sm font-medium text-red-700";
  cardError.hidden = true;

  const save = document.createElement("button");
  save.type = "submit";
  save.className = "self-end px-4 py-2 bg-slate-900 text-white text-sm font-medium rounded-lg hover:bg-slate-800";
  save.textContent = "Save bands";

  form.append(header, bands, add, fan, cardError, save);
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    saveBands(form, routine.name, cardError);
  });
  return form;
}

function render(body) {
  if (document.activeElement !== deviceInput) deviceInput.value = body.device_id;
  cards.replaceChildren();
  for (const routine of body.routines) cards.append(renderCard(routine));
}

async function loadRoutines() {
  const response = await fetch("/routines", {headers: {Accept: "application/json"}});
  const body = await readJson(response);
  if (!Array.isArray(body.routines)) throw new Error("Routine response was not a list.");
  clearError();
  render(body);
}

async function activateRoutine(name) {
  try {
    clearError();
    await readJson(await fetch("/routines/active", {
      method: "POST",
      headers: jsonHeaders,
      body: JSON.stringify({routine: name})
    }));
    await loadRoutines();
  } catch (error) {
    showError(error.message || "Could not activate that routine.");
  }
}

async function saveBands(form, name, cardError) {
  cardError.hidden = true;
  const bands = collectBands(form);
  if (bands.error) {
    cardError.hidden = false;
    cardError.textContent = bands.error;
    showError(bands.error);
    return;
  }
  const payload = {temps: bands.temps};
  for (const [fieldName] of FAN) {
    const value = fanValue(form, fieldName);
    if (value === null) {
      const message = "Fan fields must be whole numbers.";
      cardError.hidden = false;
      cardError.textContent = message;
      showError(message);
      return;
    }
    payload[fieldName] = value;
  }
  try {
    clearError();
    await readJson(await fetch("/routines/" + encodeURIComponent(name), {
      method: "PUT",
      headers: jsonHeaders,
      body: JSON.stringify(payload)
    }));
    await loadRoutines();
  } catch (error) {
    cardError.hidden = false;
    cardError.textContent = error.message || "Could not save bands.";
    showError(cardError.textContent);
  }
}

async function loadInterval() {
  intervalError.hidden = true;
  const response = await fetch("/config/history-interval", {headers: {Accept: "application/json"}});
  if (!response.ok) throw new Error("Could not load the interval (" + response.status + ")");
  const body = await response.json();
  if (!Number.isInteger(body.weather_history_interval) || body.weather_history_interval < 0) {
    throw new Error("Interval response was not a whole number of seconds.");
  }
  intervalSeconds.value = String(body.weather_history_interval);
}

function tabClass(selected) {
  return "px-3 py-1 text-sm font-medium rounded-md " + (selected
    ? "bg-white shadow-sm text-slate-900"
    : "text-slate-600 hover:text-slate-900");
}

function selectTab(name) {
  const general = name === "general";
  generalPanel.hidden = !general;
  routinesPanel.hidden = general;
  generalTab.setAttribute("aria-selected", general ? "true" : "false");
  routinesTab.setAttribute("aria-selected", general ? "false" : "true");
  generalTab.className = tabClass(general);
  routinesTab.className = tabClass(!general);
  if (!general) loadRoutines().catch((error) => showError(error.message || "Could not load routines."));
}

function buildDialog() {
  const style = document.createElement("style");
  style.textContent = "#settings-dialog{border:0;padding:0}#settings-dialog::backdrop{background:rgb(15 23 42 / 0.45)}";
  document.head.append(style);

  const dialog = document.createElement("dialog");
  dialog.id = "settings-dialog";
  dialog.className = "rounded-2xl shadow-xl border border-slate-200 w-[min(72rem,calc(100vw-2rem))]";
  dialog.setAttribute("aria-labelledby", "settings-title");

  const shell = document.createElement("div");
  shell.className = "flex flex-col max-h-[calc(100vh-2rem)]";

  const top = document.createElement("div");
  top.className = "flex items-center justify-between gap-3 px-5 pt-5";
  const title = document.createElement("h2");
  title.id = "settings-title";
  title.className = "text-lg font-semibold text-slate-900";
  title.textContent = "Settings";
  const close = document.createElement("button");
  close.type = "button";
  close.className = "p-1.5 text-slate-500 hover:text-slate-900 hover:bg-slate-100 rounded-md";
  close.setAttribute("aria-label", "Close");
  close.innerHTML = '<i class="ph ph-x text-lg" aria-hidden="true"></i>';
  close.addEventListener("click", () => dialog.close());
  top.append(title, close);

  const tablist = document.createElement("div");
  tablist.className = "px-5 pt-3";
  tablist.setAttribute("role", "tablist");
  tablist.setAttribute("aria-label", "Settings");
  const tabs = document.createElement("div");
  tabs.className = "inline-flex p-1 bg-slate-100 rounded-lg";
  generalTab = document.createElement("button");
  generalTab.type = "button";
  generalTab.id = "settings-tab-general";
  generalTab.setAttribute("role", "tab");
  generalTab.setAttribute("aria-controls", "settings-panel-general");
  generalTab.textContent = "General";
  routinesTab = document.createElement("button");
  routinesTab.type = "button";
  routinesTab.id = "settings-tab-routines";
  routinesTab.setAttribute("role", "tab");
  routinesTab.setAttribute("aria-controls", "settings-panel-routines");
  routinesTab.textContent = "Routines";
  generalTab.addEventListener("click", () => selectTab("general"));
  routinesTab.addEventListener("click", () => selectTab("routines"));
  tabs.append(generalTab, routinesTab);
  tablist.append(tabs);

  generalPanel = document.createElement("div");
  generalPanel.id = "settings-panel-general";
  generalPanel.setAttribute("role", "tabpanel");
  generalPanel.className = "overflow-auto p-5";
  const form = document.createElement("form");
  form.id = "interval-form";
  form.className = "flex flex-col gap-4 max-w-md";
  const hint = document.createElement("p");
  hint.className = "text-sm text-slate-500";
  hint.textContent = "Seconds between Ambient history passes. Use a whole number, 0 or greater. The collector reads it on the next pass.";
  const label = document.createElement("label");
  label.className = "flex flex-col gap-1 text-sm font-medium text-slate-700";
  label.htmlFor = "interval-seconds";
  label.append("Seconds");
  intervalSeconds = document.createElement("input");
  intervalSeconds.id = "interval-seconds";
  intervalSeconds.type = "number";
  intervalSeconds.min = "0";
  intervalSeconds.step = "1";
  intervalSeconds.inputMode = "numeric";
  intervalSeconds.required = true;
  intervalSeconds.className = "px-3 py-1.5 text-sm border border-slate-300 rounded-md focus:ring-2 focus:ring-brand-500 focus:border-brand-500 outline-none";
  label.append(intervalSeconds);
  intervalError = document.createElement("p");
  intervalError.id = "interval-error";
  intervalError.className = "text-sm font-medium text-red-700";
  intervalError.hidden = true;
  const saveRow = document.createElement("div");
  const saveInterval = document.createElement("button");
  saveInterval.type = "submit";
  saveInterval.className = "px-4 py-2 bg-slate-900 text-white text-sm font-medium rounded-lg hover:bg-slate-800";
  saveInterval.textContent = "Save";
  saveRow.append(saveInterval);
  form.append(hint, label, intervalError, saveRow);
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    intervalError.hidden = true;
    const value = Number(intervalSeconds.value);
    if (!Number.isInteger(value) || value < 0) {
      showIntervalError("Enter a whole number of seconds, 0 or greater.");
      return;
    }
    try {
      const response = await fetch("/config/history-interval", {
        method: "POST",
        headers: jsonHeaders,
        body: JSON.stringify({weather_history_interval: value})
      });
      if (!response.ok) throw new Error("Save failed (" + response.status + ").");
      const body = await response.json();
      if (body.weather_history_interval !== value) throw new Error("Save did not keep that interval.");
    } catch (error) {
      showIntervalError(error.message || "Save failed.");
    }
  });
  generalPanel.append(form);

  routinesPanel = document.createElement("div");
  routinesPanel.id = "settings-panel-routines";
  routinesPanel.setAttribute("role", "tabpanel");
  routinesPanel.className = "overflow-auto p-5 flex flex-col gap-4";
  errorNode = document.createElement("p");
  errorNode.id = "settings-error";
  errorNode.className = "bg-red-50 text-red-700 px-4 py-3 rounded-lg border border-red-100 text-sm font-medium";
  errorNode.hidden = true;
  errorMsg = document.createElement("span");
  errorNode.append(errorMsg);

  const device = document.createElement("section");
  device.className = "bg-white rounded-xl shadow-sm border border-slate-200 p-4";
  device.setAttribute("aria-label", "Device");
  const deviceTitle = document.createElement("h3");
  deviceTitle.className = "text-sm font-semibold text-slate-900";
  deviceTitle.textContent = "Device";
  const deviceHint = document.createElement("p");
  deviceHint.className = "mt-1 text-sm text-slate-500";
  deviceHint.textContent = "Saving a new device id restarts thermostat control.";
  const deviceForm = document.createElement("form");
  deviceForm.className = "mt-3 flex flex-wrap items-end gap-3";
  const deviceLabel = document.createElement("label");
  deviceLabel.className = "flex flex-col gap-1 text-sm font-medium text-slate-700 flex-1 min-w-[16rem]";
  deviceLabel.htmlFor = "device-id";
  deviceLabel.append("Device id");
  deviceInput = document.createElement("input");
  deviceInput.id = "device-id";
  deviceInput.autocomplete = "off";
  deviceInput.spellcheck = false;
  deviceInput.required = true;
  deviceInput.className = "px-3 py-1.5 text-sm border border-slate-300 rounded-md focus:ring-2 focus:ring-brand-500 focus:border-brand-500 outline-none font-mono";
  deviceLabel.append(deviceInput);
  const deviceSave = document.createElement("button");
  deviceSave.type = "submit";
  deviceSave.className = "px-4 py-2 bg-slate-900 text-white text-sm font-medium rounded-lg hover:bg-slate-800";
  deviceSave.textContent = "Save device";
  deviceForm.append(deviceLabel, deviceSave);
  deviceForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const deviceId = deviceInput.value.trim();
    if (!deviceId) {
      showError("Device id is required.");
      return;
    }
    try {
      clearError();
      await readJson(await fetch("/routines/device", {
        method: "POST",
        headers: jsonHeaders,
        body: JSON.stringify({device_id: deviceId})
      }));
      await loadRoutines();
    } catch (error) {
      showError(error.message || "Could not save the device id.");
    }
  });
  device.append(deviceTitle, deviceHint, deviceForm);

  cards = document.createElement("div");
  cards.id = "cards";
  cards.className = "grid grid-cols-1 xl:grid-cols-2 gap-4";
  cards.setAttribute("aria-label", "Routines");
  routinesPanel.append(errorNode, device, cards);

  shell.append(top, tablist, generalPanel, routinesPanel);
  dialog.append(shell);
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) dialog.close();
  });
  return dialog;
}

const settingsOpen = document.getElementById("settings-open");
if (settingsOpen) {
  const dialog = buildDialog();
  document.body.append(dialog);
  selectTab("general");
  settingsOpen.addEventListener("click", () => {
    selectTab("general");
    dialog.showModal();
    loadInterval().catch((error) => showIntervalError(error.message || "Could not load the interval."));
  });
}
})();

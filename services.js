const POLL_MS = 2000;
const panels = new Map();
const root = document.getElementById("panels");
const errorNode = document.getElementById("error");
const errorMsg = document.getElementById("error-msg");

function showError(error) {
  errorNode.hidden = false;
  errorMsg.textContent = error.message || "Could not load logs.";
}

function panelFor(name) {
  const existing = panels.get(name);
  if (existing) return existing;
  const section = document.createElement("section");
  section.className = "bg-white rounded-xl shadow-sm border border-slate-200 flex flex-col min-h-[16rem]";
  const header = document.createElement("h2");
  header.className = "px-4 py-3 text-sm font-semibold text-slate-800 border-b border-slate-200 font-mono";
  header.textContent = name;
  const pre = document.createElement("pre");
  pre.className = "flex-1 m-0 p-4 text-xs leading-5 text-slate-100 bg-slate-900 overflow-auto max-h-[24rem] whitespace-pre-wrap break-all";
  pre.textContent = "No lines yet.";
  section.append(header, pre);
  root.append(section);
  const panel = {pre: pre, text: "No lines yet."};
  panels.set(name, panel);
  return panel;
}

function render(loggers) {
  for (const logger of loggers) {
    const panel = panelFor(logger.name);
    const text = logger.lines.length ? logger.lines.join("\n") : "No lines yet.";
    if (text === panel.text) continue;
    const box = panel.pre;
    const atBottom = box.scrollHeight - box.scrollTop - box.clientHeight < 40;
    box.textContent = text;
    panel.text = text;
    if (atBottom) box.scrollTop = box.scrollHeight;
  }
}

async function load() {
  const response = await fetch("/services/logs");
  if (!response.ok) throw new Error("Log request failed (" + response.status + ")");
  const body = await response.json();
  if (!Array.isArray(body.loggers)) throw new Error("Log response was not a list.");
  errorNode.hidden = true;
  render(body.loggers);
}

async function tick() {
  try {
    await load();
  } catch (error) {
    showError(error);
  }
  setTimeout(tick, POLL_MS);
}

tick();

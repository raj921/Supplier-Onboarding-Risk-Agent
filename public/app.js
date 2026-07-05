const fields = ["supplier_packet", "procurement_policy", "vendor_history", "late_correction"];
const commandForm = document.getElementById("terminal-form");
const commandInput = document.getElementById("terminal-command");
const commandButtons = [...document.querySelectorAll("[data-command]")];
const terminalLog = document.getElementById("terminal-log");
const statusPill = document.getElementById("status-pill");
const connectionStatus = document.getElementById("connection-status");
const timeline = document.getElementById("timeline");
const proofJson = document.getElementById("proof-json");
const resetDocsButton = document.getElementById("reset-docs");

const history = [];
let samples = {};
let historyIndex = 0;
let running = false;

function appendEntry(kind, text) {
  const entry = document.createElement("pre");
  entry.className = `terminal-entry ${kind}`;
  entry.textContent = text;
  terminalLog.appendChild(entry);
  terminalLog.scrollTop = terminalLog.scrollHeight;
}

function setBusy(command) {
  running = true;
  statusPill.textContent = "running";
  connectionStatus.textContent = "running";
  commandInput.disabled = true;
  commandButtons.forEach((button) => {
    button.disabled = true;
  });
  appendEntry("command", `$ ${command}`);
  appendEntry("pending", "running on Railway...");
}

function clearBusy(ok) {
  running = false;
  statusPill.textContent = ok ? "idle" : "failed";
  connectionStatus.textContent = ok ? "ready" : "check output";
  commandInput.disabled = false;
  commandButtons.forEach((button) => {
    button.disabled = false;
  });
}

function removePending() {
  const pending = terminalLog.querySelector(".terminal-entry.pending:last-child");
  if (pending) {
    pending.remove();
  }
}

function writeTimeline(items) {
  timeline.innerHTML = "";
  const lines = items.length ? items : ["No proof trace from this command."];
  for (const item of lines) {
    const li = document.createElement("li");
    li.textContent = item;
    timeline.appendChild(li);
  }
}

function updateProof(data) {
  document.getElementById("score-before").textContent = data.proof?.scoreBefore ?? 0;
  document.getElementById("score-after").textContent = data.proof?.scoreAfter ?? 0;
  document.getElementById("risk-delta").textContent = `+${data.proof?.riskDelta ?? 0}`;
  document.getElementById("verdict").textContent = data.proof?.verdict ?? "review";
  document.getElementById("hero-verdict").textContent = data.proof?.verdict ?? "review";
  proofJson.textContent = JSON.stringify(data.proofJson || {}, null, 2);
  writeTimeline(data.timeline || []);
}

function rememberCommand(command) {
  if (!command || command === history[history.length - 1]) {
    historyIndex = history.length;
    return;
  }
  history.push(command);
  historyIndex = history.length;
}

async function runCommand(command) {
  const cleanCommand = command.trim();
  if (!cleanCommand || running) {
    return;
  }

  if (cleanCommand === "clear") {
    terminalLog.innerHTML = "";
    rememberCommand(cleanCommand);
    commandInput.value = "";
    return;
  }

  rememberCommand(cleanCommand);
  setBusy(cleanCommand);

  try {
    const response = await fetch("/api/terminal", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        command: cleanCommand,
        documents: collectDocuments(),
      }),
    });
    const data = await response.json().catch(() => ({}));
    removePending();

    if (!response.ok) {
      throw new Error(data.detail || "Terminal request failed.");
    }

    const suffix = `\n\nexit ${data.exitCode} in ${data.durationSeconds}s`;
    appendEntry(data.ok ? "output" : "error", `${data.output || ""}${suffix}`);
    updateProof(data);
    clearBusy(data.ok);
  } catch (error) {
    removePending();
    const message = error instanceof Error ? error.message : String(error);
    appendEntry("error", `${message}\n\nexit 1`);
    clearBusy(false);
  }
}

async function loadSamples() {
  const response = await fetch("/api/sample-data");
  samples = await response.json();
  resetDocuments();
}

function collectDocuments() {
  const documents = {};
  for (const name of fields) {
    documents[name] = document.getElementById(name).value;
  }
  return documents;
}

function resetDocuments() {
  for (const name of fields) {
    document.getElementById(name).value = samples[name] || "";
  }
  appendEntry("output", "Sample documents restored in the editor.");
}

commandForm.addEventListener("submit", (event) => {
  event.preventDefault();
  runCommand(commandInput.value);
});

commandInput.addEventListener("keydown", (event) => {
  if (event.key === "ArrowUp") {
    event.preventDefault();
    historyIndex = Math.max(0, historyIndex - 1);
    commandInput.value = history[historyIndex] || commandInput.value;
  }
  if (event.key === "ArrowDown") {
    event.preventDefault();
    historyIndex = Math.min(history.length, historyIndex + 1);
    commandInput.value = history[historyIndex] || "";
  }
});

for (const button of commandButtons) {
  button.addEventListener("click", () => {
    commandInput.value = button.dataset.command;
    runCommand(button.dataset.command);
  });
}

resetDocsButton.addEventListener("click", resetDocuments);

terminalLog.innerHTML = "";
appendEntry("output", "Hosted terminal ready. Only supplier-memory-radar commands are accepted.");
loadSamples().then(() => runCommand("supplier-memory-radar analyze"));

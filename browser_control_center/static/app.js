const state = {
  summary: null,
  lastSmokeResult: null,
};

// These ready-made payloads let a beginner explore the API without first having
// to invent valid requests from memory.
const httpApiSamples = {
  health: {
    method: "GET",
    path: "/api/v1/health",
    body: "",
  },
  validate2d: {
    method: "POST",
    path: "/api/v1/scene/validate",
    body: JSON.stringify(
      {
        sceneType: "2d",
        primitive: "triangles",
        vertices: [
          { x: -1.0, y: -1.0, r: 1.0, g: 0.0, b: 0.0, a: 1.0 },
          { x: 0.0, y: 1.0, r: 0.0, g: 1.0, b: 0.0, a: 1.0 },
          { x: 1.0, y: -1.0, r: 0.0, g: 0.0, b: 1.0, a: 1.0 },
        ],
      },
      null,
      2
    ),
  },
  post3d: {
    method: "POST",
    path: "/api/v1/scene",
    body: JSON.stringify(
      {
        sceneType: "3d",
        primitive: "triangles",
        camera: {
          position: { x: 2.5, y: 2.0, z: 2.8 },
          target: { x: 0.0, y: 0.0, z: 0.0 },
          up: { x: 0.0, y: 1.0, z: 0.0 },
          fovYDegrees: 60.0,
          nearPlane: 0.1,
          farPlane: 100.0,
        },
        vertices: [
          { x: -0.8, y: -0.8, z: 0.0, r: 1.0, g: 0.2, b: 0.2 },
          { x: 0.8, y: -0.8, z: 0.0, r: 0.2, g: 1.0, b: 0.2 },
          { x: 0.0, y: 0.8, z: 0.0, r: 0.2, g: 0.4, b: 1.0 },
        ],
        indices: [0, 1, 2],
      },
      null,
      2
    ),
  },
};

function setTheme(nextTheme) {
  document.body.setAttribute("data-theme", nextTheme);
  localStorage.setItem("halcyn-control-center-theme", nextTheme);
}

async function postJson(requestUrl, requestPayload = {}) {
  const response = await fetch(requestUrl, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(requestPayload),
  });
  return response.json();
}

function renderTools(availableTools) {
  const container = document.getElementById("tool-grid");
  container.innerHTML = "";

  // The tool cards are generated from the server summary so the browser does not
  // need to know in advance which tools exist or how many there are.
  for (const [name, details] of Object.entries(availableTools)) {
    const card = document.createElement("div");
    card.className = "tool-card";
    card.innerHTML = `
      <strong>${name}</strong>
      <span class="status-pill ${details.available ? "status-running" : "status-stopped"}">
        ${details.available ? "Available" : "Missing"}
      </span>
      <div class="muted">${details.path || "No path detected"}</div>
    `;
    container.appendChild(card);
  }
}

function renderAppSummary(managedApplication) {
  document.getElementById("app-status-pill").textContent = managedApplication.status;
  document.getElementById("app-status-pill").className = `status-pill status-${managedApplication.status}`;

  const summaryContainer = document.getElementById("app-summary");
  const processIdentifier = managedApplication.pid ?? "Not running";
  summaryContainer.innerHTML = `
    <div><strong>Status</strong><span>${managedApplication.status}</span></div>
    <div><strong>PID</strong><span>${processIdentifier}</span></div>
    <div><strong>Started</strong><span>${managedApplication.started_at_utc ?? "N/A"}</span></div>
    <div><strong>Stopped</strong><span>${managedApplication.stopped_at_utc ?? "N/A"}</span></div>
    <div><strong>Command</strong><span>${(managedApplication.command || []).join(" ") || "N/A"}</span></div>
  `;

  const output = document.getElementById("app-output");
  output.textContent =
    (managedApplication.output_lines || []).join("\n") || "The app is not running.";
}

function renderJobs(backgroundJobs) {
  const container = document.getElementById("job-list");
  container.innerHTML = "";

  if (!backgroundJobs.length) {
    container.innerHTML = `<div class="response-panel empty-state">No jobs have been started yet.</div>`;
    return;
  }

  // Newest jobs are shown first because that matches the "what just happened?"
  // question users usually ask when looking at a build/test dashboard.
  for (const job of [...backgroundJobs].reverse()) {
    const card = document.createElement("div");
    card.className = "job-card";
    card.innerHTML = `
      <div class="button-row">
        <strong>${job.kind}</strong>
        <span class="status-pill status-${job.status}">${job.status}</span>
      </div>
      <div class="stack-list">
        <div><strong>Job ID</strong><span>${job.job_id}</span></div>
        <div><strong>Started</strong><span>${job.started_at_utc || "Queued"}</span></div>
        <div><strong>Finished</strong><span>${job.finished_at_utc || "Still running"}</span></div>
        <div><strong>Command</strong><span>${job.command.join(" ")}</span></div>
      </div>
      <pre>${(job.output_lines || []).join("\n") || "No output yet."}</pre>
    `;
    container.appendChild(card);
  }
}

function renderLogs(logEntries) {
  const target = document.getElementById("control-center-logs");
  target.textContent = logEntries
    .map((entry) => `[${entry.timestamp_utc}] [${entry.level}] [${entry.component}] ${entry.message}`)
    .join("\n");
}

function renderDocs(documentationLinks) {
  const container = document.getElementById("docs-links");
  container.innerHTML = "";

  // The server sends a plain map of documentation routes. The browser adds the
  // human-friendly labels so docs organization can evolve without hard-coding HTML.
  const documentationLabels = {
    overview: "Overview",
    tutorial: "Tutorial",
    api: "API Reference",
    architecture: "Architecture",
    testing: "Testing Guide",
    codeDocsGuide: "Code Docs Guide",
    fieldReference: "Field Reference",
    controlCenter: "Control Center Guide",
    sceneStudioGuide: "Scene Studio Guide",
    generatedCodeDocs: "Generated Code Docs",
    sceneStudio: "Open Scene Studio",
  };

  for (const [key, href] of Object.entries(documentationLinks)) {
    const card = document.createElement("a");
    card.className = "doc-card";
    card.href = href;
    card.target = "_blank";
    card.rel = "noreferrer";
    card.innerHTML = `<strong>${documentationLabels[key] || key}</strong><span>Open ${href}</span>`;
    container.appendChild(card);
  }
}

function renderSmokeResult(result) {
  const target = document.getElementById("smoke-results");
  if (!result) {
    target.textContent = "No smoke checks run yet.";
    return;
  }

  target.textContent = JSON.stringify(result, null, 2);
}

function renderSummary(summary) {
  state.summary = summary;
  document.getElementById("project-root").textContent = summary.projectRoot;
  document.getElementById("last-refresh").textContent = new Date().toLocaleTimeString();
  renderTools(summary.tools);
  renderAppSummary(summary.app);
  renderJobs(summary.jobs);
  renderLogs(summary.logs);
  renderDocs(summary.docs);
  renderSmokeResult(state.lastSmokeResult);
}

async function refreshSummary() {
  // The Control Center uses a single summary endpoint for the dashboard's core state
  // so the browser can redraw from one coherent snapshot.
  const summaryResponse = await fetch("/api/system/summary");
  const summary = await summaryResponse.json();
  renderSummary(summary);
}

async function refreshSummarySafely() {
  try {
    await refreshSummary();
  } catch (error) {
    document.getElementById("last-refresh").textContent = "Refresh failed";
    console.error("Failed to refresh the Control Center summary.", error);
  }
}

function activateSection(sectionName) {
  document.querySelectorAll(".nav-link").forEach((button) => {
    button.classList.toggle("active", button.dataset.sectionLink === sectionName);
  });
  document.querySelectorAll(".section").forEach((section) => {
    section.classList.toggle("active", section.dataset.section === sectionName);
  });
}

async function startJob(action, extraPayload = {}) {
  const endpointMap = {
    bootstrap: "/api/jobs/bootstrap",
    build: "/api/jobs/build",
    test: "/api/jobs/test",
    format: "/api/jobs/format",
    "generate-code-docs": "/api/jobs/generate-code-docs",
  };

  // Jobs all share the same "click button, POST action, refresh dashboard" pattern.
  await postJson(endpointMap[action], extraPayload);
  await refreshSummary();
}

function getFormData(formId) {
  const form = document.getElementById(formId);
  return Object.fromEntries(new FormData(form).entries());
}

async function sendApiRequest() {
  // The playground forwards whatever the user typed almost verbatim so it can act
  // as a small manual API client inside the Control Center.
  const formValues = getFormData("api-form");
  const requestResponse = await postJson("/api/playground/request", {
    ...formValues,
    body: document.getElementById("api-body").value,
  });

  document.getElementById("api-response").textContent = JSON.stringify(requestResponse, null, 2);
  await refreshSummary();
}

async function runSmokeChecks() {
  const formValues = getFormData("smoke-form");
  state.lastSmokeResult = await postJson("/api/app/smoke", formValues);
  renderSmokeResult(state.lastSmokeResult);
}

async function startApp() {
  const applicationRequest = getFormData("app-form");
  await postJson("/api/app/start", applicationRequest);
  await refreshSummary();
}

async function stopApp() {
  await postJson("/api/app/stop", {});
  await refreshSummary();
}

function applySample(sampleName) {
  const selectedSample = httpApiSamples[sampleName];
  if (!selectedSample) {
    return;
  }

  const form = document.getElementById("api-form");
  form.elements.method.value = selectedSample.method;
  form.elements.path.value = selectedSample.path;
  document.getElementById("api-body").value = selectedSample.body;
}

function wireEvents() {
  // Event wiring is centralized so the startup sequence can stay readable and so
  // future contributors only have one place to look for UI behavior hookups.
  document.querySelectorAll("[data-section-link]").forEach((button) => {
    button.addEventListener("click", () => activateSection(button.dataset.sectionLink));
  });

  document.querySelectorAll("[data-job-action]").forEach((button) => {
    button.addEventListener("click", async () => {
      const action = button.dataset.jobAction;
      const configuration = button.dataset.configuration;
      await startJob(action, configuration ? { configuration } : {});
    });
  });

  document.querySelectorAll("[data-playground-sample]").forEach((button) => {
    button.addEventListener("click", () => applySample(button.dataset.playgroundSample));
  });

  document.getElementById("send-api-button").addEventListener("click", sendApiRequest);
  document.getElementById("run-smoke-button").addEventListener("click", runSmokeChecks);
  document.getElementById("start-app-button").addEventListener("click", startApp);
  document.getElementById("stop-app-button").addEventListener("click", stopApp);
  document.getElementById("refresh-button").addEventListener("click", refreshSummary);
  document.getElementById("theme-toggle").addEventListener("click", () => {
    const nextTheme = document.body.getAttribute("data-theme") === "dark" ? "light" : "dark";
    setTheme(nextTheme);
  });
}

document.addEventListener("DOMContentLoaded", async () => {
  const savedTheme =
    localStorage.getItem("halcyn-control-center-theme") ||
    localStorage.getItem("halcyn-control-plane-theme") ||
    "dark";
  setTheme(savedTheme);
  wireEvents();
  applySample("health");
  await refreshSummarySafely();
  // A lightweight polling loop is enough for this dashboard because the browser is
  // mostly observing state rather than driving high-frequency interactions.
  setInterval(() => {
    void refreshSummarySafely();
  }, 4000);
});

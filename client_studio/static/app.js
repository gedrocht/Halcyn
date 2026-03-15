const state = {
  catalog: null,
  latestPreview: null,
  liveSession: null,
  selectedPresetId: null,
  previewBusy: false,
  applyBusy: false,
  previewTimerId: null,
  configureTimerId: null,
  sessionPollTimerId: null,
  sessionEventSource: null,
  lastConfigureSignature: null,
  lastPreviewSignature: null,
  pointer: {
    x: 0.5,
    y: 0.5,
    speed: 0,
    lastTimestamp: performance.now(),
    lastX: 0.5,
    lastY: 0.5,
  },
  audio: {
    enabled: false,
    level: 0,
    bass: 0,
    mid: 0,
    treble: 0,
    microphoneStream: null,
    audioContext: null,
    frequencyAnalyser: null,
    microphoneSourceNode: null,
    animationFrameId: 0,
    frequencyByteData: null,
  },
};

// The browser keeps fast-changing interaction state locally so it can respond
// immediately to pointer and microphone input, while the server stays responsible
// for authoritative scene generation and live-session state.
function clamp(value, lower, upper) {
  return Math.max(lower, Math.min(upper, value));
}

function fract(value) {
  return value - Math.floor(value);
}

async function fetchJson(requestUrl) {
  const httpResponse = await fetch(requestUrl);
  return httpResponse.json();
}

async function postJson(requestUrl, requestPayload = {}) {
  const httpResponse = await fetch(requestUrl, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(requestPayload),
  });
  return httpResponse.json();
}

function buildPayloadSignature(requestPayload) {
  // Signatures let us skip redundant network requests when the generated payload
  // would be identical to the one we already sent.
  return JSON.stringify(requestPayload);
}

function getControlForm() {
  return document.getElementById("control-form");
}

function setLastAction(text) {
  document.getElementById("last-action").textContent = text;
}

function writeApplyLog(logPayload) {
  document.getElementById("apply-log").textContent = JSON.stringify(logPayload, null, 2);
}

function updateRangeValue(inputId, labelId, digits = 2) {
  const rangeInput = document.getElementById(inputId);
  const valueLabel = document.getElementById(labelId);
  valueLabel.textContent = Number.parseFloat(rangeInput.value).toFixed(digits);
}

function updateAllRangeValues() {
  updateRangeValue("density-input", "density-value", 0);
  updateRangeValue("speed-input", "speed-value", 2);
  updateRangeValue("gain-input", "gain-value", 2);
  updateRangeValue("manual-drive-input", "manual-drive-value", 2);
  updateRangeValue("point-size-input", "point-size-value", 1);
  updateRangeValue("line-width-input", "line-width-value", 2);
  updateRangeValue("auto-apply-ms-input", "auto-apply-ms-value", 0);
}

function currentTarget() {
  const formData = new FormData(getControlForm());
  const host = String(formData.get("host") || "127.0.0.1").trim() || "127.0.0.1";
  const port = Number.parseInt(String(formData.get("port") || "8080"), 10) || 8080;
  return { host, port };
}

function syncTargetSummary() {
  const targetConnection = currentTarget();
  document.getElementById("target-summary").textContent =
    `${targetConnection.host}:${targetConnection.port}`;
}

function getSelectedPreset() {
  if (!state.catalog) {
    return null;
  }
  return state.catalog.presets.find((preset) => preset.id === state.selectedPresetId) || null;
}

function selectPreset(presetId) {
  state.selectedPresetId = presetId;
  const preset = getSelectedPreset();
  if (!preset) {
    return;
  }

  // Resetting the controls to preset defaults gives every preset a predictable
  // starting point before the user begins customizing it.
  const controls = getControlForm().elements;
  const defaults = preset.defaults;
  controls.density.value = defaults.density;
  controls.pointSize.value = defaults.pointSize;
  controls.lineWidth.value = defaults.lineWidth;
  controls.speed.value = defaults.speed;
  controls.gain.value = defaults.gain;
  controls.manualDrive.value = defaults.manualDrive;
  controls.background.value = defaults.background;
  controls.primaryColor.value = defaults.primaryColor;
  controls.secondaryColor.value = defaults.secondaryColor;

  document.getElementById("preset-summary").textContent = preset.name;
  renderPresetDeck();
  updateAllRangeValues();
  syncTargetSummary();
}

function renderPresetDeck() {
  const presetGrid = document.getElementById("preset-grid");
  presetGrid.innerHTML = "";

  for (const preset of state.catalog.presets) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = `preset-card${preset.id === state.selectedPresetId ? " active" : ""}`;
    button.innerHTML = `
      <strong>${preset.name}</strong>
      <p>${preset.summary}</p>
      <span class="preset-tag">${preset.emphasis}</span>
    `;
    button.addEventListener("click", () => {
      selectPreset(preset.id);
      queueLiveSessionConfigure();
      void previewScene();
    });
    presetGrid.appendChild(button);
  }
}

function isLiveStreaming() {
  return document.getElementById("auto-apply-toggle").checked;
}

function buildSignalsPayload() {
  // Signals arrive from different browser features, but the server wants one
  // normalized structure no matter which inputs are enabled.
  return {
    useEpoch: document.getElementById("epoch-toggle").checked,
    useNoise: document.getElementById("noise-toggle").checked,
    usePointer: document.getElementById("pointer-toggle").checked,
    useAudio: document.getElementById("audio-toggle").checked && state.audio.enabled,
    epochSeconds: Date.now() / 1000,
    noiseSeed: 1,
    pointer: {
      x: state.pointer.x,
      y: state.pointer.y,
      speed: state.pointer.speed,
    },
    audio: {
      level: state.audio.level,
      bass: state.audio.bass,
      mid: state.audio.mid,
      treble: state.audio.treble,
    },
    manual: {
      drive: Number.parseFloat(getControlForm().elements.manualDrive.value),
    },
  };
}

function buildRequestPayload() {
  // Preview, apply, and live-session routes all share this same payload shape.
  // Using one builder helps keep those browser-to-server contracts aligned.
  const formData = new FormData(getControlForm());
  return {
    presetId: state.selectedPresetId,
    target: currentTarget(),
    settings: {
      density: Number.parseInt(String(formData.get("density")), 10),
      pointSize: Number.parseFloat(String(formData.get("pointSize"))),
      lineWidth: Number.parseFloat(String(formData.get("lineWidth"))),
      speed: Number.parseFloat(String(formData.get("speed"))),
      gain: Number.parseFloat(String(formData.get("gain"))),
      manualDrive: Number.parseFloat(String(formData.get("manualDrive"))),
      background: String(formData.get("background")),
      primaryColor: String(formData.get("primaryColor")),
      secondaryColor: String(formData.get("secondaryColor")),
    },
    session: {
      cadenceMs: Number.parseInt(String(formData.get("autoApplyMs")), 10),
    },
    signals: buildSignalsPayload(),
  };
}

function renderPointerBlip() {
  const blip = document.getElementById("pointer-blip");
  blip.style.left = `${state.pointer.x * 100}%`;
  blip.style.top = `${state.pointer.y * 100}%`;
}

function localEnergyEstimate() {
  // This estimate is only for immediate browser feedback. The server computes the
  // authoritative energy value again when it builds the actual scene.
  const manualDrive = Number.parseFloat(getControlForm().elements.manualDrive.value) || 0;
  const pointerSpeed = document.getElementById("pointer-toggle").checked ? state.pointer.speed : 0;
  const audioLevel = document.getElementById("audio-toggle").checked ? state.audio.level : 0;
  const useNoise = document.getElementById("noise-toggle").checked;
  const noisePhase = useNoise ? fract(Math.sin((Date.now() / 1000) * 0.27) * 43758.5453123) : 0;
  return clamp(manualDrive * 0.5 + pointerSpeed * 0.4 + audioLevel * 0.9 + noisePhase * 0.25, 0, 2.2);
}

function renderSignalReadouts() {
  document.getElementById("pointer-readout").textContent =
    `x ${state.pointer.x.toFixed(2)} / y ${state.pointer.y.toFixed(2)} / speed ${state.pointer.speed.toFixed(2)}`;
  document.getElementById("audio-readout").textContent =
    `level ${state.audio.level.toFixed(2)} / bass ${state.audio.bass.toFixed(2)} / mid ${state.audio.mid.toFixed(2)} / treble ${state.audio.treble.toFixed(2)}`;
  document.getElementById("energy-readout").textContent = localEnergyEstimate().toFixed(2);
  renderPointerBlip();
}

function renderPreview(sceneBundle) {
  state.latestPreview = sceneBundle;
  document.getElementById("scene-preview").textContent = JSON.stringify(sceneBundle.scene, null, 2);
  document.getElementById("analysis-summary").textContent =
    `${sceneBundle.preset.name}: ${sceneBundle.analysis.primitive}, ${sceneBundle.analysis.vertexCount} vertices, sources ${sceneBundle.analysis.activeSources.join(", ")}, energy ${sceneBundle.analysis.energy.toFixed(2)}.`;
  setLastAction(`Previewed ${sceneBundle.preset.name}`);
}

function renderLiveSession(sessionPayload) {
  state.liveSession = sessionPayload.session;
  const session = sessionPayload.session;
  const sessionSummaryTarget = document.getElementById("session-summary");
  const target = sessionSummaryTarget;
  const framesSummary = `${session.frames_applied} ok / ${session.frames_failed} failed`;
  const cadenceSummary = `${session.cadence_ms} ms`;
  target.textContent = `${session.status} • ${cadenceSummary} • ${framesSummary}`;
}

function renderLiveSessionSnapshot(sessionPayload) {
  state.liveSession = sessionPayload.session;
  const session = sessionPayload.session;
  const sessionSummaryTarget = document.getElementById("session-summary");
  const framesSummary = `${session.frames_applied} ok / ${session.frames_failed} failed`;
  const cadenceSummary = `${session.cadence_ms} ms`;
  sessionSummaryTarget.textContent = `${session.status} - ${cadenceSummary} - ${framesSummary}`;
}

async function refreshLiveSession() {
  try {
    const sessionPayload = await fetchJson("/api/client-studio/session");
    renderLiveSessionSnapshot(sessionPayload);
  } catch {
    document.getElementById("session-summary").textContent = "Unavailable";
  }
}

function clearSessionPolling() {
  if (state.sessionPollTimerId !== null) {
    window.clearInterval(state.sessionPollTimerId);
    state.sessionPollTimerId = null;
  }
}

function connectSessionStream() {
  clearSessionPolling();
  if (state.sessionEventSource !== null) {
    state.sessionEventSource.close();
    state.sessionEventSource = null;
  }
  if (!window.EventSource) {
    state.sessionPollTimerId = window.setInterval(() => {
      void refreshLiveSession();
    }, 1500);
    return;
  }

  // Server-Sent Events let the server push state changes to the browser without
  // the browser repeatedly polling for updates.
  const sessionEventSource = new window.EventSource("/api/client-studio/session/stream");
  sessionEventSource.addEventListener("session", (event) => {
    const sessionPayload = JSON.parse(event.data);
    renderLiveSessionSnapshot(sessionPayload);
  });
  sessionEventSource.addEventListener("error", () => {
    sessionEventSource.close();
    if (state.sessionEventSource === sessionEventSource) {
      state.sessionEventSource = null;
    }
    state.sessionPollTimerId = window.setInterval(() => {
      void refreshLiveSession();
    }, 1500);
    setLastAction("Live session stream disconnected; using polling fallback");
  });
  state.sessionEventSource = sessionEventSource;
}

function teardownSessionStream() {
  clearSessionPolling();
  if (state.sessionEventSource !== null) {
    state.sessionEventSource.close();
    state.sessionEventSource = null;
  }
}

async function previewScene(
  requestPayload = buildRequestPayload(),
  requestSignature = buildPayloadSignature(requestPayload),
) {
  if (state.previewBusy) {
    return;
  }

  state.previewBusy = true;
  try {
    const sceneBundle = await postJson("/api/client-studio/preview", requestPayload);
    state.lastPreviewSignature = requestSignature;
    renderPreview(sceneBundle);
  } catch (error) {
    writeApplyLog({ status: "preview-error", message: String(error) });
    setLastAction("Preview failed");
  } finally {
    state.previewBusy = false;
  }
}

function queuePreviewScene() {
  if (state.previewTimerId !== null) {
    window.clearTimeout(state.previewTimerId);
  }

  state.previewTimerId = window.setTimeout(() => {
    state.previewTimerId = null;
    const requestPayload = buildRequestPayload();
    const requestSignature = buildPayloadSignature(requestPayload);
    // Debouncing keeps quick slider drags from generating many previews the user
    // never has time to see.
    if (requestSignature === state.lastPreviewSignature && state.latestPreview !== null) {
      return;
    }
    void previewScene(requestPayload, requestSignature);
  }, 60);
}

async function applyScene() {
  if (state.applyBusy) {
    return;
  }

  state.applyBusy = true;
  try {
    const applyResponse = await postJson("/api/client-studio/apply", buildRequestPayload());
    writeApplyLog(applyResponse);
    if (applyResponse.scene) {
      document.getElementById("scene-preview").textContent =
        JSON.stringify(applyResponse.scene, null, 2);
    }
    setLastAction(
      applyResponse.status === "applied"
        ? `Applied ${applyResponse.preset.name}`
        : applyResponse.status
    );
  } catch (error) {
    writeApplyLog({ status: "apply-error", message: String(error) });
    setLastAction("Apply failed");
  } finally {
    state.applyBusy = false;
    await refreshLiveSession();
  }
}

async function startLiveSession() {
  const requestPayload = buildRequestPayload();
  const requestSignature = buildPayloadSignature(requestPayload);
  try {
    const sessionResponse = await postJson("/api/client-studio/session/start", requestPayload);
    state.lastConfigureSignature = requestSignature;
    renderLiveSessionSnapshot(sessionResponse);
    setLastAction(`Live stream started at ${sessionResponse.session.cadence_ms} ms`);
  } catch (error) {
    writeApplyLog({ status: "session-start-error", message: String(error) });
    setLastAction("Live stream failed to start");
    document.getElementById("auto-apply-toggle").checked = false;
  }
}

async function stopLiveSession() {
  if (state.configureTimerId !== null) {
    window.clearTimeout(state.configureTimerId);
    state.configureTimerId = null;
  }
  state.lastConfigureSignature = null;

  try {
    const sessionResponse = await postJson("/api/client-studio/session/stop", {});
    renderLiveSessionSnapshot(sessionResponse);
    setLastAction("Live stream stopped");
  } catch (error) {
    writeApplyLog({ status: "session-stop-error", message: String(error) });
    setLastAction("Live stream stop failed");
  }
}

function queueLiveSessionConfigure() {
  if (!isLiveStreaming()) {
    return;
  }

  // Configure requests are deduplicated and slightly delayed so the browser feels
  // responsive without sending a request on every tiny input change.
  if (buildPayloadSignature(buildRequestPayload()) === state.lastConfigureSignature) {
    return;
  }

  if (state.configureTimerId !== null) {
    return;
  }

  state.configureTimerId = window.setTimeout(async () => {
    state.configureTimerId = null;
    if (!isLiveStreaming()) {
      return;
    }
    const requestPayload = buildRequestPayload();
    const requestSignature = buildPayloadSignature(requestPayload);
    if (requestSignature === state.lastConfigureSignature) {
      return;
    }
    try {
      const sessionResponse = await postJson(
        "/api/client-studio/session/configure",
        requestPayload
      );
      state.lastConfigureSignature = requestSignature;
      renderLiveSessionSnapshot(sessionResponse);
    } catch (error) {
      setLastAction(`Live update failed: ${String(error)}`);
    }
  }, 40);
}

function queueInteractiveUpdate() {
  if (isLiveStreaming()) {
    queueLiveSessionConfigure();
    return;
  }
  if (state.latestPreview !== null) {
    queuePreviewScene();
  }
}

function stopAudioCapture(suppressInteractiveUpdate = false) {
  if (state.audio.animationFrameId) {
    cancelAnimationFrame(state.audio.animationFrameId);
  }
  if (state.audio.microphoneStream) {
    for (const track of state.audio.microphoneStream.getTracks()) {
      track.stop();
    }
  }
  if (state.audio.audioContext) {
    void state.audio.audioContext.close();
  }
  state.audio = {
    enabled: false,
    level: 0,
    bass: 0,
    mid: 0,
    treble: 0,
    microphoneStream: null,
    audioContext: null,
    frequencyAnalyser: null,
    microphoneSourceNode: null,
    animationFrameId: 0,
    frequencyByteData: null,
  };
  renderSignalReadouts();
  if (!suppressInteractiveUpdate) {
    queueInteractiveUpdate();
  }
}

function pumpAudioMetrics() {
  if (
    !state.audio.enabled ||
    !state.audio.frequencyAnalyser ||
    !state.audio.frequencyByteData
  ) {
    return;
  }

  // The analyser provides a full frequency spectrum. We collapse that into broad
  // bands because the scene generators only need coarse musical energy buckets.
  state.audio.frequencyAnalyser.getByteFrequencyData(state.audio.frequencyByteData);
  const values = Array.from(state.audio.frequencyByteData);
  const average = values.reduce((sum, value) => sum + value, 0) / Math.max(values.length, 1);
  const third = Math.max(1, Math.floor(values.length / 3));
  const bass = values.slice(0, third);
  const mid = values.slice(third, third * 2);
  const treble = values.slice(third * 2);

  const averageBand = (band) =>
    band.reduce((sum, value) => sum + value, 0) / Math.max(band.length, 1) / 255;

  state.audio.level = clamp(average / 255, 0, 1);
  state.audio.bass = clamp(averageBand(bass), 0, 1);
  state.audio.mid = clamp(averageBand(mid), 0, 1);
  state.audio.treble = clamp(averageBand(treble), 0, 1);
  renderSignalReadouts();
  queueInteractiveUpdate();
  state.audio.animationFrameId = requestAnimationFrame(pumpAudioMetrics);
}

async function startAudioCapture() {
  if (state.audio.enabled) {
    return;
  }
  if (!navigator.mediaDevices?.getUserMedia) {
    writeApplyLog({
      status: "audio-unavailable",
      message: "This browser does not support microphone capture.",
    });
    document.getElementById("audio-toggle").checked = false;
    return;
  }

  try {
    const microphoneStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const audioContext = new window.AudioContext();
    const frequencyAnalyser = audioContext.createAnalyser();
    frequencyAnalyser.fftSize = 256;
    const microphoneSourceNode = audioContext.createMediaStreamSource(microphoneStream);
    microphoneSourceNode.connect(frequencyAnalyser);
    state.audio = {
      enabled: true,
      level: 0,
      bass: 0,
      mid: 0,
      treble: 0,
      microphoneStream,
      audioContext,
      frequencyAnalyser,
      microphoneSourceNode,
      animationFrameId: 0,
      frequencyByteData: new Uint8Array(frequencyAnalyser.frequencyBinCount),
    };
    pumpAudioMetrics();
    setLastAction("Microphone capture enabled");
  } catch (error) {
    document.getElementById("audio-toggle").checked = false;
    writeApplyLog({ status: "audio-denied", message: String(error) });
    setLastAction("Microphone unavailable");
  }
}

function handlePointerMove(event) {
  const stage = document.getElementById("pointer-stage");
  const rect = stage.getBoundingClientRect();
  const x = clamp((event.clientX - rect.left) / rect.width, 0, 1);
  const y = clamp((event.clientY - rect.top) / rect.height, 0, 1);
  const now = performance.now();
  const elapsedMilliseconds = Math.max(16, now - state.pointer.lastTimestamp);
  const pointerDistance = Math.hypot(x - state.pointer.lastX, y - state.pointer.lastY);
  const pointerSpeed = clamp(pointerDistance / (elapsedMilliseconds / 1000), 0, 1);

  state.pointer = {
    x,
    y,
    speed: pointerSpeed,
    lastTimestamp: now,
    lastX: x,
    lastY: y,
  };
  renderSignalReadouts();
  queueInteractiveUpdate();
}

function teardownClientStudio() {
  if (state.previewTimerId !== null) {
    window.clearTimeout(state.previewTimerId);
    state.previewTimerId = null;
  }
  if (state.configureTimerId !== null) {
    window.clearTimeout(state.configureTimerId);
    state.configureTimerId = null;
  }
  teardownSessionStream();
  stopAudioCapture(true);
}

function wireEvents() {
  // Keeping event hookup in one place makes the startup path easier to follow and
  // gives future contributors one obvious place to look for UI behavior.
  document.getElementById("preview-button").addEventListener("click", () => {
    void previewScene();
  });

  document.getElementById("apply-button").addEventListener("click", () => {
    void applyScene();
  });

  document.getElementById("auto-apply-toggle").addEventListener("change", async (event) => {
    if (event.target.checked) {
      await startLiveSession();
    } else {
      await stopLiveSession();
    }
  });

  document.getElementById("pointer-stage").addEventListener("pointermove", handlePointerMove);
  document.getElementById("pointer-stage").addEventListener("pointerleave", () => {
    state.pointer.speed = 0;
    renderSignalReadouts();
    queueInteractiveUpdate();
  });

  document.getElementById("audio-toggle").addEventListener("change", async (event) => {
    if (event.target.checked) {
      await startAudioCapture();
    } else {
      stopAudioCapture();
      setLastAction("Microphone capture disabled");
    }
  });

  document.querySelectorAll("input").forEach((input) => {
    input.addEventListener("input", () => {
      updateAllRangeValues();
      syncTargetSummary();
      renderSignalReadouts();
      queueInteractiveUpdate();
    });
  });
}

async function bootstrap() {
  // The page boots in three stages: fetch catalog metadata, hydrate the controls,
  // then request the first preview and live-session snapshot.
  state.catalog = await fetchJson("/api/client-studio/catalog");
  state.selectedPresetId = state.catalog.defaults.presetId;
  document.getElementById("auto-apply-ms-input").value = state.catalog.defaults.autoApplyMs;
  renderPresetDeck();
  selectPreset(state.selectedPresetId);
  updateAllRangeValues();
  renderSignalReadouts();
  wireEvents();
  await previewScene();
  await refreshLiveSession();
  connectSessionStream();
}

document.addEventListener("DOMContentLoaded", () => {
  void bootstrap().catch((error) => {
    writeApplyLog({ status: "bootstrap-error", message: String(error) });
    setLastAction("Client Studio failed to start");
  });
});

window.addEventListener("beforeunload", () => {
  // Release timers, streams, and audio capture when the page closes so the browser
  // does not keep background work alive unnecessarily.
  teardownClientStudio();
});

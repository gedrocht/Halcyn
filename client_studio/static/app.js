const state = {
  catalog: null,
  selectedPresetId: null,
  latestPreview: null,
  busy: false,
  autoApplyTimerId: null,
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
    stream: null,
    context: null,
    analyser: null,
    source: null,
    frameId: 0,
    data: null,
  },
};

function clamp(value, lower, upper) {
  return Math.max(lower, Math.min(upper, value));
}

function fract(value) {
  return value - Math.floor(value);
}

async function postJson(url, payload = {}) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return response.json();
}

function form() {
  return document.getElementById("control-form");
}

function setLastAction(text) {
  document.getElementById("last-action").textContent = text;
}

function writeApplyLog(payload) {
  document.getElementById("apply-log").textContent = JSON.stringify(payload, null, 2);
}

function updateRangeValue(inputId, labelId, digits = 2) {
  const input = document.getElementById(inputId);
  const label = document.getElementById(labelId);
  label.textContent = Number.parseFloat(input.value).toFixed(digits);
}

function updateAllRangeValues() {
  updateRangeValue("density-input", "density-value", 0);
  updateRangeValue("speed-input", "speed-value", 2);
  updateRangeValue("gain-input", "gain-value", 2);
  updateRangeValue("manual-drive-input", "manual-drive-value", 2);
  updateRangeValue("point-size-input", "point-size-value", 1);
  updateRangeValue("line-width-input", "line-width-value", 2);
}

function currentTarget() {
  const data = new FormData(form());
  const host = String(data.get("host") || "127.0.0.1").trim() || "127.0.0.1";
  const port = Number.parseInt(String(data.get("port") || "8080"), 10) || 8080;
  return { host, port };
}

function syncTargetSummary() {
  const target = currentTarget();
  document.getElementById("target-summary").textContent = `${target.host}:${target.port}`;
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

  const controls = form().elements;
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
}

function renderPresetDeck() {
  const target = document.getElementById("preset-grid");
  target.innerHTML = "";

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
      void previewScene();
    });
    target.appendChild(button);
  }
}

function buildSignalsPayload() {
  const nowSeconds = Date.now() / 1000;
  return {
    useEpoch: document.getElementById("epoch-toggle").checked,
    useNoise: document.getElementById("noise-toggle").checked,
    usePointer: document.getElementById("pointer-toggle").checked,
    useAudio: document.getElementById("audio-toggle").checked && state.audio.enabled,
    epochSeconds: nowSeconds,
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
      drive: Number.parseFloat(form().elements.manualDrive.value),
    },
  };
}

function buildRequestPayload() {
  const data = new FormData(form());
  return {
    presetId: state.selectedPresetId,
    target: currentTarget(),
    settings: {
      density: Number.parseInt(String(data.get("density")), 10),
      pointSize: Number.parseFloat(String(data.get("pointSize"))),
      lineWidth: Number.parseFloat(String(data.get("lineWidth"))),
      speed: Number.parseFloat(String(data.get("speed"))),
      gain: Number.parseFloat(String(data.get("gain"))),
      manualDrive: Number.parseFloat(String(data.get("manualDrive"))),
      background: String(data.get("background")),
      primaryColor: String(data.get("primaryColor")),
      secondaryColor: String(data.get("secondaryColor")),
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
  const manualDrive = Number.parseFloat(form().elements.manualDrive.value) || 0;
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

function renderPreview(bundle) {
  state.latestPreview = bundle;
  document.getElementById("scene-preview").textContent = JSON.stringify(bundle.scene, null, 2);
  document.getElementById("analysis-summary").textContent =
    `${bundle.preset.name}: ${bundle.analysis.primitive}, ${bundle.analysis.vertexCount} vertices, sources ${bundle.analysis.activeSources.join(", ")}, energy ${bundle.analysis.energy.toFixed(2)}.`;
  setLastAction(`Previewed ${bundle.preset.name}`);
}

async function previewScene() {
  if (state.busy) {
    return;
  }

  state.busy = true;
  try {
    const bundle = await postJson("/api/client-studio/preview", buildRequestPayload());
    renderPreview(bundle);
  } catch (error) {
    writeApplyLog({ status: "preview-error", message: String(error) });
    setLastAction("Preview failed");
  } finally {
    state.busy = false;
  }
}

async function applyScene(reason = "manual") {
  if (state.busy) {
    return;
  }

  state.busy = true;
  try {
    const payload = buildRequestPayload();
    const response = await postJson("/api/client-studio/apply", payload);
    writeApplyLog(response);
    if (response.scene) {
      document.getElementById("scene-preview").textContent = JSON.stringify(response.scene, null, 2);
    }
    setLastAction(
      response.status === "applied"
        ? `Applied ${response.preset.name} (${reason})`
        : `${response.status} (${reason})`
    );
  } catch (error) {
    writeApplyLog({ status: "apply-error", message: String(error) });
    setLastAction("Apply failed");
  } finally {
    state.busy = false;
  }
}

function stopAudioCapture() {
  if (state.audio.frameId) {
    cancelAnimationFrame(state.audio.frameId);
  }
  if (state.audio.stream) {
    for (const track of state.audio.stream.getTracks()) {
      track.stop();
    }
  }
  if (state.audio.context) {
    void state.audio.context.close();
  }
  state.audio = {
    enabled: false,
    level: 0,
    bass: 0,
    mid: 0,
    treble: 0,
    stream: null,
    context: null,
    analyser: null,
    source: null,
    frameId: 0,
    data: null,
  };
  renderSignalReadouts();
}

function pumpAudioMetrics() {
  if (!state.audio.enabled || !state.audio.analyser || !state.audio.data) {
    return;
  }

  state.audio.analyser.getByteFrequencyData(state.audio.data);
  const values = Array.from(state.audio.data);
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
  state.audio.frameId = requestAnimationFrame(pumpAudioMetrics);
}

async function startAudioCapture() {
  if (state.audio.enabled) {
    return;
  }
  if (!navigator.mediaDevices?.getUserMedia) {
    writeApplyLog({ status: "audio-unavailable", message: "This browser does not support microphone capture." });
    document.getElementById("audio-toggle").checked = false;
    return;
  }

  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const context = new window.AudioContext();
    const analyser = context.createAnalyser();
    analyser.fftSize = 256;
    const source = context.createMediaStreamSource(stream);
    source.connect(analyser);
    state.audio = {
      enabled: true,
      level: 0,
      bass: 0,
      mid: 0,
      treble: 0,
      stream,
      context,
      analyser,
      source,
      frameId: 0,
      data: new Uint8Array(analyser.frequencyBinCount),
    };
    pumpAudioMetrics();
    setLastAction("Microphone capture enabled");
  } catch (error) {
    document.getElementById("audio-toggle").checked = false;
    writeApplyLog({ status: "audio-denied", message: String(error) });
    setLastAction("Microphone unavailable");
  }
}

function configureAutoApply() {
  if (state.autoApplyTimerId) {
    clearInterval(state.autoApplyTimerId);
    state.autoApplyTimerId = null;
  }
  if (document.getElementById("auto-apply-toggle").checked) {
    const intervalMs = state.catalog?.defaults?.autoApplyMs || 750;
    state.autoApplyTimerId = window.setInterval(() => {
      void applyScene("auto");
    }, intervalMs);
    setLastAction("Auto-apply armed");
  }
}

function handlePointerMove(event) {
  const stage = document.getElementById("pointer-stage");
  const rect = stage.getBoundingClientRect();
  const x = clamp((event.clientX - rect.left) / rect.width, 0, 1);
  const y = clamp((event.clientY - rect.top) / rect.height, 0, 1);
  const now = performance.now();
  const dt = Math.max(16, now - state.pointer.lastTimestamp);
  const distance = Math.hypot(x - state.pointer.lastX, y - state.pointer.lastY);
  const speed = clamp(distance / (dt / 1000), 0, 1);

  state.pointer = {
    x,
    y,
    speed,
    lastTimestamp: now,
    lastX: x,
    lastY: y,
  };
  renderSignalReadouts();
}

function wireEvents() {
  document.getElementById("preview-button").addEventListener("click", () => {
    void previewScene();
  });
  document.getElementById("apply-button").addEventListener("click", () => {
    void applyScene("manual");
  });
  document.getElementById("auto-apply-toggle").addEventListener("change", configureAutoApply);

  document.getElementById("pointer-stage").addEventListener("pointermove", handlePointerMove);
  document.getElementById("pointer-stage").addEventListener("pointerleave", () => {
    state.pointer.speed = 0;
    renderSignalReadouts();
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
      if (state.latestPreview) {
        void previewScene();
      }
    });
  });
}

async function bootstrap() {
  state.catalog = await fetch("/api/client-studio/catalog").then((response) => response.json());
  state.selectedPresetId = state.catalog.defaults.presetId;
  renderPresetDeck();
  selectPreset(state.selectedPresetId);
  syncTargetSummary();
  updateAllRangeValues();
  renderSignalReadouts();
  wireEvents();
  await previewScene();
}

document.addEventListener("DOMContentLoaded", () => {
  void bootstrap();
});

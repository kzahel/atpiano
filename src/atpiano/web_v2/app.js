"use strict";

const STREAM_SCHEMA = "atpiano.corrected-stream.v1";
const BLOCK_HEADER_BYTES = 48;
const MAX_WEBSOCKET_BUFFER_BYTES = 4 * 1024 * 1024;
const TIMELINE = window.atpianoTimeline;
const PITCH_MIN = 21;
const PITCH_MAX = 108;
const PEDAL_HEIGHT = 38;
const PITCH_GUTTER_WIDTH = 64;
const CAPTURE_CONSTRAINTS = {
  channelCount: 1,
  echoCancellation: false,
  noiseSuppression: false,
  autoGainControl: false,
};

const state = {
  config: null,
  session: null,
  events: [],
  nextSequence: 0,
  seekS: 0,
  windowS: 30,
  follow: true,
  queryKey: "",
  capture: null,
  pollTimer: null,
  eventRequestId: 0,
  inspectionS: null,
  showRoll: true,
  showKeyboard: true,
  showScore: true,
  keyboardKeys: new Map(),
  score: null,
  scoreRenderKey: "",
  scoreRenderer: null,
};

function el(id) {
  return document.getElementById(id);
}

function formatClock(seconds, tenths = false) {
  const value = Math.max(0, Number(seconds) || 0);
  const minutes = Math.floor(value / 60);
  const remainder = value - minutes * 60;
  return `${String(minutes).padStart(2, "0")}:${remainder
    .toFixed(tenths ? 1 : 0)
    .padStart(tenths ? 4 : 2, "0")}`;
}

function formatBytes(bytes) {
  const value = Math.max(0, Number(bytes) || 0);
  if (value >= 1024 ** 3) return `${(value / 1024 ** 3).toFixed(1)} GiB`;
  if (value >= 1024 ** 2) return `${(value / 1024 ** 2).toFixed(1)} MiB`;
  return `${(value / 1024).toFixed(1)} KiB`;
}

function showError(error) {
  el("error-message").textContent = error ? error.message || String(error) : "";
}

function showTimelineError(error) {
  const message = error ? error.message || String(error) : "";
  el("timeline-error").textContent = message;
  el("timeline-error").hidden = !message;
}

async function fetchJson(url, options) {
  const response = await fetch(url, { cache: "no-store", ...options });
  const value = await response.json();
  if (!response.ok) throw new Error(value.error || `HTTP ${response.status}`);
  return value;
}

function lane(name) {
  return state.session?.lanes?.find((item) => item.name === name) || null;
}

function currentWindow() {
  return TIMELINE.visibleWindow(
    state.session?.duration_s || 0,
    state.windowS,
    state.seekS,
    state.follow
  );
}

function buildKeyboard() {
  const keyboard = el("piano-keyboard");
  for (const layout of TIMELINE.keyboardLayout(PITCH_MIN, PITCH_MAX)) {
    const key = document.createElement("span");
    key.className = `piano-key ${layout.kind}`;
    key.dataset.pitch = String(layout.pitch);
    key.dataset.landmark = layout.landmark;
    key.style.width = `${layout.widthPercent}%`;
    if (layout.leftPercent != null) {
      key.style.left = `${layout.leftPercent}%`;
    }
    key.title = layout.name;
    const label = document.createElement("span");
    label.className = "key-label";
    label.textContent = layout.landmark;
    key.appendChild(label);
    keyboard.appendChild(key);
    state.keyboardKeys.set(layout.pitch, key);
  }
}

function updateViewVisibility() {
  el("roll-view").hidden = !state.showRoll;
  el("keyboard-view").hidden = !state.showKeyboard;
  el("score-view").hidden = !state.showScore;
}

async function renderCommittedScore(snapshot) {
  const target = el("score-paper");
  const renderKey = `${snapshot.session_id}:${snapshot.musicxml.sha256}`;
  if (renderKey === state.scoreRenderKey) return;
  state.scoreRenderKey = renderKey;
  target.classList.remove("placeholder");
  target.textContent = "Rendering committed score…";
  if (!window.opensheetmusicdisplay?.OpenSheetMusicDisplay) {
    target.innerHTML =
      '<p class="score-error">The pinned browser score renderer could not load. ' +
      "The MusicXML download is still available.</p>";
    return;
  }
  try {
    const response = await fetch("/api/artifacts/score/current.musicxml", {
      cache: "no-store",
    });
    if (!response.ok) throw new Error(`MusicXML: HTTP ${response.status}`);
    const musicxml = await response.text();
    if (renderKey !== state.scoreRenderKey) return;
    target.replaceChildren();
    const renderer = new window.opensheetmusicdisplay.OpenSheetMusicDisplay(
      target,
      {
        autoResize: true,
        backend: "svg",
        drawTitle: true,
        drawPartNames: true,
        drawingParameters: "compacttight",
      }
    );
    state.scoreRenderer = renderer;
    await renderer.load(musicxml);
    if (renderKey !== state.scoreRenderKey) return;
    renderer.render();
  } catch (error) {
    if (renderKey !== state.scoreRenderKey) return;
    const message = document.createElement("p");
    message.className = "score-error";
    message.textContent = error.message || String(error);
    target.replaceChildren(message);
  }
}

function updateScore() {
  const score = state.score;
  const snapshot = score?.snapshot;
  const runtimeAvailable = Boolean(score?.runtime?.available);
  const running = score?.status === "running";
  const button = el("generate-score");
  button.disabled = !score?.can_generate || running;
  button.textContent = running
    ? "Rendering…"
    : snapshot
      ? "Refresh committed score"
      : "Render committed score";
  for (const id of ["download-score-musicxml", "download-score-midi"]) {
    el(id).classList.toggle("disabled", !snapshot);
  }

  if (!runtimeAvailable) {
    el("score-status").textContent = "Score runtime not installed";
    el("score-detail").textContent =
      "Run `uv run atpiano setup-midi2score`, then restart this app.";
  } else if (running) {
    const sampleRate = Number(state.session?.session?.sample_rate_hz || 1);
    el("score-status").textContent =
      `Rendering through ${formatClock(score.job?.commit_sample / sampleRate, true)}…`;
    el("score-detail").textContent =
      "MIDI2ScoreTransformer is working in the background; capture is unaffected.";
  } else if (score?.status === "failed") {
    el("score-status").textContent = "Score render failed";
    el("score-detail").textContent = score.error || "The score job failed.";
  } else if (snapshot) {
    el("score-status").textContent =
      `${snapshot.note_count} notes · through ${formatClock(snapshot.commit_s, true)}`;
    el("score-detail").textContent = score.stale
      ? `This score ends at ${formatClock(
          snapshot.commit_s,
          true
        )}; newer committed notes are ready. Refresh when useful.`
      : "This score exactly represents the current closed committed prefix.";
  } else {
    el("score-status").textContent =
      score?.commit_sample > 0
        ? "Committed notes are ready"
        : "No committed score yet";
    el("score-detail").textContent =
      "Only closed notes behind the commit horizon enter this score.";
  }

  if (snapshot && state.showScore) {
    renderCommittedScore(snapshot);
  } else if (!snapshot && !state.scoreRenderKey) {
    const target = el("score-paper");
    target.classList.add("placeholder");
    target.textContent =
      "Play or replay some notes, then render the stable committed section.";
  }
}

async function generateScore() {
  showError(null);
  try {
    state.score = await fetchJson("/api/score", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    });
    updateScore();
  } catch (error) {
    showError(error);
  }
}

function pinInspection(seconds) {
  const range = currentWindow();
  state.seekS = range.startS;
  state.follow = false;
  state.inspectionS = Math.max(
    range.startS,
    Math.min(Number(seconds) || 0, range.endS)
  );
  el("follow-head").checked = false;
  drawTimeline();
}

function drawKeyboard(snapshot) {
  const activeByPitch = new Map(
    snapshot.notes.map((event) => [event.pitch, event])
  );
  for (const [pitch, key] of state.keyboardKeys) {
    const event = activeByPitch.get(pitch);
    const kind = TIMELINE.isBlackKey(pitch) ? "black" : "white";
    key.className = `piano-key ${kind}${
      event ? ` ${event.lifecycle}` : ""
    }`;
    key.querySelector(".key-label").textContent = event
      ? TIMELINE.midiName(pitch)
      : key.dataset.landmark;
  }

  const sampleRate = Number(state.session?.session?.sample_rate_hz || 1);
  const range = currentWindow();
  const sampleS =
    snapshot.sample == null ? null : Number(snapshot.sample) / sampleRate;
  const noteNames = snapshot.notes.map((event) => TIMELINE.midiName(event.pitch));
  const pinned = snapshot.mode === "pinned";
  el("keyboard-time").textContent =
    sampleS == null
      ? "Waiting for notes"
      : `${pinned ? "Pinned" : "Latest attack"} · ${formatClock(sampleS, true)}`;
  el("keyboard-notes").textContent =
    noteNames.length > 0 ? noteNames.join(" · ") : "No notes sounding";
  el("follow-latest").disabled = !pinned;
  el("follow-latest").textContent = pinned
    ? "Follow latest attack"
    : "Following latest attack";
  el("inspection-time").min = String(range.startS);
  el("inspection-time").max = String(range.endS);
  el("inspection-time").value = String(
    Math.max(range.startS, Math.min(sampleS ?? range.startS, range.endS))
  );
  el("inspection-time").disabled = state.events.length === 0;
  el("piano-keyboard").setAttribute(
    "aria-label",
    noteNames.length > 0
      ? `${pinned ? "Notes sounding" : "Latest detected attack"}: ${noteNames.join(
          ", "
        )}`
      : "No detected piano keys"
  );
}

function updateControls() {
  const status = state.session?.status || "idle";
  const active = ["warming", "active", "stopping"].includes(status);
  const recording = Boolean(state.capture);
  el("start-microphone").disabled = active || recording;
  el("stop-microphone").disabled = !recording;
  el("start-replay").hidden = !state.config?.replay?.configured;
  el("start-replay").disabled = active || recording;
  for (const id of ["download-midi", "download-jsonl"]) {
    el(id).classList.toggle("disabled", !state.session?.exports_ready);
  }
}

function updateStatus() {
  const current = state.session || {
    status: "idle",
    storage: {},
    transport: {},
  };
  const status = current.status || "idle";
  el("session-state").textContent =
    {
      idle: "Ready",
      warming: "Loading local models",
      active: "Listening",
      stopping: "Settling tail",
      complete: "Stopped · stable",
      failed: "Session failed",
    }[status] || status;
  el("status-dot").className = `status-dot ${status}`;
  const session = current.session;
  el("source-value").textContent = session?.source || "No source";
  el("duration-value").textContent = formatClock(current.duration_s, true);
  el("session-id").textContent = current.session_id || "none";
  const horizons = current.horizons;
  el("preview-value").textContent = horizons
    ? `${Number(horizons.lag_s.provisional).toFixed(2)} s lag`
    : "—";
  el("commit-value").textContent = horizons
    ? `${Number(horizons.lag_s.commit).toFixed(2)} s lag`
    : "—";
  const preview = lane("preview");
  const commit = lane("commit");
  el("preview-detail").textContent = preview
    ? `${preview.window?.processed || 0} windows · ${
        preview.retention?.active_identity_count || 0
      } active`
    : "Basic Pitch";
  el("commit-detail").textContent = commit
    ? `${commit.scheduler?.decode_count || 0} decodes · ${
        commit.events?.emissions || 0
      } revisions${commit.scheduler?.degraded_mode ? " · degraded hop" : ""}`
    : "Transkun";
  el("storage-value").textContent = formatBytes(current.storage?.audio_pcm_bytes);
  el("storage-detail").textContent = current.storage?.warning
    ? `low space · ${formatBytes(current.storage.free_bytes)} free`
    : `${formatBytes(current.storage?.free_bytes)} free`;
  const buffered = state.capture?.socket?.bufferedAmount || 0;
  const maxBuffered = state.capture?.maxBufferedBytes || 0;
  el("transport-value").textContent =
    `${current.transport?.received_blocks || 0} blocks · ` +
    `sequence ${current.transport?.last_event_sequence || state.nextSequence}` +
    (state.capture
      ? ` · ${formatBytes(buffered)} queued / ${formatBytes(maxBuffered)} high`
      : "");
  if (current.error) showError(new Error(current.error));
  if (state.capture) {
    el("action-status").textContent =
      `Microphone active · ${formatClock(
        state.capture.frameCount / state.capture.audioContext.sampleRate,
        true
      )}`;
  } else {
    el("action-status").textContent =
      {
        idle: "Choose deterministic replay or start the microphone.",
        warming: "Loading Basic Pitch and Transkun locally…",
        active:
          session?.source === "replay"
            ? "Fixture replay is feeding the same corrected-session engine."
            : "Microphone blocks are entering the corrected-session engine.",
        stopping: "Running one bounded tail decode and closing exports…",
        complete: "All source audio is settled. Review, seek, or export.",
        failed: "Inspect the error, then start a fresh session.",
      }[status] || "";
  }
  updateControls();
}

async function loadVisibleEvents(force = false) {
  const session = state.session?.session;
  if (!session || !state.session?.horizons) {
    state.eventRequestId += 1;
    state.events = [];
    state.queryKey = "";
    drawTimeline();
    return;
  }
  const range = currentWindow();
  const sampleRate = Number(session.sample_rate_hz);
  const startSample = Math.max(0, Math.floor(range.startS * sampleRate));
  const endSample = Math.max(startSample + 1, Math.ceil(range.endS * sampleRate));
  const eventSequence = Number(
    state.session?.transport?.last_event_sequence || 0
  );
  const audioHead = Number(state.session?.horizons?.audio_head_sample || 0);
  const queryKey = TIMELINE.viewportQueryKey(
    session.session_id,
    startSample,
    endSample,
    eventSequence,
    audioHead,
    state.session?.status || "idle"
  );
  if (!force && queryKey === state.queryKey) {
    drawTimeline();
    return;
  }
  const requestId = ++state.eventRequestId;
  try {
    const payload = await fetchJson(
      `/api/events?start_sample=${startSample}&end_sample=${endSample}` +
        "&include_history=0"
    );
    if (
      requestId !== state.eventRequestId ||
      payload.session_id !== state.session?.session?.session_id
    ) {
      return;
    }
    if (!Array.isArray(payload.materialized)) {
      throw new Error("Timeline response did not contain visible events.");
    }
    state.events = payload.materialized;
    state.nextSequence = eventSequence;
    state.queryKey = queryKey;
    showTimelineError(null);
    drawTimeline();
  } catch (error) {
    if (requestId !== state.eventRequestId) return;
    showTimelineError(
      new Error(`Timeline could not load visible events: ${error.message || error}`)
    );
    throw error;
  }
}

async function poll() {
  try {
    const previousSessionId = state.session?.session_id;
    const [session, score] = await Promise.all([
      fetchJson("/api/session"),
      fetchJson("/api/score"),
    ]);
    state.session = session;
    state.score = score;
    if (state.session.session_id !== previousSessionId) {
      state.nextSequence = 0;
      state.queryKey = "";
      state.inspectionS = null;
      state.scoreRenderKey = "";
      state.scoreRenderer = null;
    }
    updateStatus();
    updateScore();
    await loadVisibleEvents();
  } catch (error) {
    showError(error);
    if (el("timeline-error").hidden) showTimelineError(error);
  } finally {
    state.pollTimer = window.setTimeout(poll, 750);
  }
}

function drawTimeline() {
  const canvas = el("timeline");
  const width = Math.max(300, canvas.clientWidth);
  const height = Math.max(300, canvas.clientHeight);
  const plotWidth = Math.max(1, width - PITCH_GUTTER_WIDTH);
  const dpr = window.devicePixelRatio || 1;
  canvas.width = Math.round(width * dpr);
  canvas.height = Math.round(height * dpr);
  const context = canvas.getContext("2d");
  context.scale(dpr, dpr);
  context.fillStyle = "#0c0f0e";
  context.fillRect(0, 0, width, height);

  const range = currentWindow();
  const noteHeight = height - PEDAL_HEIGHT;
  const rowHeight = noteHeight / (PITCH_MAX - PITCH_MIN + 1);
  for (let pitch = PITCH_MIN; pitch <= PITCH_MAX; pitch += 1) {
    const pitchClass = ((pitch % 12) + 12) % 12;
    const black = TIMELINE.isBlackKey(pitch);
    const y = (PITCH_MAX - pitch) * rowHeight;
    context.fillStyle = black ? "#0f1311" : pitchClass === 0 ? "#181d1a" : "#141816";
    context.fillRect(PITCH_GUTTER_WIDTH, y, plotWidth, Math.ceil(rowHeight));
    context.fillStyle = "#d7d2c7";
    context.fillRect(0, y, PITCH_GUTTER_WIDTH, Math.ceil(rowHeight));
    if (black) {
      context.fillStyle = "#111412";
      context.fillRect(
        PITCH_GUTTER_WIDTH * 0.34,
        y,
        PITCH_GUTTER_WIDTH * 0.66,
        Math.ceil(rowHeight)
      );
    }
    if (pitch === PITCH_MIN || pitch === PITCH_MAX || pitchClass === 0) {
      context.fillStyle = "#30342f";
      context.font = "8px ui-monospace, SFMono-Regular, Menlo, monospace";
      context.textBaseline = "middle";
      context.fillText(TIMELINE.midiName(pitch), 4, y + rowHeight / 2);
    }
  }
  context.strokeStyle = "#555a53";
  context.beginPath();
  context.moveTo(PITCH_GUTTER_WIDTH + 0.5, 0);
  context.lineTo(PITCH_GUTTER_WIDTH + 0.5, height);
  context.stroke();

  const tickStep = range.spanS <= 15 ? 1 : range.spanS <= 60 ? 5 : 10;
  const firstTick = Math.ceil(range.startS / tickStep) * tickStep;
  context.font = "10px ui-monospace, SFMono-Regular, Menlo, monospace";
  context.textBaseline = "top";
  for (let second = firstTick; second <= range.endS; second += tickStep) {
    const x =
      PITCH_GUTTER_WIDTH +
      ((second - range.startS) / range.spanS) * plotWidth;
    context.strokeStyle = second % 10 === 0 ? "#394039" : "#252a26";
    context.beginPath();
    context.moveTo(x + 0.5, 0);
    context.lineTo(x + 0.5, height);
    context.stroke();
    context.fillStyle = "#747b74";
    context.fillText(formatClock(second), x + 5, 5);
  }

  const sampleRate = Number(state.session?.session?.sample_rate_hz || 1);
  const notes = state.events.filter(
    (event) =>
      Number.isInteger(event.pitch) &&
      event.pitch >= PITCH_MIN &&
      event.pitch <= PITCH_MAX
  );
  const commitSample = Number(state.session?.horizons?.commit_sample || 0);
  const audioHeadSample = Number(
    state.session?.horizons?.audio_head_sample || 0
  );
  for (const event of notes) {
    const interval = TIMELINE.noteDisplayInterval(
      event,
      commitSample,
      audioHeadSample
    );
    const geometry = TIMELINE.noteGeometry(
      { ...event, offset_sample: interval.offsetSample },
      sampleRate,
      range.startS,
      range.spanS,
      plotWidth,
      PITCH_MIN,
      PITCH_MAX,
      noteHeight
    );
    const provisional = event.lifecycle === "provisional";
    context.fillStyle = provisional ? "rgba(255, 189, 106, .30)" : "#73e1c1";
    context.strokeStyle = provisional ? "#ffbd6a" : "#99f0d7";
    context.lineWidth = provisional ? 1 : 0.5;
    if (interval.open) {
      const stubWidth = Math.max(
        3,
        Math.min(geometry.width, (0.18 / range.spanS) * plotWidth)
      );
      context.fillRect(
        PITCH_GUTTER_WIDTH + geometry.x,
        geometry.y + 0.5,
        stubWidth,
        geometry.height
      );
      context.strokeRect(
        PITCH_GUTTER_WIDTH + geometry.x + 0.5,
        geometry.y + 1,
        stubWidth,
        Math.max(1, geometry.height - 1)
      );
      const tailStart = Math.max(0, geometry.x + stubWidth);
      const tailEnd = Math.min(plotWidth, geometry.x + geometry.width);
      if (tailEnd > tailStart) {
        context.strokeStyle = provisional
          ? "rgba(255, 189, 106, .30)"
          : "rgba(115, 225, 193, .30)";
        context.lineWidth = 1;
        context.setLineDash([3, 4]);
        context.beginPath();
        context.moveTo(
          PITCH_GUTTER_WIDTH + tailStart,
          geometry.y + geometry.height / 2
        );
        context.lineTo(
          PITCH_GUTTER_WIDTH + tailEnd,
          geometry.y + geometry.height / 2
        );
        context.stroke();
        context.setLineDash([]);
      }
      continue;
    }
    context.fillRect(
      PITCH_GUTTER_WIDTH + geometry.x,
      geometry.y + 0.5,
      geometry.width,
      geometry.height
    );
    context.strokeRect(
      PITCH_GUTTER_WIDTH + geometry.x + 0.5,
      geometry.y + 1,
      geometry.width,
      Math.max(1, geometry.height - 1)
    );
    if (geometry.x + geometry.width > plotWidth) {
      const edgeX = PITCH_GUTTER_WIDTH + plotWidth - 1;
      const middleY = geometry.y + geometry.height / 2;
      context.strokeStyle = provisional ? "#ffbd6a" : "#99f0d7";
      context.lineWidth = 1;
      context.beginPath();
      context.moveTo(edgeX - 4, geometry.y + 1);
      context.lineTo(edgeX, middleY);
      context.lineTo(edgeX - 4, geometry.y + geometry.height - 1);
      context.stroke();
    }
  }

  context.fillStyle = "#101512";
  context.fillRect(PITCH_GUTTER_WIDTH, noteHeight, plotWidth, PEDAL_HEIGHT);
  context.fillStyle = "#252a26";
  context.fillRect(0, noteHeight, PITCH_GUTTER_WIDTH, PEDAL_HEIGHT);
  context.fillStyle = "#aaa79f";
  context.font = "8px ui-monospace, SFMono-Regular, Menlo, monospace";
  context.textBaseline = "middle";
  context.fillText("PEDAL", 4, noteHeight + PEDAL_HEIGHT / 2);
  for (const event of state.events.filter((item) => Number.isInteger(item.controller))) {
    const onsetS = event.onset_sample / sampleRate;
    const offsetS =
      event.offset_sample == null ? range.endS : event.offset_sample / sampleRate;
    const x =
      PITCH_GUTTER_WIDTH +
      ((onsetS - range.startS) / range.spanS) * plotWidth;
    const endX =
      PITCH_GUTTER_WIDTH +
      ((offsetS - range.startS) / range.spanS) * plotWidth;
    const y = event.controller === 64 ? noteHeight + 5 : noteHeight + 21;
    context.fillStyle = event.controller === 64 ? "#76a9ff" : "#c596ff";
    context.fillRect(x, y, Math.max(2, endX - x), 11);
  }

  const commitS = commitSample / sampleRate;
  if (commitS >= range.startS && commitS <= range.endS) {
    const x =
      PITCH_GUTTER_WIDTH +
      ((commitS - range.startS) / range.spanS) * plotWidth;
    context.strokeStyle = "#76a9ff";
    context.lineWidth = 2;
    context.beginPath();
    context.moveTo(x, 0);
    context.lineTo(x, height);
    context.stroke();
  }

  const snapshot = TIMELINE.keyboardSnapshot(
    state.events,
    sampleRate,
    state.inspectionS
  );
  if (snapshot.mode === "pinned" && snapshot.sample != null) {
    const inspectionS = snapshot.sample / sampleRate;
    if (inspectionS >= range.startS && inspectionS <= range.endS) {
      const x =
        PITCH_GUTTER_WIDTH +
        ((inspectionS - range.startS) / range.spanS) * plotWidth;
      context.strokeStyle = "#ff816c";
      context.lineWidth = 1;
      context.beginPath();
      context.moveTo(x, 0);
      context.lineTo(x, height);
      context.stroke();
    }
  }

  const windowState = currentWindow();
  el("timeline-seek").max = String(windowState.maximumStart);
  el("timeline-seek").value = String(windowState.startS);
  el("timeline-seek").disabled = windowState.maximumStart === 0;
  el("range-label").textContent =
    `${formatClock(windowState.startS)} — ${formatClock(windowState.endS)}`;
  const pedalCount = state.events.filter((item) =>
    Number.isInteger(item.controller)
  ).length;
  el("visible-count").textContent =
    `${notes.length} ${notes.length === 1 ? "note" : "notes"}` +
    (pedalCount ? ` · ${pedalCount} pedal` : "");
  el("timeline-empty").hidden = state.events.length > 0;
  drawKeyboard(snapshot);
}

function packPcmBlock(samples, capture, firstSample, workletTime) {
  const buffer = new ArrayBuffer(BLOCK_HEADER_BYTES + samples.length * 2);
  const view = new DataView(buffer);
  for (const [index, value] of [..."ATPB"].entries()) {
    view.setUint8(index, value.charCodeAt(0));
  }
  view.setUint8(4, 1);
  view.setUint8(5, 1);
  view.setUint16(6, BLOCK_HEADER_BYTES, true);
  view.setUint32(8, capture.blockCount, true);
  view.setUint32(12, 0, true);
  view.setBigUint64(16, BigInt(firstSample), true);
  view.setUint32(24, samples.length, true);
  view.setUint32(28, capture.audioContext.sampleRate, true);
  view.setFloat64(32, performance.now(), true);
  view.setFloat64(40, workletTime, true);
  for (let index = 0; index < samples.length; index += 1) {
    const sample = Math.max(-1, Math.min(1, samples[index]));
    view.setInt16(
      BLOCK_HEADER_BYTES + index * 2,
      sample < 0 ? sample * 32768 : sample * 32767,
      true
    );
  }
  return buffer;
}

function sendControl(socket, type, fields = {}) {
  socket.send(JSON.stringify({ schema_version: STREAM_SCHEMA, type, ...fields }));
}

function openSocket(sampleRate, metadata) {
  return new Promise((resolve, reject) => {
    const protocol = location.protocol === "https:" ? "wss:" : "ws:";
    const socket = new WebSocket(`${protocol}//${location.host}/api/live`);
    socket.addEventListener("open", () => {
      sendControl(socket, "start", {
        sample_rate_hz: sampleRate,
        client_metadata: metadata,
      });
    });
    socket.addEventListener("message", (event) => {
      const message = JSON.parse(event.data);
      if (message.type === "ready") resolve({ socket, message });
      else if (message.type === "block_ack") {
        state.session && (state.session.horizons = message.horizons);
        state.capture && (state.capture.acknowledgedBlocks += 1);
        state.queryKey = "";
      } else if (message.type === "stopped") {
        state.capture?.stopResolver?.(message);
      } else if (message.type === "error") {
        reject(new Error(message.error || "Corrected capture failed."));
      }
    });
    socket.addEventListener("error", () => reject(new Error("Local WebSocket failed.")));
    socket.addEventListener("close", () => {
      if (!state.capture?.stopping) reject(new Error("Capture WebSocket closed."));
    });
  });
}

async function startMicrophone() {
  showError(null);
  if (!navigator.mediaDevices?.getUserMedia || !window.AudioWorkletNode) {
    showError(new Error("This browser does not provide AudioWorklet microphone capture."));
    return;
  }
  let stream;
  let audioContext;
  try {
    el("action-status").textContent = "Requesting microphone access…";
    stream = await navigator.mediaDevices.getUserMedia({
      audio: CAPTURE_CONSTRAINTS,
      video: false,
    });
    audioContext = new AudioContext();
    await audioContext.resume();
    await audioContext.audioWorklet.addModule("/capture-processor.js");
    el("action-status").textContent = "Warming both local models…";
    const trackSettings = stream.getAudioTracks()[0]?.getSettings() || {};
    const connection = await openSocket(audioContext.sampleRate, {
      started_at: new Date().toISOString(),
      requested_constraints: CAPTURE_CONSTRAINTS,
      actual_track_settings: trackSettings,
      user_agent: navigator.userAgent,
    });
    const source = audioContext.createMediaStreamSource(stream);
    const node = new AudioWorkletNode(audioContext, "atpiano-corrected-capture");
    const muted = audioContext.createGain();
    muted.gain.value = 0;
    const capture = {
      stream,
      audioContext,
      source,
      node,
      muted,
      socket: connection.socket,
      frameCount: 0,
      blockCount: 0,
      acknowledgedBlocks: 0,
      maxBufferedBytes: 0,
      stoppedFrameCount: null,
      workletStopResolver: null,
      stopResolver: null,
      stopping: false,
    };
    state.capture = capture;
    node.port.onmessage = (event) => {
      if (event.data.type === "chunk") {
        const samples = new Float32Array(event.data.samples);
        if (event.data.firstSample !== capture.frameCount) {
          showError(new Error("Browser source sample sequence became discontinuous."));
          stopMicrophone();
          return;
        }
        if (
          capture.socket.readyState !== WebSocket.OPEN ||
          capture.socket.bufferedAmount > MAX_WEBSOCKET_BUFFER_BYTES
        ) {
          showError(new Error("Local inference cannot keep up with microphone capture."));
          stopMicrophone();
          return;
        }
        capture.socket.send(
          packPcmBlock(samples, capture, event.data.firstSample, event.data.workletTime)
        );
        capture.maxBufferedBytes = Math.max(
          capture.maxBufferedBytes,
          capture.socket.bufferedAmount
        );
        capture.frameCount += samples.length;
        capture.blockCount += 1;
        updateStatus();
      } else if (event.data.type === "stopped") {
        capture.stoppedFrameCount = event.data.frameCount;
        capture.workletStopResolver?.(true);
      }
    };
    source.connect(node);
    node.connect(muted);
    muted.connect(audioContext.destination);
    state.queryKey = "";
    updateControls();
  } catch (error) {
    stream?.getTracks().forEach((track) => track.stop());
    if (audioContext && audioContext.state !== "closed") await audioContext.close();
    state.capture = null;
    showError(error);
    updateControls();
  }
}

async function stopMicrophone() {
  const capture = state.capture;
  if (!capture || capture.stopping) return;
  capture.stopping = true;
  updateControls();
  el("action-status").textContent = "Flushing the browser sample tail…";
  const workletStopped = new Promise((resolve) => {
    capture.workletStopResolver = resolve;
  });
  capture.node.port.postMessage({ type: "stop" });
  const acknowledged = await Promise.race([
    workletStopped,
    new Promise((resolve) => window.setTimeout(() => resolve(false), 1500)),
  ]);
  if (!acknowledged || capture.stoppedFrameCount !== capture.frameCount) {
    showError(new Error("The browser could not close a complete sample sequence."));
    capture.socket.close();
  } else {
    el("action-status").textContent = "Settling the bounded correction tail…";
    const serverStopped = new Promise((resolve) => {
      capture.stopResolver = resolve;
    });
    sendControl(capture.socket, "stop", {
      frame_count: capture.frameCount,
      block_count: capture.blockCount,
    });
    const result = await Promise.race([
      serverStopped,
      new Promise((resolve) => window.setTimeout(() => resolve(null), 90000)),
    ]);
    if (!result) showError(new Error("The local server did not finish Stop in time."));
  }
  capture.stream.getTracks().forEach((track) => track.stop());
  capture.source.disconnect();
  capture.node.disconnect();
  capture.muted.disconnect();
  await capture.audioContext.close();
  capture.socket.close();
  state.capture = null;
  state.queryKey = "";
  updateControls();
  await pollOnce();
}

async function pollOnce() {
  const [session, score] = await Promise.all([
    fetchJson("/api/session"),
    fetchJson("/api/score"),
  ]);
  state.session = session;
  state.score = score;
  updateStatus();
  updateScore();
  await loadVisibleEvents(true);
}

async function startReplay() {
  showError(null);
  try {
    state.session = await fetchJson("/api/replay", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    });
    state.nextSequence = 0;
    state.queryKey = "";
    state.inspectionS = null;
    updateStatus();
  } catch (error) {
    showError(error);
  }
}

function wireInteractions() {
  el("start-microphone").addEventListener("click", startMicrophone);
  el("stop-microphone").addEventListener("click", stopMicrophone);
  el("start-replay").addEventListener("click", startReplay);
  el("generate-score").addEventListener("click", generateScore);
  el("show-roll").addEventListener("change", (event) => {
    state.showRoll = event.target.checked;
    updateViewVisibility();
    if (state.showRoll) drawTimeline();
  });
  el("show-keyboard").addEventListener("change", (event) => {
    state.showKeyboard = event.target.checked;
    updateViewVisibility();
    if (state.showKeyboard) drawTimeline();
  });
  el("show-score").addEventListener("change", (event) => {
    state.showScore = event.target.checked;
    updateViewVisibility();
    if (state.showScore) updateScore();
  });
  el("window-size").addEventListener("change", (event) => {
    state.windowS = Number(event.target.value);
    state.queryKey = "";
    loadVisibleEvents(true).catch(showError);
  });
  el("follow-head").addEventListener("change", (event) => {
    state.follow = event.target.checked;
    state.queryKey = "";
    loadVisibleEvents(true).catch(showError);
  });
  el("timeline-seek").addEventListener("input", (event) => {
    state.follow = false;
    el("follow-head").checked = false;
    state.seekS = Number(event.target.value);
    state.queryKey = "";
    loadVisibleEvents(true).catch(showError);
  });
  el("timeline").addEventListener("click", (event) => {
    if (event.offsetX < PITCH_GUTTER_WIDTH) return;
    const range = currentWindow();
    const plotWidth = Math.max(
      1,
      el("timeline").clientWidth - PITCH_GUTTER_WIDTH
    );
    const position = Math.max(
      0,
      Math.min(1, (event.offsetX - PITCH_GUTTER_WIDTH) / plotWidth)
    );
    pinInspection(range.startS + position * range.spanS);
  });
  el("inspection-time").addEventListener("input", (event) => {
    pinInspection(Number(event.target.value));
  });
  el("follow-latest").addEventListener("click", () => {
    state.inspectionS = null;
    state.follow = true;
    el("follow-head").checked = true;
    state.queryKey = "";
    loadVisibleEvents(true).catch(showError);
  });
  window.addEventListener("resize", drawTimeline);
}

async function boot() {
  buildKeyboard();
  updateViewVisibility();
  wireInteractions();
  drawTimeline();
  try {
    state.config = await fetchJson("/api/config");
    updateControls();
    await pollOnce();
  } catch (error) {
    showError(error);
  }
  poll();
}

boot();

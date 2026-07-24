"use strict";

const MAX_CAPTURE_SECONDS = 120;
const LIVE_STREAM_SCHEMA = "atpiano.live-stream.v1";
const LIVE_BLOCK_HEADER_BYTES = 48;
const MAX_WEBSOCKET_BUFFER_BYTES = 4 * 1024 * 1024;
const LIVE_VIEW_SECONDS = 10;
const CAPTURE_CONSTRAINTS = {
  channelCount: 1,
  echoCancellation: false,
  noiseSuppression: false,
  autoGainControl: false,
};

const state = {
  mode: "review",
  runId: null,
  run: null,
  scores: null,
  reference: [],
  prediction: [],
  events: [],
  duration: 1,
  zoom: 110,
  showReference: true,
  showPrediction: true,
  reviewWired: false,
  notationWired: false,
  notation: null,
  oracle: null,
  activeOracleLane: "audio",
  scoreRenderers: {},
  capture: null,
  take: null,
  recordingUrl: null,
  live: {
    events: new Map(),
    audioHeadS: 0,
    sampleRate: 0,
    windowCount: 0,
    recentPitches: [],
    highlightedPitches: new Map(),
    animation: null,
  },
};

const noteNames = ["C", "C♯", "D", "E♭", "E", "F", "F♯", "G", "A♭", "A", "B♭", "B"];

function artifact(name) {
  if (state.runId) {
    return `/api/runs/${encodeURIComponent(state.runId)}/artifacts/${encodeURIComponent(name)}`;
  }
  return `/artifacts/${encodeURIComponent(name)}`;
}

function runApi(name) {
  if (!state.runId) throw new Error("This action requires the local workbench.");
  return `/api/runs/${encodeURIComponent(state.runId)}/${name}`;
}

async function fetchJson(name) {
  const response = await fetch(artifact(name));
  if (!response.ok) throw new Error(`${name}: HTTP ${response.status}`);
  return response.json();
}

async function fetchJsonl(name) {
  const response = await fetch(artifact(name));
  if (!response.ok) {
    if (response.status === 404) return [];
    throw new Error(`${name}: HTTP ${response.status}`);
  }
  const text = await response.text();
  return text
    .split("\n")
    .filter(Boolean)
    .map((line) => JSON.parse(line));
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function pitchName(pitch) {
  return `${noteNames[pitch % 12]}${Math.floor(pitch / 12) - 1}`;
}

function formatF1(value) {
  return value == null ? "n/a" : value.toFixed(3);
}

function formatSeconds(value) {
  return value == null ? "n/a" : `${value.toFixed(3)} s`;
}

function formatClock(seconds) {
  const minutes = Math.floor(seconds / 60);
  const remainder = seconds - minutes * 60;
  return `${minutes}:${remainder.toFixed(1).padStart(4, "0")}`;
}

function metric(label, value, detail) {
  return `<div class="metric"><span>${escapeHtml(label)}</span><strong>${escapeHtml(
    value
  )}</strong><span>${escapeHtml(detail)}</span></div>`;
}

function renderMetrics() {
  const scores = state.scores;
  const latency = scores.latency || {};
  const visible = latency.reference_onset_to_first_visible_s || {};
  const committed = latency.reference_onset_to_commit_s || {};
  const live = scores.live_reconciliation;
  const qualityLabel = scores.quality_available === false ? "No aligned reference" : "aligned MIDI";
  const metrics = [
    metric("Onset F1", formatF1(scores.onset?.["50_ms"]?.f1), "±50 ms matching tolerance"),
    metric("Note + offset F1", formatF1(scores.note_with_offset?.f1), "20% duration / 50 ms floor"),
    metric("Frame F1", formatF1(scores.frame?.f1), `${scores.frame?.frame_hz || "—"} Hz activity grid`),
    metric("First visible p50", formatSeconds(visible.p50), `${visible.count || 0} reference-matched notes`),
    metric("Committed p95", formatSeconds(committed.p95), `${committed.count || 0} reference-matched notes`),
    metric("Reference notes", String(scores.reference_note_count ?? "—"), qualityLabel),
    metric("Estimated notes", String(scores.estimated_note_count ?? "—"), "final committed transcript"),
    metric(
      "Retraction rate",
      scores.retraction_rate == null ? "n/a" : `${(scores.retraction_rate * 100).toFixed(1)}%`,
      "of provisional emissions"
    ),
  ];
  if (live) {
    metrics.push(
      metric(
        "Live ↔ final matches",
        `${live.matched_note_count} / ${live.final_note_count}`,
        "same pitch and onset within 80 ms"
      ),
      metric("Final additions", String(live.final_additions), "notes absent from committed live view"),
      metric("Live removals", String(live.live_removals), "live notes absent from final pass"),
      metric(
        "Onset revision p50",
        formatSeconds(live.onset_change_s?.p50),
        `${live.onset_change_s?.count || 0} matched notes`
      )
    );
  }
  document.querySelector("#metric-grid").innerHTML = metrics.join("");
}

function renderLifecycle() {
  const counts = state.scores.lifecycle || {
    provisional: state.events.filter((event) => event.lifecycle === "provisional").length,
    committed: state.events.filter((event) => event.lifecycle === "committed").length,
    retracted: state.events.filter((event) => event.lifecycle === "retracted").length,
  };
  document.querySelector("#lifecycle").innerHTML = ["provisional", "committed", "retracted"]
    .map(
      (name) =>
        `<div class="life ${name}"><span>${name}</span><strong>${counts[name] || 0}</strong></div>`
    )
    .join("");
}

function renderProvenance() {
  const run = state.run;
  const rows = [
    ["Run", run.run_id],
    ["Input", run.input?.input_id],
    ["Mode", run.mode],
    ["Model", `Basic Pitch ${run.model?.package_version || "—"}`],
    ["Adapter", run.model?.adapter],
    ["Model SHA-256", run.model?.artifact_sha256],
    ["Audio SHA-256", run.input?.audio_sha256],
    ["Git revision", run.runtime?.git_revision],
  ];
  document.querySelector("#provenance").innerHTML = rows
    .filter(([, value]) => value != null)
    .map(([label, value]) => `<dt>${escapeHtml(label)}</dt><dd>${escapeHtml(value)}</dd>`)
    .join("");
}

function renderEvents() {
  document.querySelector("#event-count").textContent = `${state.events.length} events`;
  document.querySelector("#event-body").innerHTML = state.events
    .slice()
    .sort((a, b) => a.emitted_elapsed_s - b.emitted_elapsed_s)
    .map((event) => {
      const latency =
        event.source_to_emission_latency_s == null
          ? "n/a"
          : `${event.source_to_emission_latency_s.toFixed(3)} s`;
      return `<tr>
        <td>${event.emitted_elapsed_s.toFixed(3)} s</td>
        <td>${pitchName(event.pitch)} <span class="muted">(${event.pitch})</span></td>
        <td><span class="state ${event.lifecycle}">${event.lifecycle}</span></td>
        <td>${event.revision}</td>
        <td>${event.velocity ?? "—"}</td>
        <td>${latency}</td>
      </tr>`;
    })
    .join("");
}

function summaryPills(summary) {
  if (!summary) return '<span class="muted">No score imported yet.</span>';
  const values = [
    `${summary.measures ?? "—"} measures`,
    `${summary.pitched_note_elements ?? "—"} note elements`,
    `${summary.parts ?? "—"} parts`,
    `${summary.arpeggiate_marks ?? 0} arpeggio marks`,
  ];
  if (summary.time_signatures?.length) values.push(summary.time_signatures.join(", "));
  return values.map((value) => `<span>${escapeHtml(value)}</span>`).join("");
}

async function renderMusicXml(targetId, relativePath, rendererKey) {
  const target = document.querySelector(`#${targetId}`);
  if (!relativePath) {
    target.classList.add("placeholder");
    target.textContent =
      "Import Ivory MusicXML above to render this lane beside the local score.";
    return;
  }
  target.classList.remove("placeholder");
  target.textContent = "Rendering score…";
  if (!window.opensheetmusicdisplay?.OpenSheetMusicDisplay) {
    target.innerHTML =
      '<p class="score-error">The pinned score renderer could not load. ' +
      "The MusicXML download is still available.</p>";
    return;
  }
  try {
    const response = await fetch(artifact(relativePath), { cache: "no-store" });
    if (!response.ok) throw new Error(`MusicXML: HTTP ${response.status}`);
    const musicxml = await response.text();
    target.replaceChildren();
    const renderer = new window.opensheetmusicdisplay.OpenSheetMusicDisplay(target, {
      autoResize: true,
      backend: "svg",
      drawTitle: true,
      drawPartNames: true,
      drawingParameters: "compacttight",
    });
    state.scoreRenderers[rendererKey] = renderer;
    await renderer.load(musicxml);
    renderer.render();
  } catch (error) {
    target.innerHTML = `<p class="score-error">${escapeHtml(
      error.message || String(error)
    )}</p>`;
  }
}

function populateNotationOptions() {
  const selected = state.notation?.selected;
  if (!selected) return;
  document.querySelector("#notation-tempo").value = selected.tempo_bpm;
  document.querySelector(
    "#notation-meter"
  ).value = `${selected.meter_numerator}/${selected.meter_denominator}`;
  document.querySelector("#notation-first-beat").value = selected.first_beat_s;
  document.querySelector("#notation-key").value = selected.key;
  document.querySelector("#notation-quantization").value = selected.quantization;
  document.querySelector("#notation-split").value = selected.staff_split_pitch;
}

function renderHypotheses() {
  const hypotheses = state.notation?.hypotheses;
  if (!hypotheses) return;
  const rankedKeys = (hypotheses.key?.ranked_profiles || [])
    .slice(0, 3)
    .map((candidate) => `${candidate.key} ${candidate.correlation.toFixed(2)}`)
    .join(" · ");
  const tempo = hypotheses.tempo;
  const partituraMeter = tempo.partitura?.meter_numerator;
  document.querySelector("#notation-hypotheses").innerHTML = [
    `<div><span>Selected key</span><strong>${escapeHtml(
      state.notation.selected.key
    )}</strong><small>${escapeHtml(rankedKeys)}</small></div>`,
    `<div><span>Selected tempo</span><strong>${state.notation.selected.tempo_bpm.toFixed(
      1
    )} BPM</strong><small>raw onset estimate ${tempo.pretty_midi_raw_bpm.toFixed(
      1
    )}; half-time normalized</small></div>`,
    `<div><span>Meter confidence</span><strong>Manual default</strong><small>4/4 until confirmed${
      partituraMeter ? `; rejected Partitura candidate ${partituraMeter}/4` : ""
    }</small></div>`,
  ].join("");
}

async function renderNotationComparison() {
  if (!state.notation) return;
  populateNotationOptions();
  renderHypotheses();
  document.querySelector("#notation-status").textContent =
    `${state.notation.selected.key} · ${state.notation.selected.tempo_bpm.toFixed(1)} BPM · ` +
    `${state.notation.selected.meter_numerator}/${state.notation.selected.meter_denominator}`;
  document.querySelector("#local-score-summary").innerHTML = summaryPills(
    state.notation.summary
  );
  const localPath = state.notation.artifacts.musicxml;
  const localDownload = document.querySelector("#download-local-musicxml");
  localDownload.href = artifact(localPath);
  localDownload.download = `atpiano-${state.notation.variant_id}.musicxml`;
  await renderMusicXml("local-score", localPath, `local-${state.notation.variant_id}`);

  const lane = state.oracle?.lanes?.[state.activeOracleLane] || null;
  document.querySelector("#oracle-lane-title").textContent =
    state.activeOracleLane === "audio" ? "from WAV" : "from MIDI";
  document.querySelectorAll("[data-oracle-lane]").forEach((button) => {
    button.classList.toggle("active", button.dataset.oracleLane === state.activeOracleLane);
  });
  document.querySelector("#oracle-score-summary").innerHTML = summaryPills(lane?.summary);
  await renderMusicXml(
    "oracle-score",
    lane?.artifact || null,
    `oracle-${state.activeOracleLane}-${lane?.sha256 || "empty"}`
  );
  drawRoll();
}

async function loadNotation() {
  try {
    if (state.mode === "workbench") {
      const [notationResponse, oracleResponse] = await Promise.all([
        fetch(runApi("notation"), { cache: "no-store" }),
        fetch(runApi("oracle"), { cache: "no-store" }),
      ]);
      const notation = await notationResponse.json();
      const oracle = await oracleResponse.json();
      if (!notationResponse.ok) {
        throw new Error(notation.error || `Notation: HTTP ${notationResponse.status}`);
      }
      if (!oracleResponse.ok) {
        throw new Error(oracle.error || `Oracle: HTTP ${oracleResponse.status}`);
      }
      state.notation = notation;
      state.oracle = oracle;
    } else {
      state.notation = await fetchJson("notation/current.json");
      state.oracle = { lanes: {} };
    }
    await renderNotationComparison();
  } catch (error) {
    document.querySelector("#notation-status").textContent = "Score unavailable";
    document.querySelector("#local-score").innerHTML =
      `<p class="score-error">${escapeHtml(error.message || String(error))}</p>`;
  }
}

async function regenerateNotation(event) {
  event.preventDefault();
  if (!state.runId || state.mode !== "workbench") return;
  const meter = document.querySelector("#notation-meter").value.split("/").map(Number);
  const options = {
    tempo_bpm: Number(document.querySelector("#notation-tempo").value),
    meter_numerator: meter[0],
    meter_denominator: meter[1],
    first_beat_s: Number(document.querySelector("#notation-first-beat").value),
    key: document.querySelector("#notation-key").value.trim(),
    quantization: document.querySelector("#notation-quantization").value,
    staff_split_pitch: Number(document.querySelector("#notation-split").value),
  };
  const button = document.querySelector("#regenerate-notation");
  button.disabled = true;
  document.querySelector("#notation-status").textContent = "Regenerating score";
  try {
    const response = await fetch(runApi("notation"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(options),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || `Notation: HTTP ${response.status}`);
    state.notation = result;
    await renderNotationComparison();
  } catch (error) {
    showError(error);
  } finally {
    button.disabled = false;
  }
}

async function importOracle(lane, file) {
  if (!file || !state.runId) return;
  const safeFilename = file.name.replace(/[^\x20-\x7E]/g, "_");
  document.querySelector("#notation-status").textContent = `Importing Ivory ${lane} score`;
  try {
    const response = await fetch(runApi(`oracle/${lane}`), {
      method: "POST",
      headers: {
        "Content-Type": "application/vnd.recordare.musicxml+xml",
        "X-Atpiano-Filename": safeFilename,
      },
      body: file,
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || `Oracle import: HTTP ${response.status}`);
    state.oracle = result;
    state.activeOracleLane = lane;
    await renderNotationComparison();
  } catch (error) {
    showError(error);
  }
}

function wireNotationInteractions() {
  if (state.notationWired) return;
  state.notationWired = true;
  document.querySelector("#notation-options").addEventListener("submit", regenerateNotation);
  document.querySelector("#import-oracle-audio").addEventListener("change", (event) => {
    importOracle("audio", event.target.files?.[0]);
  });
  document.querySelector("#import-oracle-midi").addEventListener("change", (event) => {
    importOracle("midi", event.target.files?.[0]);
  });
  document.querySelectorAll("[data-oracle-lane]").forEach((button) => {
    button.addEventListener("click", async () => {
      state.activeOracleLane = button.dataset.oracleLane;
      await renderNotationComparison();
    });
  });
}

function drawRoll() {
  if (!state.run) return;
  const canvas = document.querySelector("#piano-roll");
  const scroller = document.querySelector("#roll-scroller");
  const dpr = window.devicePixelRatio || 1;
  const labelWidth = 58;
  const pitchMin = 21;
  const pitchMax = 108;
  const rowHeight = 6.5;
  const cssHeight = (pitchMax - pitchMin + 1) * rowHeight;
  const cssWidth = Math.max(scroller.clientWidth - 2, labelWidth + state.duration * state.zoom + 20);
  canvas.style.width = `${cssWidth}px`;
  canvas.style.height = `${cssHeight}px`;
  canvas.width = Math.round(cssWidth * dpr);
  canvas.height = Math.round(cssHeight * dpr);
  const context = canvas.getContext("2d");
  context.scale(dpr, dpr);
  context.fillStyle = "#0c0d0d";
  context.fillRect(0, 0, cssWidth, cssHeight);

  for (let pitch = pitchMin; pitch <= pitchMax; pitch += 1) {
    const y = (pitchMax - pitch) * rowHeight;
    const isC = pitch % 12 === 0;
    const isBlack = [1, 3, 6, 8, 10].includes(pitch % 12);
    context.fillStyle = isBlack ? "#101312" : "#151716";
    context.fillRect(labelWidth, y, cssWidth - labelWidth, rowHeight);
    context.strokeStyle = isC ? "#343834" : "#222522";
    context.beginPath();
    context.moveTo(labelWidth, y);
    context.lineTo(cssWidth, y);
    context.stroke();
    if (isC) {
      context.fillStyle = "#8f948e";
      context.font = "10px ui-monospace, monospace";
      context.fillText(pitchName(pitch), 10, y + rowHeight - 1);
    }
  }

  context.strokeStyle = "#2b2f2c";
  context.fillStyle = "#777c77";
  context.font = "10px ui-monospace, monospace";
  for (let second = 0; second <= Math.ceil(state.duration); second += 1) {
    const x = labelWidth + second * state.zoom;
    context.beginPath();
    context.moveTo(x, 0);
    context.lineTo(x, cssHeight);
    context.stroke();
    context.fillText(`${second}s`, x + 4, 12);
  }

  if (state.notation?.selected) {
    const selected = state.notation.selected;
    const beatDuration = 60 / selected.tempo_bpm;
    const measureBeats =
      selected.meter_numerator * (4 / selected.meter_denominator);
    let beatIndex = 0;
    for (
      let beatTime = selected.first_beat_s;
      beatTime <= state.duration;
      beatTime += beatDuration
    ) {
      const measurePosition = beatIndex % Math.max(1, Math.round(measureBeats));
      const isDownbeat = measurePosition === 0;
      const x = labelWidth + beatTime * state.zoom;
      context.strokeStyle = isDownbeat
        ? "rgba(83, 216, 208, 0.50)"
        : "rgba(83, 216, 208, 0.16)";
      context.lineWidth = isDownbeat ? 1.4 : 0.7;
      context.beginPath();
      context.moveTo(x, 0);
      context.lineTo(x, cssHeight);
      context.stroke();
      if (isDownbeat) {
        context.fillStyle = "#53d8d0";
        context.fillText(`m${Math.floor(beatIndex / measureBeats) + 1}`, x + 4, 26);
      }
      beatIndex += 1;
    }
  }

  function drawNotes(notes, fill, stroke, inset) {
    notes.forEach((note) => {
      const x = labelWidth + note.onset_s * state.zoom;
      const width = Math.max(2, (note.offset_s - note.onset_s) * state.zoom);
      const y = (pitchMax - note.pitch) * rowHeight + inset;
      context.fillStyle = fill;
      context.strokeStyle = stroke;
      context.lineWidth = 1;
      context.fillRect(x, y, width, rowHeight - inset * 2);
      context.strokeRect(x + 0.5, y + 0.5, Math.max(1, width - 1), rowHeight - inset * 2 - 1);
    });
  }

  if (state.showReference) {
    drawNotes(state.reference, "rgba(83, 216, 208, 0.18)", "#53d8d0", 0.5);
  }
  if (state.showPrediction) {
    drawNotes(state.prediction, "rgba(255, 122, 69, 0.68)", "#ff9a72", 1.7);
  }

  const audio = document.querySelector("#result-audio");
  if (Number.isFinite(audio.currentTime)) {
    const x = labelWidth + audio.currentTime * state.zoom;
    context.strokeStyle = "#f4efe4";
    context.lineWidth = 1.5;
    context.beginPath();
    context.moveTo(x, 0);
    context.lineTo(x, cssHeight);
    context.stroke();
  }
}

function wireReviewInteractions() {
  if (state.reviewWired) return;
  state.reviewWired = true;
  const audio = document.querySelector("#result-audio");
  const zoom = document.querySelector("#zoom");
  let animation = null;
  const animate = () => {
    drawRoll();
    if (!audio.paused) animation = requestAnimationFrame(animate);
  };
  audio.addEventListener("play", () => {
    if (animation) cancelAnimationFrame(animation);
    animate();
  });
  audio.addEventListener("pause", () => {
    if (animation) cancelAnimationFrame(animation);
    drawRoll();
  });
  audio.addEventListener("seeked", drawRoll);
  zoom.addEventListener("input", () => {
    state.zoom = Number(zoom.value);
    document.querySelector("#zoom-value").textContent = `${state.zoom} px/s`;
    drawRoll();
  });
  document.querySelector("#show-reference").addEventListener("change", (event) => {
    state.showReference = event.target.checked;
    drawRoll();
  });
  document.querySelector("#show-prediction").addEventListener("change", (event) => {
    state.showPrediction = event.target.checked;
    drawRoll();
  });
  window.addEventListener("resize", drawRoll);
}

function showError(error) {
  const fragment = document.querySelector("#error-template").content.cloneNode(true);
  const element = fragment.querySelector(".error");
  fragment.querySelector("span").textContent = error.message || String(error);
  document.body.appendChild(fragment);
  window.setTimeout(() => element.remove(), 8000);
}

async function loadRun() {
  const [run, scores, reference, prediction, events] = await Promise.all([
    fetchJson("run.json"),
    fetchJson("scores.json"),
    fetchJson("reference.json"),
    fetchJson("prediction.json"),
    fetchJsonl("events.jsonl"),
  ]);
  state.run = run;
  state.scores = scores;
  state.reference = reference.notes || [];
  state.prediction = prediction.notes || [];
  state.events = events;
  state.duration = Math.max(
    1,
    ...state.reference.map((note) => note.offset_s),
    ...state.prediction.map((note) => note.offset_s)
  );
  document.querySelector("#review").hidden = false;
  document.querySelector("#mode-badge").textContent = run.mode;
  document.querySelector("#model-name").textContent = `Basic Pitch ${run.model?.package_version || ""}`;
  document.querySelector("#result-audio").src = artifact(run.input.audio);
  document.querySelector("#download-oracle-audio").href = artifact(run.input.audio);
  document.querySelector("#download-oracle-audio").download =
    `${run.input?.input_id || "atpiano"}-original.wav`;
  document.querySelector("#download-oracle-midi").href = artifact(
    run.artifacts?.prediction_midi || "prediction.mid"
  );
  document.querySelector("#download-oracle-midi").download =
    `${run.input?.input_id || "atpiano"}-prediction.mid`;
  const referenceToggle = document.querySelector("#show-reference");
  referenceToggle.disabled = state.reference.length === 0;
  referenceToggle.checked = state.reference.length > 0;
  state.showReference = state.reference.length > 0;
  renderMetrics();
  renderLifecycle();
  renderProvenance();
  renderEvents();
  wireReviewInteractions();
  wireNotationInteractions();
  if (state.mode !== "workbench") {
    document.querySelector(".oracle-workflow").hidden = true;
    document.querySelectorAll("#notation-options input, #notation-options select").forEach(
      (input) => {
        input.disabled = true;
      }
    );
    document.querySelector("#regenerate-notation").hidden = true;
  }
  drawRoll();
  await loadNotation();
}

function setCaptureUi(recording) {
  document.querySelector("#start-recording").disabled = recording;
  document.querySelector("#stop-recording").disabled = !recording;
  document.querySelector("#capture-indicator").classList.toggle("active", recording);
}

function updateCaptureMeter(samples) {
  let peak = 0;
  for (const sample of samples) peak = Math.max(peak, Math.abs(sample));
  const percentage = Math.min(100, Math.max(1, Math.sqrt(peak) * 100));
  document.querySelector("#level-fill").style.width = `${percentage}%`;
}

function liveSend(socket, type, values = {}) {
  if (socket?.readyState !== WebSocket.OPEN) return false;
  socket.send(JSON.stringify({ schema_version: LIVE_STREAM_SCHEMA, type, ...values }));
  return true;
}

function resetLiveEvaluator() {
  state.live.events.clear();
  state.live.audioHeadS = 0;
  state.live.sampleRate = 0;
  state.live.windowCount = 0;
  state.live.recentPitches = [];
  state.live.highlightedPitches.clear();
  document.querySelector("#live-status").textContent = "Connecting";
  document.querySelector("#live-pitch-set").textContent = "Play to reveal pitches";
  document.querySelector("#live-audio-head").textContent = "0.0 s";
  document.querySelector("#live-window-count").textContent = "0";
  document.querySelector("#live-latency").textContent = "—";
  document.querySelector("#live-transport").textContent = "warming model";
  renderLiveKeyboard();
  drawLiveRoll();
}

function buildLiveKeyboard() {
  const keyboard = document.querySelector("#live-keyboard");
  keyboard.replaceChildren();
  for (let pitch = 21; pitch <= 108; pitch += 1) {
    const key = document.createElement("span");
    key.className = `live-key${[1, 3, 6, 8, 10].includes(pitch % 12) ? " black" : ""}`;
    key.dataset.pitch = String(pitch);
    key.title = `${pitchName(pitch)} · MIDI ${pitch}`;
    keyboard.appendChild(key);
  }
}

function renderLiveKeyboard() {
  const now = performance.now();
  document.querySelectorAll(".live-key").forEach((key) => {
    const highlight = state.live.highlightedPitches.get(Number(key.dataset.pitch));
    const visible = highlight && now - highlight.at < 1500;
    key.classList.toggle("active", Boolean(visible));
    key.classList.toggle("committed", Boolean(visible && highlight.lifecycle === "committed"));
  });
}

function drawLiveRoll() {
  const canvas = document.querySelector("#live-roll");
  if (!canvas) return;
  const dpr = window.devicePixelRatio || 1;
  const width = Math.max(320, canvas.clientWidth);
  const height = 360;
  if (canvas.width !== Math.round(width * dpr) || canvas.height !== Math.round(height * dpr)) {
    canvas.width = Math.round(width * dpr);
    canvas.height = Math.round(height * dpr);
  }
  const context = canvas.getContext("2d");
  context.setTransform(dpr, 0, 0, dpr, 0, 0);
  context.fillStyle = "#0c0d0d";
  context.fillRect(0, 0, width, height);

  const viewEnd = Math.max(LIVE_VIEW_SECONDS, state.live.audioHeadS + 0.25);
  const viewStart = viewEnd - LIVE_VIEW_SECONDS;
  const timeX = (seconds) => ((seconds - viewStart) / LIVE_VIEW_SECONDS) * width;
  const pitchY = (pitch) => ((108 - pitch) / 88) * height;
  const rowHeight = height / 88;

  for (let second = Math.ceil(viewStart); second <= viewEnd; second += 1) {
    const x = timeX(second);
    context.strokeStyle = second % 5 === 0 ? "#383d39" : "#202321";
    context.lineWidth = 1;
    context.beginPath();
    context.moveTo(x + 0.5, 0);
    context.lineTo(x + 0.5, height);
    context.stroke();
  }
  for (let pitch = 24; pitch <= 108; pitch += 12) {
    const y = pitchY(pitch);
    context.strokeStyle = "#292d2a";
    context.beginPath();
    context.moveTo(0, y);
    context.lineTo(width, y);
    context.stroke();
  }

  const events = [...state.live.events.values()].sort(
    (left, right) => left.onset_sample - right.onset_sample
  );
  for (const event of events) {
    const onset = event.onset_sample / state.live.sampleRate;
    const detectedOffset = event.offset_sample / state.live.sampleRate;
    const offset =
      event.lifecycle === "provisional"
        ? Math.max(onset + 0.06, state.live.audioHeadS)
        : Math.max(onset + 0.04, detectedOffset);
    if (offset < viewStart || onset > viewEnd || event.pitch < 21 || event.pitch > 108) continue;
    const x = timeX(Math.max(viewStart, onset));
    const endX = timeX(Math.min(viewEnd, offset));
    const y = pitchY(event.pitch);
    if (event.lifecycle === "retracted") {
      context.strokeStyle = "#9b83d5";
      context.strokeRect(x, y, Math.max(3, endX - x), Math.max(2, rowHeight - 1));
    } else {
      context.fillStyle = event.lifecycle === "committed" ? "#53d8d0" : "#f6c453";
      context.globalAlpha = event.lifecycle === "committed" ? 0.86 : 0.74;
      context.fillRect(x, y, Math.max(3, endX - x), Math.max(2, rowHeight - 1));
      context.globalAlpha = 1;
    }
  }

  const headX = timeX(state.live.audioHeadS);
  context.strokeStyle = "#f4efe4";
  context.lineWidth = 1.5;
  context.beginPath();
  context.moveTo(headX, 0);
  context.lineTo(headX, height);
  context.stroke();
  renderLiveKeyboard();
}

function animateLiveEvaluator() {
  drawLiveRoll();
  const capture = state.capture;
  if (capture && !capture.stopped) {
    state.live.animation = requestAnimationFrame(animateLiveEvaluator);
  }
}

function applyLiveEvents(message, socket) {
  state.live.audioHeadS = message.audio_head_sample / state.live.sampleRate;
  document.querySelector("#live-audio-head").textContent = `${state.live.audioHeadS.toFixed(1)} s`;
  state.live.windowCount += message.windows_processed;
  document.querySelector("#live-window-count").textContent = String(state.live.windowCount);
  const firstEvents = [];
  for (const event of message.events) {
    state.live.events.set(event.event_id, event);
    if (event.lifecycle !== "retracted") {
      state.live.highlightedPitches.set(event.pitch, {
        at: performance.now(),
        lifecycle: event.lifecycle,
      });
    }
    if (event.revision === 1 && event.lifecycle === "provisional") firstEvents.push(event);
  }
  if (firstEvents.length) {
    const newestOnset = Math.max(...firstEvents.map((event) => event.onset_sample));
    const cluster = [...state.live.events.values()]
      .filter(
        (event) =>
          event.lifecycle !== "retracted" &&
          Math.abs(event.onset_sample - newestOnset) / state.live.sampleRate <= 0.18
      )
      .map((event) => event.pitch);
    state.live.recentPitches = [...new Set(cluster)].sort((left, right) => left - right);
    document.querySelector("#live-pitch-set").textContent =
      state.live.recentPitches.map(pitchName).join(" · ") || "—";
    const latency = firstEvents[firstEvents.length - 1].source_to_emission_latency_s;
    document.querySelector("#live-latency").textContent =
      latency == null ? "—" : `${latency.toFixed(2)} s`;
  }
  drawLiveRoll();
  requestAnimationFrame(() => {
    liveSend(socket, "paint", {
      batch_id: message.batch_id,
      page_paint_ms: performance.now(),
      first_event_ids: firstEvents.map((event) => event.event_id),
    });
  });
}

function openLiveSocket(sampleRate, metadata) {
  return new Promise((resolve, reject) => {
    const scheme = window.location.protocol === "https:" ? "wss:" : "ws:";
    const socket = new WebSocket(`${scheme}//${window.location.host}/api/live`);
    let ready = false;
    const fail = (error) => {
      if (!ready) reject(error);
      else showError(error);
    };
    socket.addEventListener("open", () => {
      liveSend(socket, "start", {
        sample_rate_hz: sampleRate,
        client_metadata: metadata,
      });
    });
    socket.addEventListener("message", (event) => {
      if (typeof event.data !== "string") return;
      const message = JSON.parse(event.data);
      if (message.type === "ready") {
        ready = true;
        document.querySelector("#live-status").textContent = "Listening";
        document.querySelector("#live-transport").textContent = "continuous";
        resolve({ socket, ready: message });
      } else if (message.type === "block_ack") {
        if (state.capture) {
          state.capture.acknowledgedBlocks = message.sequence + 1;
          state.capture.serverFrames = message.received_source_frames;
        }
      } else if (message.type === "events") {
        applyLiveEvents(message, socket);
      } else if (message.type === "clock_pong") {
        const pageReceiveMs = performance.now();
        liveSend(socket, "clock_observation", {
          page_send_ms: message.page_send_ms,
          page_receive_ms: pageReceiveMs,
          host_receive_ns: message.host_receive_ns,
          host_send_ns: message.host_send_ns,
        });
      } else if (message.type === "stopped") {
        if (state.capture?.stopSocketResolver) {
          state.capture.stopSocketResolver(message);
        }
      } else if (message.type === "error") {
        fail(new Error(message.error || "Live recognition failed."));
      }
    });
    socket.addEventListener("error", () => fail(new Error("Live WebSocket connection failed.")));
    socket.addEventListener("close", () => {
      if (!ready) reject(new Error("Live WebSocket closed before the model was ready."));
    });
  });
}

function packLivePcmBlock(samples, capture, firstSample, workletTime) {
  const buffer = new ArrayBuffer(LIVE_BLOCK_HEADER_BYTES + samples.length * 2);
  const view = new DataView(buffer);
  for (const [index, value] of [..."ATPB"].entries()) {
    view.setUint8(index, value.charCodeAt(0));
  }
  view.setUint8(4, 1);
  view.setUint8(5, 1);
  view.setUint16(6, LIVE_BLOCK_HEADER_BYTES, true);
  view.setUint32(8, capture.chunkCount, true);
  view.setUint32(12, 0, true);
  view.setBigUint64(16, BigInt(firstSample), true);
  view.setUint32(24, samples.length, true);
  view.setUint32(28, capture.audioContext.sampleRate, true);
  view.setFloat64(32, performance.now(), true);
  view.setFloat64(40, workletTime, true);
  for (let index = 0; index < samples.length; index += 1) {
    const sample = Math.max(-1, Math.min(1, samples[index]));
    view.setInt16(
      LIVE_BLOCK_HEADER_BYTES + index * 2,
      sample < 0 ? sample * 32768 : sample * 32767,
      true
    );
  }
  return buffer;
}

function flattenChunks(chunks, frameCount) {
  const samples = new Float32Array(frameCount);
  let cursor = 0;
  for (const chunk of chunks) {
    samples.set(chunk, cursor);
    cursor += chunk.length;
  }
  return samples;
}

function encodeWav(samples, sampleRate) {
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);
  const writeAscii = (offset, value) => {
    for (let index = 0; index < value.length; index += 1) {
      view.setUint8(offset + index, value.charCodeAt(index));
    }
  };
  writeAscii(0, "RIFF");
  view.setUint32(4, 36 + samples.length * 2, true);
  writeAscii(8, "WAVE");
  writeAscii(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeAscii(36, "data");
  view.setUint32(40, samples.length * 2, true);
  for (let index = 0; index < samples.length; index += 1) {
    const sample = Math.max(-1, Math.min(1, samples[index]));
    view.setInt16(44 + index * 2, sample < 0 ? sample * 32768 : sample * 32767, true);
  }
  return new Blob([buffer], { type: "audio/wav" });
}

function drawRecordingWaveform(samples) {
  const canvas = document.querySelector("#recording-waveform");
  const dpr = window.devicePixelRatio || 1;
  const width = Math.max(300, canvas.clientWidth);
  const height = 128;
  canvas.width = Math.round(width * dpr);
  canvas.height = Math.round(height * dpr);
  const context = canvas.getContext("2d");
  context.scale(dpr, dpr);
  context.fillStyle = "#0c0d0d";
  context.fillRect(0, 0, width, height);
  context.strokeStyle = "#343834";
  context.beginPath();
  context.moveTo(0, height / 2);
  context.lineTo(width, height / 2);
  context.stroke();
  context.strokeStyle = "#53d8d0";
  context.lineWidth = 1;
  context.beginPath();
  const framesPerPixel = Math.max(1, Math.floor(samples.length / width));
  for (let x = 0; x < width; x += 1) {
    let minimum = 1;
    let maximum = -1;
    const start = x * framesPerPixel;
    const end = Math.min(samples.length, start + framesPerPixel);
    for (let index = start; index < end; index += 1) {
      minimum = Math.min(minimum, samples[index]);
      maximum = Math.max(maximum, samples[index]);
    }
    context.moveTo(x + 0.5, (1 - maximum) * height * 0.5);
    context.lineTo(x + 0.5, (1 - minimum) * height * 0.5);
  }
  context.stroke();
}

async function startRecording() {
  discardRecording();
  if (!navigator.mediaDevices?.getUserMedia || !window.AudioWorkletNode) {
    showError(new Error("This browser does not provide the required Web Audio microphone APIs."));
    return;
  }
  setCaptureUi(true);
  resetLiveEvaluator();
  document.querySelector("#capture-status").textContent = "Requesting microphone access…";
  let stream = null;
  let audioContext = null;
  let capture = null;
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      audio: CAPTURE_CONSTRAINTS,
      video: false,
    });
    audioContext = new AudioContext();
    await audioContext.resume();
    await audioContext.audioWorklet.addModule("/capture-processor.js");
    const source = audioContext.createMediaStreamSource(stream);
    const captureNode = new AudioWorkletNode(audioContext, "atpiano-capture");
    const mutedOutput = audioContext.createGain();
    mutedOutput.gain.value = 0;
    const trackSettings = stream.getAudioTracks()[0]?.getSettings() || {};
    capture = {
      stream,
      audioContext,
      source,
      captureNode,
      mutedOutput,
      chunks: [],
      frameCount: 0,
      chunkCount: 0,
      startedAt: new Date().toISOString(),
      stopped: false,
      sequenceError: false,
      stopFrameCount: null,
      stopResolver: null,
      stopSocketResolver: null,
      animation: null,
      clockInterval: null,
      websocket: null,
      jobId: null,
      acknowledgedBlocks: 0,
      serverFrames: 0,
      transportError: null,
    };
    state.capture = capture;
    captureNode.port.onmessage = (event) => {
      if (event.data.type === "chunk") {
        const samples = new Float32Array(event.data.samples);
        if (event.data.firstSample !== capture.frameCount) {
          capture.sequenceError = true;
          showError(new Error("The browser audio sample sequence was discontinuous."));
        }
        if (
          !capture.websocket ||
          capture.websocket.readyState !== WebSocket.OPEN ||
          capture.websocket.bufferedAmount > MAX_WEBSOCKET_BUFFER_BYTES
        ) {
          capture.transportError = "The live transport could not keep up with capture.";
          showError(new Error(capture.transportError));
          stopRecording();
          return;
        }
        const block = packLivePcmBlock(
          samples,
          capture,
          event.data.firstSample,
          event.data.workletTime
        );
        capture.websocket.send(block);
        capture.chunks.push(samples);
        capture.frameCount += samples.length;
        capture.chunkCount += 1;
        updateCaptureMeter(samples);
      } else if (event.data.type === "stopped") {
        capture.stopFrameCount = event.data.frameCount;
        if (capture.stopResolver) capture.stopResolver(true);
      }
    };
    document.querySelector("#capture-status").textContent = "Warming the local model…";
    const metadata = {
      schema_version: "atpiano.browser-capture.v1",
      started_at: capture.startedAt,
      requested_constraints: CAPTURE_CONSTRAINTS,
      actual_track_settings: {
        sampleRate: trackSettings.sampleRate ?? null,
        channelCount: trackSettings.channelCount ?? null,
        echoCancellation: trackSettings.echoCancellation ?? null,
        noiseSuppression: trackSettings.noiseSuppression ?? null,
        autoGainControl: trackSettings.autoGainControl ?? null,
        latency: trackSettings.latency ?? null,
      },
    };
    const connection = await openLiveSocket(audioContext.sampleRate, metadata);
    capture.websocket = connection.socket;
    capture.jobId = connection.ready.job_id;
    state.live.sampleRate = audioContext.sampleRate;
    capture.clockInterval = window.setInterval(() => {
      liveSend(capture.websocket, "clock_ping", { page_send_ms: performance.now() });
    }, 2000);
    liveSend(capture.websocket, "clock_ping", { page_send_ms: performance.now() });
    source.connect(captureNode);
    captureNode.connect(mutedOutput);
    mutedOutput.connect(audioContext.destination);
    document.querySelector("#capture-status").textContent = "Recognizing mono PCM live";
    const tick = () => {
      if (state.capture !== capture || capture.stopped) return;
      const elapsed = capture.frameCount / audioContext.sampleRate;
      document.querySelector("#capture-time").textContent = formatClock(elapsed);
      if (elapsed >= MAX_CAPTURE_SECONDS) {
        stopRecording();
        return;
      }
      capture.animation = requestAnimationFrame(tick);
    };
    tick();
    animateLiveEvaluator();
  } catch (error) {
    if (capture?.clockInterval) window.clearInterval(capture.clockInterval);
    if (capture?.websocket) capture.websocket.close();
    if (stream) stream.getTracks().forEach((track) => track.stop());
    if (audioContext && audioContext.state !== "closed") await audioContext.close();
    state.capture = null;
    setCaptureUi(false);
    document.querySelector("#live-status").textContent = "Unavailable";
    document.querySelector("#live-transport").textContent = "failed";
    document.querySelector("#capture-status").textContent = "Microphone unavailable";
    showError(error);
  }
}

async function stopRecording() {
  const capture = state.capture;
  if (!capture || capture.stopped) return;
  capture.stopped = true;
  document.querySelector("#capture-status").textContent = "Finishing recording…";
  const stopped = new Promise((resolve) => {
    capture.stopResolver = resolve;
  });
  capture.captureNode.port.postMessage({ type: "stop" });
  const acknowledged = await Promise.race([
    stopped,
    new Promise((resolve) => window.setTimeout(() => resolve(false), 1000)),
  ]);
  if (capture.animation) cancelAnimationFrame(capture.animation);
  if (state.live.animation) cancelAnimationFrame(state.live.animation);
  if (capture.clockInterval) window.clearInterval(capture.clockInterval);
  const trackSettings = capture.stream.getAudioTracks()[0]?.getSettings() || {};

  if (
    !acknowledged ||
    capture.sequenceError ||
    capture.stopFrameCount !== capture.frameCount ||
    capture.transportError
  ) {
    capture.websocket?.close();
    capture.stream.getTracks().forEach((track) => track.stop());
    await capture.audioContext.close();
    setCaptureUi(false);
    state.capture = null;
    document.querySelector("#capture-status").textContent = "Recording was incomplete";
    showError(
      new Error(capture.transportError || "The browser audio sample sequence was incomplete.")
    );
    return;
  }
  if (capture.frameCount === 0) {
    capture.websocket?.close();
    capture.stream.getTracks().forEach((track) => track.stop());
    await capture.audioContext.close();
    setCaptureUi(false);
    state.capture = null;
    document.querySelector("#capture-status").textContent = "No samples were captured";
    showError(new Error("The microphone did not produce any audio samples."));
    return;
  }
  document.querySelector("#capture-status").textContent = "Closing the live stream…";
  const socketStopped = new Promise((resolve) => {
    capture.stopSocketResolver = resolve;
  });
  liveSend(capture.websocket, "stop", {
    frame_count: capture.frameCount,
    block_count: capture.chunkCount,
    capture_elapsed_s: capture.frameCount / capture.audioContext.sampleRate,
  });
  const stoppedMessage = await Promise.race([
    socketStopped,
    new Promise((resolve) => window.setTimeout(() => resolve(null), 30000)),
  ]);
  capture.stream.getTracks().forEach((track) => track.stop());
  capture.source.disconnect();
  capture.captureNode.disconnect();
  capture.mutedOutput.disconnect();
  await capture.audioContext.close();
  setCaptureUi(false);
  document.querySelector("#start-recording").disabled = true;
  state.capture = null;
  if (!stoppedMessage) {
    document.querySelector("#capture-status").textContent = "Live finalization failed";
    showError(new Error("The local server did not acknowledge the complete live stream."));
    return;
  }

  const samples = flattenChunks(capture.chunks, capture.frameCount);
  const duration = capture.frameCount / capture.audioContext.sampleRate;
  const blob = encodeWav(samples, capture.audioContext.sampleRate);
  state.take = {
    blob,
    samples,
    metadata: {
      schema_version: "atpiano.browser-capture.v1",
      sample_rate_hz: capture.audioContext.sampleRate,
      frame_count: capture.frameCount,
      chunk_count: capture.chunkCount,
      capture_elapsed_s: duration,
      started_at: capture.startedAt,
      requested_constraints: CAPTURE_CONSTRAINTS,
      actual_track_settings: {
        sampleRate: trackSettings.sampleRate ?? null,
        channelCount: trackSettings.channelCount ?? null,
        echoCancellation: trackSettings.echoCancellation ?? null,
        noiseSuppression: trackSettings.noiseSuppression ?? null,
        autoGainControl: trackSettings.autoGainControl ?? null,
        latency: trackSettings.latency ?? null,
      },
    },
  };
  if (state.recordingUrl) URL.revokeObjectURL(state.recordingUrl);
  state.recordingUrl = URL.createObjectURL(blob);
  document.querySelector("#recording-preview").src = state.recordingUrl;
  document.querySelector("#take-meta").textContent =
    `${duration.toFixed(1)} s · ${capture.audioContext.sampleRate.toLocaleString()} Hz`;
  document.querySelector("#take-panel").hidden = false;
  document.querySelector("#capture-time").textContent = formatClock(duration);
  document.querySelector("#capture-status").textContent = "Running the exact final pass";
  document.querySelector("#live-status").textContent = "Reconciling";
  document.querySelector("#live-transport").textContent = "complete";
  drawRecordingWaveform(samples);
  await completeLiveJob(stoppedMessage.job_id);
}

function discardRecording() {
  if (state.capture) return;
  if (state.recordingUrl) URL.revokeObjectURL(state.recordingUrl);
  state.recordingUrl = null;
  state.take = null;
  document.querySelector("#recording-preview").removeAttribute("src");
  document.querySelector("#take-panel").hidden = true;
  document.querySelector("#job-panel").hidden = true;
  document.querySelector("#capture-status").textContent = "Ready for a new take";
  document.querySelector("#capture-time").textContent = "0:00.0";
  document.querySelector("#level-fill").style.width = "0";
}

async function pollJob(jobId) {
  while (true) {
    const response = await fetch(`/api/jobs/${encodeURIComponent(jobId)}`, {
      cache: "no-store",
    });
    if (!response.ok) throw new Error(`Job status: HTTP ${response.status}`);
    const job = await response.json();
    if (job.status === "queued") {
      document.querySelector("#job-title").textContent = "Waiting for the model";
      document.querySelector("#job-detail").textContent =
        "The local workbench runs one transcription at a time.";
    } else if (job.status === "transcribing") {
      document.querySelector("#job-title").textContent = "Transcribing on this Mac";
      document.querySelector("#job-detail").textContent =
        "Basic Pitch is decoding the complete recording. This usually takes a few seconds.";
    } else if (job.status === "failed") {
      throw new Error(job.error || "Transcription failed.");
    } else if (job.status === "complete") {
      return job;
    }
    await new Promise((resolve) => window.setTimeout(resolve, 750));
  }
}

async function completeLiveJob(jobId) {
  document.querySelector("#job-panel").hidden = false;
  document.querySelector(".spinner").hidden = false;
  document.querySelector("#job-title").textContent = "Reconciling the complete take";
  document.querySelector("#job-detail").textContent =
    "The untouched full-file adapter is replacing or confirming the rolling preview.";
  try {
    const completed = await pollJob(jobId);
    state.runId = completed.job_id;
    window.history.replaceState({}, "", completed.run_url);
    document.querySelector("#job-title").textContent = "Transcription complete";
    document.querySelector("#job-detail").textContent =
      "The live history and best final transcript are ready below.";
    document.querySelector(".spinner").hidden = true;
    document.querySelector("#capture-status").textContent = "Live take complete";
    document.querySelector("#live-status").textContent = "Finalized";
    await loadRun();
    document.querySelector("#start-recording").disabled = false;
    document.querySelector("#review").scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    document.querySelector("#job-panel").hidden = true;
    document.querySelector("#live-status").textContent = "Final pass failed";
    document.querySelector("#start-recording").disabled = false;
    showError(error);
  }
}

function wireRecorder() {
  document.querySelector("#start-recording").addEventListener("click", startRecording);
  document.querySelector("#stop-recording").addEventListener("click", stopRecording);
  document.querySelector("#discard-recording").addEventListener("click", discardRecording);
  buildLiveKeyboard();
  drawLiveRoll();
}

async function init() {
  try {
    const configResponse = await fetch("/api/config", { cache: "no-store" });
    if (!configResponse.ok) throw new Error(`Workbench configuration: HTTP ${configResponse.status}`);
    const config = await configResponse.json();
    state.mode = config.mode;
    const query = new URLSearchParams(window.location.search);
    state.runId = query.get("run");
    if (state.mode === "workbench") {
      document.querySelector("#recorder").hidden = false;
      document.querySelector("#page-kind").textContent = "workbench";
      document.querySelector("#mode-badge").textContent = "Ready to record";
      wireRecorder();
      if (state.runId) await loadRun();
    } else {
      state.runId = null;
      document.querySelector("#page-kind").textContent = "run review";
      await loadRun();
    }
  } catch (error) {
    showError(error);
  }
}

init();

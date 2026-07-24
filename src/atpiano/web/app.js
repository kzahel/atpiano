"use strict";

const state = {
  run: null,
  scores: null,
  reference: [],
  prediction: [],
  events: [],
  duration: 1,
  zoom: 110,
  showReference: true,
  showPrediction: true,
};

const noteNames = ["C", "C♯", "D", "E♭", "E", "F", "F♯", "G", "A♭", "A", "B♭", "B"];

function artifact(name) {
  return `/artifacts/${name}`;
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

function pitchName(pitch) {
  return `${noteNames[pitch % 12]}${Math.floor(pitch / 12) - 1}`;
}

function formatF1(value) {
  return value == null ? "n/a" : value.toFixed(3);
}

function formatSeconds(value) {
  return value == null ? "n/a" : `${value.toFixed(3)} s`;
}

function metric(label, value, detail) {
  return `<div class="metric"><span>${label}</span><strong>${value}</strong><span>${detail}</span></div>`;
}

function renderMetrics() {
  const scores = state.scores;
  const latency = scores.latency || {};
  const visible = latency.reference_onset_to_first_visible_s || {};
  const committed = latency.reference_onset_to_commit_s || {};
  document.querySelector("#metric-grid").innerHTML = [
    metric("Onset F1", formatF1(scores.onset?.["50_ms"]?.f1), "±50 ms matching tolerance"),
    metric("Note + offset F1", formatF1(scores.note_with_offset?.f1), "20% duration / 50 ms floor"),
    metric("Frame F1", formatF1(scores.frame?.f1), `${scores.frame?.frame_hz || "—"} Hz activity grid`),
    metric("First visible p50", formatSeconds(visible.p50), `${visible.count || 0} reference-matched notes`),
    metric("Committed p95", formatSeconds(committed.p95), `${committed.count || 0} reference-matched notes`),
    metric("Reference notes", String(scores.reference_note_count ?? "—"), "aligned MIDI"),
    metric("Estimated notes", String(scores.estimated_note_count ?? "—"), "final committed transcript"),
    metric(
      "Retraction rate",
      scores.retraction_rate == null ? "n/a" : `${(scores.retraction_rate * 100).toFixed(1)}%`,
      "of provisional emissions"
    ),
  ].join("");
}

function renderLifecycle() {
  const counts = state.scores.lifecycle || {
    provisional: state.events.filter((event) => event.lifecycle === "provisional").length,
    committed: state.events.filter((event) => event.lifecycle === "committed").length,
    retracted: state.events.filter((event) => event.lifecycle === "retracted").length,
  };
  document.querySelector("#lifecycle").innerHTML = ["provisional", "committed", "retracted"]
    .map((name) => `<div class="life ${name}"><span>${name}</span><strong>${counts[name] || 0}</strong></div>`)
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
    .map(([label, value]) => `<dt>${label}</dt><dd>${value}</dd>`)
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

function drawRoll() {
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

  const audio = document.querySelector("#audio");
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

function wireInteractions() {
  const audio = document.querySelector("#audio");
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
  fragment.querySelector("span").textContent = error.message;
  document.body.appendChild(fragment);
}

async function load() {
  try {
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
    document.querySelector("#mode-badge").textContent = run.mode;
    document.querySelector("#model-name").textContent = `Basic Pitch ${run.model?.package_version || ""}`;
    document.querySelector("#audio").src = artifact(run.input.audio);
    renderMetrics();
    renderLifecycle();
    renderProvenance();
    renderEvents();
    wireInteractions();
    drawRoll();
  } catch (error) {
    showError(error);
  }
}

load();


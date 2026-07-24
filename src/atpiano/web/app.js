"use strict";

const MAX_CAPTURE_SECONDS = 120;
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
  capture: null,
  take: null,
  recordingUrl: null,
};

const noteNames = ["C", "C♯", "D", "E♭", "E", "F", "F♯", "G", "A♭", "A", "B"];

function artifact(name) {
  if (state.runId) {
    return `/api/runs/${encodeURIComponent(state.runId)}/artifacts/${encodeURIComponent(name)}`;
  }
  return `/artifacts/${encodeURIComponent(name)}`;
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
  const qualityLabel = scores.quality_available === false ? "No aligned reference" : "aligned MIDI";
  document.querySelector("#metric-grid").innerHTML = [
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
  ].join("");
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
  const referenceToggle = document.querySelector("#show-reference");
  referenceToggle.disabled = state.reference.length === 0;
  referenceToggle.checked = state.reference.length > 0;
  state.showReference = state.reference.length > 0;
  renderMetrics();
  renderLifecycle();
  renderProvenance();
  renderEvents();
  wireReviewInteractions();
  drawRoll();
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
  document.querySelector("#capture-status").textContent = "Requesting microphone access…";
  let stream = null;
  let audioContext = null;
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      audio: CAPTURE_CONSTRAINTS,
      video: false,
    });
    audioContext = new AudioContext();
    await audioContext.audioWorklet.addModule("/capture-processor.js");
    const source = audioContext.createMediaStreamSource(stream);
    const captureNode = new AudioWorkletNode(audioContext, "atpiano-capture");
    const mutedOutput = audioContext.createGain();
    mutedOutput.gain.value = 0;
    source.connect(captureNode);
    captureNode.connect(mutedOutput);
    mutedOutput.connect(audioContext.destination);
    const capture = {
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
      stopResolver: null,
      animation: null,
    };
    captureNode.port.onmessage = (event) => {
      if (event.data.type === "chunk") {
        const samples = new Float32Array(event.data.samples);
        if (event.data.firstSample !== capture.frameCount) {
          showError(new Error("The browser audio sample sequence was discontinuous."));
        }
        capture.chunks.push(samples);
        capture.frameCount += samples.length;
        capture.chunkCount += 1;
        updateCaptureMeter(samples);
      } else if (event.data.type === "stopped" && capture.stopResolver) {
        capture.stopResolver();
      }
    };
    state.capture = capture;
    document.querySelector("#capture-status").textContent = "Recording mono PCM";
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
  } catch (error) {
    if (stream) stream.getTracks().forEach((track) => track.stop());
    if (audioContext && audioContext.state !== "closed") await audioContext.close();
    setCaptureUi(false);
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
  await Promise.race([
    stopped,
    new Promise((resolve) => window.setTimeout(resolve, 500)),
  ]);
  if (capture.animation) cancelAnimationFrame(capture.animation);
  capture.stream.getTracks().forEach((track) => track.stop());
  capture.source.disconnect();
  capture.captureNode.disconnect();
  capture.mutedOutput.disconnect();
  await capture.audioContext.close();
  setCaptureUi(false);
  state.capture = null;

  if (capture.frameCount === 0) {
    document.querySelector("#capture-status").textContent = "No samples were captured";
    showError(new Error("The microphone did not produce any audio samples."));
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
    },
  };
  if (state.recordingUrl) URL.revokeObjectURL(state.recordingUrl);
  state.recordingUrl = URL.createObjectURL(blob);
  document.querySelector("#recording-preview").src = state.recordingUrl;
  document.querySelector("#take-meta").textContent =
    `${duration.toFixed(1)} s · ${capture.audioContext.sampleRate.toLocaleString()} Hz`;
  document.querySelector("#take-panel").hidden = false;
  document.querySelector("#capture-time").textContent = formatClock(duration);
  document.querySelector("#capture-status").textContent = "Take ready to review";
  drawRecordingWaveform(samples);
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
  document.querySelector("#transcribe-recording").disabled = false;
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

async function transcribeRecording() {
  if (!state.take) return;
  const button = document.querySelector("#transcribe-recording");
  button.disabled = true;
  document.querySelector("#job-panel").hidden = false;
  document.querySelector(".spinner").hidden = false;
  document.querySelector("#job-title").textContent = "Uploading recording";
  document.querySelector("#job-detail").textContent = "Preparing a versioned local input.";
  try {
    const encodedMetadata = btoa(JSON.stringify(state.take.metadata));
    const response = await fetch("/api/transcriptions", {
      method: "POST",
      headers: {
        "Content-Type": "audio/wav",
        "X-Atpiano-Capture-Metadata": encodedMetadata,
      },
      body: state.take.blob,
    });
    const job = await response.json();
    if (!response.ok) throw new Error(job.error || `Upload failed: HTTP ${response.status}`);
    const completed = await pollJob(job.job_id);
    state.runId = completed.job_id;
    window.history.replaceState({}, "", completed.run_url);
    document.querySelector("#job-title").textContent = "Transcription complete";
    document.querySelector("#job-detail").textContent = "The recovered notes are ready below.";
    document.querySelector(".spinner").hidden = true;
    await loadRun();
    document.querySelector("#review").scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    document.querySelector("#job-panel").hidden = true;
    button.disabled = false;
    showError(error);
  }
}

function wireRecorder() {
  document.querySelector("#start-recording").addEventListener("click", startRecording);
  document.querySelector("#stop-recording").addEventListener("click", stopRecording);
  document.querySelector("#discard-recording").addEventListener("click", discardRecording);
  document.querySelector("#transcribe-recording").addEventListener("click", transcribeRecording);
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

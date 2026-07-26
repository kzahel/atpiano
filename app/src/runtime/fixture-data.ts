import type {
  Artifact,
  ArtifactAccess,
  EventRevision,
  Horizon,
  Job,
  RuntimeCapabilities,
  Session,
  Workspace,
} from "./atpiano-runtime.js";
import {
  FixtureRuntime,
  type FixtureSessionData,
} from "./fixture-runtime.js";

const schemaVersion = "atpiano.contract.v1" as const;
const workspaceId = "local";
const sampleRate = 48_000;
const primarySessionId = "20260726T100000-abcdef123456";
const hash = "d".repeat(64);

const workspace: Workspace = {
  schema_version: schemaVersion,
  workspace_id: workspaceId,
  name: "On this Mac",
  mode: "local",
  created_at: "2026-07-26T09:12:00Z",
  owner_user_id: null,
};

const capabilities: RuntimeCapabilities = {
  schema_version: schemaVersion,
  runtime_mode: "fixture",
  supported_schema_versions: [schemaVersion],
  supported_pcm_protocol_versions: ["atpiano.pcm.v1"],
  capture_sources: ["microphone", "replay"],
  score_available: true,
  recoverable_delete: true,
  max_pcm_block_frames: 1_048_576,
  max_event_range_samples: 5_760_000,
};

function session(
  sessionId: string,
  startedAt: string,
  frames: number,
  source: Session["source"],
  displayName: string,
  status: Session["status"] = "complete",
): Session {
  return {
    schema_version: schemaVersion,
    workspace_id: workspaceId,
    session_id: sessionId,
    status,
    source,
    sample_rate_hz: sampleRate,
    source_frame_count: frames,
    started_at: startedAt,
    completed_at: status === "complete" ? startedAt : null,
    active_capture_id: status === "active" ? `capture:${sessionId}` : null,
    current_transcription_run_id: `run:${sessionId}`,
    display_name: displayName,
    available_artifact_kinds:
      status === "complete"
        ? ["audio", "event-history", "midi", "musicxml"]
        : [],
  };
}

function horizon(value: Session, commitSample: number): Horizon {
  return {
    schema_version: schemaVersion,
    workspace_id: workspaceId,
    session_id: value.session_id,
    transcription_run_id: value.current_transcription_run_id!,
    sample_rate_hz: sampleRate,
    audio_head_sample: value.source_frame_count,
    provisional_sample: Math.max(commitSample, value.source_frame_count - 2_400),
    commit_sample: commitSample,
    recorded_at: value.started_at,
  };
}

function note(
  target: Session,
  index: number,
  pitch: number,
  onsetSeconds: number,
  durationSeconds: number,
  lifecycle: EventRevision["lifecycle"] = "committed",
): EventRevision {
  return {
    schema_version: schemaVersion,
    workspace_id: workspaceId,
    session_id: target.session_id,
    transcription_run_id: target.current_transcription_run_id!,
    event_id: `note:${target.session_id}:${index}`,
    revision: 1,
    lane: lifecycle === "committed" ? "commit" : "preview",
    kind: "note",
    lifecycle,
    onset_sample: Math.round(onsetSeconds * sampleRate),
    offset_sample: Math.round((onsetSeconds + durationSeconds) * sampleRate),
    offset_state: "closed",
    pitch,
    velocity: 68 + (index % 4) * 6,
    confidence: lifecycle === "committed" ? 0.94 : 0.76,
    supersedes_revision: null,
  };
}

function pedal(
  target: Session,
  index: number,
  onsetSeconds: number,
  durationSeconds: number,
): EventRevision {
  return {
    schema_version: schemaVersion,
    workspace_id: workspaceId,
    session_id: target.session_id,
    transcription_run_id: target.current_transcription_run_id!,
    event_id: `pedal:${target.session_id}:${index}`,
    revision: 1,
    lane: "commit",
    kind: "sustain",
    lifecycle: "committed",
    onset_sample: Math.round(onsetSeconds * sampleRate),
    offset_sample: Math.round((onsetSeconds + durationSeconds) * sampleRate),
    offset_state: "closed",
    pitch: null,
    velocity: 96,
    confidence: 0.97,
    supersedes_revision: null,
  };
}

function artifact(target: Session, kind: Artifact["kind"], filename: string): Artifact {
  return {
    schema_version: schemaVersion,
    workspace_id: workspaceId,
    session_id: target.session_id,
    artifact_id: `artifact:${target.session_id}:${kind}`,
    kind,
    media_type:
      kind === "musicxml"
        ? "application/vnd.recordare.musicxml+xml"
        : kind === "midi"
          ? "audio/midi"
          : "application/json",
    filename,
    sha256: hash,
    byte_count: kind === "musicxml" ? 82_104 : 4_096,
    source_horizon_sample: target.source_frame_count,
    created_at: target.completed_at ?? target.started_at,
    transcription_run_id: target.current_transcription_run_id,
    producing_job_id: kind === "musicxml" ? "job:fixture-score" : null,
    provenance: {
      schema_version: schemaVersion,
      application_version: "0.1.0",
      schema_versions: { contract: schemaVersion },
      adapter: "fixture-runtime",
      execution_backend: "deterministic",
      model_id: null,
      checkpoint_sha256: null,
      settings_sha256: null,
      source_artifact_sha256: [],
    },
  };
}

function record(
  value: Session,
  values: EventRevision[],
  withArtifacts = false,
): FixtureSessionData {
  const artifacts = withArtifacts
    ? [
        artifact(value, "midi", "session.mid"),
        artifact(value, "event-history", "session.jsonl"),
        artifact(value, "musicxml", "score.musicxml"),
      ]
    : [];
  const access = Object.fromEntries(
    artifacts.map((item): [string, ArtifactAccess] => [
      item.artifact_id,
      {
        schema_version: schemaVersion,
        workspace_id: workspaceId,
        session_id: value.session_id,
        artifact_id: item.artifact_id,
        media_type: item.media_type,
        download_name: item.filename,
        url: `data:text/plain,Deterministic%20${encodeURIComponent(item.filename)}`,
        expires_at: null,
      },
    ]),
  );
  return {
    session: value,
    horizon: horizon(value, Math.max(0, value.source_frame_count - sampleRate)),
    events: {
      schema_version: schemaVersion,
      workspace_id: workspaceId,
      session_id: value.session_id,
      start_sample: 0,
      end_sample: value.source_frame_count,
      items: values,
      next_cursor: null,
    },
    artifacts: {
      schema_version: schemaVersion,
      workspace_id: workspaceId,
      session_id: value.session_id,
      items: artifacts,
      next_cursor: null,
    },
    artifactAccess: access,
  };
}

const primary = session(
  primarySessionId,
  "2026-07-26T10:00:00Z",
  sampleRate * 42,
  "replay",
  "Morning progression",
);
const nocturne = session(
  "20260725T201500-bbbbbbbbbbbb",
  "2026-07-25T20:15:00Z",
  sampleRate * 27,
  "microphone",
  "Nocturne sketch",
);
const warmup = session(
  "20260724T074500-cccccccccccc",
  "2026-07-24T07:45:00Z",
  sampleRate * 18,
  "microphone",
  "Chromatic warm-up",
);

const primaryNotes = [
  note(primary, 1, 48, 1.2, 1.7),
  note(primary, 2, 55, 1.2, 1.7),
  note(primary, 3, 60, 1.2, 1.7),
  note(primary, 4, 52, 4.6, 1.3),
  note(primary, 5, 59, 4.6, 1.3),
  note(primary, 6, 64, 4.6, 1.3),
  note(primary, 7, 55, 8.1, 2.2),
  note(primary, 8, 62, 8.1, 2.2),
  note(primary, 9, 67, 8.1, 2.2),
  note(primary, 10, 60, 12.4, 0.8),
  note(primary, 11, 64, 13.35, 0.8),
  note(primary, 12, 67, 14.3, 0.8),
  note(primary, 13, 72, 15.25, 2.4),
  note(primary, 14, 76, 19.1, 1.4),
  note(primary, 15, 79, 21.0, 1.4),
  note(primary, 16, 84, 23.0, 2.7),
  note(primary, 17, 65, 35.4, 1.1, "provisional"),
  note(primary, 18, 69, 35.4, 1.1, "provisional"),
  pedal(primary, 1, 1.0, 9.5),
  pedal(primary, 2, 18.7, 7.4),
];

const nocturneNotes = [
  note(nocturne, 1, 45, 2, 3),
  note(nocturne, 2, 52, 2, 3),
  note(nocturne, 3, 57, 2, 3),
  note(nocturne, 4, 64, 5.5, 1),
  note(nocturne, 5, 65, 7.1, 1),
  note(nocturne, 6, 69, 9, 2.2),
  pedal(nocturne, 1, 1.8, 10.3),
];

const warmupNotes = Array.from({ length: 16 }, (_, index) =>
  note(warmup, index + 1, 48 + index, 0.8 + index * 0.9, 0.55),
);

const scoreJob: Job = {
  schema_version: schemaVersion,
  workspace_id: workspaceId,
  session_id: primary.session_id,
  job_id: "job:fixture-score",
  kind: "score",
  status: "complete",
  input_horizon_sample: primary.source_frame_count - sampleRate,
  created_at: "2026-07-26T10:00:43Z",
  started_at: "2026-07-26T10:00:43Z",
  completed_at: "2026-07-26T10:00:45Z",
  artifact_ids: [`artifact:${primary.session_id}:musicxml`],
  error: null,
};

export function createFixtureRuntime(): FixtureRuntime {
  return new FixtureRuntime({
    fixtureId: "deterministic-musical-loop-v1",
    capabilities,
    workspace,
    capture: {
      schema_version: schemaVersion,
      workspace_id: workspaceId,
      session_id: primary.session_id,
      capture_id: `capture:${primary.session_id}`,
      status: "recording",
      source: "replay",
      sample_rate_hz: sampleRate,
      accepted_through_sample: 0,
      started_at: primary.started_at,
      stopped_at: null,
      error_id: null,
    },
    sessions: [
      record(primary, primaryNotes, true),
      record(nocturne, nocturneNotes),
      record(warmup, warmupNotes),
    ],
    scoreJob,
    trashedAt: "2026-07-26T11:00:00Z",
  });
}

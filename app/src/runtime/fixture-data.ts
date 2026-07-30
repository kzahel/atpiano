import type {
  Artifact,
  ArtifactAccess,
  EventRevision,
  Horizon,
  Job,
  RuntimeCapabilities,
  ScoreVariantPage,
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
const scoreHash = "8ad10edb9214c4c428225789d5eb6b6f7611c87f48cc8526b42bf5ea5c411e1d";
const fixtureSteps = ["C", "E", "G", "B", "A", "F", "D", "G"] as const;
const fixtureAdditionalMeasures = Array.from({ length: 104 }, (_, index) => {
  const number = index + 17;
  const step = fixtureSteps[index % fixtureSteps.length]!;
  const authoredBreak = number === 61
    ? "<print new-page=\"yes\"/>"
    : "";
  const finalBarline = number === 120
    ? "<barline location=\"right\"><bar-style>light-heavy</bar-style></barline>"
    : "";
  return `    <measure number="${number}">
      ${authoredBreak}
      <note><pitch><step>${step}</step><octave>4</octave></pitch><duration>16</duration><voice>1</voice><type>whole</type><staff>1</staff></note>
      <backup><duration>16</duration></backup>
      <note><pitch><step>${step}</step><octave>3</octave></pitch><duration>16</duration><voice>2</voice><type>whole</type><staff>2</staff></note>
      ${finalBarline}
    </measure>`;
}).join("\n");

export const fixtureScoreMusicXml = `<?xml version="1.0" encoding="UTF-8"?>
<score-partwise version="4.0">
  <work><work-title>Morning progression</work-title></work>
  <part-list>
    <score-part id="P1">
      <part-name>Piano</part-name>
      <score-instrument id="P1-I1"><instrument-name>Piano</instrument-name></score-instrument>
      <midi-instrument id="P1-I1"><midi-channel>1</midi-channel><midi-program>1</midi-program></midi-instrument>
    </score-part>
  </part-list>
  <part id="P1">
    <measure number="1">
      <attributes>
        <divisions>4</divisions>
        <key><fifths>0</fifths></key>
        <time><beats>4</beats><beat-type>4</beat-type></time>
        <staves>2</staves>
        <clef number="1"><sign>G</sign><line>2</line></clef>
        <clef number="2"><sign>F</sign><line>4</line></clef>
      </attributes>
      <direction placement="above"><direction-type><metronome><beat-unit>quarter</beat-unit><per-minute>72</per-minute></metronome></direction-type></direction>
      <note><pitch><step>C</step><octave>4</octave></pitch><duration>16</duration><voice>1</voice><type>whole</type><staff>1</staff></note>
      <backup><duration>16</duration></backup>
      <note><pitch><step>C</step><octave>3</octave></pitch><duration>16</duration><voice>2</voice><type>whole</type><staff>2</staff></note>
    </measure>
    <measure number="2">
      <note><pitch><step>E</step><octave>4</octave></pitch><duration>16</duration><voice>1</voice><type>whole</type><staff>1</staff></note>
      <backup><duration>16</duration></backup>
      <note><pitch><step>E</step><octave>3</octave></pitch><duration>16</duration><voice>2</voice><type>whole</type><staff>2</staff></note>
    </measure>
    <measure number="3">
      <note><pitch><step>G</step><octave>4</octave></pitch><duration>16</duration><voice>1</voice><type>whole</type><staff>1</staff></note>
      <backup><duration>16</duration></backup>
      <note><pitch><step>G</step><octave>2</octave></pitch><duration>16</duration><voice>2</voice><type>whole</type><staff>2</staff></note>
    </measure>
    <measure number="4">
      <note><pitch><step>C</step><octave>5</octave></pitch><duration>16</duration><voice>1</voice><type>whole</type><staff>1</staff></note>
      <backup><duration>16</duration></backup>
      <note><pitch><step>C</step><octave>3</octave></pitch><duration>16</duration><voice>2</voice><type>whole</type><staff>2</staff></note>
    </measure>
    <measure number="5">
      <print new-system="yes"/>
      <note><pitch><step>A</step><octave>4</octave></pitch><duration>16</duration><voice>1</voice><type>whole</type><staff>1</staff></note>
      <backup><duration>16</duration></backup>
      <note><pitch><step>A</step><octave>2</octave></pitch><duration>16</duration><voice>2</voice><type>whole</type><staff>2</staff></note>
    </measure>
    <measure number="6">
      <note><pitch><step>F</step><octave>4</octave></pitch><duration>16</duration><voice>1</voice><type>whole</type><staff>1</staff></note>
      <backup><duration>16</duration></backup>
      <note><pitch><step>F</step><octave>3</octave></pitch><duration>16</duration><voice>2</voice><type>whole</type><staff>2</staff></note>
    </measure>
    <measure number="7">
      <note><pitch><step>D</step><octave>4</octave></pitch><duration>16</duration><voice>1</voice><type>whole</type><staff>1</staff></note>
      <backup><duration>16</duration></backup>
      <note><pitch><step>D</step><octave>3</octave></pitch><duration>16</duration><voice>2</voice><type>whole</type><staff>2</staff></note>
    </measure>
    <measure number="8">
      <note><pitch><step>G</step><octave>4</octave></pitch><duration>16</duration><voice>1</voice><type>whole</type><staff>1</staff></note>
      <backup><duration>16</duration></backup>
      <note><pitch><step>G</step><octave>2</octave></pitch><duration>16</duration><voice>2</voice><type>whole</type><staff>2</staff></note>
    </measure>
    <measure number="9">
      <print new-system="yes"/>
      <note><pitch><step>F</step><octave>4</octave></pitch><duration>16</duration><voice>1</voice><type>whole</type><staff>1</staff></note>
      <backup><duration>16</duration></backup>
      <note><pitch><step>F</step><octave>2</octave></pitch><duration>16</duration><voice>2</voice><type>whole</type><staff>2</staff></note>
    </measure>
    <measure number="10">
      <note><pitch><step>A</step><octave>4</octave></pitch><duration>16</duration><voice>1</voice><type>whole</type><staff>1</staff></note>
      <backup><duration>16</duration></backup>
      <note><pitch><step>A</step><octave>2</octave></pitch><duration>16</duration><voice>2</voice><type>whole</type><staff>2</staff></note>
    </measure>
    <measure number="11">
      <note><pitch><step>B</step><octave>4</octave></pitch><duration>16</duration><voice>1</voice><type>whole</type><staff>1</staff></note>
      <backup><duration>16</duration></backup>
      <note><pitch><step>B</step><octave>2</octave></pitch><duration>16</duration><voice>2</voice><type>whole</type><staff>2</staff></note>
    </measure>
    <measure number="12">
      <note><pitch><step>E</step><octave>5</octave></pitch><duration>16</duration><voice>1</voice><type>whole</type><staff>1</staff></note>
      <backup><duration>16</duration></backup>
      <note><pitch><step>E</step><octave>3</octave></pitch><duration>16</duration><voice>2</voice><type>whole</type><staff>2</staff></note>
    </measure>
    <measure number="13">
      <print new-system="yes"/>
      <note><pitch><step>D</step><octave>5</octave></pitch><duration>16</duration><voice>1</voice><type>whole</type><staff>1</staff></note>
      <backup><duration>16</duration></backup>
      <note><pitch><step>D</step><octave>3</octave></pitch><duration>16</duration><voice>2</voice><type>whole</type><staff>2</staff></note>
    </measure>
    <measure number="14">
      <note><pitch><step>C</step><octave>5</octave></pitch><duration>16</duration><voice>1</voice><type>whole</type><staff>1</staff></note>
      <backup><duration>16</duration></backup>
      <note><pitch><step>C</step><octave>3</octave></pitch><duration>16</duration><voice>2</voice><type>whole</type><staff>2</staff></note>
    </measure>
    <measure number="15">
      <note><pitch><step>G</step><octave>4</octave></pitch><duration>16</duration><voice>1</voice><type>whole</type><staff>1</staff></note>
      <backup><duration>16</duration></backup>
      <note><pitch><step>G</step><octave>2</octave></pitch><duration>16</duration><voice>2</voice><type>whole</type><staff>2</staff></note>
    </measure>
    <measure number="16">
      <note><pitch><step>C</step><octave>5</octave></pitch><duration>16</duration><voice>1</voice><type>whole</type><staff>1</staff></note>
      <backup><duration>16</duration></backup>
      <note><pitch><step>C</step><octave>3</octave></pitch><duration>16</duration><voice>2</voice><type>whole</type><staff>2</staff></note>
    </measure>
${fixtureAdditionalMeasures}
  </part>
</score-partwise>`;

const workspace: Workspace = {
  schema_version: schemaVersion,
  workspace_id: workspaceId,
  name: "On this device",
  mode: "local",
  created_at: "2026-07-26T09:12:00Z",
  owner_user_id: null,
  administrative_group_id: "group:fixture",
  home_profile_id: "profile:fixture",
};

const capabilities: RuntimeCapabilities = {
  schema_version: schemaVersion,
  runtime_mode: "fixture",
  supported_schema_versions: [schemaVersion],
  supported_pcm_protocol_versions: ["atpiano.pcm.v1"],
  capture_sources: ["microphone", "upload", "replay"],
  correction: {
    configured_mode: "delayed",
    default_mode: "delayed",
    reason: "deterministic fixture policy",
    backend_profile_path: null,
    backend_profile_status: "not-configured",
    backend_profile_id: null,
    backend_profile_recommendation: null,
  },
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
    created_by_user_id: null,
    performed_by_profile_id: "profile:fixture",
    display_name: displayName,
    recognized_note_count: 0,
    corrected_note_count: 0,
    correction_mode: "delayed",
    correction_profile_id: null,
    correction_reason: "deterministic fixture policy",
    available_artifact_kinds:
      status === "complete"
        ? [
            "audio",
            "event-history",
            "midi",
            "musicxml",
            "score-alignment",
          ]
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
        : kind === "audio"
          ? "audio/wav"
        : kind === "midi"
          ? "audio/midi"
          : "application/json",
    filename,
    sha256: kind === "musicxml" ? scoreHash : hash,
    byte_count: kind === "musicxml" ? 82_104 : 4_096,
    source_horizon_sample:
      kind === "musicxml" || kind === "score-alignment"
        ? Math.max(0, target.source_frame_count - sampleRate)
        : target.source_frame_count,
    created_at: target.completed_at ?? target.started_at,
    transcription_run_id: target.current_transcription_run_id,
    producing_job_id:
      kind === "musicxml" || kind === "score-alignment"
        ? "job:fixture-score"
        : null,
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
  const recognizedNoteCount = values.filter(
    (event) =>
      event.kind === "note" &&
      event.lifecycle !== "retracted",
  ).length;
  const correctedNoteCount = values.filter(
    (event) =>
      event.kind === "note" &&
      event.lifecycle === "committed",
  ).length;
  const summary = {
    ...value,
    recognized_note_count: recognizedNoteCount,
    corrected_note_count: correctedNoteCount,
  };
  const artifacts = withArtifacts
    ? [
        artifact(summary, "audio", "000000.wav"),
        artifact(summary, "midi", "session.mid"),
        artifact(summary, "event-history", "session.jsonl"),
        artifact(summary, "musicxml", "score.musicxml"),
        artifact(summary, "score-alignment", "alignment.json"),
      ]
    : [];
  const mappedNotes = values
    .filter(
      (event) =>
        event.kind === "note" &&
        event.lifecycle === "committed" &&
        event.pitch !== null &&
        event.offset_sample !== null,
    )
    .sort(
      (left, right) =>
        left.onset_sample - right.onset_sample ||
        left.pitch! - right.pitch! ||
        left.offset_sample! -
          left.onset_sample -
          (right.offset_sample! - right.onset_sample) ||
        left.event_id.localeCompare(right.event_id),
    );
  const alignmentRows = [
    ...mappedNotes.map((event, index) => ({
      source_index: index,
      event_id: event.event_id,
      pitch: event.pitch,
      onset_sample: event.onset_sample,
      offset_sample: event.offset_sample,
      status: "mapped",
      score_time_quarters: {
        numerator: index * 4,
        denominator: 1,
      },
    })),
    ...Array.from({ length: 104 }, (_, index) => {
      const sourceIndex = mappedNotes.length + index;
      const onsetSample = 1_152_000 + index * 7_000;
      return {
        source_index: sourceIndex,
        event_id: `fixture-score-note:${value.session_id}:${sourceIndex}`,
        pitch: 48 + (index % 24),
        onset_sample: onsetSample,
        offset_sample: onsetSample + 4_000,
        status: "mapped",
        score_time_quarters: {
          numerator: sourceIndex * 4,
          denominator: 1,
        },
      };
    }),
  ];
  const alignment = {
    schema_version: "atpiano.score-alignment.v2",
    session_id: value.session_id,
    sample_rate_hz: value.sample_rate_hz,
    musicxml: { sha256: scoreHash },
    mapping: {
      algorithm: "monotonic-exact-pitch-lcs-v1",
      source_order: "onset-sample,pitch,duration,source-index",
      score_order: "attack-quarters,pitch,output-index",
    },
    rows: alignmentRows,
  };
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
        url:
          item.kind === "musicxml"
            ? `data:application/vnd.recordare.musicxml+xml,${encodeURIComponent(fixtureScoreMusicXml)}`
          : item.kind === "score-alignment"
            ? `data:application/json,${encodeURIComponent(JSON.stringify(alignment))}`
            : `data:text/plain,Deterministic%20${encodeURIComponent(item.filename)}`,
        expires_at: null,
      },
    ]),
  );
  return {
    session: summary,
    horizon: horizon(
      summary,
      Math.max(0, summary.source_frame_count - sampleRate),
    ),
    events: {
      schema_version: schemaVersion,
      workspace_id: workspaceId,
      session_id: summary.session_id,
      start_sample: 0,
      end_sample: summary.source_frame_count,
      items: values,
      next_cursor: null,
    },
    artifacts: {
      schema_version: schemaVersion,
      workspace_id: workspaceId,
      session_id: summary.session_id,
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
  artifact_ids: [
    `artifact:${primary.session_id}:musicxml`,
    `artifact:${primary.session_id}:score-alignment`,
  ],
  error: null,
};

const scoreVariants: ScoreVariantPage = {
  schema_version: schemaVersion,
  workspace_id: workspaceId,
  session_id: primary.session_id,
  producer: {
    schema_version: "atpiano.score-producer.v1",
    pipeline_revision: 3,
    pipeline_fingerprint:
      "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    application_version: "0.1.0",
    application_revision: "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    application_dirty: false,
    execution: "pinned-runtime",
    adapter_schema: "atpiano.midi2score-adapter.v1",
    alignment_schema: "atpiano.score-alignment.v2",
    postprocessor_version: "deterministic-engraving-v2",
    model_repository_commit: "cccccccccccccccccccccccccccccccccccccccc",
    model_checkpoint_sha256:
      "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
  },
  freshness: {
    schema_version: "atpiano.score-freshness.v1",
    status: "current",
    reason: "current",
    current_pipeline_revision: 3,
    snapshot_pipeline_revision: 3,
    refresh_recommended: false,
  },
  items: [
    {
      schema_version: schemaVersion,
      workspace_id: workspaceId,
      session_id: primary.session_id,
      score_variant_id: "score-variant:fixture-automatic",
      role: "automatic",
      label: "Automatic clefs · Six flats",
      baseline_musicxml_artifact_id:
        `artifact:${primary.session_id}:musicxml`,
      baseline_alignment_artifact_id:
        `artifact:${primary.session_id}:score-alignment`,
      musicxml_artifact_id: `artifact:${primary.session_id}:musicxml`,
      alignment_artifact_id:
        `artifact:${primary.session_id}:score-alignment`,
      source_horizon_sample: primary.source_frame_count - sampleRate,
      clef_policy: "automatic",
      target_key_fifths: null,
      key_fifths: -6,
      available_enharmonic_fifths: 6,
      available_enharmonic_label:
        "Six sharps — F-sharp major / D-sharp minor",
      selected: true,
      needs_review: false,
      created_at: "2026-07-26T10:00:45Z",
    },
  ],
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
    scoreVariants,
    trashedAt: "2026-07-26T11:00:00Z",
  });
}

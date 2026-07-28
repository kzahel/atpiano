import type {
  Artifact,
  ArtifactAccess,
  ArtifactContent,
  ArtifactExportResult,
  ArtifactPage,
  AtpianoRuntime,
  Capture,
  CaptureStart,
  CaptureStop,
  DeleteSessionRequest,
  DeleteSessionResult,
  EventPage,
  EventRangeRequest,
  EventSubscriber,
  EventSubscription,
  Horizon,
  Job,
  PageRequest,
  PcmBlock,
  Profile,
  ProfileCreate,
  ProfilePage,
  RecordingImportStart,
  ReplayStart,
  RuntimeCapabilities,
  RuntimeRequest,
  ScoreJobStart,
  ScoreVariant,
  ScoreVariantPage,
  ScoreVariantRequest,
  Session,
  SessionAnnotation,
  SessionAnnotationPatch,
  SessionPage,
  SessionPerformerAttribution,
  SessionPerformerPatch,
  GroupPage,
  Workspace,
  WorkspacePage,
} from "./atpiano-runtime.js";
import { startBrowserArtifactExport } from "../lib/artifact-export.js";

export interface FixtureRuntimeData {
  readonly fixtureId: string;
  readonly capabilities: RuntimeCapabilities;
  readonly workspace: Workspace;
  readonly capture: Capture;
  readonly sessions: readonly FixtureSessionData[];
  readonly scoreJob: Job;
  readonly scoreVariants?: ScoreVariantPage;
  readonly trashedAt: string;
}

export interface FixtureSessionData {
  readonly session: Session;
  readonly horizon: Horizon;
  readonly events: EventPage;
  readonly artifacts: ArtifactPage;
  readonly artifactAccess: Readonly<Record<string, ArtifactAccess>>;
}

function assertRequest(request: RuntimeRequest): void {
  if (!request.requestId) {
    throw new Error("runtime request requires requestId");
  }
  if (request.signal?.aborted) {
    throw request.signal.reason ?? new DOMException("Aborted", "AbortError");
  }
}

function pageWindow<T>(
  items: readonly T[],
  request: PageRequest,
): T[] {
  if (request.cursor !== undefined) {
    throw new Error("fixture runtime has one page and rejects cursors");
  }
  const limit = request.limit ?? items.length;
  if (!Number.isInteger(limit) || limit < 1) {
    throw new Error("page limit must be a positive integer");
  }
  return items.slice(0, limit);
}

/**
 * Deterministic in-memory consumer of the same runtime contract used by local
 * and hosted adapters. It is a Phase 3 bring-up aid, not a test-only domain
 * shortcut: values still carry explicit workspace/session/capture IDs and
 * source-sample coordinates.
 */
export class FixtureRuntime implements AtpianoRuntime {
  readonly #data: FixtureRuntimeData;
  readonly #sessions: Map<string, FixtureSessionData>;
  #capture: Capture;
  #session: Session;
  #profiles: Profile[];
  #nextSample = 0;

  constructor(data: FixtureRuntimeData) {
    if (data.sessions.length === 0) {
      throw new Error("fixture runtime requires at least one session");
    }
    this.#data = data;
    this.#sessions = new Map(
      data.sessions.map((record) => [record.session.session_id, record]),
    );
    this.#capture = data.capture;
    this.#session = data.sessions[0]!.session;
    this.#profiles = [
      {
        schema_version: "atpiano.contract.v1",
        profile_id: data.workspace.home_profile_id ?? "profile:fixture",
        display_name: "Pianist",
        disabled: false,
        created_at: data.workspace.created_at,
        controller_role: "owner",
      },
    ];
  }

  async getCapabilities(request: RuntimeRequest): Promise<RuntimeCapabilities> {
    assertRequest(request);
    return this.#data.capabilities;
  }

  async listWorkspaces(request: PageRequest): Promise<WorkspacePage> {
    assertRequest(request);
    return {
      schema_version: "atpiano.contract.v1",
      items: pageWindow([this.#data.workspace], request),
      next_cursor: null,
    };
  }

  async listGroups(request: PageRequest): Promise<GroupPage> {
    assertRequest(request);
    return {
      schema_version: "atpiano.contract.v1",
      items: pageWindow([
        {
          schema_version: "atpiano.contract.v1",
          group_id:
            this.#data.workspace.administrative_group_id ?? "group:fixture",
          name: "Fixture household",
          kind: "household",
          default_space_audience: "group",
          default_space_role: "editor",
          created_at: this.#data.workspace.created_at,
          current_user_role: "owner",
        },
      ], request),
      next_cursor: null,
    };
  }

  async listProfiles(
    workspaceId: string,
    request: PageRequest,
  ): Promise<ProfilePage> {
    assertRequest(request);
    this.#assertWorkspace(workspaceId);
    return {
      schema_version: "atpiano.contract.v1",
      workspace_id: workspaceId,
      group_id:
        this.#data.workspace.administrative_group_id ?? "group:fixture",
      items: pageWindow(this.#profiles, request),
      next_cursor: null,
    };
  }

  async createProfile(
    input: ProfileCreate,
    request: RuntimeRequest,
  ): Promise<Profile> {
    assertRequest(request);
    const profile: Profile = {
      schema_version: "atpiano.contract.v1",
      profile_id: `profile:fixture-${this.#profiles.length + 1}`,
      display_name: input.display_name,
      disabled: false,
      created_at: this.#data.workspace.created_at,
      controller_role: "owner",
    };
    this.#profiles.push(profile);
    return profile;
  }

  async listSessions(
    workspaceId: string,
    request: PageRequest,
  ): Promise<SessionPage> {
    assertRequest(request);
    this.#assertWorkspace(workspaceId);
    const items = pageWindow(
      [...this.#sessions.values()].map((record) =>
        record.session.session_id === this.#session.session_id
          ? this.#session
          : record.session
      ),
      request,
    );
    return {
      schema_version: "atpiano.contract.v1",
      workspace_id: workspaceId,
      items,
      next_cursor: null,
    };
  }

  async getSession(
    workspaceId: string,
    sessionId: string,
    request: RuntimeRequest,
  ): Promise<Session> {
    assertRequest(request);
    this.#assertTarget(workspaceId, sessionId);
    return sessionId === this.#session.session_id
      ? this.#session
      : this.#record(sessionId).session;
  }

  async updateSessionAnnotation(
    input: SessionAnnotationPatch,
    request: RuntimeRequest,
  ): Promise<SessionAnnotation> {
    assertRequest(request);
    this.#assertTarget(input.workspace_id, input.session_id);
    const record = this.#record(input.session_id);
    const updated = {
      ...record.session,
      display_name: input.display_name,
    };
    this.#sessions.set(input.session_id, {
      ...record,
      session: updated,
    });
    if (this.#session.session_id === input.session_id) {
      this.#session = updated;
    }
    return {
      schema_version: "atpiano.contract.v1",
      workspace_id: input.workspace_id,
      session_id: input.session_id,
      display_name: input.display_name,
      updated_at: this.#data.trashedAt,
    };
  }

  async updateSessionPerformer(
    input: SessionPerformerPatch,
    request: RuntimeRequest,
  ): Promise<SessionPerformerAttribution> {
    assertRequest(request);
    this.#assertTarget(input.workspace_id, input.session_id);
    const record = this.#record(input.session_id);
    const updated = {
      ...record.session,
      performed_by_profile_id: input.performed_by_profile_id,
    };
    this.#sessions.set(input.session_id, {
      ...record,
      session: updated,
    });
    if (this.#session.session_id === input.session_id) {
      this.#session = updated;
    }
    return {
      schema_version: "atpiano.contract.v1",
      workspace_id: input.workspace_id,
      session_id: input.session_id,
      performed_by_profile_id: input.performed_by_profile_id,
      updated_at: this.#data.trashedAt,
    };
  }

  async getHorizon(
    workspaceId: string,
    sessionId: string,
    request: RuntimeRequest,
  ): Promise<Horizon> {
    assertRequest(request);
    this.#assertTarget(workspaceId, sessionId);
    const horizon = this.#record(sessionId).horizon;
    if (sessionId !== this.#session.session_id) {
      return horizon;
    }
    return {
      ...horizon,
      audio_head_sample: this.#session.source_frame_count,
      provisional_sample: Math.min(
        horizon.provisional_sample,
        this.#session.source_frame_count,
      ),
      commit_sample: Math.min(
        horizon.commit_sample,
        this.#session.source_frame_count,
      ),
    };
  }

  async startCapture(
    input: CaptureStart,
    request: RuntimeRequest,
  ): Promise<Capture> {
    assertRequest(request);
    this.#assertWorkspace(input.workspace_id);
    this.#nextSample = 0;
    this.#capture = {
      ...this.#data.capture,
      source: "microphone",
      status: "recording",
      accepted_through_sample: 0,
      stopped_at: null,
    };
    this.#session = {
      ...this.#data.sessions[0]!.session,
      source: "microphone",
      status: "active",
      source_frame_count: 0,
      recognized_note_count: 0,
      corrected_note_count: 0,
      performed_by_profile_id: input.performed_by_profile_id,
      completed_at: null,
      active_capture_id: this.#capture.capture_id,
    };
    return this.#capture;
  }

  streamPcm(block: PcmBlock): void {
    const { envelope, payload } = block;
    this.#assertTarget(envelope.workspace_id, envelope.session_id);
    if (envelope.capture_id !== this.#capture.capture_id) {
      throw new Error("PCM capture target is stale");
    }
    if (envelope.first_sample !== this.#nextSample) {
      throw new Error("PCM source sample is not contiguous");
    }
    if (payload.byteLength !== envelope.payload_byte_count) {
      throw new Error("PCM payload bytes do not match its envelope");
    }
    this.#nextSample += envelope.frame_count;
    this.#capture = {
      ...this.#capture,
      accepted_through_sample: this.#nextSample,
    };
  }

  async stopCapture(
    input: CaptureStop,
    request: RuntimeRequest,
  ): Promise<Session> {
    assertRequest(request);
    this.#assertTarget(input.workspace_id, input.session_id);
    if (
      input.capture_id !== this.#capture.capture_id ||
      input.accepted_frame_count !== this.#nextSample
    ) {
      throw new Error("Stop target or accepted frame count is stale");
    }
    this.#capture = {
      ...this.#capture,
      status: "complete",
      stopped_at: this.#data.trashedAt,
    };
    this.#session = {
      ...this.#session,
      status: "complete",
      source_frame_count: this.#nextSample,
      completed_at: this.#data.trashedAt,
      active_capture_id: null,
    };
    return this.#session;
  }

  async startReplay(
    input: ReplayStart,
    request: RuntimeRequest,
  ): Promise<Capture> {
    assertRequest(request);
    this.#assertWorkspace(input.workspace_id);
    if (input.fixture_id !== this.#data.fixtureId) {
      throw new Error("fixture does not exist");
    }
    this.#nextSample = 0;
    this.#capture = {
      ...this.#data.capture,
      source: "replay",
      status: "recording",
      accepted_through_sample: 0,
      stopped_at: null,
    };
    this.#session = {
      ...this.#data.sessions[0]!.session,
      source: "replay",
      status: "active",
      source_frame_count: this.#data.sessions[0]!.session.source_frame_count,
      completed_at: null,
      active_capture_id: this.#capture.capture_id,
    };
    return this.#capture;
  }

  async importRecording(
    input: RecordingImportStart,
    file: Blob,
    request: RuntimeRequest,
  ): Promise<Capture> {
    assertRequest(request);
    this.#assertWorkspace(input.workspace_id);
    if (file.size !== input.byte_count || file.size === 0) {
      throw new Error("fixture recording upload size is invalid");
    }
    const displayName = input.filename.replace(/\.(?:wav|mp3)$/i, "");
    this.#capture = {
      ...this.#data.capture,
      source: "upload",
      status: "complete",
      accepted_through_sample: this.#session.source_frame_count,
      stopped_at: this.#data.trashedAt,
    };
    this.#session = {
      ...this.#session,
      source: "upload",
      status: "complete",
      display_name: displayName,
      performed_by_profile_id: input.performed_by_profile_id,
      completed_at: this.#data.trashedAt,
      active_capture_id: null,
    };
    return this.#capture;
  }

  subscribeEvents(
    workspaceId: string,
    sessionId: string,
    range: EventRangeRequest,
    subscriber: EventSubscriber,
  ): EventSubscription {
    assertRequest(range);
    this.#assertTarget(workspaceId, sessionId);
    const events = this.#record(sessionId).events;
    let closed = false;
    queueMicrotask(() => {
      if (!closed) {
        subscriber.next({
          ...events,
          start_sample: range.startSample,
          end_sample: range.endSample,
        });
      }
    });
    return {
      close() {
        closed = true;
      },
    };
  }

  async listArtifacts(
    workspaceId: string,
    sessionId: string,
    request: PageRequest,
  ): Promise<ArtifactPage> {
    assertRequest(request);
    this.#assertTarget(workspaceId, sessionId);
    const artifacts = this.#record(sessionId).artifacts;
    return {
      ...artifacts,
      items: pageWindow(artifacts.items, request),
      next_cursor: null,
    };
  }

  async getArtifactAccess(
    workspaceId: string,
    sessionId: string,
    artifactId: string,
    request: RuntimeRequest,
  ): Promise<ArtifactAccess> {
    assertRequest(request);
    this.#assertTarget(workspaceId, sessionId);
    const access = this.#record(sessionId).artifactAccess[artifactId];
    if (access === undefined) {
      throw new Error("artifact does not exist");
    }
    return access;
  }

  async readArtifact(
    workspaceId: string,
    sessionId: string,
    artifactId: string,
    request: RuntimeRequest,
  ): Promise<ArtifactContent> {
    const access = await this.getArtifactAccess(
      workspaceId,
      sessionId,
      artifactId,
      request,
    );
    const response = await fetch(access.url, {
      ...(request.signal === undefined ? {} : { signal: request.signal }),
    });
    if (!response.ok) {
      throw new Error(`Artifact download failed: HTTP ${response.status}`);
    }
    return {
      access,
      bytes: await response.arrayBuffer(),
    };
  }

  async exportArtifact(
    workspaceId: string,
    sessionId: string,
    artifactId: string,
    request: RuntimeRequest,
  ): Promise<ArtifactExportResult> {
    return startBrowserArtifactExport(
      await this.readArtifact(
        workspaceId,
        sessionId,
        artifactId,
        request,
      ),
    );
  }

  async startScoreJob(
    input: ScoreJobStart,
    request: RuntimeRequest,
  ): Promise<Job> {
    assertRequest(request);
    this.#assertTarget(input.workspace_id, input.session_id);
    if (
      input.transcription_run_id !==
        this.#session.current_transcription_run_id ||
      input.commit_sample !== this.#data.scoreJob.input_horizon_sample
    ) {
      throw new Error("score job target or horizon is stale");
    }
    return this.#data.scoreJob;
  }

  async listScoreVariants(
    workspaceId: string,
    sessionId: string,
    request: RuntimeRequest,
  ): Promise<ScoreVariantPage> {
    assertRequest(request);
    this.#assertTarget(workspaceId, sessionId);
    return this.#data.scoreVariants ?? {
      schema_version: "atpiano.contract.v1",
      workspace_id: workspaceId,
      session_id: sessionId,
      items: [],
      producer: null,
      freshness: null,
    };
  }

  async createScoreVariant(
    input: ScoreVariantRequest,
    request: RuntimeRequest,
  ): Promise<ScoreVariant> {
    assertRequest(request);
    this.#assertTarget(input.workspace_id, input.session_id);
    const variant = this.#data.scoreVariants?.items.find(
      (candidate) =>
        candidate.baseline_musicxml_artifact_id ===
          input.baseline_musicxml_artifact_id &&
        candidate.baseline_alignment_artifact_id ===
          input.baseline_alignment_artifact_id &&
        candidate.clef_policy === input.clef_policy &&
        candidate.target_key_fifths === input.target_key_fifths,
    );
    if (!variant) throw new Error("fixture score variant does not exist");
    return variant;
  }

  async getJob(jobId: string, request: RuntimeRequest): Promise<Job> {
    assertRequest(request);
    if (jobId !== this.#data.scoreJob.job_id) {
      throw new Error("job does not exist");
    }
    return this.#data.scoreJob;
  }

  async deleteSession(
    input: DeleteSessionRequest,
    request: RuntimeRequest,
  ): Promise<DeleteSessionResult> {
    assertRequest(request);
    this.#assertTarget(input.workspace_id, input.session_id);
    if (this.#session.status === "active") {
      throw new Error("active session cannot be deleted");
    }
    this.#sessions.delete(input.session_id);
    return {
      schema_version: "atpiano.contract.v1",
      workspace_id: input.workspace_id,
      session_id: input.session_id,
      trashed_at: this.#data.trashedAt,
      recoverable: true,
    };
  }

  #assertWorkspace(workspaceId: string): void {
    if (workspaceId !== this.#data.workspace.workspace_id) {
      throw new Error("workspace does not exist");
    }
  }

  #assertTarget(workspaceId: string, sessionId: string): void {
    this.#assertWorkspace(workspaceId);
    if (!this.#sessions.has(sessionId)) {
      throw new Error("session does not exist");
    }
  }

  #record(sessionId: string): FixtureSessionData {
    const record = this.#sessions.get(sessionId);
    if (record === undefined) {
      throw new Error("session does not exist");
    }
    return record;
  }
}

export type { Artifact };

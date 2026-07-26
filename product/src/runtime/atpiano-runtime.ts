import type { components } from "../generated/schema.js";

type Schemas = components["schemas"];

export type RuntimeCapabilities = Schemas["RuntimeCapabilities"];
export type Workspace = Schemas["Workspace"];
export type WorkspacePage = Schemas["WorkspacePage"];
export type Session = Schemas["Session"];
export type SessionPage = Schemas["SessionPage"];
export type Capture = Schemas["Capture"];
export type CaptureStart = Schemas["CaptureStart"];
export type CaptureStop = Schemas["CaptureStop"];
export type ReplayStart = Schemas["ReplayStart"];
export type EventRevision = Schemas["EventRevision"];
export type EventPage = Schemas["EventPage"];
export type PcmEnvelope = Schemas["PcmEnvelope"];
export type Artifact = Schemas["Artifact"];
export type ArtifactPage = Schemas["ArtifactPage"];
export type ArtifactAccess = Schemas["ArtifactAccess"];
export type ScoreJobStart = Schemas["ScoreJobStart"];
export type Job = Schemas["Job"];
export type DeleteSessionRequest = Schemas["DeleteSessionRequest"];
export type DeleteSessionResult = Schemas["DeleteSessionResult"];

export interface RuntimeRequest {
  readonly requestId: string;
  readonly signal?: AbortSignal;
}

export interface PageRequest extends RuntimeRequest {
  readonly cursor?: string;
  readonly limit?: number;
}

export interface EventRangeRequest extends PageRequest {
  readonly startSample: number;
  readonly endSample: number;
}

export interface EventSubscription {
  /**
   * Idempotently release transport and callbacks. No event may be delivered
   * after close() returns.
   */
  close(): void;
}

export interface EventSubscriber {
  next(page: EventPage): void;
  error(error: unknown): void;
}

export interface PcmBlock {
  readonly envelope: PcmEnvelope;
  readonly payload: ArrayBuffer;
}

/**
 * Platform-neutral application boundary used by the shared frontend.
 *
 * Every result repeats its target IDs. A consumer must discard a result whose
 * request ID or resource IDs no longer match its active intent. AbortSignal
 * cancellation prevents avoidable work but is not relied on to suppress a
 * response that already crossed a process or network boundary.
 */
export interface AtpianoRuntime {
  getCapabilities(request: RuntimeRequest): Promise<RuntimeCapabilities>;
  listWorkspaces(request: PageRequest): Promise<WorkspacePage>;
  listSessions(
    workspaceId: string,
    request: PageRequest,
  ): Promise<SessionPage>;
  getSession(
    workspaceId: string,
    sessionId: string,
    request: RuntimeRequest,
  ): Promise<Session>;
  startCapture(input: CaptureStart, request: RuntimeRequest): Promise<Capture>;
  streamPcm(block: PcmBlock): void;
  stopCapture(input: CaptureStop, request: RuntimeRequest): Promise<Session>;
  startReplay(input: ReplayStart, request: RuntimeRequest): Promise<Capture>;
  subscribeEvents(
    workspaceId: string,
    sessionId: string,
    range: EventRangeRequest,
    subscriber: EventSubscriber,
  ): EventSubscription;
  listArtifacts(
    workspaceId: string,
    sessionId: string,
    request: PageRequest,
  ): Promise<ArtifactPage>;
  getArtifactAccess(
    workspaceId: string,
    sessionId: string,
    artifactId: string,
    request: RuntimeRequest,
  ): Promise<ArtifactAccess>;
  startScoreJob(
    input: ScoreJobStart,
    request: RuntimeRequest,
  ): Promise<Job>;
  getJob(jobId: string, request: RuntimeRequest): Promise<Job>;
  deleteSession(
    input: DeleteSessionRequest,
    request: RuntimeRequest,
  ): Promise<DeleteSessionResult>;
}

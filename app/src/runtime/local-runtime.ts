import {
  createAtpianoHttpClient,
  type AtpianoHttpClient,
} from "../http-client.js";
import { startBrowserArtifactExport } from "../lib/artifact-export.js";
import type {
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
  WorkspacePage,
} from "./atpiano-runtime.js";

const streamSchema = "atpiano.corrected-stream.v1";
const pcmHeaderBytes = 48;
const subscriptionIntervalMs = 750;

interface StreamMessage {
  readonly type?: string;
  readonly session_id?: string;
  readonly sample_rate_hz?: number;
  readonly received_source_frames?: number;
  readonly sequence?: number;
  readonly error?: string;
}

interface PendingSocket {
  readonly socket: WebSocket;
  readonly ready: Promise<Capture>;
  resolveReady(capture: Capture): void;
  rejectReady(error: Error): void;
  readonly stopped: Promise<void>;
  resolveStopped(): void;
  rejectStopped(error: Error): void;
  capture: Capture | null;
  sentFrameCount: number;
  sentBlockCount: number;
  acknowledgedFrameCount: number;
  acknowledgedBlockCount: number;
  bufferedAmountHighWater: number;
}

function abortOptions(request: RuntimeRequest): { signal?: AbortSignal } {
  return request.signal === undefined ? {} : { signal: request.signal };
}

function errorMessage(error: unknown, fallback: string): string {
  if (
    typeof error === "object" &&
    error !== null &&
    "error" in error
  ) {
    if (typeof error.error === "string") return error.error;
    if (
      typeof error.error === "object" &&
      error.error !== null &&
      "message" in error.error
    ) {
      return String(error.error.message);
    }
  }
  if (
    typeof error === "object" &&
    error !== null &&
    "message" in error
  ) {
    return String(error.message);
  }
  return fallback;
}

function dataOrThrow<T>(
  result: { data?: T; error?: unknown },
  fallback: string,
): T {
  if (result.data !== undefined) return result.data;
  throw new Error(errorMessage(result.error, fallback));
}

function captureFromSession(
  session: Session,
  source: Capture["source"],
): Capture {
  return {
    schema_version: "atpiano.contract.v1",
    workspace_id: session.workspace_id,
    session_id: session.session_id,
    capture_id: session.active_capture_id ?? `capture:${session.session_id}`,
    status:
      session.status === "stopping"
        ? "stopping"
        : session.status === "complete"
          ? "complete"
          : "recording",
    source,
    sample_rate_hz: session.sample_rate_hz,
    accepted_through_sample: session.source_frame_count,
    started_at: session.started_at,
    stopped_at: session.completed_at,
    error_id: null,
  };
}

function packPcmBlock(block: PcmBlock): ArrayBuffer {
  const output = new ArrayBuffer(pcmHeaderBytes + block.payload.byteLength);
  const view = new DataView(output);
  for (const [index, value] of [..."ATPB"].entries()) {
    view.setUint8(index, value.charCodeAt(0));
  }
  view.setUint8(4, 1);
  view.setUint8(5, 1);
  view.setUint16(6, pcmHeaderBytes, true);
  view.setUint32(8, block.envelope.sequence, true);
  view.setUint32(12, 0, true);
  view.setBigUint64(16, BigInt(block.envelope.first_sample), true);
  view.setUint32(24, block.envelope.frame_count, true);
  view.setUint32(28, block.envelope.sample_rate_hz, true);
  view.setFloat64(32, performance.now(), true);
  view.setFloat64(
    40,
    block.envelope.first_sample / block.envelope.sample_rate_hz,
    true,
  );
  new Uint8Array(output, pcmHeaderBytes).set(new Uint8Array(block.payload));
  return output;
}

export class LocalRuntime implements AtpianoRuntime {
  readonly #baseUrl: string;
  readonly #client: AtpianoHttpClient;
  readonly #fetch: typeof fetch;
  readonly #WebSocket: typeof WebSocket;
  readonly #webSocketProtocol: string | undefined;
  #pendingSocket: PendingSocket | null = null;

  constructor({
    baseUrl = globalThis.location?.origin ?? "http://127.0.0.1",
    fetchImplementation = globalThis.fetch,
    WebSocketImplementation = globalThis.WebSocket,
    bearerToken,
    webSocketProtocol,
  }: {
    readonly baseUrl?: string;
    readonly fetchImplementation?: typeof fetch;
    readonly WebSocketImplementation?: typeof WebSocket;
    readonly bearerToken?: string;
    readonly webSocketProtocol?: string;
  } = {}) {
    this.#baseUrl = baseUrl.replace(/\/$/, "");
    const browserFetch = fetchImplementation.bind(globalThis);
    this.#fetch = bearerToken === undefined
      ? browserFetch
      : async (input, init) => {
          const request = new Request(input, init);
          const headers = new Headers(request.headers);
          headers.set("Authorization", `Bearer ${bearerToken}`);
          return browserFetch(new Request(request, { headers }));
        };
    this.#WebSocket = WebSocketImplementation;
    this.#webSocketProtocol = webSocketProtocol;
    this.#client = createAtpianoHttpClient({
      baseUrl: this.#baseUrl,
      fetch: this.#fetch,
    });
  }

  async getCapabilities(request: RuntimeRequest): Promise<RuntimeCapabilities> {
    return dataOrThrow(
      await this.#client.GET("/api/v1/capabilities", abortOptions(request)),
      "Runtime capabilities could not be loaded.",
    );
  }

  async listWorkspaces(request: PageRequest): Promise<WorkspacePage> {
    return dataOrThrow(
      await this.#client.GET("/api/v1/workspaces", {
        ...abortOptions(request),
        params: {
          query: {
            ...(request.cursor === undefined ? {} : { cursor: request.cursor }),
            ...(request.limit === undefined ? {} : { limit: request.limit }),
          },
        },
      }),
      "Workspaces could not be loaded.",
    );
  }

  async listSessions(
    workspaceId: string,
    request: PageRequest,
  ): Promise<SessionPage> {
    return dataOrThrow(
      await this.#client.GET("/api/v1/workspaces/{workspace_id}/sessions", {
        ...abortOptions(request),
        params: {
          path: { workspace_id: workspaceId },
          query: {
            ...(request.cursor === undefined ? {} : { cursor: request.cursor }),
            ...(request.limit === undefined ? {} : { limit: request.limit }),
          },
        },
      }),
      "Sessions could not be loaded.",
    );
  }

  async getSession(
    workspaceId: string,
    sessionId: string,
    request: RuntimeRequest,
  ): Promise<Session> {
    return dataOrThrow(
      await this.#client.GET(
        "/api/v1/workspaces/{workspace_id}/sessions/{session_id}",
        {
          ...abortOptions(request),
          params: {
            path: {
              workspace_id: workspaceId,
              session_id: sessionId,
            },
          },
        },
      ),
      "The selected session could not be loaded.",
    );
  }

  async updateSessionAnnotation(
    input: SessionAnnotationPatch,
    request: RuntimeRequest,
  ): Promise<SessionAnnotation> {
    return dataOrThrow(
      await this.#client.PATCH(
        "/api/v1/workspaces/{workspace_id}/sessions/{session_id}",
        {
          ...abortOptions(request),
          params: {
            path: {
              workspace_id: input.workspace_id,
              session_id: input.session_id,
            },
          },
          body: input,
        },
      ),
      "The session name could not be saved.",
    );
  }

  async getHorizon(
    workspaceId: string,
    sessionId: string,
    request: RuntimeRequest,
  ): Promise<Horizon> {
    return dataOrThrow(
      await this.#client.GET(
        "/api/v1/workspaces/{workspace_id}/sessions/{session_id}/horizon",
        {
          ...abortOptions(request),
          params: {
            path: {
              workspace_id: workspaceId,
              session_id: sessionId,
            },
          },
        },
      ),
      "Session progress could not be loaded.",
    );
  }

  async startCapture(
    input: CaptureStart,
    request: RuntimeRequest,
  ): Promise<Capture> {
    if (request.signal?.aborted) {
      throw request.signal.reason ?? new DOMException("Aborted", "AbortError");
    }
    if (this.#pendingSocket !== null) {
      throw new Error("a local microphone capture is already connected");
    }
    const protocol = this.#baseUrl.startsWith("https:") ? "wss:" : "ws:";
    const host = new URL(this.#baseUrl).host;
    const socket = this.#webSocketProtocol === undefined
      ? new this.#WebSocket(`${protocol}//${host}/api/live`)
      : new this.#WebSocket(
          `${protocol}//${host}/api/live`,
          this.#webSocketProtocol,
        );
    let resolveReady!: (capture: Capture) => void;
    let rejectReady!: (error: Error) => void;
    let resolveStopped!: () => void;
    let rejectStopped!: (error: Error) => void;
    const pending: PendingSocket = {
      socket,
      ready: new Promise((resolve, reject) => {
        resolveReady = resolve;
        rejectReady = reject;
      }),
      resolveReady,
      rejectReady,
      stopped: new Promise((resolve, reject) => {
        resolveStopped = resolve;
        rejectStopped = reject;
      }),
      resolveStopped,
      rejectStopped,
      capture: null,
      sentFrameCount: 0,
      sentBlockCount: 0,
      acknowledgedFrameCount: 0,
      acknowledgedBlockCount: 0,
      bufferedAmountHighWater: 0,
    };
    this.#pendingSocket = pending;
    socket.binaryType = "arraybuffer";
    socket.addEventListener("open", () => {
      socket.send(
        JSON.stringify({
          schema_version: streamSchema,
          type: "start",
          sample_rate_hz: input.sample_rate_hz,
          client_metadata: {
            started_at: new Date().toISOString(),
            request_id: input.request_id,
            user_agent: navigator.userAgent,
          },
        }),
      );
    });
    socket.addEventListener("message", (event) => {
      if (typeof event.data !== "string") return;
      const message = JSON.parse(event.data) as StreamMessage;
      if (
        message.type === "ready" &&
        message.session_id &&
        message.sample_rate_hz
      ) {
        const capture: Capture = {
          schema_version: "atpiano.contract.v1",
          workspace_id: input.workspace_id,
          session_id: message.session_id,
          capture_id: `capture:${message.session_id}`,
          status: "recording",
          source: "microphone",
          sample_rate_hz: message.sample_rate_hz,
          accepted_through_sample: 0,
          started_at: new Date().toISOString(),
          stopped_at: null,
          error_id: null,
        };
        pending.capture = capture;
        pending.resolveReady(capture);
      } else if (message.type === "block_ack" && pending.capture) {
        pending.acknowledgedFrameCount =
          message.received_source_frames ??
          pending.acknowledgedFrameCount;
        pending.acknowledgedBlockCount = Math.max(
          pending.acknowledgedBlockCount,
          (message.sequence ?? -1) + 1,
        );
        pending.capture = {
          ...pending.capture,
          accepted_through_sample:
            message.received_source_frames ??
            pending.capture.accepted_through_sample,
        };
      } else if (message.type === "stopped") {
        pending.resolveStopped();
      } else if (message.type === "error") {
        const error = new Error(message.error ?? "Local capture failed.");
        pending.rejectReady(error);
        pending.rejectStopped(error);
      }
    });
    socket.addEventListener("error", () => {
      const error = new Error("The local capture WebSocket failed.");
      pending.rejectReady(error);
      pending.rejectStopped(error);
    });
    request.signal?.addEventListener(
      "abort",
      () => {
        socket.close();
        pending.rejectReady(
          request.signal?.reason ?? new DOMException("Aborted", "AbortError"),
        );
      },
      { once: true },
    );
    try {
      return await pending.ready;
    } catch (error) {
      this.#pendingSocket = null;
      socket.close();
      throw error;
    }
  }

  streamPcm(block: PcmBlock): void {
    const pending = this.#pendingSocket;
    if (
      pending?.capture === null ||
      pending?.capture === undefined ||
      pending.socket.readyState !== this.#WebSocket.OPEN
    ) {
      throw new Error("local capture is not ready for PCM");
    }
    if (
      block.envelope.capture_id !== pending.capture.capture_id ||
      block.envelope.session_id !== pending.capture.session_id
    ) {
      throw new Error("PCM target does not match the active local capture");
    }
    if (
      block.envelope.sequence !== pending.sentBlockCount ||
      block.envelope.first_sample !== pending.sentFrameCount
    ) {
      throw new Error("PCM does not continue the local transport sample clock");
    }
    pending.socket.send(packPcmBlock(block));
    pending.sentBlockCount += 1;
    pending.sentFrameCount += block.envelope.frame_count;
    pending.bufferedAmountHighWater = Math.max(
      pending.bufferedAmountHighWater,
      pending.socket.bufferedAmount,
    );
  }

  async stopCapture(
    input: CaptureStop,
    request: RuntimeRequest,
  ): Promise<Session> {
    const pending = this.#pendingSocket;
    if (
      pending?.capture === null ||
      pending?.capture === undefined ||
      pending.capture.capture_id !== input.capture_id ||
      pending.capture.session_id !== input.session_id
    ) {
      throw new Error("Stop target does not match the active local capture");
    }
    if (input.accepted_frame_count !== pending.sentFrameCount) {
      throw new Error("Stop frame count does not match sent PCM");
    }
    pending.socket.send(
      JSON.stringify({
        schema_version: streamSchema,
        type: "stop",
        frame_count: pending.sentFrameCount,
        block_count: pending.sentBlockCount,
        transport: {
          sent_frame_count: pending.sentFrameCount,
          sent_block_count: pending.sentBlockCount,
          acknowledged_frame_count: pending.acknowledgedFrameCount,
          acknowledged_block_count: pending.acknowledgedBlockCount,
          socket_buffered_bytes_at_stop: pending.socket.bufferedAmount,
          socket_buffered_bytes_high_water: pending.bufferedAmountHighWater,
        },
      }),
    );
    const timeout = new Promise<never>((_, reject) => {
      window.setTimeout(
        () => reject(new Error("The local engine did not acknowledge Stop.")),
        10_000,
      );
    });
    try {
      await Promise.race([pending.stopped, timeout]);
    } finally {
      pending.socket.close();
      this.#pendingSocket = null;
    }
    return this.getSession(input.workspace_id, input.session_id, request);
  }

  async startReplay(
    input: ReplayStart,
    request: RuntimeRequest,
  ): Promise<Capture> {
    const response = await this.#fetch(`${this.#baseUrl}/api/replay`, {
      ...abortOptions(request),
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        fixture_id: input.fixture_id,
        request_id: input.request_id,
      }),
    });
    if (!response.ok) {
      const error = await response.json() as unknown;
      throw new Error(errorMessage(error, "The fixture replay could not start."));
    }
    const page = await this.listSessions(input.workspace_id, {
      requestId: request.requestId,
      ...(request.signal === undefined ? {} : { signal: request.signal }),
      limit: 1,
    });
    const session = page.items[0];
    if (session === undefined) {
      throw new Error("The local replay did not create a session.");
    }
    return captureFromSession(session, "replay");
  }

  async importRecording(
    input: RecordingImportStart,
    file: Blob,
    request: RuntimeRequest,
  ): Promise<Capture> {
    if (file.size !== input.byte_count) {
      throw new Error("The selected recording size changed before upload.");
    }
    const response = await this.#fetch(
      `${this.#baseUrl}/api/v1/workspaces/${encodeURIComponent(
        input.workspace_id,
      )}/recording-imports`,
      {
        ...abortOptions(request),
        method: "POST",
        headers: {
          "Content-Type": input.media_type,
          "X-Atpiano-Filename": encodeURIComponent(input.filename),
          "X-Atpiano-Request-Id": input.request_id,
        },
        body: file,
      },
    );
    if (!response.ok) {
      let error: unknown;
      try {
        error = await response.json();
      } catch {
        error = undefined;
      }
      throw new Error(
        errorMessage(error, "The recording could not be imported."),
      );
    }
    return await response.json() as Capture;
  }

  subscribeEvents(
    workspaceId: string,
    sessionId: string,
    range: EventRangeRequest,
    subscriber: EventSubscriber,
  ): EventSubscription {
    let closed = false;
    let timer: number | undefined;
    let controller: AbortController | null = null;
    const poll = async () => {
      if (closed) return;
      controller = new AbortController();
      range.signal?.addEventListener("abort", () => controller?.abort(), {
        once: true,
      });
      try {
        const page = dataOrThrow<EventPage>(
          await this.#client.GET(
            "/api/v1/workspaces/{workspace_id}/sessions/{session_id}/events",
            {
              signal: controller.signal,
              params: {
                path: {
                  workspace_id: workspaceId,
                  session_id: sessionId,
                },
                query: {
                  start_sample: range.startSample,
                  end_sample: range.endSample,
                  ...(range.cursor === undefined ? {} : { cursor: range.cursor }),
                  ...(range.limit === undefined ? {} : { limit: range.limit }),
                },
              },
            },
          ),
          "The session notes could not be loaded.",
        );
        if (!closed && page.session_id === sessionId) subscriber.next(page);
      } catch (error) {
        if (!closed && !(error instanceof DOMException && error.name === "AbortError")) {
          subscriber.error(error);
        }
      } finally {
        if (!closed) timer = window.setTimeout(poll, subscriptionIntervalMs);
      }
    };
    void poll();
    return {
      close() {
        closed = true;
        controller?.abort();
        if (timer !== undefined) window.clearTimeout(timer);
      },
    };
  }

  async listArtifacts(
    workspaceId: string,
    sessionId: string,
    request: PageRequest,
  ): Promise<ArtifactPage> {
    return dataOrThrow(
      await this.#client.GET(
        "/api/v1/workspaces/{workspace_id}/sessions/{session_id}/artifacts",
        {
          ...abortOptions(request),
          params: {
            path: {
              workspace_id: workspaceId,
              session_id: sessionId,
            },
            query: {
              ...(request.cursor === undefined ? {} : { cursor: request.cursor }),
              ...(request.limit === undefined ? {} : { limit: request.limit }),
            },
          },
        },
      ),
      "Session exports could not be loaded.",
    );
  }

  async getArtifactAccess(
    workspaceId: string,
    sessionId: string,
    artifactId: string,
    request: RuntimeRequest,
  ): Promise<ArtifactAccess> {
    return dataOrThrow(
      await this.#client.GET(
        "/api/v1/workspaces/{workspace_id}/sessions/{session_id}/artifacts/{artifact_id}/access",
        {
          ...abortOptions(request),
          params: {
            path: {
              workspace_id: workspaceId,
              session_id: sessionId,
              artifact_id: artifactId,
            },
          },
        },
      ),
      "The selected export could not be opened.",
    );
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
    const response = await this.#fetch(
      new URL(access.url, this.#baseUrl),
      abortOptions(request),
    );
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
    return dataOrThrow(
      await this.#client.POST(
        "/api/v1/workspaces/{workspace_id}/sessions/{session_id}/score-jobs",
        {
          ...abortOptions(request),
          params: {
            path: {
              workspace_id: input.workspace_id,
              session_id: input.session_id,
            },
          },
          body: input,
        },
      ),
      "Score generation could not start.",
    );
  }

  async listScoreVariants(
    workspaceId: string,
    sessionId: string,
    request: RuntimeRequest,
  ): Promise<ScoreVariantPage> {
    return dataOrThrow(
      await this.#client.GET(
        "/api/v1/workspaces/{workspace_id}/sessions/{session_id}/score-variants",
        {
          ...abortOptions(request),
          params: {
            path: {
              workspace_id: workspaceId,
              session_id: sessionId,
            },
          },
        },
      ),
      "Score engraving choices could not be loaded.",
    );
  }

  async createScoreVariant(
    input: ScoreVariantRequest,
    request: RuntimeRequest,
  ): Promise<ScoreVariant> {
    return dataOrThrow(
      await this.#client.POST(
        "/api/v1/workspaces/{workspace_id}/sessions/{session_id}/score-variants",
        {
          ...abortOptions(request),
          params: {
            path: {
              workspace_id: input.workspace_id,
              session_id: input.session_id,
            },
          },
          body: input,
        },
      ),
      "The score engraving choice could not be saved.",
    );
  }

  async getJob(jobId: string, request: RuntimeRequest): Promise<Job> {
    return dataOrThrow(
      await this.#client.GET("/api/v1/jobs/{job_id}", {
        ...abortOptions(request),
        params: { path: { job_id: jobId } },
      }),
      "Score generation progress could not be loaded.",
    );
  }

  async deleteSession(
    input: DeleteSessionRequest,
    request: RuntimeRequest,
  ): Promise<DeleteSessionResult> {
    return dataOrThrow(
      await this.#client.DELETE(
        "/api/v1/workspaces/{workspace_id}/sessions/{session_id}",
        {
          ...abortOptions(request),
          params: {
            path: {
              workspace_id: input.workspace_id,
              session_id: input.session_id,
            },
          },
          body: input,
        },
      ),
      "The session could not be moved to trash.",
    );
  }
}

import { describe, expect, it } from "vitest";

import type { Session } from "../../src/runtime/atpiano-runtime.js";
import { LocalRuntime } from "../../src/runtime/local-runtime.js";

const session: Session = {
  schema_version: "atpiano.contract.v1",
  workspace_id: "local",
  session_id: "session-local",
  status: "complete",
  source: "microphone",
  sample_rate_hz: 48_000,
  source_frame_count: 4,
  started_at: "2026-07-26T10:00:00Z",
  completed_at: "2026-07-26T10:00:01Z",
  active_capture_id: null,
  current_transcription_run_id: "run-local",
  display_name: "Local capture",
  correction_mode: null,
  correction_reason: null,
  available_artifact_kinds: [],
};

function response(value: unknown, status = 200): Response {
  return new Response(JSON.stringify(value), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const fakeFetch: typeof fetch = async (input, init) => {
  const request = input instanceof Request ? input : new Request(input, init);
  const url = new URL(request.url);
  if (url.pathname === "/api/replay" && request.method === "POST") {
    return response({ session: { session_id: session.session_id } }, 202);
  }
  if (url.pathname === "/api/v1/workspaces/local/sessions") {
    return response({
      schema_version: "atpiano.contract.v1",
      workspace_id: "local",
      items: [session],
      next_cursor: null,
    });
  }
  if (url.pathname === "/api/v1/workspaces/local/sessions/session-local") {
    return response(session);
  }
  return response({ error: { message: `unexpected ${url.pathname}` } }, 404);
};

type Listener = (event: Event) => void;

class FakeWebSocket {
  static readonly OPEN = 1;
  static instances: FakeWebSocket[] = [];
  readonly sent: (string | ArrayBufferLike | Blob | ArrayBufferView)[] = [];
  readonly listeners = new Map<string, Listener[]>();
  readyState = FakeWebSocket.OPEN;
  binaryType: BinaryType = "blob";

  constructor(readonly url: string) {
    FakeWebSocket.instances.push(this);
  }

  addEventListener(type: string, listener: Listener): void {
    this.listeners.set(type, [...(this.listeners.get(type) ?? []), listener]);
  }

  send(value: string | ArrayBufferLike | Blob | ArrayBufferView): void {
    this.sent.push(value);
  }

  close(): void {
    this.readyState = 3;
  }

  emit(type: string, event: Event = new Event(type)): void {
    for (const listener of this.listeners.get(type) ?? []) listener(event);
  }

  message(value: unknown): void {
    this.emit(
      "message",
      new MessageEvent("message", { data: JSON.stringify(value) }),
    );
  }
}

describe("local runtime", () => {
  it("maps configured replay to an explicit active capture", async () => {
    const runtime = new LocalRuntime({
      baseUrl: "http://127.0.0.1:8002",
      fetchImplementation: fakeFetch,
      WebSocketImplementation: FakeWebSocket as unknown as typeof WebSocket,
    });

    const capture = await runtime.startReplay(
      {
        schema_version: "atpiano.contract.v1",
        workspace_id: "local",
        fixture_id: "fixture",
        repeat: 1,
        silence_samples: 0,
        realtime: false,
        request_id: "replay-1",
      },
      { requestId: "replay-1" },
    );

    expect(capture.session_id).toBe(session.session_id);
    expect(capture.capture_id).toBe(`capture:${session.session_id}`);
    expect(capture.source).toBe("replay");
  });

  it("owns WebSocket control and binary PCM framing", async () => {
    FakeWebSocket.instances = [];
    const runtime = new LocalRuntime({
      baseUrl: "http://127.0.0.1:8002",
      fetchImplementation: fakeFetch,
      WebSocketImplementation: FakeWebSocket as unknown as typeof WebSocket,
    });
    const starting = runtime.startCapture(
      {
        schema_version: "atpiano.contract.v1",
        workspace_id: "local",
        source: "microphone",
        sample_rate_hz: 48_000,
        request_id: "capture-1",
      },
      { requestId: "capture-1" },
    );
    const socket = FakeWebSocket.instances[0]!;
    socket.emit("open");
    expect(JSON.parse(socket.sent[0] as string).type).toBe("start");
    socket.message({
      schema_version: "atpiano.corrected-stream.v1",
      type: "ready",
      session_id: session.session_id,
      sample_rate_hz: 48_000,
    });
    const capture = await starting;

    runtime.streamPcm({
      envelope: {
        protocol_version: "atpiano.pcm.v1",
        workspace_id: "local",
        session_id: session.session_id,
        capture_id: capture.capture_id,
        stream_id: "stream-1",
        sequence: 0,
        first_sample: 0,
        frame_count: 4,
        sample_rate_hz: 48_000,
        channel_count: 1,
        sample_format: "pcm-s16le",
        payload_byte_count: 8,
      },
      payload: new ArrayBuffer(8),
    });
    const packed = socket.sent[1] as ArrayBuffer;
    expect(new TextDecoder().decode(packed.slice(0, 4))).toBe("ATPB");
    expect(new DataView(packed).getUint32(24, true)).toBe(4);

    const stopping = runtime.stopCapture(
      {
        schema_version: "atpiano.contract.v1",
        workspace_id: "local",
        session_id: session.session_id,
        capture_id: capture.capture_id,
        accepted_frame_count: 4,
        request_id: "capture-1",
      },
      { requestId: "capture-1" },
    );
    expect(JSON.parse(socket.sent[2] as string)).toMatchObject({
      type: "stop",
      frame_count: 4,
      block_count: 1,
    });
    socket.message({
      schema_version: "atpiano.corrected-stream.v1",
      type: "stopped",
    });

    expect((await stopping).session_id).toBe(session.session_id);
  });
});

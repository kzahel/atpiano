import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

import type {
  Artifact,
  Capture,
  EventRevision,
  Horizon,
  Job,
  RuntimeCapabilities,
  Session,
  Workspace,
} from "../src/runtime/atpiano-runtime.js";
import {
  FixtureRuntime,
  type FixtureRuntimeData,
} from "../src/runtime/fixture-runtime.js";

interface FixtureObject {
  readonly model: string;
  readonly value: unknown;
}

const repositoryRoot = fileURLToPath(new URL("../..", import.meta.url));
const fixtureDocument = JSON.parse(
  readFileSync(
    `${repositoryRoot}/contracts/fixtures/v1/contract-examples.json`,
    "utf8",
  ),
) as { readonly objects: readonly FixtureObject[] };

function fixture<T>(model: string): T {
  const selected = fixtureDocument.objects.find(
    (candidate) => candidate.model === model,
  );
  assert.ok(selected);
  return selected.value as T;
}

function runtimeData(): FixtureRuntimeData {
  const workspace = fixture<Workspace>("Workspace");
  const session = fixture<Session>("Session");
  const capture = fixture<Capture>("Capture");
  const event = fixture<EventRevision>("EventRevision");
  const horizon = fixture<Horizon>("Horizon");
  const artifact = fixture<Artifact>("Artifact");
  const scoreJob = fixture<Job>("Job");
  return {
    fixtureId: "deterministic-musical-loop-v1",
    capabilities: fixture<RuntimeCapabilities>("RuntimeCapabilities"),
    workspace,
    capture,
    sessions: [{
      session,
      horizon,
      events: {
        schema_version: "atpiano.contract.v1",
        workspace_id: workspace.workspace_id,
        session_id: session.session_id,
        start_sample: 0,
        end_sample: session.source_frame_count,
        items: [event],
        next_cursor: null,
      },
      artifacts: {
        schema_version: "atpiano.contract.v1",
        workspace_id: workspace.workspace_id,
        session_id: session.session_id,
        items: [artifact],
        next_cursor: null,
      },
      artifactAccess: {
        [artifact.artifact_id]: {
          schema_version: "atpiano.contract.v1",
          workspace_id: workspace.workspace_id,
          session_id: session.session_id,
          artifact_id: artifact.artifact_id,
          media_type: artifact.media_type,
          download_name: artifact.filename,
          url: `/fixture/${artifact.artifact_id}`,
          expires_at: null,
        },
      },
    }],
    scoreJob,
    trashedAt: "2026-07-26T11:00:00Z",
  };
}

test("fixture runtime exercises replay, PCM, Stop, and explicit reads", async () => {
  const data = runtimeData();
  const runtime = new FixtureRuntime(data);
  const request = { requestId: "request-1" };

  const workspaces = await runtime.listWorkspaces(request);
  const sessions = await runtime.listSessions(
    data.workspace.workspace_id,
    request,
  );
  assert.equal(workspaces.items[0]?.workspace_id, "local");
  assert.equal(
    sessions.items[0]?.session_id,
    data.sessions[0]!.session.session_id,
  );
  const annotation = await runtime.updateSessionAnnotation(
    {
      schema_version: "atpiano.contract.v1",
      workspace_id: data.workspace.workspace_id,
      session_id: data.sessions[0]!.session.session_id,
      display_name: "Renamed fixture",
      request_id: "request-rename",
    },
    request,
  );
  assert.equal(annotation.display_name, "Renamed fixture");
  assert.equal(
    (
      await runtime.getSession(
        data.workspace.workspace_id,
        data.sessions[0]!.session.session_id,
        request,
      )
    ).display_name,
    "Renamed fixture",
  );

  const capture = await runtime.startReplay(
    {
      schema_version: "atpiano.contract.v1",
      workspace_id: data.workspace.workspace_id,
      fixture_id: data.fixtureId,
      repeat: 1,
      silence_samples: 0,
      realtime: false,
      request_id: "request-replay",
    },
    request,
  );
  const payload = new ArrayBuffer(8);
  runtime.streamPcm({
    envelope: {
      protocol_version: "atpiano.pcm.v1",
      workspace_id: data.workspace.workspace_id,
      session_id: data.sessions[0]!.session.session_id,
      capture_id: capture.capture_id,
      stream_id: "stream-1",
      sequence: 0,
      first_sample: 0,
      frame_count: 4,
      sample_rate_hz: capture.sample_rate_hz,
      channel_count: 1,
      sample_format: "pcm-s16le",
      payload_byte_count: 8,
    },
    payload,
  });
  const stopped = await runtime.stopCapture(
    {
      schema_version: "atpiano.contract.v1",
      workspace_id: data.workspace.workspace_id,
      session_id: data.sessions[0]!.session.session_id,
      capture_id: capture.capture_id,
      accepted_frame_count: 4,
      request_id: "request-stop",
    },
    request,
  );

  assert.equal(stopped.status, "complete");
  assert.equal(stopped.source_frame_count, 4);
  assert.equal(
    (await runtime.listArtifacts(
      data.workspace.workspace_id,
      data.sessions[0]!.session.session_id,
      request,
    )).items[0]?.artifact_id,
    data.sessions[0]!.artifacts.items[0]?.artifact_id,
  );
});

test("fixture runtime models recording import as upload, not replay", async () => {
  const data = runtimeData();
  const runtime = new FixtureRuntime(data);
  const file = new Blob(["wav"]);
  const capture = await runtime.importRecording(
    {
      schema_version: "atpiano.contract.v1",
      workspace_id: data.workspace.workspace_id,
      filename: "Player take.wav",
      media_type: "audio/wav",
      byte_count: file.size,
      request_id: "request-import",
    },
    file,
    { requestId: "request-import" },
  );
  const session = await runtime.getSession(
    data.workspace.workspace_id,
    capture.session_id,
    { requestId: "request-import-session" },
  );

  assert.equal(capture.source, "upload");
  assert.equal(session.source, "upload");
  assert.equal(session.display_name, "Player take");
});

test("fixture subscription disposal suppresses late delivery", async () => {
  const data = runtimeData();
  const runtime = new FixtureRuntime(data);
  let deliveries = 0;
  const subscription = runtime.subscribeEvents(
    data.workspace.workspace_id,
    data.sessions[0]!.session.session_id,
    {
      requestId: "request-events",
      startSample: 0,
      endSample: 100,
    },
    {
      next() {
        deliveries += 1;
      },
      error(error) {
        throw error;
      },
    },
  );
  subscription.close();
  await Promise.resolve();

  assert.equal(deliveries, 0);
});

test("fixture runtime rejects stale targets and cancelled requests", async () => {
  const data = runtimeData();
  const runtime = new FixtureRuntime(data);
  const controller = new AbortController();
  controller.abort(new Error("cancelled"));

  await assert.rejects(
    runtime.getSession("local", data.sessions[0]!.session.session_id, {
      requestId: "cancelled",
      signal: controller.signal,
    }),
    /cancelled/,
  );
  await assert.rejects(
    runtime.getSession("other", data.sessions[0]!.session.session_id, {
      requestId: "wrong-workspace",
    }),
    /workspace does not exist/,
  );
});

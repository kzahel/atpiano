import { useCallback, useRef } from "react";

import { requestId } from "../lib/format.js";
import type {
  AtpianoRuntime,
  Capture,
  Session,
} from "../runtime/atpiano-runtime.js";
import { useWorkspaceStore } from "../state/workspace-store.js";

const constraints: MediaTrackConstraints = {
  channelCount: 1,
  echoCancellation: false,
  noiseSuppression: false,
  autoGainControl: false,
};

interface BrowserCapture {
  readonly operationId: string;
  readonly capture: Capture;
  readonly stream: MediaStream;
  readonly context: AudioContext;
  readonly source: MediaStreamAudioSourceNode;
  readonly node: AudioWorkletNode;
  readonly muted: GainNode;
  frameCount: number;
  sequence: number;
  stoppedFrameCount: number | null;
  stopWorklet: ((complete: boolean) => void) | null;
}

function pcm16(samples: Float32Array): ArrayBuffer {
  const buffer = new ArrayBuffer(samples.length * 2);
  const view = new DataView(buffer);
  for (let index = 0; index < samples.length; index += 1) {
    const sample = Math.max(-1, Math.min(1, samples[index]!));
    view.setInt16(
      index * 2,
      sample < 0 ? sample * 32_768 : sample * 32_767,
      true,
    );
  }
  return buffer;
}

async function closeBrowserCapture(value: BrowserCapture): Promise<void> {
  value.stream.getTracks().forEach((track) => track.stop());
  value.source.disconnect();
  value.node.disconnect();
  value.muted.disconnect();
  if (value.context.state !== "closed") await value.context.close();
}

export function useMicrophone({
  runtime,
  workspaceId,
  performerProfileId,
  onChanged,
  onStopped,
}: {
  readonly runtime: AtpianoRuntime;
  readonly workspaceId: string | undefined;
  readonly performerProfileId: string | null;
  readonly onChanged: () => Promise<void>;
  readonly onStopped: (session: Session) => void;
}) {
  const browserCapture = useRef<BrowserCapture | null>(null);
  const beginCapture = useWorkspaceStore((state) => state.beginCapture);
  const warmCapture = useWorkspaceStore((state) => state.warmCapture);
  const recordCapture = useWorkspaceStore((state) => state.recordCapture);
  const markStopping = useWorkspaceStore((state) => state.stopCapture);
  const completeCapture = useWorkspaceStore((state) => state.completeCapture);
  const failCapture = useWorkspaceStore((state) => state.failCapture);

  const start = useCallback(async () => {
    if (!workspaceId) return;
    const operationId = requestId("microphone");
    beginCapture(operationId);
    let stream: MediaStream | null = null;
    let context: AudioContext | null = null;
    try {
      if (!navigator.mediaDevices?.getUserMedia || !window.AudioWorkletNode) {
        throw new Error("This browser does not support AudioWorklet microphone capture.");
      }
      stream = await navigator.mediaDevices.getUserMedia({
        audio: constraints,
        video: false,
      });
      context = new AudioContext();
      await context.resume();
      await context.audioWorklet.addModule("/capture-processor.js");
      warmCapture(operationId);
      const capture = await runtime.startCapture(
        {
          schema_version: "atpiano.contract.v1",
          workspace_id: workspaceId,
          source: "microphone",
          sample_rate_hz: context.sampleRate,
          performed_by_profile_id: performerProfileId,
          request_id: operationId,
        },
        { requestId: operationId },
      );
      const source = context.createMediaStreamSource(stream);
      const node = new AudioWorkletNode(context, "atpiano-capture");
      const muted = context.createGain();
      muted.gain.value = 0;
      const state: BrowserCapture = {
        operationId,
        capture,
        stream,
        context,
        source,
        node,
        muted,
        frameCount: 0,
        sequence: 0,
        stoppedFrameCount: null,
        stopWorklet: null,
      };
      browserCapture.current = state;
      node.port.onmessage = (event: MessageEvent<{
        type: "chunk" | "stopped";
        firstSample?: number;
        frameCount?: number;
        samples?: ArrayBuffer;
      }>) => {
        if (event.data.type === "stopped") {
          state.stoppedFrameCount = event.data.frameCount ?? null;
          state.stopWorklet?.(true);
          return;
        }
        if (
          event.data.samples === undefined ||
          event.data.firstSample !== state.frameCount
        ) {
          failCapture(operationId, new Error("Browser sample sequence became discontinuous."));
          return;
        }
        const samples = new Float32Array(event.data.samples);
        const payload = pcm16(samples);
        runtime.streamPcm({
          envelope: {
            protocol_version: "atpiano.pcm.v1",
            workspace_id: workspaceId,
            session_id: capture.session_id,
            capture_id: capture.capture_id,
            stream_id: `stream:${capture.capture_id}`,
            sequence: state.sequence,
            first_sample: state.frameCount,
            frame_count: samples.length,
            sample_rate_hz: context!.sampleRate,
            channel_count: 1,
            sample_format: "pcm-s16le",
            payload_byte_count: payload.byteLength,
          },
          payload,
        });
        state.frameCount += samples.length;
        state.sequence += 1;
      };
      source.connect(node);
      node.connect(muted);
      muted.connect(context.destination);
      recordCapture(operationId, capture);
      await onChanged();
    } catch (error) {
      stream?.getTracks().forEach((track) => track.stop());
      if (context && context.state !== "closed") await context.close();
      failCapture(operationId, error);
    }
  }, [
    beginCapture,
    failCapture,
    onChanged,
    performerProfileId,
    recordCapture,
    runtime,
    warmCapture,
    workspaceId,
  ]);

  const stop = useCallback(async () => {
    const state = browserCapture.current;
    if (!state) return;
    markStopping(state.operationId);
    try {
      const workletStopped = new Promise<boolean>((resolve) => {
        state.stopWorklet = resolve;
      });
      state.node.port.postMessage({ type: "stop" });
      const complete = await Promise.race([
        workletStopped,
        new Promise<false>((resolve) =>
          window.setTimeout(() => resolve(false), 1_500),
        ),
      ]);
      if (!complete || state.stoppedFrameCount !== state.frameCount) {
        throw new Error("The browser could not close a complete sample sequence.");
      }
      const settledSession = await runtime.stopCapture(
        {
          schema_version: "atpiano.contract.v1",
          workspace_id: state.capture.workspace_id,
          session_id: state.capture.session_id,
          capture_id: state.capture.capture_id,
          accepted_frame_count: state.frameCount,
          request_id: state.operationId,
        },
        { requestId: state.operationId },
      );
      await closeBrowserCapture(state);
      browserCapture.current = null;
      completeCapture(state.operationId);
      await onChanged();
      onStopped(settledSession);
    } catch (error) {
      await closeBrowserCapture(state);
      browserCapture.current = null;
      failCapture(state.operationId, error);
    }
  }, [
    completeCapture,
    failCapture,
    markStopping,
    onChanged,
    onStopped,
    runtime,
  ]);

  return { start, stop };
}

import { describe, expect, it } from "vitest";

import {
  CAPTURE_LATENCY_HINT,
  collectBrowserCaptureMetadata,
} from "../../src/lib/capture-metadata.js";

describe("browser capture metadata", () => {
  it("retains browser, device, and actual audio settings without device IDs", async () => {
    Object.defineProperties(navigator, {
      hardwareConcurrency: { configurable: true, value: 4 },
      deviceMemory: { configurable: true, value: 3 },
      maxTouchPoints: { configurable: true, value: 5 },
      userAgentData: {
        configurable: true,
        value: {
          brands: [{ brand: "Chromium", version: "150" }],
          mobile: true,
          platform: "Android",
          async getHighEntropyValues(hints: readonly string[]) {
            expect(hints).toContain("model");
            return {
              architecture: "arm",
              bitness: "64",
              model: "Test Tablet",
              platformVersion: "16.0.0",
            };
          },
        },
      },
    });
    const track = {
      label: "Built-in microphone",
      readyState: "live",
      enabled: true,
      muted: false,
      getSettings: () => ({
        autoGainControl: false,
        channelCount: 1,
        deviceId: "do-not-retain",
        groupId: "do-not-retain",
        sampleRate: 48_000,
      }),
      getConstraints: () => ({
        channelCount: 1,
        echoCancellation: false,
      }),
      getCapabilities: () => ({
        channelCount: { min: 1, max: 2 },
        deviceId: "do-not-retain",
      }),
    } as unknown as MediaStreamTrack;
    const metadata = await collectBrowserCaptureMetadata({
      stream: {
        getAudioTracks: () => [track],
      } as unknown as MediaStream,
      context: {
        sampleRate: 48_000,
        state: "running",
        baseLatency: 0.08,
        outputLatency: 0.04,
      } as AudioContext,
      requestId: "microphone:test",
      requestedConstraints: {
        channelCount: 1,
        echoCancellation: false,
        noiseSuppression: false,
        autoGainControl: false,
      },
      requestedLatencyHint: CAPTURE_LATENCY_HINT,
    });

    expect(metadata).toMatchObject({
      schema_version: "atpiano.browser-capture-client.v1",
      request_id: "microphone:test",
      browser: {
        user_agent_data: {
          mobile: true,
          platform: "Android",
          high_entropy: {
            architecture: "arm",
            bitness: "64",
            model: "Test Tablet",
            platformVersion: "16.0.0",
          },
        },
      },
      device: {
        hardware_concurrency: 4,
        device_memory_gib: 3,
        max_touch_points: 5,
      },
      audio: {
        track: {
          label: "Built-in microphone",
          settings: {
            autoGainControl: false,
            channelCount: 1,
            sampleRate: 48_000,
          },
          device_id_present: true,
          group_id_present: true,
        },
        context: {
          sample_rate_hz: 48_000,
          requested_latency_hint: "playback",
          base_latency_s: 0.08,
          output_latency_s: 0.04,
        },
      },
    });
    expect(JSON.stringify(metadata)).not.toContain("do-not-retain");
    const mutableNavigator = navigator as unknown as Record<string, unknown>;
    delete mutableNavigator.hardwareConcurrency;
    delete mutableNavigator.deviceMemory;
    delete mutableNavigator.maxTouchPoints;
    delete mutableNavigator.userAgentData;
  });
});

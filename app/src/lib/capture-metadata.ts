export const CAPTURE_LATENCY_HINT = "playback" as const;

interface NavigatorUADataLike {
  readonly brands?: readonly {
    readonly brand: string;
    readonly version: string;
  }[];
  readonly mobile?: boolean;
  readonly platform?: string;
  getHighEntropyValues?(
    hints: readonly string[],
  ): Promise<Record<string, unknown>>;
}

interface NavigatorConnectionLike {
  readonly effectiveType?: string;
  readonly downlink?: number;
  readonly rtt?: number;
  readonly saveData?: boolean;
}

type ExtendedNavigator = Navigator & {
  readonly deviceMemory?: number;
  readonly userAgentData?: NavigatorUADataLike;
  readonly connection?: NavigatorConnectionLike;
};

function finiteNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value)
    ? value
    : null;
}

function safeRecord(
  value: object | undefined,
  omittedKeys: ReadonlySet<string> = new Set(),
): Record<string, unknown> | null {
  if (value === undefined) return null;
  return Object.fromEntries(
    Object.entries(value).filter(
      ([key, item]) =>
        !omittedKeys.has(key) &&
        item !== undefined &&
        (typeof item !== "number" || Number.isFinite(item)),
    ),
  );
}

async function userAgentData(
  navigatorValue: ExtendedNavigator,
): Promise<Record<string, unknown> | null> {
  const data = navigatorValue.userAgentData;
  if (data === undefined) return null;
  const lowEntropy = {
    brands: data.brands ?? [],
    mobile: data.mobile ?? null,
    platform: data.platform ?? null,
  };
  if (data.getHighEntropyValues === undefined) return lowEntropy;
  try {
    const highEntropy = await data.getHighEntropyValues([
      "architecture",
      "bitness",
      "formFactors",
      "fullVersionList",
      "model",
      "platformVersion",
      "uaFullVersion",
      "wow64",
    ]);
    return {
      ...lowEntropy,
      high_entropy: safeRecord(highEntropy),
    };
  } catch (error) {
    return {
      ...lowEntropy,
      high_entropy_error:
        error instanceof Error ? `${error.name}: ${error.message}` : String(error),
    };
  }
}

export async function collectBrowserCaptureMetadata({
  stream,
  context,
  requestId,
  requestedConstraints,
  requestedLatencyHint,
}: {
  readonly stream: MediaStream;
  readonly context: AudioContext;
  readonly requestId: string;
  readonly requestedConstraints: MediaTrackConstraints;
  readonly requestedLatencyHint: AudioContextLatencyCategory;
}): Promise<Record<string, unknown>> {
  const navigatorValue = navigator as ExtendedNavigator;
  const track = stream.getAudioTracks()[0];
  const trackSettings = track?.getSettings();
  const omittedDeviceIdentifiers = new Set(["deviceId", "groupId"]);
  const screenOrientation = globalThis.screen?.orientation;
  const visualViewport = globalThis.visualViewport;
  const connection = navigatorValue.connection;
  return {
    schema_version: "atpiano.browser-capture-client.v1",
    started_at: new Date().toISOString(),
    request_id: requestId,
    application: {
      build_id: __ATPIANO_BUILD_ID__,
      origin: globalThis.location?.origin ?? null,
      secure_context: globalThis.isSecureContext,
      cross_origin_isolated: globalThis.crossOriginIsolated,
      visibility_state: globalThis.document?.visibilityState ?? null,
    },
    browser: {
      user_agent: navigatorValue.userAgent,
      user_agent_data: await userAgentData(navigatorValue),
      language: navigatorValue.language,
      languages: [...navigatorValue.languages],
      legacy_platform: navigatorValue.platform,
      legacy_vendor: navigatorValue.vendor,
    },
    device: {
      hardware_concurrency: navigatorValue.hardwareConcurrency,
      device_memory_gib: finiteNumber(navigatorValue.deviceMemory),
      max_touch_points: navigatorValue.maxTouchPoints,
    },
    display: {
      screen_width_px: finiteNumber(globalThis.screen?.width),
      screen_height_px: finiteNumber(globalThis.screen?.height),
      screen_color_depth: finiteNumber(globalThis.screen?.colorDepth),
      orientation_type: screenOrientation?.type ?? null,
      orientation_angle: finiteNumber(screenOrientation?.angle),
      viewport_width_px: finiteNumber(globalThis.innerWidth),
      viewport_height_px: finiteNumber(globalThis.innerHeight),
      visual_viewport_width_px: finiteNumber(visualViewport?.width),
      visual_viewport_height_px: finiteNumber(visualViewport?.height),
      device_pixel_ratio: finiteNumber(globalThis.devicePixelRatio),
    },
    locale: {
      time_zone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    },
    network: connection === undefined
      ? null
      : {
          effective_type: connection.effectiveType ?? null,
          downlink_mbps: finiteNumber(connection.downlink),
          round_trip_time_ms: finiteNumber(connection.rtt),
          save_data: connection.saveData ?? null,
        },
    audio: {
      requested_constraints: safeRecord(requestedConstraints),
      track: track === undefined
        ? null
        : {
            label: track.label || null,
            ready_state: track.readyState,
            enabled: track.enabled,
            muted: track.muted,
            settings: safeRecord(
              trackSettings,
              omittedDeviceIdentifiers,
            ),
            constraints: safeRecord(track.getConstraints()),
            capabilities: safeRecord(
              track.getCapabilities(),
              omittedDeviceIdentifiers,
            ),
            device_id_present: Boolean(trackSettings?.deviceId),
            group_id_present: Boolean(trackSettings?.groupId),
          },
      context: {
        sample_rate_hz: context.sampleRate,
        state: context.state,
        requested_latency_hint: requestedLatencyHint,
        base_latency_s: finiteNumber(context.baseLatency),
        output_latency_s: finiteNumber(context.outputLatency),
      },
      processor: {
        name: "atpiano-capture",
        script_path: "/capture-processor.js",
        output_block_frames: 2_048,
        sample_format: "pcm-s16le",
      },
    },
  };
}

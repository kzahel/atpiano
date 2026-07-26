import type {
  EventRevision,
  Horizon,
} from "../runtime/atpiano-runtime.js";

export interface PedalDisplaySegment {
  readonly start: number;
  readonly end: number;
  readonly suspectLongEstimate: boolean;
}

export function pedalDisplaySegment(
  pedal: EventRevision,
  horizon: Horizon | undefined,
  totalSamples: number,
  sampleRateHz: number,
): PedalDisplaySegment | null {
  if (
    pedal.lifecycle === "retracted" ||
    (pedal.kind !== "sustain" && pedal.kind !== "soft-pedal")
  ) {
    return null;
  }

  const visibleBoundary =
    pedal.lifecycle === "committed"
      ? (horizon?.commit_sample ?? totalSamples)
      : (horizon?.audio_head_sample ?? totalSamples);
  const end = Math.min(
    Math.max(pedal.onset_sample, pedal.offset_sample ?? visibleBoundary),
    visibleBoundary,
    totalSamples,
  );
  if (pedal.onset_sample >= visibleBoundary || end <= pedal.onset_sample) {
    return null;
  }

  const duration = end - pedal.onset_sample;
  return {
    start: pedal.onset_sample,
    end,
    suspectLongEstimate:
      duration >= sampleRateHz * 10 &&
      duration >= Math.max(1, totalSamples) * 0.5,
  };
}

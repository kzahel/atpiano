import { formatClock } from "../lib/format.js";
import { usePlaybackControls } from "./playback-provider.js";
import { usePlaybackStore } from "../state/playback-store.js";
import { useWorkspaceStore } from "../state/workspace-store.js";

export function AudioPlayback({
  unavailableReason,
}: {
  readonly unavailableReason: string;
}) {
  const controls = usePlaybackControls();
  const available = usePlaybackStore((state) => state.available);
  const status = usePlaybackStore((state) => state.status);
  const positionSample = usePlaybackStore((state) => state.positionSample);
  const totalSamples = usePlaybackStore((state) => state.totalSamples);
  const sampleRateHz = usePlaybackStore((state) => state.sampleRateHz);
  const error = usePlaybackStore((state) => state.error);
  const inspectionSample = useWorkspaceStore(
    (state) => state.inspectionSample,
  );
  const playing = status === "playing";

  return (
    <section className="playback-transport" aria-label="Recorded audio playback">
      <button
        className="playback-button"
        type="button"
        disabled={!available}
        onClick={controls.toggle}
        aria-label={playing ? "Pause recorded audio" : "Play recorded audio"}
      >
        <span aria-hidden="true">{playing ? "Ⅱ" : "▶"}</span>
      </button>
      <label className="playback-scrubber">
        <span className="sr-only">Recorded audio position</span>
        <input
          type="range"
          min={0}
          max={Math.max(1, totalSamples)}
          value={positionSample}
          step={Math.max(1, Math.round(sampleRateHz / 100))}
          disabled={!available}
          onChange={(event) =>
            controls.seek(Number(event.currentTarget.value))
          }
        />
      </label>
      <output>
        {formatClock(positionSample, sampleRateHz)}
        <span aria-hidden="true"> / </span>
        <span className="sr-only"> of </span>
        {formatClock(totalSamples, sampleRateHz)}
      </output>
      <span className="playback-status">
        {error ??
          (!available
            ? unavailableReason
            : playing
              ? "Playing"
              : status === "ended"
                ? "Ended"
                : "Paused")}
      </span>
      {inspectionSample !== null && !playing && (
        <button
          className="text-button"
          type="button"
          onClick={controls.clearInspection}
        >
          Follow latest attack
        </button>
      )}
    </section>
  );
}

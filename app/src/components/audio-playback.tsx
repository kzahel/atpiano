import { useEffect, useRef, useState } from "react";

import { formatClock } from "../lib/format.js";

export interface AudioPlaybackSource {
  readonly artifactId: string;
  readonly url: string;
  readonly startSample: number;
  readonly endSample: number;
}

function sourceIndexAt(
  sources: readonly AudioPlaybackSource[],
  sample: number,
): number {
  const index = sources.findIndex((source) => sample < source.endSample);
  return index === -1 ? Math.max(0, sources.length - 1) : index;
}

export function AudioPlayback({
  sources,
  totalSamples,
  sampleRateHz,
  inspectionSample,
  onInspect,
  unavailableReason,
}: {
  readonly sources: readonly AudioPlaybackSource[];
  readonly totalSamples: number;
  readonly sampleRateHz: number;
  readonly inspectionSample: number | null;
  readonly onInspect: (sample: number | null) => void;
  readonly unavailableReason: string;
}) {
  const audio = useRef<HTMLAudioElement>(null);
  const desiredSample = useRef(0);
  const shouldPlay = useRef(false);
  const seeking = useRef(false);
  const [activeIndex, setActiveIndex] = useState(0);
  const [positionSample, setPositionSample] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const source = sources[activeIndex];
  const sourceKey = sources.map((item) => item.artifactId).join("|");

  const playElement = () => {
    if (!audio.current) return;
    void audio.current.play().catch(() => {
      shouldPlay.current = false;
      setPlaying(false);
      setError("Recorded audio could not be played.");
    });
  };

  const seekTo = (rawSample: number) => {
    const sample = Math.max(0, Math.min(totalSamples, rawSample));
    desiredSample.current = sample;
    setPositionSample(sample);
    onInspect(sample);
    if (!sources.length) return;
    const nextIndex = sourceIndexAt(sources, sample);
    if (nextIndex !== activeIndex) {
      setActiveIndex(nextIndex);
      return;
    }
    if (audio.current && source && audio.current.readyState >= 1) {
      seeking.current = true;
      audio.current.currentTime =
        (sample - source.startSample) / sampleRateHz;
      if (shouldPlay.current) playElement();
    }
  };

  useEffect(() => {
    shouldPlay.current = false;
    setPlaying(false);
    setActiveIndex(0);
    setPositionSample(0);
    desiredSample.current = 0;
    setError(null);
    if (audio.current && !audio.current.paused) audio.current.pause();
  }, [sourceKey]);

  useEffect(() => {
    if (
      inspectionSample !== null &&
      Math.abs(inspectionSample - positionSample) > sampleRateHz / 20
    ) {
      seekTo(inspectionSample);
    }
  }, [inspectionSample]);

  const togglePlayback = () => {
    if (!sources.length) return;
    if (playing) {
      shouldPlay.current = false;
      setPlaying(false);
      audio.current?.pause();
      return;
    }
    setError(null);
    shouldPlay.current = true;
    setPlaying(true);
    const restart = positionSample >= totalSamples;
    seekTo(restart ? 0 : positionSample);
    if (!restart && audio.current?.readyState) playElement();
  };

  const updatePositionFromElement = () => {
    if (
      !audio.current ||
      !source ||
      audio.current.readyState < 1 ||
      seeking.current
    ) {
      return;
    }
    const sample = Math.min(
      totalSamples,
      Math.round(
        source.startSample + audio.current.currentTime * sampleRateHz,
      ),
    );
    if (sample === desiredSample.current) return;
    desiredSample.current = sample;
    setPositionSample(sample);
    onInspect(sample);
  };

  useEffect(() => {
    if (!playing || !source) return;
    let animationFrame = 0;
    const update = () => {
      updatePositionFromElement();
      animationFrame = window.requestAnimationFrame(update);
    };
    animationFrame = window.requestAnimationFrame(update);
    return () => window.cancelAnimationFrame(animationFrame);
  }, [
    onInspect,
    playing,
    sampleRateHz,
    source?.artifactId,
    totalSamples,
  ]);

  return (
    <section className="playback-transport" aria-label="Recorded audio playback">
      <audio
        ref={audio}
        src={source?.url}
        preload="metadata"
        onLoadedMetadata={() => {
          if (!audio.current || !source) return;
          seeking.current = true;
          audio.current.currentTime = Math.max(
            0,
            (desiredSample.current - source.startSample) / sampleRateHz,
          );
          if (shouldPlay.current) playElement();
        }}
        onSeeked={() => {
          seeking.current = false;
        }}
        onTimeUpdate={() => {
          updatePositionFromElement();
        }}
        onEnded={() => {
          const nextIndex = activeIndex + 1;
          if (nextIndex < sources.length) {
            const nextSample = sources[nextIndex]!.startSample;
            desiredSample.current = nextSample;
            setPositionSample(nextSample);
            onInspect(nextSample);
            setActiveIndex(nextIndex);
            return;
          }
          shouldPlay.current = false;
          setPlaying(false);
          setPositionSample(totalSamples);
          onInspect(totalSamples);
        }}
      />
      <button
        className="playback-button"
        type="button"
        disabled={!sources.length}
        onClick={togglePlayback}
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
          disabled={!sources.length}
          onChange={(event) => seekTo(Number(event.currentTarget.value))}
        />
      </label>
      <output>
        {formatClock(positionSample, sampleRateHz)}
        <span aria-hidden="true"> / </span>
        <span className="sr-only"> of </span>
        {formatClock(totalSamples, sampleRateHz)}
      </output>
      <span className="playback-status">
        {error ?? (!sources.length ? unavailableReason : playing ? "Playing" : "Paused")}
      </span>
      {inspectionSample !== null && !playing && (
        <button
          className="text-button"
          type="button"
          onClick={() => {
            seekTo(0);
            onInspect(null);
          }}
        >
          Follow latest attack
        </button>
      )}
    </section>
  );
}

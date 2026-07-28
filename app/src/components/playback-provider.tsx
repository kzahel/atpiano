import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { usePlaybackStore } from "../state/playback-store.js";
import { useWorkspaceStore } from "../state/workspace-store.js";

export interface AudioPlaybackSource {
  readonly artifactId: string;
  readonly url: string;
  readonly startSample: number;
  readonly endSample: number;
}

interface PlaybackControls {
  readonly play: () => void;
  readonly pause: () => void;
  readonly toggle: () => void;
  readonly seek: (sample: number) => void;
  readonly playSession: (sessionId: string) => void;
  readonly seekSession: (sessionId: string, sample: number) => void;
  readonly clearInspection: () => void;
}

const PlaybackControlsContext = createContext<PlaybackControls | null>(null);

export function usePlaybackControls(): PlaybackControls {
  const controls = useContext(PlaybackControlsContext);
  if (!controls) {
    throw new Error("Playback controls require PlaybackProvider");
  }
  return controls;
}

function sourceIndexAt(
  sources: readonly AudioPlaybackSource[],
  sample: number,
): number {
  const index = sources.findIndex((source) => sample < source.endSample);
  return index === -1 ? Math.max(0, sources.length - 1) : index;
}

export function PlaybackProvider({
  sessionId,
  sources,
  totalSamples,
  sampleRateHz,
  cueSample = 0,
  cueReady = true,
  sourceError = null,
  selectedSessionId = sessionId,
  onSessionRequest = () => undefined,
  children,
}: {
  readonly sessionId: string | null;
  readonly sources: readonly AudioPlaybackSource[];
  readonly totalSamples: number;
  readonly sampleRateHz: number;
  readonly cueSample?: number;
  readonly cueReady?: boolean;
  readonly sourceError?: string | null;
  readonly selectedSessionId?: string | null;
  readonly onSessionRequest?: (sessionId: string) => void;
  readonly children: ReactNode;
}) {
  const audio = useRef<HTMLAudioElement>(null);
  const desiredSample = useRef(0);
  const shouldPlay = useRef(false);
  const seeking = useRef(false);
  const manualPositionChosen = useRef(false);
  const pendingAction = useRef<
    | { readonly kind: "play"; readonly sessionId: string }
    | {
        readonly kind: "seek";
        readonly sessionId: string;
        readonly sample: number;
      }
    | null
  >(null);
  const seekRef = useRef<(sample: number) => void>(() => undefined);
  const [activeIndex, setActiveIndex] = useState(0);
  const playing = usePlaybackStore((state) => state.status === "playing");
  const source = sources[activeIndex];
  const sourceKey = sources.map((item) => item.artifactId).join("|");

  const publishPosition = useCallback((sample: number) => {
    usePlaybackStore.getState().setPosition(sample);
    if (sessionId === selectedSessionId) {
      useWorkspaceStore.getState().setInspectionSample(sample);
    }
  }, [selectedSessionId, sessionId]);

  const playElement = useCallback(() => {
    if (!audio.current) return;
    void audio.current.play().catch(() => {
      shouldPlay.current = false;
      usePlaybackStore.getState().setError(
        "Recorded audio could not be played.",
      );
    });
  }, []);

  const seekTo = useCallback((rawSample: number, manual: boolean) => {
    const sample = Math.max(0, Math.min(totalSamples, rawSample));
    if (manual) manualPositionChosen.current = true;
    desiredSample.current = sample;
    publishPosition(sample);
    if (!sources.length) return;
    const nextIndex = sourceIndexAt(sources, sample);
    if (nextIndex !== activeIndex) {
      seeking.current = true;
      setActiveIndex(nextIndex);
      return;
    }
    if (audio.current && source && audio.current.readyState >= 1) {
      seeking.current = true;
      audio.current.currentTime =
        (sample - source.startSample) / sampleRateHz;
      if (shouldPlay.current) playElement();
    }
  }, [
    activeIndex,
    playElement,
    publishPosition,
    sampleRateHz,
    source,
    sources,
    totalSamples,
  ]);
  const seek = useCallback(
    (sample: number) => seekTo(sample, true),
    [seekTo],
  );
  seekRef.current = seek;

  const pause = useCallback(() => {
    shouldPlay.current = false;
    if (audio.current && !audio.current.paused) audio.current.pause();
    const state = usePlaybackStore.getState();
    if (state.available && state.status !== "ended") {
      state.setStatus("paused");
    }
  }, []);

  const play = useCallback(() => {
    const state = usePlaybackStore.getState();
    if (!state.available || !sources.length) return;
    if (!cueReady) {
      if (sessionId) {
        pendingAction.current = { kind: "play", sessionId };
      }
      return;
    }
    state.clearError();
    shouldPlay.current = true;
    state.setStatus("playing");
    const freshRun =
      state.status === "idle" &&
      state.positionSample === 0 &&
      !manualPositionChosen.current;
    const restarting =
      state.status === "ended" || state.positionSample >= totalSamples;
    if (restarting) {
      state.followScore();
      manualPositionChosen.current = false;
    }
    if (freshRun || restarting) {
      seekTo(cueSample, false);
      return;
    }
    if (audio.current?.readyState) playElement();
  }, [
    cueReady,
    cueSample,
    playElement,
    seekTo,
    sessionId,
    sources.length,
    totalSamples,
  ]);

  const toggle = useCallback(() => {
    if (shouldPlay.current) pause();
    else play();
  }, [pause, play]);

  const playSession = useCallback((requestedSessionId: string) => {
    if (
      requestedSessionId !== sessionId ||
      !sources.length ||
      !cueReady
    ) {
      pendingAction.current = {
        kind: "play",
        sessionId: requestedSessionId,
      };
      if (requestedSessionId !== sessionId) {
        onSessionRequest(requestedSessionId);
      }
      return;
    }
    pendingAction.current = null;
    play();
  }, [
    cueReady,
    onSessionRequest,
    play,
    sessionId,
    sources.length,
  ]);

  const seekSession = useCallback((
    requestedSessionId: string,
    sample: number,
  ) => {
    if (requestedSessionId !== sessionId || !sources.length) {
      pendingAction.current = {
        kind: "seek",
        sessionId: requestedSessionId,
        sample,
      };
      if (requestedSessionId !== sessionId) {
        onSessionRequest(requestedSessionId);
      }
      return;
    }
    pendingAction.current = null;
    seek(sample);
  }, [onSessionRequest, seek, sessionId, sources.length]);

  const clearInspection = useCallback(() => {
    seek(0);
    useWorkspaceStore.getState().setInspectionSample(null);
  }, [seek]);

  useEffect(() => {
    shouldPlay.current = false;
    seeking.current = false;
    manualPositionChosen.current = false;
    if (audio.current && !audio.current.paused) audio.current.pause();
    setActiveIndex(0);
    desiredSample.current = 0;
    usePlaybackStore.getState().configure({
      sessionId,
      sourceKey,
      available: sources.length > 0,
      totalSamples,
      sampleRateHz,
    });
  }, [sampleRateHz, sessionId, sourceKey, sources.length, totalSamples]);

  useEffect(() => {
    if (!sourceError || !sessionId) return;
    usePlaybackStore.getState().setError(sourceError);
  }, [sessionId, sourceError]);

  useEffect(() => {
    const action = pendingAction.current;
    if (
      !action ||
      action.sessionId !== sessionId ||
      !sources.length ||
      (action.kind === "play" && !cueReady)
    ) {
      return;
    }
    pendingAction.current = null;
    if (action.kind === "seek") {
      seek(action.sample);
    } else {
      play();
    }
  }, [cueReady, play, seek, sessionId, sources.length]);

  useEffect(
    () =>
      useWorkspaceStore.subscribe((state, previous) => {
        const sample = state.inspectionSample;
        if (
          sessionId !== selectedSessionId ||
          sample === null ||
          sample === previous.inspectionSample ||
          Math.abs(
            sample - usePlaybackStore.getState().positionSample,
          ) <= sampleRateHz / 20
        ) {
          return;
        }
        seekRef.current(sample);
      }),
    [sampleRateHz, selectedSessionId, sessionId],
  );

  const updatePositionFromElement = useCallback(() => {
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
    publishPosition(sample);
  }, [publishPosition, sampleRateHz, source, totalSamples]);

  useEffect(() => {
    if (!playing || !source) return;
    let animationFrame = 0;
    const update = () => {
      updatePositionFromElement();
      animationFrame = window.requestAnimationFrame(update);
    };
    animationFrame = window.requestAnimationFrame(update);
    return () => window.cancelAnimationFrame(animationFrame);
  }, [playing, source, updatePositionFromElement]);

  useEffect(
    () => () => {
      shouldPlay.current = false;
      if (audio.current && !audio.current.paused) audio.current.pause();
    },
    [],
  );

  const controls = useMemo<PlaybackControls>(
    () => ({
      play,
      pause,
      toggle,
      seek,
      playSession,
      seekSession,
      clearInspection,
    }),
    [
      clearInspection,
      pause,
      play,
      playSession,
      seek,
      seekSession,
      toggle,
    ],
  );

  return (
    <PlaybackControlsContext.Provider value={controls}>
      <audio
        ref={audio}
        className="persistent-playback-audio"
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
        onTimeUpdate={updatePositionFromElement}
        onEnded={() => {
          const nextIndex = activeIndex + 1;
          if (nextIndex < sources.length) {
            const nextSample = sources[nextIndex]!.startSample;
            desiredSample.current = nextSample;
            publishPosition(nextSample);
            seeking.current = true;
            setActiveIndex(nextIndex);
            return;
          }
          shouldPlay.current = false;
          usePlaybackStore.getState().setStatus("ended");
          publishPosition(totalSamples);
        }}
        onError={() => {
          if (!source) return;
          shouldPlay.current = false;
          usePlaybackStore.getState().setError(
            "Recorded audio could not be played.",
          );
        }}
      />
      {children}
    </PlaybackControlsContext.Provider>
  );
}

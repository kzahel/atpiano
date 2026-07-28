import { create } from "zustand";

export type PlaybackStatus =
  | "idle"
  | "playing"
  | "paused"
  | "ended"
  | "error";

export type ScoreFollowState = "following" | "detached";

interface PlaybackConfiguration {
  readonly sessionId: string | null;
  readonly sourceKey: string;
  readonly available: boolean;
  readonly totalSamples: number;
  readonly sampleRateHz: number;
}

interface PlaybackState {
  sessionId: string | null;
  sourceKey: string;
  available: boolean;
  status: PlaybackStatus;
  positionSample: number;
  totalSamples: number;
  sampleRateHz: number;
  scoreFollow: ScoreFollowState;
  error: string | null;
  configure(configuration: PlaybackConfiguration): void;
  setStatus(status: PlaybackStatus): void;
  setPosition(positionSample: number): void;
  setError(error: string): void;
  clearError(): void;
  followScore(): void;
  detachScore(): void;
}

const initialPlayback = {
  sessionId: null,
  sourceKey: "",
  available: false,
  status: "idle" as const,
  positionSample: 0,
  totalSamples: 0,
  sampleRateHz: 48_000,
  scoreFollow: "following" as const,
  error: null,
};

export const usePlaybackStore = create<PlaybackState>((set) => ({
  ...initialPlayback,
  configure: (configuration) =>
    set((state) => {
      const identityChanged =
        state.sessionId !== configuration.sessionId ||
        state.sourceKey !== configuration.sourceKey;
      if (identityChanged) {
        return {
          ...configuration,
          status: "idle",
          positionSample: 0,
          scoreFollow: "following",
          error: null,
        };
      }
      return {
        available: configuration.available,
        totalSamples: configuration.totalSamples,
        sampleRateHz: configuration.sampleRateHz,
      };
    }),
  setStatus: (status) => set({ status }),
  setPosition: (positionSample) => set({ positionSample }),
  setError: (error) => set({ error, status: "error" }),
  clearError: () => set({ error: null }),
  followScore: () => set({ scoreFollow: "following" }),
  detachScore: () => set({ scoreFollow: "detached" }),
}));

export function resetPlaybackStore(): void {
  usePlaybackStore.setState(initialPlayback);
}

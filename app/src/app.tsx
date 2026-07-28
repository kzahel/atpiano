import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import { ArtifactPanel } from "./components/artifact-panel.js";
import { CaptureDeck } from "./components/capture-deck.js";
import { PerformanceViews } from "./components/performance-views.js";
import {
  PlaybackProvider,
  type AudioPlaybackSource,
} from "./components/playback-provider.js";
import { ScoreReader } from "./components/score-reader.js";
import { SessionRail } from "./components/session-rail.js";
import { SessionTitleEditor } from "./components/session-title-editor.js";
import { SessionsHome } from "./components/sessions-home.js";
import { useMicrophone } from "./hooks/use-microphone.js";
import { artifactText } from "./lib/artifact-content.js";
import { eventWindow, liveFrameCount } from "./lib/event-window.js";
import {
  formatClock,
  formatSessionDate,
  requestId,
  sessionSourceLabel,
} from "./lib/format.js";
import {
  firstVisibleNoteSample,
  openingEventPage,
} from "./lib/opening-event-page.js";
import { parseScoreAlignment } from "./lib/score-alignment.js";
import {
  scoreReaderRouteFromUrl,
  sessionIdFromUrl,
  urlForScoreReader,
  urlForSession,
  urlWithoutScoreReader,
  type ScoreReaderRoute,
} from "./lib/session-url.js";
import type {
  Artifact,
  EventPage,
  Job,
  ScoreVariant,
  Session,
  SessionPage,
} from "./runtime/atpiano-runtime.js";
import { useRuntime } from "./runtime/runtime-context.js";
import { useWorkspaceStore } from "./state/workspace-store.js";

function ViewSwitch({
  checked,
  label,
  onChange,
}: {
  readonly checked: boolean;
  readonly label: string;
  readonly onChange: () => void;
}) {
  return (
    <label className={`view-chip ${checked ? "checked" : ""}`}>
      <input type="checkbox" checked={checked} onChange={onChange} />
      <span aria-hidden="true">{checked ? "✓" : "○"}</span>
      {label}
    </label>
  );
}

function EmptyWorkspace({ onNew }: { readonly onNew: () => void }) {
  return (
    <section className="empty-workspace">
      <span className="empty-mark" aria-hidden="true">♪</span>
      <p className="eyebrow">Your piano, made visible</p>
      <h1>Begin a performance</h1>
      <p>
        Record your piano through the microphone or import a WAV or MP3.
        Atpiano keeps the immediate recognition visible while corrected notes
        settle behind it.
      </p>
      <button className="button primary" type="button" onClick={onNew}>
        Create a new session
      </button>
    </section>
  );
}

export interface AppViewer {
  readonly username: string;
  readonly displayName: string;
  readonly canWrite: boolean;
  readonly logoutPending: boolean;
  readonly onLogout: () => void;
}

export function App({
  viewer,
}: {
  readonly viewer?: AppViewer;
} = {}) {
  const runtime = useRuntime();
  const queryClient = useQueryClient();
  const selectedSessionId = useWorkspaceStore((state) => state.selectedSessionId);
  const libraryIntent = useWorkspaceStore((state) => state.libraryIntent);
  const newIntent = useWorkspaceStore((state) => state.newIntent);
  const selectSession = useWorkspaceStore((state) => state.selectSession);
  const showLibrary = useWorkspaceStore((state) => state.showLibrary);
  const beginNew = useWorkspaceStore((state) => state.beginNew);
  const captureState = useWorkspaceStore((state) => state.captureState);
  const beginCapture = useWorkspaceStore((state) => state.beginCapture);
  const warmCapture = useWorkspaceStore((state) => state.warmCapture);
  const recordCapture = useWorkspaceStore((state) => state.recordCapture);
  const stopCapture = useWorkspaceStore((state) => state.stopCapture);
  const completeCapture = useWorkspaceStore((state) => state.completeCapture);
  const failCapture = useWorkspaceStore((state) => state.failCapture);
  const resetCapture = useWorkspaceStore((state) => state.resetCapture);
  const showRoll = useWorkspaceStore((state) => state.showRoll);
  const showKeyboard = useWorkspaceStore((state) => state.showKeyboard);
  const showScore = useWorkspaceStore((state) => state.showScore);
  const toggleView = useWorkspaceStore((state) => state.toggleView);
  const [eventPage, setEventPage] = useState<EventPage | null>(null);
  const [scoreJob, setScoreJob] = useState<Job | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [eventError, setEventError] = useState<string | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);
  const [sessionActionError, setSessionActionError] =
    useState<string | null>(null);
  const [scoreActionError, setScoreActionError] = useState<string | null>(null);
  const [routeReady, setRouteReady] = useState(false);
  const [scoreReaderRoute, setScoreReaderRoute] =
    useState<ScoreReaderRoute | null>(() =>
      scoreReaderRouteFromUrl(window.location.href)
    );
  const [playbackSessionId, setPlaybackSessionId] = useState<string | null>(
    () => sessionIdFromUrl(window.location.href),
  );
  const [pendingAutoScoreSessionId, setPendingAutoScoreSessionId] =
    useState<string | null>(null);
  const [autoScoringSessionId, setAutoScoringSessionId] =
    useState<string | null>(null);
  const [sessionNavOpen, setSessionNavOpen] = useState(false);
  const sessionNavTrigger = useRef<HTMLButtonElement>(null);
  const canWrite = viewer?.canWrite ?? true;

  useEffect(() => {
    if (toast === null) return;
    const timer = window.setTimeout(() => setToast(null), 3_200);
    return () => window.clearTimeout(timer);
  }, [toast]);

  const closeSessionNav = useCallback(() => {
    setSessionNavOpen(false);
    window.requestAnimationFrame(() => sessionNavTrigger.current?.focus());
  }, []);

  const openSession = useCallback((sessionId: string) => {
    setPlaybackSessionId(sessionId);
    selectSession(sessionId);
  }, [selectSession]);

  const beginNewSession = useCallback(() => {
    setPlaybackSessionId(null);
    beginNew();
  }, [beginNew]);

  const selectFromSessionNav = useCallback((sessionId: string) => {
    openSession(sessionId);
    closeSessionNav();
  }, [closeSessionNav, openSession]);

  const showLibraryFromSessionNav = useCallback(() => {
    showLibrary();
    closeSessionNav();
  }, [closeSessionNav, showLibrary]);

  const beginNewFromSessionNav = useCallback(() => {
    beginNewSession();
    closeSessionNav();
  }, [beginNewSession, closeSessionNav]);

  useEffect(() => {
    if (!sessionNavOpen) return;

    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") closeSessionNav();
    };
    document.body.classList.add("session-nav-open");
    window.addEventListener("keydown", closeOnEscape);
    return () => {
      document.body.classList.remove("session-nav-open");
      window.removeEventListener("keydown", closeOnEscape);
    };
  }, [closeSessionNav, sessionNavOpen]);

  const capabilities = useQuery({
    queryKey: ["capabilities"],
    queryFn: ({ signal }) =>
      runtime.getCapabilities({
        requestId: requestId("capabilities"),
        signal,
      }),
    staleTime: Infinity,
  });
  const workspaces = useQuery({
    queryKey: ["workspaces"],
    queryFn: ({ signal }) =>
      runtime.listWorkspaces({
        requestId: requestId("workspaces"),
        signal,
      }),
    staleTime: 30_000,
  });
  const workspace = workspaces.data?.items[0];
  const sessions = useQuery({
    queryKey: ["sessions", workspace?.workspace_id],
    queryFn: ({ signal }) =>
      runtime.listSessions(workspace!.workspace_id, {
        requestId: requestId("sessions"),
        signal,
        limit: 100,
      }),
    enabled: workspace !== undefined,
    refetchInterval: (query) =>
      captureState.phase === "recording" ||
      query.state.data?.items.some(
        (session) =>
          session.status === "active" || session.status === "stopping",
      )
        ? 1_000
        : false,
  });
  const sessionItems = sessions.data?.items ?? [];
  const activeSession = sessionItems.find(
    (session) =>
      session.status === "active" ||
      session.status === "stopping" ||
      session.session_id === captureState.capture?.session_id,
  );
  const selectedSessionIsActive =
    activeSession?.session_id === selectedSessionId;

  useEffect(() => {
    const requestedSession = sessionIdFromUrl(window.location.href);
    if (requestedSession) openSession(requestedSession);
    else showLibrary();
    setRouteReady(true);
  }, [openSession, showLibrary]);

  useEffect(() => {
    const restoreRoute = () => {
      const requestedSession = sessionIdFromUrl(window.location.href);
      if (requestedSession) openSession(requestedSession);
      else showLibrary();
      setScoreReaderRoute(scoreReaderRouteFromUrl(window.location.href));
    };
    window.addEventListener("popstate", restoreRoute);
    return () => window.removeEventListener("popstate", restoreRoute);
  }, [openSession, showLibrary]);

  useEffect(() => {
    if (!routeReady) return;
    window.history.replaceState(
      null,
      "",
      urlForSession(
        window.location.href,
        libraryIntent || newIntent ? null : selectedSessionId,
      ),
    );
  }, [libraryIntent, newIntent, routeReady, selectedSessionId]);

  const selectedSession = useQuery({
    queryKey: ["session", workspace?.workspace_id, selectedSessionId],
    queryFn: ({ signal }) =>
      runtime.getSession(workspace!.workspace_id, selectedSessionId!, {
        requestId: requestId("session"),
        signal,
      }),
    enabled: workspace !== undefined && selectedSessionId !== null,
    refetchInterval: (query) =>
      captureState.phase === "recording" ||
      query.state.data?.status === "active" ||
      query.state.data?.status === "stopping"
        ? 750
        : false,
  });
  const playbackSession = sessionItems.find(
    (session) => session.session_id === playbackSessionId,
  ) ?? (
    selectedSession.data?.session_id === playbackSessionId
      ? selectedSession.data
      : undefined
  );
  const horizon = useQuery({
    queryKey: ["horizon", workspace?.workspace_id, selectedSessionId],
    queryFn: ({ signal }) =>
      runtime.getHorizon(workspace!.workspace_id, selectedSessionId!, {
        requestId: requestId("horizon"),
        signal,
      }),
    enabled: workspace !== undefined && selectedSessionId !== null,
    refetchInterval:
      captureState.phase === "recording" || selectedSessionIsActive
        ? 750
        : false,
  });
  const artifacts = useQuery({
    queryKey: ["artifacts", workspace?.workspace_id, selectedSessionId],
    queryFn: ({ signal }) =>
      runtime.listArtifacts(workspace!.workspace_id, selectedSessionId!, {
        requestId: requestId("artifacts"),
        signal,
        limit: 100,
      }),
    enabled: workspace !== undefined && selectedSessionId !== null,
  });
  const fallbackScoreArtifact = artifacts.data?.items.find(
    (artifact) => artifact.kind === "musicxml",
  );
  const fallbackScoreAlignmentArtifact = artifacts.data?.items.find(
    (artifact) => artifact.kind === "score-alignment",
  );
  const scoreVariants = useQuery({
    queryKey: ["score-variants", workspace?.workspace_id, selectedSessionId],
    queryFn: ({ signal }) =>
      runtime.listScoreVariants(
        workspace!.workspace_id,
        selectedSessionId!,
        {
          requestId: requestId("score-variants"),
          signal,
        },
      ),
    enabled:
      workspace !== undefined &&
      selectedSessionId !== null &&
      fallbackScoreArtifact !== undefined,
  });
  const selectedScoreVariant = scoreVariants.data?.items.find(
    (variant) => variant.selected,
  );
  const scoreArtifact = artifacts.data?.items.find(
    (artifact) =>
      artifact.artifact_id === selectedScoreVariant?.musicxml_artifact_id,
  ) ?? fallbackScoreArtifact;
  const scoreAlignmentArtifact = artifacts.data?.items.find(
    (artifact) =>
      artifact.artifact_id === selectedScoreVariant?.alignment_artifact_id,
  ) ?? fallbackScoreAlignmentArtifact;
  const playbackArtifacts = useQuery({
    queryKey: ["artifacts", workspace?.workspace_id, playbackSessionId],
    queryFn: ({ signal }) =>
      runtime.listArtifacts(workspace!.workspace_id, playbackSessionId!, {
        requestId: requestId("playback-artifacts"),
        signal,
        limit: 100,
      }),
    enabled:
      workspace !== undefined &&
      playbackSessionId !== null &&
      playbackSession?.status !== "active",
  });
  const audioArtifacts = useMemo(
    () => {
      const available = (playbackArtifacts.data?.items ?? []).filter(
        (artifact) => artifact.kind === "audio",
      );
      const compressed = available.filter(
        (artifact) => artifact.media_type === "audio/mpeg",
      );
      return (compressed.length ? compressed : available)
        .sort(
          (left, right) =>
            left.source_horizon_sample - right.source_horizon_sample ||
            left.filename.localeCompare(right.filename),
        );
    },
    [playbackArtifacts.data?.items],
  );
  const audioPlayback = useQuery({
    queryKey: [
      "audio-playback",
      playbackSessionId,
      ...audioArtifacts.map((artifact) => artifact.artifact_id),
    ],
    queryFn: async ({ signal }): Promise<AudioPlaybackSource[]> => {
      const startSamples = audioArtifacts.map(
        (_, index) =>
          index === 0 ? 0 : audioArtifacts[index - 1]!.source_horizon_sample,
      );
      return Promise.all(
        audioArtifacts.map(async (artifact, index) => {
          const content = await runtime.readArtifact(
            playbackSession!.workspace_id,
            playbackSession!.session_id,
            artifact.artifact_id,
            { requestId: requestId("audio-access"), signal },
          );
          const source = {
            artifactId: artifact.artifact_id,
            url: URL.createObjectURL(
              new Blob([content.bytes], {
                type: content.access.media_type,
              }),
            ),
            startSample: startSamples[index]!,
            endSample: artifact.source_horizon_sample,
          };
          return source;
        }),
      );
    },
    enabled:
      audioArtifacts.length > 0 &&
      playbackSession?.status !== "active",
    staleTime: Infinity,
    gcTime: 0,
  });
  useEffect(() => {
    const sources = audioPlayback.data;
    return () => {
      sources?.forEach((source) => {
        if (source.url.startsWith("blob:")) URL.revokeObjectURL(source.url);
      });
    };
  }, [audioPlayback.data]);
  const playbackOpening = useQuery({
    queryKey: [
      "session-opening-preview",
      playbackSession?.workspace_id,
      playbackSession?.session_id,
      playbackSession?.source_frame_count,
    ],
    queryFn: ({ signal }) =>
      openingEventPage(
        runtime,
        playbackSession!,
        Math.max(
          1,
          Math.min(
            playbackSession!.source_frame_count,
            capabilities.data?.max_event_range_samples ?? 5_760_000,
          ),
        ),
        signal,
      ),
    enabled:
      playbackSession !== undefined &&
      playbackSession.status !== "active" &&
      playbackSession.recognized_note_count > 0,
    staleTime: Infinity,
  });
  const playbackFirstNoteSample = firstVisibleNoteSample(
    playbackOpening.data?.items ?? [],
  );
  const playbackCueSample = playbackFirstNoteSample === null
    ? 0
    : Math.max(
        0,
        playbackFirstNoteSample -
          Math.round((playbackSession?.sample_rate_hz ?? 48_000) * 0.75),
      );
  const playbackCueReady =
    playbackSession?.recognized_note_count === 0 ||
    playbackOpening.isFetched;
  const playbackSourceFailure =
    playbackArtifacts.error ?? audioPlayback.error;
  const playbackSourceError = playbackSourceFailure instanceof Error
    ? playbackSourceFailure.message
    : playbackSourceFailure
      ? String(playbackSourceFailure)
      : playbackSession?.status !== "active" &&
          playbackArtifacts.isFetched &&
          audioArtifacts.length === 0
        ? "This session does not have a playable recording."
        : null;
  const scoreXml = useQuery({
    queryKey: ["artifact-content", scoreArtifact?.artifact_id],
    queryFn: ({ signal }) =>
      artifactText(
        runtime,
        scoreArtifact!.workspace_id,
        scoreArtifact!.session_id,
        scoreArtifact!.artifact_id,
        scoreArtifact!.sha256,
        signal,
      ),
    enabled: scoreArtifact !== undefined,
    staleTime: Infinity,
  });
  const scoreAlignment = useQuery({
    queryKey: [
      "score-alignment",
      scoreArtifact?.artifact_id,
      scoreAlignmentArtifact?.artifact_id,
    ],
    queryFn: async ({ signal }) => {
      const content = await runtime.readArtifact(
        scoreAlignmentArtifact!.workspace_id,
        scoreAlignmentArtifact!.session_id,
        scoreAlignmentArtifact!.artifact_id,
        { requestId: requestId("score-alignment"), signal },
      );
      return parseScoreAlignment(
        JSON.parse(new TextDecoder().decode(content.bytes)),
        {
        sessionId: scoreAlignmentArtifact!.session_id,
        musicXmlSha256: scoreArtifact!.sha256,
        },
      );
    },
    enabled:
      scoreArtifact !== undefined &&
      scoreAlignmentArtifact !== undefined,
    staleTime: Infinity,
  });
  const readerScoreXml = useQuery({
    queryKey: [
      "reader-score-content",
      workspace?.workspace_id,
      selectedSessionId,
      scoreReaderRoute?.artifactId,
      scoreReaderRoute?.sha256,
    ],
    queryFn: ({ signal }) =>
      artifactText(
        runtime,
        workspace!.workspace_id,
        selectedSessionId!,
        scoreReaderRoute!.artifactId,
        scoreReaderRoute!.sha256,
        signal,
      ),
    enabled:
      workspace !== undefined &&
      selectedSessionId !== null &&
      scoreReaderRoute !== null,
    staleTime: Infinity,
  });
  const readerScoreAlignment = useQuery({
    queryKey: [
      "reader-score-alignment",
      workspace?.workspace_id,
      selectedSessionId,
      scoreReaderRoute?.artifactId,
      scoreReaderRoute?.alignmentArtifactId,
    ],
    queryFn: async ({ signal }) => {
      const content = await runtime.readArtifact(
        workspace!.workspace_id,
        selectedSessionId!,
        scoreReaderRoute!.alignmentArtifactId!,
        { requestId: requestId("reader-score-alignment"), signal },
      );
      return parseScoreAlignment(
        JSON.parse(new TextDecoder().decode(content.bytes)),
        {
        sessionId: selectedSessionId!,
        musicXmlSha256: scoreReaderRoute!.sha256,
        },
      );
    },
    enabled:
      workspace !== undefined &&
      selectedSessionId !== null &&
      scoreReaderRoute?.alignmentArtifactId !== null &&
      scoreReaderRoute?.alignmentArtifactId !== undefined,
    staleTime: Infinity,
  });
  const scoreJobQuery = useQuery({
    queryKey: ["job", scoreJob?.job_id],
    queryFn: ({ signal }) =>
      runtime.getJob(scoreJob!.job_id, {
        requestId: requestId("score-job"),
        signal,
      }),
    enabled:
      scoreJob !== null &&
      scoreJob.job_id !== "pending" &&
      (scoreJob.status === "pending" || scoreJob.status === "running"),
    refetchInterval: 750,
  });

  useEffect(() => {
    const result = scoreJobQuery.data;
    if (!result || result.session_id !== selectedSessionId) return;
    setScoreJob(result);
    if (result.status === "complete") {
      void queryClient.invalidateQueries({ queryKey: ["artifacts"] });
      setScoreActionError(null);
      if (result.session_id === autoScoringSessionId) {
        setAutoScoringSessionId(null);
      }
    }
    if (result.status === "failed") {
      setScoreActionError(
        result.error?.message ?? "Score generation failed.",
      );
      if (result.session_id === autoScoringSessionId) {
        setAutoScoringSessionId(null);
      }
    }
  }, [
    queryClient,
    autoScoringSessionId,
    scoreJobQuery.data,
    scoreJobQuery.dataUpdatedAt,
    selectedSessionId,
  ]);

  useEffect(() => {
    if (
      !scoreJobQuery.error ||
      scoreJob === null ||
      (scoreJob.status !== "pending" && scoreJob.status !== "running")
    ) {
      return;
    }
    const message = scoreJobQuery.error instanceof Error
      ? scoreJobQuery.error.message
      : String(scoreJobQuery.error);
    setScoreJob({
      ...scoreJob,
      status: "failed",
      completed_at: new Date().toISOString(),
      error: {
        schema_version: "atpiano.contract.v1",
        error_id: `error:${scoreJob.job_id}:poll`,
        code: "internal",
        message,
        retryable: true,
        workspace_id: scoreJob.workspace_id,
        session_id: scoreJob.session_id,
        capture_id: null,
        job_id: scoreJob.job_id,
      },
    });
    setAutoScoringSessionId((sessionId) =>
      sessionId === scoreJob.session_id ? null : sessionId,
    );
    setScoreActionError(message);
  }, [scoreJob, scoreJobQuery.error]);

  useEffect(() => {
    setEventPage(null);
    setEventError(null);
    setExportError(null);
    setSessionActionError(null);
    setScoreActionError(null);
  }, [selectedSessionId]);

  useEffect(() => {
    if (!workspace || !selectedSession.data) return;
    const target = selectedSession.data;
    const maxRange =
      capabilities.data?.max_event_range_samples ?? 5_760_000;
    const range = eventWindow(
      target.source_frame_count,
      horizon.data?.audio_head_sample,
      maxRange,
    );
    const subscription = runtime.subscribeEvents(
      workspace.workspace_id,
      target.session_id,
      {
        requestId: requestId("events"),
        startSample: range.startSample,
        endSample: range.endSample,
        limit: 4_096,
      },
      {
        next(page) {
          if (page.session_id === target.session_id) {
            setEventPage(page);
            setEventError(null);
          }
        },
        error(error) {
          setEventError(
            error instanceof Error ? error.message : String(error),
          );
        },
      },
    );
    return () => subscription.close();
  }, [
    runtime,
    capabilities.data?.max_event_range_samples,
    horizon.data?.audio_head_sample,
    selectedSession.data,
    selectedSession.data?.source_frame_count,
    workspace,
  ]);

  const invalidateWorkspace = useCallback(async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["sessions"] }),
      queryClient.invalidateQueries({ queryKey: ["session"] }),
      queryClient.invalidateQueries({ queryKey: ["horizon"] }),
      queryClient.invalidateQueries({ queryKey: ["artifacts"] }),
    ]);
  }, [queryClient]);

  const microphone = useMicrophone({
    runtime,
    workspaceId: workspace?.workspace_id,
    onChanged: invalidateWorkspace,
    onStopped: (session) => setPendingAutoScoreSessionId(session.session_id),
  });

  useEffect(() => {
    const sessionId = captureState.capture?.session_id;
    if (sessionId) setPlaybackSessionId(sessionId);
  }, [captureState.capture?.session_id]);

  const importRecording = useCallback(async (file: File) => {
    if (!workspace) return;
    const operationId = requestId("recording-import");
    beginCapture(operationId);
    try {
      const suffix = file.name.toLowerCase().match(/\.(wav|mp3)$/)?.[1];
      if (!suffix) {
        throw new Error("Choose a WAV or MP3 recording.");
      }
      if (file.size === 0) {
        throw new Error("The selected recording is empty.");
      }
      if (file.size > 2_147_483_648) {
        throw new Error("The selected recording is larger than 2 GiB.");
      }
      const capture = await runtime.importRecording(
        {
          schema_version: "atpiano.contract.v1",
          workspace_id: workspace.workspace_id,
          filename: file.name,
          media_type: suffix === "wav" ? "audio/wav" : "audio/mpeg",
          byte_count: file.size,
          request_id: operationId,
        },
        file,
        { requestId: operationId },
      );
      recordCapture(operationId, capture);
      setPlaybackSessionId(capture.session_id);
      await invalidateWorkspace();
    } catch (error) {
      failCapture(operationId, error);
    }
  }, [
    beginCapture,
    failCapture,
    invalidateWorkspace,
    recordCapture,
    runtime,
    workspace,
  ]);

  const replay = useCallback(async () => {
    if (!workspace) return;
    const operationId = requestId("replay");
    beginCapture(operationId);
    warmCapture(operationId);
    try {
      const capture = await runtime.startReplay(
        {
          schema_version: "atpiano.contract.v1",
          workspace_id: workspace.workspace_id,
          fixture_id: "deterministic-musical-loop-v1",
          repeat: 1,
          silence_samples: 0,
          realtime: capabilities.data?.runtime_mode !== "fixture",
          request_id: operationId,
        },
        { requestId: operationId },
      );
      recordCapture(operationId, capture);
      openSession(capture.session_id);
      await invalidateWorkspace();
    } catch (error) {
      failCapture(operationId, error);
    }
  }, [
    beginCapture,
    capabilities.data?.runtime_mode,
    failCapture,
    invalidateWorkspace,
    recordCapture,
    runtime,
    openSession,
    warmCapture,
    workspace,
  ]);

  useEffect(() => {
    const capture = captureState.capture;
    const session = selectedSession.data;
    if (
      capture?.source !== "upload" ||
      session?.session_id !== capture.session_id ||
      captureState.operationId === null
    ) {
      return;
    }
    if (
      session.status === "stopping" &&
      captureState.phase !== "stopping"
    ) {
      stopCapture(captureState.operationId);
    } else if (session.status === "complete") {
      setPendingAutoScoreSessionId(session.session_id);
      completeCapture(captureState.operationId);
    } else if (session.status === "failed") {
      setSessionActionError(
        "The recording was uploaded, but processing did not complete. "
        + "The failed session was preserved.",
      );
      completeCapture(captureState.operationId);
    }
  }, [
    captureState.capture,
    captureState.operationId,
    captureState.phase,
    completeCapture,
    selectedSession.data,
    stopCapture,
  ]);

  const deleteSession = useMutation({
    mutationFn: async (target: Session) => {
      if (!window.confirm(`Move “${target.display_name ?? target.session_id}” to recoverable trash?`)) {
        throw new DOMException("Delete cancelled", "AbortError");
      }
      return runtime.deleteSession(
        {
          schema_version: "atpiano.contract.v1",
          workspace_id: target.workspace_id,
          session_id: target.session_id,
          request_id: requestId("delete"),
          confirmation: "recoverable-delete",
        },
        { requestId: requestId("delete-session") },
      );
    },
    onSuccess: async (result, target) => {
      showLibrary();
      setPlaybackSessionId((current) =>
        current === target.session_id ? null : current
      );
      setSessionActionError(null);
      setToast("Session moved to recoverable trash.");
      await invalidateWorkspace();
    },
    onError: (error) => {
      if (error instanceof DOMException && error.name === "AbortError") return;
      setSessionActionError(
        error instanceof Error ? error.message : String(error),
      );
    },
  });

  const scoreVariantMutation = useMutation({
    mutationFn: async (variant: {
      readonly baselineMusicXmlArtifactId: string;
      readonly baselineAlignmentArtifactId: string;
      readonly clefPolicy: "preserve" | "automatic";
      readonly targetKeyFifths: number | null;
    }) => {
      const target = selectedSession.data;
      if (!target) throw new Error("No score session is selected.");
      return runtime.createScoreVariant(
        {
          schema_version: "atpiano.contract.v1",
          workspace_id: target.workspace_id,
          session_id: target.session_id,
          baseline_musicxml_artifact_id:
            variant.baselineMusicXmlArtifactId,
          baseline_alignment_artifact_id:
            variant.baselineAlignmentArtifactId,
          clef_policy: variant.clefPolicy,
          target_key_fifths: variant.targetKeyFifths,
          request_id: requestId("score-variant"),
        },
        { requestId: requestId("score-variant-create") },
      );
    },
    onSuccess: async () => {
      setScoreActionError(null);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["artifacts"] }),
        queryClient.invalidateQueries({ queryKey: ["score-variants"] }),
      ]);
    },
    onError: (error) => {
      setScoreActionError(
        error instanceof Error ? error.message : String(error),
      );
    },
  });

  const selectScoreVariant = useCallback(
    (variant: ScoreVariant) => {
      scoreVariantMutation.mutate({
        baselineMusicXmlArtifactId:
          variant.baseline_musicxml_artifact_id,
        baselineAlignmentArtifactId:
          variant.baseline_alignment_artifact_id,
        clefPolicy: variant.clef_policy,
        targetKeyFifths: variant.target_key_fifths,
      });
    },
    [scoreVariantMutation],
  );

  const createEnharmonicVariant = useCallback(() => {
    if (
      !selectedScoreVariant ||
      selectedScoreVariant.available_enharmonic_fifths === null
    ) {
      return;
    }
    scoreVariantMutation.mutate({
      baselineMusicXmlArtifactId:
        selectedScoreVariant.baseline_musicxml_artifact_id,
      baselineAlignmentArtifactId:
        selectedScoreVariant.baseline_alignment_artifact_id,
      clefPolicy: "automatic",
      targetKeyFifths:
        selectedScoreVariant.available_enharmonic_fifths,
    });
  }, [scoreVariantMutation, selectedScoreVariant]);

  const createAutomaticVariant = useCallback(() => {
    if (!selectedScoreVariant) return;
    scoreVariantMutation.mutate({
      baselineMusicXmlArtifactId:
        selectedScoreVariant.baseline_musicxml_artifact_id,
      baselineAlignmentArtifactId:
        selectedScoreVariant.baseline_alignment_artifact_id,
      clefPolicy: "automatic",
      targetKeyFifths: null,
    });
  }, [scoreVariantMutation, selectedScoreVariant]);

  const generateScore = useCallback(async () => {
    const target = selectedSession.data;
    if (!target || !horizon.data || !target.current_transcription_run_id) return;
    setScoreActionError(null);
    setScoreJob({
      schema_version: "atpiano.contract.v1",
      workspace_id: target.workspace_id,
      session_id: target.session_id,
      job_id: "pending",
      kind: "score",
      status: "pending",
      input_horizon_sample: horizon.data.commit_sample,
      created_at: new Date().toISOString(),
      started_at: null,
      completed_at: null,
      artifact_ids: [],
      error: null,
    });
    try {
      const job = await runtime.startScoreJob(
        {
          schema_version: "atpiano.contract.v1",
          workspace_id: target.workspace_id,
          session_id: target.session_id,
          transcription_run_id: target.current_transcription_run_id,
          commit_sample: horizon.data.commit_sample,
          request_id: requestId("score"),
        },
        { requestId: requestId("score-start") },
      );
      setScoreJob(job);
      await queryClient.invalidateQueries({ queryKey: ["artifacts"] });
    } catch (error) {
      setScoreJob(null);
      setAutoScoringSessionId((sessionId) =>
        sessionId === target.session_id ? null : sessionId,
      );
      setScoreActionError(
        error instanceof Error ? error.message : String(error),
      );
    }
  }, [horizon.data, queryClient, runtime, selectedSession.data]);

  useEffect(() => {
    const target = selectedSession.data;
    if (
      pendingAutoScoreSessionId === null ||
      target?.session_id !== pendingAutoScoreSessionId ||
      target.status !== "complete" ||
      !horizon.data
    ) {
      return;
    }
    setPendingAutoScoreSessionId(null);
    if (!capabilities.data?.score_available) {
      return;
    }
    setAutoScoringSessionId(target.session_id);
    void generateScore();
  }, [
    capabilities.data?.score_available,
    generateScore,
    horizon.data,
    pendingAutoScoreSessionId,
    selectedSession.data,
  ]);

  const exportArtifact = useCallback(async (artifact: Artifact) => {
    setExportError(null);
    try {
      const result = await runtime.exportArtifact(
        artifact.workspace_id,
        artifact.session_id,
        artifact.artifact_id,
        { requestId: requestId("artifact-access") },
      );
      if (result.outcome === "saved" && result.fileName) {
        setToast(`Saved ${result.fileName}.`);
      } else if (result.outcome === "download-started" && result.fileName) {
        setToast(`Downloading ${result.fileName}…`);
      }
    } catch (error) {
      setExportError(error instanceof Error ? error.message : String(error));
    }
  }, [runtime]);

  const exportPinnedScore = useCallback(async () => {
    if (!workspace || !selectedSessionId || !scoreReaderRoute) return;
    try {
      const result = await runtime.exportArtifact(
        workspace.workspace_id,
        selectedSessionId,
        scoreReaderRoute.artifactId,
        { requestId: requestId("reader-score-download") },
      );
      if (result.outcome === "saved" && result.fileName) {
        setToast(`Saved ${result.fileName}.`);
      } else if (result.outcome === "download-started" && result.fileName) {
        setToast(`Downloading ${result.fileName}…`);
      }
    } catch (error) {
      setToast(error instanceof Error ? error.message : String(error));
    }
  }, [runtime, scoreReaderRoute, selectedSessionId, workspace]);

  const saveSelectedTitle = useCallback(async (displayName: string) => {
    const target = selectedSession.data;
    if (!target) throw new Error("No session is selected.");
    const annotation = await runtime.updateSessionAnnotation(
      {
        schema_version: "atpiano.contract.v1",
        workspace_id: target.workspace_id,
        session_id: target.session_id,
        display_name: displayName,
        request_id: requestId("session-name"),
      },
      { requestId: requestId("session-name-save") },
    );
    queryClient.setQueryData<Session>(
      ["session", target.workspace_id, target.session_id],
      (current) =>
        current
          ? { ...current, display_name: annotation.display_name }
          : current,
    );
    queryClient.setQueryData<SessionPage>(
      ["sessions", target.workspace_id],
      (current) =>
        current
          ? {
              ...current,
              items: current.items.map((session) =>
                session.session_id === target.session_id
                  ? { ...session, display_name: annotation.display_name }
                  : session
              ),
            }
          : current,
    );
  }, [queryClient, runtime, selectedSession.data]);

  const currentScoreRoute = useMemo<ScoreReaderRoute | null>(
    () =>
      scoreArtifact
        ? {
            artifactId: scoreArtifact.artifact_id,
            sha256: scoreArtifact.sha256,
            sourceHorizonSample: scoreArtifact.source_horizon_sample,
            alignmentArtifactId:
              scoreAlignmentArtifact?.artifact_id ?? null,
          }
        : null,
    [scoreAlignmentArtifact?.artifact_id, scoreArtifact],
  );

  const openScoreReader = useCallback(() => {
    if (!currentScoreRoute) return;
    window.history.pushState(
      null,
      "",
      urlForScoreReader(window.location.href, currentScoreRoute),
    );
    setScoreReaderRoute(currentScoreRoute);
  }, [currentScoreRoute]);

  const useCurrentScore = useCallback(() => {
    if (!currentScoreRoute) return;
    window.history.replaceState(
      null,
      "",
      urlForScoreReader(window.location.href, currentScoreRoute),
    );
    setScoreReaderRoute(currentScoreRoute);
  }, [currentScoreRoute]);

  const closeScoreReader = useCallback(() => {
    window.history.replaceState(
      null,
      "",
      urlWithoutScoreReader(window.location.href),
    );
    setScoreReaderRoute(null);
  }, []);

  const selected = selectedSession.data;
  const selectedFrames = selected
    ? liveFrameCount(
        selected.source_frame_count,
        horizon.data?.audio_head_sample,
      )
    : 0;
  const displayedSession = selected && selectedFrames !== selected.source_frame_count
    ? { ...selected, source_frame_count: selectedFrames }
    : selected;
  const events = eventPage?.items ?? [];
  const selectedIsActive =
    selected !== undefined &&
    (
      selected.status === "active" ||
      selected.status === "stopping" ||
      selected.session_id === captureState.capture?.session_id
    );
  const settleAudioHead = horizon.data?.audio_head_sample ?? selectedFrames;
  const settleCommit = horizon.data?.commit_sample ?? 0;
  const settlePercent = settleAudioHead > 0
    ? Math.min(100, Math.round((settleCommit / settleAudioHead) * 100))
    : 0;
  const selectedScoreJob =
    scoreJob?.session_id === selected?.session_id ? scoreJob : null;
  const scoreStatus = selectedScoreJob?.status ?? (
    selected?.available_artifact_kinds.includes("musicxml") ? "complete" : null
  );

  if (scoreReaderRoute !== null) {
    if (!selected) {
      return (
        <PlaybackProvider
          sessionId={playbackSession?.session_id ?? null}
          sources={audioPlayback.data ?? []}
          totalSamples={playbackSession?.source_frame_count ?? 0}
          sampleRateHz={playbackSession?.sample_rate_hz ?? 48_000}
          cueSample={playbackCueSample}
          cueReady={playbackCueReady}
          sourceError={playbackSourceError}
          selectedSessionId={selectedSessionId}
          onSessionRequest={setPlaybackSessionId}
        >
          <div className="score-reader reader-boot" role="status">
            <strong>Opening pinned score…</strong>
            <span>
              Loading its session and exact MusicXML snapshot.
            </span>
            {(selectedSession.isError || workspaces.isError) && (
              <button type="button" onClick={closeScoreReader}>
                Return to workspace
              </button>
            )}
          </div>
        </PlaybackProvider>
      );
    }
    return (
      <PlaybackProvider
        sessionId={playbackSession?.session_id ?? null}
        sources={audioPlayback.data ?? []}
        totalSamples={playbackSession?.source_frame_count ?? 0}
        sampleRateHz={playbackSession?.sample_rate_hz ?? 48_000}
        cueSample={playbackCueSample}
        cueReady={playbackCueReady}
        sourceError={playbackSourceError}
        selectedSessionId={selectedSessionId}
        onSessionRequest={setPlaybackSessionId}
      >
        <ScoreReader
          route={scoreReaderRoute}
          session={selected}
          xml={readerScoreXml.data}
          xmlError={readerScoreXml.error}
          alignment={readerScoreAlignment.data}
          alignmentError={readerScoreAlignment.error}
          currentArtifactId={scoreArtifact?.artifact_id}
          onClose={closeScoreReader}
          onUseCurrent={useCurrentScore}
          onDownload={() => void exportPinnedScore()}
        />
      </PlaybackProvider>
    );
  }

  return (
    <PlaybackProvider
      sessionId={playbackSession?.session_id ?? null}
      sources={audioPlayback.data ?? []}
      totalSamples={playbackSession?.source_frame_count ?? 0}
      sampleRateHz={playbackSession?.sample_rate_hz ?? 48_000}
      cueSample={playbackCueSample}
      cueReady={playbackCueReady}
      sourceError={playbackSourceError}
      selectedSessionId={selectedSessionId}
      onSessionRequest={setPlaybackSessionId}
    >
      <div className="app-shell">
      <SessionRail
        sessions={sessionItems.slice(0, 6)}
        selectedSessionId={selectedSessionId}
        activeSessionId={activeSession?.session_id ?? null}
        libraryIntent={libraryIntent}
        newIntent={newIntent}
        canWrite={canWrite}
        mobileOpen={sessionNavOpen}
        onHome={showLibraryFromSessionNav}
        onNew={beginNewFromSessionNav}
        onSelect={selectFromSessionNav}
        onClose={closeSessionNav}
      />
      {sessionNavOpen && (
        <button
          className="session-rail-backdrop"
          type="button"
          aria-label="Close session history"
          onClick={closeSessionNav}
        />
      )}

      <main className="workspace" inert={sessionNavOpen ? true : undefined}>
        <header className="workspace-topbar">
          <div className="topbar-primary">
            <button
              className="mobile-session-trigger"
              ref={sessionNavTrigger}
              type="button"
              aria-controls="session-navigation"
              aria-expanded={sessionNavOpen}
              onClick={() => setSessionNavOpen(true)}
            >
              <span className="menu-icon" aria-hidden="true">
                <i />
                <i />
                <i />
              </span>
              Sessions
            </button>
          </div>
          <div className="topbar-actions">
            {viewer !== undefined && (
              <div className="viewer-control">
                <span title={viewer.username}>{viewer.displayName}</span>
                <button
                  type="button"
                  disabled={viewer.logoutPending}
                  onClick={viewer.onLogout}
                >
                  {viewer.logoutPending ? "Signing out…" : "Logout"}
                </button>
              </div>
            )}
          </div>
        </header>

        {(workspaces.isError || sessions.isError) && (
          <section className="fatal-state" role="alert">
            <p className="eyebrow">Runtime unavailable</p>
            <h1>The performance workspace could not connect.</h1>
            <p>{String(workspaces.error ?? sessions.error)}</p>
          </section>
        )}

        {libraryIntent && !sessions.isLoading && !sessions.isError && (
          <SessionsHome
            sessions={sessionItems}
            activeSessionId={activeSession?.session_id ?? null}
            canWrite={canWrite}
            maxEventRangeSamples={
              capabilities.data?.max_event_range_samples ?? 5_760_000
            }
            onNew={beginNewSession}
            onSelect={openSession}
          />
        )}

        {!libraryIntent && !newIntent && !selected && !sessions.isLoading && (
          <EmptyWorkspace onNew={beginNewSession} />
        )}

        {newIntent && canWrite && (
          <CaptureDeck
            capabilities={capabilities.data}
            captureState={captureState}
            activeSession={activeSession}
            onMicrophone={() => void microphone.start()}
            onImport={(file) => void importRecording(file)}
            onReplay={() => void replay()}
            onStop={() => void microphone.stop()}
            onDismissError={resetCapture}
          />
        )}

        {selected && !newIntent && (
          <>
            <section className="session-hero">
              <div className="session-title">
                <p className="eyebrow">
                  {selectedIsActive ? "Active performance" : "Saved performance"}
                  <span aria-hidden="true">·</span>
                  <i className={`state-${selected.status}`}>{selected.status}</i>
                </p>
                <SessionTitleEditor
                  session={selected}
                  canEdit={canWrite}
                  onSave={saveSelectedTitle}
                />
                <p>
                  {formatSessionDate(selected.started_at)}
                  <span>·</span>
                  {sessionSourceLabel(selected.source)}
                  <span>·</span>
                  {formatClock(selectedFrames, selected.sample_rate_hz)}
                </p>
              </div>
              <div className="session-actions">
                {selectedIsActive && captureState.capture?.source === "microphone" && (
                  <button
                    className="button stop"
                    type="button"
                    disabled={captureState.phase === "stopping"}
                    onClick={() => void microphone.stop()}
                  >
                    {captureState.phase === "stopping"
                      ? `Settling… ${settlePercent}%`
                      : "Stop & settle"}
                  </button>
                )}
                {!selectedIsActive && canWrite && (
                  <button
                    className="button danger-quiet"
                    type="button"
                    disabled={deleteSession.isPending}
                    onClick={() => deleteSession.mutate(selected)}
                  >
                    Delete session
                  </button>
                )}
                {canWrite && (
                  <button
                    className="button secondary"
                    type="button"
                    onClick={beginNewSession}
                  >
                    New session
                  </button>
                )}
              </div>
            </section>

            {sessionActionError && (
              <p className="surface-feedback error session-action-error" role="alert">
                {sessionActionError}
              </p>
            )}

            {activeSession && !selectedIsActive && (
              <button
                className="active-capture-banner"
                type="button"
                onClick={() => openSession(activeSession.session_id)}
              >
                <span><i aria-hidden="true" /> Recording continues in another session</span>
                <strong>Return to live performance →</strong>
              </button>
            )}

            {selectedIsActive && captureState.phase !== "idle" && (
              <div className={`live-status-strip ${captureState.phase}`} role="status">
                <i aria-hidden="true" />
                <strong>
                  {captureState.phase === "recording"
                    ? captureState.capture?.source === "upload"
                      ? "Processing imported recording"
                      : selected.correction_mode === "after-stop"
                        ? "Listening now; correction begins after Stop"
                        : selected.correction_mode === "unavailable"
                          ? "Listening with provisional recognition"
                          : "Listening with background correction"
                    : captureState.phase === "stopping"
                      ? captureState.capture?.source === "upload"
                        ? "Recording imported; correction is settling"
                        : "Closing microphone capture"
                      : captureState.phase === "failed"
                        ? "Capture needs attention"
                        : "Preparing the local engine"}
                </strong>
                <span>
                  {captureState.capture?.source === "replay"
                    ? "Deterministic test recording"
                    : captureState.capture?.source === "upload"
                      ? "Imported WAV/MP3"
                      : "Physical microphone"}
                </span>
                {captureState.phase === "stopping" && (
                  <div className="settle-progress">
                    <span>
                      Corrected {formatClock(settleCommit, selected.sample_rate_hz)}
                      {" "}of {formatClock(settleAudioHead, selected.sample_rate_hz)}
                    </span>
                    <progress
                      max={100}
                      value={settlePercent}
                      aria-label="Final correction progress"
                    />
                  </div>
                )}
              </div>
            )}

            {selected.status === "stopping" && captureState.phase === "idle" && (
              <div className="live-status-strip stopping" role="status">
                <i aria-hidden="true" />
                <strong>
                  {selected.source === "upload"
                    ? "Recording imported; correction is settling"
                    : "Capture complete; correction is settling"}
                </strong>
                <span>
                  Corrected {formatClock(settleCommit, selected.sample_rate_hz)}
                  {" "}of {formatClock(settleAudioHead, selected.sample_rate_hz)}
                </span>
                <div className="settle-progress">
                  <progress
                    max={100}
                    value={settlePercent}
                    aria-label="Background correction progress"
                  />
                </div>
              </div>
            )}

            <section className="session-summary" aria-label="Session summary">
              <span>
                <strong>{selected.recognized_note_count}</strong> notes
              </span>
              <i aria-hidden="true">·</i>
              <span>
                <strong>{selected.corrected_note_count}</strong> corrected
              </span>
              {selected.status === "stopping" && (
                <>
                  <i aria-hidden="true">·</i>
                  <span>
                    corrected through{" "}
                    <strong>
                      {formatClock(
                        horizon.data?.commit_sample ?? 0,
                        selected.sample_rate_hz,
                      )}
                    </strong>
                  </span>
                </>
              )}
            </section>

            <section className="performance-heading">
              <div>
                <p className="eyebrow">Performance</p>
                <h2>What the piano played</h2>
              </div>
              <div className="view-switches" role="group" aria-label="Visible performance views">
                <ViewSwitch checked={showRoll} label="Piano roll" onChange={() => toggleView("roll")} />
                <ViewSwitch checked={showKeyboard} label="Keyboard" onChange={() => toggleView("keyboard")} />
                <ViewSwitch checked={showScore} label="Score" onChange={() => toggleView("score")} />
              </div>
            </section>

            {(eventError || scoreActionError) && (
              <div className="performance-feedback">
                {eventError && (
                  <p className="surface-feedback error" role="alert">
                    The performance events could not refresh. {eventError}
                  </p>
                )}
                {scoreActionError && (
                  <p className="surface-feedback error" role="alert">
                    {scoreActionError}
                  </p>
                )}
              </div>
            )}

            <PerformanceViews
              session={displayedSession}
              events={events}
              horizon={horizon.data}
              showRoll={showRoll}
              showKeyboard={showKeyboard}
              showScore={showScore}
              scoreStatus={scoreStatus}
              scoreErrorMessage={selectedScoreJob?.error?.message ?? null}
              scoreAvailable={capabilities.data?.score_available ?? false}
              scoreXml={scoreXml.data}
              scoreXmlError={scoreXml.error}
              scoreAlignment={scoreAlignment.data}
              scoreAlignmentError={scoreAlignment.error}
              scoreFreshness={scoreVariants.data?.freshness ?? null}
              scoreProducer={scoreVariants.data?.producer ?? null}
              scoreHorizonSample={scoreArtifact?.source_horizon_sample}
              scoreVariants={scoreVariants.data?.items ?? []}
              selectedScoreVariant={selectedScoreVariant}
              scoreVariantBusy={scoreVariantMutation.isPending}
              audioUnavailableReason={
                selected.status === "active"
                  ? "Playback available after Stop"
                  : audioPlayback.isLoading
                    ? "Loading recorded audio"
                    : "Recorded audio unavailable"
              }
              onGenerateScore={() => void generateScore()}
              onOpenScoreReader={openScoreReader}
              onSelectScoreVariant={selectScoreVariant}
              onCreateAutomaticVariant={createAutomaticVariant}
              onCreateEnharmonicVariant={createEnharmonicVariant}
            />

            <ArtifactPanel
              artifacts={artifacts.data?.items ?? []}
              baselineScoreArtifactId={
                selectedScoreVariant?.baseline_musicxml_artifact_id
              }
              selectedScoreArtifactId={scoreArtifact?.artifact_id}
              error={
                exportError ??
                (artifacts.error instanceof Error
                  ? artifacts.error.message
                  : artifacts.error
                    ? String(artifacts.error)
                    : null)
              }
              onDownload={(artifact) => void exportArtifact(artifact)}
            />
          </>
        )}
        {toast && (
          <div className="toast" role="status" aria-live="polite">
            {toast}
          </div>
        )}
      </main>
      </div>
    </PlaybackProvider>
  );
}

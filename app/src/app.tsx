import {
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import { ArtifactPanel } from "./components/artifact-panel.js";
import type { AudioPlaybackSource } from "./components/audio-playback.js";
import { CaptureDeck } from "./components/capture-deck.js";
import { PerformanceViews } from "./components/performance-views.js";
import { ScoreReader } from "./components/score-reader.js";
import { SessionRail } from "./components/session-rail.js";
import { useMicrophone } from "./hooks/use-microphone.js";
import { artifactText } from "./lib/artifact-content.js";
import { eventWindow, liveFrameCount } from "./lib/event-window.js";
import { formatClock, formatSessionDate, requestId } from "./lib/format.js";
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
  Session,
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
        Record the room or replay the musical fixture. Atpiano keeps the
        immediate recognition visible while corrected notes settle behind it.
      </p>
      <button className="button primary" type="button" onClick={onNew}>
        Create a new session
      </button>
    </section>
  );
}

export function App() {
  const runtime = useRuntime();
  const queryClient = useQueryClient();
  const selectedSessionId = useWorkspaceStore((state) => state.selectedSessionId);
  const newIntent = useWorkspaceStore((state) => state.newIntent);
  const selectSession = useWorkspaceStore((state) => state.selectSession);
  const beginNew = useWorkspaceStore((state) => state.beginNew);
  const captureState = useWorkspaceStore((state) => state.captureState);
  const beginCapture = useWorkspaceStore((state) => state.beginCapture);
  const warmCapture = useWorkspaceStore((state) => state.warmCapture);
  const recordCapture = useWorkspaceStore((state) => state.recordCapture);
  const failCapture = useWorkspaceStore((state) => state.failCapture);
  const resetCapture = useWorkspaceStore((state) => state.resetCapture);
  const showRoll = useWorkspaceStore((state) => state.showRoll);
  const showKeyboard = useWorkspaceStore((state) => state.showKeyboard);
  const showScore = useWorkspaceStore((state) => state.showScore);
  const toggleView = useWorkspaceStore((state) => state.toggleView);
  const inspectionSample = useWorkspaceStore((state) => state.inspectionSample);
  const setInspectionSample = useWorkspaceStore(
    (state) => state.setInspectionSample,
  );
  const [eventPage, setEventPage] = useState<EventPage | null>(null);
  const [scoreJob, setScoreJob] = useState<Job | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [routeReady, setRouteReady] = useState(false);
  const [scoreReaderRoute, setScoreReaderRoute] =
    useState<ScoreReaderRoute | null>(() =>
      scoreReaderRouteFromUrl(window.location.href)
    );
  const [pendingAutoScoreSessionId, setPendingAutoScoreSessionId] =
    useState<string | null>(null);
  const [autoScoringSessionId, setAutoScoringSessionId] =
    useState<string | null>(null);

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
    refetchInterval: captureState.phase === "recording" ? 1_000 : false,
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
    if (requestedSession) selectSession(requestedSession);
    setRouteReady(true);
  }, [selectSession]);

  useEffect(() => {
    const restoreRoute = () => {
      const requestedSession = sessionIdFromUrl(window.location.href);
      if (requestedSession) selectSession(requestedSession);
      setScoreReaderRoute(scoreReaderRouteFromUrl(window.location.href));
    };
    window.addEventListener("popstate", restoreRoute);
    return () => window.removeEventListener("popstate", restoreRoute);
  }, [selectSession]);

  useEffect(() => {
    if (!routeReady) return;
    window.history.replaceState(
      null,
      "",
      urlForSession(
        window.location.href,
        newIntent ? null : selectedSessionId,
      ),
    );
  }, [newIntent, routeReady, selectedSessionId]);

  useEffect(() => {
    if (
      routeReady &&
      !newIntent &&
      selectedSessionId === null &&
      sessionItems[0] !== undefined
    ) {
      selectSession(activeSession?.session_id ?? sessionItems[0].session_id);
    }
  }, [
    activeSession?.session_id,
    newIntent,
    routeReady,
    selectSession,
    selectedSessionId,
    sessionItems,
  ]);

  const selectedSession = useQuery({
    queryKey: ["session", workspace?.workspace_id, selectedSessionId],
    queryFn: ({ signal }) =>
      runtime.getSession(workspace!.workspace_id, selectedSessionId!, {
        requestId: requestId("session"),
        signal,
      }),
    enabled: workspace !== undefined && selectedSessionId !== null,
    refetchInterval:
      captureState.phase === "recording" || selectedSessionIsActive
        ? 750
        : false,
  });
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
  const scoreArtifact = artifacts.data?.items.find(
    (artifact) => artifact.kind === "musicxml",
  );
  const scoreAlignmentArtifact = artifacts.data?.items.find(
    (artifact) => artifact.kind === "score-alignment",
  );
  const audioArtifacts = useMemo(
    () => {
      const available = (artifacts.data?.items ?? []).filter(
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
    [artifacts.data?.items],
  );
  const audioPlayback = useQuery({
    queryKey: [
      "audio-playback",
      selectedSessionId,
      ...audioArtifacts.map((artifact) => artifact.artifact_id),
    ],
    queryFn: async ({ signal }): Promise<AudioPlaybackSource[]> => {
      const startSamples = audioArtifacts.map(
        (_, index) =>
          index === 0 ? 0 : audioArtifacts[index - 1]!.source_horizon_sample,
      );
      return Promise.all(
        audioArtifacts.map(async (artifact, index) => {
          const access = await runtime.getArtifactAccess(
            artifact.workspace_id,
            artifact.session_id,
            artifact.artifact_id,
            { requestId: requestId("audio-access"), signal },
          );
          const source = {
            artifactId: artifact.artifact_id,
            url: new URL(access.url, window.location.origin).href,
            startSample: startSamples[index]!,
            endSample: artifact.source_horizon_sample,
          };
          return source;
        }),
      );
    },
    enabled:
      audioArtifacts.length > 0 &&
      selectedSession.data?.status !== "active",
    staleTime: Infinity,
  });
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
      const access = await runtime.getArtifactAccess(
        scoreAlignmentArtifact!.workspace_id,
        scoreAlignmentArtifact!.session_id,
        scoreAlignmentArtifact!.artifact_id,
        { requestId: requestId("score-alignment"), signal },
      );
      const response = await fetch(
        new URL(access.url, window.location.origin),
        { signal },
      );
      if (!response.ok) {
        throw new Error(
          `Score alignment download failed: HTTP ${response.status}`,
        );
      }
      return parseScoreAlignment(await response.json(), {
        sessionId: scoreAlignmentArtifact!.session_id,
        musicXmlSha256: scoreArtifact!.sha256,
      });
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
      const access = await runtime.getArtifactAccess(
        workspace!.workspace_id,
        selectedSessionId!,
        scoreReaderRoute!.alignmentArtifactId!,
        { requestId: requestId("reader-score-alignment"), signal },
      );
      const response = await fetch(
        new URL(access.url, window.location.origin),
        { signal },
      );
      if (!response.ok) {
        throw new Error(
          `Score alignment download failed: HTTP ${response.status}`,
        );
      }
      return parseScoreAlignment(await response.json(), {
        sessionId: selectedSessionId!,
        musicXmlSha256: scoreReaderRoute!.sha256,
      });
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
      if (result.session_id === autoScoringSessionId) {
        setNotice("Capture settled and the score snapshot is ready.");
        setAutoScoringSessionId(null);
      }
    }
    if (result.status === "failed") {
      setNotice(result.error?.message ?? "Score generation failed.");
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
    setNotice(message);
  }, [scoreJob, scoreJobQuery.error]);

  useEffect(() => setEventPage(null), [selectedSessionId]);

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
          if (page.session_id === target.session_id) setEventPage(page);
        },
        error(error) {
          setNotice(error instanceof Error ? error.message : String(error));
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
      selectSession(capture.session_id);
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
    selectSession,
    warmCapture,
    workspace,
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
    onSuccess: async (result) => {
      beginNew();
      setNotice(`Session ${result.session_id} moved to recoverable trash.`);
      await invalidateWorkspace();
    },
    onError: (error) => {
      if (error instanceof DOMException && error.name === "AbortError") return;
      setNotice(error instanceof Error ? error.message : String(error));
    },
  });

  const generateScore = useCallback(async () => {
    const target = selectedSession.data;
    if (!target || !horizon.data || !target.current_transcription_run_id) return;
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
      setNotice(error instanceof Error ? error.message : String(error));
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
      setNotice("Capture settled. Score generation is not installed.");
      return;
    }
    setAutoScoringSessionId(target.session_id);
    setNotice("Capture settled. Generating the score snapshot…");
    void generateScore();
  }, [
    capabilities.data?.score_available,
    generateScore,
    horizon.data,
    pendingAutoScoreSessionId,
    selectedSession.data,
  ]);

  const downloadArtifact = useCallback(async (artifact: Artifact) => {
    try {
      const access = await runtime.getArtifactAccess(
        artifact.workspace_id,
        artifact.session_id,
        artifact.artifact_id,
        { requestId: requestId("artifact-access") },
      );
      const link = document.createElement("a");
      link.href = access.url;
      link.download = access.download_name;
      link.click();
    } catch (error) {
      setNotice(error instanceof Error ? error.message : String(error));
    }
  }, [runtime]);

  const downloadPinnedScore = useCallback(async () => {
    if (!workspace || !selectedSessionId || !scoreReaderRoute) return;
    try {
      const access = await runtime.getArtifactAccess(
        workspace.workspace_id,
        selectedSessionId,
        scoreReaderRoute.artifactId,
        { requestId: requestId("reader-score-download") },
      );
      const link = document.createElement("a");
      link.href = new URL(access.url, window.location.origin).href;
      link.download = access.download_name;
      link.click();
    } catch (error) {
      setNotice(error instanceof Error ? error.message : String(error));
    }
  }, [runtime, scoreReaderRoute, selectedSessionId, workspace]);

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
  const noteCount = events.filter(
    (event) => event.kind === "note" && event.lifecycle !== "retracted",
  ).length;
  const committedCount = events.filter(
    (event) => event.kind === "note" && event.lifecycle === "committed",
  ).length;
  const selectedIsActive = selected?.session_id === activeSession?.session_id;
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
      );
    }
    return (
      <ScoreReader
        route={scoreReaderRoute}
        session={selected}
        xml={readerScoreXml.data}
        xmlError={readerScoreXml.error}
        alignment={readerScoreAlignment.data}
        alignmentError={readerScoreAlignment.error}
        inspectionSample={inspectionSample}
        currentArtifactId={scoreArtifact?.artifact_id}
        onClose={closeScoreReader}
        onUseCurrent={useCurrentScore}
        onDownload={() => void downloadPinnedScore()}
      />
    );
  }

  return (
    <div className="app-shell">
      <SessionRail
        workspace={workspace}
        sessions={sessionItems}
        selectedSessionId={selectedSessionId}
        activeSessionId={activeSession?.session_id ?? null}
        newIntent={newIntent}
        onNew={beginNew}
        onSelect={selectSession}
      />

      <main className="workspace">
        <header className="workspace-topbar">
          <div>
            <span className="runtime-badge">
              <i aria-hidden="true" />
              {capabilities.data?.runtime_mode === "fixture"
                ? "Deterministic fixture"
                : "Local engine"}
            </span>
          </div>
          <div className="topbar-actions">
            <span>Schema v1</span>
            <button
              className="help-button"
              type="button"
              title="Atpiano keeps provisional and corrected notes visibly distinct."
              aria-label="About this workspace"
            >
              ?
            </button>
          </div>
        </header>

        {notice && (
          <div className="notice" role="status">
            <span>{notice}</span>
            <button type="button" onClick={() => setNotice(null)}>Dismiss</button>
          </div>
        )}

        {(workspaces.isError || sessions.isError) && (
          <section className="fatal-state" role="alert">
            <p className="eyebrow">Runtime unavailable</p>
            <h1>The performance workspace could not connect.</h1>
            <p>{String(workspaces.error ?? sessions.error)}</p>
          </section>
        )}

        {!newIntent && !selected && !sessions.isLoading && (
          <EmptyWorkspace onNew={beginNew} />
        )}

        {newIntent && (
          <CaptureDeck
            capabilities={capabilities.data}
            captureState={captureState}
            activeSession={activeSession}
            onMicrophone={() => void microphone.start()}
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
                </p>
                <h1>{selected.display_name ?? "Untitled performance"}</h1>
                <p>
                  {formatSessionDate(selected.started_at)}
                  <span>·</span>
                  {selected.source === "microphone" ? "Microphone" : "Fixture replay"}
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
                {!selectedIsActive && (
                  <button
                    className="button danger-quiet"
                    type="button"
                    disabled={deleteSession.isPending}
                    onClick={() => deleteSession.mutate(selected)}
                  >
                    Delete session
                  </button>
                )}
                <button className="button secondary" type="button" onClick={beginNew}>
                  New session
                </button>
              </div>
            </section>

            {activeSession && !selectedIsActive && (
              <button
                className="active-capture-banner"
                type="button"
                onClick={() => selectSession(activeSession.session_id)}
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
                    ? selected.correction_mode === "after-stop"
                      ? "Listening now; correction begins after Stop"
                      : selected.correction_mode === "unavailable"
                        ? "Listening with provisional recognition"
                        : "Listening with background correction"
                    : captureState.phase === "stopping"
                      ? "Closing microphone capture"
                      : captureState.phase === "failed"
                        ? "Capture needs attention"
                        : "Preparing the local engine"}
                </strong>
                <span>
                  {captureState.capture?.source === "replay"
                    ? "Deterministic musical fixture"
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
                <strong>Capture complete; correction is settling</strong>
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

            <section className="metrics-row" aria-label="Session summary">
              <article>
                <span>Recognized notes</span>
                <strong>{noteCount}</strong>
                <small>{committedCount} corrected</small>
              </article>
              <article>
                <span>Corrected through</span>
                <strong>
                  {horizon.data
                    ? formatClock(horizon.data.commit_sample, selected.sample_rate_hz)
                    : "—"}
                </strong>
                <small>
                  {selected.correction_mode
                    ? `${selected.correction_mode} correction`
                    : "source sample horizon"}
                </small>
              </article>
              <article>
                <span>Session state</span>
                <strong className={`state-${selected.status}`}>{selected.status}</strong>
                <small>{selectedIsActive ? "writer attached" : "read-only history"}</small>
              </article>
              <article>
                <span>Artifacts</span>
                <strong>{artifacts.data?.items.length ?? 0}</strong>
                <small>checksummed exports</small>
              </article>
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

            <PerformanceViews
              session={displayedSession}
              events={events}
              horizon={horizon.data}
              inspectionSample={inspectionSample}
              showRoll={showRoll}
              showKeyboard={showKeyboard}
              showScore={showScore}
              scoreStatus={scoreStatus}
              scoreAvailable={capabilities.data?.score_available ?? false}
              scoreXml={scoreXml.data}
              scoreXmlError={scoreXml.error}
              scoreAlignment={scoreAlignment.data}
              scoreAlignmentError={scoreAlignment.error}
              scoreHorizonSample={scoreArtifact?.source_horizon_sample}
              audioSources={audioPlayback.data ?? []}
              audioUnavailableReason={
                selected.status === "active"
                  ? "Playback available after Stop"
                  : audioPlayback.isLoading
                    ? "Loading recorded audio"
                    : "Recorded audio unavailable"
              }
              onInspect={setInspectionSample}
              onGenerateScore={() => void generateScore()}
              onOpenScoreReader={openScoreReader}
            />

            <ArtifactPanel
              artifacts={artifacts.data?.items ?? []}
              onDownload={(artifact) => void downloadArtifact(artifact)}
            />
            <footer className="session-footer">
              <span>Session ID</span>
              <code>{selected.session_id}</code>
              <span>Source sample clock · {selected.sample_rate_hz.toLocaleString()} Hz</span>
            </footer>
          </>
        )}
      </main>
    </div>
  );
}

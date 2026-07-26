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
import { CaptureDeck } from "./components/capture-deck.js";
import { PerformanceViews } from "./components/performance-views.js";
import { SessionRail } from "./components/session-rail.js";
import { useMicrophone } from "./hooks/use-microphone.js";
import { formatClock, formatSessionDate, requestId } from "./lib/format.js";
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

  useEffect(() => {
    if (
      !newIntent &&
      selectedSessionId === null &&
      sessionItems[0] !== undefined
    ) {
      selectSession(activeSession?.session_id ?? sessionItems[0].session_id);
    }
  }, [
    activeSession?.session_id,
    newIntent,
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
  });
  const horizon = useQuery({
    queryKey: ["horizon", workspace?.workspace_id, selectedSessionId],
    queryFn: ({ signal }) =>
      runtime.getHorizon(workspace!.workspace_id, selectedSessionId!, {
        requestId: requestId("horizon"),
        signal,
      }),
    enabled: workspace !== undefined && selectedSessionId !== null,
    refetchInterval: captureState.phase === "recording" ? 750 : false,
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
  const scoreXml = useQuery({
    queryKey: ["artifact-content", scoreArtifact?.artifact_id],
    queryFn: async ({ signal }) => {
      const access = await runtime.getArtifactAccess(
        scoreArtifact!.workspace_id,
        scoreArtifact!.session_id,
        scoreArtifact!.artifact_id,
        { requestId: requestId("score-content"), signal },
      );
      const response = await fetch(
        new URL(access.url, window.location.origin),
        { signal },
      );
      if (!response.ok) {
        throw new Error(`MusicXML download failed: HTTP ${response.status}`);
      }
      return response.text();
    },
    enabled: scoreArtifact !== undefined,
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
    }
    if (result.status === "failed") {
      setNotice(result.error?.message ?? "Score generation failed.");
    }
  }, [
    queryClient,
    scoreJobQuery.data,
    scoreJobQuery.dataUpdatedAt,
    selectedSessionId,
  ]);

  useEffect(() => {
    setEventPage(null);
    if (!workspace || !selectedSession.data) return;
    const target = selectedSession.data;
    const endSample = Math.max(1, target.source_frame_count);
    const maxRange =
      capabilities.data?.max_event_range_samples ?? 5_760_000;
    const subscription = runtime.subscribeEvents(
      workspace.workspace_id,
      target.session_id,
      {
        requestId: requestId("events"),
        startSample: Math.max(0, endSample - maxRange),
        endSample,
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
      setNotice(error instanceof Error ? error.message : String(error));
    }
  }, [horizon.data, queryClient, runtime, selectedSession.data]);

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

  const selected = selectedSession.data;
  const events = eventPage?.items ?? [];
  const noteCount = events.filter(
    (event) => event.kind === "note" && event.lifecycle !== "retracted",
  ).length;
  const committedCount = events.filter(
    (event) => event.kind === "note" && event.lifecycle === "committed",
  ).length;
  const selectedIsActive = selected?.session_id === activeSession?.session_id;
  const scoreStatus = scoreJob?.status ?? (
    selected?.available_artifact_kinds.includes("musicxml") ? "complete" : null
  );

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
                  {formatClock(selected.source_frame_count, selected.sample_rate_hz)}
                </p>
              </div>
              <div className="session-actions">
                {selectedIsActive && captureState.capture?.source === "microphone" && (
                  <button className="button stop" type="button" onClick={() => void microphone.stop()}>
                    Stop &amp; settle
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
                    ? "Listening and correcting"
                    : captureState.phase === "stopping"
                      ? "Settling the final notes"
                      : captureState.phase === "failed"
                        ? "Capture needs attention"
                        : "Preparing the local engine"}
                </strong>
                <span>
                  {captureState.capture?.source === "replay"
                    ? "Deterministic musical fixture"
                    : "Physical microphone"}
                </span>
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
                <small>source sample horizon</small>
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
              session={selected}
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
              onInspect={setInspectionSample}
              onGenerateScore={() => void generateScore()}
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

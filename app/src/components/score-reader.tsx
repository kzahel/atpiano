import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { MusicXmlScore, type ScoreRenderPages } from "./musicxml-score.js";
import { formatClock } from "../lib/format.js";
import {
  scoreAttackAtSample,
  sourceSampleAtScoreQuarter,
  type ScoreAlignment,
} from "../lib/score-alignment.js";
import {
  pageForMeasure,
  pageForScoreQuarter,
  scoreReaderLayout,
  spreadStart,
  type ScoreDensity,
} from "../lib/score-reader-layout.js";
import type { ScoreReaderRoute } from "../lib/session-url.js";
import type { Session } from "../runtime/atpiano-runtime.js";

const densityStorageKey = "atpiano.score-reader-density";

function initialDensity(): ScoreDensity {
  try {
    const value = window.localStorage.getItem(densityStorageKey);
    if (value === "large" || value === "comfortable" || value === "compact") {
      return value;
    }
  } catch {
    // Storage is optional in private or embedded browser contexts.
  }
  return "comfortable";
}

function interactiveTarget(target: EventTarget | null): boolean {
  return target instanceof Element &&
    target.closest("button, input, select, textarea, a, [role='button']") !== null;
}

export function ScoreReader({
  route,
  session,
  xml,
  xmlError,
  alignment,
  alignmentError,
  inspectionSample,
  currentArtifactId,
  onClose,
  onUseCurrent,
  onDownload,
}: {
  readonly route: ScoreReaderRoute;
  readonly session: Session;
  readonly xml: string | undefined;
  readonly xmlError: Error | null;
  readonly alignment: ScoreAlignment | undefined;
  readonly alignmentError: Error | null;
  readonly inspectionSample: number | null;
  readonly currentArtifactId: string | undefined;
  readonly onClose: () => void;
  readonly onUseCurrent: () => void;
  readonly onDownload: () => void;
}) {
  const shell = useRef<HTMLDivElement>(null);
  const stage = useRef<HTMLDivElement>(null);
  const swipeStart = useRef<number | null>(null);
  const swipeMoved = useRef(false);
  const anchorMeasure = useRef(0);
  const anchorSample = useRef<number | null>(inspectionSample);
  const controlsTimer = useRef<number | null>(null);
  const [density, setDensity] = useState<ScoreDensity>(initialDensity);
  const [stageSize, setStageSize] = useState(() => ({
    width: window.innerWidth,
    height: Math.max(320, window.innerHeight - 64),
  }));
  const [renderPages, setRenderPages] = useState<ScoreRenderPages>({
    pageCount: 1,
    pages: [{
      pageIndex: 0,
      firstMeasureOrdinal: 0,
      firstScoreQuarter: 0,
    }],
  });
  const [pageStart, setPageStart] = useState(0);
  const [fullscreen, setFullscreen] = useState(false);
  const [fullscreenError, setFullscreenError] = useState<string | null>(null);
  const [controlsVisible, setControlsVisible] = useState(true);
  const layout = useMemo(
    () => scoreReaderLayout(stageSize.width, stageSize.height, density),
    [density, stageSize.height, stageSize.width],
  );

  useEffect(() => {
    try {
      window.localStorage.setItem(densityStorageKey, density);
    } catch {
      // The selected density remains valid for this mounted reader.
    }
  }, [density]);

  useEffect(() => {
    const element = stage.current;
    if (!element) return;
    const measure = () => {
      const bounds = element.getBoundingClientRect();
      setStageSize({
        width: bounds.width || window.innerWidth,
        height: bounds.height || Math.max(320, window.innerHeight - 64),
      });
    };
    measure();
    if (typeof ResizeObserver === "undefined") {
      window.addEventListener("resize", measure);
      return () => window.removeEventListener("resize", measure);
    }
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  const revealControls = useCallback(() => {
    setControlsVisible(true);
    if (controlsTimer.current !== null) {
      window.clearTimeout(controlsTimer.current);
    }
    controlsTimer.current = window.setTimeout(() => {
      const active = document.activeElement;
      if (!active || !shell.current?.querySelector(".reader-toolbar")?.contains(active)) {
        setControlsVisible(false);
      }
    }, 4_000);
  }, []);

  useEffect(() => {
    revealControls();
    return () => {
      if (controlsTimer.current !== null) {
        window.clearTimeout(controlsTimer.current);
      }
    };
  }, [revealControls]);

  useEffect(() => {
    const update = () => setFullscreen(document.fullscreenElement !== null);
    document.addEventListener("fullscreenchange", update);
    return () => document.removeEventListener("fullscreenchange", update);
  }, []);

  const handlePages = useCallback((next: ScoreRenderPages) => {
    let targetPage = pageForMeasure(next.pages, anchorMeasure.current);
    if (anchorSample.current !== null) {
      const targetQuarter = scoreAttackAtSample(
        alignment,
        anchorSample.current,
        route.sourceHorizonSample,
      );
      if (targetQuarter !== null) {
        targetPage = pageForScoreQuarter(next.pages, targetQuarter);
      }
    }
    setRenderPages(next);
    setPageStart(spreadStart(targetPage, next.pageCount, layout.pageSpan));
  }, [
    alignment,
    layout.pageSpan,
    route.sourceHorizonSample,
  ]);

  useEffect(() => {
    const page = renderPages.pages.find(
      (candidate) => candidate.pageIndex === pageStart,
    );
    if (!page) return;
    anchorMeasure.current = page.firstMeasureOrdinal;
    anchorSample.current = sourceSampleAtScoreQuarter(
      alignment,
      page.firstScoreQuarter,
    );
  }, [alignment, pageStart, renderPages.pages]);

  const turn = useCallback((direction: -1 | 1) => {
    setPageStart((current) =>
      spreadStart(
        current + direction * layout.pageSpan,
        renderPages.pageCount,
        layout.pageSpan,
      )
    );
    revealControls();
  }, [
    layout.pageSpan,
    renderPages.pageCount,
    revealControls,
  ]);

  useEffect(() => {
    const keydown = (event: KeyboardEvent) => {
      if (interactiveTarget(event.target)) return;
      if (event.key === "ArrowLeft" || event.key === "PageUp") {
        event.preventDefault();
        turn(-1);
      } else if (event.key === "ArrowRight" || event.key === "PageDown") {
        event.preventDefault();
        turn(1);
      }
    };
    window.addEventListener("keydown", keydown);
    return () => window.removeEventListener("keydown", keydown);
  }, [turn]);

  const toggleFullscreen = async () => {
    setFullscreenError(null);
    try {
      if (document.fullscreenElement) {
        await document.exitFullscreen();
      } else if (shell.current?.requestFullscreen) {
        await shell.current.requestFullscreen();
      } else {
        setFullscreenError("Browser fullscreen is unavailable.");
      }
    } catch {
      setFullscreenError("Browser fullscreen was not permitted.");
    }
  };

  const firstVisiblePage = pageStart + 1;
  const lastVisiblePage = Math.min(
    renderPages.pageCount,
    pageStart + layout.pageSpan,
  );
  const pageLabel = firstVisiblePage === lastVisiblePage
    ? `Page ${firstVisiblePage} of ${renderPages.pageCount}`
    : `Pages ${firstVisiblePage}–${lastVisiblePage} of ${renderPages.pageCount}`;
  const hasNewerScore = currentArtifactId !== undefined &&
    currentArtifactId !== route.artifactId;

  return (
    <div
      ref={shell}
      className={`score-reader ${controlsVisible ? "" : "controls-hidden"}`}
      onPointerMove={revealControls}
      onPointerDown={() => revealControls()}
      onFocusCapture={revealControls}
    >
      <header className="reader-toolbar">
        <button className="reader-workspace" type="button" onClick={onClose}>
          <span aria-hidden="true">←</span> Workspace
        </button>
        <div className="reader-identity">
          <strong>{session.display_name ?? "Untitled performance"}</strong>
          <small>
            Through {formatClock(
              route.sourceHorizonSample,
              session.sample_rate_hz,
            )} · {route.sha256.slice(0, 8)}
          </small>
        </div>
        <output aria-live="polite">{pageLabel}</output>
        <label className="reader-density">
          <span>Density</span>
          <select
            value={density}
            onChange={(event) =>
              setDensity(event.currentTarget.value as ScoreDensity)
            }
          >
            <option value="large">Large</option>
            <option value="comfortable">Comfortable</option>
            <option value="compact">Compact</option>
          </select>
        </label>
        <button type="button" onClick={onDownload}>Download</button>
        <button
          type="button"
          onClick={() => void toggleFullscreen()}
          aria-label={fullscreen ? "Exit fullscreen" : "Enter fullscreen"}
        >
          <span aria-hidden="true">{fullscreen ? "⊙" : "⛶"}</span>
        </button>
      </header>

      {hasNewerScore && (
        <button
          className="reader-update"
          type="button"
          onClick={onUseCurrent}
        >
          A newer committed score is available · Use newer score
        </button>
      )}
      {(alignmentError || fullscreenError) && (
        <p className="reader-advisory" role="status">
          {fullscreenError ??
            "The score is readable, but its playback cursor is unavailable."}
        </p>
      )}

      <main
        ref={stage}
        className="reader-stage"
        aria-label="Score page reader"
        onPointerDown={(event) => {
          swipeStart.current = event.clientX;
          swipeMoved.current = false;
        }}
        onPointerMove={(event) => {
          if (
            swipeStart.current !== null &&
            Math.abs(event.clientX - swipeStart.current) > 12
          ) {
            swipeMoved.current = true;
          }
        }}
        onPointerUp={(event) => {
          if (swipeStart.current === null) return;
          const distance = event.clientX - swipeStart.current;
          swipeStart.current = null;
          if (Math.abs(distance) >= 54) turn(distance > 0 ? -1 : 1);
        }}
      >
        {xml ? (
          <MusicXmlScore
            xml={xml}
            alignment={alignment}
            inspectionSample={inspectionSample}
            scoreHorizonSample={route.sourceHorizonSample}
            readerLayout={layout}
            pageStart={pageStart}
            pageSpan={layout.pageSpan}
            onPages={handlePages}
          />
        ) : (
          <div className="reader-loading" role={xmlError ? "alert" : "status"}>
            <strong>
              {xmlError ? "The pinned score could not load." : "Loading pinned score…"}
            </strong>
            <span>
              {xmlError
                ? "Return to the workspace or download the MusicXML artifact."
                : "The exact MusicXML snapshot is being prepared for this screen."}
            </span>
          </div>
        )}
        <button
          className="reader-turn-zone previous"
          type="button"
          aria-label="Previous score page"
          disabled={pageStart === 0}
          onClick={() => {
            if (!swipeMoved.current) turn(-1);
            swipeMoved.current = false;
          }}
        >
          <span aria-hidden="true">‹</span>
        </button>
        <button
          className="reader-turn-zone next"
          type="button"
          aria-label="Next score page"
          disabled={pageStart + layout.pageSpan >= renderPages.pageCount}
          onClick={() => {
            if (!swipeMoved.current) turn(1);
            swipeMoved.current = false;
          }}
        >
          <span aria-hidden="true">›</span>
        </button>
      </main>
    </div>
  );
}

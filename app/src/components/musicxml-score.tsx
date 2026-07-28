import { useEffect, useRef, useState } from "react";
import type {
  OpenSheetMusicDisplay as OsmdRenderer,
} from "opensheetmusicdisplay";

import { reportClientAssetLoadError } from "../client-update.js";
import {
  moveScoreCursor,
  scoreAttackAtSample,
  type ScoreAlignment,
  type ScoreCursorLike,
} from "../lib/score-alignment.js";
import type {
  ScorePageAnchor,
  ScoreReaderLayout,
} from "../lib/score-reader-layout.js";
import { usePlaybackStore } from "../state/playback-store.js";

export interface ScoreRenderPages {
  readonly pageCount: number;
  readonly pages: readonly ScorePageAnchor[];
}

interface SourceMeasureLike {
  readonly measureListIndex?: number;
}

interface GraphicalMeasureLike {
  readonly parentSourceMeasure?: SourceMeasureLike;
}

interface MusicSystemLike {
  readonly GraphicalMeasures?: readonly (
    readonly (GraphicalMeasureLike | undefined)[]
  )[];
  GetSystemsFirstTimeStamp?(): { readonly RealValue?: number };
}

interface MusicPageLike {
  readonly MusicSystems?: readonly MusicSystemLike[];
}

interface GraphicLike {
  readonly MusicPages?: readonly MusicPageLike[];
}

interface ReaderEngravingRules {
  NewPageAtXMLNewPageAttribute: boolean;
  NewSystemAtXMLNewPageAttribute: boolean;
  NewSystemAtXMLNewSystemAttribute: boolean;
  MinimumDistanceBetweenSystems: number;
  MinSkyBottomDistBetweenSystems: number;
  PageTopMargin: number;
  PageTopMarginNarrow: number;
  PageBottomMargin: number;
}

interface PlaybackGraphicalNoteLike {
  getNoteheadSVGs?(): HTMLElement[];
}

interface PlaybackCursorLike extends ScoreCursorLike {
  readonly cursorElement?: HTMLElement;
  GNotesUnderCursor?(): readonly PlaybackGraphicalNoteLike[];
}

interface ScorePanelGeometry {
  readonly viewportTop: number;
  readonly viewportHeight: number;
  readonly scrollTop: number;
  readonly scrollHeight: number;
  readonly cursorTop: number;
  readonly cursorHeight: number;
}

export function scorePanelFollowTop(
  geometry: ScorePanelGeometry,
): number | null {
  const cursorCenter =
    geometry.cursorTop + geometry.cursorHeight / 2;
  const safeTop = geometry.viewportTop + geometry.viewportHeight * 0.22;
  const safeBottom =
    geometry.viewportTop + geometry.viewportHeight * 0.78;
  if (cursorCenter >= safeTop && cursorCenter <= safeBottom) return null;
  const relativeCenter = cursorCenter - geometry.viewportTop;
  const maximum = Math.max(
    0,
    geometry.scrollHeight - geometry.viewportHeight,
  );
  return Math.max(
    0,
    Math.min(
      maximum,
      geometry.scrollTop + relativeCenter - geometry.viewportHeight / 2,
    ),
  );
}

function pageElements(container: HTMLElement): HTMLElement[] {
  return Array.from(container.children).filter(
    (child): child is HTMLElement =>
      child instanceof HTMLElement &&
      child.id.startsWith("osmdCanvasPage"),
  );
}

function pageAnchors(renderer: OsmdRenderer): ScorePageAnchor[] {
  const graphic = (
    renderer as unknown as { GraphicSheet?: GraphicLike }
  ).GraphicSheet;
  return (graphic?.MusicPages ?? []).map((page, pageIndex) => {
    const systems = page.MusicSystems ?? [];
    let firstMeasureOrdinal = pageIndex;
    for (const system of systems) {
      const measures = system.GraphicalMeasures ?? [];
      const first = measures
        .flatMap((staffMeasures) => staffMeasures)
        .find((measure) =>
          Number.isSafeInteger(
            measure?.parentSourceMeasure?.measureListIndex,
          )
        );
      if (first?.parentSourceMeasure?.measureListIndex !== undefined) {
        firstMeasureOrdinal =
          first.parentSourceMeasure.measureListIndex;
        break;
      }
    }
    const timestamp = systems[0]?.GetSystemsFirstTimeStamp?.().RealValue;
    return {
      pageIndex,
      firstMeasureOrdinal,
      firstScoreQuarter:
        typeof timestamp === "number" && Number.isFinite(timestamp)
          ? timestamp * 4
          : null,
    };
  });
}

export function MusicXmlScore({
  xml,
  alignment,
  inspectionSample,
  scoreHorizonSample,
  readerLayout = null,
  pageStart = 0,
  pageSpan = 1,
  onPages,
}: {
  readonly xml: string;
  readonly alignment: ScoreAlignment | undefined;
  readonly inspectionSample: number | null;
  readonly scoreHorizonSample: number | undefined;
  readonly readerLayout?: ScoreReaderLayout | null;
  readonly pageStart?: number;
  readonly pageSpan?: 1 | 2;
  readonly onPages?: (pages: ScoreRenderPages) => void;
}) {
  const paper = useRef<HTMLDivElement>(null);
  const target = useRef<HTMLDivElement>(null);
  const renderer = useRef<OsmdRenderer | null>(null);
  const priorTargetQuarter = useRef<number | null>(null);
  const highlightedQuarter = useRef<number | null>(null);
  const highlightedNoteheads = useRef<Set<HTMLElement>>(new Set());
  const automaticScrollUntil = useRef(0);
  const onPagesRef = useRef(onPages);
  const [error, setError] = useState<string | null>(null);
  const [renderVersion, setRenderVersion] = useState(0);
  const playbackStatus = usePlaybackStore((state) => state.status);
  const scoreFollow = usePlaybackStore((state) => state.scoreFollow);
  const detachScore = usePlaybackStore((state) => state.detachScore);
  const priorScoreFollow = useRef(scoreFollow);
  onPagesRef.current = onPages;

  const clearNoteHighlight = () => {
    for (const notehead of highlightedNoteheads.current) {
      notehead.classList.remove("playback-note-active");
    }
    highlightedNoteheads.current.clear();
    highlightedQuarter.current = null;
  };

  useEffect(() => {
    if (
      priorScoreFollow.current === "detached" &&
      scoreFollow === "following"
    ) {
      automaticScrollUntil.current = performance.now() + 180;
    }
    priorScoreFollow.current = scoreFollow;
  }, [scoreFollow]);

  useEffect(() => {
    const container = target.current;
    if (!container) return;
    let cancelled = false;
    let currentRenderer: OsmdRenderer | null = null;
    clearNoteHighlight();
    renderer.current = null;
    priorTargetQuarter.current = null;
    setError(null);
    void import("opensheetmusicdisplay")
      .then(async ({ OpenSheetMusicDisplay }) => {
        if (cancelled) return;
        const reader = readerLayout !== null;
        const next = new OpenSheetMusicDisplay(container, {
          autoResize: !reader,
          backend: "svg",
          drawTitle: false,
          drawingParameters: "compacttight",
          followCursor: false,
          cursorsOptions: [
            {
              type: 1,
              color: "#2fbe8c",
              alpha: 0.42,
              follow: false,
            },
          ],
        });
        currentRenderer = next;
        if (reader) {
          const rules = next.EngravingRules as unknown as ReaderEngravingRules;
          rules.NewPageAtXMLNewPageAttribute = true;
          rules.NewSystemAtXMLNewPageAttribute = true;
          rules.NewSystemAtXMLNewSystemAttribute = true;
          rules.MinimumDistanceBetweenSystems =
            readerLayout.engraving.minimumDistanceBetweenSystems;
          rules.MinSkyBottomDistBetweenSystems =
            readerLayout.engraving.minSkyBottomDistanceBetweenSystems;
          rules.PageTopMargin = 5;
          rules.PageTopMarginNarrow = 4;
          rules.PageBottomMargin = 4;
        }
        if (readerLayout) {
          next.setCustomPageFormat(
            readerLayout.formatWidth,
            readerLayout.formatHeight,
          );
        }
        await next.load(xml);
        if (cancelled) return;
        next.render();
        next.cursor.SkipInvisibleNotes = true;
        next.cursor.hide();
        renderer.current = next;
        const elements = pageElements(container);
        for (const [index, element] of elements.entries()) {
          element.classList.add("score-render-page");
          element.dataset.pageIndex = String(index);
        }
        const anchors = pageAnchors(next);
        for (const [index, element] of elements.entries()) {
          const anchor = anchors[index];
          if (!anchor) continue;
          element.dataset.firstMeasure = String(
            anchor.firstMeasureOrdinal,
          );
          if (anchor.firstScoreQuarter !== null) {
            element.dataset.firstScoreQuarter = String(
              anchor.firstScoreQuarter,
            );
          }
        }
        onPagesRef.current?.({
          pageCount: Math.max(elements.length, anchors.length, 1),
          pages: anchors.length
            ? anchors
            : [{
                pageIndex: 0,
                firstMeasureOrdinal: 0,
                firstScoreQuarter: 0,
              }],
        });
        setRenderVersion((value) => value + 1);
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        setError(
          reportClientAssetLoadError(error)
            ? "Atpiano was updated. Reload this page to render notation."
            : "Notation rendering failed.",
        );
      });
    return () => {
      cancelled = true;
      clearNoteHighlight();
      if (renderer.current === currentRenderer) renderer.current = null;
      currentRenderer?.clear();
      container.replaceChildren();
    };
  }, [
    readerLayout?.formatHeight,
    readerLayout?.formatWidth,
    readerLayout?.kind,
    readerLayout?.engraving.minSkyBottomDistanceBetweenSystems,
    readerLayout?.engraving.minimumDistanceBetweenSystems,
    xml,
  ]);

  useEffect(() => {
    if (
      readerLayout ||
      playbackStatus !== "playing" ||
      scoreFollow !== "following"
    ) {
      return;
    }
    const detachForScrollIntent = () => detachScore();
    const detachForWindowScroll = () => {
      if (performance.now() > automaticScrollUntil.current) {
        detachScore();
      }
    };
    const keydown = (event: KeyboardEvent) => {
      if (
        event.target instanceof Element &&
        event.target.closest(
          "button, input, select, textarea, a, [role='button']",
        )
      ) {
        return;
      }
      if (
        [
          "ArrowUp",
          "ArrowDown",
          "PageUp",
          "PageDown",
          "Home",
          "End",
          " ",
        ].includes(event.key)
      ) {
        detachScore();
      }
    };
    window.addEventListener("wheel", detachForScrollIntent, {
      passive: true,
    });
    window.addEventListener("touchmove", detachForScrollIntent, {
      passive: true,
    });
    window.addEventListener("scroll", detachForWindowScroll, {
      passive: true,
    });
    window.addEventListener("keydown", keydown);
    return () => {
      window.removeEventListener("wheel", detachForScrollIntent);
      window.removeEventListener("touchmove", detachForScrollIntent);
      window.removeEventListener("scroll", detachForWindowScroll);
      window.removeEventListener("keydown", keydown);
    };
  }, [detachScore, playbackStatus, readerLayout, scoreFollow]);

  useEffect(() => {
    if (!readerLayout || !target.current) return;
    for (const [index, element] of pageElements(target.current).entries()) {
      const visible = index >= pageStart && index < pageStart + pageSpan;
      element.hidden = !visible;
      element.setAttribute("aria-hidden", String(!visible));
    }
  }, [pageSpan, pageStart, readerLayout, renderVersion]);

  useEffect(() => {
    const cursor = renderer.current?.cursor as
      | PlaybackCursorLike
      | undefined;
    if (!cursor) return;
    const targetQuarter = scoreAttackAtSample(
      alignment,
      inspectionSample,
      scoreHorizonSample,
    );
    priorTargetQuarter.current = moveScoreCursor(
      cursor,
      targetQuarter,
      priorTargetQuarter.current,
    );
    if (highlightedQuarter.current !== targetQuarter) {
      clearNoteHighlight();
      if (targetQuarter !== null) {
        for (const note of cursor.GNotesUnderCursor?.() ?? []) {
          for (const notehead of note.getNoteheadSVGs?.() ?? []) {
            notehead.classList.add("playback-note-active");
            highlightedNoteheads.current.add(notehead);
          }
        }
        highlightedQuarter.current = targetQuarter;
      }
    }
    if (
      readerLayout ||
      playbackStatus !== "playing" ||
      scoreFollow !== "following" ||
      !paper.current ||
      !cursor.cursorElement
    ) {
      return;
    }
    const viewport = paper.current.getBoundingClientRect();
    const cursorBounds = cursor.cursorElement.getBoundingClientRect();
    const nextTop = scorePanelFollowTop({
      viewportTop: viewport.top,
      viewportHeight: paper.current.clientHeight || viewport.height,
      scrollTop: paper.current.scrollTop,
      scrollHeight: paper.current.scrollHeight,
      cursorTop: cursorBounds.top,
      cursorHeight: cursorBounds.height,
    });
    if (
      nextTop !== null &&
      Math.abs(nextTop - paper.current.scrollTop) >= 1
    ) {
      automaticScrollUntil.current = performance.now() + 180;
      paper.current.scrollTop = nextTop;
    }
  }, [
    alignment,
    inspectionSample,
    playbackStatus,
    readerLayout,
    renderVersion,
    scoreFollow,
    scoreHorizonSample,
  ]);

  const className = readerLayout
    ? "score-paper rendered reader-score-paper"
    : "score-paper rendered";
  return (
    <div
      ref={paper}
      className={className}
      onScroll={() => {
        if (
          !readerLayout &&
          playbackStatus === "playing" &&
          scoreFollow === "following" &&
          performance.now() > automaticScrollUntil.current
        ) {
          detachScore();
        }
      }}
      style={
        readerLayout
          ? {
              width: `${
                readerLayout.pageWidthPx * readerLayout.pageSpan +
                (readerLayout.pageSpan - 1) * 24
              }px`,
              minHeight: `${readerLayout.pageHeightPx}px`,
              "--reader-page-width":
                `${readerLayout.pageWidthPx}px`,
            }
          : undefined
      }
    >
      <div ref={target} aria-label="Rendered committed MusicXML score" />
      {error && <p className="score-render-error" role="status">{error}</p>}
    </div>
  );
}

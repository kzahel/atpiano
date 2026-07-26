import { useEffect, useRef, useState } from "react";
import type {
  OpenSheetMusicDisplay as OsmdRenderer,
} from "opensheetmusicdisplay";

import {
  moveScoreCursor,
  scoreAttackAtSample,
  type ScoreAlignment,
} from "../lib/score-alignment.js";
import type {
  ScorePageAnchor,
  ScoreReaderLayout,
} from "../lib/score-reader-layout.js";

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
  const target = useRef<HTMLDivElement>(null);
  const renderer = useRef<OsmdRenderer | null>(null);
  const priorTargetQuarter = useRef<number | null>(null);
  const onPagesRef = useRef(onPages);
  const [error, setError] = useState<string | null>(null);
  const [renderVersion, setRenderVersion] = useState(0);
  onPagesRef.current = onPages;

  useEffect(() => {
    const container = target.current;
    if (!container) return;
    let cancelled = false;
    let currentRenderer: OsmdRenderer | null = null;
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
          followCursor: !reader,
          cursorsOptions: [
            {
              type: 1,
              color: "#2fbe8c",
              alpha: 0.82,
              follow: !reader,
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
      .catch(() => {
        if (!cancelled) setError("Notation rendering failed.");
      });
    return () => {
      cancelled = true;
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
    if (!readerLayout || !target.current) return;
    for (const [index, element] of pageElements(target.current).entries()) {
      const visible = index >= pageStart && index < pageStart + pageSpan;
      element.hidden = !visible;
      element.setAttribute("aria-hidden", String(!visible));
    }
  }, [pageSpan, pageStart, readerLayout, renderVersion]);

  useEffect(() => {
    const cursor = renderer.current?.cursor;
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
  }, [
    alignment,
    inspectionSample,
    renderVersion,
    scoreHorizonSample,
  ]);

  const className = readerLayout
    ? "score-paper rendered reader-score-paper"
    : "score-paper rendered";
  return (
    <div
      className={className}
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

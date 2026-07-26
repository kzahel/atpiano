export type ScoreDensity = "large" | "comfortable" | "compact";

export interface ScoreReaderLayout {
  readonly kind: "screen" | "paper";
  readonly pageSpan: 1 | 2;
  readonly pageWidthPx: number;
  readonly pageHeightPx: number;
  readonly formatWidth: number;
  readonly formatHeight: number;
  readonly zoom: number;
}

export interface ScorePageAnchor {
  readonly pageIndex: number;
  readonly firstMeasureOrdinal: number;
}

const a4Width = 210;
const a4Height = 297;
const paperRatio = a4Width / a4Height;
const spreadGap = 24;
const paperMargin = 24;
const screenMargin = 12;
const minimumSpreadPageWidth = 500;

const densityZoom: Record<ScoreDensity, number> = {
  large: 1.16,
  comfortable: 1,
  compact: 0.88,
};

function positiveSize(value: number, fallback: number): number {
  return Number.isFinite(value) && value > 0 ? value : fallback;
}

export function scoreReaderLayout(
  rawWidth: number,
  rawHeight: number,
  density: ScoreDensity,
): ScoreReaderLayout {
  const width = positiveSize(rawWidth, 360);
  const height = positiveSize(rawHeight, 640);
  const screenLayout = width < 600 || height < 560;
  const margin = screenLayout ? screenMargin : paperMargin;
  const availableWidth = Math.max(280, width - margin * 2);
  const availableHeight = Math.max(240, height - margin * 2);
  const zoom = densityZoom[density];

  if (screenLayout) {
    const pageWidthPx = Math.floor(availableWidth);
    const pageHeightPx = Math.floor(availableHeight);
    return {
      kind: "screen",
      pageSpan: 1,
      pageWidthPx,
      pageHeightPx,
      formatWidth: a4Width,
      formatHeight: a4Width * (pageHeightPx / pageWidthPx),
      zoom,
    };
  }

  const spreadAvailable = (availableWidth - spreadGap) / 2;
  const spreadPageWidth = Math.min(
    spreadAvailable,
    availableHeight * paperRatio,
  );
  const pageSpan = (
    spreadPageWidth >= minimumSpreadPageWidth ? 2 : 1
  ) as 1 | 2;
  const pageAvailable = pageSpan === 2
    ? spreadAvailable
    : availableWidth;
  const pageWidthPx = Math.floor(
    Math.min(pageAvailable, availableHeight * paperRatio),
  );
  return {
    kind: "paper",
    pageSpan,
    pageWidthPx,
    pageHeightPx: Math.floor(pageWidthPx / paperRatio),
    formatWidth: a4Width,
    formatHeight: a4Height,
    zoom,
  };
}

export function spreadStart(
  requestedPage: number,
  pageCount: number,
  pageSpan: 1 | 2,
): number {
  if (pageCount < 1) return 0;
  const clamped = Math.max(0, Math.min(pageCount - 1, requestedPage));
  return pageSpan === 2 ? clamped - (clamped % 2) : clamped;
}

export function pageForMeasure(
  pages: readonly ScorePageAnchor[],
  measureOrdinal: number,
): number {
  let page = 0;
  for (const candidate of pages) {
    if (candidate.firstMeasureOrdinal > measureOrdinal) break;
    page = candidate.pageIndex;
  }
  return page;
}

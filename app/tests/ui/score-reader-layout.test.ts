import { describe, expect, it } from "vitest";

import {
  pageForMeasure,
  pageForScoreQuarter,
  scoreReaderLayout,
  spreadStart,
} from "../../src/lib/score-reader-layout.js";

describe("score reader layout", () => {
  it("uses screen-shaped single pages on phones", () => {
    const portrait = scoreReaderLayout(360, 720, "large");
    const landscape = scoreReaderLayout(844, 390, "comfortable");

    expect(portrait.kind).toBe("screen");
    expect(portrait.pageSpan).toBe(1);
    expect(portrait.formatHeight).toBeGreaterThan(portrait.formatWidth);
    expect(landscape.kind).toBe("screen");
    expect(landscape.formatHeight).toBeLessThan(landscape.formatWidth);
  });

  it("selects paper pages and readable spreads from measured space", () => {
    const tablet = scoreReaderLayout(768, 920, "comfortable");
    const laptop = scoreReaderLayout(1440, 820, "compact");

    expect(tablet.kind).toBe("paper");
    expect(tablet.pageSpan).toBe(1);
    expect(laptop.kind).toBe("paper");
    expect(laptop.pageSpan).toBe(2);
    expect(laptop.formatWidth).toBeGreaterThan(tablet.formatWidth);
    expect(
      laptop.engraving.minimumDistanceBetweenSystems,
    ).toBeLessThan(
      tablet.engraving.minimumDistanceBetweenSystems,
    );
  });

  it("makes every density a distinct engraving profile", () => {
    const large = scoreReaderLayout(1200, 900, "large");
    const comfortable = scoreReaderLayout(1200, 900, "comfortable");
    const compact = scoreReaderLayout(1200, 900, "compact");

    expect(large.formatWidth).toBeLessThan(comfortable.formatWidth);
    expect(comfortable.formatWidth).toBeLessThan(compact.formatWidth);
    expect(
      large.engraving.minimumDistanceBetweenSystems,
    ).toBeGreaterThan(
      comfortable.engraving.minimumDistanceBetweenSystems,
    );
    expect(
      comfortable.engraving.minSkyBottomDistanceBetweenSystems,
    ).toBeGreaterThan(
      compact.engraving.minSkyBottomDistanceBetweenSystems,
    );
    expect(large.formatWidth / large.formatHeight).toBeCloseTo(
      comfortable.formatWidth / comfortable.formatHeight,
    );
  });

  it("clamps turns to a complete spread", () => {
    expect(spreadStart(-1, 5, 1)).toBe(0);
    expect(spreadStart(3, 5, 2)).toBe(2);
    expect(spreadStart(99, 5, 2)).toBe(4);
  });

  it("restores the page containing a measure anchor", () => {
    const pages = [
      { pageIndex: 0, firstMeasureOrdinal: 0, firstScoreQuarter: 0 },
      { pageIndex: 1, firstMeasureOrdinal: 4, firstScoreQuarter: 16 },
      { pageIndex: 2, firstMeasureOrdinal: 9, firstScoreQuarter: 36 },
    ];

    expect(pageForMeasure(pages, 0)).toBe(0);
    expect(pageForMeasure(pages, 7)).toBe(1);
    expect(pageForMeasure(pages, 99)).toBe(2);
    expect(pageForScoreQuarter(pages, 20)).toBe(1);
  });
});

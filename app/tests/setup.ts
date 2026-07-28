import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

Object.defineProperty(window, "matchMedia", {
  configurable: true,
  value: vi.fn().mockImplementation(() => ({
    matches: false,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  })),
});

const localValues = new Map<string, string>();
Object.defineProperty(window, "localStorage", {
  configurable: true,
  value: {
    getItem(key: string) {
      return localValues.get(key) ?? null;
    },
    setItem(key: string, value: string) {
      localValues.set(key, String(value));
    },
    removeItem(key: string) {
      localValues.delete(key);
    },
    clear() {
      localValues.clear();
    },
  },
});

let nextObjectUrl = 0;
Object.defineProperty(URL, "createObjectURL", {
  configurable: true,
  value: vi.fn(() => `blob:atpiano-test-${nextObjectUrl += 1}`),
});
Object.defineProperty(URL, "revokeObjectURL", {
  configurable: true,
  value: vi.fn(),
});

vi.mock("opensheetmusicdisplay", () => ({
  OpenSheetMusicDisplay: class {
    readonly #container: HTMLElement;
    Zoom = 1;
    readonly EngravingRules = {
      NewPageAtXMLNewPageAttribute: false,
      NewSystemAtXMLNewPageAttribute: false,
      NewSystemAtXMLNewSystemAttribute: false,
      MinimumDistanceBetweenSystems: 7,
      MinSkyBottomDistBetweenSystems: 5,
      PageTopMargin: 5,
      PageTopMarginNarrow: 0,
      PageBottomMargin: 5,
    };
    readonly cursor = {
      SkipInvisibleNotes: true,
      Iterator: {
        CurrentSourceTimestamp: { RealValue: 0 },
        EndReached: false,
      },
      reset() {
        this.Iterator.CurrentSourceTimestamp.RealValue = 0;
        this.Iterator.EndReached = false;
      },
      next() {
        this.Iterator.CurrentSourceTimestamp.RealValue += 1;
        if (this.Iterator.CurrentSourceTimestamp.RealValue >= 16) {
          this.Iterator.EndReached = true;
        }
      },
      show() {},
      hide() {},
    };
    readonly GraphicSheet = {
      MusicPages: [0, 4, 8, 12].map((measure) => ({
        MusicSystems: [{
          GraphicalMeasures: [[{
            parentSourceMeasure: { measureListIndex: measure },
          }]],
          GetSystemsFirstTimeStamp: () => ({ RealValue: measure }),
        }],
      })),
    };

    constructor(container: HTMLElement) {
      this.#container = container;
    }

    setPageFormat() {}

    setCustomPageFormat(width: number, height: number) {
      this.#container.dataset.osmdFormatWidth = String(width);
      this.#container.dataset.osmdFormatHeight = String(height);
    }

    async load() {}

    render() {
      this.#container.dataset.osmdMinimumSystemDistance = String(
        this.EngravingRules.MinimumDistanceBetweenSystems,
      );
      this.#container.dataset.osmdSkyBottomSystemDistance = String(
        this.EngravingRules.MinSkyBottomDistBetweenSystems,
      );
      this.#container.replaceChildren(
        ...this.GraphicSheet.MusicPages.map((_, index) => {
          const page = document.createElement("div");
          page.id = `osmdCanvasPage${index}`;
          const svg = document.createElementNS(
            "http://www.w3.org/2000/svg",
            "svg",
          );
          svg.setAttribute("aria-label", `Fixture score page ${index + 1}`);
          page.append(svg);
          return page;
        }),
      );
    }

    clear() {
      this.#container.replaceChildren();
    }
  },
}));

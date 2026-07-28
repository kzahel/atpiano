import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { PianoKeyboard } from "../../src/components/piano-keyboard.js";
import type { PianoSynthController } from "../../src/lib/piano-synth.js";

describe("playable piano keyboard", () => {
  it("starts and releases a synthesized note with pointer input", () => {
    const synth: PianoSynthController = {
      noteOn: vi.fn(),
      noteOff: vi.fn(),
      releaseAll: vi.fn(),
    };
    render(
      <PianoKeyboard
        events={[]}
        inspectionSample={null}
        createSynth={() => synth}
      />,
    );

    const middleC = screen.getByRole("button", { name: "Play C4" });
    fireEvent.pointerDown(middleC, { button: 0, pointerId: 7 });

    expect(synth.noteOn).toHaveBeenCalledWith(60);
    expect(middleC.getAttribute("aria-pressed")).toBe("true");

    fireEvent.pointerUp(middleC, { pointerId: 7 });

    expect(synth.noteOff).toHaveBeenCalledWith(60);
    expect(middleC.getAttribute("aria-pressed")).toBe("false");
  });

  it("supports arrow navigation and keyboard note audition", () => {
    const synth: PianoSynthController = {
      noteOn: vi.fn(),
      noteOff: vi.fn(),
      releaseAll: vi.fn(),
    };
    render(
      <PianoKeyboard
        events={[]}
        inspectionSample={null}
        createSynth={() => synth}
      />,
    );

    const middleC = screen.getByRole("button", { name: "Play C4" });
    middleC.focus();
    fireEvent.keyDown(middleC, { key: "ArrowRight" });

    const cSharp = screen.getByRole("button", { name: "Play C♯4" });
    expect(document.activeElement).toBe(cSharp);

    fireEvent.keyDown(cSharp, { key: " " });
    expect(synth.noteOn).toHaveBeenCalledWith(61);
    fireEvent.keyUp(cSharp, { key: " " });
    expect(synth.noteOff).toHaveBeenCalledWith(61);
  });
});

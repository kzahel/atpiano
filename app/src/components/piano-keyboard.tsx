import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
  type PointerEvent,
} from "react";

import { noteName } from "../lib/format.js";
import { pianoLayout } from "../lib/piano-layout.js";
import {
  PianoSynth,
  type PianoSynthController,
} from "../lib/piano-synth.js";
import type { EventRevision } from "../runtime/atpiano-runtime.js";

function activePitches(
  events: readonly EventRevision[],
  sample: number,
): Set<number> {
  return new Set(
    events
      .filter(
        (event) =>
          event.kind === "note" &&
          event.pitch !== null &&
          event.lifecycle !== "retracted" &&
          event.onset_sample <= sample &&
          (event.offset_sample ?? sample) >= sample,
      )
      .map((event) => event.pitch!),
  );
}

export function PianoKeyboard({
  events,
  inspectionSample,
  createSynth = () => new PianoSynth(),
}: {
  readonly events: readonly EventRevision[];
  readonly inspectionSample: number | null;
  readonly createSynth?: () => PianoSynthController;
}) {
  const notes = events.filter(
    (event) => event.kind === "note" && event.lifecycle !== "retracted",
  );
  const latest = Math.max(0, ...notes.map((event) => event.onset_sample));
  const sample = inspectionSample ?? latest;
  const sounding = activePitches(notes, sample);
  const layout = useMemo(pianoLayout, []);
  const synth = useRef<PianoSynthController | null>(null);
  const pointerNotes = useRef(new Map<number, number>());
  const keyButtons = useRef(new Map<number, HTMLButtonElement>());
  const [auditioned, setAuditioned] = useState<ReadonlySet<number>>(
    () => new Set(),
  );
  const [focusPitch, setFocusPitch] = useState(60);
  const [audioError, setAudioError] = useState<string | null>(null);

  useEffect(
    () => () => {
      synth.current?.releaseAll();
    },
    [],
  );

  const startNote = (pitch: number) => {
    try {
      synth.current ??= createSynth();
      synth.current.noteOn(pitch);
      setAuditioned((current) => new Set(current).add(pitch));
      setAudioError(null);
    } catch (error) {
      setAudioError(error instanceof Error ? error.message : String(error));
    }
  };

  const stopNote = (pitch: number) => {
    synth.current?.noteOff(pitch);
    setAuditioned((current) => {
      const next = new Set(current);
      next.delete(pitch);
      return next;
    });
  };

  const stopPointerNote = (event: PointerEvent<HTMLButtonElement>) => {
    const pitch = pointerNotes.current.get(event.pointerId);
    if (pitch === undefined) return;
    pointerNotes.current.delete(event.pointerId);
    stopNote(pitch);
  };

  const handleKeyDown = (
    event: KeyboardEvent<HTMLButtonElement>,
    pitch: number,
  ) => {
    const focusTarget =
      event.key === "ArrowLeft"
        ? Math.max(21, pitch - 1)
        : event.key === "ArrowRight"
          ? Math.min(108, pitch + 1)
          : event.key === "Home"
            ? 21
            : event.key === "End"
              ? 108
              : null;
    if (focusTarget !== null) {
      event.preventDefault();
      setFocusPitch(focusTarget);
      keyButtons.current.get(focusTarget)?.focus();
      return;
    }
    if ((event.key === "Enter" || event.key === " ") && !event.repeat) {
      event.preventDefault();
      startNote(pitch);
    }
  };

  const handleKeyUp = (
    event: KeyboardEvent<HTMLButtonElement>,
    pitch: number,
  ) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      stopNote(pitch);
    }
  };

  return (
    <section className="view-card keyboard-card">
      <div className="view-heading">
        <div>
          <p className="eyebrow">Play or check a pitch</p>
          <h3>Detected keys</h3>
        </div>
        <output>
          {sounding.size
            ? [...sounding].map(noteName).join(" · ")
            : "No keys sounding"}
        </output>
      </div>
      <p className="keyboard-hint">Click, tap, or focus a key to hear it.</p>
      <div className="piano-keyboard" role="group" aria-label="Playable piano keyboard">
        {layout.map((key) => {
          const detected = sounding.has(key.pitch);
          const playing = auditioned.has(key.pitch);
          const name = noteName(key.pitch);
          return (
            <button
              key={key.pitch}
              className={`${key.black ? "black" : "white"} ${
                detected ? "sounding" : ""
              } ${playing ? "auditioned" : ""}`}
              type="button"
              aria-label={`Play ${name}${detected ? ", detected at the current position" : ""}`}
              aria-pressed={playing}
              tabIndex={key.pitch === focusPitch ? 0 : -1}
              ref={(element) => {
                if (element) keyButtons.current.set(key.pitch, element);
                else keyButtons.current.delete(key.pitch);
              }}
              style={{
                left: `${key.leftPercent}%`,
                width: `${key.widthPercent}%`,
              }}
              title={`Play ${name}`}
              onFocus={() => setFocusPitch(key.pitch)}
              onPointerDown={(event) => {
                if (event.button !== 0) return;
                event.preventDefault();
                event.currentTarget.setPointerCapture?.(event.pointerId);
                pointerNotes.current.set(event.pointerId, key.pitch);
                startNote(key.pitch);
              }}
              onPointerUp={stopPointerNote}
              onPointerCancel={stopPointerNote}
              onLostPointerCapture={stopPointerNote}
              onKeyDown={(event) => handleKeyDown(event, key.pitch)}
              onKeyUp={(event) => handleKeyUp(event, key.pitch)}
            />
          );
        })}
      </div>
      {audioError && (
        <p className="surface-feedback error" role="alert">{audioError}</p>
      )}
    </section>
  );
}

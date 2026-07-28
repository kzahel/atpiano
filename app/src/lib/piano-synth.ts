export interface PianoSynthController {
  noteOn(pitch: number): void;
  noteOff(pitch: number): void;
  releaseAll(): void;
}

interface PianoVoice {
  readonly envelope: GainNode;
  readonly oscillators: readonly OscillatorNode[];
}

function createAudioContext(): AudioContext {
  const AudioContextConstructor = window.AudioContext ??
    (
      window as typeof window & {
        readonly webkitAudioContext?: typeof AudioContext;
      }
    ).webkitAudioContext;
  if (!AudioContextConstructor) {
    throw new Error("Your browser does not support synthesized piano audio.");
  }
  return new AudioContextConstructor();
}

export function midiFrequency(pitch: number): number {
  return 440 * 2 ** ((pitch - 69) / 12);
}

export class PianoSynth implements PianoSynthController {
  readonly #voices = new Map<number, PianoVoice>();
  readonly #contextFactory: () => AudioContext;
  #context: AudioContext | null = null;

  constructor(contextFactory: () => AudioContext = createAudioContext) {
    this.#contextFactory = contextFactory;
  }

  noteOn(pitch: number): void {
    if (this.#voices.has(pitch)) return;

    const context = this.#context ??= this.#contextFactory();
    if (context.state === "suspended") void context.resume();

    const now = context.currentTime;
    const envelope = context.createGain();
    envelope.gain.setValueAtTime(0.0001, now);
    envelope.gain.exponentialRampToValueAtTime(0.24, now + 0.008);
    envelope.gain.exponentialRampToValueAtTime(0.1, now + 0.16);
    envelope.gain.exponentialRampToValueAtTime(0.035, now + 1.8);
    envelope.connect(context.destination);

    const fundamental = midiFrequency(pitch);
    const partials = [
      { ratio: 1, gain: 0.72, type: "triangle" as OscillatorType },
      { ratio: 2, gain: 0.2, type: "sine" as OscillatorType },
      { ratio: 3, gain: 0.08, type: "sine" as OscillatorType },
    ];
    const oscillators = partials.map((partial) => {
      const oscillator = context.createOscillator();
      const partialGain = context.createGain();
      oscillator.type = partial.type;
      oscillator.frequency.setValueAtTime(fundamental * partial.ratio, now);
      partialGain.gain.setValueAtTime(partial.gain, now);
      oscillator.connect(partialGain);
      partialGain.connect(envelope);
      oscillator.start(now);
      return oscillator;
    });

    this.#voices.set(pitch, { envelope, oscillators });
  }

  noteOff(pitch: number): void {
    const voice = this.#voices.get(pitch);
    const context = this.#context;
    if (!voice || !context) return;

    this.#voices.delete(pitch);
    const now = context.currentTime;
    const stopAt = now + 0.42;
    voice.envelope.gain.cancelScheduledValues(now);
    voice.envelope.gain.setValueAtTime(
      Math.max(0.0001, voice.envelope.gain.value),
      now,
    );
    voice.envelope.gain.exponentialRampToValueAtTime(0.0001, stopAt);
    voice.oscillators.forEach((oscillator) => oscillator.stop(stopAt + 0.02));
  }

  releaseAll(): void {
    [...this.#voices.keys()].forEach((pitch) => this.noteOff(pitch));
  }
}

import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import {
  compareTransformerMidiOrder,
  transformerMidiOrder,
  transformerMidiTick,
} from "../src/lib/score-alignment.js";

interface TickCase {
  readonly label: string;
  readonly source_sample: number;
  readonly expected_tick: number;
}

interface DurationCase {
  readonly label: string;
  readonly onset_sample: number;
  readonly offset_sample: number;
  readonly expected_onset_tick: number;
  readonly expected_offset_tick: number;
  readonly expected_duration_ticks: number;
}

interface FixtureNote {
  readonly event_id: string;
  readonly pitch: number;
  readonly onset_sample: number;
  readonly offset_sample: number;
}

interface MidiTickFixture {
  readonly operation_identity: string;
  readonly parameters: { readonly sample_rate_hz: number };
  readonly tick_cases: readonly TickCase[];
  readonly duration_cases: readonly DurationCase[];
  readonly ordering: {
    readonly notes: readonly FixtureNote[];
    readonly expected_event_ids: readonly string[];
  };
}

async function fixture(): Promise<MidiTickFixture> {
  return JSON.parse(
    await readFile(
      new URL("../../contracts/fixtures/v1/midi-tick-parity.json", import.meta.url),
      "utf8",
    ),
  ) as MidiTickFixture;
}

test("browser conversion matches the canonical producer ticks", async () => {
  const document = await fixture();
  assert.equal(
    document.operation_identity,
    "mido-second2tick-float-python-half-even-v1",
  );
  const sampleRateHz = document.parameters.sample_rate_hz;
  for (const value of document.tick_cases) {
    assert.equal(
      transformerMidiTick(value.source_sample, sampleRateHz),
      BigInt(value.expected_tick),
      value.label,
    );
  }
  for (const value of document.duration_cases) {
    const onset = transformerMidiTick(value.onset_sample, sampleRateHz);
    const offset = transformerMidiTick(value.offset_sample, sampleRateHz);
    assert.equal(onset, BigInt(value.expected_onset_tick), value.label);
    assert.equal(offset, BigInt(value.expected_offset_tick), value.label);
    assert.equal(
      offset - onset,
      BigInt(value.expected_duration_ticks),
      value.label,
    );
  }
});

test("browser ordering matches the canonical producer order", async () => {
  const document = await fixture();
  const sampleRateHz = document.parameters.sample_rate_hz;
  const ordered = document.ordering.notes.toSorted((left, right) =>
    compareTransformerMidiOrder(
      transformerMidiOrder(left, sampleRateHz),
      transformerMidiOrder(right, sampleRateHz),
    )
  );

  assert.deepEqual(
    ordered.map((value) => value.event_id),
    document.ordering.expected_event_ids,
  );
});

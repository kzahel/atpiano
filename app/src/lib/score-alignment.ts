export interface ScoreRational {
  readonly numerator: number;
  readonly denominator: number;
}

export interface ScoreAlignmentRow {
  readonly source_index: number;
  readonly event_id: string;
  readonly pitch: number;
  readonly onset_sample: number;
  readonly offset_sample: number;
  readonly status: "mapped" | "unmatched";
  readonly score_time_quarters: ScoreRational | null;
}

export interface ScoreAlignment {
  readonly schema_version: "atpiano.score-alignment.v2";
  readonly session_id: string;
  readonly sample_rate_hz: number;
  readonly musicxml: {
    readonly sha256: string;
  };
  readonly rows: readonly ScoreAlignmentRow[];
}

interface ExpectedScoreAlignment {
  readonly sessionId: string;
  readonly musicXmlSha256: string;
}

export interface ScoreCursorLike {
  readonly Iterator: {
    readonly CurrentSourceTimestamp: {
      readonly RealValue: number;
    };
    readonly EndReached: boolean;
  };
  reset(): void;
  next(): void;
  show(): void;
  hide(): void;
}

function record(value: unknown, field: string): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new Error(`${field} is invalid`);
  }
  return value as Record<string, unknown>;
}

function integer(value: unknown, field: string): number {
  if (!Number.isSafeInteger(value) || Number(value) < 0) {
    throw new Error(`${field} is invalid`);
  }
  return Number(value);
}

function rational(value: unknown, field: string): ScoreRational {
  const item = record(value, field);
  const numerator = integer(item.numerator, `${field}.numerator`);
  const denominator = integer(item.denominator, `${field}.denominator`);
  if (denominator === 0) throw new Error(`${field}.denominator is invalid`);
  return { numerator, denominator };
}

export function scoreRationalValue(value: ScoreRational): number {
  return value.numerator / value.denominator;
}

export function transformerMidiTick(
  sourceSample: number,
  sampleRateHz: number,
): bigint {
  // Mirror mido.second2tick's floating-point operation order before applying
  // Python's ties-to-even round. Algebraically equivalent rational arithmetic
  // can choose a different tick when the intermediate float straddles 0.5.
  const seconds = sourceSample / sampleRateHz;
  const secondsPerTick = 500_000 * 1e-6 / 480;
  const tick = seconds / secondsPerTick;
  const lower = Math.floor(tick);
  const fraction = tick - lower;
  if (fraction < 0.5) return BigInt(lower);
  if (fraction > 0.5) return BigInt(lower + 1);
  return BigInt(lower % 2 === 0 ? lower : lower + 1);
}

export type TransformerMidiOrder = readonly [
  onsetTick: bigint,
  pitch: number,
  durationTicks: bigint,
  onsetSample: number,
  offsetSample: number,
  eventId: string,
];

export function transformerMidiOrder(
  source: {
    readonly event_id: string;
    readonly pitch: number;
    readonly onset_sample: number;
    readonly offset_sample: number;
  },
  sampleRateHz: number,
): TransformerMidiOrder {
  const onsetTick = transformerMidiTick(
    source.onset_sample,
    sampleRateHz,
  );
  const offsetTick = transformerMidiTick(
    source.offset_sample,
    sampleRateHz,
  );
  return [
    onsetTick,
    source.pitch,
    offsetTick - onsetTick,
    source.onset_sample,
    source.offset_sample,
    source.event_id,
  ];
}

export function compareTransformerMidiOrder(
  left: TransformerMidiOrder,
  right: TransformerMidiOrder,
): number {
  if (left[0] < right[0]) return -1;
  if (left[0] > right[0]) return 1;
  if (left[1] < right[1]) return -1;
  if (left[1] > right[1]) return 1;
  if (left[2] < right[2]) return -1;
  if (left[2] > right[2]) return 1;
  if (left[3] < right[3]) return -1;
  if (left[3] > right[3]) return 1;
  if (left[4] < right[4]) return -1;
  if (left[4] > right[4]) return 1;
  if (left[5] < right[5]) return -1;
  if (left[5] > right[5]) return 1;
  return 0;
}

export function parseScoreAlignment(
  value: unknown,
  expected: ExpectedScoreAlignment,
): ScoreAlignment {
  const document = record(value, "score alignment");
  if (document.schema_version !== "atpiano.score-alignment.v2") {
    throw new Error("Score alignment version is unsupported");
  }
  if (document.session_id !== expected.sessionId) {
    throw new Error("Score alignment belongs to another session");
  }
  const musicxml = record(document.musicxml, "score alignment MusicXML");
  if (musicxml.sha256 !== expected.musicXmlSha256) {
    throw new Error("Score alignment belongs to another score snapshot");
  }
  const mapping = record(document.mapping, "score alignment mapping");
  if (
    mapping.algorithm !== "monotonic-exact-pitch-lcs-v1" ||
    mapping.source_order !==
      "onset-sample,pitch,duration,source-index" ||
    mapping.score_order !== "attack-quarters,pitch,output-index"
  ) {
    throw new Error("Score alignment mapping is unsupported");
  }
  if (!Array.isArray(document.rows)) {
    throw new Error("Score alignment rows are invalid");
  }
  const sampleRateHz = integer(document.sample_rate_hz, "sample_rate_hz");
  if (sampleRateHz === 0) {
    throw new Error("sample_rate_hz is invalid");
  }
  let priorMidiOrder: TransformerMidiOrder | null = null;
  const rows = document.rows.map((value, index): ScoreAlignmentRow => {
    const item = record(value, `score alignment row ${index}`);
    const sourceIndex = integer(item.source_index, "source_index");
    const onsetSample = integer(item.onset_sample, "onset_sample");
    const offsetSample = integer(item.offset_sample, "offset_sample");
    const pitch = integer(item.pitch, "pitch");
    if (
      sourceIndex !== index ||
      typeof item.event_id !== "string" ||
      offsetSample < onsetSample ||
      pitch < 21 ||
      pitch > 108
    ) {
      throw new Error("Score alignment source order is invalid");
    }
    const midiOrder = transformerMidiOrder({
      event_id: item.event_id,
      pitch,
      onset_sample: onsetSample,
      offset_sample: offsetSample,
    }, sampleRateHz);
    if (
      priorMidiOrder !== null &&
      compareTransformerMidiOrder(midiOrder, priorMidiOrder) < 0
    ) {
      throw new Error("Score alignment MIDI order is invalid");
    }
    priorMidiOrder = midiOrder;
    if (item.status === "unmatched") {
      if (item.score_time_quarters !== null) {
        throw new Error("Unmatched score alignment row has score time");
      }
      return {
        source_index: sourceIndex,
        event_id: item.event_id,
        pitch,
        onset_sample: onsetSample,
        offset_sample: offsetSample,
        status: "unmatched",
        score_time_quarters: null,
      };
    }
    if (item.status !== "mapped") {
      throw new Error("Score alignment status is invalid");
    }
    const scoreTime = rational(
      item.score_time_quarters,
      "score_time_quarters",
    );
    return {
      source_index: sourceIndex,
      event_id: item.event_id,
      pitch,
      onset_sample: onsetSample,
      offset_sample: offsetSample,
      status: "mapped",
      score_time_quarters: scoreTime,
    };
  });
  const sourceOrderedRows = rows.toSorted(
    (left, right) =>
      left.onset_sample - right.onset_sample ||
      left.pitch - right.pitch ||
      (
        left.offset_sample - left.onset_sample -
        (right.offset_sample - right.onset_sample)
      ) ||
      left.source_index - right.source_index,
  );
  let priorScoreTime = -1;
  for (const row of sourceOrderedRows) {
    if (row.status === "unmatched" || row.score_time_quarters === null) {
      continue;
    }
    const scoreValue = scoreRationalValue(row.score_time_quarters);
    if (scoreValue < priorScoreTime) {
      throw new Error("Score alignment score order is invalid");
    }
    priorScoreTime = scoreValue;
  }
  return {
    schema_version: "atpiano.score-alignment.v2",
    session_id: expected.sessionId,
    sample_rate_hz: sampleRateHz,
    musicxml: { sha256: expected.musicXmlSha256 },
    rows: sourceOrderedRows,
  };
}

export function scoreAttackAtSample(
  alignment: ScoreAlignment | undefined,
  sample: number | null,
  scoreHorizonSample: number | undefined,
): number | null {
  if (
    alignment === undefined ||
    sample === null ||
    scoreHorizonSample === undefined ||
    sample < 0 ||
    sample > scoreHorizonSample
  ) {
    return null;
  }
  let low = 0;
  let high = alignment.rows.length;
  while (low < high) {
    const middle = Math.floor((low + high) / 2);
    if (alignment.rows[middle]!.onset_sample <= sample) {
      low = middle + 1;
    } else {
      high = middle;
    }
  }
  for (let index = low - 1; index >= 0; index -= 1) {
    const row = alignment.rows[index]!;
    if (row.status === "mapped" && row.score_time_quarters !== null) {
      return scoreRationalValue(row.score_time_quarters);
    }
  }
  return null;
}

export function sourceSampleAtScoreQuarter(
  alignment: ScoreAlignment | undefined,
  scoreQuarter: number | null,
): number | null {
  if (alignment === undefined || scoreQuarter === null) return null;
  let lastMappedSample: number | null = null;
  for (const row of alignment.rows) {
    if (row.status !== "mapped" || row.score_time_quarters === null) continue;
    lastMappedSample = row.onset_sample;
    if (scoreRationalValue(row.score_time_quarters) >= scoreQuarter) {
      return row.onset_sample;
    }
  }
  return lastMappedSample;
}

function cursorQuarter(cursor: ScoreCursorLike): number {
  return cursor.Iterator.CurrentSourceTimestamp.RealValue * 4;
}

export function moveScoreCursor(
  cursor: ScoreCursorLike,
  targetQuarter: number | null,
  priorTargetQuarter: number | null,
): number | null {
  if (targetQuarter === null) {
    cursor.hide();
    return null;
  }
  if (
    priorTargetQuarter !== null &&
    Math.abs(priorTargetQuarter - targetQuarter) < 1e-8
  ) {
    return priorTargetQuarter;
  }
  if (
    priorTargetQuarter === null ||
    targetQuarter < priorTargetQuarter - 1e-8
  ) {
    cursor.reset();
  }
  let guard = 0;
  while (
    cursorQuarter(cursor) < targetQuarter - 1e-8 &&
    !cursor.Iterator.EndReached
  ) {
    const before = cursorQuarter(cursor);
    cursor.next();
    guard += 1;
    if (cursorQuarter(cursor) <= before + 1e-10 || guard > 10_000) break;
  }
  cursor.show();
  return targetQuarter;
}

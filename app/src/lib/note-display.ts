import type { EventRevision, Horizon } from "../runtime/atpiano-runtime.js";

export interface NoteDisplaySegments {
  readonly solidStart: number;
  readonly solidEnd: number;
  readonly tailStart: number | null;
  readonly tailEnd: number | null;
}

export function noteDisplaySegments(
  note: EventRevision,
  horizon: Horizon | undefined,
  sampleRateHz: number,
): NoteDisplaySegments | null {
  const onset = note.onset_sample;
  const audioHead = Math.max(onset, horizon?.audio_head_sample ?? onset);
  const commit = Math.max(0, horizon?.commit_sample ?? 0);
  const committed = note.lifecycle === "committed";

  if (committed && onset >= commit) return null;

  if (note.offset_state === "open") {
    const boundary = onset <= commit ? commit : audioHead;
    const visibleEnd = committed ? Math.min(boundary, commit) : boundary;
    if (visibleEnd <= onset) return null;
    const solidEnd = Math.min(
      visibleEnd,
      onset + Math.max(1, Math.round(sampleRateHz * 0.18)),
    );
    return {
      solidStart: onset,
      solidEnd,
      tailStart: solidEnd < visibleEnd ? solidEnd : null,
      tailEnd: solidEnd < visibleEnd ? visibleEnd : null,
    };
  }

  const rawEnd = Math.max(onset, note.offset_sample ?? onset);
  const visibleEnd = committed
    ? Math.min(rawEnd, commit)
    : Math.min(rawEnd, audioHead);
  if (visibleEnd <= onset) return null;
  return {
    solidStart: onset,
    solidEnd: visibleEnd,
    tailStart: null,
    tailEnd: null,
  };
}

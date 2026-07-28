import { requestId } from "./format.js";
import type {
  AtpianoRuntime,
  EventPage,
  EventRevision,
  Session,
} from "../runtime/atpiano-runtime.js";

function eventPageOnce(
  runtime: AtpianoRuntime,
  session: Session,
  startSample: number,
  endSample: number,
  signal: AbortSignal,
): Promise<EventPage> {
  return new Promise((resolve, reject) => {
    let settled = false;
    let subscription: ReturnType<AtpianoRuntime["subscribeEvents"]> | null =
      null;
    const finish = (operation: () => void) => {
      if (settled) return;
      settled = true;
      signal.removeEventListener("abort", abort);
      subscription?.close();
      operation();
    };
    const abort = () =>
      finish(() =>
        reject(
          new DOMException("Preview loading was cancelled.", "AbortError"),
        )
      );
    signal.addEventListener("abort", abort, { once: true });
    if (signal.aborted) {
      abort();
      return;
    }
    try {
      subscription = runtime.subscribeEvents(
        session.workspace_id,
        session.session_id,
        {
          requestId: requestId("session-preview"),
          signal,
          startSample,
          endSample,
          limit: 256,
        },
        {
          next: (page) => finish(() => resolve(page)),
          error: (error) => finish(() => reject(error)),
        },
      );
    } catch (error) {
      finish(() => reject(error));
    }
  });
}

function hasVisibleNote(page: EventPage): boolean {
  return page.items.some(
    (event) =>
      event.kind === "note" &&
      event.pitch !== null &&
      event.lifecycle !== "retracted",
  );
}

function isPageLimitError(error: unknown): boolean {
  return error instanceof Error &&
    error.message.includes("materialized event range exceeds page limit");
}

export async function openingEventPage(
  runtime: AtpianoRuntime,
  session: Session,
  endSample: number,
  signal: AbortSignal,
): Promise<EventPage> {
  const search = async (
    start: number,
    end: number,
  ): Promise<EventPage> => {
    try {
      return await eventPageOnce(runtime, session, start, end, signal);
    } catch (error) {
      if (!isPageLimitError(error) || end - start <= 1) throw error;

      const middle = start + Math.floor((end - start) / 2);
      const left = await search(start, middle);
      if (hasVisibleNote(left)) return left;
      return search(middle, end);
    }
  };

  return search(0, endSample);
}

export function firstVisibleNoteSample(
  events: readonly EventRevision[],
): number | null {
  let first: number | null = null;
  for (const event of events) {
    if (
      event.kind !== "note" ||
      event.pitch === null ||
      event.lifecycle === "retracted"
    ) {
      continue;
    }
    first = first === null
      ? event.onset_sample
      : Math.min(first, event.onset_sample);
  }
  return first;
}

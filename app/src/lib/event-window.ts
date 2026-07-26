export function liveFrameCount(
  storedFrameCount: number,
  audioHeadSample: number | undefined,
): number {
  return Math.max(storedFrameCount, audioHeadSample ?? 0);
}

export function eventWindow(
  storedFrameCount: number,
  audioHeadSample: number | undefined,
  maxRangeSamples: number,
): { readonly startSample: number; readonly endSample: number } {
  const endSample = Math.max(
    1,
    liveFrameCount(storedFrameCount, audioHeadSample),
  );
  return {
    startSample: Math.max(0, endSample - maxRangeSamples),
    endSample,
  };
}

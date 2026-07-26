export interface KeyLayout {
  readonly pitch: number;
  readonly black: boolean;
  readonly leftPercent: number;
  readonly widthPercent: number;
}

const blackClasses = new Set([1, 3, 6, 8, 10]);

export function pianoLayout(): KeyLayout[] {
  const whitePitches = Array.from(
    { length: 88 },
    (_, index) => index + 21,
  ).filter((pitch) => !blackClasses.has(pitch % 12));
  const whiteWidth = 100 / whitePitches.length;
  let whiteIndex = 0;
  return Array.from({ length: 88 }, (_, index) => {
    const pitch = index + 21;
    const black = blackClasses.has(pitch % 12);
    if (!black) {
      const result = {
        pitch,
        black,
        leftPercent: whiteIndex * whiteWidth,
        widthPercent: whiteWidth,
      };
      whiteIndex += 1;
      return result;
    }
    return {
      pitch,
      black,
      leftPercent: whiteIndex * whiteWidth - whiteWidth * 0.32,
      widthPercent: whiteWidth * 0.64,
    };
  });
}

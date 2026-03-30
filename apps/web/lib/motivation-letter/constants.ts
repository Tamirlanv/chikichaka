import type { MotivationPasteMeta } from "./types";

export const MIN_MOTIVATION_LETTER_LENGTH = 350;
export const MAX_MOTIVATION_LETTER_LENGTH = 1000;

export const DEFAULT_MOTIVATION_PASTE_META: MotivationPasteMeta = {
  wasPasted: false,
  pasteCount: 0,
  lastPastedAt: null,
};

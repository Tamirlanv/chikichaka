"use client";

import { useMemo, useState } from "react";
import { DEFAULT_MOTIVATION_PASTE_META } from "./constants";
import {
  getMotivationLetterCharCount,
  handleMotivationPasteMeta,
  normalizeMotivationLetter,
  trimToMotivationMax,
  validateMotivationLetter,
} from "./helpers";
import type { MotivationLetterState, MotivationPasteMeta } from "./types";

function buildState(text: string, meta: MotivationPasteMeta): MotivationLetterState {
  const normalized = normalizeMotivationLetter(trimToMotivationMax(text));
  const validation = validateMotivationLetter(normalized);
  return {
    text: normalized,
    charCount: getMotivationLetterCharCount(normalized),
    isValid: validation.isValid,
    errors: validation.errors,
    meta,
  };
}

export function useMotivationLetterField(initialValue = "", initialMeta?: Partial<MotivationPasteMeta>) {
  const bootMeta: MotivationPasteMeta = useMemo(
    () => ({
      wasPasted: Boolean(initialMeta?.wasPasted),
      pasteCount: initialMeta?.pasteCount && initialMeta.pasteCount > 0 ? Math.floor(initialMeta.pasteCount) : 0,
      lastPastedAt: typeof initialMeta?.lastPastedAt === "string" ? initialMeta.lastPastedAt : null,
    }),
    [initialMeta?.lastPastedAt, initialMeta?.pasteCount, initialMeta?.wasPasted],
  );
  const [state, setState] = useState<MotivationLetterState>(buildState(initialValue, bootMeta));

  function setText(next: string) {
    setState((prev) => buildState(next, prev.meta));
  }

  function registerPaste() {
    setState((prev) => buildState(prev.text, handleMotivationPasteMeta(prev.meta)));
  }

  function reset(nextText = "", nextMeta: MotivationPasteMeta = DEFAULT_MOTIVATION_PASTE_META) {
    setState(buildState(nextText, nextMeta));
  }

  return { state, setText, registerPaste, reset };
}

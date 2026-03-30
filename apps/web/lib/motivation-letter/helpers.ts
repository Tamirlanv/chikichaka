import { DEFAULT_MOTIVATION_PASTE_META, MAX_MOTIVATION_LETTER_LENGTH, MIN_MOTIVATION_LETTER_LENGTH } from "./constants";
import type { MotivationPasteMeta, MotivationValidationResult } from "./types";

export function normalizeMotivationLetter(text: string): string {
  return text.replace(/\r\n/g, "\n").replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/g, "");
}

export function getMotivationLetterCharCount(text: string): number {
  return text.length;
}

export function trimToMotivationMax(text: string): string {
  return text.length > MAX_MOTIVATION_LETTER_LENGTH ? text.slice(0, MAX_MOTIVATION_LETTER_LENGTH) : text;
}

export function validateMotivationLetter(text: string): MotivationValidationResult {
  const normalized = normalizeMotivationLetter(text);
  const charCount = getMotivationLetterCharCount(normalized);
  const trimmed = normalized.trim();
  const errors: string[] = [];

  if (trimmed.length === 0) {
    errors.push("Пожалуйста, напишите мотивационное письмо.");
  } else if (trimmed.length < MIN_MOTIVATION_LETTER_LENGTH) {
    errors.push(`Минимальный объем — ${MIN_MOTIVATION_LETTER_LENGTH} символов.`);
  }

  if (charCount > MAX_MOTIVATION_LETTER_LENGTH) {
    errors.push(`Максимальный объем — ${MAX_MOTIVATION_LETTER_LENGTH} символов.`);
  }

  return {
    isValid: errors.length === 0,
    errors,
  };
}

export function handleMotivationPasteMeta(prevMeta: MotivationPasteMeta): MotivationPasteMeta {
  return {
    wasPasted: true,
    pasteCount: prevMeta.pasteCount + 1,
    lastPastedAt: new Date().toISOString(),
  };
}

export function parseMotivationPasteMeta(input: unknown): MotivationPasteMeta {
  if (!input || typeof input !== "object") {
    return DEFAULT_MOTIVATION_PASTE_META;
  }
  const item = input as Partial<MotivationPasteMeta>;
  return {
    wasPasted: Boolean(item.wasPasted),
    pasteCount: typeof item.pasteCount === "number" && item.pasteCount >= 0 ? Math.floor(item.pasteCount) : 0,
    lastPastedAt: typeof item.lastPastedAt === "string" ? item.lastPastedAt : null,
  };
}

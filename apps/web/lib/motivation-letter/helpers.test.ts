import { describe, expect, it, vi } from "vitest";
import {
  MAX_MOTIVATION_LETTER_LENGTH,
  MIN_MOTIVATION_LETTER_LENGTH,
} from "./constants";
import {
  getMotivationLetterCharCount,
  handleMotivationPasteMeta,
  normalizeMotivationLetter,
  trimToMotivationMax,
  validateMotivationLetter,
} from "./helpers";

describe("motivation-letter/helpers", () => {
  it("normalizes line endings and strips control chars", () => {
    expect(normalizeMotivationLetter("a\r\nb\u0007")).toBe("a\nb");
  });

  it("counts chars as-is", () => {
    expect(getMotivationLetterCharCount("abc")).toBe(3);
  });

  it("trims to max motivation letter length", () => {
    const long = "x".repeat(MAX_MOTIVATION_LETTER_LENGTH + 100);
    expect(trimToMotivationMax(long)).toHaveLength(MAX_MOTIVATION_LETTER_LENGTH);
  });

  it("validates empty and too-short letters", () => {
    const empty = validateMotivationLetter("");
    expect(empty.isValid).toBe(false);
    expect(empty.errors[0]).toContain("Пожалуйста");

    const short = validateMotivationLetter("x".repeat(MIN_MOTIVATION_LETTER_LENGTH - 1));
    expect(short.isValid).toBe(false);
    expect(short.errors[0]).toContain(String(MIN_MOTIVATION_LETTER_LENGTH));
  });

  it("validates boundary lengths", () => {
    expect(validateMotivationLetter("x".repeat(MIN_MOTIVATION_LETTER_LENGTH)).isValid).toBe(true);
    expect(validateMotivationLetter("x".repeat(MAX_MOTIVATION_LETTER_LENGTH)).isValid).toBe(true);
    expect(validateMotivationLetter("x".repeat(MAX_MOTIVATION_LETTER_LENGTH + 1)).isValid).toBe(false);
  });

  it("updates paste meta without exposing UI state", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-03-30T12:00:00.000Z"));
    const next = handleMotivationPasteMeta({
      wasPasted: false,
      pasteCount: 0,
      lastPastedAt: null,
    });
    expect(next.wasPasted).toBe(true);
    expect(next.pasteCount).toBe(1);
    expect(next.lastPastedAt).toBe("2026-03-30T12:00:00.000Z");
    vi.useRealTimers();
  });
});

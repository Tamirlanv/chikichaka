import { describe, expect, it } from "vitest";
import { PERSONALITY_QUESTIONS, PERSONALITY_QUESTION_IDS } from "./questions";

function expectedPersonalityIds(): string[] {
  return Array.from({ length: 40 }, (_, i) =>
    `00000000-0000-4000-8000-${String(i + 1).padStart(12, "0")}`,
  );
}

describe("personality question IDs contract", () => {
  it("has exactly 40 questions and 40 IDs", () => {
    expect(PERSONALITY_QUESTIONS.length).toBe(40);
    expect(PERSONALITY_QUESTION_IDS.length).toBe(40);
  });

  it("uses stable UUIDs aligned with seed / API scoring", () => {
    const expected = new Set(expectedPersonalityIds());
    for (const q of PERSONALITY_QUESTIONS) {
      expect(expected.has(q.id)).toBe(true);
    }
  });
});

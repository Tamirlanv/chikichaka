import { describe, expect, it } from "vitest";

import { evaluateThresholds } from "../rules/thresholdEvaluator.js";

describe("evaluateThresholds", () => {
  it("checks IELTS >= 6.0", () => {
    expect(evaluateThresholds("ielts", 6.5).ieltsMinPassed).toBe(true);
    expect(evaluateThresholds("ielts", 5.5).ieltsMinPassed).toBe(false);
  });

  it("uses TOEFL_THRESHOLD from env (default 60)", () => {
    expect(evaluateThresholds("toefl", 65).toeflMinPassed).toBe(true);
    expect(evaluateThresholds("toefl", 59).toeflMinPassed).toBe(false);
  });

  it("nulls threshold when declaration mismatch for english exams", () => {
    expect(evaluateThresholds("ielts", 7.0, { declarationMismatch: true }).ieltsMinPassed).toBeNull();
    expect(evaluateThresholds("toefl", 100, { declarationMismatch: true }).toeflMinPassed).toBeNull();
  });

  it("flags ENT / NIS score detected", () => {
    expect(evaluateThresholds("ent", 110).entScoreDetected).toBe(true);
    expect(evaluateThresholds("nis_12", 88).entScoreDetected).toBe(true);
    expect(evaluateThresholds("ent", null).entScoreDetected).toBe(false);
  });
});

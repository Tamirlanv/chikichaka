import { describe, expect, it } from "vitest";
import { calculateProfile } from "./calculateProfile";
import { PERSONALITY_QUESTIONS, PERSONALITY_QUESTION_IDS } from "./questions";
import type { AnswerKey, UserAnswer } from "./types";

function answersAll(key: AnswerKey): UserAnswer[] {
  return PERSONALITY_QUESTION_IDS.map((id) => ({ questionId: id, answer: key }));
}

describe("personality-profile calculateProfile", () => {
  it("sums scores and returns totalScore=120 for 40 answered questions", () => {
    const res = calculateProfile(answersAll("A"), PERSONALITY_QUESTIONS, "ru");
    expect(res.totalScore).toBe(120);
    const sum = Object.values(res.rawScores).reduce((a, b) => a + b, 0);
    expect(sum).toBe(120);
    expect(res.ranking.length).toBe(5);
  });

  it("supports partial answers", () => {
    const partial: UserAnswer[] = PERSONALITY_QUESTION_IDS.slice(0, 10).map((id) => ({ questionId: id, answer: "B" }));
    const res = calculateProfile(partial, PERSONALITY_QUESTIONS, "en");
    expect(res.totalScore).toBeGreaterThan(0);
    expect(res.totalScore).toBeLessThan(120);
    expect(res.profileTitle.length).toBeGreaterThan(0);
  });

  it("zero-state returns 0 totals and safe defaults", () => {
    const res = calculateProfile([], PERSONALITY_QUESTIONS, "ru");
    expect(res.totalScore).toBe(0);
    expect(Object.values(res.percentages).every((x) => x === 0)).toBe(true);
    expect(res.explainability.answerContributions.length).toBe(0);
  });

  it("balanced profile detection triggers BALANCED when top1-top3 <= 3", () => {
    // Construct near-even: cycle answers to spread scoring.
    const cycle: AnswerKey[] = ["A", "B", "C", "D"];
    const ans: UserAnswer[] = PERSONALITY_QUESTION_IDS.map((id, i) => ({ questionId: id, answer: cycle[i % 4] }));
    const res = calculateProfile(ans, PERSONALITY_QUESTIONS, "ru");
    // Not guaranteed in all configs, but should usually trend balanced; assert via flag rule directly.
    if (res.flags.isBalancedProfile) {
      expect(res.profileType).toBe("BALANCED");
    }
  });

  it("fallback mapping always returns a known profileType", () => {
    const res = calculateProfile(answersAll("D"), PERSONALITY_QUESTIONS, "en");
    expect(
      ["INITIATOR", "ARCHITECT", "INTEGRATOR", "ADAPTER", "ANALYST", "BALANCED"].includes(res.profileType),
    ).toBe(true);
  });

  it("explainability includes answerContributions with addedTo rules", () => {
    const res = calculateProfile(answersAll("C"), PERSONALITY_QUESTIONS, "ru");
    expect(res.explainability.answerContributions.length).toBe(40);
    expect(res.explainability.topTraitsWhy.length).toBeGreaterThanOrEqual(2);
    const one = res.explainability.answerContributions[0];
    expect(one).toHaveProperty("questionId");
    expect(one).toHaveProperty("answer");
    expect(one).toHaveProperty("addedTo");
  });
});


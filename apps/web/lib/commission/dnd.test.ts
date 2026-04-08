import { describe, expect, it } from "vitest";
import type { CommissionBoardColumn } from "./types";
import { canMoveCards, isNextStageOnly, resolveDropStage } from "./dnd";

describe("commission dnd", () => {
  it("allows move only for reviewer/admin", () => {
    expect(canMoveCards("viewer")).toBe(false);
    expect(canMoveCards("reviewer")).toBe(true);
    expect(canMoveCards("admin")).toBe(true);
  });

  it("allows only next stage moves", () => {
    expect(isNextStageOnly("data_check", "application_review")).toBe(true);
    expect(isNextStageOnly("data_check", "interview")).toBe(false);
    expect(isNextStageOnly("result", "committee_decision")).toBe(false);
  });

  it("resolves drop stage by column id", () => {
    const columns: CommissionBoardColumn[] = [
      { stage: "data_check", title: "A", applications: [] },
      { stage: "interview", title: "B", applications: [] },
    ];
    expect(resolveDropStage("column:interview", columns)).toBe("interview");
    expect(resolveDropStage("column:unknown", columns)).toBeNull();
  });

  it("resolves drop stage by card id in target column", () => {
    const columns: CommissionBoardColumn[] = [
      {
        stage: "application_review",
        title: "A",
        applications: [
          {
            applicationId: "app-1",
            candidateId: "c1",
            candidateFullName: "Ivan Ivanov",
            program: "B",
            city: null,
            phone: null,
            age: null,
            submittedAt: null,
            updatedAt: null,
            currentStage: "application_review",
            currentStageStatus: null,
            finalDecision: null,
            manualAttentionFlag: false,
            commentCount: 0,
            aiRecommendation: null,
            aiConfidence: null,
            visualState: "neutral",
            aiInterviewCompletedAtIso: null,
            rubricThreeSectionsComplete: false,
            applicationReviewTotalScore: null,
            dataCheckRunStatus: null,
            stageOneDataReady: false,
            interviewScheduledAtIso: null,
          },
        ],
      },
    ];
    expect(resolveDropStage("app-1", columns)).toBe("application_review");
    expect(resolveDropStage("missing-app", columns)).toBeNull();
  });
});

import { describe, expect, it } from "vitest";

import {
  getLatestCandidateVisibleNote,
  isApplicationReviewStage,
  isDataVerificationStage,
  requiresRedirectFromInterviewRoute,
  type CandidateApplicationStatus,
} from "./candidate-status";

function buildStatus(overrides: Partial<CandidateApplicationStatus> = {}): CandidateApplicationStatus {
  return {
    current_stage: "application",
    submission_state: {
      state: "in_progress",
      submitted_at: null,
      locked: false,
    },
    stage_history: [],
    stage_descriptions: {},
    ...overrides,
  };
}

describe("candidate status helpers", () => {
  it("detects data verification stage", () => {
    expect(isDataVerificationStage(buildStatus({ current_stage: "initial_screening" }))).toBe(true);
    expect(isDataVerificationStage(buildStatus({ current_stage: "application" }))).toBe(false);
  });

  it("detects application review stage", () => {
    expect(isApplicationReviewStage(buildStatus({ current_stage: "application_review" }))).toBe(true);
    expect(isApplicationReviewStage(buildStatus({ current_stage: "initial_screening" }))).toBe(false);
  });

  it("returns latest non-empty candidate visible note", () => {
    const status = buildStatus({
      stage_history: [
        {
          to_stage: "application",
          entered_at: "2026-01-01T00:00:00Z",
          candidate_visible_note: "Первая заметка",
        },
        {
          to_stage: "initial_screening",
          entered_at: "2026-01-02T00:00:00Z",
          candidate_visible_note: "  ",
        },
        {
          to_stage: "initial_screening",
          entered_at: "2026-01-03T00:00:00Z",
          candidate_visible_note: "Актуальная заметка",
        },
      ],
    });
    expect(getLatestCandidateVisibleNote(status)).toBe("Актуальная заметка");
  });

  it("requiresRedirectFromInterviewRoute when on interview URL but stage is not interview", () => {
    const s = buildStatus({ current_stage: "application" });
    expect(requiresRedirectFromInterviewRoute("/application/interview", s)).toBe(true);
    expect(requiresRedirectFromInterviewRoute("/application/personal", s)).toBe(false);
    expect(requiresRedirectFromInterviewRoute("/application/interview", null)).toBe(false);
  });

  it("does not require redirect when on interview URL and stage is interview", () => {
    const s = buildStatus({ current_stage: "interview" });
    expect(requiresRedirectFromInterviewRoute("/application/interview", s)).toBe(false);
  });
});

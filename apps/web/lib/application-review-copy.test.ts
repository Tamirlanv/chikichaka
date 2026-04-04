import { describe, expect, it } from "vitest";

import { buildApplicationReviewCopy, FALLBACK_APPLICATION_REVIEW_CENTER } from "./application-review-copy";
import type { CandidateApplicationStatus } from "./candidate-status";
import { FALLBACK_STAGE_HINT } from "./data-verification-copy";

function buildStatus(overrides: Partial<CandidateApplicationStatus> = {}): CandidateApplicationStatus {
  return {
    current_stage: "application_review",
    submission_state: {
      state: "submitted",
      submitted_at: "2026-01-01T00:00:00Z",
      locked: true,
    },
    stage_history: [],
    stage_descriptions: {},
    ...overrides,
  };
}

describe("buildApplicationReviewCopy", () => {
  it("uses API stage description for hint when present", () => {
    const out = buildApplicationReviewCopy(
      buildStatus({
        stage_descriptions: { application_review: "Ждём экспертизу." },
      }),
    );
    expect(out.stageHint).toBe("Ждём экспертизу.");
  });

  it("falls back to shared stage hint when description missing", () => {
    const out = buildApplicationReviewCopy(buildStatus());
    expect(out.stageHint).toBe(FALLBACK_STAGE_HINT);
  });

  it("uses latest candidate_visible_note as center body when set", () => {
    const out = buildApplicationReviewCopy(
      buildStatus({
        stage_history: [
          {
            to_stage: "application_review",
            entered_at: "2026-01-02T00:00:00Z",
            candidate_visible_note: "Кастомный текст от комиссии.",
          },
        ],
      }),
    );
    expect(out.centerBody).toBe("Кастомный текст от комиссии.");
  });

  it("falls back to default center copy", () => {
    const out = buildApplicationReviewCopy(buildStatus());
    expect(out.centerBody).toBe(FALLBACK_APPLICATION_REVIEW_CENTER);
  });
});

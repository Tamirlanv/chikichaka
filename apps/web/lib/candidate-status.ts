export type InitialScreeningPipeline = {
  run_status: string | null;
  processing_state: "processing" | "success" | "problem";
  message: string;
};

export type CandidateApplicationStatus = {
  application_id?: string;
  current_stage: string;
  initial_screening_pipeline?: InitialScreeningPipeline | null;
  submission_state: {
    state: string;
    submitted_at: string | null;
    locked: boolean;
    queue_status?: "ready" | "degraded" | string;
    queue_failures_count?: number;
    queue_message?: string | null;
  };
  stage_history: Array<{
    from_stage?: string | null;
    to_stage: string;
    entered_at: string;
    exited_at?: string | null;
    candidate_visible_note?: string | null;
  }>;
  stage_descriptions: Record<string, string>;
};

export function isDataVerificationStage(status: CandidateApplicationStatus | null): boolean {
  return status?.current_stage === "initial_screening";
}

/** Заявка на этапе «Оценка заявки» у комиссии (после проверки данных). */
export function isApplicationReviewStage(status: CandidateApplicationStatus | null): boolean {
  return status?.current_stage === "application_review";
}

/** Этап устного / уточняющего собеседования с комиссией. */
export function isInterviewStage(status: CandidateApplicationStatus | null): boolean {
  return status?.current_stage === "interview";
}

export function getLatestCandidateVisibleNote(status: CandidateApplicationStatus | null): string | null {
  if (!status?.stage_history?.length) return null;
  for (let i = status.stage_history.length - 1; i >= 0; i -= 1) {
    const note = status.stage_history[i]?.candidate_visible_note?.trim();
    if (note) return note;
  }
  return null;
}

/** User is on /application/interview but active application is not in interview stage (e.g. new draft after commission archive). */
export function requiresRedirectFromInterviewRoute(
  pathname: string | null | undefined,
  status: CandidateApplicationStatus | null,
): boolean {
  if (!pathname?.startsWith("/application/interview")) return false;
  if (!status) return false;
  return !isInterviewStage(status);
}

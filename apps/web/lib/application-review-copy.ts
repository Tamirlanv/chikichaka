import { getLatestCandidateVisibleNote, type CandidateApplicationStatus } from "./candidate-status";
import { FALLBACK_STAGE_HINT } from "./data-verification-copy";

/** Текст по макету кандидата на этапе «Оценка заявки» (как на скрине). */
export const FALLBACK_APPLICATION_REVIEW_CENTER =
  "Прошу ожидайте, ваши данные сейчас на этапе оценивания модерацией. По окончании этапа на вашу почту придет сообщение о статусе заявки.";

export const FALLBACK_APPLICATION_REVIEW_ETA = "Оценивание длиться до 1-2 рабочих дня";

export function buildApplicationReviewCopy(status: CandidateApplicationStatus | null): {
  stageHint: string;
  centerBody: string;
  etaLine: string;
} {
  const stageHint =
    status?.stage_descriptions?.application_review?.trim() || FALLBACK_STAGE_HINT;
  const centerBody = getLatestCandidateVisibleNote(status)?.trim() || FALLBACK_APPLICATION_REVIEW_CENTER;
  const etaLine = FALLBACK_APPLICATION_REVIEW_ETA;

  return { stageHint, centerBody, etaLine };
}

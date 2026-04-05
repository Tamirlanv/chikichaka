import { getLatestCandidateVisibleNote, type CandidateApplicationStatus } from "./candidate-status";

export const FALLBACK_STAGE_HINT = "Пожалуйста ожидайте перехода на следующий этап";
export const FALLBACK_CENTER_BODY =
  "Пожалуйста ожидайте, ваши данные сейчас на этапе проверки модерации. По окончании проверки на вашу почту придет сообщение о статусе заявки.";
export const FALLBACK_ETA = "Модерация длится 5-10 минут";

export function buildDataVerificationCopy(status: CandidateApplicationStatus | null): {
  stageHint: string;
  centerBody: string;
  queueWarning: string | null;
} {
  const pipe = status?.initial_screening_pipeline;
  const stageHint =
    status?.current_stage === "initial_screening" && pipe?.message?.trim()
      ? pipe.message.trim()
      : status?.stage_descriptions?.initial_screening?.trim() || FALLBACK_STAGE_HINT;

  let centerBody = getLatestCandidateVisibleNote(status) || FALLBACK_CENTER_BODY;
  if (status?.current_stage === "initial_screening" && pipe?.message?.trim()) {
    centerBody = pipe.message.trim();
  }

  const queueWarning =
    status?.submission_state.queue_status === "degraded"
      ? (status.submission_state.queue_message ?? "Часть фоновой обработки ожидает восстановления сервиса.")
      : null;

  return { stageHint, centerBody, queueWarning };
}

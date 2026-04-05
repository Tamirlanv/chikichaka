import { apiFetch } from "@/lib/api-client";

export type AiInterviewCandidateQuestion = {
  id: string;
  sortOrder: number;
  questionText: string;
};

export type AiInterviewQuestionsResponse = {
  questions: AiInterviewCandidateQuestion[];
};

export async function getCandidateAiInterviewQuestions(): Promise<AiInterviewQuestionsResponse> {
  return await apiFetch<AiInterviewQuestionsResponse>("/candidates/me/application/ai-interview/questions");
}

export type AiInterviewCandidateAnswer = {
  questionId: string;
  text: string;
  updatedAt?: string | null;
};

export type AiInterviewAnswersResponse = {
  answers: AiInterviewCandidateAnswer[];
};

export async function getCandidateAiInterviewAnswers(): Promise<AiInterviewAnswersResponse> {
  return await apiFetch<AiInterviewAnswersResponse>("/candidates/me/application/ai-interview/answers");
}

export type PostAiInterviewAnswersBody = {
  answers: Array<{ questionId: string; text: string }>;
};

export async function postCandidateAiInterviewAnswers(
  body: PostAiInterviewAnswersBody,
): Promise<{ saved: number }> {
  return await apiFetch<{ saved: number }>("/candidates/me/application/ai-interview/answers", {
    method: "POST",
    json: body,
  });
}

export type PreferenceWindowPayload = {
  openedAt: string | null;
  expiresAt: string | null;
  status: string | null;
  remainingSeconds: number | null;
};

export type ScheduledInterviewPayload = {
  sessionId: string;
  scheduledAt: string | null;
  interviewMode: string | null;
  locationOrLink: string | null;
  scheduledByUserId: string | null;
  reminderRequestedAt: string | null;
  reminderSentAt: string | null;
};

export type CandidateAiInterviewStatus = {
  aiInterviewCompleted: boolean;
  preferencesSubmitted: boolean;
  approvedQuestionCount: number;
  answeredQuestionCount: number;
  preferenceWindow: PreferenceWindowPayload;
  scheduledInterview: ScheduledInterviewPayload | null;
};

export async function getCandidateAiInterviewStatus(): Promise<CandidateAiInterviewStatus> {
  return await apiFetch<CandidateAiInterviewStatus>("/candidates/me/application/ai-interview/status");
}

export async function postCandidateAiInterviewComplete(): Promise<{
  applicationId: string;
  sessionId: string;
  status: string;
  completedAt: string;
  alreadyCompleted?: boolean;
}> {
  return await apiFetch("/candidates/me/application/ai-interview/complete", { method: "POST", json: {} });
}

export type InterviewPreferenceDay = { date: string; label: string };
export type InterviewPreferenceSlot = { timeRangeCode: string; label: string };

export async function getInterviewPreferenceAvailableDays(): Promise<{ days: InterviewPreferenceDay[] }> {
  return await apiFetch("/candidates/me/application/interview-preferences/available-days");
}

export async function getInterviewPreferenceAvailableSlots(slotDate: string): Promise<{ slots: InterviewPreferenceSlot[] }> {
  const p = new URLSearchParams();
  p.set("slot_date", slotDate);
  return await apiFetch(`/candidates/me/application/interview-preferences/available-slots?${p.toString()}`);
}

export async function postInterviewPreferencesSubmit(slots: Array<{ date: string; timeRangeCode: string }>): Promise<{
  ok: boolean;
  submittedAt: string;
}> {
  return await apiFetch("/candidates/me/application/interview-preferences/submit", {
    method: "POST",
    json: { slots },
  });
}

export async function postCommissionInterviewReminder(): Promise<{
  ok: boolean;
  alreadySent?: boolean;
  alreadyRequested?: boolean;
  reminderSent?: boolean;
}> {
  return await apiFetch("/candidates/me/application/commission-interview/reminder", {
    method: "POST",
    json: {},
  });
}

import { apiFetch } from "@/lib/api-client";

export type CandidateActivityEventType =
  | "platform_interaction_ping"
  | "interview_info_opened"
  | "interview_instruction_opened"
  | "interview_link_copied"
  | "interview_link_opened"
  | "stage_action_started"
  | "section_saved"
  | "document_uploaded"
  | "internal_test_saved"
  | "internal_test_submitted"
  | "application_submitted"
  | "application_reopened"
  | "interview_preferences_submitted"
  | "ai_interview_completed"
  | "reminder_requested";

type CandidateActivityBody = {
  eventType: CandidateActivityEventType;
  occurredAt?: string;
  stage?: string;
  metadata?: Record<string, unknown>;
};

export async function postCandidateActivityEvent(body: CandidateActivityBody): Promise<void> {
  await apiFetch("/candidates/me/application/activity-events", {
    method: "POST",
    json: body,
  });
}

export async function postCandidateActivityEventSafe(body: CandidateActivityBody): Promise<void> {
  try {
    await postCandidateActivityEvent(body);
  } catch {
    // Telemetry is best-effort and must not break candidate UX.
  }
}

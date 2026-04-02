import type { AnswerKey, Question } from "./types";

export type ServerInternalTestQuestion = {
  id: string;
  display_order: number;
  question_type: string;
};

export type PersonalityQuestionMappings =
  | {
      ok: true;
      uiToServer: Map<string, string>;
      serverToUi: Map<string, string>;
    }
  | { ok: false; error: string };

/** User-facing messages when GET /internal-test/questions does not match the UI contract. */
export const INTERNAL_TEST_SYNC_ERRORS = {
  empty:
    "Вопросы теста ещё не настроены на сервере. Обратитесь к администратору или попробуйте позже.",
  wrongCount: (received: number, expected: number) =>
    `Тест временно недоступен: на сервере ${received} вопросов, ожидается ${expected}. Обратитесь к администратору.`,
  wrongType:
    "Тест временно недоступен: найден вопрос несовместимого типа. Обратитесь к администратору.",
} as const;

function assertChoiceQuestionTypes(
  rows: ServerInternalTestQuestion[],
): true | { ok: false; error: string } {
  for (const sq of rows) {
    if (sq.question_type !== "single_choice" && sq.question_type !== "multi_choice") {
      return { ok: false, error: INTERNAL_TEST_SYNC_ERRORS.wrongType };
    }
  }
  return true;
}

/**
 * Map static UI questions to server IDs for POST /internal-test/answers.
 * Prefer matching by stable UUID (`ui.id === server.id`); if any UI id is missing on the server,
 * fall back to pairing by sorted `display_order` (legacy DBs with different UUIDs).
 */
export function buildPersonalityQuestionMappings(
  uiQuestions: readonly Question[],
  serverQuestions: ServerInternalTestQuestion[],
): PersonalityQuestionMappings {
  const expected = uiQuestions.length;

  if (!serverQuestions.length) {
    return { ok: false, error: INTERNAL_TEST_SYNC_ERRORS.empty };
  }

  const serverById = new Map(serverQuestions.map((s) => [s.id, s]));

  const byIdUiToServer = new Map<string, string>();
  const byIdServerToUi = new Map<string, string>();
  let allUiHaveSameIdOnServer = true;
  for (const ui of uiQuestions) {
    const sv = serverById.get(ui.id);
    if (!sv) {
      allUiHaveSameIdOnServer = false;
      break;
    }
    byIdUiToServer.set(ui.id, sv.id);
    byIdServerToUi.set(sv.id, ui.id);
  }

  if (allUiHaveSameIdOnServer && byIdUiToServer.size === expected) {
    const mappedRows = uiQuestions.map((ui) => serverById.get(ui.id) as ServerInternalTestQuestion);
    const typeCheck = assertChoiceQuestionTypes(mappedRows);
    if (typeCheck !== true) return typeCheck;
    return { ok: true, uiToServer: byIdUiToServer, serverToUi: byIdServerToUi };
  }

  const sorted = [...serverQuestions].sort((a, b) => {
    if (a.display_order !== b.display_order) {
      return a.display_order - b.display_order;
    }
    return a.id.localeCompare(b.id);
  });

  if (sorted.length !== expected) {
    return { ok: false, error: INTERNAL_TEST_SYNC_ERRORS.wrongCount(sorted.length, expected) };
  }

  const typeCheck = assertChoiceQuestionTypes(sorted);
  if (typeCheck !== true) return typeCheck;

  const uiToServer = new Map<string, string>();
  const serverToUi = new Map<string, string>();
  for (let i = 0; i < expected; i++) {
    const ui = uiQuestions[i];
    const sv = sorted[i];
    uiToServer.set(ui.id, sv.id);
    serverToUi.set(sv.id, ui.id);
  }
  return { ok: true, uiToServer, serverToUi };
}

export function mapServerAnswersToUiRecord(
  serverToUi: Map<string, string>,
  savedAnswers: Array<{
    question_id: string;
    selected_options?: string[] | null;
  }>,
): Record<string, AnswerKey | undefined> {
  const acc: Record<string, AnswerKey | undefined> = {};
  for (const item of savedAnswers) {
    const uiId = serverToUi.get(item.question_id);
    if (!uiId) continue;
    const first = item.selected_options?.[0];
    if (first && ["A", "B", "C", "D"].includes(first)) {
      acc[uiId] = first as AnswerKey;
    }
  }
  return acc;
}

export function buildInternalTestAnswerPayload(
  questions: readonly Question[],
  answers: Record<string, AnswerKey | undefined>,
  uiToServer: Map<string, string>,
): Array<{ question_id: string; selected_options: AnswerKey[] }> {
  const out: Array<{ question_id: string; selected_options: AnswerKey[] }> = [];
  for (const q of questions) {
    const key = answers[q.id];
    if (!key) continue;
    const serverId = uiToServer.get(q.id);
    if (!serverId) continue;
    out.push({ question_id: serverId, selected_options: [key] });
  }
  return out;
}

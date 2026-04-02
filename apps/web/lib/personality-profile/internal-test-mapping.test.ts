import { describe, expect, it } from "vitest";
import { PERSONALITY_QUESTIONS } from "./questions";
import {
  buildInternalTestAnswerPayload,
  buildPersonalityQuestionMappings,
  INTERNAL_TEST_SYNC_ERRORS,
  mapServerAnswersToUiRecord,
} from "./internal-test-mapping";

describe("buildPersonalityQuestionMappings", () => {
  it("uses id-first mapping when server UUIDs match static UI ids", () => {
    const server = PERSONALITY_QUESTIONS.map((q) => ({
      id: q.id,
      display_order: q.index * 999,
      question_type: "single_choice" as const,
    }));
    const m = buildPersonalityQuestionMappings(PERSONALITY_QUESTIONS, server);
    expect(m.ok).toBe(true);
    if (!m.ok) return;
    expect(m.uiToServer.get(PERSONALITY_QUESTIONS[0]!.id)).toBe(PERSONALITY_QUESTIONS[0]!.id);
  });

  it("maps by display_order when server uses different UUIDs than static UI ids", () => {
    const server = PERSONALITY_QUESTIONS.map((q, i) => ({
      id: `aaaaaaaa-aaaa-4000-8000-${String(i + 1).padStart(12, "0")}`,
      display_order: (i + 1) * 10,
      question_type: "single_choice" as const,
    }));
    const m = buildPersonalityQuestionMappings(PERSONALITY_QUESTIONS, server);
    expect(m.ok).toBe(true);
    if (!m.ok) return;
    expect(m.uiToServer.get(PERSONALITY_QUESTIONS[0]!.id)).toBe(server[0]!.id);
    expect(m.serverToUi.get(server[0]!.id)).toBe(PERSONALITY_QUESTIONS[0]!.id);
  });

  it("fails when server count differs from UI with explicit count message", () => {
    const server = [
      {
        id: "aaaaaaaa-aaaa-4000-8000-000000000001",
        display_order: 10,
        question_type: "single_choice",
      },
    ];
    const m = buildPersonalityQuestionMappings(PERSONALITY_QUESTIONS, server);
    expect(m.ok).toBe(false);
    if (m.ok) return;
    expect(m.error).toContain("на сервере 1 вопросов");
  });

  it("fails when server list is empty with empty message", () => {
    const m = buildPersonalityQuestionMappings(PERSONALITY_QUESTIONS, []);
    expect(m.ok).toBe(false);
    if (m.ok) return;
    expect(m.error).toBe(INTERNAL_TEST_SYNC_ERRORS.empty);
  });

  it("fails when server has non-choice question_type", () => {
    const server = PERSONALITY_QUESTIONS.map((q, i) => ({
      id: `aaaaaaaa-aaaa-4000-8000-${String(i + 1).padStart(12, "0")}`,
      display_order: (i + 1) * 10,
      question_type: i === 0 ? "text" : "single_choice",
    }));
    const m = buildPersonalityQuestionMappings(PERSONALITY_QUESTIONS, server);
    expect(m.ok).toBe(false);
    if (m.ok) return;
    expect(m.error).toBe(INTERNAL_TEST_SYNC_ERRORS.wrongType);
  });
});

describe("mapServerAnswersToUiRecord", () => {
  it("maps saved answers from server ids to ui ids", () => {
    const server = PERSONALITY_QUESTIONS.map((q, i) => ({
      id: `bbbbbbbb-bbbb-4000-8000-${String(i + 1).padStart(12, "0")}`,
      display_order: (i + 1) * 10,
      question_type: "single_choice" as const,
    }));
    const m = buildPersonalityQuestionMappings(PERSONALITY_QUESTIONS, server);
    expect(m.ok).toBe(true);
    if (!m.ok) return;
    const ui = mapServerAnswersToUiRecord(m.serverToUi, [
      { question_id: server[0]!.id, selected_options: ["B"] },
    ]);
    expect(ui[PERSONALITY_QUESTIONS[0]!.id]).toBe("B");
  });
});

describe("buildInternalTestAnswerPayload", () => {
  it("uses server question_id in POST payload", () => {
    const server = PERSONALITY_QUESTIONS.map((q, i) => ({
      id: `cccccccc-cccc-4000-8000-${String(i + 1).padStart(12, "0")}`,
      display_order: (i + 1) * 10,
      question_type: "single_choice" as const,
    }));
    const m = buildPersonalityQuestionMappings(PERSONALITY_QUESTIONS, server);
    expect(m.ok).toBe(true);
    if (!m.ok) return;
    const answers = { [PERSONALITY_QUESTIONS[0]!.id]: "A" as const };
    const payload = buildInternalTestAnswerPayload(PERSONALITY_QUESTIONS, answers, m.uiToServer);
    expect(payload).toHaveLength(1);
    expect(payload[0]!.question_id).toBe(server[0]!.id);
    expect(payload[0]!.selected_options).toEqual(["A"]);
  });
});

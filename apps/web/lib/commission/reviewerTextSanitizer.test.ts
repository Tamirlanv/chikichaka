import { describe, expect, it } from "vitest";

import { sanitizeReviewerExplanation } from "./reviewerTextSanitizer";

describe("sanitizeReviewerExplanation", () => {
  it("removes technical english residue", () => {
    const raw =
      "The applicant's materials include responses to five questions. Data unavailable. " +
      "pipeline payload contains heuristics and q1 markers.";
    expect(sanitizeReviewerExplanation(raw)).toBe("");
  });

  it("keeps russian reviewer-friendly explanation", () => {
    const raw =
      "Инициативность: кандидат самостоятельно запустил проект OKU. " +
      "Устойчивость: преодолел внутренний барьер и продолжил работу.";
    const out = sanitizeReviewerExplanation(raw);
    expect(out).toContain("Инициативность");
    expect(out).toContain("Устойчивость");
    expect(out).not.toContain("payload");
  });

  it("preserves structured path intro and aspect lines", () => {
    const raw = [
      "Для раздела «Путь» рассчитаны рекомендованные баллы:",
      "«Инициативность» — 3",
      "«Устойчивость» — 3",
      "«Рефлексия и рост» — 3",
      "",
      "Инициативность: Кандидат показывает инициативу в действиях.",
    ].join("\n");
    const out = sanitizeReviewerExplanation(raw);
    expect(out).toContain("Для раздела «Путь» рассчитаны рекомендованные баллы:");
    expect(out).toContain("«Инициативность» — 3");
    expect(out).toContain("«Устойчивость» — 3");
    expect(out).toContain("«Рефлексия и рост» — 3");
    expect(out).not.toContain("«Рефлексия...");
  });
});

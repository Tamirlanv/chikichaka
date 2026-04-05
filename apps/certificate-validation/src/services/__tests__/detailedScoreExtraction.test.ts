import { describe, expect, it } from "vitest";

import {
  extractEntDetailed,
  extractIeltsDetailed,
  extractScoreForDocumentType,
} from "../extraction/detailedScoreExtraction.js";

describe("detailedScoreExtraction", () => {
  it("returns method for IELTS overall band score", () => {
    const d = extractIeltsDetailed("Overall Band Score: 6.5");
    expect(d.score).toBe(6.5);
    expect(d.method).toBe("ielts:overall_band_score_line");
    expect(d.targetFieldFound).toBe(true);
    expect(d.targetFieldType).toBe("ielts_overall_band");
    expect(d.extractionConfidenceTier).toBe("high");
  });

  it("does not derive IELTS score from section-only values", () => {
    const d = extractIeltsDetailed("Listening 7.0 Reading 6.0 Writing 5.5 Speaking 6.0");
    expect(d.score).toBeNull();
    expect(d.method).toBe("ielts:target_field_missing");
    expect(d.targetFieldFound).toBe(false);
  });

  it("extractScoreForDocumentType skips unknown", () => {
    const d = extractScoreForDocumentType("anything", "unknown");
    expect(d.score).toBeNull();
    expect(d.method).toBe("skipped_unknown_type");
  });

  it("extracts ENT using target-field context and ignores unrelated numbers", () => {
    const text = `
      Серия ST СЕРТИФИКАТ 2089899
      candidate id 702901
      В том числе: математика 25 баллов, физика 25 баллов
      ҚОРЫТЫНДЫ БАЛЛ 100
      КТ - 98
    `;
    const d = extractEntDetailed(text);
    expect(d.score).toBe(100);
    expect(d.targetFieldFound).toBe(true);
    expect(d.targetFieldType).toBe("ent_total_score");
    expect(d.method).toContain("ent:");
    expect(["high", "medium", "low"]).toContain(d.extractionConfidenceTier);
  });
});

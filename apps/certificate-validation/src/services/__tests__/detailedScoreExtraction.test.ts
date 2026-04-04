import { describe, expect, it } from "vitest";

import { extractIeltsDetailed, extractScoreForDocumentType } from "../extraction/detailedScoreExtraction.js";

describe("detailedScoreExtraction", () => {
  it("returns method for IELTS overall band score", () => {
    const d = extractIeltsDetailed("Overall Band Score: 6.5");
    expect(d.score).toBe(6.5);
    expect(d.method).toContain("ielts:");
  });

  it("extractScoreForDocumentType skips unknown", () => {
    const d = extractScoreForDocumentType("anything", "unknown");
    expect(d.score).toBeNull();
    expect(d.method).toBe("skipped_unknown_type");
  });
});

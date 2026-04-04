import { describe, expect, it } from "vitest";

import { mapDeclarationToDocumentType, mergeDocumentType } from "../classification/mergeDocumentType.js";

describe("mapDeclarationToDocumentType", () => {
  it("maps english proof kinds", () => {
    expect(
      mapDeclarationToDocumentType({
        englishProofKind: "ielts_6",
        certificateProofKind: null,
        documentRole: "english"
      })
    ).toBe("ielts");
    expect(
      mapDeclarationToDocumentType({
        englishProofKind: "toefl_60_78",
        certificateProofKind: null,
        documentRole: "english"
      })
    ).toBe("toefl");
  });

  it("maps certificate proof kinds", () => {
    expect(
      mapDeclarationToDocumentType({
        englishProofKind: null,
        certificateProofKind: "ent",
        documentRole: "certificate"
      })
    ).toBe("ent");
    expect(
      mapDeclarationToDocumentType({
        englishProofKind: null,
        certificateProofKind: "nis_12",
        documentRole: "certificate"
      })
    ).toBe("nis_12");
  });
});

describe("mergeDocumentType", () => {
  it("uses OCR when no declaration", () => {
    expect(mergeDocumentType("ielts", null).resolved).toBe("ielts");
  });

  it("uses declaration when OCR unknown", () => {
    const m = mergeDocumentType("unknown", "toefl");
    expect(m.resolved).toBe("toefl");
    expect(m.mismatch).toBe(false);
  });

  it("flags cross-family mismatch", () => {
    const m = mergeDocumentType("ielts", "toefl");
    expect(m.resolved).toBe("toefl");
    expect(m.mismatch).toBe(true);
  });
});

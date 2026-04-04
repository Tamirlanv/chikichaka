import type { DocumentType } from "../types.js";

/** Map education form kinds to document type for the current attachment slot. */
export function mapDeclarationToDocumentType(input: {
  englishProofKind?: string | null;
  certificateProofKind?: string | null;
  documentRole: "english" | "certificate" | "additional";
}): DocumentType | null {
  if (input.documentRole === "english") {
    if (input.englishProofKind === "ielts_6") return "ielts";
    if (input.englishProofKind === "toefl_60_78") return "toefl";
    return null;
  }
  if (input.documentRole === "certificate") {
    if (input.certificateProofKind === "ent") return "ent";
    if (input.certificateProofKind === "nis_12") return "nis_12";
    return null;
  }
  return null;
}

/**
 * OCR-first when no declaration; otherwise prefer declaration for extraction,
 * with warnings on strong disagreement.
 */
export function mergeDocumentType(
  ocrType: DocumentType,
  expected: DocumentType | null
): { resolved: DocumentType; warnings: string[]; mismatch: boolean } {
  if (!expected || expected === "unknown") {
    return { resolved: ocrType, warnings: [], mismatch: false };
  }
  if (ocrType === "unknown") {
    return {
      resolved: expected,
      warnings: ["OCR could not classify document type; using declared type for extraction."],
      mismatch: false
    };
  }
  if (ocrType === expected) {
    return { resolved: expected, warnings: [], mismatch: false };
  }

  const crossFamily =
    (ocrType === "ielts" && expected === "toefl") ||
    (ocrType === "toefl" && expected === "ielts") ||
    (ocrType === "ent" && expected === "nis_12") ||
    (ocrType === "nis_12" && expected === "ent");

  if (crossFamily) {
    return {
      resolved: expected,
      warnings: [
        `Declaration expects ${expected} but OCR suggests ${ocrType}; using declaration for extraction; threshold should be reviewed manually.`
      ],
      mismatch: true
    };
  }

  return {
    resolved: expected,
    warnings: [`OCR classified as ${ocrType} but declaration specifies ${expected}; using declaration for extraction.`],
    mismatch: true
  };
}

import type { DocumentType } from "../types.js";

/** Reject obviously wrong numbers from OCR noise. */
export function validatePlausibleScore(
  documentType: DocumentType,
  score: number
): { ok: boolean; reason?: string } {
  if (documentType === "unknown") {
    return { ok: false, reason: "document_type_unknown" };
  }
  if (documentType === "ielts") {
    if (score < 4 || score > 9) {
      return { ok: false, reason: "ielts_band_outside_4_9" };
    }
    return { ok: true };
  }
  if (documentType === "toefl") {
    if (!Number.isFinite(score) || Math.floor(score) !== score) {
      return { ok: false, reason: "toefl_total_must_be_integer" };
    }
    if (score < 0 || score > 120) {
      return { ok: false, reason: "toefl_total_outside_0_120" };
    }
    return { ok: true };
  }
  if (documentType === "ent" || documentType === "nis_12") {
    if (score < 0 || score > 140) {
      return { ok: false, reason: "aggregate_score_outside_0_140" };
    }
    return { ok: true };
  }
  return { ok: true };
}

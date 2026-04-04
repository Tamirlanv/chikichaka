import { env } from "../../config/env.js";
import type { DocumentType } from "../types.js";

export function evaluateThresholds(
  documentType: DocumentType,
  score: number | null,
  opts?: { declarationMismatch?: boolean }
): {
  ieltsMinPassed?: boolean | null;
  entScoreDetected?: boolean | null;
  toeflMinPassed?: boolean | null;
} {
  const mismatch = opts?.declarationMismatch ?? false;

  if (documentType === "ielts") {
    if (mismatch) return { ieltsMinPassed: null };
    return { ieltsMinPassed: score === null ? null : score >= 6.0 };
  }
  if (documentType === "toefl") {
    if (mismatch) return { toeflMinPassed: null };
    return { toeflMinPassed: score === null ? null : score >= env.TOEFL_THRESHOLD };
  }
  if (documentType === "ent" || documentType === "nis_12") {
    return { entScoreDetected: score !== null };
  }
  return {};
}

export function computePassedThreshold(
  documentType: DocumentType,
  score: number | null,
  declarationMismatch: boolean
): { passed: boolean | null; thresholdType: "ielts" | "toefl" | null } {
  if (documentType !== "ielts" && documentType !== "toefl") {
    return { passed: null, thresholdType: null };
  }
  if (declarationMismatch || score === null) {
    return { passed: null, thresholdType: documentType };
  }
  if (documentType === "ielts") {
    return { passed: score >= 6.0, thresholdType: "ielts" };
  }
  return { passed: score >= env.TOEFL_THRESHOLD, thresholdType: "toefl" };
}

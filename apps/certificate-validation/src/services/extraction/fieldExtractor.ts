import type { DocumentType } from "../types.js";
import { extractScoreForDocumentType } from "./detailedScoreExtraction.js";

export function extractFields(
  text: string,
  documentType: DocumentType
): {
  candidateName?: string | null;
  certificateNumber?: string | null;
  examDate?: string | null;
  totalScore?: number | null;
  scoreLabel?: string | null;
  extractionMethod?: string | null;
  targetFieldFound?: boolean;
  targetFieldType?: string | null;
  targetFieldEvidence?: string | null;
} {
  const certificateNumber =
    text.match(/\b(?:candidate\s*no|certificate\s*no|reg(?:istration)?\s*no)[:\s]*([A-Z0-9-]{5,})/i)?.[1] ?? null;
  const examDate = text.match(/\b(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4})\b/)?.[1] ?? null;

  const detail = extractScoreForDocumentType(text, documentType);
  let totalScore: number | null = detail.score;
  let scoreLabel: string | null = null;
  const extractionMethod = detail.method;
  const targetFieldFound = detail.targetFieldFound;
  const targetFieldType = detail.targetFieldType;
  const targetFieldEvidence = detail.targetFieldEvidence;

  if (documentType === "ielts") {
    scoreLabel = totalScore != null ? "overall band score" : null;
  } else if (documentType === "toefl") {
    scoreLabel = totalScore != null ? "total score" : null;
  } else if (documentType === "ent") {
    scoreLabel = totalScore != null ? "итоговый балл (ЕНТ)" : null;
  } else if (documentType === "nis_12") {
    scoreLabel = totalScore != null ? "итоговый балл (NIS)" : null;
  }

  return {
    candidateName: null,
    certificateNumber,
    examDate,
    totalScore,
    scoreLabel,
    extractionMethod,
    targetFieldFound,
    targetFieldType,
    targetFieldEvidence,
  };
}

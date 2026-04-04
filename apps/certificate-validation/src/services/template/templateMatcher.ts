import type { DocumentType, TemplateMatchResult } from "../types.js";

const REQUIRED_ANCHORS: Record<DocumentType, string[]> = {
  ielts: ["ielts", "overall", "band"],
  toefl: ["toefl", "score"],
  ent: ["балл", "ент"],
  nis_12: ["балл", "ниш"],
  unknown: []
};

export function matchTemplate(text: string, type: DocumentType): TemplateMatchResult {
  const anchors = REQUIRED_ANCHORS[type] ?? [];
  if (!anchors.length) return { score: 0, anchorsFound: [], missingAnchors: [] };
  const lower = text.toLowerCase();
  const anchorsFound = anchors.filter((a) => lower.includes(a.toLowerCase()));
  const missingAnchors = anchors.filter((a) => !lower.includes(a.toLowerCase()));
  const score = Number((anchorsFound.length / anchors.length).toFixed(3));
  return { score, anchorsFound, missingAnchors };
}

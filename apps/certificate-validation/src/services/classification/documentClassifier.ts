import type { DocumentType } from "../types.js";

function isBandLike(n: number): boolean {
  return n >= 4 && n <= 9 && (Number.isInteger(n * 2) || Number.isInteger(n));
}

/** Heuristic scores; pick highest compatible type. */
export function classifyDocumentType(text: string): DocumentType {
  const t = text.toLowerCase();
  const scores: Record<Exclude<DocumentType, "unknown">, number> = {
    ielts: 0,
    toefl: 0,
    ent: 0,
    nis_12: 0
  };

  if (t.includes("ielts")) scores.ielts += 4;
  if (t.includes("test report form") || t.includes("trf")) scores.ielts += 3;
  if (/overall\s*band|band\s*score/i.test(t)) scores.ielts += 3;
  if (t.includes("british council") || t.includes("idp")) scores.ielts += 1;

  const bandMatch = t.match(/overall[^\d]{0,40}([0-9](?:\.[0-9])?)/i);
  if (bandMatch) {
    const v = Number(bandMatch[1]);
    if (isBandLike(v)) scores.ielts += 2;
  }

  if (t.includes("toefl")) scores.toefl += 4;
  if (t.includes("ets")) scores.toefl += 2;
  if (/\bibt\b|internet-based|internet based/i.test(t)) scores.toefl += 2;
  if (/total\s*score/i.test(t)) scores.toefl += 2;

  if (/ент\b|единое национальное|national testing|uac|тестирования/i.test(t)) scores.ent += 4;
  if (/серия\s*st|сертификат\s*[-*]?\s*\d{4,}/i.test(t)) scores.ent += 2;
  if (/кт\s*[-:]\s*\d{2,3}/i.test(t)) scores.ent += 2;
  if (/баллов в том числе|жалпы\s*бал/i.test(t)) scores.ent += 1;
  if (t.includes("итоговый балл") || t.includes("қорытынды")) {
    scores.ent += 1;
    scores.nis_12 += 1;
  }

  if (/nazarbayev|nazarbayev intellectual|ниш\b|nis\b|intellectual schools/i.test(t)) scores.nis_12 += 5;
  if (/12\s*(th)?\s*grade|twelfth grade|аттестат/i.test(t)) scores.nis_12 += 1;
  if (/\bент\b|єнт/i.test(t)) scores.ent += 2;

  const entries = Object.entries(scores) as [Exclude<DocumentType, "unknown">, number][];
  entries.sort((a, b) => b[1] - a[1]);
  const [best, bestScore] = entries[0]!;

  if (bestScore < 3) return "unknown";

  const second = entries[1]![1];
  if (bestScore === second && bestScore >= 3) {
    if (scores.ielts === scores.toefl && scores.ielts >= 3) return "unknown";
    if (scores.ent === scores.nis_12 && scores.ent >= 3) return "unknown";
  }

  return best;
}

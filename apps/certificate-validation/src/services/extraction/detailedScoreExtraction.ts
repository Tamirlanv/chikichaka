/**
 * Type-specific score extraction with explicit method labels for explainability.
 */

import type { DocumentType } from "../types.js";

export type TargetFieldType =
  | "ielts_overall_band"
  | "toefl_total_score"
  | "ent_total_score"
  | "nis_total_score"
  | null;

export type DetailedScore = {
  score: number | null;
  method: string;
  targetFieldFound: boolean;
  targetFieldType: TargetFieldType;
  targetFieldEvidence: string | null;
  extractionConfidenceTier: "high" | "medium" | "low" | null;
};

function clampIeltsBand(n: number): boolean {
  return n >= 4 && n <= 9;
}

function isHalfBand(n: number): boolean {
  const x = Math.round(n * 10) / 10;
  return Number.isInteger(x * 2);
}

function toAsciiScoreToken(token: string): string {
  return token.replace(",", ".").replace(/\s+/g, "");
}

function compactOneLine(text: string): string {
  return text
    .replace(/\r\n/g, "\n")
    .replace(/\u00A0/g, " ")
    .replace(/[“”«»]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function buildFound(
  score: number,
  method: string,
  targetFieldType: Exclude<TargetFieldType, null>,
  targetFieldEvidence: string,
): DetailedScore {
  return {
    score,
    method,
    targetFieldFound: true,
    targetFieldType,
    targetFieldEvidence,
    extractionConfidenceTier: "medium",
  };
}

function buildMissing(
  method: string,
  targetFieldType: Exclude<TargetFieldType, null>,
): DetailedScore {
  return {
    score: null,
    method,
    targetFieldFound: false,
    targetFieldType,
    targetFieldEvidence: null,
    extractionConfidenceTier: null,
  };
}

/** Fix common OCR line breaks inside band scores (e.g. "6" + newline + ".0"). */
function normalizeIeltsOcrLayout(text: string): string {
  let t = text.replace(/\r\n/g, "\n");
  t = t.replace(/([456789])\s*\n\s*\.([05])\b/g, "$1.$2");
  t = t.replace(/([456789])\s+([.,])\s*([05])\b/g, "$1.$3");
  t = t.replace(/overall\s*\n\s*band/gi, "overall band");
  return t;
}

function ieltsScoreFromToken(token: string): number | null {
  const n = Number(toAsciiScoreToken(token));
  if (!Number.isFinite(n)) return null;
  if (!clampIeltsBand(n) || !isHalfBand(n)) return null;
  return Number(n.toFixed(1));
}

export function extractIeltsDetailed(text: string): DetailedScore {
  const normalized = normalizeIeltsOcrLayout(text);
  const oneLine = compactOneLine(normalized);
  const patterns: { re: RegExp; method: string }[] = [
    {
      re: /overall\s*band\s*score[^\d]{0,24}(?<!\d)([456789](?:[.,][05])?)(?!\d)/gi,
      method: "ielts:overall_band_score_line",
    },
    {
      re: /overall\s*band[^\d]{0,24}(?<!\d)([456789](?:[.,][05])?)(?!\d)/gi,
      method: "ielts:overall_band_line",
    },
    {
      re: /overall[\s\S]{0,180}?band[^\d]{0,32}(?<!\d)([456789](?:[.,][05])?)(?!\d)/gi,
      method: "ielts:overall_near_band_line",
    },
    {
      re: /overall[\s\S]{0,180}?(?<!\d)([456789](?:[.,][05])?)(?!\d)[^\d]{0,24}band/gi,
      method: "ielts:overall_number_before_band",
    },
    {
      re: /test\s*results[\s\S]{0,220}?overall[\s\S]{0,120}?(?<!\d)([456789](?:[.,][05])?)(?!\d)/gi,
      method: "ielts:test_results_overall_window",
    },
  ];

  for (const { re, method } of patterns) {
    const regex = new RegExp(re.source, re.flags);
    let match: RegExpExecArray | null;
    while ((match = regex.exec(oneLine)) !== null) {
      const score = ieltsScoreFromToken(match[1] ?? "");
      if (score == null) continue;
      const evidence = oneLine.slice(Math.max(0, match.index - 30), Math.min(oneLine.length, match.index + 120));
      const out = buildFound(score, method, "ielts_overall_band", evidence);
      out.extractionConfidenceTier =
        method === "ielts:overall_band_score_line" || method === "ielts:overall_band_line" ? "high" : "medium";
      return out;
    }
  }

  const lines = normalized
    .split(/\n+/)
    .map((line) => line.trim())
    .filter(Boolean);
  for (const line of lines) {
    if (!/overall/i.test(line) || !/band/i.test(line)) continue;
    const trailing = line.match(/([456789](?:[.,][05])?)\s*$/);
    const score = trailing ? ieltsScoreFromToken(trailing[1] ?? "") : null;
    if (score != null) {
      const out = buildFound(score, "ielts:overall_line_trailing_number", "ielts_overall_band", line.slice(0, 180));
      out.extractionConfidenceTier = "medium";
      return out;
    }
  }

  return buildMissing("ielts:target_field_missing", "ielts_overall_band");
}

export function extractToeflDetailed(text: string): DetailedScore {
  const patterns: { re: RegExp; method: string }[] = [
    { re: /total\s*score\s*[:\s#]*([0-9]{2,3})\b/gi, method: "toefl:total_score_line" },
    { re: /my\s*total\s*(?:test\s*)?score\s*[:\s#]*([0-9]{2,3})\b/gi, method: "toefl:my_total_score_line" },
    { re: /\btotal\s*:\s*([0-9]{2,3})\b/gi, method: "toefl:total_colon_line" }
  ];
  const candidates: { v: number; method: string; i: number }[] = [];
  for (const { re, method } of patterns) {
    let m: RegExpExecArray | null;
    const r = new RegExp(re.source, re.flags);
    while ((m = r.exec(text)) !== null) {
      const v = Number(m[1]);
      if (v >= 0 && v <= 120) candidates.push({ v, method, i: m.index });
    }
  }
  if (candidates.length) {
    const best = candidates.reduce((a, b) => (a.v >= b.v ? a : b));
    const evidence = text.slice(Math.max(0, best.i - 24), Math.min(text.length, best.i + 80)).replace(/\s+/g, " ");
    const out = buildFound(best.v, best.method, "toefl_total_score", evidence);
    out.extractionConfidenceTier = best.method === "toefl:total_score_line" ? "high" : "medium";
    return out;
  }

  const readingBlock = text.match(/reading[^\n]{0,40}([0-9]{1,3})/i);
  const listeningBlock = text.match(/listening[^\n]{0,40}([0-9]{1,3})/i);
  if (readingBlock && listeningBlock) {
    const r = Number(readingBlock[1]);
    const l = Number(listeningBlock[1]);
    const tl = text.toLowerCase();
    if (r <= 30 && l <= 30 && (tl.includes("toefl") || tl.includes("ets"))) {
      const m3 = text.match(/\b([8-9][0-9]|1[0-1][0-9]|120)\b/);
      if (m3) {
        const v = Number(m3[1]);
        if (v >= 60 && v <= 120) {
          const idx = m3.index ?? 0;
          const evidence = text.slice(Math.max(0, idx - 24), Math.min(text.length, idx + 80)).replace(/\s+/g, " ");
          const out = buildFound(v, "toefl:weak_from_section_scores_context", "toefl_total_score", evidence);
          out.extractionConfidenceTier = "low";
          return out;
        }
      }
    }
  }
  return buildMissing("toefl:target_field_missing", "toefl_total_score");
}

type RankedCandidate = {
  v: number;
  i: number;
  method: string;
  evidence: string;
  rank: number;
};

function contextWindow(text: string, index: number, around = 90): string {
  return text.slice(Math.max(0, index - around), Math.min(text.length, index + around));
}

function rankEntCandidate(text: string, value: number, index: number): number {
  const ctx = contextWindow(text, index, 110);
  const hasResultAnchor = /(итог|қорыт|корыт|жалпы|общ)/i.test(ctx);
  const hasScoreAnchor = /(балл|баллов|ұпай|упай|score)/i.test(ctx);
  const hasEntMarker = /(?:\bент\b|\bкт\b|uac|тест)/i.test(ctx);
  const hasAnti = /(candidate|серия|номер|рег(истрац|\.?)|certificate\s*no|дата|date|год|жыл|№)/i.test(ctx);
  const hasSection = /(в том числе|ішінде|матем|физ|хим|биол|истор|геог|reading|listening|writing|speaking)/i.test(ctx);
  const hasFinalHeader = /(итогов\w*\s*балл|қорытынды\s*балл|жалпы\s*балл|общ(?:ий|ая|ее)\s*балл)/i.test(ctx);

  let rank = 0;
  if (hasFinalHeader) rank += 9;
  if (hasResultAnchor) rank += 7;
  if (hasScoreAnchor) rank += 5;
  if (hasResultAnchor && hasScoreAnchor) rank += 6;
  if (hasEntMarker) rank += 3;
  if (/(из\s*200|\/\s*200|200\s*бал)/i.test(ctx)) rank += 2;
  if (value >= 90 && value <= 130) rank += 1;
  if (value === 100) rank += 3;
  if (hasAnti) rank -= 8;
  if (hasSection) rank -= 7;
  if (hasSection && !hasFinalHeader) rank -= 3;
  if (hasAnti && !hasFinalHeader) rank -= 3;
  if (/кт\s*[-:—]?\s*[0-9]{2,3}/i.test(ctx)) rank += 1;
  return rank;
}

function extractKazakhDetailed(text: string, kind: "ent" | "nis_12"): DetailedScore {
  const normalized = compactOneLine(text.toLowerCase());
  const candidates: RankedCandidate[] = [];
  const minAllowed = kind === "ent" ? 50 : 0;
  const maxAllowed = 140;

  const anchored: { re: RegExp; method: string; boost: number }[] = [
    {
      re: /(?:итоговый|қорытынды|корытынды|итог|жалпы|общ(?:ий|ая|ее)?)\s*(?:балл|ұпай|упай)?[^\d]{0,32}([0-9]{2,3})\b/gi,
      method: `${kind}:target_anchor_number`,
      boost: 9,
    },
    {
      re: /(?:балл|баллов|ұпай|упай|score)[^\d]{0,20}([0-9]{2,3})\b/gi,
      method: `${kind}:score_anchor_number`,
      boost: 4,
    },
    {
      re: /(?:кт|ент|uac)[^\d]{0,12}([0-9]{2,3})\b/gi,
      method: `${kind}:ent_marker_number`,
      boost: 3,
    },
  ];
  for (const { re, method, boost } of anchored) {
    const regex = new RegExp(re.source, re.flags);
    let match: RegExpExecArray | null;
    while ((match = regex.exec(normalized)) !== null) {
      const raw = match[1] ?? "";
      const v = Number(raw);
      if (!Number.isFinite(v) || v < minAllowed || v > maxAllowed) continue;
      const i = match.index + match[0].lastIndexOf(raw);
      const evidence = contextWindow(normalized, i, 120);
      candidates.push({
        v,
        i,
        method,
        evidence,
        rank: rankEntCandidate(normalized, v, i) + boost,
      });
    }
  }

  const direct = /\b([0-9]{2,3})\b/g;
  let dm: RegExpExecArray | null;
  while ((dm = direct.exec(normalized)) !== null) {
    const v = Number(dm[1]);
    if (!Number.isFinite(v) || v < minAllowed || v > maxAllowed) continue;
    const i = dm.index;
    const evidence = contextWindow(normalized, i, 120);
    candidates.push({
      v,
      i,
      method: `${kind}:context_ranked_digits`,
      evidence,
      rank: rankEntCandidate(normalized, v, i),
    });
  }

  const spaced = /(?<!\d)([0-9])\s+([0-9])\s+([0-9])(?!\d)/g;
  let sm: RegExpExecArray | null;
  while ((sm = spaced.exec(normalized)) !== null) {
    const token = `${sm[1]}${sm[2]}${sm[3]}`;
    const v = Number(token);
    if (!Number.isFinite(v) || v < minAllowed || v > maxAllowed) continue;
    const i = sm.index;
    const evidence = contextWindow(normalized, i, 120);
    candidates.push({
      v,
      i,
      method: `${kind}:spaced_digits_target_context`,
      evidence,
      rank: rankEntCandidate(normalized, v, i) + 4,
    });
  }

  if (kind === "ent") {
    const lettersAsDigits = normalized.match(
      /(?:итог|қорыт|жалпы|общ|балл|ұпай)[^\d]{0,32}1\s*0\s*0\b/,
    );
    if (lettersAsDigits) {
      const i = lettersAsDigits.index ?? 0;
      const evidence = contextWindow(normalized, i, 120);
      candidates.push({
        v: 100,
        i,
        method: "ent:target_anchor_spaced_100",
        evidence,
        rank: rankEntCandidate(normalized, 100, i) + 8,
      });
    }
  } else if (/nazarbayev|intellectual schools|ниш/.test(normalized)) {
    const m2 = normalized.match(/([0-9]{2,3})\s*(?:балл|points|score)/);
    if (m2) {
      const v = Number(m2[1]);
      if (v >= minAllowed && v <= maxAllowed) {
        const i = m2.index ?? 0;
        const evidence = contextWindow(normalized, i, 120);
        candidates.push({
          v,
          i,
          method: "nis_12:nis_keyword_near_score",
          evidence,
          rank: 10,
        });
      }
    }
  }

  if (candidates.length > 0) {
    candidates.sort((a, b) => b.rank - a.rank || b.v - a.v);
    const best = candidates[0];
    const minRank = kind === "ent" ? 8 : 6;
    if (best.rank >= minRank) {
      const out = buildFound(
        best.v,
        `${best.method}:ranked`,
        kind === "ent" ? "ent_total_score" : "nis_total_score",
        best.evidence,
      );
      if (best.rank >= 14) out.extractionConfidenceTier = "high";
      else if (best.rank >= 10) out.extractionConfidenceTier = "medium";
      else out.extractionConfidenceTier = "low";
      return out;
    }
  }

  return buildMissing(`${kind}:target_field_missing`, kind === "ent" ? "ent_total_score" : "nis_total_score");
}

export function extractEntDetailed(text: string): DetailedScore {
  return extractKazakhDetailed(text, "ent");
}

export function extractNisDetailed(text: string): DetailedScore {
  return extractKazakhDetailed(text, "nis_12");
}

export function extractScoreForDocumentType(text: string, documentType: DocumentType): DetailedScore {
  switch (documentType) {
    case "ielts":
      return extractIeltsDetailed(text);
    case "toefl":
      return extractToeflDetailed(text);
    case "ent":
      return extractEntDetailed(text);
    case "nis_12":
      return extractNisDetailed(text);
    default:
      return {
        score: null,
        method: "skipped_unknown_type",
        targetFieldFound: false,
        targetFieldType: null,
        targetFieldEvidence: null,
        extractionConfidenceTier: null,
      };
  }
}

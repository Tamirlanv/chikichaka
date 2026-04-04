/**
 * Type-specific score extraction with explicit method labels for explainability.
 */

import type { DocumentType } from "../types.js";

export type DetailedScore = {
  score: number | null;
  method: string;
};

function clampIeltsBand(n: number): boolean {
  return n >= 4 && n <= 9;
}

function isHalfBand(n: number): boolean {
  const x = Math.round(n * 10) / 10;
  return Number.isInteger(x * 2);
}

export function extractIeltsDetailed(text: string): DetailedScore {
  const candidates: { v: number; method: string }[] = [];

  const patterns: { re: RegExp; method: string }[] = [
    { re: /overall\s*band\s*score\s*[:\s#]*([0-9](?:\.[0-9])?)/gi, method: "ielts:overall_band_score_line" },
    { re: /overall\s*band\s*[:\s#]*([0-9](?:\.[0-9])?)/gi, method: "ielts:overall_band_line" },
    { re: /band\s*score\s*[:\s#]*([0-9](?:\.[0-9])?)/gi, method: "ielts:band_score_line" }
  ];
  for (const { re, method } of patterns) {
    let m: RegExpExecArray | null;
    const r = new RegExp(re.source, re.flags);
    while ((m = r.exec(text)) !== null) {
      const v = Number(m[1]);
      if (clampIeltsBand(v) && isHalfBand(v)) candidates.push({ v, method });
    }
  }

  const overallLine = text.match(/overall[^\n]{0,120}/i);
  if (overallLine) {
    const m2 = overallLine[0].match(/([0-9](?:\.[0-9])?)\s*$/);
    if (m2) {
      const v = Number(m2[1]);
      if (clampIeltsBand(v) && isHalfBand(v)) {
        candidates.push({ v, method: "ielts:overall_line_trailing_number" });
      }
    }
  }

  if (candidates.length) {
    const best = candidates.reduce((a, b) => (a.v >= b.v ? a : b));
    return { score: best.v, method: best.method };
  }

  const loose = text.match(/\bielts\b[^0-9]{0,200}?\b([0-9](?:\.[0-9])?)\b/i);
  if (loose) {
    const v = Number(loose[1]);
    if (clampIeltsBand(v) && isHalfBand(v)) {
      return { score: v, method: "ielts:loose_after_ielts_keyword" };
    }
  }
  return { score: null, method: "ielts:none" };
}

export function extractToeflDetailed(text: string): DetailedScore {
  const patterns: { re: RegExp; method: string }[] = [
    { re: /total\s*score\s*[:\s#]*([0-9]{2,3})\b/gi, method: "toefl:total_score_line" },
    { re: /my\s*total\s*(?:test\s*)?score\s*[:\s#]*([0-9]{2,3})\b/gi, method: "toefl:my_total_score_line" },
    { re: /\btotal\s*:\s*([0-9]{2,3})\b/gi, method: "toefl:total_colon_line" }
  ];
  const candidates: { v: number; method: string }[] = [];
  for (const { re, method } of patterns) {
    let m: RegExpExecArray | null;
    const r = new RegExp(re.source, re.flags);
    while ((m = r.exec(text)) !== null) {
      const v = Number(m[1]);
      if (v >= 0 && v <= 120) candidates.push({ v, method });
    }
  }
  if (candidates.length) {
    const best = candidates.reduce((a, b) => (a.v >= b.v ? a : b));
    return { score: best.v, method: best.method };
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
          return { score: v, method: "toefl:weak_from_section_scores_context" };
        }
      }
    }
  }
  return { score: null, method: "toefl:none" };
}

function extractKazakhDetailed(text: string, kind: "ent" | "nis_12"): DetailedScore {
  const low = text.toLowerCase();
  const candidates: { v: number; method: string }[] = [];

  const anchored: { re: RegExp; method: string }[] = [
    { re: /(?:итоговый|қорытынды|итог)\s*балл\s*[:\s]*([0-9]{2,3})\b/gi, method: `${kind}:итоговый_балл` },
    { re: /(?:total|overall)\s*score\s*[:\s]*([0-9]{2,3})\b/gi, method: `${kind}:total_score_line` },
    { re: /балл\s*[:\s]*([0-9]{2,3})\b/gi, method: `${kind}:балл_line_weak` }
  ];
  for (const { re, method } of anchored) {
    let m: RegExpExecArray | null;
    const r = new RegExp(re.source, re.flags);
    while ((m = r.exec(low)) !== null) {
      const v = Number(m[1]);
      if (v >= 0 && v <= 140) candidates.push({ v, method });
    }
  }

  if (kind === "ent") {
    const m = low.match(/(?:ент|uac|тестирования)[^\d]{0,50}([0-9]{2,3})\b/);
    if (m) {
      const v = Number(m[1]);
      if (v >= 50 && v <= 140) candidates.push({ v, method: "ent:ент_context" });
    }
  }
  if (kind === "nis_12") {
    if (/nazarbayev|intellectual schools|ниш/.test(low)) {
      const m2 = low.match(/([0-9]{2,3})\s*(?:балл|points|score)/);
      if (m2) {
        const v = Number(m2[1]);
        if (v >= 0 && v <= 140) candidates.push({ v, method: "nis_12:nis_keyword_near_score" });
      }
    }
  }

  if (candidates.length) {
    const best = candidates.reduce((a, b) => (a.v >= b.v ? a : b));
    return { score: best.v, method: best.method };
  }
  return { score: null, method: `${kind}:none` };
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
      return { score: null, method: "skipped_unknown_type" };
  }
}

/** Thin wrappers over detailed extraction — same behaviour as before refactor. */

import {
  extractEntDetailed,
  extractIeltsDetailed,
  extractNisDetailed,
  extractToeflDetailed
} from "./detailedScoreExtraction.js";

export function parseIeltsOverall(text: string): number | null {
  return extractIeltsDetailed(text).score;
}

export function parseToeflScore(text: string): number | null {
  return extractToeflDetailed(text).score;
}

export function parseEntScore(text: string): number | null {
  return extractEntDetailed(text).score;
}

export function parseNisScore(text: string): number | null {
  return extractNisDetailed(text).score;
}

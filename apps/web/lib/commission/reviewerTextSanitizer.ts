const TECH_PATTERNS: RegExp[] = [
  /\bq\d+\b/i,
  /data unavailable/i,
  /details unavailable/i,
  /submission includes responses/i,
  /\bspam_questions\b/i,
  /\bspam_check\b/i,
  /\bheuristics\b/i,
  /\baction_score\b/i,
  /\breflection_score\b/i,
  /\bjson\b/i,
  /\bpayload\b/i,
  /\bpipeline\b/i,
];

const ASPECT_SCORE_LINE = /^«[^»\n]+»\s*—\s*[1-5]$/u;
const PATH_INTRO_LINE = /^Для раздела «Путь» рассчитаны рекомендованные баллы:?$/u;

function stripTechnicalResidue(text: string): string {
  let cleaned = text.trim();
  cleaned = cleaned.replace(/^[\-\*\d\.\)\s]+/, "");
  for (const pattern of TECH_PATTERNS) cleaned = cleaned.replace(pattern, "");
  cleaned = cleaned.replaceAll("Данные недоступны", "");
  cleaned = cleaned.replaceAll("Детали недоступны", "");
  return cleaned.replace(/\s{2,}/g, " ").trim();
}

function splitSentences(text: string): string[] {
  const parts = text.split(/(?<=[.!?…])\s+/).map((s) => s.trim()).filter(Boolean);
  return parts.length ? parts : (text.trim() ? [text.trim()] : []);
}

function truncateSentence(text: string, limit: number): string {
  if (text.length <= limit) return text;
  const cut = text.slice(0, limit).trimEnd();
  const space = cut.lastIndexOf(" ");
  return `${(space > 0 ? cut.slice(0, space) : cut).trimEnd()}...`;
}

function sanitizeStructuredParagraph(paragraph: string): string {
  const lines = paragraph
    .split(/\n+/)
    .map((line) => stripTechnicalResidue(line))
    .map((line) => line.trim())
    .filter(Boolean);
  if (!lines.length) return "";

  const hasPathStructuredIntro = lines.some((line) => PATH_INTRO_LINE.test(line));
  const hasAspectScores = lines.some((line) => ASPECT_SCORE_LINE.test(line));
  if (!hasPathStructuredIntro && !hasAspectScores) return "";

  return lines.join("\n");
}

function isUiFriendlySentence(text: string): boolean {
  if (text.length < 14) return false;
  if (TECH_PATTERNS.some((p) => p.test(text))) return false;
  const cyr = (text.match(/[А-Яа-яЁё]/g) ?? []).length;
  const lat = (text.match(/[A-Za-z]/g) ?? []).length;
  if (cyr === 0) return false;
  if (lat > cyr) return false;
  return true;
}

export function sanitizeReviewerExplanation(text: string): string {
  const paragraphs = text
    .split(/\n{2,}/)
    .map((p) => p.trim())
    .filter(Boolean);

  const collected: string[] = [];
  for (const paragraph of paragraphs) {
    const structured = sanitizeStructuredParagraph(paragraph);
    if (structured) {
      collected.push(structured);
      continue;
    }

    const cleaned = stripTechnicalResidue(paragraph);
    const sentenceCandidates: string[] = [];
    for (const sentence of splitSentences(cleaned)) {
      const normalized = truncateSentence(stripTechnicalResidue(sentence), 220);
      if (isUiFriendlySentence(normalized)) sentenceCandidates.push(normalized);
    }
    if (sentenceCandidates.length) {
      collected.push(sentenceCandidates.join(" "));
    }
  }
  const deduped = [...new Set(collected.map((item) => item.replace(/[ \t]{2,}/g, " ").trim()))];
  if (!deduped.length) return "";
  return deduped
    .slice(0, 10)
    .map((paragraph) => truncateSentence(paragraph, 420))
    .join("\n\n");
}

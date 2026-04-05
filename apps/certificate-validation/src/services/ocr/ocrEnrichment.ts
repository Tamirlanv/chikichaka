import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

import sharp from "sharp";

import type { DocumentType } from "../types.js";
import { runTesseractStdout } from "./tesseractCli.js";

const MAX_CHUNK_CHARS = 4000;
const MAX_TOTAL_CHARS = 16000;

export type OcrEnrichmentResult = {
  text: string;
  warnings: string[];
};

/**
 * Extra OCR passes + ROI crops when a single full-page pass misses table digits.
 * Appended to primary OCR text before score extraction.
 */
export async function enrichOcrTextDetailed(
  preprocessedImagePath: string,
  documentType: DocumentType,
  ocrLang: string,
): Promise<OcrEnrichmentResult> {
  if (documentType !== "ielts" && documentType !== "ent") {
    return { text: "", warnings: [] };
  }

  const chunks: string[] = [];
  const dedupe = new Set<string>();
  const warnings: string[] = [];
  const lang = ocrLang.trim() || "eng";
  let totalChars = 0;

  const pushChunk = (label: string, raw: string): void => {
    const normalized = (raw || "").trim();
    if (!normalized) return;
    const compact = normalized.replace(/\s+/g, " ").trim();
    if (compact.length < 12) return;
    if (dedupe.has(compact)) return;
    dedupe.add(compact);
    const limited = compact.slice(0, MAX_CHUNK_CHARS);
    if (totalChars + limited.length > MAX_TOTAL_CHARS) return;
    chunks.push(`[${label}]\n${limited}`);
    totalChars += limited.length;
  };

  for (const psm of ["6", "11", "3"]) {
    try {
      const t = await runTesseractStdout(preprocessedImagePath, lang, psm);
      if (t.length > 20) {
        pushChunk(`psm${psm}`, t);
        warnings.push(`ocr_enrichment_pass psm${psm}: ok`);
      } else {
        warnings.push(`ocr_enrichment_pass psm${psm}: empty`);
      }
    } catch {
      warnings.push(`ocr_enrichment_pass psm${psm}: failed`);
    }
  }

  if (documentType === "ielts") {
    const ieltsRois: Array<{ label: string; frac: CropFrac }> = [
      { label: "ielts_bottom_roi", frac: { topFrac: 0.42, heightFrac: 0.58 } },
      { label: "ielts_mid_roi", frac: { topFrac: 0.28, heightFrac: 0.45 } },
    ];
    for (const roi of ieltsRois) {
      try {
        const text = await cropOcrRegion(preprocessedImagePath, roi.frac, lang);
        if (text) {
          pushChunk(roi.label, text);
          warnings.push(`ocr_enrichment_pass ${roi.label}: ok`);
        } else {
          warnings.push(`ocr_enrichment_pass ${roi.label}: empty`);
        }
      } catch {
        warnings.push(`ocr_enrichment_pass ${roi.label}: failed`);
      }
    }
  }

  if (documentType === "ent") {
    const entRois: Array<{ label: string; frac: CropFrac }> = [
      { label: "ent_top_roi", frac: { topFrac: 0.06, heightFrac: 0.34, leftFrac: 0.05, widthFrac: 0.9 } },
      { label: "ent_center_roi", frac: { topFrac: 0.2, heightFrac: 0.65, leftFrac: 0.1, widthFrac: 0.8 } },
      { label: "ent_bottom_roi", frac: { topFrac: 0.45, heightFrac: 0.5, leftFrac: 0.05, widthFrac: 0.9 } },
    ];
    for (const roi of entRois) {
      try {
        const text = await cropOcrRegion(preprocessedImagePath, roi.frac, lang);
        if (text) {
          pushChunk(roi.label, text);
          warnings.push(`ocr_enrichment_pass ${roi.label}: ok`);
        } else {
          warnings.push(`ocr_enrichment_pass ${roi.label}: empty`);
        }
      } catch {
        warnings.push(`ocr_enrichment_pass ${roi.label}: failed`);
      }
    }

    for (const factor of [1.4, 1.8]) {
      const label = `ent_upscale_${factor}x`;
      try {
        const upscale = await upscaleWholeImageOcr(preprocessedImagePath, factor, lang);
        if (upscale) {
          pushChunk(label, upscale);
          warnings.push(`ocr_enrichment_pass ${label}: ok`);
        } else {
          warnings.push(`ocr_enrichment_pass ${label}: empty`);
        }
      } catch {
        warnings.push(`ocr_enrichment_pass ${label}: failed`);
      }
    }
  }

  return {
    text: chunks.filter(Boolean).join("\n\n"),
    warnings,
  };
}

/** Backward-compatible wrapper used by older call sites/tests. */
export async function enrichOcrText(
  preprocessedImagePath: string,
  documentType: DocumentType,
  ocrLang: string,
): Promise<string> {
  const out = await enrichOcrTextDetailed(preprocessedImagePath, documentType, ocrLang);
  return out.text;
}

async function upscaleWholeImageOcr(
  imagePath: string,
  factor: number,
  lang: string,
): Promise<string> {
  const dir = await mkdtemp(join(tmpdir(), "ocr-upscale-"));
  const outPath = join(dir, `scaled-${String(factor).replace(".", "_")}.png`);
  try {
    const meta = await sharp(imagePath).metadata();
    const w = meta.width ?? 0;
    const h = meta.height ?? 0;
    if (w < 20 || h < 20) return "";

    const width = Math.max(64, Math.round(w * factor));
    const height = Math.max(64, Math.round(h * factor));
    await sharp(imagePath)
      .resize({ width, height, kernel: "lanczos3" })
      .greyscale()
      .normalize()
      .sharpen()
      .png()
      .toFile(outPath);

    const t6 = await runTesseractStdout(outPath, lang, "6").catch(() => "");
    const t11 = await runTesseractStdout(outPath, lang, "11").catch(() => "");
    return [t6, t11].filter((x) => x.length > 8).join("\n");
  } finally {
    await rm(dir, { recursive: true, force: true }).catch(() => undefined);
  }
}

type CropFrac = {
  topFrac: number;
  heightFrac: number;
  leftFrac?: number;
  widthFrac?: number;
};

async function cropOcrRegion(
  imagePath: string,
  frac: CropFrac,
  lang: string,
): Promise<string> {
  const left = frac.leftFrac ?? 0;
  const width = frac.widthFrac ?? 1;
  const meta = await sharp(imagePath).metadata();
  const w = meta.width ?? 0;
  const h = meta.height ?? 0;
  if (w < 20 || h < 20) return "";

  const leftPx = Math.floor(w * left);
  const topPx = Math.floor(h * frac.topFrac);
  const widthPx = Math.floor(w * width);
  const heightPx = Math.floor(h * frac.heightFrac);
  if (widthPx < 30 || heightPx < 30) return "";

  const dir = await mkdtemp(join(tmpdir(), "ocr-roi-"));
  const outPath = join(dir, "crop.png");
  try {
    await sharp(imagePath)
      .extract({ left: leftPx, top: topPx, width: widthPx, height: heightPx })
      .greyscale()
      .normalize()
      .sharpen()
      .png()
      .toFile(outPath);

    const t6 = await runTesseractStdout(outPath, lang, "6").catch(() => "");
    const t11 = await runTesseractStdout(outPath, lang, "11").catch(() => "");
    return [t6, t11].filter((x) => x.length > 8).join("\n");
  } finally {
    await rm(dir, { recursive: true, force: true }).catch(() => undefined);
  }
}

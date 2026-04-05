import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

import sharp from "sharp";

import type { DocumentType } from "../types.js";
import { runTesseractStdout } from "./tesseractCli.js";

/**
 * Extra OCR passes + ROI crops when a single full-page pass misses table digits.
 * Appended to primary OCR text before score extraction.
 */
export async function enrichOcrText(
  preprocessedImagePath: string,
  documentType: DocumentType,
  ocrLang: string,
): Promise<string> {
  if (documentType !== "ielts" && documentType !== "ent") {
    return "";
  }

  const chunks: string[] = [];
  const lang = ocrLang.trim() || "eng";

  for (const psm of ["6", "11", "3"]) {
    try {
      const t = await runTesseractStdout(preprocessedImagePath, lang, psm);
      if (t.length > 20) chunks.push(`[psm${psm}]\n${t}`);
    } catch {
      /* ignore */
    }
  }

  if (documentType === "ielts") {
    const bottom = await cropOcrRegion(preprocessedImagePath, { topFrac: 0.42, heightFrac: 0.58 }, lang);
    if (bottom) chunks.push(`[ielts_bottom_roi]\n${bottom}`);
    const mid = await cropOcrRegion(preprocessedImagePath, { topFrac: 0.28, heightFrac: 0.45 }, lang);
    if (mid) chunks.push(`[ielts_mid_roi]\n${mid}`);
  }

  if (documentType === "ent") {
    const top = await cropOcrRegion(
      preprocessedImagePath,
      { topFrac: 0.06, heightFrac: 0.34, leftFrac: 0.05, widthFrac: 0.9 },
      lang,
    );
    if (top) chunks.push(`[ent_top_roi]\n${top}`);
    const center = await cropOcrRegion(
      preprocessedImagePath,
      { topFrac: 0.2, heightFrac: 0.65, leftFrac: 0.1, widthFrac: 0.8 },
      lang,
    );
    if (center) chunks.push(`[ent_center_roi]\n${center}`);
    const bottom = await cropOcrRegion(
      preprocessedImagePath,
      { topFrac: 0.45, heightFrac: 0.5, leftFrac: 0.05, widthFrac: 0.9 },
      lang,
    );
    if (bottom) chunks.push(`[ent_bottom_roi]\n${bottom}`);

    for (const factor of [1.4, 1.8]) {
      const upscale = await upscaleWholeImageOcr(preprocessedImagePath, factor, lang);
      if (upscale) chunks.push(`[ent_upscale_${factor}x]\n${upscale}`);
    }
  }

  return chunks.filter(Boolean).join("\n\n");
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

/**
 * Прогон certificate-validation на файлах из apps/web/public/legal/ (см. expected.json).
 * Без файлов тесты skipped.
 * PDF: если текстовый слой достаточный — plainText (как API); если скан — первая страница в PNG (pdf-parse getScreenshot) + OCR.
 * Изображения: полный путь OCR (tesseract). В тесте preprocessImage замокан как identity — ffmpeg не нужен.
 * LEGAL_SKIP_IMAGE_FIXTURES=1 — пропустить jpeg/png.
 * LEGAL_SKIP_OCR_FIXTURES=1 — пропустить всё, что требует Tesseract (изображения и сканы PDF). Без этого флага при отсутствии Tesseract тест падает с явной ошибкой.
 */
import { execSync } from "node:child_process";
import { accessSync, constants as fsConstants, existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, extname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { PDFParse } from "pdf-parse";
import { afterAll, describe, expect, it, vi } from "vitest";

import { env } from "../../config/env.js";

vi.mock("../image/preprocessImage.js", () => ({
  preprocessImage: async (sourcePath: string) => sourcePath,
}));

import { validateCertificateImage } from "../certificateValidationOrchestrator.js";

const __dirname = dirname(fileURLToPath(import.meta.url));

function tesseractAvailable(): boolean {
  const bin = env.TESSERACT_BIN;
  try {
    if (bin.includes("/") || (bin.length >= 2 && bin[1] === ":")) {
      accessSync(bin, fsConstants.X_OK);
      return true;
    }
    execSync(`which ${bin}`, { stdio: "ignore" });
    return true;
  } catch {
    return false;
  }
}

const HAS_TESSERACT = tesseractAvailable();

function resolveLegalDir(): string {
  const envDir = process.env.LEGAL_FIXTURES_DIR?.trim();
  if (envDir) return envDir;
  return join(__dirname, "../../../../web/public/legal");
}

type ManifestFixture = {
  id: string;
  file: string;
  documentRole: "english" | "certificate" | "additional";
  certificateProofKind: string | null;
  englishProofKind: string | null;
  expectedDocumentType: string;
  expectedScore: number;
  /** Tesseract `-l`; overrides default `OCR_LANG` for this fixture. */
  ocrLang?: string;
};

type Manifest = { fixtures: ManifestFixture[] };

type LegalRow = {
  id: string;
  file: string;
  expectedDocumentType: string;
  expectedScore: number;
  detectedDocumentType: string;
  detectedScore: number | null;
  scoreMatchesExpected: boolean;
  processingStatus: string;
  ocrLangUsed: string | null;
  status: "ok" | "failed" | "skipped" | "type_ok_score_missing";
  notes: string;
};

const executionSummary: LegalRow[] = [];

async function extractPdfPlainText(buffer: Buffer): Promise<string> {
  const parser = new PDFParse({ data: buffer });
  try {
    const result = await parser.getText();
    return (result.text || "").trim();
  } finally {
    await parser.destroy();
  }
}

const PDF_TEXT_RASTER_THRESHOLD = 20;

async function writeFirstPageScreenshotToTemp(
  pdfBuffer: Buffer,
  tmpPrefix: string,
): Promise<{ path: string; cleanup: () => void }> {
  const parser = new PDFParse({ data: pdfBuffer });
  try {
    const shot = await parser.getScreenshot({ first: 1, imageBuffer: true, scale: 3.5 });
    const page = shot.pages[0];
    if (!page?.data?.length) {
      throw new Error("PDF getScreenshot: empty first page");
    }
    const dir = mkdtempSync(join(tmpdir(), `${tmpPrefix}-`));
    const pngPath = join(dir, "page1.png");
    writeFileSync(pngPath, Buffer.from(page.data));
    return {
      path: pngPath,
      cleanup: () => rmSync(dir, { recursive: true, force: true }),
    };
  } finally {
    await parser.destroy();
  }
}

async function scanPdfNeedsRaster(): Promise<Record<string, boolean>> {
  const legalDir = resolveLegalDir();
  const manifestPath = join(legalDir, "expected.json");
  const result: Record<string, boolean> = {};
  if (!existsSync(manifestPath)) return result;
  const manifest = JSON.parse(readFileSync(manifestPath, "utf-8")) as Manifest;
  for (const fx of manifest.fixtures) {
    if (!fx.file.toLowerCase().endsWith(".pdf")) continue;
    const p = join(legalDir, fx.file);
    if (!existsSync(p)) continue;
    const buf = readFileSync(p);
    const plain = await extractPdfPlainText(buf);
    result[fx.id] = plain.length <= PDF_TEXT_RASTER_THRESHOLD;
  }
  return result;
}

const pdfNeedsRaster = await scanPdfNeedsRaster();

function logFixtureResult(
  absPath: string,
  out: Awaited<ReturnType<typeof validateCertificateImage>>,
) {
  const row = {
    file: absPath,
    detectedDocumentType: out.documentType,
    detectedScore: out.extractedFields.totalScore ?? null,
    processingStatus: out.processingStatus,
    scorePlausible: out.extractedFields.scorePlausible ?? null,
    scoreRejectionReason: out.extractedFields.scoreRejectionReason ?? null,
    thresholdChecks: out.thresholdChecks,
    extractionMethod: out.extractedFields.extractionMethod ?? null,
    warnings: out.warnings,
    errors: out.errors,
    rawDetectedTextPreview: out.extractedFields.rawDetectedText?.slice(0, 4000) ?? null,
  };
  console.log(JSON.stringify(row, null, 2));
}

describe("legal fixtures (apps/web/public/legal)", () => {
  const legalDir = resolveLegalDir();
  const manifestPath = join(legalDir, "expected.json");

  it("manifest exists", () => {
    if (!existsSync(manifestPath)) {
      throw new Error(`Missing ${manifestPath} — create apps/web/public/legal/expected.json`);
    }
  });

  const manifest: Manifest = existsSync(manifestPath)
    ? (JSON.parse(readFileSync(manifestPath, "utf-8")) as Manifest)
    : { fixtures: [] };

  const skipOcrEnv = process.env.LEGAL_SKIP_OCR_FIXTURES === "1";
  /** When not "0", fail if numeric score is missing (strict). When "0", only assert document type + log summary. */
  const requireScore = process.env.LEGAL_REQUIRE_SCORE !== "0";

  for (const fx of manifest.fixtures) {
    const absPath = join(legalDir, fx.file);
    const extLower = extname(fx.file).toLowerCase();
    const isImage = [".png", ".jpg", ".jpeg", ".webp"].includes(extLower);
    const needsRasterPdf = extLower === ".pdf" && pdfNeedsRaster[fx.id] === true;
    const needsOcr = isImage || needsRasterPdf;
    const skipImage = isImage && process.env.LEGAL_SKIP_IMAGE_FIXTURES === "1";
    const skipOcr = needsOcr && skipOcrEnv;

    if (!existsSync(absPath)) {
      it.skip(`${fx.id}: ${fx.file} (missing file)`);
      continue;
    }
    if (skipImage) {
      it.skip(`${fx.id}: ${fx.file} (LEGAL_SKIP_IMAGE_FIXTURES=1)`);
      continue;
    }
    if (skipOcr) {
      it.skip(`${fx.id}: ${fx.file} (LEGAL_SKIP_OCR_FIXTURES=1)`);
      executionSummary.push({
        id: fx.id,
        file: fx.file,
        expectedDocumentType: fx.expectedDocumentType,
        expectedScore: fx.expectedScore,
        detectedDocumentType: "—",
        detectedScore: null,
        scoreMatchesExpected: false,
        processingStatus: "skipped",
        ocrLangUsed: fx.ocrLang ?? env.OCR_LANG,
        status: "skipped",
        notes: "LEGAL_SKIP_OCR_FIXTURES=1",
      });
      continue;
    }
    if (needsOcr && !HAS_TESSERACT) {
      it(`${fx.id}: ${fx.file} — Tesseract required`, () => {
        throw new Error(
          `OCR is required for this fixture but Tesseract was not found (TESSERACT_BIN=${env.TESSERACT_BIN}). ` +
            `Install tesseract and language packs (see apps/certificate-validation/docs/ocr-setup.md), ` +
            `or set LEGAL_SKIP_OCR_FIXTURES=1 to skip OCR cases in CI.`,
        );
      });
      continue;
    }

    it(
      `${fx.id}: ${fx.file}`,
      async () => {
        const ext = extname(fx.file).toLowerCase();
        let out: Awaited<ReturnType<typeof validateCertificateImage>>;
        let cleanupRaster: (() => void) | undefined;
        const ocrLang = fx.ocrLang?.trim() || undefined;

        try {
          if (ext === ".pdf") {
            const buf = readFileSync(absPath);
            const plainText = await extractPdfPlainText(buf);
            if (plainText.length > PDF_TEXT_RASTER_THRESHOLD) {
              out = await validateCertificateImage({
                plainText,
                documentRole: fx.documentRole,
                englishProofKind: fx.englishProofKind,
                certificateProofKind: fx.certificateProofKind,
                skipPersistence: true,
              });
            } else {
              const tmp = await writeFirstPageScreenshotToTemp(buf, `legal-${fx.id}`);
              cleanupRaster = tmp.cleanup;
              out = await validateCertificateImage({
                imagePath: tmp.path,
                documentRole: fx.documentRole,
                englishProofKind: fx.englishProofKind,
                certificateProofKind: fx.certificateProofKind,
                skipPersistence: true,
                ocrLang,
              });
            }
          } else if ([".png", ".jpg", ".jpeg", ".webp"].includes(ext)) {
            out = await validateCertificateImage({
              imagePath: absPath,
              documentRole: fx.documentRole,
              englishProofKind: fx.englishProofKind,
              certificateProofKind: fx.certificateProofKind,
              skipPersistence: true,
              ocrLang,
            });
          } else {
            throw new Error(`Unsupported fixture extension: ${ext}`);
          }

          logFixtureResult(absPath, out);

          const score = out.extractedFields.totalScore;

          const typeOk = out.documentType === fx.expectedDocumentType;
          const scoreOk =
            score != null &&
            Math.abs(score - fx.expectedScore) < 0.001 &&
            typeOk;
          executionSummary.push({
            id: fx.id,
            file: fx.file,
            expectedDocumentType: fx.expectedDocumentType,
            expectedScore: fx.expectedScore,
            detectedDocumentType: out.documentType,
            detectedScore: score ?? null,
            scoreMatchesExpected: scoreOk,
            processingStatus: out.processingStatus,
            ocrLangUsed:
              ext === ".pdf" && pdfNeedsRaster[fx.id] !== true ? "plainText_pdf" : ocrLang ?? env.OCR_LANG,
            status: scoreOk ? "ok" : typeOk && !requireScore ? "type_ok_score_missing" : "failed",
            notes: [
              out.warnings.length ? `warnings: ${out.warnings.join("; ")}` : "",
              out.errors.length ? `errors: ${out.errors.join("; ")}` : "",
              !scoreOk && requireScore ? "mismatch vs expected.json (document type or score)" : "",
              !scoreOk && !requireScore && score == null
                ? "LEGAL_REQUIRE_SCORE=0: document type asserted; score not in OCR output — use higher-DPI scan or manual review"
                : "",
            ]
              .filter(Boolean)
              .join(" ") || "—",
          });

          expect(out.documentType, "document type").toBe(fx.expectedDocumentType);
          if (requireScore) {
            expect(score, "score must be extracted (set LEGAL_REQUIRE_SCORE=0 to allow missing score for low-quality scans)").not.toBeNull();
            expect(score as number, "score matches manifest (update expected.json if document is different)").toBeCloseTo(
              fx.expectedScore,
              2,
            );
          }
        } finally {
          cleanupRaster?.();
        }
      },
      120_000,
    );
  }

  afterAll(() => {
    if (executionSummary.length === 0) return;
    console.log("\n=== legal fixtures: actual extraction summary (vs expected.json) ===\n");
    console.log(JSON.stringify(executionSummary, null, 2));
  });
});

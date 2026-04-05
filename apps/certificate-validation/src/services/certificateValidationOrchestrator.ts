import { pgPool } from "../db/pg.js";
import { saveCertificateValidationResult } from "../repositories/certificateValidationRepository.js";
import { classifyDocumentType } from "./classification/documentClassifier.js";
import { mapDeclarationToDocumentType, mergeDocumentType } from "./classification/mergeDocumentType.js";
import { extractFields } from "./extraction/fieldExtractor.js";
import { validatePlausibleScore } from "./extraction/plausibleScore.js";
import { preprocessImage } from "./image/preprocessImage.js";
import { TesseractOcrProvider } from "./ocr/tesseractOcrProvider.js";
import { enrichOcrText } from "./ocr/ocrEnrichment.js";
import { env } from "../config/env.js";
import { evaluateAuthenticity } from "./rules/authenticityHeuristics.js";
import { computePassedThreshold, evaluateThresholds } from "./rules/thresholdEvaluator.js";
import { buildOptionalSummary } from "./summary/llmSummaryService.js";
import { matchTemplate } from "./template/templateMatcher.js";
import type { CertificateValidationResult, DocumentType } from "./types.js";
import { writeTempFileFromBase64 } from "../utils/tempImageFromBase64.js";

export type ValidateCertificateInput = {
  imagePath?: string;
  imageBase64?: string;
  mimeType?: string;
  applicationId?: string | null;
  includeSummary?: boolean;
  /** When set (e.g. PDF text from API), skips preprocess + OCR */
  plainText?: string | null;
  expectedDocumentType?: DocumentType | null;
  englishProofKind?: string | null;
  certificateProofKind?: string | null;
  /** Which education attachment this is — used with proof kinds when expectedDocumentType is omitted */
  documentRole?: "english" | "certificate" | "additional";
  /** When true, do not INSERT into certificate_validation_results (caller persists, e.g. API). */
  skipPersistence?: boolean;
  /** Overrides default `OCR_LANG` for Tesseract (`-l`), e.g. `rus+kaz+eng` for Cyrillic scans. */
  ocrLang?: string | null;
};

function emptyFailure(
  errors: string[],
  processingStatus: CertificateValidationResult["processingStatus"] = "processing_failed"
): CertificateValidationResult {
  return {
    documentType: "unknown",
    processingStatus,
    extractedFields: { rawDetectedText: null },
    scoreLabel: null,
    passedThreshold: null,
    thresholdType: null,
    thresholdChecks: {},
    authenticity: {
      status: "manual_review_required",
      templateMatchScore: null,
      ocrConfidence: null,
      fraudSignals: ["validation_input_invalid"]
    },
    warnings: [],
    errors,
    explainability: ["Missing image or text input"],
    confidence: 0
  };
}

export async function validateCertificateImage(
  input: ValidateCertificateInput
): Promise<CertificateValidationResult> {
  const warnings: string[] = [];
  const errors: string[] = [];
  let cleanup: (() => Promise<void>) | undefined;

  try {
    let ocr: { text: string; confidence: number | null };

    let preprocessedPath: string | undefined;

    if (input.plainText?.trim()) {
      ocr = { text: input.plainText.trim(), confidence: 1.0 };
    } else {
      let path = input.imagePath;
      if (input.imageBase64) {
        const t = await writeTempFileFromBase64(input.imageBase64, input.mimeType ?? "image/jpeg");
        path = t.path;
        cleanup = t.cleanup;
      }
      if (!path) {
        return emptyFailure(["Provide plainText, imagePath, or imageBase64"]);
      }

      preprocessedPath = await preprocessImage(path);
      const ocrOpts = input.ocrLang?.trim() ? { ocrLang: input.ocrLang.trim() } : undefined;
      ocr = await new TesseractOcrProvider().extractText(preprocessedPath, ocrOpts);
    }

    if (!ocr.text?.trim()) {
      return {
        documentType: "unknown",
        processingStatus: "ocr_failed",
        extractedFields: { rawDetectedText: null },
        scoreLabel: null,
        passedThreshold: null,
        thresholdType: null,
        thresholdChecks: {},
        authenticity: {
          status: "insufficient_quality",
          templateMatchScore: null,
          ocrConfidence: ocr.confidence,
          fraudSignals: ["ocr_empty_output"]
        },
        warnings,
        errors: ["OCR failed to detect text"],
        explainability: ["Tesseract returned empty text"],
        confidence: 0.1
      };
    }

    const ocrDocumentType = classifyDocumentType(ocr.text);

    const fromDeclaration = mapDeclarationToDocumentType({
      englishProofKind: input.englishProofKind,
      certificateProofKind: input.certificateProofKind,
      documentRole: input.documentRole ?? "additional"
    });
    const expected: DocumentType | null =
      input.expectedDocumentType && input.expectedDocumentType !== "unknown"
        ? input.expectedDocumentType
        : fromDeclaration;

    const merged = mergeDocumentType(ocrDocumentType, expected);
    warnings.push(...merged.warnings);
    const documentType = merged.resolved;

    if (merged.mismatch) {
      warnings.push("Declaration vs OCR mismatch: threshold not applied automatically.");
    }

    let template = matchTemplate(ocr.text, documentType);
    let extracted = extractFields(ocr.text, documentType);

    if (
      extracted.totalScore == null &&
      preprocessedPath &&
      (documentType === "ielts" || documentType === "ent")
    ) {
      const lang = input.ocrLang?.trim() || env.OCR_LANG;
      try {
        const extra = await enrichOcrText(preprocessedPath, documentType, lang);
        if (extra.trim()) {
          warnings.push("Supplementary OCR (multi-pass / ROI) appended for score extraction.");
          ocr = { text: `${ocr.text}\n\n${extra}`, confidence: ocr.confidence };
          template = matchTemplate(ocr.text, documentType);
          extracted = extractFields(ocr.text, documentType);
        }
      } catch {
        warnings.push("Supplementary OCR enrichment failed; using primary OCR text only.");
      }
    }

    let finalScore: number | null = extracted.totalScore ?? null;
    let scorePlausible: boolean | null = null;
    let scoreRejectionReason: string | null = null;
    const targetFieldFound = extracted.targetFieldFound === true;
    const targetFieldType = extracted.targetFieldType ?? null;
    const targetFieldEvidence = extracted.targetFieldEvidence ?? null;
    if (finalScore != null && documentType !== "unknown") {
      const plaus = validatePlausibleScore(documentType, finalScore);
      if (!plaus.ok) {
        scoreRejectionReason = plaus.reason ?? "unknown";
        warnings.push(`Extracted score rejected as implausible (${plaus.reason}).`);
        finalScore = null;
        scorePlausible = false;
      } else {
        scorePlausible = true;
      }
    }
    if (documentType !== "unknown" && !targetFieldFound) {
      warnings.push("Target score field was not detected; manual review required.");
    }

    const thresholds = evaluateThresholds(documentType, finalScore, {
      declarationMismatch: merged.mismatch
    });
    const passedMeta = computePassedThreshold(documentType, finalScore, merged.mismatch);

    const fraudExtra: string[] = [];
    if (merged.mismatch) fraudExtra.push("declaration_ocr_mismatch");
    if (scorePlausible === false) fraudExtra.push("implausible_score_rejected");

    const auth = evaluateAuthenticity({
      templateScore: template.score,
      ocrConfidence: ocr.confidence,
      hasScore: finalScore !== null && finalScore !== undefined,
      missingAnchors: template.missingAnchors,
      extraFraudSignals: fraudExtra
    });

    const usedOcr = !input.plainText?.trim();
    const ocrLow = usedOcr && ocr.confidence !== null && ocr.confidence < 0.35;
    if (ocrLow) {
      warnings.push("Low OCR confidence; verify document manually.");
    }

    let processingStatus: CertificateValidationResult["processingStatus"] =
      documentType === "unknown" ? "unsupported" : "processed";
    if (documentType !== "unknown" && ocrLow) {
      processingStatus = "low_quality";
    }

    const plausLine =
      scorePlausible === true
        ? "Plausibility: passed"
        : scorePlausible === false
          ? `Plausibility: rejected (${scoreRejectionReason ?? "?"})`
          : "Plausibility: no numeric score to validate";

    const explainability = [
      `OCR classified as ${ocrDocumentType}, resolved type: ${documentType}`,
      `Template score: ${template.score}`,
      `Extraction method: ${extracted.extractionMethod ?? "n/a"}`,
      `Target field: ${targetFieldType ?? "n/a"} (${targetFieldFound ? "found" : "missing"})`,
      `Detected score (after plausibility): ${finalScore ?? "none"}`,
      plausLine
    ];
    if (template.missingAnchors.length) warnings.push(`Missing anchors: ${template.missingAnchors.join(", ")}`);
    if (documentType === "unknown") warnings.push("Document type is unknown after merge");

    const confidence = Number(
      Math.max(
        0,
        Math.min(
          1,
          0.25 +
            template.score * 0.35 +
            (ocr.confidence ?? 0) * 0.2 +
            (finalScore != null ? 0.1 : 0) -
            errors.length * 0.05 -
            (merged.mismatch ? 0.15 : 0)
        )
      ).toFixed(3)
    );

    const result: CertificateValidationResult = {
      documentType,
      processingStatus,
      extractedFields: {
        ...extracted,
        totalScore: finalScore,
        rawDetectedText: ocr.text.slice(0, 3000),
        ocrDocumentType,
        declarationMismatch: merged.mismatch,
        extractionMethod: extracted.extractionMethod ?? null,
        targetFieldFound,
        targetFieldType,
        targetFieldEvidence,
        scorePlausible,
        scoreRejectionReason
      },
      thresholdChecks: thresholds,
      scoreLabel: finalScore != null ? extracted.scoreLabel ?? null : null,
      passedThreshold: passedMeta.passed,
      thresholdType: passedMeta.thresholdType,
      authenticity: {
        status: auth.status,
        templateMatchScore: template.score,
        ocrConfidence: ocr.confidence,
        fraudSignals: auth.fraudSignals
      },
      warnings,
      errors,
      explainability,
      confidence
    };

    if (input.includeSummary) result.summaryText = await buildOptionalSummary(result);
    if (!input.skipPersistence) {
      await saveCertificateValidationResult(pgPool, { applicationId: input.applicationId, result });
    }
    return result;
  } catch (error) {
    return {
      documentType: "unknown",
      processingStatus: "processing_failed",
      extractedFields: { rawDetectedText: null },
      scoreLabel: null,
      passedThreshold: null,
      thresholdType: null,
      thresholdChecks: {},
      authenticity: {
        status: "manual_review_required",
        templateMatchScore: null,
        ocrConfidence: null,
        fraudSignals: ["processing_exception"]
      },
      warnings,
      errors: [error instanceof Error ? error.message : "Unknown processing error"],
      explainability: ["Pipeline failed before final assembly"],
      confidence: 0
    };
  } finally {
    if (cleanup) await cleanup().catch(() => undefined);
  }
}

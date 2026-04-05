import { describe, expect, it, vi } from "vitest";

import * as repo from "../../repositories/certificateValidationRepository.js";
import { validateCertificateImage } from "../certificateValidationOrchestrator.js";

vi.mock("../image/preprocessImage.js", () => ({
  preprocessImage: vi.fn().mockResolvedValue("/tmp/preprocessed.png")
}));
vi.mock("../ocr/tesseractOcrProvider.js", () => ({
  TesseractOcrProvider: class {
    extractText() {
      return Promise.resolve({
        text: "IELTS Test Report Form Overall Band Score 6.5",
        confidence: 0.82
      });
    }
  }
}));

describe("validateCertificateImage", () => {
  it("returns processed ielts result", async () => {
    vi.spyOn(repo, "saveCertificateValidationResult").mockResolvedValueOnce();
    const out = await validateCertificateImage({ imagePath: "/tmp/cert.png" });
    expect(out.documentType).toBe("ielts");
    expect(out.processingStatus).toBe("processed");
    expect(out.thresholdChecks.ieltsMinPassed).toBe(true);
    expect(out.extractedFields.targetFieldFound).toBe(true);
    expect(out.extractedFields.targetFieldType).toBe("ielts_overall_band");
    expect(out.extractedFields.extractionConfidenceTier).toBe("high");
  });

  it("infers ielts from declaration for additional document when only english proof is declared", async () => {
    const out = await validateCertificateImage({
      plainText:
        "IELTS Test Report Form\nBritish Council\nOverall Band Score 6.0\nListening 6.0 Reading 6.5 Writing 6.0 Speaking 6.0",
      documentRole: "additional",
      englishProofKind: "ielts_6",
      certificateProofKind: null,
      skipPersistence: true
    });
    expect(out.documentType).toBe("ielts");
    expect(out.extractedFields.totalScore).toBe(6.0);
    expect(out.processingStatus).toBe("processed");
  });
});

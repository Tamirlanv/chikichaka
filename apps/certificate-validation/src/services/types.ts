export type DocumentType = "ielts" | "toefl" | "ent" | "nis_12" | "unknown";

/** @deprecated use ent | nis_12 — kept for DB rows / older clients */
export type LegacyDocumentType = DocumentType | "ent_nish";

export type ProcessingStatus =
  | "processed"
  | "unsupported"
  | "ocr_failed"
  | "low_quality"
  | "processing_failed";

export type AuthenticityStatus =
  | "likely_authentic"
  | "suspicious"
  | "manual_review_required"
  | "insufficient_quality";

export type ThresholdType = "ielts" | "toefl";

export type CertificateValidationResult = {
  documentType: DocumentType;
  processingStatus: ProcessingStatus;
  extractedFields: {
    candidateName?: string | null;
    certificateNumber?: string | null;
    examDate?: string | null;
    totalScore?: number | null;
    scoreLabel?: string | null;
    sectionScores?: Record<string, number | null> | null;
    rawDetectedText?: string | null;
    ocrDocumentType?: DocumentType | null;
    declarationMismatch?: boolean;
    /** Which rule matched (e.g. ielts:overall_band_score_line) */
    extractionMethod?: string | null;
    /** Whether parser found the explicit target score field for this document type */
    targetFieldFound?: boolean;
    /** Target field id used by parser (e.g. ielts_overall_band, ent_total_score) */
    targetFieldType?: string | null;
    /** Short context snippet around matched target field */
    targetFieldEvidence?: string | null;
    /** After plausibility check */
    scorePlausible?: boolean | null;
    scoreRejectionReason?: string | null;
  };
  thresholdChecks: {
    ieltsMinPassed?: boolean | null;
    entScoreDetected?: boolean | null;
    toeflMinPassed?: boolean | null;
  };
  /** Mirrors business rules: only for ielts/toefl; null if not applicable or indeterminate */
  scoreLabel?: string | null;
  passedThreshold?: boolean | null;
  thresholdType?: ThresholdType | null;
  authenticity: {
    status: AuthenticityStatus;
    templateMatchScore: number | null;
    ocrConfidence: number | null;
    fraudSignals: string[];
  };
  warnings: string[];
  errors: string[];
  explainability: string[];
  confidence: number;
  summaryText?: string | null;
};

export type FileValidationResult = {
  isValid: boolean;
  warnings: string[];
  errors: string[];
};

export type OcrResult = {
  text: string;
  confidence: number | null;
  words?: Array<{ text: string; confidence: number | null }>;
};

export type TemplateMatchResult = {
  score: number;
  anchorsFound: string[];
  missingAnchors: string[];
};

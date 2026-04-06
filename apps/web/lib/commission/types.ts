export type CommissionRange = "day" | "week" | "month" | "year";
export type CommissionEngagementSort = "risk" | "freshness" | "engagement";
export type CommissionHistoryMode = "events" | "archive";
export type CommissionHistoryEventFilter =
  | "all"
  | "commission"
  | "system"
  | "candidates"
  | "stage"
  | "interview"
  | "decision";
export type CommissionHistorySort = "newest" | "oldest";

export type CommissionRole = "viewer" | "reviewer" | "admin";

export type CommissionStage =
  | "data_check"
  | "application_review"
  | "interview"
  | "committee_decision"
  | "result";

export type StageStatus = "new" | "in_review" | "needs_attention" | "approved" | "rejected";
export type FinalDecision = "move_forward" | "reject" | "waitlist" | "invite_interview" | "enrolled";
export type AIRecommendation = "recommend" | "neutral" | "caution";

export type CardVisualState = "positive" | "negative" | "neutral" | "attention";

export type CommissionBoardApplicationCard = {
  applicationId: string;
  candidateId: string;
  candidateFullName: string;
  program: string;
  city: string | null;
  phone: string | null;
  age: number | null;
  submittedAt: string | null;
  updatedAt: string | null;
  currentStage: CommissionStage;
  currentStageStatus: StageStatus | null;
  finalDecision: FinalDecision | null;
  manualAttentionFlag: boolean;
  commentCount: number;
  aiRecommendation: AIRecommendation | null;
  aiConfidence: number | null;
  visualState: CardVisualState;
  /** ISO timestamp when candidate finished AI interview (API: ai_interview_completed_at_iso). */
  aiInterviewCompletedAtIso: string | null;
  /** Path + motivation + achievements: all manual scores set (one reviewer). */
  rubricThreeSectionsComplete: boolean;
  /** Sum of manual scores across required stage-2 sections for the completed reviewer set. */
  applicationReviewTotalScore?: number | null;
  /** Latest data-check run aggregate status when card is on «Проверка данных» (API: data_check_run_status). */
  dataCheckRunStatus: string | null;
  /** AI summary present and data-check pipeline ready. */
  stageOneDataReady: boolean;
  /** Commission interview scheduled (API: interview_scheduled_at_iso). */
  interviewScheduledAtIso: string | null;
};

export type CommissionBoardColumn = {
  stage: CommissionStage;
  title: string;
  applications: CommissionBoardApplicationCard[];
};

export type CommissionBoardMetrics = {
  totalApplications: number;
  todayApplications: number;
  foundationApplications: number;
  bachelorApplications: number;
};

export type CommissionBoardFilters = {
  search: string;
  program: string | null;
  range: CommissionRange;
};

export type CommissionBoardResponse = {
  filters: CommissionBoardFilters;
  metrics: CommissionBoardMetrics;
  columns: CommissionBoardColumn[];
};

export type CommissionEngagementLevel = "High" | "Medium" | "Low";
export type CommissionRiskLevel = "High" | "Medium" | "Low";

export type CommissionEngagementCard = {
  applicationId: string;
  candidateFullName: string;
  lastActivityAtIso: string | null;
  lastActivityHumanized: string;
  activeTimeHumanized: string | null;
  engagementLevel: CommissionEngagementLevel;
  riskLevel: CommissionRiskLevel;
  program: string | null;
  currentStage: string | null;
};

export type CommissionEngagementColumn = {
  id: "high_risk" | "medium_risk" | "low_risk";
  title: string;
  cards: CommissionEngagementCard[];
};

export type CommissionEngagementResponse = {
  filters: {
    search: string;
    program: string | null;
    sort: CommissionEngagementSort;
  };
  totals: {
    total: number;
    highRisk: number;
    mediumRisk: number;
    lowRisk: number;
  };
  columns: CommissionEngagementColumn[];
};

export type CommissionHistoryEvent = {
  id: string;
  applicationId: string;
  candidateFullName: string;
  program: string | null;
  currentStage: string | null;
  eventType: string;
  eventCategory: "commission" | "system" | "candidate";
  description: string;
  initiator: string;
  timestamp: string;
};

export type CommissionHistoryResponse = {
  items: CommissionHistoryEvent[];
  total: number;
  filters: {
    search: string;
    program: string | null;
    eventType: CommissionHistoryEventFilter;
    sort: CommissionHistorySort;
  };
};

export type CommissionApplicationHistoryResponse = {
  applicationId: string;
  items: CommissionHistoryEvent[];
  total: number;
  filters: {
    eventType: CommissionHistoryEventFilter;
    sort: CommissionHistorySort;
  };
};

export type CommissionUpdatesResponse = {
  changedApplicationIds: string[];
  latestCursor: string;
};

export type ApplicationAISummaryView = {
  summaryText: string | null;
  strengths: string[];
  weakPoints: string[];
  leadershipSignals: string[];
  missionFitNotes: string[];
  redFlags: string[];
  recommendation: AIRecommendation | null;
  confidenceScore: number | null;
  explainabilityNotes: string[];
  generatedAt: string | null;
  status: "not_generated" | "ready" | "failed";
};

export type ValidationCheckResult = {
  status: string;
  result: Record<string, unknown> | null;
  updatedAt: string | null;
};

export type ValidationReport = {
  runId: string;
  candidateId: string;
  applicationId: string;
  overallStatus: string;
  checks: {
    links: ValidationCheckResult | null;
    videoPresentation: ValidationCheckResult | null;
    certificates: ValidationCheckResult | null;
  };
  warnings: string[];
  errors: string[];
  explainability: string[];
  updatedAt: string | null;
};

export type CommissionApplicationDetailView = {
  application_id: string;
  submitted_at: string | null;
  candidate: {
    full_name: string;
    city: string | null;
    phone: string | null;
    program: string | null;
    age: number | null;
  };
  stage: {
    currentStage: CommissionStage;
    currentStageStatus: StageStatus;
    finalDecision: FinalDecision | null;
    availableNextActions: string[];
  };
  personalInfo: {
    basicInfo: Record<string, unknown>;
    contacts: Record<string, unknown>;
    guardians: Array<Record<string, unknown>>;
    address: Record<string, unknown>;
    education: Record<string, unknown>;
  };
  test: Record<string, unknown> | null;
  motivation: Record<string, unknown> | null;
  path: {
    answers: Array<{ questionKey: string; questionTitle: string; text: string }>;
    summary?: string | null;
    keyThemes?: string[] | null;
  } | null;
  achievements: Record<string, unknown> | null;
  aiSummary: ApplicationAISummaryView | null;
  validationReport?: ValidationReport | null;
  review: {
    rubricScores: Array<{
      criterion: string;
      value: "strong" | "medium" | "low";
      authorId: string;
      updatedAt: string;
    }>;
    internalRecommendations: Array<{
      authorId: string;
      recommendation: "recommend_forward" | "needs_discussion" | "reject";
      reasonComment: string | null;
      updatedAt: string;
    }>;
    tags: string[];
  };
  comments: Array<{
    id: string;
    text: string;
    authorId: string | null;
    createdAt: string | null;
    tags: string[];
  }>;
  recentActivity: Array<{
    id: string;
    event_type: string;
    timestamp: string;
    actor_user_id: string | null;
    previous_value: unknown;
    next_value: unknown;
    metadata: unknown;
  }>;
};

export type CommissionApplicationPersonalInfoView = {
  applicationId: string;
  isArchived?: boolean;
  readOnly?: boolean;
  readOnlyReason?: string | null;
  candidateSummary: {
    fullName: string;
    program: string | null;
    phone: string | null;
    telegram: string | null;
    instagram: string | null;
    submittedAt: string | null;
    currentStage: CommissionStage | string;
    currentStageStatus: StageStatus | string;
  };
  aiSummary: {
    profileTitle: string | null;
    summaryText: string | null;
    strengths: string[];
    weakPoints: string[];
  } | null;
  stageContext: {
    currentStage: CommissionStage | string;
    currentStageStatus: StageStatus | string;
    availableActions: string[];
  };
  personalInfo: {
    basicInfo: {
      fullName: string;
      gender: string | null;
      birthDate: string | null;
      age: number | null;
    };
    guardians: Array<{
      role: string;
      fullName: string;
      phone: string | null;
    }>;
    address: {
      country: string | null;
      region: string | null;
      city: string | null;
      fullAddress: string | null;
    };
    contacts: {
      phone: string | null;
      instagram: string | null;
      telegram: string | null;
      whatsapp: string | null;
    };
    documents: Array<{
      id: string;
      type: string;
      fileName: string;
      fileSize: string | null;
      fileUrl: string | null;
      fileRef: string | null;
      /** gray | green | red — граница карточки в списке документов комиссии */
      borderTone?: "gray" | "green" | "red";
    }>;
    videoPresentation: {
      url: string;
      borderTone?: "gray" | "green";
      summary?: string;
      duration?: string | null;
      candidateVisibility?: string | null;
    } | null;
  };
  motivation: {
    narrative: string | null;
  };
  path: Array<{
    questionTitle: string;
    description: string;
    text: string;
  }> | null;
  achievements: {
    text: string | null;
    role: string | null;
    year: string | null;
    links: Array<{
      label: string;
      url: string;
      linkType: string | null;
    }>;
  };
  processingStatus: {
    overall: "pending" | "running" | "partial" | "ready" | "failed";
    completedCount: number;
    totalCount: number;
    units: Record<string, string>;
    manualReviewRequired: boolean;
    warnings: string[];
    errors: string[];
  } | null;
  comments: Array<{
    id: string;
    text: string;
    authorName: string;
    createdAt: string | null;
  }>;
  actions: {
    canComment: boolean;
    canMoveForward: boolean;
    canApproveAiInterview?: boolean;
    canGenerateAiInterview?: boolean;
  };
};

export type AiInterviewDraftQuestion = {
  id: string;
  questionText: string;
  reasonType?: string;
  reasonDescription?: string;
  sourceSections?: string[];
  severity?: string;
  generatedBy?: string;
  isEditedByCommission?: boolean;
  commissionEditedText?: string | null;
  sortOrder?: number;
};

export type AiInterviewDraftView = {
  applicationId: string;
  status: string;
  revision: number;
  questions: AiInterviewDraftQuestion[];
  generatedFromSignals?: Record<string, unknown> | null;
  generationSource?: string | null;
  fallbackReason?: string | null;
  issueCount?: number | null;
  generatedAt: string | null;
  approvedAt: string | null;
  approvedByUserId: string | null;
};

export type CommissionApplicationTestInfoView = {
  personalityProfile: {
    profileType: string;
    profileTitle: string;
    summary: string;
    rawScores: Record<string, number>;
    ranking: Array<{ trait: string; score: number }>;
    dominantTrait: string;
    secondaryTrait: string;
    weakestTrait: string;
    flags?: Record<string, boolean>;
    meta?: Record<string, unknown>;
  } | null;
  testLang: string;
  questions: Array<{
    index: number;
    questionId: string;
    prompt: string;
    selectedAnswer: string | null;
  }>;
  aiSummary: {
    aboutCandidate: string | null;
    weakPoints: string[];
  } | null;
};

/** Строка сайдбара: текст или строка с тоном (валидация документов). */
export type SidebarSectionItem =
  | string
  | {
      text: string;
      tone?: "neutral" | "success" | "danger";
    };

export type SidebarSection = {
  title: string;
  items: SidebarSectionItem[];
  attentionNotes?: AttentionNote[];
};

export type CommissionSidebarPanelView = {
  type: "validation" | "summary";
  title: string;
  sections: SidebarSection[];
};

export type AttentionNoteCategory =
  | "originality"
  | "consistency"
  | "paste_behavior"
  | "content_quality";

export type AttentionNoteSeverity = "low" | "medium" | "high";

export type AttentionNote = {
  category: AttentionNoteCategory;
  title: string;
  message: string;
  severity: AttentionNoteSeverity;
  confidence?: number | null;
};

export type ReviewScoreItem = {
  key: string;
  label: string;
  recommendedScore: number;
  manualScore: number | null;
  effectiveScore: number;
};

export type ReviewScoreBlock = {
  section: string;
  items: ReviewScoreItem[];
  totalScore: number;
  maxTotalScore: number;
  /** Округлённое среднее рекомендуемых подкритериев раздела (1–5). */
  aggregateRecommendedScore?: number;
  /** Текст пояснения сводной рекомендации (API). */
  aggregateRecommendationExplanation?: string;
};

/** Итог AI-собеседования: краткая сводка и списки снятых/открытых пунктов. */
export type CommissionAiInterviewResolutionSummary = {
  shortSummary: string;
  resolvedPoints: string[];
  unresolvedPoints: string[];
  newInformation: string[];
  followUpFocus?: string[];
  confidence: "low" | "medium" | "high";
  generatedAt: string;
  promptVersion?: string;
  generationSource?: "llm" | "fallback" | string;
};

export type CommissionCandidatePreferencePanel = {
  preferredSlots: Array<{
    date: string;
    timeRangeCode: string;
    timeRange: string;
  }>;
  preferencesSubmittedAt: string | null;
  windowStatus: string | null;
  windowOpenedAt: string | null;
  windowExpiresAt: string | null;
  remainingSeconds: number | null;
};

export type CommissionScheduledInterviewPayload = {
  sessionId: string;
  scheduledAt: string | null;
  interviewMode: string | null;
  locationOrLink: string | null;
  scheduledByUserId: string | null;
  reminderRequestedAt?: string | null;
  reminderSentAt?: string | null;
  outcomeRecordedAt?: string | null;
};

/** GET /commission/applications/:id/stage-advance-preview */
export type StageAdvancePrimaryAction = {
  kind: "open_application";
  applicationId: string;
  query: { interviewSubTab?: string };
};

export type StageAdvancePreviewResponse = {
  allowed: boolean;
  candidateFullName: string;
  targetStageLabel: string;
  transition?: string | null;
  confirm?: {
    title: string;
    message: string;
    confirmLabel: string;
    cancelLabel: string;
  };
  blocked?: {
    code: string | null;
    message: string;
    confirmLabel: string;
    cancelLabel: string;
    primaryAction: StageAdvancePrimaryAction | null;
  };
};

/**
 * Карточка сессии AI-собеседования для комиссии: вопросы/ответы, слоты, расписание, сводка.
 * Источник: GET .../ai-interview/candidate-session.
 */
export type CommissionAiInterviewSessionView = {
  applicationId: string;
  candidateId: string;
  sessionId: string | null;
  interviewCompletedAt: string | null;
  questionsAndAnswers: Array<{
    questionId: string;
    questionText: string;
    answerText: string;
    order: number;
  }>;
  preferredSlots: Array<{
    date: string;
    timeRangeCode: string;
    timeRange: string;
  }>;
  candidatePreferencePanel?: CommissionCandidatePreferencePanel;
  commissionSchedule?: {
    scheduledInterview: CommissionScheduledInterviewPayload | null;
  };
  resolutionSummary: CommissionAiInterviewResolutionSummary | null;
  resolutionSummaryError: string | null;
};

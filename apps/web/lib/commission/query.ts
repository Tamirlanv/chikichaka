import { apiFetch, apiFetchBlob } from "../api-client";
import { COMMISSION_STAGE_ORDER, COMMISSION_STAGE_TITLES } from "./constants";
import { sortColumnApplications } from "./sort";
import { getApplicationCardVisualState } from "./visual-state";
import { buildInterviewColumns, mapApiRowToInterviewCard } from "./interviewBoard";
import type { InterviewBoardColumn, InterviewBoardFilters } from "./interviewTypes";
import type {
  AiInterviewDraftView,
  CommissionAiInterviewSessionView,
  StageAdvancePreviewResponse,
  CommissionBoardApplicationCard,
  CommissionBoardFilters,
  CommissionBoardMetrics,
  CommissionBoardResponse,
  CommissionApplicationDetailView,
  CommissionApplicationPersonalInfoView,
  CommissionApplicationTestInfoView,
  CommissionSidebarPanelView,
  CommissionRange,
  CommissionRole,
  CommissionStage,
  CommissionUpdatesResponse,
  CommissionScheduledInterviewPayload,
  ReviewScoreBlock,
  CommissionEngagementCard,
  CommissionEngagementResponse,
  CommissionEngagementSort,
  CommissionHistoryEvent,
  CommissionHistoryResponse,
  CommissionApplicationHistoryResponse,
  CommissionHistoryEventFilter,
  CommissionHistorySort,
} from "./types";

type ApiCard = Record<string, unknown>;

function toStage(v: unknown): CommissionStage {
  const s = String(v ?? "");
  if (s === "data_check" || s === "application_review" || s === "interview" || s === "committee_decision" || s === "result") {
    return s;
  }
  return "result";
}

function asStr(v: unknown): string | null {
  if (v == null) return null;
  const s = String(v);
  return s.length ? s : null;
}

function asNum(v: unknown): number | null {
  if (typeof v === "number" && Number.isFinite(v)) return v;
  if (typeof v === "string" && v.trim()) {
    const n = Number(v);
    if (Number.isFinite(n)) return n;
  }
  return null;
}

function formatMinutesRu(totalMinutes: number): string {
  const minutes = Math.max(0, Math.floor(totalMinutes));
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;
  const minutesWord =
    mins % 10 === 1 && mins % 100 !== 11
      ? "минута"
      : mins % 10 >= 2 && mins % 10 <= 4 && (mins % 100 < 10 || mins % 100 >= 20)
        ? "минуты"
        : "минут";
  if (hours <= 0) {
    return `${mins} ${minutesWord}`;
  }
  const hoursWord =
    hours % 10 === 1 && hours % 100 !== 11
      ? "час"
      : hours % 10 >= 2 && hours % 10 <= 4 && (hours % 100 < 10 || hours % 100 >= 20)
        ? "часа"
        : "часов";
  return `${hours} ${hoursWord} ${mins} ${minutesWord}`;
}

function asBool(v: unknown): boolean {
  return Boolean(v);
}

function mapHistoryEvent(raw: Record<string, unknown>): CommissionHistoryEvent {
  const categoryRaw = String(raw.eventCategory ?? raw.event_category ?? "system");
  const eventCategory: CommissionHistoryEvent["eventCategory"] =
    categoryRaw === "commission" || categoryRaw === "candidate" ? categoryRaw : "system";
  return {
    id: String(raw.id ?? ""),
    applicationId: String(raw.applicationId ?? raw.application_id ?? ""),
    candidateFullName: String(raw.candidateFullName ?? raw.candidate_full_name ?? "Кандидат"),
    program: asStr(raw.program),
    currentStage: asStr(raw.currentStage ?? raw.current_stage),
    eventType: String(raw.eventType ?? raw.event_type ?? "Событие"),
    eventCategory,
    description: String(raw.description ?? ""),
    initiator: String(raw.initiator ?? "Система"),
    timestamp: String(raw.timestamp ?? ""),
  };
}

export function mapApiCard(card: ApiCard): CommissionBoardApplicationCard {
  const currentStage = toStage(card.stage_column ?? card.currentStage);
  const currentStageStatus = asStr(card.stage_status ?? card.currentStageStatus) as CommissionBoardApplicationCard["currentStageStatus"];
  const finalDecision = asStr(card.final_decision ?? card.finalDecision) as CommissionBoardApplicationCard["finalDecision"];
  const manualAttentionFlag = asBool(card.attention_flag_manual ?? card.manualAttentionFlag);

  return {
    applicationId: String(card.application_id ?? card.applicationId ?? ""),
    candidateId: String(card.application_id ?? card.applicationId ?? ""),
    candidateFullName: String(card.candidate_full_name ?? card.candidateFullName ?? ""),
    program: String(card.program ?? ""),
    city: asStr(card.city),
    phone: asStr(card.phone),
    age: asNum(card.age),
    submittedAt: asStr(card.submitted_at_iso ?? card.submittedAt),
    updatedAt: asStr(card.updated_at_iso ?? card.updatedAt),
    currentStage,
    currentStageStatus,
    finalDecision,
    manualAttentionFlag,
    commentCount: asNum(card.comment_count ?? card.commentCount) ?? 0,
    aiRecommendation: asStr(card.ai_recommendation ?? card.aiRecommendation) as CommissionBoardApplicationCard["aiRecommendation"],
    aiConfidence: asNum(card.ai_confidence ?? card.aiConfidence),
    visualState: getApplicationCardVisualState({ currentStageStatus, finalDecision, manualAttentionFlag }),
    aiInterviewCompletedAtIso: asStr(card.ai_interview_completed_at_iso ?? card.aiInterviewCompletedAtIso),
    rubricThreeSectionsComplete: Boolean(card.rubric_three_sections_complete ?? card.rubricThreeSectionsComplete),
    applicationReviewTotalScore: asNum(
      card.application_review_total_score ?? card.applicationReviewTotalScore,
    ),
    stageOneDataReady: Boolean(card.stage_one_data_ready ?? card.stageOneDataReady),
    dataCheckRunStatus: asStr(card.data_check_run_status ?? card.dataCheckRunStatus),
    interviewScheduledAtIso: asStr(card.interview_scheduled_at_iso ?? card.interviewScheduledAtIso),
  };
}

/** Default matches API max (200); avoids cards «missing» from Kanban when many applications exist. */
const COMMISSION_BOARD_LIST_LIMIT = "200";

function toParams(filters: CommissionBoardFilters): URLSearchParams {
  const p = new URLSearchParams();
  p.set("limit", COMMISSION_BOARD_LIST_LIMIT);
  if (filters.search.trim()) p.set("search", filters.search.trim());
  if (filters.program) p.set("program", filters.program);
  return p;
}

function defaultMetrics(cards: CommissionBoardApplicationCard[]): CommissionBoardMetrics {
  const today = new Date();
  const todayIso = `${today.getUTCFullYear()}-${String(today.getUTCMonth() + 1).padStart(2, "0")}-${String(today.getUTCDate()).padStart(2, "0")}`;

  const programBucket = (programValue: string | null | undefined): "foundation" | "bachelor" | "other" => {
    const raw = (programValue ?? "").trim().toLowerCase();
    if (!raw) return "other";
    if (raw.includes("foundation")) return "foundation";
    if (raw.includes("бак") || raw.includes("bachelor")) return "bachelor";
    return "other";
  };

  return {
    totalApplications: cards.length,
    todayApplications: cards.filter((c) => (c.submittedAt ?? "").startsWith(todayIso)).length,
    foundationApplications: cards.filter((c) => programBucket(c.program) === "foundation").length,
    bachelorApplications: cards.filter((c) => programBucket(c.program) === "bachelor").length,
  };
}

export async function getArchivedCommissionApplications(
  filters: Pick<CommissionBoardFilters, "search" | "program">,
): Promise<CommissionBoardApplicationCard[]> {
  const p = new URLSearchParams();
  if (filters.search.trim()) p.set("search", filters.search.trim());
  if (filters.program) p.set("program", filters.program);
  const q = p.toString();
  const rows = await apiFetch<ApiCard[]>(`/commission/applications/archived${q ? `?${q}` : ""}`);
  return rows.map(mapApiCard);
}

export async function getCommissionHistoryEvents(filters: {
  search: string;
  program: string | null;
  eventType: CommissionHistoryEventFilter;
  sort: CommissionHistorySort;
  limit?: number;
  offset?: number;
}): Promise<CommissionHistoryResponse> {
  const params = new URLSearchParams();
  if (filters.search.trim()) params.set("search", filters.search.trim());
  if (filters.program) params.set("program", filters.program);
  params.set("eventType", filters.eventType);
  params.set("sort", filters.sort);
  params.set("limit", String(Math.max(1, Math.min(filters.limit ?? 200, 500))));
  params.set("offset", String(Math.max(0, filters.offset ?? 0)));
  const payload = await apiFetch<Record<string, unknown>>(`/commission/history/events?${params.toString()}`);
  const itemsRaw = Array.isArray(payload.items) ? payload.items : [];
  const filtersRaw = (payload.filters as Record<string, unknown> | undefined) ?? {};
  return {
    items: itemsRaw.map((row) => mapHistoryEvent(row as Record<string, unknown>)),
    total: asNum(payload.total) ?? 0,
    filters: {
      search: String(filtersRaw.search ?? ""),
      program: asStr(filtersRaw.program),
      eventType: String(filtersRaw.eventType ?? "all") as CommissionHistoryEventFilter,
      sort: String(filtersRaw.sort ?? "newest") as CommissionHistorySort,
    },
  };
}

export async function getCommissionApplicationHistoryEvents(
  applicationId: string,
  filters: {
    eventType?: CommissionHistoryEventFilter;
    sort?: CommissionHistorySort;
    limit?: number;
    offset?: number;
  } = {},
): Promise<CommissionApplicationHistoryResponse> {
  const params = new URLSearchParams();
  params.set("eventType", filters.eventType ?? "all");
  params.set("sort", filters.sort ?? "newest");
  params.set("limit", String(Math.max(1, Math.min(filters.limit ?? 200, 500))));
  params.set("offset", String(Math.max(0, filters.offset ?? 0)));
  const payload = await apiFetch<Record<string, unknown>>(
    `/commission/applications/${applicationId}/history-events?${params.toString()}`,
  );
  const itemsRaw = Array.isArray(payload.items) ? payload.items : [];
  const filtersRaw = (payload.filters as Record<string, unknown> | undefined) ?? {};
  return {
    applicationId: String(payload.applicationId ?? payload.application_id ?? applicationId),
    items: itemsRaw.map((row) => mapHistoryEvent(row as Record<string, unknown>)),
    total: asNum(payload.total) ?? 0,
    filters: {
      eventType: String(filtersRaw.eventType ?? "all") as CommissionHistoryEventFilter,
      sort: String(filtersRaw.sort ?? "newest") as CommissionHistorySort,
    },
  };
}

export async function getBoardMetrics(filters: CommissionBoardFilters): Promise<CommissionBoardMetrics> {
  try {
    const params = new URLSearchParams();
    params.set("range", filters.range);
    if (filters.search.trim()) params.set("search", filters.search.trim());
    if (filters.program) params.set("program", filters.program);
    return await apiFetch<CommissionBoardMetrics>(`/commission/metrics?${params.toString()}`);
  } catch {
    // Fallback for old backend contract.
    const p = toParams(filters);
    const rows = await apiFetch<ApiCard[]>(`/commission/applications?${p.toString()}`);
    const cards = rows.map(mapApiCard);
    return defaultMetrics(cards);
  }
}

export async function getCommissionBoard(filters: CommissionBoardFilters): Promise<CommissionBoardResponse> {
  const rows = await apiFetch<ApiCard[]>(`/commission/applications?${toParams(filters).toString()}`);
  const cards = rows.map(mapApiCard);

  const columns = COMMISSION_STAGE_ORDER.map((stage) => ({
    stage,
    title: COMMISSION_STAGE_TITLES[stage],
    applications: sortColumnApplications(cards.filter((c) => c.currentStage === stage)),
  }));

  const metrics = await getBoardMetrics(filters);
  return { filters, columns, metrics };
}

export type CommissionMe = {
  userId: string;
  email: string | null;
  role: CommissionRole | null;
};

export async function getCommissionMe(): Promise<CommissionMe | null> {
  try {
    return await apiFetch<CommissionMe>("/commission/me");
  } catch {
    return null;
  }
}

export async function getCommissionRole(): Promise<CommissionRole | null> {
  const me = await getCommissionMe();
  return me?.role ?? null;
}

/** Поиск заявок для страницы «Документы» (без фильтра по колонке канбана). */
export async function searchCommissionApplicationsForDocuments(query: string): Promise<CommissionBoardApplicationCard[]> {
  const q = query.trim();
  if (!q) return [];
  const params = new URLSearchParams();
  params.set("search", q);
  params.set("limit", "200");
  const rows = await apiFetch<ApiCard[]>(`/commission/applications?${params.toString()}`);
  return rows.map(mapApiCard);
}

export async function getCommissionInterviewBoard(filters: InterviewBoardFilters): Promise<InterviewBoardColumn[]> {
  const p = new URLSearchParams();
  p.set("stage", "interview");
  p.set("interviewKanbanOnly", "true");
  p.set("limit", "200");
  if (filters.search.trim()) p.set("search", filters.search.trim());
  if (filters.program) p.set("program", filters.program);
  p.set("scope", filters.scope);
  const rows = await apiFetch<Record<string, unknown>[]>(`/commission/applications?${p.toString()}`);
  const cards = rows.map(mapApiRowToInterviewCard);
  return buildInterviewColumns(cards);
}

function mapEngagementCard(card: Record<string, unknown>): CommissionEngagementCard {
  const engagementRaw = String(card.engagementLevel ?? card.engagement_level ?? "Medium");
  const riskRaw = String(card.riskLevel ?? card.risk_level ?? "Medium");
  const engagementLevel: CommissionEngagementCard["engagementLevel"] =
    engagementRaw === "High" || engagementRaw === "Low" ? engagementRaw : "Medium";
  const riskLevel: CommissionEngagementCard["riskLevel"] =
    riskRaw === "High" || riskRaw === "Low" ? riskRaw : "Medium";
  const breakdown = (card.breakdown as Record<string, unknown> | undefined) ?? {};
  const activeTimeScore = asNum(breakdown.active_time_score ?? breakdown.activeTimeScore);
  const activeTimeHumanizedRaw = asStr(card.activeTimeHumanized ?? card.active_time_humanized);

  return {
    applicationId: String(card.applicationId ?? card.application_id ?? ""),
    candidateFullName: String(card.candidateFullName ?? card.candidate_full_name ?? "Кандидат"),
    lastActivityAtIso: asStr(card.lastActivityAtIso ?? card.last_activity_at_iso),
    lastActivityHumanized: String(card.lastActivityHumanized ?? card.last_activity_humanized ?? "нет активности"),
    activeTimeHumanized:
      activeTimeHumanizedRaw ??
      (activeTimeScore != null ? formatMinutesRu(activeTimeScore) : null),
    engagementLevel,
    riskLevel,
    program: asStr(card.program),
    currentStage: asStr(card.currentStage ?? card.current_stage),
  };
}

export async function getCommissionEngagementBoard(
  filters: {
    search: string;
    program: string | null;
    sort: CommissionEngagementSort;
    limit?: number;
    offset?: number;
  },
): Promise<CommissionEngagementResponse> {
  const params = new URLSearchParams();
  const q = filters.search.trim();
  if (q) params.set("search", q);
  if (filters.program) params.set("program", filters.program);
  params.set("sort", filters.sort);
  params.set("limit", String(Math.max(1, Math.min(filters.limit ?? 200, 200))));
  params.set("offset", String(Math.max(0, filters.offset ?? 0)));
  const payload = await apiFetch<Record<string, unknown>>(`/commission/engagement?${params.toString()}`);

  const rawFilters = (payload.filters as Record<string, unknown> | undefined) ?? {};
  const rawTotals = (payload.totals as Record<string, unknown> | undefined) ?? {};
  const rawColumns = Array.isArray(payload.columns) ? payload.columns : [];

  return {
    filters: {
      search: String(rawFilters.search ?? ""),
      program: asStr(rawFilters.program),
      sort: (String(rawFilters.sort ?? "risk") as CommissionEngagementSort),
    },
    totals: {
      total: asNum(rawTotals.total) ?? 0,
      highRisk: asNum(rawTotals.highRisk ?? rawTotals.high_risk) ?? 0,
      mediumRisk: asNum(rawTotals.mediumRisk ?? rawTotals.medium_risk) ?? 0,
      lowRisk: asNum(rawTotals.lowRisk ?? rawTotals.low_risk) ?? 0,
    },
    columns: rawColumns
      .map((col) => {
        const c = col as Record<string, unknown>;
        const idRaw = String(c.id ?? "");
        if (idRaw !== "high_risk" && idRaw !== "medium_risk" && idRaw !== "low_risk") return null;
        return {
          id: idRaw,
          title: String(c.title ?? ""),
          cards: (Array.isArray(c.cards) ? c.cards : []).map((r) => mapEngagementCard(r as Record<string, unknown>)),
        };
      })
      .filter((c): c is CommissionEngagementResponse["columns"][number] => c !== null),
  };
}

export async function getStageAdvancePreview(applicationId: string): Promise<StageAdvancePreviewResponse> {
  return await apiFetch<StageAdvancePreviewResponse>(
    `/commission/applications/${applicationId}/stage-advance-preview`,
  );
}

export async function moveApplicationToNextStage(applicationId: string, reasonComment?: string): Promise<void> {
  await apiFetch(`/commission/applications/${applicationId}/stage/advance`, {
    method: "POST",
    json: { reason_comment: reasonComment ?? null },
  });
}

export async function createQuickComment(applicationId: string, body: string): Promise<void> {
  await apiFetch(`/commission/applications/${applicationId}/comments`, {
    method: "POST",
    json: { body },
  });
}

export async function setAttentionFlag(applicationId: string, value: boolean, reasonComment?: string): Promise<void> {
  await apiFetch(`/commission/applications/${applicationId}/attention`, {
    method: "PATCH",
    json: { value, reason_comment: reasonComment ?? null },
  });
}

export async function getUpdates(cursor: string | null): Promise<CommissionUpdatesResponse> {
  const q = cursor ? `?cursor=${encodeURIComponent(cursor)}` : "";
  return await apiFetch<CommissionUpdatesResponse>(`/commission/updates${q}`);
}

export function rangeFromQuery(v: string | null): CommissionRange {
  if (v === "day" || v === "week" || v === "month" || v === "year") return v;
  return "week";
}

export async function getCommissionApplicationDetail(applicationId: string): Promise<CommissionApplicationDetailView> {
  return await apiFetch<CommissionApplicationDetailView>(`/commission/applications/${applicationId}`);
}

export async function getCommissionApplicationPersonalInfo(
  applicationId: string,
): Promise<CommissionApplicationPersonalInfoView> {
  return await apiFetch<CommissionApplicationPersonalInfoView>(`/commission/applications/${applicationId}/personal-info`);
}

export async function getApplicationAuditPreview(applicationId: string): Promise<CommissionApplicationDetailView["recentActivity"]> {
  return await apiFetch<CommissionApplicationDetailView["recentActivity"]>(`/commission/applications/${applicationId}/audit`);
}

export async function updateStageStatus(applicationId: string, status: string, reasonComment?: string): Promise<void> {
  await apiFetch(`/commission/applications/${applicationId}/stage-status`, {
    method: "PATCH",
    json: { status, reason_comment: reasonComment ?? null },
  });
}

export async function setFinalDecision(applicationId: string, finalDecision: string, reasonComment?: string): Promise<void> {
  await apiFetch(`/commission/applications/${applicationId}/final-decision`, {
    method: "POST",
    json: { final_decision: finalDecision, reason_comment: reasonComment ?? null },
  });
}

export async function setRubricScores(
  applicationId: string,
  items: Array<{ rubric: string; score: string }>,
  comment?: string,
): Promise<void> {
  await apiFetch(`/commission/applications/${applicationId}/rubric`, {
    method: "PUT",
    json: { items, comment: comment ?? null },
  });
}

export async function setInternalRecommendation(
  applicationId: string,
  recommendation: string,
  reasonComment?: string,
): Promise<void> {
  await apiFetch(`/commission/applications/${applicationId}/internal-recommendation`, {
    method: "PUT",
    json: { recommendation, reason_comment: reasonComment ?? null },
  });
}

export async function createApplicationComment(applicationId: string, body: string): Promise<void> {
  await apiFetch(`/commission/applications/${applicationId}/comments`, {
    method: "POST",
    json: { body },
  });
}

export type DeleteCommissionApplicationResult = {
  archivedApplicationId: string;
  newApplicationId: string;
};

export async function deleteCommissionApplication(applicationId: string): Promise<DeleteCommissionApplicationResult> {
  return await apiFetch<DeleteCommissionApplicationResult>(`/commission/applications/${applicationId}`, {
    method: "DELETE",
  });
}

export async function getCommissionApplicationTestInfo(
  applicationId: string,
): Promise<CommissionApplicationTestInfoView> {
  return await apiFetch<CommissionApplicationTestInfoView>(`/commission/applications/${applicationId}/test-info`);
}

export async function createCommissionComment(applicationId: string, body: string): Promise<void> {
  await createApplicationComment(applicationId, body);
}

const _TAB_TO_QUERY: Record<string, string> = {
  "Личная информация": "personal",
  "Тест": "test",
  "Мотивация": "motivation",
  "Путь": "path",
  "Достижения": "achievements",
};

export async function getCommissionSidebarPanel(
  applicationId: string,
  tab: string,
): Promise<CommissionSidebarPanelView> {
  const queryTab =
    tab === "ai_interview"
      ? "ai_interview"
      : tab === "engagement"
        ? "engagement"
        : (_TAB_TO_QUERY[tab] ?? "personal");
  return await apiFetch<CommissionSidebarPanelView>(
    `/commission/applications/${applicationId}/sidebar?tab=${encodeURIComponent(queryTab)}`,
  );
}

export async function getSectionReviewScores(
  applicationId: string,
  tab: string,
): Promise<ReviewScoreBlock> {
  const queryTab = _TAB_TO_QUERY[tab] ?? "personal";
  return await apiFetch<ReviewScoreBlock>(
    `/commission/applications/${applicationId}/section-scores?tab=${encodeURIComponent(queryTab)}`,
  );
}

export async function saveSectionReviewScores(
  applicationId: string,
  section: string,
  scores: Array<{ key: string; score: number }>,
): Promise<ReviewScoreBlock> {
  return await apiFetch<ReviewScoreBlock>(
    `/commission/applications/${applicationId}/section-scores`,
    {
      method: "PUT",
      json: { section, scores },
    },
  );
}

export async function getAiInterviewDraft(applicationId: string): Promise<AiInterviewDraftView> {
  return await apiFetch<AiInterviewDraftView>(`/commission/applications/${applicationId}/ai-interview/draft`);
}

export async function getCommissionAiInterviewCandidateSession(
  applicationId: string,
): Promise<CommissionAiInterviewSessionView> {
  return await apiFetch<CommissionAiInterviewSessionView>(
    `/commission/applications/${applicationId}/ai-interview/candidate-session`,
  );
}

export async function postCommissionInterviewSchedule(
  applicationId: string,
  body: {
    scheduledAt: string;
    interviewMode?: string | null;
    locationOrLink?: string | null;
  },
): Promise<{ ok: boolean; scheduledInterview: CommissionScheduledInterviewPayload }> {
  return await apiFetch(`/commission/applications/${applicationId}/commission-interview/schedule`, {
    method: "POST",
    json: {
      scheduledAt: body.scheduledAt,
      interviewMode: body.interviewMode ?? null,
      locationOrLink: body.locationOrLink ?? null,
    },
  });
}

export async function postCommissionInterviewOutcome(
  applicationId: string,
): Promise<{ ok: boolean; scheduledInterview: CommissionScheduledInterviewPayload }> {
  return await apiFetch(`/commission/applications/${applicationId}/commission-interview/outcome`, {
    method: "POST",
  });
}

export async function generateAiInterviewDraft(applicationId: string, force = false): Promise<AiInterviewDraftView> {
  return await apiFetch<AiInterviewDraftView>(`/commission/applications/${applicationId}/ai-interview/generate`, {
    method: "POST",
    json: { force },
  });
}

export async function patchAiInterviewDraft(
  applicationId: string,
  body: { revision: number; questions: Record<string, unknown>[] },
): Promise<AiInterviewDraftView> {
  return await apiFetch<AiInterviewDraftView>(`/commission/applications/${applicationId}/ai-interview/draft`, {
    method: "PATCH",
    json: body,
  });
}

export async function approveAiInterview(applicationId: string): Promise<Record<string, unknown>> {
  return await apiFetch<Record<string, unknown>>(`/commission/applications/${applicationId}/ai-interview/approve`, {
    method: "POST",
  });
}

/** Открыть файл документа в новой вкладке (inline, через blob + object URL). */
export async function openCommissionApplicationDocumentInNewTab(
  applicationId: string,
  documentId: string,
): Promise<void> {
  const preOpenedWindow = window.open("", "_blank");
  if (!preOpenedWindow) {
    throw new Error("Не удалось открыть новую вкладку. Разрешите всплывающие окна.");
  }
  try {
    const blob = await apiFetchBlob(
      `/commission/applications/${applicationId}/documents/${documentId}/file`,
    );
    if (blob.size === 0) {
      preOpenedWindow.close();
      throw new Error("Пустой файл — нечего открыть.");
    }
    const objectUrl = URL.createObjectURL(blob);
    preOpenedWindow.location.href = objectUrl;
  } catch (error) {
    preOpenedWindow.close();
    throw error;
  }
  // Не вызываем revokeObjectURL после открытия: встроенный PDF во второй вкладке может
  // обращаться к blob: URL ещё долго; любой отзыв до закрытия вкладки даёт Chrome ERR_FILE_NOT_FOUND (-6).
  // Один object URL на клик — приемлемая утечка до перезагрузки страницы комиссии.
}

/** Скачать файл документа (тот же blob, что и для просмотра). */
export async function downloadCommissionApplicationDocument(
  applicationId: string,
  documentId: string,
  fileName: string,
): Promise<void> {
  const blob = await apiFetchBlob(
    `/commission/applications/${applicationId}/documents/${documentId}/file`,
  );
  if (blob.size === 0) {
    throw new Error("Пустой файл — нечего скачать.");
  }
  const objectUrl = URL.createObjectURL(blob);
  try {
    const a = document.createElement("a");
    a.href = objectUrl;
    a.download = fileName || "document";
    a.rel = "noopener";
    document.body.appendChild(a);
    a.click();
    a.remove();
  } finally {
    window.setTimeout(() => URL.revokeObjectURL(objectUrl), 60_000);
  }
}

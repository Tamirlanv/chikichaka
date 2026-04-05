"use client";

import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from "react";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { PillSegmentedControl } from "@/components/application/PillSegmentedControl";
import { CandidateInterviewPreferencesForm } from "@/components/application/CandidateInterviewPreferencesForm";
import { ApiError, apiFetch, apiFetchCached } from "@/lib/api-client";
import { postCandidateActivityEventSafe } from "@/lib/candidate-activity";
import { isInterviewStage, type CandidateApplicationStatus } from "@/lib/candidate-status";
import {
  CommissionInterviewScheduledBanner,
  CommissionInterviewScheduledCard,
} from "@/components/application/CommissionInterviewScheduledCard";
import {
  getCandidateAiInterviewAnswers,
  getCandidateAiInterviewQuestions,
  getCandidateAiInterviewStatus,
  postCandidateAiInterviewAnswers,
  postCandidateAiInterviewComplete,
  postCommissionInterviewReminder,
  type AiInterviewCandidateQuestion,
  type PreferenceWindowPayload,
  type ScheduledInterviewPayload,
} from "@/lib/candidate-ai-interview";
import styles from "./interview-page.module.css";

const ME_TTL_MS = 5 * 60 * 1000;
const THINKING_DELAY_MS = 3500;
const THINKING_DELAY_REDUCED_MS = 200;

type InterviewTab = "ai" | "commission";

function PreferenceCountdown({ expiresAt, show }: { expiresAt: string | null; show: boolean }) {
  const [left, setLeft] = useState<number | null>(null);
  useEffect(() => {
    if (!show || !expiresAt) {
      setLeft(null);
      return;
    }
    const exp = new Date(expiresAt).getTime();
    const tick = () => setLeft(Math.max(0, Math.floor((exp - Date.now()) / 1000)));
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [expiresAt, show]);
  if (!show || left === null) return null;
  const m = Math.floor(left / 60);
  const sec = left % 60;
  return (
    <p style={{ margin: 0, fontSize: 14, color: "#626262" }}>
      Окно для отправки предпочтений: осталось {m} мин. {sec.toString().padStart(2, "0")} сек.
    </p>
  );
}

function useReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReduced(mq.matches);
    const listener = () => setReduced(mq.matches);
    mq.addEventListener("change", listener);
    return () => mq.removeEventListener("change", listener);
  }, []);
  return reduced;
}

export default function CandidateInterviewPage() {
  const router = useRouter();
  const [interviewTab, setInterviewTab] = useState<InterviewTab>("ai");
  const [firstName, setFirstName] = useState("");
  const [questions, setQuestions] = useState<AiInterviewCandidateQuestion[]>([]);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);
  const [thinking, setThinking] = useState(false);
  const [thinkingAfterQuestionId, setThinkingAfterQuestionId] = useState<string | null>(null);
  const [aiInterviewCompleted, setAiInterviewCompleted] = useState(false);
  const [preferencesSubmitted, setPreferencesSubmitted] = useState(false);
  const [preferenceWindow, setPreferenceWindow] = useState<PreferenceWindowPayload | null>(null);
  const [scheduledInterview, setScheduledInterview] = useState<ScheduledInterviewPayload | null>(null);
  const [finalizeError, setFinalizeError] = useState<string | null>(null);
  const [finalizePending, setFinalizePending] = useState(false);
  const messagesScrollRef = useRef<HTMLDivElement>(null);
  const thinkingTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const redirectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const finalizeOnceRef = useRef(false);
  const localAiCompleteRef = useRef(false);
  const interviewInfoLoggedRef = useRef(false);
  const interviewInstructionLoggedRef = useRef(false);
  const reducedMotion = useReducedMotion();
  const reducedMotionRef = useRef(false);
  reducedMotionRef.current = reducedMotion;
  const [statusSyncError, setStatusSyncError] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const stageCheck = await apiFetch<CandidateApplicationStatus>("/candidates/me/application/status");
      if (!isInterviewStage(stageCheck)) {
        router.replace("/application");
        return;
      }
      const [me, qData, aData] = await Promise.all([
        apiFetchCached<{ profile?: { first_name?: string } | null }>("/auth/me", ME_TTL_MS),
        getCandidateAiInterviewQuestions(),
        getCandidateAiInterviewAnswers().catch(() => ({ answers: [] as { questionId: string; text: string }[] })),
      ]);
      setFirstName(me.profile?.first_name?.trim() ?? "");
      setQuestions([...qData.questions].sort((a, b) => a.sortOrder - b.sortOrder));
      const map: Record<string, string> = {};
      for (const a of aData.answers) {
        map[a.questionId] = a.text;
      }
      setAnswers(map);
      try {
        const st = await getCandidateAiInterviewStatus();
        setStatusSyncError(false);
        setAiInterviewCompleted(st.aiInterviewCompleted);
        setPreferencesSubmitted(st.preferencesSubmitted);
        setPreferenceWindow(st.preferenceWindow ?? null);
        setScheduledInterview(st.scheduledInterview ?? null);
        if (st.aiInterviewCompleted) {
          finalizeOnceRef.current = true;
          setInterviewTab("commission");
        }
      } catch {
        setStatusSyncError(true);
        if (localAiCompleteRef.current) {
          setAiInterviewCompleted(true);
          finalizeOnceRef.current = true;
          setInterviewTab("commission");
        }
      }
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) {
        setQuestions([]);
        setAnswers({});
        setError(
          "Вопросы собеседования пока недоступны. Они появятся после того, как комиссия утвердит формулировки и вы перейдёте на этот этап.",
        );
      } else {
        setError(e instanceof Error ? e.message : "Не удалось загрузить данные");
      }
    } finally {
      setLoading(false);
    }
  }, [router]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    return () => {
      if (thinkingTimerRef.current) clearTimeout(thinkingTimerRef.current);
      if (redirectTimerRef.current) clearTimeout(redirectTimerRef.current);
    };
  }, []);

  useEffect(() => {
    if (interviewInfoLoggedRef.current) return;
    interviewInfoLoggedRef.current = true;
    void postCandidateActivityEventSafe({
      eventType: "interview_info_opened",
      metadata: { screen: "candidate_interview_page" },
    });
  }, []);

  useEffect(() => {
    if (interviewTab !== "commission" || interviewInstructionLoggedRef.current) return;
    interviewInstructionLoggedRef.current = true;
    void postCandidateActivityEventSafe({
      eventType: "interview_instruction_opened",
      metadata: { hasScheduledInterview: Boolean(scheduledInterview?.scheduledAt) },
    });
  }, [interviewTab, scheduledInterview?.scheduledAt]);

  const sorted = useMemo(() => [...questions].sort((a, b) => a.sortOrder - b.sortOrder), [questions]);

  const firstUnanswered = useMemo(() => {
    for (const q of sorted) {
      if (!answers[q.id]) return q;
    }
    return null;
  }, [sorted, answers]);

  const allAnswered = sorted.length > 0 && firstUnanswered === null;
  const displayName = firstName || "кандидат";

  const scrollMessagesToBottom = useCallback(() => {
    const el = messagesScrollRef.current;
    if (!el) return;
    requestAnimationFrame(() => {
      el.scrollTop = el.scrollHeight;
    });
  }, []);

  useEffect(() => {
    scrollMessagesToBottom();
  }, [answers, thinking, sorted.length, loading, scrollMessagesToBottom]);

  useEffect(() => {
    if (loading) return;
    if (!allAnswered || aiInterviewCompleted) return;
    if (finalizeOnceRef.current) return;
    finalizeOnceRef.current = true;
    void (async () => {
      setFinalizePending(true);
      setFinalizeError(null);
      try {
        await postCandidateAiInterviewComplete();
        localAiCompleteRef.current = true;
        setAiInterviewCompleted(true);
        const ms = reducedMotionRef.current ? 500 : 5000;
        if (redirectTimerRef.current) clearTimeout(redirectTimerRef.current);
        redirectTimerRef.current = setTimeout(() => {
          setInterviewTab("commission");
          redirectTimerRef.current = null;
        }, ms);
      } catch (e) {
        finalizeOnceRef.current = false;
        setFinalizeError(e instanceof Error ? e.message : "Не удалось зафиксировать результаты AI-собеседования");
      } finally {
        setFinalizePending(false);
      }
    })();
  }, [loading, allAnswered, aiInterviewCompleted]);

  useEffect(() => {
    if (interviewTab !== "commission" || scheduledInterview?.scheduledAt) return;
    const id = setInterval(() => void load(), 45000);
    return () => clearInterval(id);
  }, [interviewTab, scheduledInterview?.scheduledAt, load]);

  async function handleSend() {
    if (!firstUnanswered) return;
    const text = draft.trim();
    if (!text || sending || thinking || aiInterviewCompleted) return;
    const answeredQuestionId = firstUnanswered.id;
    const idx = sorted.findIndex((q) => q.id === answeredQuestionId);
    const hasNextQuestion = idx >= 0 && idx < sorted.length - 1;

    setSending(true);
    setSendError(null);
    try {
      await postCandidateAiInterviewAnswers({
        answers: [{ questionId: answeredQuestionId, text }],
      });
      setAnswers((prev) => ({ ...prev, [answeredQuestionId]: text }));
      setDraft("");

      if (hasNextQuestion) {
        const delay = reducedMotion ? THINKING_DELAY_REDUCED_MS : THINKING_DELAY_MS;
        setThinking(true);
        setThinkingAfterQuestionId(answeredQuestionId);
        if (thinkingTimerRef.current) clearTimeout(thinkingTimerRef.current);
        thinkingTimerRef.current = setTimeout(() => {
          setThinking(false);
          setThinkingAfterQuestionId(null);
          thinkingTimerRef.current = null;
        }, delay);
      }
    } catch (e) {
      setSendError(e instanceof Error ? e.message : "Не удалось отправить ответ");
    } finally {
      setSending(false);
    }
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void handleSend();
    }
  }

  async function retryFinalize() {
    setFinalizeError(null);
    finalizeOnceRef.current = false;
    try {
      await postCandidateAiInterviewComplete();
      localAiCompleteRef.current = true;
      setAiInterviewCompleted(true);
      finalizeOnceRef.current = true;
      const ms = reducedMotionRef.current ? 500 : 5000;
      if (redirectTimerRef.current) clearTimeout(redirectTimerRef.current);
      redirectTimerRef.current = setTimeout(() => {
        setInterviewTab("commission");
        redirectTimerRef.current = null;
      }, ms);
    } catch (e) {
      setFinalizeError(e instanceof Error ? e.message : "Ошибка");
    }
  }

  const showAiChat = !loading && !error && sorted.length > 0;
  const inputLocked = sending || thinking || aiInterviewCompleted || finalizePending || allAnswered;

  return (
    <div className={styles.wrap}>
      <h2 className={styles.sectionTitle}>Собеседование</h2>

      {statusSyncError ? (
        <p role="status" style={{ margin: "0 0 12px", fontSize: 14, color: "#856404" }}>
          Не удалось загрузить статус собеседования.{" "}
          <button
            type="button"
            onClick={() => void load()}
            style={{
              padding: "4px 10px",
              borderRadius: 8,
              border: "1px solid #98da00",
              background: "#fff",
              cursor: "pointer",
            }}
          >
            Повторить
          </button>
        </p>
      ) : null}

      <PillSegmentedControl
        aria-label="Тип собеседования"
        gap="tabs"
        options={[
          { value: "ai", label: "AI собеседование" },
          {
            value: "commission",
            label: "Собеседование с комиссией",
            disabled: !aiInterviewCompleted,
          },
        ]}
        value={interviewTab}
        onChange={(v) => setInterviewTab(v as InterviewTab)}
      />

      {interviewTab === "ai" ? (
        <>
          <div className={styles.introBlock}>
            <h3 className={styles.subsectionTitle}>Индивидуальные вопросы</h3>
            <p className={styles.lead}>
              На основе ваших данных в анкете составлено несколько вопросов, чтобы узнать недостающую информацию
            </p>
          </div>

          <hr className={styles.divider} />

          {loading ? <p className="muted">Загрузка…</p> : null}
          {!loading && error ? <p className={styles.notice}>{error}</p> : null}

          {showAiChat ? (
            <section className={styles.chatViewport} aria-label="Переписка AI-собеседования">
              <div className={styles.messagesScrollWrap}>
                <div className={styles.messagesGradient} aria-hidden />
                <div ref={messagesScrollRef} className={styles.messagesScroll} tabIndex={0}>
                  <div className={styles.messagesInner}>
                    <div className={`${styles.bubbleAssistant} ${styles.bubbleEnter}`}>
                      <p className={styles.bubbleAssistantText}>
                        Здравствуйте, {displayName}!{"\n"}Я – умный ассистент inVision U, и сейчас пройдем с вами небольшое
                        собеседование, прошу отвечать честно и по теме вопроса
                      </p>
                    </div>

                    {sorted.map((q, i) => {
                      const unlocked = i === 0 || sorted.slice(0, i).every((pq) => answers[pq.id]);
                      if (!unlocked) return null;

                      const hideNextQuestion =
                        thinking && firstUnanswered && q.id === firstUnanswered.id && answers[q.id] === undefined;

                      return (
                        <Fragment key={q.id}>
                          {!hideNextQuestion ? (
                            <div className={`${styles.bubbleAssistant} ${styles.bubbleEnter}`}>
                              <p className={styles.bubbleAssistantLabel}>Вопрос {i + 1}</p>
                              <p className={styles.bubbleAssistantText}>{q.questionText}</p>
                            </div>
                          ) : null}

                          {answers[q.id] ? (
                            <>
                              <div className={`${styles.bubbleUser} ${styles.bubbleEnter}`}>
                                <p className={styles.bubbleUserLabel}>Ваш ответ</p>
                                <p className={styles.bubbleUserText}>{answers[q.id]}</p>
                              </div>
                              {thinking && thinkingAfterQuestionId === q.id ? (
                                <p className={styles.thinkingLine}>Думаю…</p>
                              ) : null}
                            </>
                          ) : null}
                        </Fragment>
                      );
                    })}

                    {allAnswered ? (
                      <div className={`${styles.bubbleAssistant} ${styles.bubbleEnter}`} style={{ marginTop: 8 }}>
                        <p className={styles.bubbleAssistantText}>
                          Большое спасибо за ваши ответы. Желаем удачи на собеседовании с комиссией!
                        </p>
                        {finalizePending ? <p className={styles.thinkingLine}>Сохраняем результаты…</p> : null}
                        {finalizeError ? (
                          <div style={{ marginTop: 12 }}>
                            <p style={{ margin: "0 0 8px", color: "#c62828", fontSize: 14 }}>{finalizeError}</p>
                            <button
                              type="button"
                              style={{
                                padding: "8px 14px",
                                borderRadius: 10,
                                border: "1px solid #98da00",
                                background: "#fff",
                                cursor: "pointer",
                              }}
                              onClick={() => void retryFinalize()}
                            >
                              Повторить сохранение
                            </button>
                          </div>
                        ) : null}
                      </div>
                    ) : null}
                  </div>
                </div>
              </div>

              {!allAnswered && firstUnanswered ? (
                <div className={styles.composer}>
                  <div className={styles.inputBlock}>
                    <div className={styles.inputWrap}>
                      <input
                        className={styles.inputField}
                        type="text"
                        placeholder="Введите ответ"
                        value={draft}
                        onChange={(e) => setDraft(e.target.value)}
                        onKeyDown={onKeyDown}
                        disabled={inputLocked}
                        aria-label="Текст ответа"
                      />
                      <button
                        type="button"
                        className={styles.sendBtn}
                        aria-label="Отправить ответ"
                        disabled={inputLocked || !draft.trim()}
                        onClick={() => void handleSend()}
                      >
                        <Image src="/assets/icons/iconamoon_send-fill.svg" alt="" width={14} height={14} />
                      </button>
                    </div>
                    {sendError ? <p className="muted" style={{ color: "#c62828", margin: 0 }}>{sendError}</p> : null}
                    <p className={styles.disclaimer}>
                      Пожалуйста, отвечайте честно, спокойно и по существу — AI-собеседование нужно для уточнения вашей
                      заявки.{"\n"}
                      Не используйте оскорбления, намеренно ложные ответы и посторонние материалы, которые не отражают ваш
                      реальный опыт
                    </p>
                  </div>
                </div>
              ) : null}
            </section>
          ) : null}

          {!loading && !error && sorted.length === 0 ? <p className="muted">Список вопросов пуст.</p> : null}
        </>
      ) : (
        <div style={{ marginTop: 24, display: "grid", gap: 16 }}>
          {scheduledInterview?.scheduledAt ? (
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                gap: 24,
                alignItems: "center",
                width: "100%",
              }}
            >
              <CommissionInterviewScheduledBanner />
              <CommissionInterviewScheduledCard
                scheduledAt={scheduledInterview.scheduledAt}
                interviewMode={scheduledInterview.interviewMode}
                locationOrLink={scheduledInterview.locationOrLink}
                reminderRequestedAt={scheduledInterview.reminderRequestedAt ?? null}
                reminderSentAt={scheduledInterview.reminderSentAt ?? null}
                onRequestReminder={async () => {
                  await postCommissionInterviewReminder();
                  const st = await getCandidateAiInterviewStatus();
                  setScheduledInterview(st.scheduledInterview ?? null);
                  setPreferenceWindow(st.preferenceWindow ?? null);
                  setPreferencesSubmitted(st.preferencesSubmitted);
                }}
              />
            </div>
          ) : preferencesSubmitted ? (
            <p style={{ margin: 0, fontSize: 14, color: "#262626", lineHeight: 1.5 }}>
              Спасибо! Ваши предпочтения по времени переданы комиссии. Окончательную дату, время и ссылку на встречу
              назначит комиссия — они появятся здесь после назначения.
            </p>
          ) : (
            <>
              <PreferenceCountdown
                expiresAt={preferenceWindow?.expiresAt ?? null}
                show={
                  preferenceWindow?.status === "awaiting_candidate_preferences" &&
                  Boolean(preferenceWindow?.expiresAt)
                }
              />
              <CandidateInterviewPreferencesForm
                disabled={!aiInterviewCompleted}
                onConflict={() => void load()}
                onSubmitted={async () => {
                  setPreferencesSubmitted(true);
                  try {
                    const st = await getCandidateAiInterviewStatus();
                    setPreferencesSubmitted(st.preferencesSubmitted);
                    setPreferenceWindow(st.preferenceWindow ?? null);
                    setScheduledInterview(st.scheduledInterview ?? null);
                  } catch {
                    setPreferencesSubmitted(true);
                  }
                }}
              />
            </>
          )}
        </div>
      )}
    </div>
  );
}

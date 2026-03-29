"use client";

import { useEffect, useState } from "react";
import { CAMPAIGN_DURATION_MS, getAdmissionDeadlineMs } from "@/lib/deadline";
import styles from "./application-sidebar.module.css";

const PIPELINE_STEPS = [
  "Подача анкеты",
  "Проверка данных",
  "Оценка заявки",
  "Собеседование",
  "Решение комиссии",
  "Результат",
] as const;

const DOC_CHECKLIST = [
  "Паспорт/ID",
  "Презентация",
  "Результаты теста на знание английского языка",
  "Результаты ЕНТ/Сертификат 12 классов NIS",
];

/** Индекс текущего этапа (0…5); позже можно подставить из API. */
const ACTIVE_STEP_INDEX = 0;

function StepDot({ active }: { active: boolean }) {
  return (
    <svg
      className={styles.stepDot}
      width={14}
      height={14}
      viewBox="0 0 14 14"
      fill="none"
      aria-hidden
    >
      <circle cx="7" cy="7" r="7" fill={active ? "#98DA00" : "#E1E1E1"} />
    </svg>
  );
}

/** Радиус кольца в viewBox 56×56, stroke 6 — как в макете */
const R = 24;
const STROKE = 6;
const CIRC = 2 * Math.PI * R;

function useDeadlineCountdown() {
  const [parts, setParts] = useState({ d: 0, h: 0, m: 0 });
  const [ringRatio, setRingRatio] = useState(1);

  useEffect(() => {
    const end = getAdmissionDeadlineMs();
    const tick = () => {
      const now = Date.now();
      const diff = Math.max(0, end - now);
      const d = Math.floor(diff / (24 * 60 * 60 * 1000));
      const h = Math.floor((diff % (24 * 60 * 60 * 1000)) / (60 * 60 * 1000));
      const m = Math.floor((diff % (60 * 60 * 1000)) / (60 * 1000));
      setParts({ d, h, m });
      const remainingRatio = Math.min(1, Math.max(0, diff / CAMPAIGN_DURATION_MS));
      setRingRatio(Number.isFinite(remainingRatio) ? remainingRatio : 0);
    };
    tick();
    const id = window.setInterval(tick, 1000);
    return () => window.clearInterval(id);
  }, []);

  return { parts, ringRatio };
}

export function ApplicationSidebar() {
  const { parts, ringRatio } = useDeadlineCountdown();
  const offset = CIRC * (1 - ringRatio);
  const activeLabel = PIPELINE_STEPS[ACTIVE_STEP_INDEX];
  const followingSteps = PIPELINE_STEPS.slice(ACTIVE_STEP_INDEX + 1);

  return (
    <aside className={styles.sidebar}>
      <div className={styles.deadlineCard}>
        <div className={styles.deadlineLeft}>
          <h3 className={styles.deadlineTitle}>Срок подачи заявки</h3>
          <div className={styles.timerRow}>
            <img
              src="/assets/icons/ic_round-timer.svg"
              alt=""
              width={24}
              height={24}
              className={styles.timerIcon}
            />
            <div className={styles.timerDigits}>
              <span>{parts.d} д</span>
              <span>{parts.h} ч</span>
              <span>{parts.m} м</span>
            </div>
          </div>
        </div>
        <div className={styles.circularWrap} aria-hidden>
          <svg width="56" height="56" viewBox="0 0 56 56">
            <circle cx="28" cy="28" r={R} fill="none" stroke="#f1f1f1" strokeWidth={STROKE} />
            <circle
              cx="28"
              cy="28"
              r={R}
              fill="none"
              stroke="#98da00"
              strokeWidth={STROKE}
              strokeLinecap="round"
              strokeDasharray={CIRC}
              strokeDashoffset={offset}
              transform="rotate(-90 28 28)"
              className={styles.progressArc}
            />
          </svg>
        </div>
      </div>

      <div className={styles.stepsCard}>
        <div className={styles.stepsRow}>
          <div className={styles.stepsListContainer}>
            <div className={styles.stepsTitleRow}>
              <p className={styles.stepsTitleText}>Этап</p>
              <p className={styles.stepsTitleText}>
                {ACTIVE_STEP_INDEX + 1}/{PIPELINE_STEPS.length}
              </p>
            </div>
            <div className={styles.stepList}>
              <div className={styles.stepItem}>
                <StepDot active />
                <p className={styles.labelActive}>{activeLabel}</p>
              </div>
              {followingSteps.length > 0 ? (
                <div className={styles.lowerSteps}>
                  <div className={styles.connectorOverlay} aria-hidden>
                    <div className={styles.connectorRotate}>
                      <svg
                        viewBox="0 0 24 4"
                        fill="none"
                        preserveAspectRatio="none"
                        className={styles.connectorSvg}
                      >
                        <path
                          d="M2 2H22"
                          stroke="#98DA00"
                          strokeWidth="4"
                          strokeLinecap="round"
                          strokeDasharray="0.1 12"
                        />
                      </svg>
                    </div>
                  </div>
                  <div className={styles.stepItemList}>
                    {followingSteps.map((label) => (
                      <div key={label} className={styles.stepItem}>
                        <StepDot active={false} />
                        <p className={styles.labelInactive}>{label}</p>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}
            </div>
          </div>
        </div>
      </div>

      <div className={styles.card}>
        <h3 className={styles.cardTitle}>Документы</h3>
        <div className={styles.documentsList}>
          {DOC_CHECKLIST.map((t) => (
            <div key={t} className={styles.docItem}>
              {t}
            </div>
          ))}
        </div>
      </div>
    </aside>
  );
}

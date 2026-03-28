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

const R = 24;
const CIRC = 2 * Math.PI * R;

function useDeadlineCountdown() {
  const [parts, setParts] = useState({ d: 0, h: 0, m: 0, s: 0 });
  const [ringRatio, setRingRatio] = useState(1);

  useEffect(() => {
    const end = getAdmissionDeadlineMs();
    const tick = () => {
      const now = Date.now();
      const diff = Math.max(0, end - now);
      const d = Math.floor(diff / (24 * 60 * 60 * 1000));
      const h = Math.floor((diff % (24 * 60 * 60 * 1000)) / (60 * 60 * 1000));
      const m = Math.floor((diff % (60 * 60 * 1000)) / (60 * 1000));
      const s = Math.floor((diff % (60 * 1000)) / 1000);
      setParts({ d, h, m, s });
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

  return (
    <aside className={styles.sidebar}>
      <div className={styles.card}>
        <h3 className={styles.cardTitle}>Срок подачи заявки</h3>
        <div className={styles.deadlineRow}>
          <div className={styles.timer}>
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
              <span>{parts.s} с</span>
            </div>
          </div>
          <div className={styles.circularWrap} aria-hidden>
            <svg width="56" height="56" viewBox="0 0 56 56">
              <circle cx="28" cy="28" r={R} fill="none" stroke="#f1f1f1" strokeWidth="4" />
              <circle
                cx="28"
                cy="28"
                r={R}
                fill="none"
                stroke="#98da00"
                strokeWidth="4"
                strokeLinecap="round"
                strokeDasharray={CIRC}
                strokeDashoffset={offset}
                transform="rotate(-90 28 28)"
                className={styles.progressArc}
              />
            </svg>
          </div>
        </div>
      </div>

      <div className={styles.card}>
        <h3 className={styles.stepsTitle}>
          Этап <span>1</span> / <span>6</span>
        </h3>
        <div className={styles.stepsList}>
          {PIPELINE_STEPS.map((label, i) => (
            <div
              key={label}
              className={`${styles.step} ${i === 0 ? styles.stepActive : ""}`}
            >
              <div className={styles.dotCol}>
                <span className={styles.stepDot} />
              </div>
              <p className={styles.stepText}>{label}</p>
            </div>
          ))}
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

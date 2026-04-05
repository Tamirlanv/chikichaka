"use client";

import { useCallback, useEffect, useState } from "react";
import { postCandidateActivityEventSafe } from "@/lib/candidate-activity";
import { detectVideoPlatformFromUrl } from "@/lib/videoPlatformFromLink";
import styles from "./CommissionInterviewScheduledCard.module.css";

function capitalizeRu(s: string): string {
  if (!s) return s;
  return s.charAt(0).toUpperCase() + s.slice(1);
}

/** «14 апреля, вторник» → «14 Апреля, Вторник» */
export function formatScheduledInterviewDateLine(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  const day = d.getDate();
  const month = capitalizeRu(
    d.toLocaleDateString("ru-RU", { month: "long" }),
  );
  const weekday = capitalizeRu(d.toLocaleDateString("ru-RU", { weekday: "long" }));
  return `${day} ${month}, ${weekday}`;
}

/** Окно 1 ч от scheduledAt (как слот комиссии). */
export function formatScheduledInterviewTimeRange(iso: string): string {
  const start = new Date(iso);
  if (Number.isNaN(start.getTime())) return "—";
  const end = new Date(start.getTime() + 60 * 60 * 1000);
  const tf = new Intl.DateTimeFormat("ru-RU", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
  return `${tf.format(start)}–${tf.format(end)}`;
}

function CopyIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden>
      <path
        d="M4.667 2.333h5.833c.644 0 1.167.522 1.167 1.167v5.833h-1.167V3.5H4.667V2.333z"
        fill="currentColor"
      />
      <path
        d="M2.333 4.667h5.833c.644 0 1.167.522 1.167 1.167v5.833c0 .645-.523 1.167-1.167 1.167H2.333A1.167 1.167 0 011.167 11.5V5.833c0-.645.523-1.167 1.166-1.167z"
        fill="currentColor"
      />
    </svg>
  );
}

function CheckIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden>
      <polyline
        points="3,7 6,10 11,4"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

type Props = {
  scheduledAt: string;
  interviewMode: string | null;
  locationOrLink: string | null;
  reminderRequestedAt: string | null;
  reminderSentAt: string | null;
  onRequestReminder: () => Promise<void>;
};

export function CommissionInterviewScheduledCard({
  scheduledAt,
  interviewMode,
  locationOrLink,
  reminderRequestedAt,
  reminderSentAt,
  onRequestReminder,
}: Props) {
  const [pending, setPending] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const requested = Boolean(reminderRequestedAt || reminderSentAt);
  const link = (locationOrLink || "").trim();
  const isHttpLink = /^https?:\/\//i.test(link);
  const fromLink = detectVideoPlatformFromUrl(link);
  const platform = fromLink || (interviewMode || "").trim() || "—";

  useEffect(() => {
    if (!copied) return;
    const t = window.setTimeout(() => setCopied(false), 5000);
    return () => window.clearTimeout(t);
  }, [copied]);

  const copyLink = useCallback(async () => {
    if (!link) return;
    try {
      await navigator.clipboard.writeText(link);
      setErr(null);
      setCopied(true);
      let host: string | null = null;
      try {
        host = new URL(link).host;
      } catch {
        host = null;
      }
      void postCandidateActivityEventSafe({
        eventType: "interview_link_copied",
        metadata: host ? { host } : undefined,
      });
    } catch {
      setErr("Не удалось скопировать");
    }
  }, [link]);

  async function onRemind() {
    if (requested || pending) return;
    setErr(null);
    setPending(true);
    try {
      await onRequestReminder();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Не удалось сохранить");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className={styles.wrap}>
      <p className={styles.title}>О собеседовании</p>

      <div className={styles.rows}>
        <div className={styles.field}>
          <p className={styles.fieldLabel}>Дата</p>
          <div className={styles.dateRow}>
            <span>{formatScheduledInterviewDateLine(scheduledAt)}</span>
            <span>{formatScheduledInterviewTimeRange(scheduledAt)}</span>
          </div>
        </div>

        <div className={styles.field}>
          <p className={styles.fieldLabel}>Платформа</p>
          <p className={styles.valuePlain}>{platform}</p>
        </div>

        <div className={styles.field}>
          <p className={styles.fieldLabel}>Ссылка</p>
          <div className={styles.linkRow}>
            {isHttpLink ? (
              <a
                className={styles.linkText}
                title={link}
                href={link}
                target="_blank"
                rel="noopener noreferrer"
                onClick={() => {
                  let host: string | null = null;
                  try {
                    host = new URL(link).host;
                  } catch {
                    host = null;
                  }
                  void postCandidateActivityEventSafe({
                    eventType: "interview_link_opened",
                    metadata: host ? { host } : undefined,
                  });
                }}
              >
                {link}
              </a>
            ) : (
              <span className={styles.linkText} title={link || undefined}>
                {link || "—"}
              </span>
            )}
            {link ? (
              <button
                type="button"
                className={styles.copyBtn}
                onClick={() => void copyLink()}
                aria-label={copied ? "Скопировано" : "Копировать ссылку"}
              >
                {copied ? <CheckIcon /> : <CopyIcon />}
              </button>
            ) : null}
          </div>
        </div>
      </div>

      {err ? (
        <p style={{ margin: 0, fontSize: 14, color: "#c62828", width: "100%", textAlign: "center" }}>{err}</p>
      ) : null}

      <button type="button" className={styles.remindBtn} disabled={requested || pending} onClick={() => void onRemind()}>
        {pending ? "Отправка…" : requested ? "Напоминание запланировано" : "Напомнить"}
      </button>

      <p className={styles.hint}>
        &quot;Напомнить&quot; – на почту придет сообщение за 3 часа до начала
      </p>
    </div>
  );
}

export function CommissionInterviewScheduledBanner() {
  return (
    <div className={styles.banner}>
      <h3 className={styles.bannerTitle}>Назначено собеседование!</h3>
      <p className={styles.bannerLead}>
        Поздравляем — комиссия назначила время. Ниже дата, платформа и ссылка на встречу. Вы можете запросить письмо-напоминание
        на почту за три часа до начала.
      </p>
    </div>
  );
}

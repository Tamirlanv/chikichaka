"use client";

import { useEffect, useMemo, useState } from "react";
import type { VideoPreviewMeta } from "@/lib/commission/video-review";
import styles from "./video-candidate-drawer.module.css";

type Props = {
  open: boolean;
  onClose: () => void;
  duration: string | null;
  summary: string | null;
  notes: string[];
  preview: VideoPreviewMeta;
  recommendedScore: number | null;
  currentScore: number | null;
  canEditScore: boolean;
  scoreLoading: boolean;
  scoreSaving: boolean;
  onSaveScore: (score: number) => Promise<void>;
};

const SCORE_TRACK = "#f1f1f1";
const SCORE_FILL = "#98da00";

export function VideoCandidateDrawer({
  open,
  onClose,
  duration,
  summary,
  notes,
  preview,
  recommendedScore,
  currentScore,
  canEditScore,
  scoreLoading,
  scoreSaving,
  onSaveScore,
}: Props) {
  const ANIMATION_MS = 220;
  const [isMounted, setIsMounted] = useState(open);
  const baselineScore = useMemo(() => currentScore ?? recommendedScore ?? 3, [currentScore, recommendedScore]);
  const [selectedScore, setSelectedScore] = useState<number>(baselineScore);
  const fallbackText = "Не удалось обработать данные";
  const durationText = duration?.trim() ? duration : fallbackText;
  const platformText = preview.platformLabel?.trim() && preview.platformLabel !== "Не определена"
    ? preview.platformLabel
    : fallbackText;
  const summaryText = summary?.trim() ? summary : fallbackText;
  const hasNotes = notes.length > 0;

  useEffect(() => {
    if (!open) return;
    setSelectedScore(baselineScore);
  }, [open, baselineScore]);

  useEffect(() => {
    if (open) {
      setIsMounted(true);
      return;
    }
    const timer = window.setTimeout(() => setIsMounted(false), ANIMATION_MS);
    return () => window.clearTimeout(timer);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  if (!isMounted) return null;

  const hasChanges = selectedScore !== baselineScore;
  const isEditEnabled = canEditScore && !scoreLoading;
  const canSubmit = isEditEnabled && !scoreSaving && hasChanges;
  const overlayClassName = `${styles.videoDrawerOverlay} ${
    open ? styles.videoDrawerOverlayOpen : styles.videoDrawerOverlayClosed
  }`;
  const drawerClassName = `${styles.videoDrawer} ${open ? styles.videoDrawerOpen : styles.videoDrawerClosed}`;

  return (
    <div
      className={overlayClassName}
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
      role="presentation"
      aria-hidden={!open}
    >
      <aside className={drawerClassName} role="dialog" aria-modal="true" aria-label="Видео кандидата">
        <button type="button" className={styles.videoDrawerCloseBtn} onClick={onClose} aria-label="Закрыть панель">
          ×
        </button>

        <div className={styles.videoDrawerHeader}>
          <p className={styles.videoDrawerTitle}>Видео кандидата</p>
          <p className={styles.videoDrawerSubtitle}>Информация и выводы по итогам видео</p>
        </div>

        <section className={styles.videoDrawerSection}>
          <p className={styles.videoDrawerSectionTitle}>Общее</p>
          <div className={styles.videoDrawerMetaRows}>
            <p className={styles.videoDrawerMetaLine}>
              <span className={styles.videoDrawerMetaLabel}>Длительность:</span> <span>{durationText}</span>
            </p>
            <p className={styles.videoDrawerMetaLine}>
              <span className={styles.videoDrawerMetaLabel}>Платформа:</span> <span>{platformText}</span>
            </p>
          </div>
        </section>

        <section className={styles.videoDrawerSection}>
          <p className={styles.videoDrawerSectionTitle}>О видео</p>
          <p className={styles.videoDrawerBodyText}>{summaryText}</p>
        </section>

        <section className={styles.videoDrawerSection}>
          <p className={styles.videoDrawerSectionTitle}>Важно</p>
          {hasNotes ? (
            <ol className={styles.videoDrawerNotesList}>
              {notes.map((note, idx) => (
                <li key={`${idx}-${note}`}>{note}</li>
              ))}
            </ol>
          ) : (
            <p className={styles.videoDrawerBodyText}>{fallbackText}</p>
          )}
        </section>

        <section className={styles.videoDrawerSection}>
          <p className={styles.videoDrawerSectionTitle}>Предпросмотр</p>
          {preview.previewKind === "youtube" && preview.previewUrl ? (
            <div className={styles.videoDrawerPreviewFrame}>
              <iframe
                title="Видео-презентация кандидата"
                src={preview.previewUrl}
                allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
                allowFullScreen
              />
            </div>
          ) : null}
          {preview.previewKind === "direct" && preview.previewUrl ? (
            <div className={styles.videoDrawerPreviewFrame}>
              <video controls src={preview.previewUrl} />
            </div>
          ) : null}
          {preview.previewKind === "external" ? (
            <div className={styles.videoDrawerPreviewFallback}>
              <span>Предпросмотр недоступен для встроенного плеера</span>
              {preview.externalUrl ? (
                <a href={preview.externalUrl} target="_blank" rel="noreferrer">
                  Открыть видео
                </a>
              ) : null}
            </div>
          ) : null}
        </section>

        <section className={styles.videoDrawerSection}>
          <p className={styles.videoDrawerSectionTitle}>Оценка</p>
          <p className={styles.videoDrawerMetaLine}>
            <span>Рекомендуемая оценка:</span> <span>{recommendedScore ?? "–"}</span>
          </p>
          <p className={styles.videoDrawerMutedText}>Установите итоговую оценку по данному разделу</p>

          <div className={styles.videoDrawerScoreDots} role="radiogroup" aria-label="Оценка видео">
            {Array.from({ length: 5 }, (_, index) => {
              const value = index + 1;
              const filled = value <= selectedScore;
              return (
                <button
                  key={value}
                  type="button"
                  role="radio"
                  aria-checked={selectedScore === value}
                  aria-label={`Оценка ${value}`}
                  disabled={!isEditEnabled || scoreSaving}
                  onClick={() => setSelectedScore(value)}
                  style={{ background: filled ? SCORE_FILL : SCORE_TRACK }}
                />
              );
            })}
          </div>

          {isEditEnabled ? (
            <div className={styles.videoDrawerActions}>
              <button
                type="button"
                className={styles.videoDrawerPrimaryBtn}
                onClick={() => void onSaveScore(selectedScore)}
                disabled={!canSubmit}
              >
                {scoreSaving ? "Сохранение..." : "Установить"}
              </button>
              <button
                type="button"
                className={styles.videoDrawerSecondaryBtn}
                onClick={() => setSelectedScore(baselineScore)}
                disabled={scoreSaving || !hasChanges}
              >
                Отмена
              </button>
            </div>
          ) : scoreLoading ? (
            <p className={styles.videoDrawerMutedText}>Загрузка оценок...</p>
          ) : (
            <p className={styles.videoDrawerMutedText}>
              Оценка в этом разделе доступна после перехода на этап «Оценка заявки».
            </p>
          )}
        </section>
      </aside>
    </div>
  );
}

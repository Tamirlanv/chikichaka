"use client";

import type { CandidateApplicationStatus } from "@/lib/candidate-status";
import {
  FALLBACK_APPLICATION_REVIEW_CENTER,
  buildApplicationReviewCopy,
} from "@/lib/application-review-copy";
import styles from "./data-verification-view.module.css";

type Props = {
  status: CandidateApplicationStatus | null;
};

/**
 * Экран кандидата на этапе «Оценка заявки» (третий этап воронки после подачи и проверки данных).
 */
export function ApplicationReviewView({ status }: Props) {
  const { centerBody, etaLine } = buildApplicationReviewCopy(status);
  const useStructuredFallback = centerBody.trim() === FALLBACK_APPLICATION_REVIEW_CENTER.trim();

  return (
    <section className={styles.root}>
      <div className={styles.stageBlock}>
        <h2 className={styles.stageTitle}>Оценка заявки</h2>
        <div className={styles.stageChipShell}>
          <div className={styles.stageChip}>Модерация</div>
        </div>
      </div>

      <div className={styles.centerBlock}>
        <h3 className={styles.centerTitle}>Ваша анкета на этапе оценки</h3>
        {useStructuredFallback ? (
          <div className={styles.centerTextFallback}>
            <p className={styles.centerText}>
              Прошу ожидайте, ваши данные сейчас на этапе оценивания модерацией.
            </p>
            <p className={styles.centerText}>
              По окончании этапа на{" "}
              <span className={styles.centerTextEmphasis}>вашу почту придет сообщение о статусе заявки</span>
            </p>
          </div>
        ) : (
          <p className={styles.centerText}>{centerBody}</p>
        )}
        <p className={styles.etaText}>{etaLine}</p>
      </div>
    </section>
  );
}

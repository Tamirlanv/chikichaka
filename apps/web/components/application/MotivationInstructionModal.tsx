"use client";

import { useEffect, useId, useState } from "react";
import { createPortal } from "react-dom";
import styles from "./presentation-instruction-modal.module.css";

type Props = {
  open: boolean;
  onClose: () => void;
};

export function MotivationInstructionModal({ open, onClose }: Props) {
  const [mounted, setMounted] = useState(false);
  const titleId = useId();

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (!open) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!mounted || !open) return null;

  return createPortal(
    <div className={styles.backdrop} role="presentation" onClick={onClose}>
      <div
        className={styles.panel}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        onClick={(e) => e.stopPropagation()}
      >
        <h2 id={titleId} className={styles.title}>
          Что желательно отразить в письме
        </h2>

        <ul className={styles.bullets}>
          <li>почему вам интересно обучение именно в inVision U;</li>
          <li>какие цели вы ставите перед собой;</li>
          <li>какой опыт, проект, инициатива или жизненная ситуация повлияли на вас сильнее всего;</li>
          <li>как вы проявляете инициативу, ответственность или лидерские качества;</li>
          <li>как обучение в inVision U поможет вам принести пользу другим и реализовать свой потенциал.</li>
        </ul>

        <p className={styles.lead}>
          Для наилучшего результата рекомендуем писать письмо прямо на платформе, своими словами. Нам важны ваш
          личный стиль, искренность и конкретные примеры из опыта.
        </p>

        <div className={`${styles.footer} modal-actions modal-actions--single`}>
          <button type="button" className="btn secondary" onClick={onClose}>
            Закрыть
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
}

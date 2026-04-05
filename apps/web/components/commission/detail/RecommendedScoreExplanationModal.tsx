"use client";

import Image from "next/image";
import { useEffect, useId, useState } from "react";
import { createPortal } from "react-dom";
import styles from "@/components/application/presentation-instruction-modal.module.css";

type Props = {
  open: boolean;
  onClose: () => void;
  body: string;
};

export function RecommendedScoreExplanationModal({ open, onClose, body }: Props) {
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

  const paragraphs =
    body.trim().length === 0
      ? [body]
      : body.split(/\n\n+/).filter((p) => p.trim().length > 0);

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
          Почему такая оценка?
        </h2>
        <div className={styles.lead} style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
          {paragraphs.map((para, i) => (
            <p key={i} style={{ margin: 0, whiteSpace: "pre-wrap" }}>
              {para}
            </p>
          ))}
        </div>
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

/** Кнопка с иконкой информации; открывает модальное пояснение рекомендуемой оценки. */
export function RecommendedScoreInfoButton({ onClick, disabled }: { onClick: () => void; disabled?: boolean }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-label="Почему такая оценка?"
      style={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 2,
        border: "none",
        background: "transparent",
        cursor: disabled ? "not-allowed" : "pointer",
        borderRadius: 6,
        opacity: disabled ? 0.45 : 1,
        verticalAlign: "middle",
      }}
    >
      <Image src="/assets/icons/material-symbols_info-rounded.svg" width={18} height={18} alt="" />
    </button>
  );
}

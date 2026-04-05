"use client";

import { useEffect, useId, useState } from "react";
import { createPortal } from "react-dom";
import styles from "./presentation-instruction-modal.module.css";

type Props = {
  open: boolean;
  onClose: () => void;
};

export function PresentationInstructionModal({ open, onClose }: Props) {
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
          Изучите инструкции по подготовке видеопрезентации (Foundation Year)
        </h2>

        <p className={styles.lead}>
          Мы хотим лучше узнать вас! Пожалуйста, запишите и отправьте короткое видео, в котором вы ответите на
          вопросы ниже. В кадре должны быть вы, говорящие прямо в камеру (формат «говорящая голова»). При желании
          вы также можете добавить простую презентацию.
        </p>

        <h3 className={styles.subtitle}>Требования к видео</h3>

        <p className={styles.blockLabel}>Продолжительность:</p>
        <p className={styles.blockValue}>до 5 минут</p>

        <p className={styles.blockLabel}>Критерии оценки:</p>
        <ul className={styles.bullets}>
          <li>мотивация</li>
          <li>лидерский потенциал</li>
          <li>креативность и структура вашего видео</li>
        </ul>

        <h3 className={styles.subtitle}>Вопросы:</h3>
        <ol className={styles.questions}>
          <li>Почему вы хотите учиться в inVision U?</li>
          <li>Какое самое большое препятствие вы преодолели, и что помогало вам не сдаваться?</li>
          <li>Каковы ваши долгосрочные цели, и как эта программа поможет вам их достичь?</li>
          <li>Что для вас значит быть лидером? Приведите пример, когда вы проявили лидерство.</li>
          <li>Расскажите о трудности, с которой столкнулась ваша команда, и какую роль вы сыграли в её решении.</li>
          <li>
            Как ваша семья поддерживает ваше решение поступить в inVision U? Кто вдохновляет и поддерживает вас
            больше всего?
          </li>
          <li>
            И наконец, расскажите о своей мечте на английском языке. Как вы изучали английский, и какого прогресса
            уже достигли?
          </li>
        </ol>

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

"use client";

import styles from "./application-header.module.css";

type Props = {
  candidateName?: string;
  subtitle?: string;
  showSubmitButton?: boolean;
  onSubmitClick?: () => void;
  onClearClick?: () => void;
};

export function ApplicationHeader({
  candidateName,
  subtitle = "Заполните форму, загрузите документы и отправляйте заявку",
  showSubmitButton = true,
  onSubmitClick,
  onClearClick,
}: Props) {
  const name = candidateName?.trim() || "кандидат";

  return (
    <header className={styles.header}>
      <div className={styles.inner}>
        <div className={styles.titleBlock}>
          <h1 className={styles.title}>Добро пожаловать, {name}</h1>
          <p className={styles.subtitle}>{subtitle}</p>
        </div>
        {showSubmitButton ? (
          <div className={styles.buttons}>
            <button type="button" className={styles.clearButton} onClick={onClearClick}>
              Очистить анкету
            </button>
            <button type="button" className="btn" onClick={onSubmitClick}>
              Отправить анкету
            </button>
          </div>
        ) : null}
      </div>
    </header>
  );
}

"use client";

import Link from "next/link";
import styles from "./auth-register.module.css";

type TermsCheckboxProps = {
  checked: boolean;
  onChange: (checked: boolean) => void;
  error?: string;
};

export function TermsCheckbox({ checked, onChange, error }: TermsCheckboxProps) {
  return (
    <div className={styles.field}>
      <div className={styles.checkboxRow}>
        <button
          type="button"
          className={`${styles.checkboxBtn} ${checked ? styles.checkboxBtnChecked : ""}`}
          onClick={() => onChange(!checked)}
          aria-label="Принять пользовательское соглашение"
          aria-pressed={checked}
        >
          {checked ? (
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden>
              <path
                d="M2 6L5 9L10 3"
                stroke="white"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          ) : null}
        </button>
        <p className={styles.checkboxText}>
          <span>Я принимаю </span>
          <Link href="/terms" className={styles.linkInline}>
            пользовательское соглашение
          </Link>
          <span> на обработку и хранение персональных данных</span>
        </p>
      </div>
      {error ? <p className={styles.fieldError}>{error}</p> : null}
    </div>
  );
}

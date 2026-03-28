"use client";

import type { ReactNode } from "react";
import styles from "./form-ui.module.css";

type Props = {
  children: ReactNode;
  checked: boolean;
  onChange: (checked: boolean) => void;
};

export function ConsentCheckbox({ children, checked, onChange }: Props) {
  return (
    <label className={styles.consentRow}>
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
      />
      <span className={styles.checkmark} />
      <span className={styles.consentText}>{children}</span>
    </label>
  );
}

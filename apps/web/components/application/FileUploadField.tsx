"use client";

import { useId, useRef } from "react";
import styles from "./form-ui.module.css";

type Props = {
  label: string;
  hint?: string;
  accept?: string;
  onFile?: (file: File | null) => void;
};

export function FileUploadField({
  label,
  hint = "Нажмите чтобы загрузить или перетащите файл. Разрешенные форматы: PDF, JPEG, PNG, HEIC до 10MB.",
  accept = ".pdf,.jpg,.jpeg,.png,.heic",
  onFile,
}: Props) {
  const id = useId();
  const inputRef = useRef<HTMLInputElement>(null);

  return (
    <div className={styles.uploadRoot}>
      <span className={styles.label} id={`${id}-label`}>
        {label}
      </span>
      <label className={styles.uploadArea} htmlFor={id}>
        <input
          ref={inputRef}
          id={id}
          type="file"
          className={styles.visuallyHidden}
          accept={accept}
          aria-labelledby={`${id}-label`}
          onChange={(e) => onFile?.(e.target.files?.[0] ?? null)}
        />
        <img
          className={styles.uploadIcon}
          src="/assets/icons/material-symbols_upload-rounded.svg"
          alt=""
          width={36}
          height={36}
        />
        <p className={styles.uploadTitle}>Загрузить файл</p>
        <p className={styles.uploadHint}>{hint}</p>
      </label>
    </div>
  );
}

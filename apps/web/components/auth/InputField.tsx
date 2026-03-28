"use client";

import styles from "./auth-register.module.css";

type InputFieldProps = {
  label: string;
  type?: string;
  placeholder: string;
  name: string;
  value: string;
  onChange: (value: string) => void;
  onBlur?: () => void;
  error?: string;
  autoComplete?: string;
  inputMode?: "numeric" | "text" | "email" | "tel" | "search" | "decimal" | "none";
};

export function InputField({
  label,
  type = "text",
  placeholder,
  name,
  value,
  onChange,
  onBlur,
  error,
  autoComplete,
  inputMode,
}: InputFieldProps) {
  return (
    <div className={styles.field}>
      <label className={styles.label} htmlFor={name}>
        {label}
      </label>
      <div className={styles.inputShell}>
        <input
          id={name}
          name={name}
          type={type}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onBlur={onBlur}
          placeholder={placeholder}
          autoComplete={autoComplete}
          inputMode={inputMode}
          className={styles.input}
        />
      </div>
      {error ? <p className={styles.fieldError}>{error}</p> : null}
    </div>
  );
}

"use client";

import { getInputConstraints, processInputValue, type InputFieldType } from "@/lib/input-constraints";
import styles from "./auth-register.module.css";

type InputFieldProps = {
  label: string;
  type?: string;
  placeholder: string;
  name: string;
  /** Пустая строка, если не задано — иначе React ругается на переход uncontrolled → controlled */
  value: string | undefined;
  onChange: (value: string) => void;
  onBlur?: () => void;
  error?: string;
  autoComplete?: string;
  inputMode?: "numeric" | "text" | "email" | "tel" | "search" | "decimal" | "none";
  fieldType?: InputFieldType;
  onProcessedValue?: (payload: { formattedValue: string; rawValue: string; isComplete: boolean }) => void;
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
  fieldType = "text",
  onProcessedValue,
}: InputFieldProps) {
  const constraints = getInputConstraints(fieldType);
  const defaultInputMode =
    fieldType === "phone" ? "tel" : fieldType === "iin" || fieldType === "date" ? "numeric" : "text";
  const shouldNormalize = type !== "password" && type !== "email";

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
          value={value ?? ""}
          onChange={(e) => {
            if (!shouldNormalize) {
              onChange(e.target.value);
              return;
            }
            const processed = processInputValue(fieldType, e.target.value, { phase: "input" });
            onChange(processed.formattedValue);
            onProcessedValue?.(processed);
          }}
          onBlur={(e) => {
            if (!shouldNormalize) {
              onBlur?.();
              return;
            }
            const processed = processInputValue(fieldType, e.target.value, { phase: "blur" });
            if (processed.formattedValue !== (value ?? "")) {
              onChange(processed.formattedValue);
            }
            onProcessedValue?.(processed);
            onBlur?.();
          }}
          placeholder={placeholder}
          autoComplete={autoComplete}
          inputMode={inputMode ?? defaultInputMode}
          maxLength={shouldNormalize ? constraints.maxLength : undefined}
          className={styles.input}
        />
      </div>
      {error ? <p className={styles.fieldError}>{error}</p> : null}
    </div>
  );
}

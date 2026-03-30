import type { ChangeEvent, FocusEvent, InputHTMLAttributes } from "react";
import { getInputConstraints, processInputValue, type InputFieldType } from "@/lib/input-constraints";
import styles from "./form-ui.module.css";

type Props = {
  label: string;
  htmlFor?: string;
  fieldType?: InputFieldType;
  onProcessedValue?: (payload: { formattedValue: string; rawValue: string; isComplete: boolean }) => void;
} & InputHTMLAttributes<HTMLInputElement>;

export function FormField({ label, id, className, fieldType = "text", onProcessedValue, ...rest }: Props) {
  const constraints = getInputConstraints(fieldType);

  function handleChange(e: ChangeEvent<HTMLInputElement>) {
    const processed = processInputValue(fieldType, e.target.value, { phase: "input" });
    e.target.value = processed.formattedValue;
    rest.onChange?.(e);
    onProcessedValue?.(processed);
  }

  function handleBlur(e: FocusEvent<HTMLInputElement>) {
    const processed = processInputValue(fieldType, e.target.value, { phase: "blur" });
    e.target.value = processed.formattedValue;
    rest.onBlur?.(e);
    onProcessedValue?.(processed);
  }

  const defaultInputMode =
    fieldType === "phone" ? "tel" : fieldType === "iin" || fieldType === "date" ? "numeric" : "text";

  return (
    <div className={`${styles.field} ${className ?? ""}`}>
      <label className={styles.label} htmlFor={id}>
        {label}
      </label>
      <input
        className={styles.input}
        id={id}
        {...rest}
        inputMode={rest.inputMode ?? defaultInputMode}
        maxLength={rest.maxLength ?? constraints.maxLength}
        onChange={handleChange}
        onBlur={handleBlur}
      />
    </div>
  );
}

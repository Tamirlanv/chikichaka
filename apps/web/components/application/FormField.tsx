import type { InputHTMLAttributes } from "react";
import styles from "./form-ui.module.css";

type Props = {
  label: string;
  htmlFor?: string;
} & InputHTMLAttributes<HTMLInputElement>;

export function FormField({ label, id, className, ...rest }: Props) {
  return (
    <div className={`${styles.field} ${className ?? ""}`}>
      <label className={styles.label} htmlFor={id}>
        {label}
      </label>
      <input className={styles.input} id={id} {...rest} />
    </div>
  );
}

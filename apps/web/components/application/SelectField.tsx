import type { SelectHTMLAttributes } from "react";
import styles from "./form-ui.module.css";

type Option = { value: string; label: string };

type Props = {
  label: string;
  htmlFor?: string;
  options: Option[];
} & SelectHTMLAttributes<HTMLSelectElement>;

export function SelectField({ label, id, options, className, ...rest }: Props) {
  return (
    <div className={`${styles.selectWrap} ${className ?? ""}`}>
      <label className={styles.label} htmlFor={id}>
        {label}
      </label>
      <select className={styles.select} id={id} {...rest}>
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </div>
  );
}

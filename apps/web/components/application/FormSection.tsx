import type { ReactNode } from "react";
import styles from "./form-ui.module.css";

type Props = {
  title: string;
  children: ReactNode;
  className?: string;
};

export function FormSection({ title, children, className }: Props) {
  return (
    <section className={`${styles.formSection} ${className ?? ""}`}>
      <h2 className={styles.sectionTitle}>{title}</h2>
      <div className={styles.sectionBody}>{children}</div>
    </section>
  );
}

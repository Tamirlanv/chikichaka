"use client";

import Link from "next/link";
import styles from "./application-header.module.css";

type Props = {
  candidateName?: string;
};

export function ApplicationHeader({ candidateName }: Props) {
  const name = candidateName?.trim() || "кандидат";

  return (
    <header className={styles.header}>
      <div className={styles.inner}>
        <div className={styles.titleBlock}>
          <h1 className={styles.title}>Добро пожаловать, {name}</h1>
          <p className={styles.subtitle}>
            Заполните форму, загрузите документы и отправляйте заявку
          </p>
        </div>
        <Link href="/application/review" className="btn">
          Отправить анкету
        </Link>
      </div>
    </header>
  );
}

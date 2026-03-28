"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { PillSegmentedControl } from "./PillSegmentedControl";
import styles from "./application-sticky-nav.module.css";

const TABS = [
  { href: "/application/personal", label: "Личная информация", value: "personal" },
  { href: "/application/contact", label: "Контакты", value: "contact" },
  { href: "/application/education", label: "Образование", value: "education" },
  { href: "/application/internal-test", label: "Внутренний тест", value: "internal_test" },
  { href: "/application/motivation", label: "Мотивация", value: "motivation" },
  { href: "/application/growth", label: "Путь", value: "growth" },
  { href: "/application/portfolio", label: "Портфолио", value: "portfolio" },
  { href: "/application/essay", label: "Эссе", value: "essay" },
] as const;

function pathToValue(path: string): string {
  const sorted = [...TABS].sort((a, b) => b.href.length - a.href.length);
  const hit = sorted.find((t) => path.startsWith(t.href));
  return hit?.value ?? "personal";
}

export function ApplicationStickyNav() {
  const pathname = usePathname();
  const router = useRouter();
  const value = pathToValue(pathname || "");
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <div className={styles.stickyWrap} data-scrolled={scrolled}>
      <div className={styles.inner}>
        <div className={styles.row}>
          <h2 className={styles.sectionTitle}>Подача анкеты</h2>
          <button
            type="button"
            className={styles.infoBtn}
            aria-label="Справка по этапам"
            title="Справка по этапам"
          >
            <img src="/assets/icons/material-symbols_info-rounded.svg" alt="" width={20} height={20} />
          </button>
        </div>
        <div className={styles.tabsScroll}>
          <PillSegmentedControl
            gap="tabs"
            aria-label="Разделы анкеты"
            options={TABS.map((t) => ({ value: t.value, label: t.label }))}
            value={value}
            onChange={(v) => {
              const next = TABS.find((t) => t.value === v);
              if (next) router.push(next.href);
            }}
          />
        </div>
      </div>
    </div>
  );
}

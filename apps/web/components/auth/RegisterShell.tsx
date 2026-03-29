"use client";

import Image from "next/image";
import { useRouter } from "next/navigation";
import styles from "./auth-register.module.css";
import wizardStyles from "./register-wizard.module.css";

const LOGO_SRC = "/assets/images/Gemini_Generated_Image_7vjh7a7vjh7a7vjh.png";

type Props = {
  children: React.ReactNode;
  /** Куда перейти, если onBack не передан */
  backHref: string;
  /** Переопределение: например с верификации вернуться к форме на той же странице */
  onBack?: () => void;
  backAriaLabel?: string;
};

export function RegisterShell({ children, backHref, onBack, backAriaLabel = "Назад" }: Props) {
  const router = useRouter();

  function handleBack() {
    if (onBack) {
      onBack();
    } else {
      router.push(backHref);
    }
  }

  return (
    <div className={styles.root}>
      <button
        type="button"
        className={wizardStyles.backBtn}
        onClick={handleBack}
        aria-label={backAriaLabel}
      >
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" aria-hidden>
          <path
            d="M15 18L9 12L15 6"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </button>
      <div className={styles.panelLeft}>
        <div className={styles.logoWrap}>
          <Image
            src={LOGO_SRC}
            alt="inVision"
            fill
            sizes="(max-width: 900px) 80vw, 474px"
            priority
            style={{ objectFit: "contain" }}
          />
        </div>
      </div>

      <div className={styles.panelRight}>{children}</div>
    </div>
  );
}

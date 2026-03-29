"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { RegisterShell } from "@/components/auth/RegisterShell";
import wizardStyles from "@/components/auth/register-wizard.module.css";
import styles from "@/components/auth/auth-register.module.css";
import { setRegisterProgram, type RegisterProgram } from "@/lib/register-flow";

const ICON_FOUNDATION = "/assets/icons/foundation.svg";
const ICON_SCHOOL = "/assets/icons/school.svg";

function CheckIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path
        d="M20 6L9 17L4 12"
        stroke="white"
        strokeWidth="3"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export default function RegisterProgramPage() {
  const router = useRouter();
  const [selected, setSelected] = useState<RegisterProgram | null>(null);

  function onContinue() {
    if (!selected) return;
    setRegisterProgram(selected);
    if (selected === "foundation") {
      router.push("/register/account");
    } else {
      router.push("/register/specialty");
    }
  }

  return (
    <RegisterShell backHref="/">
      <div className={wizardStyles.wizardColumn}>
        <h1 className={styles.title}>Выберите программу</h1>

        <div className={wizardStyles.programStack}>
          <button
            type="button"
            className={`${wizardStyles.programCard} ${selected === "foundation" ? wizardStyles.programCardSelected : ""}`}
            onClick={() => setSelected("foundation")}
          >
            <span className={wizardStyles.programCardBorder} aria-hidden />
            <span className={wizardStyles.programCardInner}>
              <span className={wizardStyles.programIcon}>
                <Image src={ICON_FOUNDATION} alt="" width={36} height={36} unoptimized />
              </span>
              <span
                className={`${wizardStyles.programLabel} ${selected === "foundation" ? wizardStyles.programLabelSelected : ""}`}
              >
                Foundation
              </span>
            </span>
            {selected === "foundation" ? (
              <span className={wizardStyles.checkWrap}>
                <CheckIcon />
              </span>
            ) : null}
          </button>

          <button
            type="button"
            className={`${wizardStyles.programCard} ${selected === "bachelor" ? wizardStyles.programCardSelected : ""}`}
            onClick={() => setSelected("bachelor")}
          >
            <span className={wizardStyles.programCardBorder} aria-hidden />
            <span className={wizardStyles.programCardInner}>
              <span className={wizardStyles.programIcon}>
                <Image src={ICON_SCHOOL} alt="" width={36} height={36} unoptimized />
              </span>
              <span
                className={`${wizardStyles.programLabel} ${selected === "bachelor" ? wizardStyles.programLabelSelected : ""}`}
              >
                Бакалавриат
              </span>
            </span>
            {selected === "bachelor" ? (
              <span className={wizardStyles.checkWrap}>
                <CheckIcon />
              </span>
            ) : null}
          </button>
        </div>

        <div className={styles.actions}>
          <button
            type="button"
            className={`${wizardStyles.continueBtn} ${selected ? wizardStyles.continueBtnEnabled : wizardStyles.continueBtnDisabled}`}
            disabled={!selected}
            onClick={onContinue}
          >
            Продолжить
          </button>
          <p className={wizardStyles.footerSmall}>
            <span>Уже есть аккаунт? </span>
            <Link href="/login" className={wizardStyles.footerSmallUnderline}>
              Войти
            </Link>
          </p>
        </div>
      </div>
    </RegisterShell>
  );
}

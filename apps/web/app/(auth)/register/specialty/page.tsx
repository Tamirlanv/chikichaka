"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import Link from "next/link";
import { RegisterShell } from "@/components/auth/RegisterShell";
import wizardStyles from "@/components/auth/register-wizard.module.css";
import styles from "@/components/auth/auth-register.module.css";
import {
  BACHELOR_SPECIALTIES,
  readRegisterFlow,
  setRegisterSpecialty,
} from "@/lib/register-flow";

function CheckIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden>
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

export default function RegisterSpecialtyPage() {
  const router = useRouter();
  const [selected, setSelected] = useState<string | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const flow = readRegisterFlow();
    if (!flow?.program) {
      router.replace("/register");
      return;
    }
    if (flow.program === "foundation") {
      router.replace("/register/account");
      return;
    }
    if (flow.specialtyId) {
      setSelected(flow.specialtyId);
    }
    setReady(true);
  }, [router]);

  function onContinue() {
    if (!selected) return;
    setRegisterSpecialty(selected);
    router.push("/register/account");
  }

  if (!ready) {
    return (
      <RegisterShell backHref="/register">
        <p className={styles.verifyHint}>Загрузка…</p>
      </RegisterShell>
    );
  }

  return (
    <RegisterShell backHref="/register">
      <div className={wizardStyles.wizardColumnSpecialty}>
        <h1 className={styles.title}>Выберите специальность</h1>

        <div className={wizardStyles.specialtyStack}>
          {BACHELOR_SPECIALTIES.map((s) => (
            <button
              key={s.id}
              type="button"
              className={`${wizardStyles.specialtyCard} ${selected === s.id ? wizardStyles.specialtyCardSelected : ""}`}
              onClick={() => setSelected(s.id)}
            >
              <span className={wizardStyles.specialtyCardBorder} aria-hidden />
              <span className={wizardStyles.specialtyCardInner}>
                <span
                  className={`${wizardStyles.specialtyLabel} ${selected === s.id ? wizardStyles.specialtyLabelSelected : ""}`}
                >
                  {s.label}
                </span>
              </span>
              {selected === s.id ? (
                <span className={wizardStyles.specialtyCheckWrap}>
                  <CheckIcon />
                </span>
              ) : null}
            </button>
          ))}
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

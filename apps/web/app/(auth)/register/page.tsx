"use client";

import { useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Controller, useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { apiFetch, ApiError } from "@/lib/api-client";
import {
  registerPageSchema,
  splitNameToProfile,
  verifyCodeSchema,
  type RegisterPageForm,
  type VerifyCodeForm,
} from "@/lib/validation";
import { InputField } from "@/components/auth/InputField";
import { TermsCheckbox } from "@/components/auth/TermsCheckbox";
import styles from "@/components/auth/auth-register.module.css";

const LOGO_SRC = "/assets/images/Gemini_Generated_Image_7vjh7a7vjh7a7vjh.png";

type Step = "form" | "verify";

export default function RegisterPage() {
  const router = useRouter();
  const [step, setStep] = useState<Step>("form");
  const [pendingEmail, setPendingEmail] = useState<string | null>(null);
  const [apiErr, setApiErr] = useState<string | null>(null);

  const form = useForm<RegisterPageForm>({
    resolver: zodResolver(registerPageSchema),
    defaultValues: {
      name: "",
      email: "",
      password: "",
      confirmPassword: "",
      agreedToTerms: false,
    },
  });

  const verifyForm = useForm<VerifyCodeForm>({
    resolver: zodResolver(verifyCodeSchema),
    defaultValues: { code: "" },
  });

  const agreed = form.watch("agreedToTerms");

  async function onSubmitForm(data: RegisterPageForm) {
    setApiErr(null);
    const { first_name, last_name } = splitNameToProfile(data.name);
    try {
      await apiFetch("/auth/register", {
        method: "POST",
        json: {
          email: data.email,
          password: data.password,
          first_name,
          last_name,
        },
      });
      setPendingEmail(data.email.trim().toLowerCase());
      setStep("verify");
      verifyForm.reset({ code: "" });
    } catch (e) {
      if (e instanceof ApiError) {
        setApiErr(e.message);
      } else {
        setApiErr("Не удалось зарегистрироваться");
      }
    }
  }

  async function onSubmitVerify(data: VerifyCodeForm) {
    if (!pendingEmail) {
      setApiErr("Сначала заполните регистрацию.");
      return;
    }
    setApiErr(null);
    try {
      await apiFetch("/auth/register/complete", {
        method: "POST",
        json: { email: pendingEmail, code: data.code },
      });
      router.replace("/dashboard?welcome=1");
      router.refresh();
    } catch (e) {
      if (e instanceof ApiError) {
        setApiErr(e.message);
      } else {
        setApiErr("Не удалось подтвердить код");
      }
    }
  }

  function goBackToForm() {
    setStep("form");
    setPendingEmail(null);
    setApiErr(null);
  }

  return (
    <div className={styles.root}>
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

      <div className={styles.panelRight}>
        {step === "form" ? (
          <form className={styles.formColumn} onSubmit={form.handleSubmit(onSubmitForm)} noValidate>
            <h1 className={styles.title}>Регистрация</h1>

            <div className={styles.fields}>
              <div className={styles.fieldStack}>
                <Controller
                  name="name"
                  control={form.control}
                  render={({ field }) => (
                    <InputField
                      label="Имя"
                      placeholder="Введите имя"
                      name={field.name}
                      value={field.value}
                      onChange={field.onChange}
                      onBlur={field.onBlur}
                      error={form.formState.errors.name?.message}
                      autoComplete="name"
                    />
                  )}
                />
                <Controller
                  name="email"
                  control={form.control}
                  render={({ field }) => (
                    <InputField
                      label="E-mail"
                      type="email"
                      placeholder="Введите e-mail"
                      name={field.name}
                      value={field.value}
                      onChange={field.onChange}
                      onBlur={field.onBlur}
                      error={form.formState.errors.email?.message}
                      autoComplete="email"
                    />
                  )}
                />
                <Controller
                  name="password"
                  control={form.control}
                  render={({ field }) => (
                    <InputField
                      label="Пароль"
                      type="password"
                      placeholder="Введите пароль"
                      name={field.name}
                      value={field.value}
                      onChange={field.onChange}
                      onBlur={field.onBlur}
                      error={form.formState.errors.password?.message}
                      autoComplete="new-password"
                    />
                  )}
                />
                <Controller
                  name="confirmPassword"
                  control={form.control}
                  render={({ field }) => (
                    <InputField
                      label="Подтвердить пароль"
                      type="password"
                      placeholder="Введите пароль"
                      name={field.name}
                      value={field.value}
                      onChange={field.onChange}
                      onBlur={field.onBlur}
                      error={form.formState.errors.confirmPassword?.message}
                      autoComplete="new-password"
                    />
                  )}
                />
              </div>

              <TermsCheckbox
                checked={agreed}
                onChange={(v) => form.setValue("agreedToTerms", v, { shouldValidate: true })}
                error={form.formState.errors.agreedToTerms?.message}
              />
            </div>

            <div className={styles.actions}>
              {apiErr ? <p className={styles.apiError}>{apiErr}</p> : null}
              <button type="submit" className={styles.submitBtn} disabled={form.formState.isSubmitting}>
                {form.formState.isSubmitting ? "Отправка…" : "Продолжить"}
              </button>
              <p className={styles.footerLine}>
                <span>Уже есть аккаунт? </span>
                <Link href="/login" className={styles.footerLink}>
                  Войти
                </Link>
              </p>
            </div>
          </form>
        ) : (
          <form className={styles.formColumn} onSubmit={verifyForm.handleSubmit(onSubmitVerify)} noValidate>
            <h1 className={styles.title}>Верификация</h1>
            {pendingEmail ? (
              <p className={styles.verifyHint}>Код отправлен на {pendingEmail}</p>
            ) : null}

            <div className={styles.fields}>
              <div className={styles.fieldStack}>
                <Controller
                  name="code"
                  control={verifyForm.control}
                  render={({ field }) => (
                    <InputField
                      label="Код"
                      placeholder="Введите код из почты"
                      name={field.name}
                      value={field.value}
                      onChange={(v) => field.onChange(v.replace(/\D/g, "").slice(0, 6))}
                      onBlur={field.onBlur}
                      error={verifyForm.formState.errors.code?.message}
                      autoComplete="one-time-code"
                      inputMode="numeric"
                    />
                  )}
                />
              </div>
            </div>

            <div className={styles.actions}>
              {apiErr ? <p className={styles.apiError}>{apiErr}</p> : null}
              <button type="submit" className={styles.submitBtn} disabled={verifyForm.formState.isSubmitting}>
                {verifyForm.formState.isSubmitting ? "Проверка…" : "Продолжить"}
              </button>
              <button type="button" className={styles.backLink} onClick={goBackToForm}>
                Назад к регистрации
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}

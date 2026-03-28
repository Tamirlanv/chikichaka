"use client";

import Image from "next/image";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { apiFetch, ApiError } from "@/lib/api-client";
import { loginSchema } from "@/lib/validation";
import { InputField } from "@/components/auth/InputField";
import styles from "@/components/auth/auth-register.module.css";

const LOGO_SRC = "/assets/images/Gemini_Generated_Image_7vjh7a7vjh7a7vjh.png";

type Form = z.infer<typeof loginSchema>;

function LoginFormInner() {
  const router = useRouter();
  const params = useSearchParams();
  const next = params.get("next") || "/dashboard";
  const [err, setErr] = useState<string | null>(null);
  const {
    control,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<Form>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: "", password: "" },
  });

  async function onSubmit(data: Form) {
    setErr(null);
    try {
      await apiFetch("/auth/login", { method: "POST", json: data });
      router.replace(next);
      router.refresh();
    } catch (e) {
      if (e instanceof ApiError) {
        setErr(e.message);
      } else {
        setErr("Не удалось войти");
      }
    }
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
        <form className={styles.formColumn} onSubmit={handleSubmit(onSubmit)} noValidate>
          <h1 className={styles.title}>Вход</h1>
          <p className={styles.verifyHint} style={{ marginTop: 0 }}>
            Личный кабинет абитуриента
          </p>

          <div className={styles.fields}>
            <div className={styles.fieldStack}>
              <Controller
                name="email"
                control={control}
                render={({ field }) => (
                  <InputField
                    label="E-mail"
                    type="email"
                    placeholder="Введите e-mail"
                    name={field.name}
                    value={field.value}
                    onChange={field.onChange}
                    onBlur={field.onBlur}
                    error={errors.email?.message}
                    autoComplete="email"
                  />
                )}
              />
              <Controller
                name="password"
                control={control}
                render={({ field }) => (
                  <InputField
                    label="Пароль"
                    type="password"
                    placeholder="Введите пароль"
                    name={field.name}
                    value={field.value}
                    onChange={field.onChange}
                    onBlur={field.onBlur}
                    error={errors.password?.message}
                    autoComplete="current-password"
                  />
                )}
              />
            </div>
          </div>

          <div className={styles.actions}>
            {err ? <p className={styles.apiError}>{err}</p> : null}
            <button type="submit" className={styles.submitBtn} disabled={isSubmitting}>
              {isSubmitting ? "Вход…" : "Продолжить"}
            </button>
            <p className={styles.footerLine}>
              <span>Нет аккаунта? </span>
              <Link href="/register" className={styles.footerLink}>
                Регистрация
              </Link>
            </p>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<p className="muted" style={{ padding: 48, textAlign: "center" }}>Загрузка…</p>}>
      <LoginFormInner />
    </Suspense>
  );
}

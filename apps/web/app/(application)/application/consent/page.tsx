"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useForm, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { apiFetch, apiFetchCached, bustApiCache } from "@/lib/api-client";
import { FormSection } from "@/components/application/FormSection";
import { Divider } from "@/components/application/Divider";
import { ConsentCheckbox } from "@/components/application/ConsentCheckbox";
import formStyles from "@/components/application/form-ui.module.css";

const CONSENT_POLICY_VERSION = "v1.0";

const schema = z.object({
  accepted_terms: z.boolean(),
  accepted_privacy: z.boolean(),
  consent_policy_version: z.string().min(1).max(64),
  accepted_at: z.string().nullable().optional(),
});

type Form = z.infer<typeof schema>;

export default function ConsentPage() {
  const [msg, setMsg] = useState<string | null>(null);

  const {
    handleSubmit,
    reset,
    control,
    register,
    formState: { isSubmitting },
  } = useForm<Form>({
    resolver: zodResolver(schema),
    defaultValues: {
      accepted_terms: false,
      accepted_privacy: false,
      consent_policy_version: CONSENT_POLICY_VERSION,
      accepted_at: null,
    },
  });

  useEffect(() => {
    async function load() {
      try {
        const app = await apiFetchCached<{
          sections: Record<string, { payload: unknown }>;
        }>("/candidates/me/application", 2 * 60 * 1000);
        const raw = app.sections.consent_agreement?.payload as Record<string, unknown> | undefined;
        if (!raw) return;
        reset({
          accepted_terms: Boolean(raw.accepted_terms),
          accepted_privacy: Boolean(raw.accepted_privacy),
          consent_policy_version: raw.consent_policy_version
            ? String(raw.consent_policy_version)
            : CONSENT_POLICY_VERSION,
          accepted_at: raw.accepted_at ? String(raw.accepted_at) : null,
        });
      } catch {
        setMsg("Не удалось загрузить данные. Обновите страницу.");
      }
    }
    void load();
  }, [reset]);

  async function onSubmit(data: Form) {
    setMsg(null);
    const payload = {
      accepted_terms: data.accepted_terms,
      accepted_privacy: data.accepted_privacy,
      consent_policy_version: data.consent_policy_version,
      accepted_at: new Date().toISOString(),
    };
    try {
      await apiFetch("/candidates/me/application/sections/consent_agreement", {
        method: "PATCH",
        json: { payload },
      });
      bustApiCache("/candidates/me");
      setMsg("Сохранено.");
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Не удалось сохранить");
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate style={{ maxWidth: 872 }}>
      <FormSection title="Согласие и условия">
        <p className="muted" style={{ margin: 0 }}>
          Для продолжения подачи заявки необходимо ознакомиться и принять условия использования платформы и политику
          конфиденциальности.
        </p>

        <Controller
          name="accepted_terms"
          control={control}
          render={({ field }) => (
            <ConsentCheckbox checked={field.value} onChange={field.onChange}>
              Я принимаю{" "}
              <a href="/terms" target="_blank" rel="noopener noreferrer">
                Условия использования
              </a>{" "}
              платформы inVision U
            </ConsentCheckbox>
          )}
        />

        <Controller
          name="accepted_privacy"
          control={control}
          render={({ field }) => (
            <ConsentCheckbox checked={field.value} onChange={field.onChange}>
              Я принимаю{" "}
              <a href="/privacy" target="_blank" rel="noopener noreferrer">
                Политику конфиденциальности
              </a>{" "}
              и даю согласие на обработку персональных данных
            </ConsentCheckbox>
          )}
        />

        <input type="hidden" {...register("consent_policy_version")} />
      </FormSection>

      <Divider />

      {msg && <p className={msg.includes("Не удалось") ? "error" : "muted"} role="alert">{msg}</p>}

      <div className={formStyles.formFooter}>
        <button className="btn secondary" type="submit" disabled={isSubmitting}>
          {isSubmitting ? "Сохранение…" : "Сохранить"}
        </button>
        <Link className="btn" href="/application/review">
          Далее
        </Link>
      </div>
    </form>
  );
}

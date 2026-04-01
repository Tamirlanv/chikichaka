"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useForm, useFieldArray } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { apiFetch, apiFetchCached, bustApiCache } from "@/lib/api-client";
import { FormSection } from "@/components/application/FormSection";
import { Divider } from "@/components/application/Divider";
import formStyles from "@/components/application/form-ui.module.css";

const activityItemSchema = z.object({
  category: z.string().min(1, "Обязательное поле").max(128),
  title: z.string().min(1, "Обязательное поле").max(255),
  organization: z.string().max(255).optional().or(z.literal("")),
  role: z.string().max(255).optional().or(z.literal("")),
  impact_summary: z.string().max(2000).optional().or(z.literal("")),
});

const schema = z.object({
  activities: z.array(activityItemSchema).min(1, "Добавьте хотя бы одно достижение").max(50),
});

type Form = z.infer<typeof schema>;

const EMPTY_ITEM: Form["activities"][number] = {
  category: "",
  title: "",
  organization: "",
  role: "",
  impact_summary: "",
};

export default function AchievementsPage() {
  const [msg, setMsg] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    reset,
    control,
    formState: { errors, isSubmitting },
  } = useForm<Form>({
    resolver: zodResolver(schema),
    defaultValues: { activities: [EMPTY_ITEM] },
  });

  const { fields, append, remove } = useFieldArray({ control, name: "activities" });

  useEffect(() => {
    async function load() {
      try {
        const app = await apiFetchCached<{
          sections: Record<string, { payload: unknown }>;
        }>("/candidates/me/application", 2 * 60 * 1000);
        const raw = app.sections.achievements_activities?.payload as Record<string, unknown> | undefined;
        if (!raw) return;
        const activities = Array.isArray(raw.activities) ? raw.activities : [];
        if (activities.length > 0) {
          reset({ activities: activities as Form["activities"] });
        }
      } catch {
        setMsg("Не удалось загрузить данные. Обновите страницу.");
      }
    }
    void load();
  }, [reset]);

  async function onSubmit(data: Form) {
    setMsg(null);
    const payload = {
      activities: data.activities.map((a) => ({
        category: a.category,
        title: a.title,
        organization: a.organization || undefined,
        role: a.role || undefined,
        impact_summary: a.impact_summary || undefined,
      })),
    };
    try {
      await apiFetch("/candidates/me/application/sections/achievements_activities", {
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
      <FormSection title="Достижения и активности">
        {fields.map((field, idx) => (
          <div key={field.id} style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            {idx > 0 && <Divider />}
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <h3 className={formStyles.label} style={{ fontSize: 16, fontWeight: 500 }}>
                Достижение {idx + 1}
              </h3>
              {fields.length > 1 && (
                <button type="button" className="btn secondary" style={{ fontSize: 13 }} onClick={() => remove(idx)}>
                  Удалить
                </button>
              )}
            </div>

            <div className={formStyles.row3}>
              <div className={formStyles.field}>
                <label className={formStyles.label}>Категория *</label>
                <input className={formStyles.input} {...register(`activities.${idx}.category`)} placeholder="Олимпиада, волонтёрство…" />
                {errors.activities?.[idx]?.category && (
                  <p className="error" style={{ margin: "4px 0 0" }}>{errors.activities[idx]!.category!.message}</p>
                )}
              </div>
              <div className={`${formStyles.field} ${formStyles.fieldSpan2}`}>
                <label className={formStyles.label}>Название *</label>
                <input className={formStyles.input} {...register(`activities.${idx}.title`)} placeholder="Название достижения" />
                {errors.activities?.[idx]?.title && (
                  <p className="error" style={{ margin: "4px 0 0" }}>{errors.activities[idx]!.title!.message}</p>
                )}
              </div>
            </div>

            <div className={formStyles.row3}>
              <div className={formStyles.field}>
                <label className={formStyles.label}>Организация</label>
                <input className={formStyles.input} {...register(`activities.${idx}.organization`)} placeholder="Организатор" />
              </div>
              <div className={formStyles.field}>
                <label className={formStyles.label}>Роль</label>
                <input className={formStyles.input} {...register(`activities.${idx}.role`)} placeholder="Ваша роль" />
              </div>
            </div>

            <div className={formStyles.field}>
              <label className={formStyles.label}>Описание влияния</label>
              <textarea
                className={formStyles.input}
                style={{ minHeight: 80, resize: "vertical", padding: "10px 16px" }}
                maxLength={2000}
                {...register(`activities.${idx}.impact_summary`)}
                placeholder="Опишите результаты и влияние"
              />
            </div>
          </div>
        ))}

        {errors.activities?.root && (
          <p className="error" style={{ margin: 0 }}>{errors.activities.root.message}</p>
        )}

        {fields.length < 50 && (
          <button type="button" className="btn secondary" onClick={() => append(EMPTY_ITEM)}>
            + Добавить достижение
          </button>
        )}
      </FormSection>

      <Divider />

      {msg && <p className={msg.includes("Не удалось") ? "error" : "muted"} role="alert">{msg}</p>}

      <div className={formStyles.formFooter}>
        <button className="btn secondary" type="submit" disabled={isSubmitting}>
          {isSubmitting ? "Сохранение…" : "Сохранить"}
        </button>
        <Link className="btn" href="/application/leadership">
          Далее
        </Link>
      </div>
    </form>
  );
}

"use client";

import Link from "next/link";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useForm, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { apiFetch, apiFetchCached, bustApiCache } from "@/lib/api-client";
import { personalSchema } from "@/lib/validation";
import { PillSegmentedControl } from "@/components/application/PillSegmentedControl";
import { FormSection } from "@/components/application/FormSection";
import { FormField } from "@/components/application/FormField";
import { Divider } from "@/components/application/Divider";
import { SelectField } from "@/components/application/SelectField";
import { FileUploadField } from "@/components/application/FileUploadField";
import { ConsentCheckbox } from "@/components/application/ConsentCheckbox";
import formStyles from "@/components/application/form-ui.module.css";

const personalFormSchema = personalSchema.extend({
  middle_name: z.string().optional(),
  gender: z.enum(["male", "female"]).optional(),
  document_type: z.enum(["id", "passport"]).optional(),
  citizenship: z.string().optional(),
  iin: z.string().optional(),
  document_number: z.string().optional(),
  document_issue_date: z.string().optional(),
  document_issued_by: z.string().optional(),
  father_last: z.string().optional(),
  father_first: z.string().optional(),
  father_middle: z.string().optional(),
  father_phone: z.string().optional(),
  mother_last: z.string().optional(),
  mother_first: z.string().optional(),
  mother_middle: z.string().optional(),
  mother_phone: z.string().optional(),
  guardian_last: z.string().optional(),
  guardian_first: z.string().optional(),
  guardian_middle: z.string().optional(),
  guardian_phone: z.string().optional(),
  consent_privacy: z.boolean().refine((v) => v === true, { message: "Необходимо согласие" }),
  consent_age: z.boolean().refine((v) => v === true, { message: "Необходимо подтверждение" }),
});

type PersonalForm = z.infer<typeof personalFormSchema>;

const FORM_DEFAULTS: Partial<PersonalForm> = {
  citizenship: "KZ",
  gender: "male",
  document_type: "id",
  consent_privacy: false,
  consent_age: false,
};

export default function PersonalPage() {
  const router = useRouter();
  const {
    register,
    handleSubmit,
    control,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<PersonalForm>({
    resolver: zodResolver(personalFormSchema),
    defaultValues: FORM_DEFAULTS as PersonalForm,
  });

  useEffect(() => {
    async function load() {
      try {
        const app = await apiFetchCached<{ sections: Record<string, { payload: unknown }> }>(
          "/candidates/me/application",
          2 * 60 * 1000,
        );
        const raw = app.sections.personal?.payload as Record<string, unknown> | undefined;
        if (!raw) return;
        reset({
          ...FORM_DEFAULTS,
          preferred_first_name: String(raw.preferred_first_name ?? ""),
          preferred_last_name: String(raw.preferred_last_name ?? ""),
          date_of_birth: raw.date_of_birth ? String(raw.date_of_birth) : "",
          pronouns: raw.pronouns ? String(raw.pronouns) : "",
          middle_name: raw.middle_name != null ? String(raw.middle_name) : "",
          gender: raw.gender === "female" ? "female" : "male",
        } as PersonalForm);
      } catch {
        /* ignore */
      }
    }
    void load();
  }, [reset]);

  async function onSubmit(data: PersonalForm) {
    /** Поля, совместимые с API `PersonalSectionPayload` (остальное — локальный UI до расширения бэкенда). */
    const payload = {
      preferred_first_name: data.preferred_first_name,
      preferred_last_name: data.preferred_last_name,
      date_of_birth: data.date_of_birth || undefined,
      pronouns: data.pronouns || undefined,
      middle_name: data.middle_name || undefined,
      gender: data.gender,
    };
    await apiFetch("/candidates/me/application/sections/personal", {
      method: "PATCH",
      json: { payload },
    });
    bustApiCache("/candidates/me");
    router.push("/application/contact");
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate>
      <FormSection title="Основная информация">
        <div className={formStyles.row3}>
          <FormField label="Фамилия" placeholder="Введите фамилию" {...register("preferred_last_name")} />
          <FormField label="Имя" placeholder="Введите имя" {...register("preferred_first_name")} />
          <FormField label="Отчество" placeholder="Введите отчество" {...register("middle_name")} />
        </div>
        <div className={formStyles.row3}>
          <FormField label="Дата рождения" placeholder="ДД.ММ.ГГГГ" type="text" {...register("date_of_birth")} />
          <div className={`${formStyles.field} ${formStyles.fieldSpan2}`}>
            <span className={formStyles.label}>Пол</span>
            <Controller
              name="gender"
              control={control}
              render={({ field }) => (
                <PillSegmentedControl
                  aria-label="Пол"
                  options={[
                    { value: "male", label: "Мужской" },
                    { value: "female", label: "Женский" },
                  ]}
                  value={field.value ?? "male"}
                  onChange={field.onChange}
                />
              )}
            />
          </div>
        </div>
        {(errors.preferred_first_name || errors.preferred_last_name) && (
          <p className="error" style={{ color: "#dc2626", fontSize: 14, margin: 0 }}>
            {errors.preferred_first_name?.message || errors.preferred_last_name?.message}
          </p>
        )}
      </FormSection>

      <Divider />

      <FormSection title="Документы">
        <div className={formStyles.row3}>
          <SelectField
            label="Гражданство"
            {...register("citizenship")}
            options={[
              { value: "KZ", label: "Казахстан" },
              { value: "OTHER", label: "Другое" },
            ]}
          />
          <FormField label="ИИН" placeholder="Введите ИИН" {...register("iin")} />
        </div>
        <div className={formStyles.row3}>
          <div className={formStyles.field}>
            <span className={formStyles.label}>Тип документа</span>
            <Controller
              name="document_type"
              control={control}
              render={({ field }) => (
                <PillSegmentedControl
                  aria-label="Тип документа"
                  options={[
                    { value: "id", label: "Уд. личности" },
                    { value: "passport", label: "Паспорт" },
                  ]}
                  value={field.value ?? "id"}
                  onChange={field.onChange}
                />
              )}
            />
          </div>
        </div>
        <div className={formStyles.row3}>
          <FormField label="Номер документа" placeholder="Введите номер документа" {...register("document_number")} />
          <FormField label="Дата выдачи" placeholder="ДД.ММ.ГГГГ" {...register("document_issue_date")} />
          <FormField label="Выдан" placeholder="Введите кем выдан" {...register("document_issued_by")} />
        </div>
        <FileUploadField label="Ваш документ" />
      </FormSection>

      <Divider />

      <FormSection title="Родители">
        <h3 className={`${formStyles.subheading} ${formStyles.subheadingFirst}`}>Отец</h3>
        <div className={formStyles.row3}>
          <FormField label="Фамилия" placeholder="Введите фамилию" {...register("father_last")} />
          <FormField label="Имя" placeholder="Введите имя" {...register("father_first")} />
          <FormField label="Отчество" placeholder="Введите отчество" {...register("father_middle")} />
        </div>
        <div className={formStyles.row3}>
          <FormField label="Номер телефона" placeholder="+7" type="tel" {...register("father_phone")} />
        </div>

        <h3 className={formStyles.subheading}>Мать</h3>
        <div className={formStyles.row3}>
          <FormField label="Фамилия" placeholder="Введите фамилию" {...register("mother_last")} />
          <FormField label="Имя" placeholder="Введите имя" {...register("mother_first")} />
          <FormField label="Отчество" placeholder="Введите отчество" {...register("mother_middle")} />
        </div>
        <div className={formStyles.row3}>
          <FormField label="Номер телефона" placeholder="+7" type="tel" {...register("mother_phone")} />
        </div>

        <h3 className={formStyles.subheading}>Опекун</h3>
        <div className={formStyles.row3}>
          <FormField label="Фамилия" placeholder="Введите фамилию" {...register("guardian_last")} />
          <FormField label="Имя" placeholder="Введите имя" {...register("guardian_first")} />
          <FormField label="Отчество" placeholder="Введите отчество" {...register("guardian_middle")} />
        </div>
        <div className={formStyles.row3}>
          <FormField label="Номер телефона" placeholder="+7" type="tel" {...register("guardian_phone")} />
        </div>
      </FormSection>

      <Divider />

      <div className={formStyles.consentBlock}>
        <Controller
          name="consent_privacy"
          control={control}
          render={({ field }) => (
            <ConsentCheckbox checked={field.value} onChange={field.onChange}>
              Отправляя эту форму, вы соглашаетесь на обработку ваших персональных данных в соответствии с нашей{" "}
              <Link href="/privacy">Политикой конфиденциальности</Link>
            </ConsentCheckbox>
          )}
        />
        {errors.consent_privacy && (
          <p style={{ color: "#dc2626", fontSize: 14, margin: 0 }}>{errors.consent_privacy.message}</p>
        )}
        <Controller
          name="consent_age"
          control={control}
          render={({ field }) => (
            <ConsentCheckbox checked={field.value} onChange={field.onChange}>
              Если участнику меньше 18 лет, эту анкету должен заполнить его родитель или законный представитель.
              Продолжая, вы подтверждаете, что вы либо (a) участник в возрасте 18 лет или старше, либо (b) родитель или
              законный представитель, заполняющий эту форму от имени несовершеннолетнего
            </ConsentCheckbox>
          )}
        />
        {errors.consent_age && (
          <p style={{ color: "#dc2626", fontSize: 14, margin: 0 }}>{errors.consent_age.message}</p>
        )}
      </div>

      <button type="submit" className={formStyles.nextBtn} disabled={isSubmitting}>
        {isSubmitting ? "Сохранение…" : "Далее"}
      </button>
    </form>
  );
}

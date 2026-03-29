"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useForm, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { apiFetch, apiFetchCached, ApiError, bustApiCache, uploadDocumentForm } from "@/lib/api-client";
import { personalSchema } from "@/lib/validation";
import { PillSegmentedControl } from "@/components/application/PillSegmentedControl";
import { FormSection } from "@/components/application/FormSection";
import { FormField } from "@/components/application/FormField";
import { Divider } from "@/components/application/Divider";
import { SelectField } from "@/components/application/SelectField";
import { FileUploadField, type UploadedFileDisplay } from "@/components/application/FileUploadField";
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
  identity_document_id: z.string().optional(),
});

type PersonalForm = z.infer<typeof personalFormSchema>;

type DocRow = { id: string; document_type: string; original_filename: string; byte_size: number };

function isUuid(s: string | undefined): s is string {
  return !!s && /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(s);
}

function docMetaForId(docs: DocRow[], docId: string | undefined): UploadedFileDisplay | null {
  if (!docId) return null;
  const d = docs.find((x) => x.id === docId);
  return d ? { name: d.original_filename, sizeBytes: d.byte_size } : null;
}

const FORM_DEFAULTS: Partial<PersonalForm> = {
  citizenship: "KZ",
  gender: "male",
  document_type: "id",
  consent_privacy: false,
  consent_age: false,
};

export default function PersonalPage() {
  const router = useRouter();
  const [applicationId, setApplicationId] = useState<string | null>(null);
  const [identityFileMeta, setIdentityFileMeta] = useState<UploadedFileDisplay | null>(null);
  const [identityUploading, setIdentityUploading] = useState(false);
  const [pageMsg, setPageMsg] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    control,
    reset,
    setValue,
    getValues,
    formState: { errors, isSubmitting },
  } = useForm<PersonalForm>({
    resolver: zodResolver(personalFormSchema),
    defaultValues: FORM_DEFAULTS as PersonalForm,
  });

  const uploadIdentityDocument = useCallback(
    async (file: File | null) => {
      if (!file) {
        if (!applicationId) return;
        try {
          const v = getValues();
          await apiFetch("/candidates/me/application/sections/personal", {
            method: "PATCH",
            json: {
              payload: {
                preferred_first_name: v.preferred_first_name,
                preferred_last_name: v.preferred_last_name,
                date_of_birth: v.date_of_birth || undefined,
                pronouns: v.pronouns || undefined,
                middle_name: v.middle_name || undefined,
                gender: v.gender,
                identity_document_id: null,
              },
            },
          });
          setValue("identity_document_id", undefined, { shouldValidate: true, shouldDirty: true });
          setIdentityFileMeta(null);
          bustApiCache("/candidates/me");
          setPageMsg(null);
        } catch (e) {
          setPageMsg(e instanceof Error ? e.message : "Не удалось удалить файл");
        }
        return;
      }

      if (!applicationId) {
        setPageMsg("Не удалось определить заявление. Обновите страницу.");
        return;
      }

      const rollback = identityFileMeta;
      setIdentityFileMeta({ name: file.name, sizeBytes: file.size });
      setIdentityUploading(true);
      setPageMsg(null);

      const fd = new FormData();
      fd.append("application_id", applicationId);
      fd.append("document_type", "supporting_documents");
      fd.append("file", file);
      try {
        const data = await uploadDocumentForm<{
          id: string;
          original_filename?: string;
          byte_size?: number;
        }>(fd);
        setValue("identity_document_id", data.id, { shouldValidate: true, shouldDirty: true });
        setIdentityFileMeta({
          name: data.original_filename ?? file.name,
          sizeBytes: data.byte_size ?? file.size,
        });
        bustApiCache("/candidates/me");
        setPageMsg(null);
      } catch (e) {
        setIdentityFileMeta(rollback);
        setPageMsg(e instanceof ApiError ? e.message : e instanceof Error ? e.message : "Не удалось загрузить файл");
      } finally {
        setIdentityUploading(false);
      }
    },
    [applicationId, getValues, identityFileMeta, setValue],
  );

  useEffect(() => {
    async function load() {
      try {
        const app = await apiFetchCached<{
          application: { id: string };
          sections: Record<string, { payload: unknown }>;
          documents?: DocRow[];
        }>("/candidates/me/application", 2 * 60 * 1000);
        setApplicationId(app.application.id);
        const raw = app.sections.personal?.payload as Record<string, unknown> | undefined;
        const docs = app.documents ?? [];
        if (!raw) return;
        const idDoc = raw.identity_document_id != null ? String(raw.identity_document_id) : undefined;
        reset({
          ...FORM_DEFAULTS,
          preferred_first_name: String(raw.preferred_first_name ?? ""),
          preferred_last_name: String(raw.preferred_last_name ?? ""),
          date_of_birth: raw.date_of_birth ? String(raw.date_of_birth) : "",
          pronouns: raw.pronouns ? String(raw.pronouns) : "",
          middle_name: raw.middle_name != null ? String(raw.middle_name) : "",
          gender: raw.gender === "female" ? "female" : "male",
          identity_document_id: idDoc,
        } as PersonalForm);
        setIdentityFileMeta(docMetaForId(docs, idDoc));
      } catch {
        setPageMsg("Не удалось загрузить данные заявления. Обновите страницу.");
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
      identity_document_id: isUuid(data.identity_document_id) ? data.identity_document_id : undefined,
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
      {pageMsg ? (
        <p className="error" role="alert" style={{ margin: "0 0 16px" }}>
          {pageMsg}
        </p>
      ) : null}
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
        <input type="hidden" {...register("identity_document_id")} />
        <FileUploadField
          label="Ваш документ"
          hint="Разрешенные форматы: .PDF .JPEG .PNG .HEIC до 10MB"
          uploadedFile={identityFileMeta}
          isUploading={identityUploading}
          onFile={(f) => void uploadIdentityDocument(f)}
        />
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

      <div className={formStyles.formFooter}>
        <button type="submit" className="btn" disabled={isSubmitting}>
          {isSubmitting ? "Сохранение…" : "Далее"}
        </button>
      </div>
    </form>
  );
}

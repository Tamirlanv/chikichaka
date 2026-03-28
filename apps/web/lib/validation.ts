import { z } from "zod";

export const registerSchema = z
  .object({
    email: z.string().email({ message: "Укажите корректный email" }),
    password: z.string().min(12, { message: "Не менее 12 символов" }).max(128, { message: "Не более 128 символов" }),
    first_name: z.string().min(1, { message: "Обязательное поле" }).max(128),
    last_name: z.string().min(1, { message: "Обязательное поле" }).max(128),
  })
  .superRefine((data, ctx) => {
    if (!/[A-Z]/.test(data.password)) {
      ctx.addIssue({ code: "custom", message: "В пароле нужна заглавная буква", path: ["password"] });
    }
    if (!/[a-z]/.test(data.password)) {
      ctx.addIssue({ code: "custom", message: "В пароле нужна строчная буква", path: ["password"] });
    }
    if (!/\d/.test(data.password)) {
      ctx.addIssue({ code: "custom", message: "В пароле нужна цифра", path: ["password"] });
    }
  });

/** Форма регистрации (UI): одно поле имени, подтверждение пароля, согласие. */
export const registerPageSchema = z
  .object({
    name: z.string().min(1, { message: "Введите имя" }).max(256),
    email: z.string().email({ message: "Некорректный e-mail" }),
    password: z.string().min(12, { message: "Не менее 12 символов" }).max(128, { message: "Не более 128 символов" }),
    confirmPassword: z.string().min(1, { message: "Подтвердите пароль" }),
    agreedToTerms: z.boolean().refine((v) => v === true, { message: "Необходимо принять соглашение" }),
  })
  .superRefine((data, ctx) => {
    if (!/[A-Z]/.test(data.password)) {
      ctx.addIssue({ code: "custom", message: "В пароле нужна заглавная буква", path: ["password"] });
    }
    if (!/[a-z]/.test(data.password)) {
      ctx.addIssue({ code: "custom", message: "В пароле нужна строчная буква", path: ["password"] });
    }
    if (!/\d/.test(data.password)) {
      ctx.addIssue({ code: "custom", message: "В пароле нужна цифра", path: ["password"] });
    }
    if (data.password !== data.confirmPassword) {
      ctx.addIssue({ code: "custom", message: "Пароли не совпадают", path: ["confirmPassword"] });
    }
  });

export type RegisterPageForm = z.infer<typeof registerPageSchema>;

export const verifyCodeSchema = z.object({
  code: z
    .string()
    .length(6, { message: "Введите 6 цифр" })
    .regex(/^\d{6}$/, { message: "Только цифры" }),
});

export type VerifyCodeForm = z.infer<typeof verifyCodeSchema>;

/** Разбор «Имя Фамилия» в поля API (одно слово → фамилия-заглушка). */
export function splitNameToProfile(name: string): { first_name: string; last_name: string } {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) {
    return { first_name: "", last_name: "—" };
  }
  if (parts.length === 1) {
    return { first_name: parts[0], last_name: "—" };
  }
  return { first_name: parts[0], last_name: parts.slice(1).join(" ") };
}

export const loginSchema = z.object({
  email: z.string().email({ message: "Укажите корректный email" }),
  password: z.string().min(1, { message: "Введите пароль" }),
});

export const personalSchema = z.object({
  preferred_first_name: z.string().min(1, { message: "Обязательное поле" }),
  preferred_last_name: z.string().min(1, { message: "Обязательное поле" }),
  date_of_birth: z.string().optional(),
  pronouns: z.string().optional(),
});

export const contactSchema = z.object({
  phone_e164: z.string().min(8, { message: "Укажите телефон в формате E.164" }).max(32),
  address_line1: z.string().min(1, { message: "Обязательное поле" }),
  address_line2: z.string().optional(),
  city: z.string().min(1, { message: "Обязательное поле" }),
  region: z.string().optional(),
  postal_code: z.string().optional(),
  country: z.string().length(2, { message: "Код страны ISO-2 (2 буквы)" }),
});

export const educationSchema = z.object({
  entries: z
    .array(
      z.object({
        institution_name: z.string().min(1, { message: "Укажите учебное заведение" }),
        degree_or_program: z.string().optional(),
        field_of_study: z.string().optional(),
        start_date: z.string().optional(),
        end_date: z.string().optional(),
        is_current: z.boolean(),
      }),
    )
    .min(1, { message: "Добавьте хотя бы одну запись об образовании" }),
});

export const socialSchema = z.object({
  attestation: z.string().min(10, { message: "Не менее 10 символов" }).max(2000, { message: "Не более 2000 символов" }),
});

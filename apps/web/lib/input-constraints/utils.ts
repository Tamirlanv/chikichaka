import { DATE_RAW_LENGTH, DEFAULT_TEXT_MAX_LENGTH, IIN_LENGTH, PHONE_RAW_LENGTH } from "./config";

export function keepOnlyDigits(value: string): string {
  return value.replace(/\D+/g, "");
}

export function limitLength(value: string, max: number): string {
  if (max <= 0) return "";
  return value.length <= max ? value : value.slice(0, max);
}

export function sanitizeText(value: string, maxLength = DEFAULT_TEXT_MAX_LENGTH): string {
  const withoutInvisible = value.replace(/[\u0000-\u001f\u007f-\u009f\u200b-\u200d\ufeff]/g, "");
  const normalizedSpaces = withoutInvisible.replace(/\s+/g, " ");
  return limitLength(normalizedSpaces.trim(), maxLength);
}

export function sanitizeLatinUsername(value: string, maxLength = DEFAULT_TEXT_MAX_LENGTH): string {
  const withoutInvisible = value.replace(/[\u0000-\u001f\u007f-\u009f\u200b-\u200d\ufeff]/g, "");
  const trimmed = withoutInvisible.trim();
  const startsWithAt = trimmed.startsWith("@");
  const body = trimmed.replace(/@/g, "").replace(/[^A-Za-z0-9._]/g, "");
  const normalized = startsWithAt ? `@${body}` : body;
  return limitLength(normalized, maxLength);
}

export function normalizeKzPhoneRaw(value: string): string {
  let digits = keepOnlyDigits(value);

  if (!digits) return "";

  if (digits.startsWith("8")) {
    digits = `7${digits.slice(1)}`;
  } else if (!digits.startsWith("7") && digits.length === 10) {
    digits = `7${digits}`;
  } else if (!digits.startsWith("7") && digits.length >= 11) {
    digits = `7${digits.slice(1)}`;
  }

  return limitLength(digits, PHONE_RAW_LENGTH);
}

export function formatPhone(value: string): string {
  const raw = normalizeKzPhoneRaw(value);
  if (!raw) return "";

  const body = raw.startsWith("7") ? raw.slice(1) : raw;
  const g1 = body.slice(0, 3);
  const g2 = body.slice(3, 6);
  const g3 = body.slice(6, 8);
  const g4 = body.slice(8, 10);

  let out = "+7";
  if (g1) out += ` ${g1}`;
  if (g2) out += ` ${g2}`;
  if (g3) out += ` ${g3}`;
  if (g4) out += ` ${g4}`;
  return out;
}

export function formatIIN(value: string): string {
  return limitLength(keepOnlyDigits(value), IIN_LENGTH);
}

export function formatDate(value: string): string {
  const raw = limitLength(keepOnlyDigits(value), DATE_RAW_LENGTH);
  const day = raw.slice(0, 2);
  const month = raw.slice(2, 4);
  const year = raw.slice(4, 8);

  if (raw.length <= 2) return day;
  if (raw.length <= 4) return `${day}.${month}`;
  return `${day}.${month}.${year}`;
}

export function isDateRangePotentiallyValid(rawDateDigits: string): boolean {
  const digits = limitLength(keepOnlyDigits(rawDateDigits), DATE_RAW_LENGTH);
  if (digits.length < 8) return true;

  const day = Number(digits.slice(0, 2));
  const month = Number(digits.slice(2, 4));
  const year = Number(digits.slice(4, 8));
  return day >= 1 && day <= 31 && month >= 1 && month <= 12 && year >= 1900 && year <= 2100;
}

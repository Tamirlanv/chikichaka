/** Общие правила для загрузок анкеты: PDF / изображения / HEIC, до 10 МБ */

export const MAX_UPLOAD_BYTES = 10 * 1024 * 1024;

const EXTENSIONS = [".pdf", ".jpg", ".jpeg", ".png", ".heic", ".heif"] as const;

const ALLOWED_MIME = new Set([
  "application/pdf",
  "image/jpeg",
  "image/png",
  "image/heic",
  "image/heif",
]);

function extensionOf(name: string): string {
  const i = name.lastIndexOf(".");
  return i >= 0 ? name.slice(i).toLowerCase() : "";
}

export function validateUploadFile(file: File): { ok: true } | { ok: false; message: string } {
  if (file.size > MAX_UPLOAD_BYTES) {
    return {
      ok: false,
      message: `Файл больше 10 МБ (${formatFileSize(file.size)}). Выберите файл до 10 МБ.`,
    };
  }
  const ext = extensionOf(file.name);
  if (!EXTENSIONS.includes(ext as (typeof EXTENSIONS)[number])) {
    return {
      ok: false,
      message: "Разрешены только файлы .PDF, .JPEG, .PNG и .HEIC",
    };
  }
  const mime = (file.type || "").split(";")[0].trim().toLowerCase();
  if (mime && !ALLOWED_MIME.has(mime)) {
    /* Браузеры часто отдают application/octet-stream вместо реального MIME — доверяем расширению */
    if (mime === "application/octet-stream" && EXTENSIONS.includes(ext as (typeof EXTENSIONS)[number])) {
      return { ok: true };
    }
    return {
      ok: false,
      message: "Неподдерживаемый тип файла. Используйте .PDF, .JPEG, .PNG или .HEIC",
    };
  }
  return { ok: true };
}

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

import { apiServerBase } from "./config";
import { getCached, setCached } from "./api-cache";

export { bustApiCache } from "./api-cache";

export class ApiError extends Error {
  status: number;
  body: unknown;
  constructor(message: string, status: number, body: unknown) {
    super(message);
    this.status = status;
    this.body = body;
  }
}

async function parseJsonSafe(res: Response): Promise<unknown> {
  const text = await res.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

/** Текст ошибки из ответа FastAPI (detail: str | list | object) */
export function formatApiErrorBody(data: unknown): string {
  if (data === null || data === undefined) return "Ошибка запроса";
  if (typeof data === "string") return data;
  if (typeof data === "object" && data !== null && "detail" in data) {
    const d = (data as { detail: unknown }).detail;
    if (typeof d === "string") return d;
    if (Array.isArray(d)) {
      return d
        .map((item) => {
          if (typeof item === "object" && item !== null && "msg" in item) {
            return String((item as { msg: unknown }).msg);
          }
          return JSON.stringify(item);
        })
        .join(" ");
    }
    if (d !== null && typeof d === "object") {
      return JSON.stringify(d);
    }
    return String(d);
  }
  if (typeof data === "object") return JSON.stringify(data);
  return String(data);
}

function apiBaseUrl(): string {
  if (typeof window === "undefined") {
    return apiServerBase();
  }
  return "";
}

export async function apiFetch<T>(
  path: string,
  init: RequestInit & { json?: unknown } = {},
): Promise<T> {
  const { json, headers, ...rest } = init;
  const base = apiBaseUrl();
  const rel = path.startsWith("/api/v1") ? path : `/api/v1${path.startsWith("/") ? path : `/${path}`}`;
  const url = path.startsWith("http") ? path : `${base}${rel}`;
  const h = new Headers(headers);
  if (json !== undefined) {
    h.set("Content-Type", "application/json");
  }
  const res = await fetch(url, {
    ...rest,
    headers: h,
    body: json !== undefined ? JSON.stringify(json) : rest.body,
    credentials: "include",
    cache: "no-store",
  });
  const data = await parseJsonSafe(res);
  if (!res.ok) {
    const msg =
      typeof data === "string"
        ? data.slice(0, 500)
        : data !== null && typeof data === "object"
          ? formatApiErrorBody(data)
          : `Request failed (${res.status})`;
    throw new ApiError(msg, res.status, data);
  }
  return data as T;
}

/** Multipart POST /api/v1/documents/upload (credentials, без Content-Type — boundary задаёт браузер). */
export async function uploadDocumentForm<T extends Record<string, unknown>>(fd: FormData): Promise<T> {
  const base = apiBaseUrl();
  const url = `${base}/api/v1/documents/upload`;
  const res = await fetch(url, {
    method: "POST",
    body: fd,
    credentials: "include",
    cache: "no-store",
  });
  const data = await parseJsonSafe(res);
  if (!res.ok) {
    throw new ApiError(formatApiErrorBody(data), res.status, data);
  }
  return data as T;
}

/** Cached GET for client-side deduplication (see api-cache). */
export async function apiFetchCached<T>(path: string, ttlMs: number): Promise<T> {
  if (typeof window === "undefined") {
    return apiFetch<T>(path);
  }
  const hit = getCached<T>(path);
  if (hit !== undefined) return hit;
  const data = await apiFetch<T>(path);
  setCached(path, data, ttlMs);
  return data;
}

export async function refreshSession(): Promise<boolean> {
  try {
    await apiFetch("/api/v1/auth/refresh", { method: "POST" });
    return true;
  } catch {
    return false;
  }
}

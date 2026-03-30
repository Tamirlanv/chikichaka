/**
 * База FastAPI для Server Components / SSR (полный URL).
 * В браузере `apiFetch` использует относительные пути `/api/v1/...` → `next.config` rewrites на бэкенд.
 * Docker: задайте `API_INTERNAL_URL=http://api:8000`. Vercel: `API_INTERNAL_URL=https://….up.railway.app`.
 */
export function apiServerBase(): string {
  const raw =
    process.env.API_INTERNAL_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  return raw.replace(/\/$/, "");
}

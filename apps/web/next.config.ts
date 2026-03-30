import type { NextConfig } from "next";
import path from "path";

function backendBaseUrl(): string {
  const raw =
    process.env.API_INTERNAL_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    "http://127.0.0.1:8000";
  return raw.replace(/\/$/, "");
}

const nextConfig: NextConfig = {
  reactStrictMode: true,
  /** Скрыть стандартный индикатор Next.js (кнопка слева снизу в dev). Ошибки сборки/рантайма по-прежнему показываются. */
  devIndicators: false,
  outputFileTracingRoot: path.join(__dirname, "../.."),
  experimental: {
    serverActions: {
      bodySizeLimit: "15mb",
    },
    middlewareClientMaxBodySize: "15mb",
  },
  /**
   * Прокси `/api/*` → FastAPI (Railway / локальный uvicorn).
   * На Vercel задайте `API_INTERNAL_URL=https://…up.railway.app` (без слэша в конце) в Env — и для build, и для runtime.
   * Браузер шлёт относительные `/api/v1/...`; Next не дергает localhost внутри serverless.
   */
  async rewrites() {
    const base = backendBaseUrl();
    return [
      {
        source: "/api/:path*",
        destination: `${base}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;

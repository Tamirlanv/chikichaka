import type { NextConfig } from "next";
import path from "path";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  /** Скрыть стандартный индикатор Next.js (кнопка слева снизу в dev). Ошибки сборки/рантайма по-прежнему показываются. */
  devIndicators: false,
  outputFileTracingRoot: path.join(__dirname, "../.."),
  experimental: {
    serverActions: {
      bodySizeLimit: "15mb",
    },
    /** См. middleware.ts — лимит тела для прокси/клонирования запроса */
    middlewareClientMaxBodySize: "15mb",
  },
  /** Прокси к FastAPI: `app/api/v1/[[...path]]/route.ts` */
};

export default nextConfig;

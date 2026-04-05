/**
 * Демо-ролики на главной странице.
 * Замените URL ниже на реальные ссылки YouTube для этапа 2, этапа 3 и полной версии.
 * Одна и та же ссылка используется для кнопки «Смотреть» и для встроенного предпросмотра.
 */

export type DemoVideoEntry = {
  /** Полная ссылка: watch?v=, youtu.be/, embed/… */
  youtubeUrl: string;
};

export const DEMO_VIDEOS: readonly DemoVideoEntry[] = [
  { youtubeUrl: "https://youtu.be/LqthoTXZY0Q?si=S3m_UuEDZFJR1iol" },
  { youtubeUrl: "https://youtu.be/LqthoTXZY0Q?si=S3m_UuEDZFJR1iol" },
  { youtubeUrl: "https://youtu.be/LqthoTXZY0Q?si=S3m_UuEDZFJR1iol" },
] as const;

/** Плейсхолдеры из шаблона (не настоящие id). */
const PLACEHOLDER_RE = /^VIDEO_ID/i;

/** 11 символов — типичный id ролика YouTube. */
const YOUTUBE_ID_RE =
  /(?:youtu\.be\/|youtube\.com\/(?:embed\/|shorts\/|live\/|watch\?[^#]*?v=))([A-Za-z0-9_-]{11})(?=[?&#/]|$)/;

const V_PARAM_RE = /[?&]v=([A-Za-z0-9_-]{11})(?:&|#|$)/;

function normalizeYoutubeInput(raw: string): string {
  let s = raw
    .trim()
    .replace(/[\u200B-\u200D\uFEFF]/g, "")
    .replace(/[\u201C\u201D]/g, '"');
  if (s.startsWith("//")) s = `https:${s}`;
  return s;
}

function isPlaceholderId(id: string): boolean {
  return PLACEHOLDER_RE.test(id);
}

/**
 * Извлекает id ролика из типичных URL YouTube.
 * Дублирует разбор через URL и через regex — на случай нестандартных query / мобильных ссылок.
 */
export function parseYouTubeVideoId(url: string): string | null {
  const t = normalizeYoutubeInput(url);
  if (!t) return null;

  const tryFromUrl = (): string | null => {
    try {
      const href = /^https?:\/\//i.test(t) ? t : `https://${t}`;
      const u = new URL(href);
      const host = u.hostname.toLowerCase();

      if (host === "youtu.be") {
        const id = u.pathname.replace(/^\//, "").split("/").filter(Boolean)[0] ?? "";
        return id && !isPlaceholderId(id) ? id : null;
      }

      if (host.endsWith("youtube.com") || host.endsWith("youtube-nocookie.com")) {
        if (u.pathname.startsWith("/embed/")) {
          const id = u.pathname.slice("/embed/".length).split("/")[0] ?? "";
          return id && !isPlaceholderId(id) ? id : null;
        }
        if (u.pathname.startsWith("/shorts/")) {
          const id = u.pathname.slice("/shorts/".length).split("/")[0] ?? "";
          return id && !isPlaceholderId(id) ? id : null;
        }
        if (u.pathname.startsWith("/live/")) {
          const id = u.pathname.slice("/live/".length).split("/")[0] ?? "";
          return id && !isPlaceholderId(id) ? id : null;
        }
        const v = u.searchParams.get("v");
        if (v && !isPlaceholderId(v)) return v;
      }
    } catch {
      return null;
    }
    return null;
  };

  const fromUrl = tryFromUrl();
  if (fromUrl) return fromUrl;

  const m1 = t.match(YOUTUBE_ID_RE);
  if (m1?.[1] && !isPlaceholderId(m1[1])) return m1[1];

  const m2 = t.match(V_PARAM_RE);
  if (m2?.[1] && !isPlaceholderId(m2[1])) return m2[1];

  return null;
}

/**
 * URL для iframe предпросмотра (основной домен embed — совместимость с политиками сети / браузера).
 */
export function getYouTubeEmbedSrc(url: string): string | null {
  const id = parseYouTubeVideoId(url);
  if (!id) return null;
  return `https://www.youtube.com/embed/${encodeURIComponent(id)}?rel=0`;
}

/** Есть id для встраивания. */
export function hasConfiguredYouTubeUrl(url: string): boolean {
  return parseYouTubeVideoId(url) !== null;
}

/**
 * Можно ли открыть ссылку «Смотреть»: https и домен YouTube (даже если id для embed не распознан).
 */
export function isOpenableYouTubePageUrl(url: string): boolean {
  const t = normalizeYoutubeInput(url);
  const href = /^https?:\/\//i.test(t) ? t : `https://${t}`;
  try {
    const u = new URL(href);
    const h = u.hostname.toLowerCase();
    return h === "youtu.be" || h.endsWith("youtube.com") || h.endsWith("youtube-nocookie.com");
  } catch {
    return false;
  }
}

/** Абсолютная ссылка для кнопки «Смотреть» или null. */
export function getYouTubeWatchHref(url: string): string | null {
  const t = normalizeYoutubeInput(url);
  if (!t) return null;
  const href = /^https?:\/\//i.test(t) ? t : `https://${t}`;
  if (!isOpenableYouTubePageUrl(href)) return null;
  try {
    return new URL(href).toString();
  } catch {
    return null;
  }
}

type VideoPreviewKind = "youtube" | "direct" | "external";

export type VideoPreviewMeta = {
  platformLabel: string;
  previewKind: VideoPreviewKind;
  previewUrl: string | null;
  externalUrl: string | null;
};

const DIRECT_VIDEO_EXTENSIONS = [".mp4", ".webm", ".mov", ".m4v", ".mkv", ".avi", ".m3u8"];

function safeParseUrl(raw: string): URL | null {
  const s = (raw || "").trim();
  if (!s) return null;
  try {
    return new URL(s);
  } catch {
    return null;
  }
}

function isDirectVideoPath(pathname: string): boolean {
  const lower = pathname.toLowerCase();
  return DIRECT_VIDEO_EXTENSIONS.some((ext) => lower.endsWith(ext));
}

function toYouTubeEmbedUrl(url: URL): string | null {
  const host = url.hostname.replace(/^www\./i, "").toLowerCase();
  if (host === "youtu.be") {
    const id = url.pathname.split("/").filter(Boolean)[0];
    return id ? `https://www.youtube.com/embed/${id}` : null;
  }
  if (host.endsWith("youtube.com")) {
    const path = url.pathname.toLowerCase();
    if (path === "/watch") {
      const id = url.searchParams.get("v");
      return id ? `https://www.youtube.com/embed/${id}` : null;
    }
    if (path.startsWith("/shorts/")) {
      const id = path.split("/").filter(Boolean)[1];
      return id ? `https://www.youtube.com/embed/${id}` : null;
    }
    if (path.startsWith("/embed/")) {
      return url.toString();
    }
  }
  return null;
}

export function resolveVideoPreviewMeta(rawUrl: string | null | undefined): VideoPreviewMeta {
  const parsed = safeParseUrl(rawUrl ?? "");
  if (!parsed) {
    return {
      platformLabel: "Не определена",
      previewKind: "external",
      previewUrl: null,
      externalUrl: null,
    };
  }

  const host = parsed.hostname.replace(/^www\./i, "").toLowerCase();
  const full = parsed.toString();

  const ytEmbed = toYouTubeEmbedUrl(parsed);
  if (ytEmbed) {
    return {
      platformLabel: "YouTube",
      previewKind: "youtube",
      previewUrl: ytEmbed,
      externalUrl: full,
    };
  }

  if (host.includes("drive.google.com")) {
    return {
      platformLabel: "Google Drive",
      previewKind: "external",
      previewUrl: null,
      externalUrl: full,
    };
  }

  if (host.includes("dropbox.com")) {
    return {
      platformLabel: "Dropbox",
      previewKind: "external",
      previewUrl: null,
      externalUrl: full,
    };
  }

  if (isDirectVideoPath(parsed.pathname)) {
    return {
      platformLabel: "Прямая ссылка",
      previewKind: "direct",
      previewUrl: full,
      externalUrl: full,
    };
  }

  return {
    platformLabel: "Публичная ссылка",
    previewKind: "external",
    previewUrl: null,
    externalUrl: full,
  };
}

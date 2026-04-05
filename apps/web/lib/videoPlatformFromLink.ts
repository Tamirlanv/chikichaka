/** Определяет подпись платформы по URL (Zoom, Google Meet, Discord). */
export function detectVideoPlatformFromUrl(raw: string | null | undefined): string | null {
  const s = (raw || "").trim();
  if (!s) return null;
  const tryUrl = s.includes("://") ? s : `https://${s}`;
  try {
    const u = new URL(tryUrl);
    const host = u.hostname.replace(/^www\./i, "").toLowerCase();
    if (host === "meet.google.com" || host.endsWith(".meet.google.com")) {
      return "Google Meet";
    }
    if (host.endsWith("zoom.us") || host.endsWith("zoomgov.com") || host === "zoom.us") {
      return "Zoom";
    }
    if (
      host === "discord.gg" ||
      host.endsWith(".discord.gg") ||
      host === "discord.com" ||
      host.endsWith(".discord.com")
    ) {
      return "Discord";
    }
  } catch {
    /* fall through */
  }
  const low = s.toLowerCase();
  if (low.includes("meet.google.com")) return "Google Meet";
  if (low.includes("zoom.us") || low.includes("zoomgov.com")) return "Zoom";
  if (low.includes("discord.gg") || low.includes("discord.com")) return "Discord";
  return null;
}

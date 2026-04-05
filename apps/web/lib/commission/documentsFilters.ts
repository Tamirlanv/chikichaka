import type { CommissionApplicationPersonalInfoView } from "./types";

export type DocumentCategoryFilter = "all" | "identity" | "presentation" | "english" | "ent_nis";

type DocRow = CommissionApplicationPersonalInfoView["personalInfo"]["documents"][number];

function matchesIdentity(typeLower: string): boolean {
  return typeLower.includes("удостовер") || typeLower.includes("паспорт");
}

function matchesEnglish(typeLower: string): boolean {
  return (
    typeLower.includes("ielts") ||
    typeLower.includes("toefl") ||
    typeLower.includes("английск") ||
    typeLower.includes("english")
  );
}

function matchesEntNis(typeLower: string): boolean {
  return (
    typeLower.includes("ент") ||
    typeLower.includes("ниш") ||
    typeLower.includes("nis") ||
    typeLower.includes("nazarbayev") ||
    typeLower.includes("етн")
  );
}

/** Клиентская фильтрация документов и видео по вкладке (без повторного запроса к API). */
export function filterDocumentsForCategory(
  docs: DocRow[],
  video: CommissionApplicationPersonalInfoView["personalInfo"]["videoPresentation"],
  filter: DocumentCategoryFilter,
): { documents: DocRow[]; showVideo: boolean } {
  const hasVideo = Boolean(video?.url?.trim());

  if (filter === "all") {
    return { documents: [...docs], showVideo: hasVideo };
  }
  if (filter === "presentation") {
    return { documents: [], showVideo: hasVideo };
  }

  const out: DocRow[] = [];
  for (const d of docs) {
    const t = (d.type ?? "").toLowerCase();
    if (filter === "identity" && matchesIdentity(t)) out.push(d);
    if (filter === "english" && matchesEnglish(t)) out.push(d);
    if (filter === "ent_nis" && matchesEntNis(t)) out.push(d);
  }
  return { documents: out, showVideo: false };
}

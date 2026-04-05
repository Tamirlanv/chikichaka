import type { CommissionBoardApplicationCard, CommissionStage } from "./types";

const GRAY_1 = "1px solid #F1F1F1";
const GREEN_2 = "2px solid #98DA00";
const BLUE_2 = "2px solid #008ADA";
const ORANGE_2 = "2px solid #DACF00";

export type CardBorderCategory = "gray" | "orange" | "blue" | "green";

function categoryToBorderStyle(cat: CardBorderCategory): string {
  switch (cat) {
    case "gray":
      return GRAY_1;
    case "green":
      return GREEN_2;
    case "blue":
      return BLUE_2;
    case "orange":
      return ORANGE_2;
    default:
      return GRAY_1;
  }
}

/**
 * Semantic border color for Kanban card (sorting, hints).
 */
export function getCardBorderCategory(
  columnStage: CommissionStage,
  card: CommissionBoardApplicationCard
): CardBorderCategory {
  if (columnStage === "data_check") {
    const rs = card.dataCheckRunStatus?.trim() ?? "";
    if (rs === "ready") {
      return "green";
    }
    if (rs === "failed" || rs === "partial") {
      return "orange";
    }
    // pending, running, or unknown — still processing, no hard failure yet
    return "blue";
  }

  if (columnStage === "committee_decision" || columnStage === "result") {
    return "gray";
  }

  if (columnStage === "application_review") {
    if (card.rubricThreeSectionsComplete) {
      return "green";
    }
    if (card.stageOneDataReady && !card.rubricThreeSectionsComplete) {
      return "blue";
    }
    return "gray";
  }

  if (columnStage === "interview") {
    const aiDone = Boolean(card.aiInterviewCompletedAtIso?.trim());
    const scheduled = Boolean(card.interviewScheduledAtIso?.trim());
    if (aiDone && scheduled) {
      return "green";
    }
    if (aiDone && !scheduled) {
      return "blue";
    }
    return "orange";
  }

  return "gray";
}

/**
 * Card border by commission column (product rules) + API hints from backend.
 */
export function getCommissionCardBorderStyle(
  columnStage: CommissionStage,
  card: CommissionBoardApplicationCard
): string {
  return categoryToBorderStyle(getCardBorderCategory(columnStage, card));
}

/**
 * Short caption for the «Проверка данных» column so users see processing vs problem vs ready,
 * aligned with {@link getCardBorderCategory} (blue / orange / green).
 */
export function getDataCheckPhaseCaption(dataCheckRunStatus: string | null | undefined): string {
  const rs = dataCheckRunStatus?.trim() ?? "";
  if (rs === "failed" || rs === "partial") {
    return "Обработка завершилась с проблемами — требуется внимание";
  }
  if (rs === "ready") {
    return "Данные обработаны";
  }
  return "Идёт обработка данных";
}

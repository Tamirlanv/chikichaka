import { getCardBorderCategory, type CardBorderCategory } from "./cardBorder";
import type { CommissionBoardApplicationCard, CommissionStage } from "./types";

/** 0–3: two color orders, newest, oldest */
export type ColumnSortMode = 0 | 1 | 2 | 3;

function submittedOrUpdatedTime(c: CommissionBoardApplicationCard): number {
  const raw = c.submittedAt || c.updatedAt;
  if (!raw) return 0;
  const t = new Date(raw).getTime();
  return Number.isFinite(t) ? t : 0;
}

/** Mode 0: orange → blue → green (gray last) */
function rankColorMode0(stage: CommissionStage, card: CommissionBoardApplicationCard): number {
  const cat = getCardBorderCategory(stage, card);
  const order: Record<CardBorderCategory, number> = { orange: 0, blue: 1, green: 2, gray: 3 };
  return order[cat];
}

/** Mode 1: green → blue → orange (gray last) */
function rankColorMode1(stage: CommissionStage, card: CommissionBoardApplicationCard): number {
  const cat = getCardBorderCategory(stage, card);
  const order: Record<CardBorderCategory, number> = { green: 0, blue: 1, orange: 2, gray: 3 };
  return order[cat];
}

/**
 * Sort applications within one Kanban column (local UI only).
 */
export function sortColumnCards(
  stage: CommissionStage,
  cards: CommissionBoardApplicationCard[],
  mode: ColumnSortMode
): CommissionBoardApplicationCard[] {
  const copy = [...cards];
  const ts = submittedOrUpdatedTime;

  if (mode === 2) {
    copy.sort((a, b) => ts(b) - ts(a));
    return copy;
  }
  if (mode === 3) {
    copy.sort((a, b) => ts(a) - ts(b));
    return copy;
  }
  if (mode === 0) {
    copy.sort((a, b) => {
      const d = rankColorMode0(stage, a) - rankColorMode0(stage, b);
      if (d !== 0) return d;
      return ts(b) - ts(a);
    });
    return copy;
  }
  copy.sort((a, b) => {
    const d = rankColorMode1(stage, a) - rankColorMode1(stage, b);
    if (d !== 0) return d;
    return ts(b) - ts(a);
  });
  return copy;
}

export const COLUMN_SORT_MODE_LABELS: readonly string[] = [
  "По цвету обводки: оранжевый, синий, зелёный",
  "По цвету обводки: зелёный, синий, оранжевый",
  "Сначала новые заявки",
  "Сначала старые заявки",
];

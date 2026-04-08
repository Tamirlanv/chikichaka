import { COMMISSION_STAGE_ORDER } from "./constants";
import type { CommissionBoardColumn, CommissionRole, CommissionStage } from "./types";

export function canMoveCards(role: CommissionRole | null): boolean {
  return role === "reviewer" || role === "admin";
}

export function isNextStageOnly(from: CommissionStage, to: CommissionStage): boolean {
  const i = COMMISSION_STAGE_ORDER.indexOf(from);
  const j = COMMISSION_STAGE_ORDER.indexOf(to);
  if (i < 0 || j < 0) return false;
  return j === i + 1;
}

export function resolveDropStage(
  overId: string | null | undefined,
  columns: CommissionBoardColumn[],
): CommissionStage | null {
  const id = String(overId ?? "").trim();
  if (!id) return null;

  if (id.startsWith("column:")) {
    const stage = id.slice("column:".length) as CommissionStage;
    return COMMISSION_STAGE_ORDER.includes(stage) ? stage : null;
  }

  for (const column of columns) {
    if (column.applications.some((card) => card.applicationId === id)) {
      return column.stage;
    }
  }
  return null;
}

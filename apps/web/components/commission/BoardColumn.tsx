"use client";

import { useDroppable } from "@dnd-kit/core";
import { COLUMN_SORT_MODE_LABELS, type ColumnSortMode } from "@/lib/commission/columnSort";
import type { CommissionBoardApplicationCard, CommissionStage } from "@/lib/commission/types";
import type { CommissionPermissions } from "@/lib/commission/permissions";
import { ApplicationCard } from "./ApplicationCard";

type Props = {
  order: number;
  stage: CommissionStage;
  title: string;
  cards: CommissionBoardApplicationCard[];
  sortMode: ColumnSortMode;
  onCycleSort: () => void;
  permissions: CommissionPermissions;
  movingId: string | null;
  onQuickComment: (applicationId: string, body: string) => Promise<void>;
  onToggleAttention: (applicationId: string, value: boolean) => Promise<void>;
};

/** 2px divider under the column title — per stage (Kanban mockup). */
function columnDividerColor(stage: CommissionStage): string {
  if (stage === "data_check") return "#DACF00";
  if (stage === "application_review") return "#008ADA";
  if (stage === "interview") return "#98DA00";
  if (stage === "committee_decision") return "#F1F1F1";
  return "#98DA00";
}

function FilterIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden>
      <path
        d="M2.5 4.5h11M4.5 8h7M6.5 11.5h3"
        stroke="#262626"
        strokeOpacity={0.8}
        strokeWidth="1.5"
        strokeLinecap="round"
      />
    </svg>
  );
}

export function BoardColumn({
  order,
  stage,
  title,
  cards,
  sortMode,
  onCycleSort,
  permissions,
  movingId,
  onQuickComment,
  onToggleAttention,
}: Props) {
  const { setNodeRef, isOver } = useDroppable({ id: `column:${stage}` });
  const dividerColor = columnDividerColor(stage);
  const sortLabel = COLUMN_SORT_MODE_LABELS[sortMode] ?? COLUMN_SORT_MODE_LABELS[0];

  return (
    <section
      ref={setNodeRef}
      style={{
        display: "flex",
        flexDirection: "column",
        width: 310,
        minWidth: 310,
        flex: "0 0 310px",
        minHeight: "fit-content",
        alignSelf: "stretch",
        background: "transparent",
        borderRadius: 16,
        boxShadow: isOver ? "0 0 0 1px rgba(38, 38, 38, 0.55)" : "none",
      }}
    >
      <header
        style={{
          display: "flex",
          alignItems: "flex-end",
          justifyContent: "space-between",
          width: "100%",
          marginBottom: 20,
        }}
      >
        <div style={{ display: "flex", alignItems: "flex-end", gap: 8, flexWrap: "wrap" }}>
          <span
            style={{
              fontSize: 24,
              lineHeight: "20px",
              fontWeight: 600,
              color: "#98DA00",
              letterSpacing: "-0.72px",
              fontFamily: "var(--font-inter, Inter, system-ui, sans-serif)",
            }}
          >
            {String(order).padStart(2, "0")}
          </span>
          <h3
            style={{
              margin: 0,
              fontSize: 16,
              lineHeight: "16px",
              fontWeight: 500,
              color: "#262626",
              letterSpacing: "-0.48px",
              fontFamily: "var(--font-inter, Inter, system-ui, sans-serif)",
            }}
          >
            {title}
          </h3>
          <span className="muted" style={{ fontSize: 12, lineHeight: "16px", marginLeft: 4 }}>
            {cards.length}
          </span>
        </div>
        <button
          type="button"
          aria-label={`Сортировка в этой колонке: ${sortLabel}. Нажмите для смены режима.`}
          title={sortLabel}
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            onCycleSort();
          }}
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: 0,
            border: "none",
            background: "transparent",
            cursor: "pointer",
            flexShrink: 0,
          }}
        >
          <FilterIcon />
        </button>
      </header>

      <div
        style={{
          height: 2,
          width: "100%",
          borderRadius: 1,
          background: dividerColor,
          flexShrink: 0,
        }}
        aria-hidden
      />

      <div
        style={{
          marginTop: 20,
          display: "flex",
          flexDirection: "column",
          gap: 12,
          width: "100%",
          padding: 16,
          background: "#fff",
          borderRadius: 16,
          boxShadow: isOver ? "0 6px 28px rgba(0,0,0,0.16)" : "0 4px 24px rgba(0,0,0,0.1)",
          outline: isOver ? "1px solid rgba(38,38,38,0.55)" : "none",
          outlineOffset: 0,
          minHeight: 48,
        }}
      >
        {cards.length === 0 ? <p className="muted" style={{ margin: 0 }}>Нет заявок</p> : null}
        {cards.map((card) => (
          <ApplicationCard
            key={card.applicationId}
            card={card}
            columnStage={stage}
            permissions={permissions}
            isMoving={movingId === card.applicationId}
            onQuickComment={onQuickComment}
            onToggleAttention={onToggleAttention}
          />
        ))}
      </div>
    </section>
  );
}

"use client";

import type { CommissionEngagementColumn } from "@/lib/commission/types";
import { EngagementCard } from "./EngagementCard";

type Props = {
  order: number;
  column: CommissionEngagementColumn;
};

function dividerColor(columnId: CommissionEngagementColumn["id"]): string {
  if (columnId === "high_risk") return "#f4511e";
  if (columnId === "medium_risk") return "#f9a825";
  return "#7cb342";
}

export function EngagementColumn({ order, column }: Props) {
  return (
    <section
      style={{
        display: "flex",
        flexDirection: "column",
        width: 310,
        minWidth: 310,
        flex: "0 0 310px",
        minHeight: "fit-content",
        background: "transparent",
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
              color: dividerColor(column.id),
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
            {column.title}
          </h3>
          <span className="muted" style={{ fontSize: 12, lineHeight: "16px", marginLeft: 4 }}>
            {column.cards.length}
          </span>
        </div>
      </header>

      <div
        style={{
          height: 2,
          width: "100%",
          borderRadius: 1,
          background: dividerColor(column.id),
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
          boxShadow: "0 4px 24px rgba(0,0,0,0.1)",
          minHeight: 48,
        }}
      >
        {column.cards.length === 0 ? <p className="muted" style={{ margin: 0 }}>Нет кандидатов</p> : null}
        {column.cards.map((card) => (
          <EngagementCard key={card.applicationId} card={card} />
        ))}
      </div>
    </section>
  );
}

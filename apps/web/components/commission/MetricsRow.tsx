"use client";

import type { CSSProperties } from "react";
import type { CommissionBoardMetrics } from "@/lib/commission/types";

const cardStyle: CSSProperties = {
  position: "relative",
  display: "flex",
  flexDirection: "column",
  alignItems: "flex-start",
  gap: 8,
  width: 160,
  minWidth: 160,
  flex: "0 0 auto",
  padding: "14px 20px",
  borderRadius: 14,
  boxSizing: "border-box",
};

const labelStyle: React.CSSProperties = {
  margin: 0,
  width: "100%",
  fontSize: 16,
  fontWeight: 400,
  lineHeight: "16px",
  color: "#626262",
  letterSpacing: "-0.48px",
  fontFamily: "var(--font-inter, Inter, system-ui, sans-serif)",
};

const valueStyle: React.CSSProperties = {
  margin: 0,
  width: "100%",
  fontSize: 24,
  fontWeight: 600,
  lineHeight: "24px",
  color: "#98DA00",
  letterSpacing: "-0.72px",
  fontFamily: "var(--font-inter, Inter, system-ui, sans-serif)",
};

export function MetricsRow({ metrics }: { metrics: CommissionBoardMetrics }) {
  const items = [
    { label: "Всего заявок", value: metrics.totalApplications },
    { label: "За сегодня", value: metrics.todayApplications },
    { label: "Foundation", value: metrics.foundationApplications },
    { label: "Бакалавриат", value: metrics.bachelorApplications },
  ];

  return (
    <section
      style={{
        display: "flex",
        flexWrap: "wrap",
        gap: 8,
        alignItems: "stretch",
        width: "100%",
        minWidth: 0,
      }}
    >
      {items.map((i) => (
        <article key={i.label} style={cardStyle}>
          <span
            aria-hidden
            style={{
              position: "absolute",
              inset: 0,
              border: "1px solid #e1e1e1",
              borderRadius: 14,
              pointerEvents: "none",
            }}
          />
          <p style={labelStyle}>{i.label}</p>
          <p style={valueStyle}>{i.value}</p>
        </article>
      ))}
    </section>
  );
}

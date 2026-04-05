"use client";

import type { InterviewBoardColumn } from "@/lib/commission/interviewTypes";
import { InterviewCard } from "./InterviewCard";

type Props = {
  order: number;
  column: InterviewBoardColumn;
};

/** Interview board: same accent as «Собеседование» on the main Kanban. */
const DIVIDER_COLOR = "#98DA00";

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

export function InterviewColumn({ order, column }: Props) {
  const n = column.cards.length;

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
            {column.title}
          </h3>
          <span className="muted" style={{ fontSize: 12, lineHeight: "16px", marginLeft: 4 }}>
            {n}
          </span>
        </div>
        <button
          type="button"
          aria-label="Фильтр колонки"
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            padding: 0,
            border: "none",
            background: "transparent",
            cursor: "default",
            flexShrink: 0,
            opacity: 0.85,
          }}
          disabled
        >
          <FilterIcon />
        </button>
      </header>

      <div
        style={{
          height: 2,
          width: "100%",
          borderRadius: 1,
          background: DIVIDER_COLOR,
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
        {column.cards.length === 0 ? <p className="muted" style={{ margin: 0 }}>Нет заявок</p> : null}
        {column.cards.map((c) => (
          <InterviewCard key={c.applicationId} card={c} />
        ))}
      </div>
    </section>
  );
}

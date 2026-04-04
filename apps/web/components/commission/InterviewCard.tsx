"use client";

import Link from "next/link";
import type { InterviewBoardCard } from "@/lib/commission/interviewTypes";

type Props = {
  card: InterviewBoardCard;
};

export function InterviewCard({ card }: Props) {
  const border = card.highlight ? "1px solid #98da00" : "1px solid #e5e5e5";
  const label = card.action === "assign_date" ? "Назначить дату" : "Собеседование";

  return (
    <article
      style={{
        width: 278,
        border,
        borderRadius: 16,
        background: "#fff",
        boxShadow: "0 1px 3px rgba(0,0,0,0.06)",
        padding: "14px 16px 12px",
        boxSizing: "border-box",
        display: "flex",
        flexDirection: "column",
        gap: 8,
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 8 }}>
        <Link
          href={`/commission/applications/${card.applicationId}`}
          style={{
            fontSize: 16,
            fontWeight: 600,
            color: "#262626",
            letterSpacing: "-0.48px",
            lineHeight: "20px",
            textDecoration: "none",
            flex: 1,
            minWidth: 0,
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
        >
          {card.candidateFullName}
        </Link>
        {card.timeLabel ? (
          <span style={{ fontSize: 14, fontWeight: 400, color: "#626262", flexShrink: 0 }}>{card.timeLabel}</span>
        ) : null}
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 14, fontWeight: 350, color: "#626262" }}>
        <span>{card.line1}</span>
        <span>{card.line2}</span>
      </div>
      <button
        type="button"
        style={{
          marginTop: 4,
          width: "100%",
          border: 0,
          borderRadius: 12,
          padding: "10px 12px",
          background: "#98da00",
          color: "#fff",
          fontSize: 14,
          fontWeight: 500,
          cursor: "pointer",
        }}
      >
        {label}
      </button>
    </article>
  );
}

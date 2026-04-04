"use client";

import Image from "next/image";
import type { InterviewBoardColumn } from "@/lib/commission/interviewTypes";
import { InterviewCard } from "./InterviewCard";

type Props = {
  column: InterviewBoardColumn;
};

export function InterviewColumn({ column }: Props) {
  const n = column.cards.length;
  return (
    <section
      style={{
        minHeight: "fit-content",
        border: "1px solid #f1f1f1",
        borderRadius: 16,
        padding: 16,
        background: "#f1f1f1",
        display: "grid",
        gap: 16,
        width: 310,
        minWidth: 310,
        flex: "0 0 310px",
      }}
    >
      <header style={{ display: "flex", alignItems: "center", gap: 8, width: "100%" }}>
        <h3 style={{ margin: 0, fontSize: 18, lineHeight: "22px", fontWeight: 550, color: "#262626" }}>
          {column.title}
          <span style={{ color: "#98da00", fontWeight: 600 }}> ({n})</span>
        </h3>
        <button
          type="button"
          aria-label="Фильтр колонки"
          style={{
            marginLeft: "auto",
            border: 0,
            background: "transparent",
            padding: 4,
            cursor: "pointer",
            display: "inline-flex",
            opacity: 0.7,
          }}
        >
          <Image src="/assets/icons/iconoir_filter-solid.svg" alt="" width={18} height={18} />
        </button>
      </header>
      {column.cards.length === 0 ? <p className="muted">Нет заявок</p> : null}
      {column.cards.map((c) => (
        <InterviewCard key={c.applicationId} card={c} />
      ))}
    </section>
  );
}

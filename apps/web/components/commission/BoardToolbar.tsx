"use client";

import Image from "next/image";
import { useState } from "react";
import { PillSegmentedControl } from "@/components/application/PillSegmentedControl";
import { CommissionBoardHelpModal } from "@/components/commission/CommissionBoardHelpModal";
import type { CommissionRange } from "@/lib/commission/types";

type Props = {
  search: string;
  range: CommissionRange;
  onSearchChange: (v: string) => void;
  onRangeChange: (v: CommissionRange) => void;
};

const RANGE_OPTIONS: { value: CommissionRange; label: string }[] = [
  { value: "day", label: "День" },
  { value: "week", label: "Неделя" },
  { value: "month", label: "Месяц" },
  { value: "year", label: "Год" },
];

export function BoardToolbar({ search, range, onSearchChange, onRangeChange }: Props) {
  const [helpOpen, setHelpOpen] = useState(false);

  return (
    <section style={{ display: "grid", gap: 16 }}>
      <CommissionBoardHelpModal open={helpOpen} onClose={() => setHelpOpen(false)} />
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 0 }}>
          <h1 className="h2" style={{ margin: 0 }}>
            Обзор заявлений
          </h1>
          <button
            type="button"
            aria-label="Справка по странице обзора заявлений"
            onClick={() => setHelpOpen(true)}
            style={{
              flexShrink: 0,
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              width: 14,
              height: 14,
              padding: 0,
              border: "none",
              background: "transparent",
              cursor: "pointer",
              lineHeight: 0,
            }}
          >
            <Image
              src="/assets/icons/material-symbols_info-rounded.svg"
              alt=""
              width={14}
              height={14}
              aria-hidden
            />
          </button>
        </div>
        <label
          style={{
            position: "relative",
            display: "flex",
            alignItems: "center",
            width: 256,
            maxWidth: "100%",
          }}
        >
          <input
            className="input"
            placeholder="Поиск"
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
            aria-label="Поиск по заявкам"
            style={{ paddingRight: 40, height: 38 }}
          />
          <Image
            src="/assets/icons/material-symbols_search-rounded.svg"
            alt=""
            width={20}
            height={20}
            style={{ position: "absolute", right: 12, pointerEvents: "none" }}
          />
        </label>
      </div>
      <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
        <div
          style={{
            display: "inline-block",
          }}
        >
          <PillSegmentedControl
            options={RANGE_OPTIONS}
            value={range}
            onChange={onRangeChange}
            gap="tabs"
            aria-label="Фильтр по времени"
          />
        </div>
      </div>
    </section>
  );
}


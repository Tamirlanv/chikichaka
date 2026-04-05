"use client";

import type { CSSProperties } from "react";
import type { CommissionHistoryEventFilter, CommissionHistorySort } from "@/lib/commission/types";

type Props = {
  search: string;
  onSearchChange: (value: string) => void;
  eventType: CommissionHistoryEventFilter;
  onEventTypeChange: (value: CommissionHistoryEventFilter) => void;
  sort: CommissionHistorySort;
  onSortChange: (value: CommissionHistorySort) => void;
};

const FILTER_OPTIONS: Array<{ value: CommissionHistoryEventFilter; label: string }> = [
  { value: "all", label: "Все" },
  { value: "commission", label: "Комиссия" },
  { value: "system", label: "Система" },
  { value: "candidates", label: "Кандидаты" },
  { value: "stage", label: "Перемещения по этапам" },
  { value: "interview", label: "Собеседования" },
  { value: "decision", label: "Решения" },
];

const labelStyle: CSSProperties = {
  fontSize: 13,
  color: "#626262",
  fontWeight: 350,
  letterSpacing: "-0.39px",
  lineHeight: 1.25,
};

const FIELD_HEIGHT_PX = 38;

/** Compact toolbar fields: overrides global `.input` padding so total height is 38px (border-box). */
const toolbarInputStyle: CSSProperties = {
  width: "100%",
  height: FIELD_HEIGHT_PX,
  minHeight: FIELD_HEIGHT_PX,
  maxHeight: FIELD_HEIGHT_PX,
  boxSizing: "border-box",
  fontSize: 14,
  lineHeight: "20px",
  padding: "8px 16px",
};

/** Chevron inset 8px from the right border; native arrow removed for consistent layout. */
const SELECT_CHEVRON =
  "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%23262626' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M6 9l6 6 6-6'/%3E%3C/svg%3E\")";

const selectStyle: CSSProperties = {
  ...toolbarInputStyle,
  appearance: "none",
  WebkitAppearance: "none",
  MozAppearance: "none",
  backgroundImage: SELECT_CHEVRON,
  backgroundRepeat: "no-repeat",
  backgroundPosition: "right 8px center",
  backgroundSize: "16px 16px",
  backgroundColor: "var(--inv-bg)",
  paddingTop: 8,
  paddingBottom: 8,
  paddingLeft: 16,
  /* 8px (inset) + 16px (icon) + 8px (gap before label text) */
  paddingRight: 32,
};

export function HistoryToolbar({
  search,
  onSearchChange,
  eventType,
  onEventTypeChange,
  sort,
  onSortChange,
}: Props) {
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "minmax(220px, 1fr) minmax(220px, 260px) minmax(160px, 200px)",
        gap: 12,
        alignItems: "start",
      }}
    >
      <label style={{ display: "grid", gap: 6, margin: 0, minWidth: 0 }}>
        <span style={labelStyle}>Поиск</span>
        <input
          className="input"
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
          placeholder="Поиск по кандидату"
          aria-label="Поиск по событиям"
          style={toolbarInputStyle}
        />
      </label>

      <label style={{ display: "grid", gap: 6, margin: 0, minWidth: 0 }}>
        <span style={labelStyle}>Фильтр</span>
        <select
          className="input"
          value={eventType}
          onChange={(e) => onEventTypeChange(e.target.value as CommissionHistoryEventFilter)}
          style={selectStyle}
        >
          {FILTER_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </label>

      <label style={{ display: "grid", gap: 6, margin: 0, minWidth: 0 }}>
        <span style={labelStyle}>Сортировка</span>
        <select
          className="input"
          value={sort}
          onChange={(e) => onSortChange(e.target.value as CommissionHistorySort)}
          style={selectStyle}
        >
          <option value="newest">Сначала новые</option>
          <option value="oldest">Сначала старые</option>
        </select>
      </label>
    </div>
  );
}

"use client";

import Image from "next/image";
import { PillSegmentedControl } from "@/components/application/PillSegmentedControl";
import type { CommissionEngagementSort } from "@/lib/commission/types";

type Props = {
  search: string;
  sort: CommissionEngagementSort;
  onSearchChange: (value: string) => void;
  onSortChange: (value: CommissionEngagementSort) => void;
};

const SORT_OPTIONS: { value: CommissionEngagementSort; label: string }[] = [
  { value: "risk", label: "По риску" },
  { value: "freshness", label: "По давности online" },
  { value: "engagement", label: "По вовлеченности" },
];

export function EngagementToolbar({ search, sort, onSearchChange, onSortChange }: Props) {
  return (
    <section style={{ display: "grid", gap: 16 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
        <h1 className="h2" style={{ margin: 0 }}>
          Вовлеченность
        </h1>
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
            onChange={(event) => onSearchChange(event.target.value)}
            aria-label="Поиск по вовлеченности"
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
      <p style={{ margin: 0, fontSize: 13, lineHeight: "18px", color: "#626262", maxWidth: 980 }}>
        Операционный индикатор вовлеченности и риска выпадения. Не является итоговой оценкой кандидата и не используется как решение о зачислении.
      </p>
      <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
        <PillSegmentedControl
          options={SORT_OPTIONS}
          value={sort}
          onChange={(value) => onSortChange(value as CommissionEngagementSort)}
          gap="tabs"
          aria-label="Сортировка вовлеченности"
        />
      </div>
    </section>
  );
}

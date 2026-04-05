"use client";

import Image from "next/image";
import { PillSegmentedControl } from "@/components/application/PillSegmentedControl";
import type { InterviewScope } from "@/lib/commission/interviewTypes";

type Props = {
  search: string;
  scope: InterviewScope;
  onSearchChange: (v: string) => void;
  onScopeChange: (v: InterviewScope) => void;
};

const SCOPE_OPTIONS: { value: InterviewScope; label: string }[] = [
  { value: "mine", label: "Назначенные вами" },
  { value: "all", label: "Все" },
];

export function InterviewToolbar({ search, scope, onSearchChange, onScopeChange }: Props) {
  return (
    <section style={{ display: "grid", gap: 16 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
        <h1 className="h2" style={{ margin: 0 }}>
          Собеседование
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
            onChange={(e) => onSearchChange(e.target.value)}
            aria-label="Поиск по собеседованиям"
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
        <div style={{ display: "inline-block" }}>
          <PillSegmentedControl
            options={SCOPE_OPTIONS}
            value={scope}
            onChange={onScopeChange}
            gap="tabs"
            aria-label="Кто назначил собеседование"
          />
        </div>
      </div>
    </section>
  );
}

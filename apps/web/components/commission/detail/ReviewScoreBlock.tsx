"use client";

import { useState, useCallback, useEffect, useMemo } from "react";
import {
  RecommendedScoreExplanationModal,
  RecommendedScoreInfoButton,
} from "@/components/commission/detail/RecommendedScoreExplanationModal";
import { sanitizeReviewerExplanation } from "@/lib/commission/reviewerTextSanitizer";
import type { ReviewScoreBlock as ReviewScoreBlockType, ReviewScoreItem } from "@/lib/commission/types";

type Props = {
  data: ReviewScoreBlockType;
  onSave: (scores: Array<{ key: string; score: number }>) => Promise<void>;
  canEdit?: boolean;
  /** Email рецензента; выводится после успешного сохранения оценки. */
  savedByEmail?: string | null;
};

const MAX_SCORE = 5;
const CIRCLE_PX = 24;
const CIRCLE_GAP = 8;
const GREEN = "#98da00";
const TRACK = "#e8e8e8";

function meanRounded(values: number[]): number {
  if (values.length === 0) return 3;
  const m = values.reduce((a, b) => a + b, 0) / values.length;
  return Math.max(1, Math.min(5, Math.round(m)));
}

function unifiedSavedScore(items: ReviewScoreItem[]): number | null {
  const manuals = items.map((i) => i.manualScore).filter((m): m is number => m !== null);
  if (manuals.length !== items.length || items.length === 0) return null;
  const first = manuals[0];
  return manuals.every((m) => m === first) ? first : null;
}

function fallbackExplanationText(data: ReviewScoreBlockType): string {
  const its = data.items;
  if (its.length === 0) return "Нет данных по подкритериям для этого раздела.";
  const agg =
    typeof data.aggregateRecommendedScore === "number"
      ? data.aggregateRecommendedScore
      : meanRounded(its.map((i) => i.recommendedScore));
  const detail = its.map((i) => `«${i.label}» — ${i.recommendedScore}`).join(", ");
  return [
    `По подкритериям: ${detail}.`,
    `Итог: при отсутствии развёрнутого пояснения ориентируйтесь на баллы в таблице выше и исходный текст заявки.`,
    `Рекомендуемая оценка: ${agg}.`,
  ].join("\n\n");
}

export function ReviewScoreBlock({ data, onSave, canEdit = true, savedByEmail = null }: Props) {
  const items = data.items;
  const aggregateRecommended =
    typeof data.aggregateRecommendedScore === "number"
      ? data.aggregateRecommendedScore
      : meanRounded(items.map((i) => i.recommendedScore));

  const explanationBody = useMemo(() => {
    const raw = data.aggregateRecommendationExplanation?.trim();
    if (raw) {
      const clean = sanitizeReviewerExplanation(raw);
      if (clean) return clean;
      if (/«[^»\n]+»\s*—\s*[1-5]/u.test(raw)) return raw;
    }
    return fallbackExplanationText(data);
  }, [data]);

  const [infoOpen, setInfoOpen] = useState(false);

  const initialSelected = useMemo(() => {
    const saved = unifiedSavedScore(items);
    if (saved !== null) return saved;
    return meanRounded(items.map((i) => i.effectiveScore));
  }, [items]);

  const [selected, setSelected] = useState(initialSelected);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setSelected(initialSelected);
  }, [data, initialSelected]);

  const savedUnified = useMemo(() => unifiedSavedScore(items), [items]);
  const needsSave = savedUnified === null || selected !== savedUnified;

  const handleSave = useCallback(async () => {
    if (!canEdit || !needsSave) return;
    setSaving(true);
    try {
      const scores = items.map((item) => ({ key: item.key, score: selected }));
      await onSave(scores);
    } finally {
      setSaving(false);
    }
  }, [canEdit, needsSave, items, onSave, selected]);

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "flex-start",
        gap: 16,
        marginTop: 32,
        width: "fit-content",
        maxWidth: "100%",
        boxSizing: "border-box",
      }}
    >
      <h3
        style={{
          margin: 0,
          fontSize: 20,
          fontWeight: 600,
          color: "#262626",
          letterSpacing: "-0.6px",
          lineHeight: "24px",
        }}
      >
        Итог
      </h3>

      <p
        style={{
          margin: 0,
          display: "flex",
          flexWrap: "wrap",
          alignItems: "center",
          columnGap: 6,
          rowGap: 4,
          fontSize: 14,
          fontWeight: 350,
          color: "#262626",
          letterSpacing: "-0.42px",
          lineHeight: "20px",
        }}
      >
        <span>Рекомендуемая оценка:</span>
        <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
          <span>{aggregateRecommended}</span>
          <RecommendedScoreInfoButton onClick={() => setInfoOpen(true)} />
        </span>
      </p>

      <RecommendedScoreExplanationModal
        open={infoOpen}
        onClose={() => setInfoOpen(false)}
        body={explanationBody}
      />

      <p
        style={{
          margin: 0,
          fontSize: 14,
          fontWeight: 350,
          color: "#626262",
          letterSpacing: "-0.42px",
          lineHeight: "20px",
        }}
      >
        Установите итоговую оценку по данному разделу
      </p>

      <div
        role="radiogroup"
        aria-label="Оценка раздела от 1 до 5"
        style={{
          display: "flex",
          flexDirection: "row",
          alignItems: "center",
          gap: CIRCLE_GAP,
        }}
      >
        {Array.from({ length: MAX_SCORE }, (_, i) => i + 1).map((val) => {
          const filled = val <= selected;
          return (
            <button
              key={val}
              type="button"
              role="radio"
              aria-checked={selected === val}
              disabled={!canEdit}
              onClick={() => {
                if (!canEdit) return;
                setSelected(val);
              }}
              style={{
                width: CIRCLE_PX,
                height: CIRCLE_PX,
                borderRadius: "50%",
                border: "none",
                padding: 0,
                cursor: canEdit ? "pointer" : "not-allowed",
                background: filled ? GREEN : TRACK,
                flexShrink: 0,
                transition: "background 0.12s ease",
              }}
            />
          );
        })}
      </div>

      {canEdit ? (
        <>
          <button
            type="button"
            className="btn"
            disabled={saving || !needsSave}
            onClick={() => void handleSave()}
            style={{ fontWeight: 350 }}
          >
            {saving
              ? "Сохранение..."
              : savedUnified !== null && !needsSave
                ? `Установлено: ${savedUnified}`
                : "Установить"}
          </button>
          {savedUnified !== null && !needsSave && savedByEmail ? (
            <p
              style={{
                margin: 0,
                fontSize: 14,
                fontWeight: 350,
                color: "#626262",
                letterSpacing: "-0.42px",
                lineHeight: "20px",
              }}
            >
              {savedByEmail}
            </p>
          ) : null}
        </>
      ) : null}
    </div>
  );
}

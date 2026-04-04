"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  getInterviewPreferenceAvailableDays,
  getInterviewPreferenceAvailableSlots,
  postInterviewPreferencesSubmit,
  type InterviewPreferenceDay,
  type InterviewPreferenceSlot,
} from "@/lib/candidate-ai-interview";

type Row = { day: string | null; timeCode: string | null };

const EMPTY_ROWS: Row[] = [
  { day: null, timeCode: null },
  { day: null, timeCode: null },
  { day: null, timeCode: null },
];

type Props = {
  /** When true, form is read-only / hidden submit */
  disabled?: boolean;
  onSubmitted: () => void;
};

export function CandidateInterviewPreferencesForm({ disabled, onSubmitted }: Props) {
  const [days, setDays] = useState<InterviewPreferenceDay[]>([]);
  const [rows, setRows] = useState<Row[]>(EMPTY_ROWS);
  const [slotsByDate, setSlotsByDate] = useState<Record<string, InterviewPreferenceSlot[]>>({});
  const [loadingDays, setLoadingDays] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  const loadDays = useCallback(async () => {
    setLoadingDays(true);
    setError(null);
    try {
      const d = await getInterviewPreferenceAvailableDays();
      setDays(d.days);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось загрузить доступные дни");
      setDays([]);
    } finally {
      setLoadingDays(false);
    }
  }, []);

  useEffect(() => {
    void loadDays();
  }, [loadDays]);

  const fetchSlots = useCallback(async (dateIso: string) => {
    if (slotsByDate[dateIso]) return;
    try {
      const r = await getInterviewPreferenceAvailableSlots(dateIso);
      setSlotsByDate((prev) => ({ ...prev, [dateIso]: r.slots }));
    } catch {
      setSlotsByDate((prev) => ({ ...prev, [dateIso]: [] }));
    }
  }, [slotsByDate]);

  const onDaySelect = useCallback(
    async (rowIdx: number, dateIso: string) => {
      setRows((prev) => {
        const next = [...prev];
        next[rowIdx] = { day: dateIso, timeCode: null };
        return next;
      });
      await fetchSlots(dateIso);
    },
    [fetchSlots],
  );

  const onTimeSelect = (rowIdx: number, code: string) => {
    setRows((prev) => {
      const next = [...prev];
      next[rowIdx] = { ...next[rowIdx], timeCode: code };
      return next;
    });
  };

  const canSubmit = useMemo(() => {
    const filled = rows.filter((r) => r.day && r.timeCode);
    if (filled.length < 1 || filled.length > 3) return false;
    const keys = new Set<string>();
    for (const r of filled) {
      const k = `${r.day}:${r.timeCode}`;
      if (keys.has(k)) return false;
      keys.add(k);
    }
    return true;
  }, [rows]);

  async function handleSubmit() {
    if (!canSubmit || disabled || pending) return;
    const filled = rows
      .filter((r) => r.day && r.timeCode)
      .map((r) => ({ date: r.day!, timeRangeCode: r.timeCode! }));
    setPending(true);
    setError(null);
    try {
      await postInterviewPreferencesSubmit(filled);
      onSubmitted();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось сохранить");
      await loadDays();
      setSlotsByDate({});
    } finally {
      setPending(false);
    }
  }

  if (loadingDays) {
    return <p style={{ margin: 0, fontSize: 14, color: "#626262" }}>Загрузка доступных дней…</p>;
  }

  if (days.length === 0) {
    return (
      <p style={{ margin: 0, fontSize: 14, color: "#626262" }}>
        Сейчас нет свободных слотов для выбора. Попробуйте позже или свяжитесь с приёмной комиссией.
      </p>
    );
  }

  return (
    <div style={{ display: "grid", gap: 16, maxWidth: 480 }}>
      <div>
        <h3 style={{ margin: "0 0 8px", fontSize: 16, fontWeight: 600, color: "#262626" }}>Удобное время для собеседования</h3>
        <p style={{ margin: 0, fontSize: 14, color: "#626262", lineHeight: 1.4 }}>
          Если вы отметите удобные дни, собеседование будет назначено автоматически. Укажите до трёх вариантов.
        </p>
      </div>

      {[0, 1, 2].map((idx) => {
        const r = rows[idx]!;
        const slots = r.day ? slotsByDate[r.day] ?? [] : [];
        return (
          <div key={idx} style={{ display: "grid", gap: 8 }}>
            <span style={{ fontSize: 13, color: "#626262" }}>Вариант {idx + 1}</span>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
              <select
                className="input"
                style={{ minWidth: 220, height: 38, borderRadius: 8 }}
                value={r.day ?? ""}
                disabled={disabled || pending}
                onChange={(e) => {
                  const v = e.target.value;
                  if (!v) {
                    setRows((prev) => {
                      const n = [...prev];
                      n[idx] = { day: null, timeCode: null };
                      return n;
                    });
                  } else {
                    void onDaySelect(idx, v);
                  }
                }}
              >
                <option value="">— День —</option>
                {days.map((d) => (
                  <option key={d.date} value={d.date}>
                    {d.label}
                  </option>
                ))}
              </select>
              <select
                className="input"
                style={{ minWidth: 200, height: 38, borderRadius: 8 }}
                value={r.timeCode ?? ""}
                disabled={disabled || pending || !r.day}
                onChange={(e) => onTimeSelect(idx, e.target.value)}
              >
                <option value="">— Время —</option>
                {slots.map((s) => (
                  <option key={s.timeRangeCode} value={s.timeRangeCode}>
                    {s.label}
                  </option>
                ))}
              </select>
            </div>
          </div>
        );
      })}

      {error ? (
        <p style={{ margin: 0, fontSize: 14, color: "#c62828" }}>{error}</p>
      ) : null}

      <button
        type="button"
        className="btn"
        style={{
          justifySelf: "start",
          padding: "10px 20px",
          borderRadius: 12,
          border: 0,
          background: canSubmit && !disabled && !pending ? "#98da00" : "#ccc",
          color: "#fff",
          cursor: canSubmit && !disabled && !pending ? "pointer" : "not-allowed",
          fontWeight: 500,
        }}
        disabled={!canSubmit || disabled || pending}
        onClick={() => void handleSubmit()}
      >
        {pending ? "Сохранение…" : "Готово"}
      </button>
    </div>
  );
}

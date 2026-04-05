"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { ApiError } from "@/lib/api-client";
import {
  getInterviewPreferenceAvailableDays,
  getInterviewPreferenceAvailableSlots,
  postInterviewPreferencesSubmit,
  type InterviewPreferenceDay,
  type InterviewPreferenceSlot,
} from "@/lib/candidate-ai-interview";
import styles from "./CandidateInterviewPreferencesForm.module.css";

type Row = { day: string | null; timeCode: string | null };

const EMPTY_ROWS: Row[] = [
  { day: null, timeCode: null },
  { day: null, timeCode: null },
  { day: null, timeCode: null },
];

const LEAD_COPY =
  "Укажите в ближайшее время (1ч.) как минимум одно удобное время для собеседование, иначе время собеседования будет назначено автоматически";

type Props = {
  /** When true, form is read-only / hidden submit */
  disabled?: boolean;
  onSubmitted: () => void;
  /** After 409 (e.g. commission scheduled first) — refetch application status */
  onConflict?: () => void | Promise<void>;
};

export function CandidateInterviewPreferencesForm({ disabled, onSubmitted, onConflict }: Props) {
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
      if (e instanceof ApiError && e.status === 409 && onConflict) {
        await onConflict();
      }
      setError(e instanceof Error ? e.message : "Не удалось сохранить");
      await loadDays();
      setSlotsByDate({});
    } finally {
      setPending(false);
    }
  }

  if (loadingDays) {
    return <p className={styles.loading}>Загрузка доступных дней…</p>;
  }

  if (days.length === 0) {
    return (
      <p className={styles.empty}>
        Не удалось загрузить календарь доступных дней. Обновите страницу или попробуйте позже.
      </p>
    );
  }

  return (
    <div className={styles.wrap}>
      <div className={styles.intro}>
        <h2 className={styles.title}>Удобное время</h2>
        <p className={styles.lead}>{LEAD_COPY}</p>
      </div>
      <hr className={styles.divider} />
      <p className={styles.hint}>Можно указать до трёх вариантов (будние дни, рабочее время).</p>

      <div className={styles.variants}>
        {[0, 1, 2].map((idx) => {
          const r = rows[idx]!;
          const slots = r.day ? slotsByDate[r.day] ?? [] : [];
          return (
            <div key={idx} className={styles.variantRow}>
              <p className={styles.variantLabel}>Вариант {idx + 1}</p>
              <div className={styles.selectRow}>
                <select
                  className={styles.select}
                  aria-label={`Вариант ${idx + 1}: день`}
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
                  <option value="">День</option>
                  {days.map((d) => (
                    <option key={d.date} value={d.date}>
                      {d.label}
                    </option>
                  ))}
                </select>
                <select
                  className={styles.select}
                  aria-label={`Вариант ${idx + 1}: время`}
                  value={r.timeCode ?? ""}
                  disabled={disabled || pending || !r.day}
                  onChange={(e) => onTimeSelect(idx, e.target.value)}
                >
                  <option value="">Время</option>
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
      </div>

      {error ? <p className={styles.error}>{error}</p> : null}

      <button
        type="button"
        className={styles.submit}
        disabled={!canSubmit || disabled || pending}
        onClick={() => void handleSubmit()}
      >
        {pending ? "Сохранение…" : "Подтвердить"}
      </button>
    </div>
  );
}

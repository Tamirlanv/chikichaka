"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { getCommissionInterviewBoard } from "@/lib/commission/query";
import { subscribeToUpdates, unsubscribeFromUpdates } from "@/lib/commission/revalidate";
import type { InterviewBoardColumn, InterviewBoardFilters } from "@/lib/commission/interviewTypes";
import { InterviewColumn } from "./InterviewColumn";
import boardStyles from "./BoardContainer.module.css";

type Props = {
  filters: InterviewBoardFilters;
  onError: (msg: string | null) => void;
};

function errorStatusCode(error: unknown): number | null {
  if (!error || typeof error !== "object") return null;
  const status = (error as { status?: unknown }).status;
  return typeof status === "number" ? status : null;
}

export function InterviewBoardContainer({ filters, onError }: Props) {
  const [columns, setColumns] = useState<InterviewBoardColumn[]>([]);
  const [loading, setLoading] = useState(true);
  const [pollingEnabled, setPollingEnabled] = useState(true);

  const filtersRef = useRef(filters);
  filtersRef.current = filters;
  const onErrorRef = useRef(onError);
  onErrorRef.current = onError;

  const refresh = useCallback(async () => {
    try {
      setLoading(true);
      const cols = await getCommissionInterviewBoard(filtersRef.current);
      setColumns(cols);
      onErrorRef.current(null);
      setPollingEnabled(true);
    } catch (e) {
      const status = errorStatusCode(e);
      if (status === 401 || status === 403) {
        setPollingEnabled(false);
      }
      onErrorRef.current(e instanceof Error ? e.message : "Не удалось загрузить собеседования");
      setColumns([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [filters.search, filters.program, filters.scope, refresh]);

  useEffect(() => {
    if (!pollingEnabled) {
      return;
    }
    const listener = () => {
      void refresh();
    };
    subscribeToUpdates(listener, {
      onUnauthorized: () => {
        setPollingEnabled(false);
      },
    });
    return () => {
      unsubscribeFromUpdates(listener);
    };
  }, [pollingEnabled, refresh]);

  if (loading && columns.length === 0) {
    return <p className="muted">Загрузка доски…</p>;
  }

  return (
    <section className={boardStyles.boardScrollStrip}>
      {columns.map((col, idx) => (
        <InterviewColumn key={col.id} order={idx + 1} column={col} />
      ))}
    </section>
  );
}

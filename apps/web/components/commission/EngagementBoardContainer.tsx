"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { getCommissionEngagementBoard } from "@/lib/commission/query";
import { subscribeToUpdates, unsubscribeFromUpdates } from "@/lib/commission/revalidate";
import type { CommissionEngagementResponse, CommissionEngagementSort } from "@/lib/commission/types";
import { EngagementColumn } from "./EngagementColumn";
import boardStyles from "./BoardContainer.module.css";

type Props = {
  filters: {
    search: string;
    program: string | null;
    sort: CommissionEngagementSort;
  };
  onError: (msg: string | null) => void;
};

function errorStatusCode(error: unknown): number | null {
  if (!error || typeof error !== "object") return null;
  const status = (error as { status?: unknown }).status;
  return typeof status === "number" ? status : null;
}

const EMPTY_BOARD: CommissionEngagementResponse = {
  filters: { search: "", program: null, sort: "risk" },
  totals: { total: 0, highRisk: 0, mediumRisk: 0, lowRisk: 0 },
  columns: [
    { id: "high_risk", title: "Высокий риск", cards: [] },
    { id: "medium_risk", title: "Средний риск", cards: [] },
    { id: "low_risk", title: "Низкий риск", cards: [] },
  ],
};

export function EngagementBoardContainer({ filters, onError }: Props) {
  const [data, setData] = useState<CommissionEngagementResponse>(EMPTY_BOARD);
  const [loading, setLoading] = useState(true);
  const [pollingEnabled, setPollingEnabled] = useState(true);

  const filtersRef = useRef(filters);
  filtersRef.current = filters;
  const onErrorRef = useRef(onError);
  onErrorRef.current = onError;

  const refresh = useCallback(async () => {
    try {
      setLoading(true);
      const board = await getCommissionEngagementBoard(filtersRef.current);
      setData(board);
      onErrorRef.current(null);
      setPollingEnabled(true);
    } catch (e) {
      const status = errorStatusCode(e);
      if (status === 401 || status === 403) setPollingEnabled(false);
      onErrorRef.current(e instanceof Error ? e.message : "Не удалось загрузить вовлеченность");
      setData(EMPTY_BOARD);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [filters.search, filters.program, filters.sort, refresh]);

  useEffect(() => {
    if (!pollingEnabled) return;
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

  if (loading && data.columns.every((column) => column.cards.length === 0)) {
    return <p className="muted">Загрузка доски…</p>;
  }

  return (
    <section className={boardStyles.boardScrollStrip}>
      {data.columns.map((column, idx) => (
        <EngagementColumn key={column.id} order={idx + 1} column={column} />
      ))}
    </section>
  );
}

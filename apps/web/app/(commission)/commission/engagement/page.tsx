"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import Image from "next/image";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { CommissionSidebar } from "@/components/commission/CommissionSidebar";
import { EngagementBoardContainer } from "@/components/commission/EngagementBoardContainer";
import { EngagementToolbar } from "@/components/commission/EngagementToolbar";
import { MetricsRow } from "@/components/commission/MetricsRow";
import { getBoardMetrics } from "@/lib/commission/query";
import { useCommissionSidebarOpen } from "@/lib/commission/use-commission-sidebar-open";
import type { CommissionBoardMetrics, CommissionEngagementSort } from "@/lib/commission/types";
import styles from "../page.module.css";

function useDebounced<T>(value: T, ms: number): T {
  const [state, setState] = useState(value);
  useEffect(() => {
    const id = window.setTimeout(() => setState(value), ms);
    return () => window.clearTimeout(id);
  }, [value, ms]);
  return state;
}

function parseSort(raw: string | null): CommissionEngagementSort {
  if (raw === "freshness" || raw === "engagement") return raw;
  return "risk";
}

export default function CommissionEngagementPage() {
  return (
    <Suspense>
      <CommissionEngagementPageInner />
    </Suspense>
  );
}

function CommissionEngagementPageInner() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const { isSidebarOpen, setIsSidebarOpen } = useCommissionSidebarOpen();

  const [search, setSearch] = useState(params.get("search") ?? "");
  const [program, setProgram] = useState<string | null>(params.get("program"));
  const [sort, setSort] = useState<CommissionEngagementSort>(parseSort(params.get("sort")));
  const [metrics, setMetrics] = useState<CommissionBoardMetrics>({
    totalApplications: 0,
    todayApplications: 0,
    foundationApplications: 0,
    bachelorApplications: 0,
  });
  const [msg, setMsg] = useState<string | null>(null);

  const debouncedSearch = useDebounced(search, 350);
  const filters = useMemo(
    () => ({ search: debouncedSearch, program, sort }),
    [debouncedSearch, program, sort],
  );
  const metricsFilters = useMemo(
    () => ({ search: debouncedSearch, program, range: "week" as const }),
    [debouncedSearch, program],
  );

  /** Строки из URL — не `[params]`: иначе при нестабильной ссылке на объект сбрасывается sort до router.replace. */
  const searchFromUrl = params.get("search") ?? "";
  const programFromUrl = params.get("program");
  const sortFromUrl = params.get("sort");

  useEffect(() => {
    setSearch(searchFromUrl);
    setProgram(programFromUrl);
    setSort(parseSort(sortFromUrl));
  }, [searchFromUrl, programFromUrl, sortFromUrl]);

  const queryString = params.toString();

  useEffect(() => {
    const next = new URLSearchParams(queryString);
    if (debouncedSearch.trim()) next.set("search", debouncedSearch.trim());
    else next.delete("search");
    if (program) next.set("program", program);
    else next.delete("program");
    next.set("sort", sort);
    const target = `${pathname}${next.toString() ? `?${next.toString()}` : ""}`;
    const current = `${pathname}${queryString ? `?${queryString}` : ""}`;
    if (target !== current) {
      router.replace(target);
    }
  }, [debouncedSearch, program, sort, queryString, pathname, router]);

  useEffect(() => {
    void (async () => {
      try {
        setMetrics(await getBoardMetrics(metricsFilters));
      } catch (error) {
        setMsg(error instanceof Error ? error.message : "Не удалось загрузить метрики");
      }
    })();
  }, [metricsFilters]);

  return (
    <div className={styles.shell}>
      <CommissionSidebar isOpen={isSidebarOpen} program={program} onProgramChange={setProgram} />
      <main className={`${styles.page} ${isSidebarOpen ? styles.pageWithSidebar : styles.pageWithSidebarCollapsed}`}>
        <button
          type="button"
          className={styles.sidebarToggle}
          onClick={() => setIsSidebarOpen((value) => !value)}
          aria-label="Toggle sidebar"
        >
          <Image src="/assets/icons/icon_sidebar.svg" alt="" width={24} height={24} />
        </button>

        <EngagementToolbar search={search} sort={sort} onSearchChange={setSearch} onSortChange={setSort} />

        <MetricsRow metrics={metrics} />

        {msg ? <p className="error">{msg}</p> : null}

        <div className={styles.boardStripBleed}>
          <EngagementBoardContainer filters={filters} onError={setMsg} />
        </div>
      </main>
    </div>
  );
}

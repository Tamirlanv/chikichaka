"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import Image from "next/image";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { CommissionSidebar } from "@/components/commission/CommissionSidebar";
import { InterviewBoardContainer } from "@/components/commission/InterviewBoardContainer";
import { InterviewToolbar } from "@/components/commission/InterviewToolbar";
import { MetricsRow } from "@/components/commission/MetricsRow";
import { getBoardMetrics } from "@/lib/commission/query";
import { useCommissionSidebarOpen } from "@/lib/commission/use-commission-sidebar-open";
import type { InterviewScope } from "@/lib/commission/interviewTypes";
import type { CommissionBoardMetrics } from "@/lib/commission/types";
import styles from "../page.module.css";

function useDebounced<T>(value: T, ms: number): T {
  const [v, setV] = useState(value);
  useEffect(() => {
    const id = window.setTimeout(() => setV(value), ms);
    return () => window.clearTimeout(id);
  }, [value, ms]);
  return v;
}

function scopeFromQuery(raw: string | null): InterviewScope {
  if (raw === "all") return "all";
  return "mine";
}

export default function CommissionInterviewPage() {
  return (
    <Suspense>
      <CommissionInterviewPageInner />
    </Suspense>
  );
}

function CommissionInterviewPageInner() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const { isSidebarOpen, setIsSidebarOpen } = useCommissionSidebarOpen();

  const [search, setSearch] = useState(params.get("search") ?? "");
  const [program, setProgram] = useState<string | null>(params.get("program"));
  const [scope, setScope] = useState<InterviewScope>(scopeFromQuery(params.get("scope")));
  const [metrics, setMetrics] = useState<CommissionBoardMetrics>({
    totalApplications: 0,
    todayApplications: 0,
    foundationApplications: 0,
    bachelorApplications: 0,
  });
  const [msg, setMsg] = useState<string | null>(null);

  const debouncedSearch = useDebounced(search, 350);

  const filters = useMemo(
    () => ({ search: debouncedSearch, program, scope }),
    [debouncedSearch, program, scope],
  );

  const metricsFilters = useMemo(
    () => ({ search: debouncedSearch, program, range: "week" as const }),
    [debouncedSearch, program],
  );

  useEffect(() => {
    setSearch(params.get("search") ?? "");
    setProgram(params.get("program"));
    setScope(scopeFromQuery(params.get("scope")));
  }, [params]);

  useEffect(() => {
    const next = new URLSearchParams(params.toString());
    if (debouncedSearch.trim()) next.set("search", debouncedSearch.trim());
    else next.delete("search");
    if (program) next.set("program", program);
    else next.delete("program");
    next.set("scope", scope);
    const target = `${pathname}${next.toString() ? `?${next.toString()}` : ""}`;
    if (target !== `${pathname}${params.toString() ? `?${params.toString()}` : ""}`) {
      router.replace(target);
    }
  }, [debouncedSearch, program, scope, params, pathname, router]);

  useEffect(() => {
    void (async () => {
      try {
        setMetrics(await getBoardMetrics(metricsFilters));
      } catch (e) {
        setMsg(e instanceof Error ? e.message : "Не удалось загрузить метрики");
      }
    })();
  }, [metricsFilters]);

  return (
    <div className={styles.shell}>
      <CommissionSidebar isOpen={isSidebarOpen} program={program} onProgramChange={setProgram} />
      <main
        className={`${styles.page} ${isSidebarOpen ? styles.pageWithSidebar : styles.pageWithSidebarCollapsed}`}
      >
        <button
          type="button"
          className={styles.sidebarToggle}
          onClick={() => setIsSidebarOpen((v) => !v)}
          aria-label="Toggle sidebar"
        >
          <Image src="/assets/icons/icon_sidebar.svg" alt="" width={24} height={24} />
        </button>

        <InterviewToolbar search={search} scope={scope} onSearchChange={setSearch} onScopeChange={setScope} />

        <MetricsRow metrics={metrics} />

        {msg ? <p className="error">{msg}</p> : null}

        <div className={styles.boardStripBleed}>
          <InterviewBoardContainer filters={filters} onError={setMsg} />
        </div>
      </main>
    </div>
  );
}

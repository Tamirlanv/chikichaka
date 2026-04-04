"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { CommissionSidebar } from "@/components/commission/CommissionSidebar";
import { getArchivedCommissionApplications } from "@/lib/commission/query";
import type { CommissionBoardApplicationCard, CommissionBoardFilters, CommissionRange } from "@/lib/commission/types";
import { rangeFromQuery } from "@/lib/commission/query";
import styles from "../page.module.css";

function useDebounced<T>(value: T, ms: number): T {
  const [v, setV] = useState(value);
  useEffect(() => {
    const id = window.setTimeout(() => setV(value), ms);
    return () => window.clearTimeout(id);
  }, [value, ms]);
  return v;
}

export default function CommissionHistoryPage() {
  return (
    <Suspense>
      <CommissionHistoryInner />
    </Suspense>
  );
}

function CommissionHistoryInner() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [search, setSearch] = useState(params.get("search") ?? "");
  const [program, setProgram] = useState<string | null>(params.get("program"));
  const [range] = useState<CommissionRange>(() => rangeFromQuery(params.get("range")));
  const [cards, setCards] = useState<CommissionBoardApplicationCard[]>([]);
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState<string | null>(null);

  const debouncedSearch = useDebounced(search, 350);

  const filters: CommissionBoardFilters = useMemo(
    () => ({ search: debouncedSearch, program, range }),
    [debouncedSearch, program, range],
  );

  useEffect(() => {
    setSearch(params.get("search") ?? "");
    setProgram(params.get("program"));
  }, [params]);

  useEffect(() => {
    const next = new URLSearchParams(params.toString());
    if (debouncedSearch.trim()) next.set("search", debouncedSearch.trim());
    else next.delete("search");
    if (program) next.set("program", program);
    else next.delete("program");
    next.set("range", range);
    const target = `${pathname}${next.toString() ? `?${next.toString()}` : ""}`;
    if (target !== `${pathname}${params.toString() ? `?${params.toString()}` : ""}`) {
      router.replace(target);
    }
  }, [debouncedSearch, program, range, params, pathname, router]);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      setLoading(true);
      setMsg(null);
      try {
        const rows = await getArchivedCommissionApplications({
          search: filters.search,
          program: filters.program,
        });
        if (!cancelled) setCards(rows);
      } catch (e) {
        if (!cancelled) setMsg(e instanceof Error ? e.message : "Не удалось загрузить историю");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [filters.search, filters.program]);

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

        <h1 style={{ margin: 0, fontSize: 24, fontWeight: 600 }}>История заявок</h1>
        <p style={{ margin: 0, color: "#626262", fontSize: 14 }}>
          Архивные заявки (удалённые из активного pipeline). Просмотр только для чтения.
        </p>

        <label
          style={{
            position: "relative",
            display: "flex",
            alignItems: "center",
            width: 320,
            maxWidth: "100%",
          }}
        >
          <input
            className="input"
            placeholder="Поиск по архиву"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            aria-label="Поиск по архивным заявкам"
            style={{ paddingRight: 12, height: 38, borderRadius: 16 }}
          />
        </label>

        {msg ? <p style={{ color: "#e53935" }}>{msg}</p> : null}

        {loading ? (
          <p className="muted">Загрузка…</p>
        ) : cards.length === 0 ? (
          <p className="muted">Нет архивных заявок.</p>
        ) : (
          <ul style={{ listStyle: "none", padding: 0, margin: 0, display: "grid", gap: 12 }}>
            {cards.map((c) => (
              <li key={c.applicationId}>
                <Link
                  href={`/commission/applications/${c.applicationId}`}
                  style={{
                    display: "block",
                    padding: "16px 20px",
                    borderRadius: 12,
                    border: "1px solid #e8e8e8",
                    background: "#fafafa",
                    textDecoration: "none",
                    color: "#262626",
                  }}
                >
                  <div style={{ fontWeight: 600 }}>{c.candidateFullName}</div>
                  <div style={{ fontSize: 13, color: "#626262", marginTop: 4 }}>
                    {c.program || "—"} · обновлено {c.updatedAt ?? "—"}
                  </div>
                  <div style={{ fontSize: 12, color: "#888", marginTop: 6 }}>Только просмотр</div>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </main>
    </div>
  );
}

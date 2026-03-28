"use client";

import { useEffect, useState } from "react";
import { apiFetchCached } from "@/lib/api-client";
import { ApplicationHeader } from "./ApplicationHeader";
import { ApplicationStickyNav } from "./ApplicationStickyNav";
import { ApplicationSidebar } from "./ApplicationSidebar";
import styles from "./application-shell.module.css";

const DASHBOARD_TTL_MS = 5 * 60 * 1000;

type Props = {
  children: React.ReactNode;
};

export function ApplicationShell({ children }: Props) {
  const [firstName, setFirstName] = useState<string | undefined>(undefined);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const data = await apiFetchCached<{ candidate_name?: string }>(
          "/candidates/me/dashboard-summary",
          DASHBOARD_TTL_MS,
        );
        if (cancelled || !data.candidate_name) return;
        const part = data.candidate_name.trim().split(/\s+/)[0];
        if (part) setFirstName(part);
      } catch {
        /* unauthenticated or network */
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className={styles.page}>
      <ApplicationHeader candidateName={firstName} />
      <ApplicationStickyNav />
      <div className={styles.layoutRow}>
        <main className={styles.main}>{children}</main>
        <div className={styles.sidebarCol}>
          <ApplicationSidebar />
        </div>
      </div>
    </div>
  );
}

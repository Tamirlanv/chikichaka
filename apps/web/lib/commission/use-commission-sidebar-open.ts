"use client";

import { useEffect, useRef, useState } from "react";

const SIDEBAR_OPEN_STORAGE_KEY = "commission.sidebar.open";

function readSidebarOpenFromStorage(defaultOpen: boolean): boolean {
  if (typeof window === "undefined") return defaultOpen;
  try {
    const raw = window.localStorage.getItem(SIDEBAR_OPEN_STORAGE_KEY);
    if (raw === "0") return false;
    if (raw === "1") return true;
  } catch {
    // noop: fall back to default
  }
  return defaultOpen;
}

export function useCommissionSidebarOpen(defaultOpen = true) {
  /** Без чтения localStorage в initializer — на SSR и при первом paint клиента совпадает с defaultOpen. */
  const [isSidebarOpen, setIsSidebarOpen] = useState<boolean>(defaultOpen);

  useEffect(() => {
    setIsSidebarOpen(readSidebarOpenFromStorage(defaultOpen));
  }, [defaultOpen]);

  const skipFirstPersist = useRef(true);
  useEffect(() => {
    if (skipFirstPersist.current) {
      skipFirstPersist.current = false;
      return;
    }
    try {
      window.localStorage.setItem(SIDEBAR_OPEN_STORAGE_KEY, isSidebarOpen ? "1" : "0");
    } catch {
      // noop: storage may be unavailable in private mode or blocked env
    }
  }, [isSidebarOpen]);

  return { isSidebarOpen, setIsSidebarOpen };
}

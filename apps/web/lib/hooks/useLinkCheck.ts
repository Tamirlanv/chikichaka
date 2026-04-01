"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { apiFetch } from "@/lib/api-client";

type LinkCheckStatus = "idle" | "checking" | "reachable" | "unreachable" | "error";

type LinkCheckResult = {
  isReachable: boolean;
  availabilityStatus: string;
  statusCode: number | null;
  warnings: string[];
  errors: string[];
};

type UseLinkCheckReturn = {
  status: LinkCheckStatus;
  result: LinkCheckResult | null;
  statusMessage: string | null;
};

const URL_PATTERN = /^https?:\/\/.+/i;
const DEBOUNCE_MS = 1000;

/**
 * Debounced link reachability check via ``POST /api/v1/links/validate``.
 * Informational only — never blocks form submission.
 */
export function useLinkCheck(url: string | undefined): UseLinkCheckReturn {
  const [status, setStatus] = useState<LinkCheckStatus>("idle");
  const [result, setResult] = useState<LinkCheckResult | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const lastCheckedRef = useRef<string>("");

  const check = useCallback(async (target: string) => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    lastCheckedRef.current = target;

    setStatus("checking");
    setResult(null);

    try {
      const res = await apiFetch<{
        isReachable: boolean;
        availabilityStatus: string;
        statusCode: number | null;
        warnings: string[];
        errors: string[];
      }>("/links/validate", {
        method: "POST",
        json: { url: target },
        signal: controller.signal,
      });

      if (controller.signal.aborted) return;

      setResult({
        isReachable: res.isReachable,
        availabilityStatus: res.availabilityStatus,
        statusCode: res.statusCode,
        warnings: res.warnings ?? [],
        errors: res.errors ?? [],
      });
      setStatus(res.isReachable ? "reachable" : "unreachable");
    } catch (e: unknown) {
      if (e instanceof DOMException && e.name === "AbortError") return;
      if (controller.signal.aborted) return;
      setStatus("error");
      setResult(null);
    }
  }, []);

  useEffect(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }

    const trimmed = (url ?? "").trim();

    if (!trimmed || !URL_PATTERN.test(trimmed)) {
      setStatus("idle");
      setResult(null);
      lastCheckedRef.current = "";
      return;
    }

    if (trimmed === lastCheckedRef.current) return;

    timerRef.current = setTimeout(() => {
      void check(trimmed);
    }, DEBOUNCE_MS);

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [url, check]);

  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

  let statusMessage: string | null = null;
  if (status === "checking") {
    statusMessage = "Проверяем ссылку...";
  } else if (status === "reachable") {
    statusMessage = "Ссылка доступна";
  } else if (status === "unreachable" && result) {
    const av = result.availabilityStatus;
    if (av === "private_access" || av === "forbidden") {
      statusMessage = "Ссылка с ограниченным доступом — откройте доступ для всех, у кого есть ссылка";
    } else if (av === "timeout") {
      statusMessage = "Не удалось проверить ссылку — время ожидания истекло";
    } else {
      statusMessage = "Ссылка недоступна — проверьте правильность и настройки доступа";
    }
  } else if (status === "unreachable") {
    statusMessage = "Ссылка недоступна — проверьте правильность и настройки доступа";
  }

  return { status, result, statusMessage };
}

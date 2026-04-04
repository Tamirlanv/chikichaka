"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { apiFetch } from "@/lib/api-client";

type LinkCheckStatus = "idle" | "checking" | "ok" | "invalid" | "error";

export type PresentationVideoCheckResult = {
  isValid: boolean;
  provider: string;
  resourceType: string;
  isAccessible: boolean;
  isProcessableVideo: boolean;
  detectedMimeType: string | null;
  detectedExtension: string | null;
  errors: string[];
  warnings: string[];
};

type UseLinkCheckReturn = {
  status: LinkCheckStatus;
  result: PresentationVideoCheckResult | null;
  statusMessage: string | null;
  /** Блокировать отправку формы: ссылка проверена и не проходит как видео-презентация. */
  shouldBlockSubmit: boolean;
};

const URL_PATTERN = /^https?:\/\/.+/i;
const DEBOUNCE_MS = 1000;

/**
 * Debounced проверка ссылки на видеопрезентацию через ``POST /api/v1/links/validate-presentation-video``.
 */
export function useLinkCheck(url: string | undefined): UseLinkCheckReturn {
  const [status, setStatus] = useState<LinkCheckStatus>("idle");
  const [result, setResult] = useState<PresentationVideoCheckResult | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const lastCheckedRef = useRef<string>("");
  const lastCompletedUrlRef = useRef<string>("");

  const check = useCallback(async (target: string) => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    lastCheckedRef.current = target;

    setStatus("checking");
    setResult(null);
    lastCompletedUrlRef.current = "";

    try {
      const res = await apiFetch<PresentationVideoCheckResult>("/links/validate-presentation-video", {
        method: "POST",
        json: { url: target },
        signal: controller.signal,
      });

      if (controller.signal.aborted) return;

      lastCompletedUrlRef.current = target;
      setResult({
        isValid: res.isValid,
        provider: res.provider,
        resourceType: res.resourceType,
        isAccessible: res.isAccessible,
        isProcessableVideo: res.isProcessableVideo,
        detectedMimeType: res.detectedMimeType ?? null,
        detectedExtension: res.detectedExtension ?? null,
        errors: res.errors ?? [],
        warnings: res.warnings ?? [],
      });

      setStatus(res.isValid ? "ok" : "invalid");
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
      lastCompletedUrlRef.current = "";
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
    statusMessage = "Проверяем ссылку…";
  } else if (status === "error") {
    statusMessage = "Не удалось проверить ссылку. Попробуйте ещё раз.";
  } else if (result) {
    const primaryError = result.errors[0];
    const warnText = result.warnings.length ? result.warnings.join(" ") : null;

    if (!result.isProcessableVideo && primaryError) {
      statusMessage = primaryError;
    } else if (!result.isAccessible) {
      statusMessage =
        "Ссылка недоступна или с ограниченным доступом — откройте доступ для всех, у кого есть ссылка";
    } else if (result.isValid) {
      statusMessage = warnText ?? "Ссылка подходит для видеопрезентации";
    } else if (primaryError) {
      statusMessage = primaryError;
    } else {
      statusMessage = "Ссылка не подходит для видеопрезентации";
    }

    if (warnText && result.isValid && statusMessage !== warnText) {
      statusMessage = `${statusMessage} ${warnText}`;
    }
  }

  const trimmedForBlock = (url ?? "").trim();
  const shouldBlockSubmit = Boolean(
    result &&
      trimmedForBlock &&
      trimmedForBlock === lastCompletedUrlRef.current &&
      !result.isValid &&
      status !== "checking" &&
      status !== "idle",
  );

  return { status, result, statusMessage, shouldBlockSubmit };
}

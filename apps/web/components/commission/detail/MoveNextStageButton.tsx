"use client";

import { useRef, useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import {
  getStageAdvancePreview,
  moveApplicationToNextStage,
} from "@/lib/commission/query";
import type { StageAdvancePreviewResponse } from "@/lib/commission/types";
import { StageTransitionModal } from "@/components/commission/StageTransitionModal";

type Props = {
  applicationId: string;
  canMoveForward: boolean;
};

export function MoveNextStageButton({ applicationId, canMoveForward }: Props) {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();
  const [modal, setModal] = useState<{
    variant: "confirm" | "blocked";
    preview: StageAdvancePreviewResponse;
  } | null>(null);
  const [isAdvancing, setIsAdvancing] = useState(false);
  const advancingRef = useRef(false);

  function openPreview() {
    setError(null);
    startTransition(async () => {
      try {
        const preview = await getStageAdvancePreview(applicationId);
        if (preview.allowed) {
          setModal({ variant: "confirm", preview });
        } else {
          setModal({ variant: "blocked", preview });
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : "Не удалось проверить переход");
      }
    });
  }

  async function executeConfirm() {
    if (advancingRef.current) return;
    advancingRef.current = true;
    setIsAdvancing(true);
    setError(null);
    try {
      await moveApplicationToNextStage(applicationId);
      try {
        await router.refresh();
      } catch {
        setError("Переход выполнен, но не удалось обновить страницу. Повторная попытка…");
        try {
          await router.refresh();
        } catch {
          setError("Не удалось обновить страницу. Перезагрузите её вручную.");
        }
      }
      setModal(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось перевести заявку на следующий этап");
      setModal(null);
    } finally {
      advancingRef.current = false;
      setIsAdvancing(false);
    }
  }

  function navigateBlockedPrimary() {
    const pa = modal?.preview.blocked?.primaryAction;
    setModal(null);
    if (pa?.kind === "open_application") {
      const q = new URLSearchParams();
      if (pa.query.interviewSubTab) q.set("interviewSubTab", pa.query.interviewSubTab);
      const qs = q.toString();
      router.push(`/commission/applications/${pa.applicationId}${qs ? `?${qs}` : ""}`);
    } else {
      router.push(`/commission/applications/${applicationId}`);
    }
  }

  if (!canMoveForward) return null;

  return (
    <div style={{ display: "grid", gap: 10, justifyItems: "center", paddingTop: 12 }}>
      {modal ? (
        <StageTransitionModal
          preview={modal.preview}
          variant={modal.variant}
          onConfirm={() => { void executeConfirm(); }}
          onPrimaryAction={navigateBlockedPrimary}
          onCancel={() => {
            if (isAdvancing) return;
            setModal(null);
          }}
          confirmDisabled={isAdvancing}
          cancelDisabled={isAdvancing}
        />
      ) : null}
      <button type="button" className="btn" onClick={openPreview} disabled={isPending}>
        {isPending ? "Проверка…" : "Продолжить"}
      </button>
      {error ? <p style={{ margin: 0, fontSize: 13, color: "#e53935" }}>{error}</p> : null}
    </div>
  );
}

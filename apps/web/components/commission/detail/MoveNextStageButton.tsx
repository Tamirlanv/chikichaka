"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { moveApplicationToNextStage } from "@/lib/commission/query";

type Props = {
  applicationId: string;
  canMoveForward: boolean;
};

export function MoveNextStageButton({ applicationId, canMoveForward }: Props) {
  const router = useRouter();
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  function onMove() {
    setError(null);
    startTransition(async () => {
      try {
        await moveApplicationToNextStage(applicationId, reason || undefined);
        setReason("");
        router.refresh();
      } catch (e) {
        setError(e instanceof Error ? e.message : "Не удалось перевести заявку на следующий этап");
      }
    });
  }

  if (!canMoveForward) return null;

  return (
    <div style={{ display: "grid", gap: 10, justifyItems: "center", paddingTop: 12 }}>
      <button type="button" className="btn" onClick={onMove} disabled={isPending}>
        {isPending ? "Выполняется..." : "Продолжить"}
      </button>
      {error ? <p style={{ margin: 0, fontSize: 13, color: "#e53935" }}>{error}</p> : null}
    </div>
  );
}

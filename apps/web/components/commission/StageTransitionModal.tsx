"use client";

import type { StageAdvancePreviewResponse } from "@/lib/commission/types";

type Props = {
  preview: StageAdvancePreviewResponse;
  variant: "confirm" | "blocked";
  onConfirm: () => void;
  onPrimaryAction: () => void;
  onCancel: () => void;
  /** Disables the confirm button (e.g. while the advance request is in flight). */
  confirmDisabled?: boolean;
  /** Disables cancel while a request is in flight (confirm variant). */
  cancelDisabled?: boolean;
};

export function StageTransitionModal({
  preview,
  variant,
  onConfirm,
  onPrimaryAction,
  onCancel,
  confirmDisabled = false,
  cancelDisabled = false,
}: Props) {
  const confirmBlock = preview.confirm;
  const blocked = preview.blocked;
  const title = variant === "confirm" ? (confirmBlock?.title ?? "Подтверждение") : "Внимание";
  const message =
    variant === "confirm" ? (confirmBlock?.message ?? "") : (blocked?.message ?? "");
  const primaryLabel =
    variant === "confirm"
      ? (confirmBlock?.confirmLabel ?? "Подтвердить")
      : (blocked?.confirmLabel ?? "Перейти");
  const cancelLabel =
    variant === "confirm" ? (confirmBlock?.cancelLabel ?? "Отмена") : (blocked?.cancelLabel ?? "Отмена");
  const showPrimary = variant === "blocked" && Boolean(blocked?.primaryAction);
  const hasTwoActions = variant === "confirm" || showPrimary;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="stage-transition-modal-title"
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 1200,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "rgba(0,0,0,0.45)",
        padding: 16,
      }}
    >
      <div
        style={{
          width: "min(440px, 100%)",
          background: "#fff",
          borderRadius: 16,
          padding: "24px 20px",
          boxShadow: "0 8px 32px rgba(0,0,0,0.2)",
        }}
      >
        <h2 id="stage-transition-modal-title" style={{ margin: "0 0 12px", fontSize: 18, fontWeight: 600 }}>
          {title}
        </h2>
        <p style={{ margin: "0 0 20px", fontSize: 14, lineHeight: 1.45, color: "#262626" }}>{message}</p>
        <div className={`modal-actions${hasTwoActions ? "" : " modal-actions--single"}`}>
          <button type="button" className="btn secondary" onClick={onCancel} disabled={cancelDisabled}>
            {cancelLabel}
          </button>
          {variant === "blocked" && showPrimary ? (
            <button type="button" className="btn" onClick={onPrimaryAction}>
              {primaryLabel}
            </button>
          ) : null}
          {variant === "confirm" ? (
            <button type="button" className="btn" onClick={onConfirm} disabled={confirmDisabled}>
              {primaryLabel}
            </button>
          ) : null}
        </div>
      </div>
    </div>
  );
}

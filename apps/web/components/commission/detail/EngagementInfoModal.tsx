"use client";

import { useEffect } from "react";
import { ENGAGEMENT_INFO_MODAL_DESCRIPTION, ENGAGEMENT_INFO_MODAL_TITLE } from "@/lib/commission/engagement-info-copy";

type Props = {
  open: boolean;
  onClose: () => void;
};

export function EngagementInfoModal({ open, onClose }: Props) {
  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="engagement-info-modal-title"
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
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        style={{
          width: "min(520px, 100%)",
          background: "#fff",
          borderRadius: 16,
          padding: "24px 20px",
          boxShadow: "0 8px 32px rgba(0,0,0,0.2)",
        }}
      >
        <h2 id="engagement-info-modal-title" style={{ margin: "0 0 12px", fontSize: 18, fontWeight: 600 }}>
          {ENGAGEMENT_INFO_MODAL_TITLE}
        </h2>
        <p style={{ margin: 0, fontSize: 14, lineHeight: 1.5, color: "#262626" }}>
          {ENGAGEMENT_INFO_MODAL_DESCRIPTION}
        </p>
        <div className="modal-actions modal-actions--single" style={{ marginTop: 20 }}>
          <button type="button" className="btn" onClick={onClose}>
            Понятно
          </button>
        </div>
      </div>
    </div>
  );
}

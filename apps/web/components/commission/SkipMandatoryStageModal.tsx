"use client";

type Props = {
  onDismiss: () => void;
};

export function SkipMandatoryStageModal({ onDismiss }: Props) {
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="skip-mandatory-stage-title"
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
        <p
          id="skip-mandatory-stage-title"
          style={{ margin: "0 0 20px", fontSize: 14, lineHeight: 1.45, color: "#262626" }}
        >
          Предупреждение: заявку нельзя перемещать через обязательный этап.
        </p>
        <div className="modal-actions modal-actions--single">
          <button type="button" className="btn" onClick={onDismiss}>
            Понятно
          </button>
        </div>
      </div>
    </div>
  );
}

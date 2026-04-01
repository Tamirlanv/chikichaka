"use client";

import type { ValidationReport } from "@/lib/commission/types";

type Props = { report: ValidationReport | null | undefined };

const STATUS_LABELS: Record<string, string> = {
  passed: "Пройдено",
  failed: "Не пройдено",
  pending: "В обработке",
  queued: "В очереди",
  manual_review_required: "Требует ревью",
  processing: "Обработка",
};

const CHECK_LABELS: Record<string, string> = {
  links: "Ссылки",
  videoPresentation: "Видео-презентация",
  certificates: "Сертификаты",
};

function statusColor(status: string): string {
  if (status === "passed") return "#22c55e";
  if (status === "failed") return "#ef4444";
  if (status === "manual_review_required") return "#f59e0b";
  return "#6b7280";
}

export function ValidationReportCard({ report }: Props) {
  if (!report) {
    return (
      <div style={{ padding: 16, background: "#f9fafb", borderRadius: 8, border: "1px solid #e5e7eb" }}>
        <p style={{ margin: 0, color: "#9ca3af", fontSize: 14 }}>Валидация данных ещё не выполнялась.</p>
      </div>
    );
  }

  const checks = [
    { key: "links", data: report.checks.links },
    { key: "videoPresentation", data: report.checks.videoPresentation },
    { key: "certificates", data: report.checks.certificates },
  ];

  return (
    <div style={{ padding: 16, background: "#f9fafb", borderRadius: 8, border: "1px solid #e5e7eb" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <h3 style={{ margin: 0, fontSize: 16, fontWeight: 600 }}>Валидация данных</h3>
        <span style={{
          fontSize: 12,
          fontWeight: 500,
          padding: "2px 8px",
          borderRadius: 4,
          color: "#fff",
          background: statusColor(report.overallStatus),
        }}>
          {STATUS_LABELS[report.overallStatus] ?? report.overallStatus}
        </span>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {checks.map(({ key, data }) => (
          <div key={key} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: 14 }}>
            <span style={{ color: "#374151" }}>{CHECK_LABELS[key] ?? key}</span>
            {data ? (
              <span style={{ color: statusColor(data.status), fontWeight: 500, fontSize: 13 }}>
                {STATUS_LABELS[data.status] ?? data.status}
              </span>
            ) : (
              <span style={{ color: "#9ca3af", fontSize: 13 }}>—</span>
            )}
          </div>
        ))}
      </div>
      {report.warnings.length > 0 && (
        <div style={{ marginTop: 8, fontSize: 13, color: "#d97706" }}>
          {report.warnings.map((w, i) => <p key={i} style={{ margin: "2px 0" }}>⚠ {w}</p>)}
        </div>
      )}
      {report.errors.length > 0 && (
        <div style={{ marginTop: 8, fontSize: 13, color: "#dc2626" }}>
          {report.errors.map((e, i) => <p key={i} style={{ margin: "2px 0" }}>✗ {e}</p>)}
        </div>
      )}
      {report.updatedAt && (
        <p style={{ margin: "8px 0 0", fontSize: 12, color: "#9ca3af" }}>
          Обновлено: {new Date(report.updatedAt).toLocaleString("ru-RU")}
        </p>
      )}
    </div>
  );
}

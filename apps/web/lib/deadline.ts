/** Длина приёмной кампании на таймере и кольце (60 суток). */
export const CAMPAIGN_DURATION_MS = 60 * 24 * 60 * 60 * 1000;

/**
 * Глобальный дедлайн подачи: `NEXT_PUBLIC_ADMISSION_DEADLINE_ISO` (одинаково для всех пользователей).
 * Иначе — `NEXT_PUBLIC_ADMISSION_CAMPAIGN_START_ISO` + 60 суток.
 */
export function getAdmissionDeadlineMs(): number {
  const iso = process.env.NEXT_PUBLIC_ADMISSION_DEADLINE_ISO;
  if (iso) {
    const t = Date.parse(iso);
    if (!Number.isNaN(t)) return t;
  }
  const startIso = process.env.NEXT_PUBLIC_ADMISSION_CAMPAIGN_START_ISO;
  if (startIso) {
    const s = Date.parse(startIso);
    if (!Number.isNaN(s)) return s + CAMPAIGN_DURATION_MS;
  }
  const defaultStart = Date.UTC(2026, 2, 27, 19, 0, 0);
  return defaultStart + CAMPAIGN_DURATION_MS;
}

export function getCampaignStartMs(): number {
  return getAdmissionDeadlineMs() - CAMPAIGN_DURATION_MS;
}

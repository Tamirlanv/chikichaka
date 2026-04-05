/** Options for commission "Назначить время" — aligned with candidate 1h slots (backend codes). */

export const COMMISSION_TIME_SLOT_OPTIONS: Array<{ value: string; label: string }> = [
  { value: "09-10", label: "9:00-10:00" },
  { value: "10-11", label: "10:00-11:00" },
  { value: "11-12", label: "11:00-12:00" },
  { value: "12-13", label: "12:00-13:00" },
  { value: "13-14", label: "13:00-14:00" },
  { value: "14-15", label: "14:00-15:00" },
  { value: "15-16", label: "15:00-16:00" },
  { value: "16-17", label: "16:00-17:00" },
];

/** Legacy 2h codes still readable in DB / older preferences */
const LEGACY_TIME_OPTIONS: Array<{ value: string; label: string }> = [
  { value: "09-11", label: "9:00-11:00" },
  { value: "11-13", label: "11:00-13:00" },
  { value: "13-15", label: "13:00-15:00" },
  { value: "15-17", label: "15:00-17:00" },
];

const _allOptions = [...COMMISSION_TIME_SLOT_OPTIONS, ...LEGACY_TIME_OPTIONS];

export function timeOptionsIncludingCode(code: string | undefined): Array<{ value: string; label: string }> {
  if (!code || _allOptions.some((o) => o.value === code)) {
    return COMMISSION_TIME_SLOT_OPTIONS;
  }
  const found = LEGACY_TIME_OPTIONS.find((o) => o.value === code);
  return found ? [found, ...COMMISSION_TIME_SLOT_OPTIONS] : COMMISSION_TIME_SLOT_OPTIONS;
}

const START_HOUR_BY_CODE: Record<string, number> = {
  "09-10": 9,
  "10-11": 10,
  "11-12": 11,
  "12-13": 12,
  "13-14": 13,
  "14-15": 14,
  "15-16": 15,
  "16-17": 16,
  "09-11": 9,
  "11-13": 11,
  "13-15": 13,
  "15-17": 15,
};

/** Build `YYYY-MM-DDTHH:mm` for datetime-local from date ISO and slot code (start of window). */
export function dateAndCodeToDatetimeLocal(dateIso: string, timeRangeCode: string): string {
  const [y, mo, d] = dateIso.split("-").map((x) => parseInt(x, 10));
  const hour = START_HOUR_BY_CODE[timeRangeCode] ?? 9;
  const dt = new Date(y, mo - 1, d, hour, 0, 0, 0);
  const pad = (n: number) => n.toString().padStart(2, "0");
  return `${dt.getFullYear()}-${pad(dt.getMonth() + 1)}-${pad(dt.getDate())}T${pad(dt.getHours())}:${pad(dt.getMinutes())}`;
}

/** Next weekday dates from tomorrow through +60 calendar days (same window as API). */
export function buildScheduleDayOptions(): Array<{ value: string; label: string }> {
  const out: Array<{ value: string; label: string }> = [];
  const start = new Date();
  start.setDate(start.getDate() + 1);
  start.setHours(12, 0, 0, 0);
  const end = new Date(start);
  end.setDate(end.getDate() + 60);
  for (let d = new Date(start); d <= end; d.setDate(d.getDate() + 1)) {
    if (d.getDay() === 0 || d.getDay() === 6) continue;
    const y = d.getFullYear();
    const m = d.getMonth() + 1;
    const day = d.getDate();
    const value = `${y}-${String(m).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
    const label = d.toLocaleDateString("ru-RU", {
      day: "numeric",
      month: "long",
      weekday: "long",
    });
    out.push({ value, label });
  }
  return out;
}

/** Include a specific YYYY-MM-DD in the dropdown when it falls outside the default window (e.g. from candidate prefs). */
export function mergeScheduleDayOptions(
  base: Array<{ value: string; label: string }>,
  extraIso: string | undefined,
): Array<{ value: string; label: string }> {
  if (!extraIso?.trim()) return base;
  if (base.some((o) => o.value === extraIso)) return base;
  const [y, mo, d] = extraIso.split("-").map((x) => parseInt(x, 10));
  if (Number.isNaN(y) || Number.isNaN(mo) || Number.isNaN(d)) return base;
  const dt = new Date(y, mo - 1, d);
  const label = dt.toLocaleDateString("ru-RU", {
    day: "numeric",
    month: "long",
    weekday: "long",
  });
  return [...base, { value: extraIso, label }].sort((a, b) => a.value.localeCompare(b.value));
}

/** One line like the commission mock: «14 Апреля, Вторник  9:00-10:00» */
export function formatPreferenceVariantLine(dateIso: string, timeRange: string | undefined): string {
  if (!dateIso?.trim() || !timeRange?.trim()) return "—";
  const [y, mo, d] = dateIso.split("-").map((x) => parseInt(x, 10));
  if (Number.isNaN(y) || Number.isNaN(mo) || Number.isNaN(d)) return "—";
  const dt = new Date(y, mo - 1, d);
  const day = dt.getDate();
  const monthRaw = dt.toLocaleDateString("ru-RU", { month: "long" });
  const weekdayRaw = dt.toLocaleDateString("ru-RU", { weekday: "long" });
  const cap = (s: string) => (s ? s.charAt(0).toUpperCase() + s.slice(1) : s);
  return `${day} ${cap(monthRaw)}, ${cap(weekdayRaw)}  ${timeRange}`;
}

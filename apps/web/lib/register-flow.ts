/** Клиентское состояние воронки регистрации (sessionStorage). */

export type RegisterProgram = "foundation" | "bachelor";

export type RegisterFlowState = {
  program: RegisterProgram;
  specialtyId?: string;
};

const STORAGE_KEY = "inv.register";

export const BACHELOR_SPECIALTIES: { id: string; label: string }[] = [
  { id: "society", label: "Общество" },
  { id: "art_media", label: "Искусство + медиа" },
  { id: "technology", label: "Технологии" },
  { id: "legislative_reforms", label: "Законодательные реформы" },
  { id: "engineering", label: "Инженерия" },
];

export function readRegisterFlow(): RegisterFlowState | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as RegisterFlowState;
    if (parsed.program !== "foundation" && parsed.program !== "bachelor") return null;
    return parsed;
  } catch {
    return null;
  }
}

export function setRegisterProgram(program: RegisterProgram): void {
  const next: RegisterFlowState =
    program === "foundation" ? { program } : { program: "bachelor" };
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(next));
}

export function setRegisterSpecialty(specialtyId: string): void {
  const flow = readRegisterFlow();
  if (!flow || flow.program !== "bachelor") return;
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify({ ...flow, specialtyId }));
}

export function clearRegisterFlow(): void {
  sessionStorage.removeItem(STORAGE_KEY);
}

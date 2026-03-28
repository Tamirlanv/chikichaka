import { AuthViewportLock } from "@/components/auth/AuthViewportLock";

/** Зелёный фон html/body и блокировка скролла документа на мобильных — только на этапе регистрации. */
export default function RegisterLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <AuthViewportLock />
      {children}
    </>
  );
}

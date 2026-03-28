"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";

export default function PrivacyPolicyPage() {
  const router = useRouter();

  function goBack() {
    if (typeof window !== "undefined" && window.history.length > 1) {
      router.back();
      return;
    }
    router.push("/application/personal");
  }

  return (
    <div className="container" style={{ padding: "40px 24px 80px", maxWidth: 720 }}>
      <h1 className="h1" style={{ fontSize: 28, marginBottom: 24 }}>
        Политика конфиденциальности
      </h1>
      <p className="muted" style={{ marginBottom: 24 }}>
        Здесь будет полный текст политики обработки персональных данных inVision U.
      </p>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 12 }}>
        <button type="button" className="btn secondary" onClick={() => goBack()}>
          Назад
        </button>
        <Link className="btn secondary" href="/">
          На главную
        </Link>
        <Link className="btn secondary" href="/application/personal">
          К анкете
        </Link>
      </div>
    </div>
  );
}

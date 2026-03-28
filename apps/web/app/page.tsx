import Link from "next/link";

export default function HomePage() {
  return (
    <div className="container home-hero">
      <h1 className="h1">inVision U</h1>
      <p className="muted">
        Портал для подачи заявления. Войдите, чтобы продолжить заполнение анкеты.
      </p>
      <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
        <Link className="btn" href="/login">
          Войти
        </Link>
        <Link className="btn secondary" href="/register">
          Создать аккаунт
        </Link>
      </div>
    </div>
  );
}

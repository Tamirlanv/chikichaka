import Link from "next/link";

export default function TermsPage() {
  return (
    <div className="container" style={{ padding: "40px 0 64px", maxWidth: 720 }}>
      <h1 className="h1">Пользовательское соглашение</h1>
      <p className="muted">Текст соглашения будет размещён здесь.</p>
      <p style={{ marginTop: 24 }}>
        <Link href="/register">← К регистрации</Link>
      </p>
    </div>
  );
}

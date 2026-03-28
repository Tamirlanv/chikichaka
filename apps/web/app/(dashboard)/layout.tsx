import Link from "next/link";
import { LogoutButton } from "@/components/LogoutButton";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="container" style={{ padding: "40px 0 64px" }}>
      <header className="platform-header">
        <div className="platform-header__brand">inVision U — абитуриент</div>
        <nav className="platform-nav">
          <Link href="/dashboard" className="btn secondary">
            Главная
          </Link>
          <Link href="/application/personal" className="btn secondary">
            Заявление
          </Link>
          <LogoutButton />
        </nav>
      </header>
      <div className="page-stack">{children}</div>
    </div>
  );
}

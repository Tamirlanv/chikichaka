import { ApplicationShell } from "@/components/application/ApplicationShell";

export default function ApplicationLayout({ children }: { children: React.ReactNode }) {
  return <ApplicationShell>{children}</ApplicationShell>;
}

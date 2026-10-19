import { PrivateShell } from "@/components/layout/shell";
export default function Layout({ children }: { children: React.ReactNode }) {
  return <PrivateShell>{children}</PrivateShell>;
}

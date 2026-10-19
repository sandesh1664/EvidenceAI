import type { Metadata } from "next";
import { headers } from "next/headers";
import { ThemeInit } from "@/components/layout/theme-init";
import { SessionProvider } from "@/lib/auth/session";
import "./globals.css";
export const metadata: Metadata = {
  title: {
    default: "EvidenceAI · Research with sources",
    template: "%s · EvidenceAI",
  },
  description: "Private document research with traceable evidence.",
};
export default async function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  await headers();
  return (
    <html lang="en">
      <body>
        <ThemeInit />
        <SessionProvider>{children}</SessionProvider>
      </body>
    </html>
  );
}

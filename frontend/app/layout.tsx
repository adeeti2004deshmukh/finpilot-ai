import type { Metadata } from "next";
import "@fontsource-variable/manrope";
import "./globals.css";
import { AppShell } from "@/components/layout/app-shell";
import { AuthProvider } from "@/components/auth/auth-provider";

export const metadata: Metadata = {
  title: "FinPilot | Personal Finance",
  description: "A clear view of your money, priorities, and plans.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full"><AuthProvider><AppShell>{children}</AppShell></AuthProvider></body>
    </html>
  );
}

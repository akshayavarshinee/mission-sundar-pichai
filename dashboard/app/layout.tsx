import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ClearPort — Customs Recovery Agent",
  description:
    "Autonomous customs-rejection recovery with an Arize eval-gate, human-in-the-loop approvals, experiment-gated learning, and drift detection.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="font-sans antialiased">{children}</body>
    </html>
  );
}

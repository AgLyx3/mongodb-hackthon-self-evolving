import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "FDE harness console",
  description: "Self-evolving deployment harness: proposals, gates, FDE decisions, survival",
};

const CUSTOMERS = [
  { id: "bank", label: "Northbridge Bank", note: "dev customer" },
  { id: "fintech", label: "Zephyr Wallet", note: "held-out customer" },
];

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" data-theme="dark">
      <body>
        <header
          style={{
            borderBottom: "1px solid var(--color-border)",
            padding: "var(--space-3) var(--space-6)",
            display: "flex",
            gap: "var(--space-6)",
            alignItems: "baseline",
            position: "sticky",
            top: 0,
            background: "var(--color-surface)",
            zIndex: "var(--z-sticky)",
          }}
        >
          <span style={{ fontSize: "var(--text-lg)", fontWeight: 600 }}>FDE harness console</span>
          <nav aria-label="Customers" style={{ display: "flex", gap: "var(--space-4)" }}>
            {CUSTOMERS.map((c) => (
              <Link
                key={c.id}
                href={`/customers/${c.id}`}
                style={{ color: "var(--color-primary)", textDecoration: "none" }}
              >
                {c.label} <span className="muted">({c.note})</span>
              </Link>
            ))}
          </nav>
          <span className="muted" style={{ marginLeft: "auto" }}>
            Synthetic, fictional customers and rules
          </span>
        </header>
        <main style={{ padding: "var(--space-6)", maxWidth: "var(--bp-xl)", margin: "0 auto" }}>
          {children}
        </main>
      </body>
    </html>
  );
}

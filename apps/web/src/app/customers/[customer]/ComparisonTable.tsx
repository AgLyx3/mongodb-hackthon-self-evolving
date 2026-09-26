import type { Comparison } from "@/lib/api";

export function ComparisonTable({ comparison }: { comparison: Comparison }) {
  const rows = comparison.rows ?? [];
  if (rows.length === 0) {
    return <p className="muted">No comparison yet. Run scripts/final_compare.py after the loop.</p>;
  }
  return (
    <table style={{ width: "100%", borderCollapse: "collapse" }}>
      <thead>
        <tr className="muted" style={{ textAlign: "left" }}>
          <th style={{ padding: "var(--space-2) 0" }}>Harness</th>
          <th>Runtime model</th>
          <th className="num">Holdout accuracy</th>
          <th className="num">Planted-signal cases</th>
          <th className="num">Failed calls</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={`${r.harness}-${r.role}`} style={{ borderTop: "1px solid var(--color-border)" }}>
            <td style={{ padding: "var(--space-2) 0" }}>
              {r.harness === "base" ? "Base (generic)" : "Evolved for this customer"}
            </td>
            <td>
              {r.role === "mid" ? "Mid-tier" : "Strong"} <span className="mono muted">{r.model}</span>
              {r.harness === "evolved" && r.role === "strong" ? (
                <span className="muted"> · evolved on the mid-tier model</span>
              ) : null}
            </td>
            <td className="num">{Math.round(r.acc * 100)}%</td>
            <td className="num">{Math.round(r.signal_acc * 100)}%</td>
            <td className="num">{r.failed_calls}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

import type { LadderRow } from "@/lib/api";

const LABEL: Record<string, string> = {
  none: "No FDE (auto-accept whatever passes the gates)",
  hints: "FDE gives hints only (counterexamples, never the fix)",
  oracle: "FDE with the full answer key (writes exact scope)",
};
const ORDER = ["none", "hints", "oracle"];

function pct(x: number | null | undefined): string {
  return x === null || x === undefined ? "–" : `${Math.round(x * 100)}%`;
}

export function LadderTable({ rows }: { rows: LadderRow[] }) {
  if (rows.length === 0) return <p className="muted">No ladder runs yet.</p>;
  const sorted = [...rows].sort(
    (a, b) => ORDER.indexOf(a.mode) - ORDER.indexOf(b.mode) || a.noise - b.noise,
  );
  return (
    <table style={{ width: "100%", borderCollapse: "collapse" }}>
      <thead>
        <tr className="muted" style={{ textAlign: "left" }}>
          <th style={{ padding: "var(--space-2) 0" }}>Reviewer</th>
          <th className="num">Start</th>
          <th className="num">Round 1</th>
          <th className="num">Round 2</th>
          <th className="num">Round 3</th>
          <th className="num">Promoted</th>
          <th className="num">Answer-key leaks</th>
        </tr>
      </thead>
      <tbody>
        {sorted.map((r) => (
          <tr key={r.id} style={{ borderTop: "1px solid var(--color-border)" }}>
            <td style={{ padding: "var(--space-2) 0" }}>
              {LABEL[r.mode] ?? r.mode}
              {r.noise > 0 ? <span className="muted"> · {Math.round(r.noise * 100)}% noisy verdicts</span> : null}
            </td>
            {[0, 1, 2, 3].map((i) => (
              <td key={i} className="num">
                {pct(r.report_by_round[i])}
              </td>
            ))}
            <td className="num">{r.promoted}</td>
            <td className="num">
              {r.leaks} / {r.leak_checks}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

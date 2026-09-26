import type { Metrics } from "@/lib/api";

export function TapInTable({ metrics }: { metrics: Metrics }) {
  if (metrics.rounds.length === 0) return <p className="muted">No discovery rounds yet.</p>;
  const ab = metrics.ablation[0];
  const cell = { padding: "var(--space-2) var(--space-2)" };
  return (
    <table style={{ width: "100%", borderCollapse: "collapse" }}>
      <thead>
        <tr className="muted" style={{ textAlign: "left" }}>
          <th style={cell}>Discovery round</th>
          <th style={cell}>Planted signals learned</th>
          <th className="num" style={cell}>Probe units</th>
          <th className="num" style={cell}>On decoy sources</th>
          <th className="num" style={cell}>Units per signal</th>
          <th className="num" style={cell}>FDE accept / edit / reject</th>
          <th className="num" style={cell}>Stopped by gates</th>
        </tr>
      </thead>
      <tbody>
        {metrics.rounds.map((r) => (
          <tr key={r.round} style={{ borderTop: "1px solid var(--color-border)" }}>
            <td style={cell}>
              Round {r.round} <span className="muted">({r.alerts_reviewed} alerts reviewed)</span>
            </td>
            <td style={cell} className="mono">
              {r.signals_learned.join(", ") || "–"}
            </td>
            <td className="num" style={cell}>{r.probe_units.toFixed(0)}</td>
            <td className="num" style={cell}>
              {r.decoy_units.toFixed(1)} ({r.probe_units ? Math.round((100 * r.decoy_units) / r.probe_units) : 0}%)
            </td>
            <td className="num" style={cell}>{r.units_per_signal ?? "–"}</td>
            <td className="num" style={cell}>
              {r.fde_accepts} / {r.fde_edits} / {r.fde_rejects}
            </td>
            <td className="num" style={cell}>{r.stopped_by_gates}</td>
          </tr>
        ))}
        {ab ? (
          <tr style={{ borderTop: "1px solid var(--color-border)" }}>
            <td style={cell}>
              Round {ab.round}, <strong>without learned source priors</strong>{" "}
              <span className="muted">(same failures, same budget)</span>
            </td>
            <td style={cell} className="muted">findings not promoted (ablation only)</td>
            <td className="num" style={cell}>{ab.units.toFixed(0)}</td>
            <td className="num" style={cell}>
              {ab.decoy.toFixed(1)} ({ab.units ? Math.round((100 * ab.decoy) / ab.units) : 0}%)
            </td>
            <td className="num" style={cell}>–</td>
            <td className="num" style={cell}>–</td>
            <td className="num" style={cell}>–</td>
          </tr>
        ) : null}
      </tbody>
    </table>
  );
}

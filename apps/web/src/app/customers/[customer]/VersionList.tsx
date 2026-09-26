import type { VersionRow } from "@/lib/api";

function fmt(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

export function VersionList({ versions }: { versions: VersionRow[] }) {
  if (versions.length === 0) return <p className="muted">No versions yet. Run the loop to create v0.</p>;
  return (
    <table style={{ width: "100%", borderCollapse: "collapse" }}>
      <thead>
        <tr className="muted" style={{ textAlign: "left" }}>
          <th style={{ padding: "var(--space-2) 0" }}>When</th>
          <th>Version</th>
          <th>Batch</th>
          <th>Change</th>
          <th>Why</th>
          <th className="num">Holdout</th>
        </tr>
      </thead>
      <tbody>
        {versions.map((v, i) => (
          <tr key={`${v.version}-${i}`} style={{ borderTop: "1px solid var(--color-border)" }}>
            <td style={{ padding: "var(--space-2) 0" }}>{fmt(v.at)}</td>
            <td className="mono">
              v{i} · {v.version}
              {i === versions.length - 1 ? " (live)" : ""}
            </td>
            <td className="num" style={{ textAlign: "left" }}>
              {v.batch}
            </td>
            <td>{v.edge ?? "base"}</td>
            <td>
              {v.unit_id ? (
                <>
                  <span className="mono">{v.unit_id}</span>{" "}
                  <span className="muted">after FDE {v.fde_action}</span>
                </>
              ) : (
                <span className="muted">{v.reason}</span>
              )}
            </td>
            <td className="num">
              {v.holdout_acc === null ? "–" : `${Math.round(v.holdout_acc * 100)}%`}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

import type { Customer, Metrics, Sources } from "@/lib/api";

type Props = { customer: Customer; sources: Sources; metrics: Metrics };

export function SourceHeatmap({ customer, sources, metrics }: Props) {
  const runs = Object.keys(sources.probes).sort();
  const ids = [...customer.manifest.map((m) => m.source_id), "customer_contact"];
  const lastUse =
    sources.usefulness_by_batch[sources.usefulness_by_batch.length - 1]?.usefulness ?? {};
  const maxCost = Math.max(
    1,
    ...runs.flatMap((r) => Object.values(sources.probes[r]).map((v) => v.cost)),
  );
  const described = Object.fromEntries(customer.manifest.map((m) => [m.source_id, m.described_as]));
  return (
    <>
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          <tr className="muted" style={{ textAlign: "left" }}>
            <th style={{ padding: "var(--space-2) 0" }}>Source (as described at onboarding)</th>
            {runs.map((r) => (
              <th key={r} className="num">
                {r.replace(":main", "").replace(":ablation_no_priors", " no priors")}
              </th>
            ))}
            <th className="num">Learned usefulness</th>
          </tr>
        </thead>
        <tbody>
          {ids.map((s) => (
            <tr key={s} style={{ borderTop: "1px solid var(--color-border)" }}>
              <td style={{ padding: "var(--space-2) 0" }}>
                <span className="mono">{s}</span>{" "}
                <span className="muted">{described[s] ?? "ask questions (costly)"}</span>
                {sources.relevant_sources.includes(s) ? "" : <span className="muted"> · decoy</span>}
              </td>
              {runs.map((r) => {
                const cell = sources.probes[r]?.[s];
                const share = cell ? cell.cost / maxCost : 0;
                return (
                  <td
                    key={r}
                    className="num"
                    style={{
                      background: `color-mix(in oklch, var(--color-primary) ${Math.round(
                        share * 60,
                      )}%, transparent)`,
                    }}
                  >
                    {cell ? cell.cost.toFixed(1) : ""}
                  </td>
                );
              })}
              <td className="num">{lastUse[s] ? `▲ ${lastUse[s].toFixed(0)}` : "–"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="muted" style={{ marginTop: "var(--space-2)" }}>
        Probe budget spent on decoy sources:{" "}
        {Object.entries(metrics.decoy_spend)
          .map(([k, v]) => `${k.replace(":main", "")} ${Math.round(v.irrelevant_share * 100)}%`)
          .join(" · ") || "–"}
      </p>
    </>
  );
}

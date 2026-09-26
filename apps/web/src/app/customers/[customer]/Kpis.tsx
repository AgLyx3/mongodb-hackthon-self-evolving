import type { Metrics } from "@/lib/api";

type KpisProps = { metrics: Metrics; strongBaseline: number | null };

function pct(x: number | null | undefined): string {
  return x === null || x === undefined ? "–" : `${Math.round(x * 100)}%`;
}

export function Kpis({ metrics, strongBaseline }: KpisProps) {
  const series = metrics.holdout_by_batch;
  const first = series[0]?.acc ?? null;
  const last = series[series.length - 1]?.acc ?? null;
  const delta = first !== null && last !== null ? last - first : null;
  const noisePts = metrics.noise_cases !== null ? (metrics.noise_cases / 40) * 100 : null;
  const tiles: { label: string; value: string; note: string }[] = [
    {
      label: "Accuracy on untouched report cases",
      value: `${pct(first)} → ${pct(last)}`,
      note:
        delta === null
          ? "no runs yet"
          : `${delta >= 0 ? "▲ +" : "▼ "}${Math.round(delta * 100)} pts; noise band ±${
              noisePts?.toFixed(1) ?? "?"
            } pts`,
    },
    {
      label: "Strong model, base harness",
      value: pct(strongBaseline),
      note: "same report cases, generic harness",
    },
    {
      label: "Planted signals learned",
      value: `${metrics.signals_learned.length} / ${metrics.planted_signals.length}`,
      note: "matched against the answer key",
    },
    {
      label: "Proposals",
      value: `${metrics.proposals} → ${metrics.promoted} promoted`,
      note: `${metrics.survived} still live; ${metrics.stopped_or_rejected} stopped by gates or FDE`,
    },
    {
      label: "LLM spend (all runs)",
      value: `$${metrics.spent_usd_total.toFixed(2)}`,
      note: "hard stop at $9 of a $10 budget",
    },
  ];
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(5, minmax(0, 1fr))",
        borderTop: "1px solid var(--color-border)",
        borderBottom: "1px solid var(--color-border)",
      }}
    >
      {tiles.map((t, i) => (
        <div
          key={t.label}
          style={{
            padding: "var(--space-3) var(--space-4)",
            borderLeft: i === 0 ? "none" : "1px solid var(--color-border)",
          }}
        >
          <div className="muted">{t.label}</div>
          <div style={{ fontSize: "var(--text-xl)", fontWeight: 600 }} className="num">
            <span style={{ display: "block", textAlign: "left" }}>{t.value}</span>
          </div>
          <div className="muted" style={{ fontSize: "var(--text-xs)" }}>
            {t.note}
          </div>
        </div>
      ))}
    </div>
  );
}

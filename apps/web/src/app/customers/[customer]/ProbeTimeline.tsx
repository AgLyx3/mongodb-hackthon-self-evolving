import type { Probe } from "@/lib/api";

export function argsText(p: Pick<Probe, "tool" | "args">): string {
  const a = p.args as Record<string, unknown>;
  if (p.tool === "search_evidence") return `"${String(a.query ?? "")}"${a.source_id ? ` in ${String(a.source_id)}` : ""}`;
  if (p.tool === "ask_customer") return `"${String(a.question ?? "")}"`;
  if (p.tool === "read_source") return `${String(a.source_id ?? "")} from ${String(a.offset ?? 0)}`;
  if (p.tool === "field_stats") return String(a.path ?? "");
  if (p.tool === "label_breakdown") {
    const cl = (a.clauses as { path: string; op: string; value: string }[] | undefined) ?? [];
    return `${cl.map((c) => `${c.path} ${c.op} ${c.value}`).join(" AND ") || "all"} by ${String(a.group_by ?? "")}`;
  }
  return JSON.stringify(a);
}

export function ProbeTimeline({ probes }: { probes: Probe[] }) {
  if (probes.length === 0) return <p className="muted">No investigation yet.</p>;
  const groups = new Map<string, Probe[]>();
  for (const p of probes) {
    const k = `${p.round}|${p.run}`;
    groups.set(k, [...(groups.get(k) ?? []), p]);
  }
  return (
    <div>
      {[...groups.entries()].map(([k, ps]) => {
        const [round, run] = k.split("|");
        const units = ps.reduce((s, p) => s + p.cost, 0);
        return (
          <details key={k} style={{ borderTop: "1px solid var(--color-border)" }}>
            <summary style={{ padding: "var(--space-2) 0", cursor: "pointer" }}>
              Round {round}
              {run === "main" ? "" : " · without learned priors"}{" "}
              <span className="muted">
                · {ps.length} probes · {units} units
              </span>
            </summary>
            <ol style={{ margin: 0, paddingLeft: "var(--space-6)" }}>
              {ps.map((p, i) => (
                <li key={i} style={{ padding: "var(--space-1) 0" }}>
                  <span className="mono">{p.tool}</span> {argsText(p)}{" "}
                  <span className="muted">
                    → {p.sources.join(", ") || "(nothing)"} · cost {p.cost}
                  </span>
                  <div className="mono muted" style={{ whiteSpace: "pre-wrap" }}>
                    {p.preview.slice(0, 220)}
                  </div>
                </li>
              ))}
            </ol>
          </details>
        );
      })}
    </div>
  );
}

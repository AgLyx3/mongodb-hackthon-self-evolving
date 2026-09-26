import type { Clause, Proposal } from "@/lib/api";

function scope(clauses: Clause[] | undefined): string {
  if (!clauses || clauses.length === 0) return "–";
  return clauses.map((c) => `${c.path} ${c.op} ${JSON.stringify(c.value)}`).join(" AND ");
}

function statusText(p: Proposal): { text: string; tone: string } {
  if (p.invalid) return { text: "✕ invalid draft", tone: "var(--color-alarm)" };
  if (p.promoted)
    return {
      text: p.fde?.action === "edit" ? "✓ promoted after FDE edit" : "✓ promoted",
      tone: "var(--color-success)",
    };
  const failed = p.gates.find((g) => !g.passed && g.gate !== "summary");
  if (failed) return { text: `✕ stopped at ${failed.gate}`, tone: "var(--color-warning)" };
  if (p.fde) return { text: `✕ FDE ${p.fde.action} (${p.fde.reason_tag})`, tone: "var(--color-alarm)" };
  return { text: "… pending", tone: "var(--color-content-muted)" };
}

export function ProposalList({ proposals }: { proposals: Proposal[] }) {
  if (proposals.length === 0) {
    return <p className="muted">No proposals yet. They appear after the first discovery round is reviewed.</p>;
  }
  return (
    <div style={{ borderTop: "1px solid var(--color-border)" }}>
      {proposals.map((p) => {
        const s = statusText(p);
        const unit = p.change?.add;
        const backtest = p.gates.find((g) => g.gate === "backtest");
        const edited = p.gates.find((g) => g.gate === "backtest_fde_edit");
        return (
          <details key={p.id} style={{ borderBottom: "1px solid var(--color-border)" }}>
            <summary
              style={{
                display: "grid",
                gridTemplateColumns: "56px 1fr 240px 180px",
                gap: "var(--space-3)",
                padding: "var(--space-2) 0",
                cursor: "pointer",
                listStyle: "none",
              }}
            >
              <span className="muted">round {p.batch}</span>
              <span>{unit ? `${unit.kind}: ${unit.title}` : p.summary}</span>
              <span style={{ color: s.tone }}>{s.text}</span>
              <span className="muted">
                {p.matched_signal ? `answer key: ${p.matched_signal}` : "answer key: no match"}
              </span>
            </summary>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "1fr 1fr",
                gap: "var(--space-6)",
                padding: "var(--space-3) 0 var(--space-4) 56px",
              }}
            >
              <div className="prose-block">
                <div className="muted">Hypothesis</div>
                <p style={{ margin: "var(--space-1) 0 var(--space-3)" }}>{p.hypothesis ?? "–"}</p>
                <div className="muted">Falsified if</div>
                <p style={{ margin: "var(--space-1) 0 var(--space-3)" }}>
                  {p.falsification_criterion ?? "–"}
                </p>
                <div className="muted">Change</div>
                <pre
                  className="mono"
                  style={{
                    background: "var(--color-surface-sunken)",
                    padding: "var(--space-2)",
                    borderRadius: "var(--radius-sm)",
                    whiteSpace: "pre-wrap",
                  }}
                >
                  {unit
                    ? `+ [${unit.unit_id}] ${unit.title}\n+ ${
                        unit.kind === "rule"
                          ? `when ${scope(unit.applies_when?.all_of)} -> ${unit.disposition}`
                          : `definition of ${unit.field}`
                      }\n+ ${unit.text}`
                    : `- retire ${p.change?.retire_hash ?? ""}`}
                  {p.fde?.action === "edit" && p.fde.final_scope
                    ? `\n\nFDE-approved scope:\n~ ${p.fde.final_scope}`
                    : ""}
                </pre>
                <div className="muted">Evidence sources</div>
                <p className="mono" style={{ margin: "var(--space-1) 0" }}>
                  {(p.evidence_refs ?? []).join(", ") || "–"}
                </p>
              </div>
              <div>
                <div className="muted">Gates (before the FDE sees it)</div>
                <ul style={{ margin: "var(--space-1) 0 var(--space-3)", paddingLeft: "var(--space-4)" }}>
                  {p.gates
                    .filter((g) => g.gate !== "summary")
                    .map((g, i) => (
                      <li key={`${g.gate}-${i}`}>
                        {g.passed ? "✓" : "✕"} {g.gate}: <span className="muted">{g.detail}</span>
                      </li>
                    ))}
                </ul>
                {backtest ? (
                  <p className="muted" style={{ margin: "0 0 var(--space-3)" }}>
                    Replay: {backtest.replay_fixed?.length ?? 0} fixed,{" "}
                    {backtest.replay_broken?.length ?? 0} broken
                    {edited ? `; after FDE edit: ${edited.detail}` : ""}
                  </p>
                ) : null}
                <div className="muted">FDE decision{p.fde ? `, signed by ${p.fde.fde_id}` : ""}</div>
                <p style={{ margin: "var(--space-1) 0 var(--space-3)" }}>
                  {p.fde
                    ? `${p.fde.action} (${p.fde.reason_tag}), edit distance ${p.fde.edit_distance.toFixed(
                        2,
                      )}. ${p.fde.rationale}`
                    : "Not shown to the FDE (stopped by a gate)."}
                </p>
                <div className="muted">Recalled past decisions (same customer, vector search)</div>
                {p.recalled && p.recalled.length > 0 ? (
                  <ul style={{ margin: "var(--space-1) 0", paddingLeft: "var(--space-4)" }}>
                    {p.recalled.slice(0, 3).map((r) => (
                      <li key={r.proposal_id}>
                        <span className="num">{r.score.toFixed(2)}</span> round {r.batch}:{" "}
                        {r.fde_action
                          ? `FDE ${r.fde_action} (${r.fde_reason})`
                          : `stopped at gates`}{" "}
                        <span className="muted">– {r.summary.slice(0, 120)}</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="muted" style={{ margin: "var(--space-1) 0" }}>
                    Nothing recalled (first round).
                  </p>
                )}
              </div>
            </div>
          </details>
        );
      })}
    </div>
  );
}

import type { Lesson, Retro, RetroRound, UptakeRow } from "@/lib/api";

const CAUSE: Record<string, string> = {
  premature: "Premature rule",
  overgeneralized: "Over-generalized rule",
  partial_data: "Partial data",
  missed_in_read: "Missed in reading",
  not_asked: "Didn't ask the customer",
  conflict_hidden: "Conflicting sources hidden",
  format: "Unverifiable evidence",
};

const cell = { padding: "var(--space-2) var(--space-2)", verticalAlign: "top" as const };

function roundLabel(r: RetroRound): string {
  return r.phase === "final" ? "After the final round" : `Start of round ${r.round}`;
}

function RoundBlock({ r }: { r: RetroRound }) {
  return (
    <div style={{ marginTop: "var(--space-4)" }}>
      <h3 style={{ fontSize: "var(--text-sm)", fontWeight: 600, margin: 0 }}>
        {roundLabel(r)}{" "}
        <span className="muted" style={{ fontWeight: 400 }}>
          · {r.explained_cases} of {r.failed_cases} failed cases traced · signed{" "}
          <span className="mono">{r.fde_id}</span>
        </span>
      </h3>
      {r.items.length === 0 ? (
        <p className="muted">No method feedback: no failure traced back to the agent&apos;s method.</p>
      ) : (
        <table style={{ width: "100%", borderCollapse: "collapse", marginTop: "var(--space-2)" }}>
          <thead>
            <tr className="muted" style={{ textAlign: "left" }}>
              <th style={cell}>Cause</th>
              <th className="num" style={cell}>Failures</th>
              <th style={cell}>Feedback</th>
              <th style={cell}>Cases</th>
            </tr>
          </thead>
          <tbody>
            {r.items.map((i, k) => (
              <tr key={k} style={{ borderTop: "1px solid var(--color-border)" }}>
                <td style={cell}>
                  {CAUSE[i.cause] ?? i.cause}
                  {i.target_unit_id ? (
                    <div className="mono muted">{i.target_unit_id}</div>
                  ) : null}
                </td>
                <td className="num" style={cell}>{i.n_cases}</td>
                <td style={cell} className="prose-block">{i.message}</td>
                <td style={cell} className="mono">{i.cases.join(", ")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function Playbook({ lessons }: { lessons: Lesson[] }) {
  if (lessons.length === 0)
    return <p className="muted">No lessons yet: a lesson is written once a kind of feedback repeats.</p>;
  return (
    <ul className="prose-block" style={{ paddingLeft: "var(--space-4)", margin: 0 }}>
      {lessons.map((l) => (
        <li key={l.id} style={{ marginBottom: "var(--space-2)" }}>
          {l.status === "active" ? l.text : <span className="muted">(draft rejected by lint: {l.lint})</span>}{" "}
          <span className="muted">
            · learned at round {l.created_batch} from repeated “{CAUSE[l.cause] ?? l.cause}” feedback
          </span>
        </li>
      ))}
    </ul>
  );
}

function recurred(u: UptakeRow): string {
  if (u.lesson_round === null) return "no lesson yet";
  if (u.recurred_after_lesson === null) return "no later round yet";
  return u.recurred_after_lesson ? `yes (round ${u.rounds_after_lesson.join(", ")})` : "no";
}

function UptakeTable({ rows }: { rows: UptakeRow[] }) {
  if (rows.length === 0) return <p className="muted">No feedback yet.</p>;
  return (
    <table style={{ width: "100%", borderCollapse: "collapse" }}>
      <thead>
        <tr className="muted" style={{ textAlign: "left" }}>
          <th style={cell}>Cause</th>
          <th style={cell}>Appeared at rounds</th>
          <th className="num" style={cell}>Lesson learned at round</th>
          <th style={cell}>Recurred after the lesson?</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((u) => (
          <tr key={u.cause} style={{ borderTop: "1px solid var(--color-border)" }}>
            <td style={cell}>{CAUSE[u.cause] ?? u.cause}</td>
            <td style={cell}>{u.rounds.join(", ")}</td>
            <td className="num" style={cell}>{u.lesson_round ?? "–"}</td>
            <td style={cell}>{recurred(u)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function RetroSection({ retro }: { retro: Retro }) {
  if (retro.rounds.length === 0)
    return <p className="muted">No retrospectives in this run (it did not use the retro FDE mode).</p>;
  return (
    <>
      {retro.rounds.map((r) => (
        <RoundBlock key={`${r.round}-${r.phase}`} r={r} />
      ))}
      <h3 style={{ fontSize: "var(--text-sm)", fontWeight: 600, margin: "var(--space-6) 0 var(--space-2)" }}>
        Discovery playbook
      </h3>
      <Playbook lessons={retro.lessons} />
      <h3 style={{ fontSize: "var(--text-sm)", fontWeight: 600, margin: "var(--space-6) 0 var(--space-2)" }}>
        Feedback uptake
      </h3>
      <UptakeTable rows={retro.uptake} />
    </>
  );
}

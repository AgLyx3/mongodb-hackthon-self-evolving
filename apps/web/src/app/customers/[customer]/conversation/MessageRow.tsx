import type { Actor, ConversationMessage } from "@/lib/api";
import { argsText } from "../ProbeTimeline";

const ACTOR: Record<Actor, string> = {
  system: "Harness",
  investigator: "Investigator",
  tool: "Tool",
  customer: "Customer contact",
  proposer: "Proposer",
  gates: "Gates",
  fde: "FDE",
  playbook: "Playbook",
};

const DECISION: Record<string, { sign: string; color: string }> = {
  accept: { sign: "✓", color: "var(--color-success)" },
  edit: { sign: "✎", color: "var(--color-warning)" },
  reject: { sign: "✗", color: "var(--color-alarm)" },
};

function Sources({ sources }: { sources: string[] }) {
  if (sources.length === 0) return null;
  return (
    <span style={{ display: "inline-flex", gap: "var(--space-1)", flexWrap: "wrap" }}>
      {sources.map((s) => (
        <span
          key={s}
          className="mono"
          style={{
            border: "1px solid var(--color-border)",
            borderRadius: "var(--radius-sm)",
            padding: "0 var(--space-1)",
            color: "var(--color-content-muted)",
          }}
        >
          {s}
        </span>
      ))}
    </span>
  );
}

function Items({ items }: { items: string[] }) {
  if (items.length === 0) return null;
  return (
    <ul className="prose-block" style={{ margin: "var(--space-1) 0 0", paddingLeft: "var(--space-4)" }}>
      {items.map((it, i) => (
        <li key={i}>{it}</li>
      ))}
    </ul>
  );
}

// Search previews are truncated JSON; the collapsed line quotes the first hit's text instead.
function firstQuote(preview: string): string | null {
  const m = preview.match(/"text": "((?:[^"\\]|\\.)*)/);
  return m ? m[1].replace(/\\"/g, '"') : null;
}

function pretty(preview: string): string {
  try {
    return JSON.stringify(JSON.parse(preview), null, 2);
  } catch {
    return preview;
  }
}

function Body({ m }: { m: ConversationMessage }) {
  switch (m.kind) {
    case "tool_call": {
      const args = JSON.parse(m.detail ?? "{}") as Record<string, unknown>;
      return (
        <div>
          <span className="mono" style={{ color: "var(--color-content)" }}>
            {m.text}
          </span>{" "}
          {argsText({ tool: m.text, args })} <span className="muted">· {m.status}</span>
        </div>
      );
    }
    case "tool_result": {
      const quote = firstQuote(m.text);
      return (
        <details>
          <summary style={{ cursor: "pointer", listStyle: "none" }}>
            <Sources sources={m.sources.length ? m.sources : ["nothing"]} />{" "}
            {quote ? (
              <span>“{quote.slice(0, 200)}{quote.length > 200 ? "…" : ""}”</span>
            ) : (
              <span className="mono muted">{m.text.slice(0, 160)}</span>
            )}
            <span className="muted"> · show raw</span>
          </summary>
          <pre
            className="mono"
            style={{
              whiteSpace: "pre-wrap",
              background: "var(--color-surface-sunken)",
              padding: "var(--space-2)",
              borderRadius: "var(--radius-sm)",
              margin: "var(--space-1) 0 0",
              maxHeight: "calc(var(--space-16) * 4)",
              overflow: "auto",
            }}
          >
            {pretty(m.text)}
          </pre>
        </details>
      );
    }
    case "finding":
      return (
        <div className="prose-block">
          <span className="muted">Finding{m.status ? ` (${m.status})` : ""}: </span>
          {m.text}
          {m.detail ? <div className="muted">Evidence: {m.detail}</div> : null}
          <Sources sources={m.sources} />
        </div>
      );
    case "proposal":
    case "revision":
      return (
        <div>
          <div>
            <span className="muted">{m.kind === "revision" ? "Revised proposal" : "Proposes"}: </span>
            <strong>{m.text}</strong> <span className="mono muted">{m.ref}</span>
          </div>
          {m.detail ? <div className="muted">{m.detail}</div> : null}
          <Items items={m.items} />
          {m.sources.length ? (
            <div style={{ marginTop: "var(--space-1)" }}>
              <span className="muted">Evidence: </span>
              <Sources sources={m.sources} />
            </div>
          ) : null}
        </div>
      );
    case "gate": {
      const ok = m.status === "pass";
      return (
        <div>
          <span style={{ color: ok ? "var(--color-success)" : "var(--color-alarm)", fontWeight: 600 }}>
            {ok ? "✓ pass" : "✗ fail"}
          </span>{" "}
          {m.text} <span className="muted">· {m.detail}</span>
        </div>
      );
    }
    case "decision": {
      const d = DECISION[m.text] ?? { sign: "·", color: "var(--color-content)" };
      return (
        <div className="prose-block">
          <span style={{ color: d.color, fontWeight: 600 }}>
            {d.sign} {m.text}
          </span>
          {m.status ? <span className="muted"> [{m.status}]</span> : null}
          {m.detail ? <div>{m.detail}</div> : null}
          {m.items.length ? <div className="muted">Counterexamples and scope:</div> : null}
          <Items items={m.items} />
        </div>
      );
    }
    case "promotion":
      return (
        <div>
          → <strong>Promoted.</strong> Live version is now <span className="mono">{m.ref}</span>
          {m.detail ? <span className="muted"> · unit <span className="mono">{m.detail}</span></span> : null}
        </div>
      );
    case "round_result":
      return (
        <div>
          <strong>{m.text}</strong> <span className="muted">· {m.detail}</span>
        </div>
      );
    case "lesson":
      return (
        <div className="prose-block">
          <span className="muted">
            {m.status === "active" ? "Lesson added" : "Lesson rejected"} ({m.detail}):{" "}
          </span>
          {m.text}
        </div>
      );
    default:
      return (
        <div className="prose-block">
          {m.text}
          {m.detail ? <div className="muted">{m.detail}</div> : null}
          <Items items={m.items} />
        </div>
      );
  }
}

export function MessageRow({ m }: { m: ConversationMessage }) {
  if (m.kind === "round_start") {
    return (
      <div
        id={`round-${m.round}`}
        style={{
          display: "flex",
          alignItems: "center",
          gap: "var(--space-3)",
          margin: "var(--space-6) 0 var(--space-2)",
        }}
      >
        <span style={{ fontSize: "var(--text-lg)", fontWeight: 600 }}>{m.text}</span>
        <span style={{ flex: 1, borderTop: "1px solid var(--color-border)" }} />
      </div>
    );
  }
  const isReply = m.kind === "tool_result";
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "calc(var(--space-16) * 2) 1fr",
        gap: "var(--space-3)",
        padding: "var(--space-2) 0",
        paddingLeft: `calc(var(--space-6) * ${m.depth})`,
        borderTop: isReply ? "none" : "1px solid var(--color-border)",
      }}
    >
      <div>
        <div style={{ fontWeight: 600, color: isReply ? "var(--color-content-muted)" : "var(--color-content)" }}>
          {isReply ? "↳ " : ""}
          {ACTOR[m.actor]}
        </div>
        {m.who ? <div className="mono muted">{m.who}</div> : null}
      </div>
      <div style={{ minWidth: 0, overflowWrap: "anywhere" }}>
        <Body m={m} />
      </div>
    </div>
  );
}

import Link from "next/link";
import { notFound } from "next/navigation";
import { api } from "@/lib/api";
import { ConversationView } from "./ConversationView";

export const dynamic = "force-dynamic";

export default async function ConversationPage({ params }: { params: Promise<{ customer: string }> }) {
  const { customer } = await params;
  if (customer !== "bank" && customer !== "fintech") notFound();
  let data;
  try {
    const [customers, conversation] = await Promise.all([api.customers(), api.conversation(customer)]);
    data = { customers, conversation };
  } catch {
    return (
      <p>
        The harness API is not reachable. Start it with{" "}
        <span className="mono">uv run uvicorn harness.api.app:app</span> in services/harness.
      </p>
    );
  }
  const c = data.customers.find((x) => x.id === customer);
  if (!c) notFound();
  const conv = data.conversation;

  return (
    <>
      <div style={{ display: "flex", alignItems: "baseline", gap: "var(--space-3)" }}>
        <h1 style={{ fontSize: "var(--text-2xl)", fontWeight: 600, margin: 0 }}>{c.display_name}: the run as a conversation</h1>
        <Link href={`/customers/${customer}`} style={{ color: "var(--color-primary)", marginLeft: "auto" }}>
          Back to dashboard
        </Link>
      </div>
      <p className="muted prose-block" style={{ margin: "var(--space-1) 0 var(--space-2)" }}>
        Every line is a recorded document from Atlas, in the order the loop produced it; nothing is regenerated.
        Investigator and Proposer are LLM agents; Gates are code; the FDE is{" "}
        <span className="mono">sim-fde:jordan</span>, a deterministic simulated reviewer that never calls an LLM.
        Run <span className="mono">{conv.run_id ?? "(pre-registry run)"}</span>
        {conv.fde_mode ? ` · FDE mode ${conv.fde_mode}` : ""}
        {conv.status ? ` · ${conv.status}` : ""}
        {conv.runtime_model ? (
          <>
            {" "}
            · triage model <span className="mono">{conv.runtime_model}</span>
          </>
        ) : null}
        .
      </p>
      {conv.messages.length === 0 ? (
        <p className="muted">No recorded run for this customer yet. Run the evolution loop to produce one.</p>
      ) : (
        <ConversationView messages={conv.messages} />
      )}
    </>
  );
}

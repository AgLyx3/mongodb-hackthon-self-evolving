import { notFound } from "next/navigation";
import { api } from "@/lib/api";
import { AccuracyChart } from "./AccuracyChart";
import { ComparisonTable } from "./ComparisonTable";
import { Kpis } from "./Kpis";
import { ProposalList } from "./ProposalList";
import { Section } from "./Section";
import { SourceHeatmap } from "./SourceHeatmap";
import { TapInTable } from "./TapInTable";
import { VersionList } from "./VersionList";

export const dynamic = "force-dynamic";

export default async function CustomerPage({ params }: { params: Promise<{ customer: string }> }) {
  const { customer } = await params;
  if (customer !== "bank" && customer !== "fintech") notFound();
  let data;
  try {
    const [customers, timeline, proposals, sources, metrics, harness, comparison] = await Promise.all([
      api.customers(),
      api.timeline(customer),
      api.proposals(customer),
      api.sources(customer),
      api.metrics(customer),
      api.harness(customer),
      api.comparison(customer),
    ]);
    data = { customers, timeline, proposals, sources, metrics, harness, comparison };
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
  const noisePts = ((data.timeline.noise_cases ?? 0) / 40) * 100;
  const points = data.metrics.holdout_by_batch.map((r) => ({
    label: r.batch === 0 ? "start (0 alerts)" : `round ${r.batch} (${r.batch * 30} alerts)`,
    acc: r.acc,
  }));
  const strong = data.metrics.strong_baseline ?? null;

  return (
    <>
      <div style={{ display: "flex", alignItems: "baseline", gap: "var(--space-3)" }}>
        <h1 style={{ fontSize: "var(--text-2xl)", fontWeight: 600, margin: 0 }}>{c.display_name}</h1>
        <span className="muted">
          {c.industry} · live version <span className="mono">{c.live_version ?? "–"}</span>
        </span>
      </div>
      <p className="muted prose-block" style={{ marginBottom: "var(--space-4)" }}>
        {customer === "fintech"
          ? "Held-out customer: code and prompts were frozen before this run; nothing was tuned on it."
          : "Development customer."}{" "}
        Each batch: the triage agent works alerts, outcomes are revealed, the investigator probes
        sources, the proposer suggests single-unit changes, gates backtest them, the simulated FDE
        decides, and only then does a version go live.
      </p>
      <Kpis metrics={data.metrics} strongBaseline={strong} />

      <Section
        title="With vs without: accuracy by discovery round"
        caption={`Measured on 40 report cases that no gate or decision ever sees. Shaded: noise band (±${noisePts.toFixed(1)} pts, from 3 re-runs of the unchanged harness on the gate's holdout). Gray: the same cheap model on the static base harness. Dashed: a strong model on the base harness.`}
      >
        <AccuracyChart
          points={points}
          noisePts={noisePts}
          strongBaseline={strong}
          withoutAcc={data.metrics.static_base_acc}
        />
      </Section>

      <Section
        title="Time to tap in"
        caption="Investigation cost per discovery round, measured in probe units (queries 1, reads 2, customer questions 3), not wall-clock. Decoy = sources the answer key marks irrelevant."
      >
        <TapInTable metrics={data.metrics} />
      </Section>

      <Section
        title="Model × harness on the report cases"
        caption="Does an evolved harness let a cheap model match a strong one? And does a harness evolved on one model's trajectories carry over to another?"
      >
        <ComparisonTable comparison={data.comparison} />
      </Section>

      <Section
        title="Proposals"
        caption="What the agent proposed, what the gates found, what it recalled from past FDE decisions, and what the FDE decided."
      >
        <ProposalList proposals={data.proposals} />
      </Section>

      <Section title="Version history" caption="Immutable, content-hashed versions. Only FDE actions move the live pointer.">
        <VersionList versions={data.timeline.versions} />
      </Section>

      <Section
        title="Where the investigator looked"
        caption="Probe budget spent per source and batch, and usefulness learned from surviving changes. 'no priors' reruns the last investigation without the learned usefulness."
      >
        <SourceHeatmap customer={c} sources={data.sources} metrics={data.metrics} />
      </Section>

      <Section title="Live harness" caption="The procedural memory the triage agent reads, rendered from versioned units.">
        <pre
          className="mono"
          style={{
            background: "var(--color-surface-sunken)",
            padding: "var(--space-4)",
            borderRadius: "var(--radius-md)",
            whiteSpace: "pre-wrap",
            maxHeight: 480,
            overflow: "auto",
          }}
        >
          {data.harness.rendered}
        </pre>
      </Section>

      <Section title="Next, not built today">
        <ul className="prose-block" style={{ paddingLeft: "var(--space-4)" }}>
          <li>
            Model-switch re-validation: the live pointer is keyed by (customer, runtime model); a new
            model starts unvalidated, re-measures the noise band, and may only re-tune the
            model-bound layer.
          </li>
          <li>
            Cross-customer synthesis: surviving changes that recur across customers become proposals
            to the base harness (the shared planted signal is the answer key).
          </li>
        </ul>
      </Section>
    </>
  );
}

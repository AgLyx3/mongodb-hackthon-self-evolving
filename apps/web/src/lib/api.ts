// Typed client for the harness API. The browser never talks to MongoDB directly.
const BASE = process.env.HARNESS_API_URL ?? "http://localhost:8000";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`API ${path} returned ${res.status}`);
  return (await res.json()) as T;
}

export type ManifestEntry = { source_id: string; kind: string; described_as: string };
export type Customer = {
  id: string;
  display_name: string;
  industry: string;
  manifest: ManifestEntry[];
  record_schema: Record<string, string>;
  live_version: string | null;
};

export type VersionRow = {
  version: string;
  parent: string | null;
  batch: number;
  reason: string;
  edge: string | null;
  proposal_id: string | null;
  holdout_acc: number | null;
  unit_id: string | null;
  fde_action: string | null;
  at: string;
};
export type Timeline = {
  versions: VersionRow[];
  noise_cases: number | null;
  noise_accs: number[] | null;
  reports: { batch: number; holdout_acc: number; probes_spent?: number; spent_usd?: number }[];
};

export type Gate = {
  gate: string;
  passed: boolean;
  detail: string;
  replay_fixed?: string[];
  replay_broken?: string[];
  holdout_net?: number;
  activations?: number;
};
export type Recalled = {
  proposal_id: string;
  summary: string;
  batch: number;
  score: number;
  fde_action: string | null;
  fde_reason: string | null;
  fde_rationale: string | null;
  fde_final_scope: string | null;
  gate: string | null;
};
export type Clause = { path: string; op: string; value: string | number | boolean };
export type UnitDoc = {
  unit_id: string;
  kind: string;
  layer: string;
  title: string;
  text: string;
  field: string | null;
  disposition: string | null;
  applies_when: { all_of: Clause[] } | null;
};
export type Proposal = {
  id: string;
  batch: number;
  summary: string;
  hypothesis?: string;
  falsification_criterion?: string;
  evidence_refs?: string[];
  change?: { add: UnitDoc | null; retire_hash: string | null };
  recalled?: Recalled[];
  invalid?: string;
  gates: Gate[];
  fde: {
    action: string;
    reason_tag: string;
    rationale: string;
    edit_distance: number;
    final_scope: string | null;
    promoted: boolean;
  } | null;
  outcome: string;
  promoted: boolean;
  matched_signal: string | null;
};

export type Sources = {
  probes: Record<string, Record<string, { cost: number; calls: number }>>;
  usefulness_by_batch: { batch: number; usefulness: Record<string, number> }[];
  relevant_sources: string[];
};

export type Metrics = {
  planted_signals: string[];
  signals_learned: string[];
  signal_recall: number;
  holdout_by_batch: { batch: number; acc: number }[];
  noise_cases: number | null;
  proposals: number;
  promoted: number;
  survived: number;
  stopped_or_rejected: number;
  fde_actions: Record<string, number>;
  fde_reasons: Record<string, number>;
  edit_distance_by_batch: Record<string, number>;
  decoy_spend: Record<string, { total: number; irrelevant: number; irrelevant_share: number }>;
  spent_usd_total: number;
  strong_baseline: number | null;
};

export type Harness = {
  version: string | null;
  rendered: string;
  units: (UnitDoc & { hash: string; scope: string | null; origin: string })[];
};

export const api = {
  customers: () => get<Customer[]>("/api/customers"),
  timeline: (c: string) => get<Timeline>(`/api/customers/${c}/timeline`),
  proposals: (c: string) => get<Proposal[]>(`/api/customers/${c}/proposals`),
  sources: (c: string) => get<Sources>(`/api/customers/${c}/sources`),
  metrics: (c: string) => get<Metrics>(`/api/customers/${c}/metrics`),
  harness: (c: string) => get<Harness>(`/api/customers/${c}/harness`),
};

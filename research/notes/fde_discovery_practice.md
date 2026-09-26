# FDE discovery practice: grounding the decision-record schema

Researched 2026-09-26. Every claim carries a source number from the list at the end.
Tags: [primary] = vendor docs, job posting, court record, or survey publisher.
[secondary] = blog or aggregator summarising someone else. Items marked
"(search snippet)" came from a search-result summary because the page itself
returned 403. Treat them as lower confidence.

## 1. How FDE discovery works (what gets decided in the first weeks)

**OpenAI.** The FDE job posting says FDEs "own discovery, technical scoping, system
design, build, and production rollout, partnering directly with customer engineering
and domain teams". They "prepare detailed scopes of work" for both POCs and production,
and they "codify solution patterns and evals". Success is measured by "production
adoption, measurable workflow impact, and eval-driven feedback" [1] (search snippet; the page returned 403).
So discovery produces a scope, a success metric, and an eval.

**OpenAI agent guide** [2] [primary, text extracted from the PDF] gives the design
decisions that discovery has to feed:
- "Use existing documents: When creating routines, use existing operating procedures,
  support scripts, or policy documents". Policies and SOPs are the evidence source for
  thresholds and eligibility rules.
- "Set up evals to establish a performance baseline". The success metric has to be set before the build.
- Tool risk is rated on "read-only vs. write access, reversibility, required account
  permissions, and financial impact". This maps to the forbidden or gated actions slot.
- Human-intervention triggers: "Exceeding failure thresholds" and "High-risk actions ...
  sensitive, irreversible, or have high stakes ... canceling user orders, authorizing
  large refunds, or making payments." That covers both the approval threshold and the escalation slot.
- Prime candidate workflows involve "context-sensitive decisions, for example refund approval".

**Anthropic.** The Applied AI FDE posting lists "Work within customer systems to build
production applications", "Deliver technical artifacts ... like MCP servers, sub-agents,
and agent skills", and "conduct discovery with customers". It asks for experience with
"evaluation frameworks" [3] [primary]. MCP servers and skills are integration-surface artifacts.

**Palantir.** Palantir popularised the FDE title "by 2009". Wikipedia describes the model
as embedding an engineer "with a customer for a few months" [4]. The AIP Bootcamp promises
"zero to use case in 1-5 days" on the customer's own data inside their security perimeter
[5] (search snippet; the page body didn't render). Palantir blog posts on the FDSE and Deployment Strategist
roles returned 403 and are not quoted.

**Sierra.** Agents carry "declarative guardrails that the agent cannot cross (e.g.,
orders can only be returned within 30 days of purchase)". Releases include "an immutable
snapshot of all of the knowledge", and "Immutable agent releases enable Sierra customers
to roll back agent behavior instantly" [6] [primary]. "Journey specs" hold return
policies and "necessary APIs". Policies encode exceptions, for example a standard 30-day
return window versus 45 days for loyal customers [7] [primary]. The eligibility rule
therefore needs an exception branch, not a single number.

**Decagon.** Implementation takes "approximately 6 weeks from initial discovery to full
deployment" [8] [primary]:
- Week 1 pre-kickoff: "Identify your existing tech stack, workflows, and key players";
  "Establish a secure sandbox environment".
- Week 2 kickoff: "Define clear metrics (e.g., deflection rates, CSAT targets) and identify
  the specific use cases for the initial pilot"; convert SOPs into AOPs.
- Technical track: "CRM access, authentication (such as Signature Auth), and API documentation".
- Weeks 3-4: "routing rules, escalation paths".
- Week 6: launch "to a specific percentage of traffic or a single channel".

Decagon's escalation policy covers "triggers ... handoff procedure, and the routing logic
that selects the right human team or individual" [9] [primary].

**Salesforce Agentforce.** The secure-implementation guidance has five attributes:
Role, Data ("only the data the agent truly needs"), Actions (public vs private actions
that require "identity verification"), Guardrails, and Channel ("Secure every deployment
endpoint") [10] [primary]. Private vs public actions means the auth method differs per action.

**Microsoft.** The agent lifecycle is discovery, experimentation, build, deploy, and
steady state. Discovery means "Identify requirements, stakeholders, needs, and project
scope". It warns that "Proof of concept ideation using synthetic data increases the risk
of agents not performing as expected in production" [11] [primary].

**Secondary synthesis.** Perspective AI describes a Week 0 "stakeholder map" that "names
every human who can kill, delay, or expand the deployment" (exec sponsor, eval owner, end
users, admin/IT counterpart, skeptic), followed by interviews and then eval co-design with
SMEs [12] [secondary, vendor content marketing]. a16z says FDE and services teams "handle
the heavy lifting of securely connecting the AI application to internal databases, APIs,
and workflows" and ensure "historical records, business logic" are available [13] [secondary].

**Takeaway.** Across vendors, the first weeks settle the following:
- use case and scope
- success metric and baseline eval
- systems and APIs, plus credentials
- policy documents that turn into rules
- escalation routing
- sandbox or environment
- staged rollout plan

## 2. Checklists and questionnaires

- **Dynamics 365 go-live checklist** [14] [primary] has 11 areas. Several are directly
  slot-relevant:
  - "Align external dependencies, such as partner systems and services, with the
    timelines and scope for go-live"
  - "Create a cutover plan that considers all dependencies, the timing ... roles and
    responsibilities"
  - "Get sign-off from stakeholders at the cutover go/no-go checkpoint"
  - SIT must "Simulate external systems that are down"
  - UAT must "Comply with regulatory requirements specific to your company, industry, or
    country/region" and "Test with migrated data"
  - Support readiness: "provide them with a support contact"; "Hypercare"
  - Solution scope must list "The type and volume of integrations".
- **SaaS kickoff templates** [15] [secondary]: the kickoff call should "establish success
  criteria, go-live date, and ownership (who owns what on each side)"; provision "SSO if
  in the contract". "Enterprise accounts with data migration or SSO can take 60 to 90 days."
- **Intercom Fin** [16] [primary]: data connectors to external systems plus
  "escalation guidance and rules" routed to specific teams.
- **CAIQ v4** (CSA) [17] [primary]: 261 yes/no questions mapped to the Cloud Controls
  Matrix. Its Data Security & Privacy (DSP) domain covers classification, retention,
  disposal, and data residency [18] [secondary]. **SIG** (Shared Assessments) spans
  roughly 19-21 risk domains including privacy and data governance [19] [secondary; the
  sharedassessments.org page needed a login]. Use these only to enumerate the values of
  the data-constraint slot (PII class, residency region, retention); FDEs don't fill them.

## 3. What causes rework, rollback, and delay

| Cause | Evidence | Slot it implicates |
| --- | --- | --- |
| Inaccurate requirements | PMI Pulse 2014: 37% of orgs cite inaccurate requirements as primary cause of failure; 2017: 39% [20] (search snippet of pmi.org; page 403) | all; esp. thresholds and eligibility |
| Late-discovered misfit leading to scope growth | Panorama 2026 ERP report: "More than a quarter of organizations exceeded their project budgets"; "Organizations often discover fatal misfits late in the project, so they turn to additional technology, scope expansion, and custom builds" [21] | system of record, integration surface |
| Integration gaps | MuleSoft 2025 (n=1,050 IT leaders): "95% of organizations face challenges in integrating AI into existing processes, and 80% cite data integration as their most significant obstacle"; 897 apps on average, only 29% integrated [22] | integration surface, auth |
| Agent quality in production | LangChain survey (n=1,340, Nov-Dec 2025): quality is the top barrier at 32%, latency 20%; security 24.9% among 2k+ employee firms [23] | success metric, eval |
| Unclear value or risk controls | Gartner (Jun 2025): >40% of agentic AI projects canceled by end-2027 due to "escalating costs, unclear business value or inadequate risk controls" [24] (search snippet; gartner.com 403) | success metric, forbidden actions |
| Policy misstated by agent | Moffatt v. Air Canada, 2024 BCCRT 149: the chatbot misstated the bereavement-refund rule and the airline was held liable [25] | business thresholds, eligibility, source-of-truth doc |
| Invented policy | Cursor "Sam" bot (2025-04-19) "responded with an invented login policy ... led to subscription cancellations" [26] | eligibility and forbidden actions (agent must not invent policy) |
| Missing human escalation | Klarna CEO (May 2025): "cost ... too predominant evaluation factor ... what you end up having is lower quality"; the company re-hired humans so "there will always be a human" [27] (secondary coverage of a Bloomberg interview) | escalation owner, success metric |
| Synthetic-data POCs | Microsoft: synthetic POC data "increases the risk of agents not performing as expected in production" [11] | system of record (use real data) |

Gap: I found no public survey with a rework rate broken down by cause (wrong system of
record vs missed compliance vs unclear escalation). The table links causes to slots by
inference from case evidence.

## 4. FDE effectiveness metrics

- **Time to value / time to first value.** TSIA ties time to value to adoption and renewal
  and says CSMs lack "use cases, business criticality, and success metrics" at handoff.
  It recommends capturing them during the sale ("left shift") [28] [primary]. Commonly
  quoted benchmarks are TTV under 30 days for B2B SaaS and 60-90 days for complex
  enterprise with integrations [29] [secondary, vendor blog; unverified origin].
- **Time to first deployment.** Decagon cites about 6 weeks [8]. Palantir cites 1-5 days
  to a working use case [5]. Intercom Fin says "two to four weeks" (search snippet) [16].
- **Production adoption, workflow impact, and eval-driven feedback.** These are OpenAI's
  stated FDE success measures [1].
- **Rework rate / time-to-decision.** I found no public FDE-specific benchmark. Proxies
  are Dynamics' "owner and a completion date" per UAT issue [14] and Sierra's daily
  annotated-conversation review [6]. For the benchmark, a reasonable choice is to define
  rework as slot values changed after the go/no-go.

## Proposed slot schema, revised

Status: **KEEP** = well supported by 3+ sources; **MERGE**/**SPLIT** = restructure;
**ADD** = missing slot that practitioners consistently mention; **DROP** = none dropped outright.

| # | Slot | Type | Status | Why it matters | Typical evidence sources | Typical trap / conflict |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | system_of_record | `{entity, system, owner_team}[]` | KEEP | Late misfit discovery drives overruns [21]; agent needs "historical records" [13] | architecture doc, DB schema, Slack "which one is canonical?" | two systems hold the same entity (CRM vs billing); stale migration doc names the old system |
| 2 | integration_surface | `{system, mode: rest/graphql/db/mcp/file, endpoint, read_write}[]` | KEEP (add read/write) | 80% cite data integration as top obstacle [22]; tool risk depends on read vs write [2] | API docs, OpenAPI spec, Jira tickets | doc says read-only but a ticket requests write-back; deprecated endpoint |
| 3 | auth_method | `{system, method: oauth/api_key/sso/signed, scope, per_action}` | KEEP | Decagon technical track [8]; Agentforce private actions need identity verification [10]; SSO adds 60-90 days [15] | security review, IT email, sandbox creds | end-user auth vs service auth conflated; SSO "in contract" but not provisioned |
| 4 | rate_limit_sla | `{system, rpm, latency_p95_ms, uptime}` | KEEP (weaker) | Dynamics perf testing "with peak volumes" and SIT "external systems that are down" [14]; latency is the #2 barrier [23] | API docs, vendor contract, incident postmortem | doc limit differs from observed 429s; peak-season volume ignored |
| 5 | data_constraints | `{pii_fields[], residency_region, retention_days, regulated_by[]}` | KEEP | UAT regulatory compliance [14]; CAIQ DSP / SIG privacy [17][19]; "only the data the agent truly needs" [10] | DPA, security questionnaire, legal email | residency stated in contract but the cluster is in another region; PII in free-text fields |
| 6 | business_thresholds | `{name, value, unit, source_doc, effective_date}[]` | KEEP | "authorizing large refunds" is a high-risk action [2]; Sierra "within 30 days" [6]; Air Canada [25] | policy PDF, SOP, finance email | policy doc vs newer email disagree; value changed mid-onboarding (needs effective_date) |
| 7 | eligibility_rule | `{rule, exceptions[], source_doc}` | KEEP, add exceptions | Sierra 30 vs 45-day loyal-customer exception [7]; SOPs become AOPs [8] | SOP, KB article, meeting notes | exception only mentioned verbally in a meeting; KB article outdated |
| 8 | escalation_owner | `{trigger[], team, contact, channel, hours}` | KEEP, widen to escalation policy | triggers + routing [9]; failure-threshold and high-risk triggers [2]; Klarna [27]; support contact [14] | org chart, Slack, runbook | named person left; two teams each think the other owns it |
| 9 | forbidden_actions | `{action, rule: never/needs_approval, approver?}[]` | KEEP, merge with approval gates | tool risk ratings [2]; Agentforce action authorization [10]; Cursor invented policy [26] | security review, legal, CX lead email | "never" in one source, "with approval" in another |
| 10 | success_metric | `{metric, baseline, target, eval_set_ref}` | KEEP, add baseline | "establish a performance baseline" [2]; deflection/CSAT targets [8]; OpenAI FDE success measures [1]; Gartner "unclear business value" [24] | kickoff deck, exec email, dashboard | exec target vs ops target differ; no baseline measured |
| 11 | go_live_constraint | `{environment: sandbox/staging/prod, freeze_windows[], rollout: pct/channel, go_no_go_owner}` | KEEP, expand | cutover plan and go/no-go sign-off [14]; staged % or channel rollout [8]; sandbox first [8]; instant rollback [6] | release calendar, change-management email, IT ticket | freeze window (e.g., fiscal year-end) collides with target date; prod creds requested before sandbox sign-off |
| 12 | **decision_owner / stakeholders** | `{role: sponsor/eval_owner/it_admin/approver, name}[]` | **ADD** | "ownership (who owns what on each side)" [15]; stakeholder map [12]; business sign-off everywhere in [14] | kickoff notes, org chart, email CCs | sponsor and approver are different people; the skeptic has a veto nobody recorded |
| 13 | **in_scope_use_cases** | `{use_case, channel, out_of_scope[]}` | **ADD** | "identify the specific use cases for the initial pilot" [8]; scope sign-off [14]; Agentforce "scope boundaries" [10] | SOW, kickoff deck | scope creep from Slack requests; channel (chat vs email vs voice) unstated |

Notes on the draft:
- **No draft slot should be dropped.** rate_limit_sla has the weakest direct support: only
  performance and SIT testing [14] and latency as a barrier [23]. Keep it, but the benchmark
  could make it optional or merge it into integration_surface.
- **Merges.** Fold "approval threshold" into forbidden_actions (`needs_approval` plus
  approver), and keep numeric values in business_thresholds so both slots reference the same values.
- **Additions.** Practitioners consistently name decision_owner/stakeholders and
  in_scope_use_cases. Both drive the "unclear value" and "inaccurate requirements" failure modes [20][24].
- **Cross-cutting field for every slot:** `source_ref` + `as_of` + `confidence`. The
  documented failures (Air Canada, Cursor, PMI, Panorama) are mostly about *which source
  wins* and *when it changed*, not about a missing field.

## Sources

1. OpenAI, Forward Deployed Engineer (FDE) - SF, job posting. https://openai.com/careers/forward-deployed-engineer-(fde)-sf-san-francisco/ (403 on fetch; search snippet)
2. OpenAI, A practical guide to building agents (PDF). https://cdn.openai.com/business-guides-and-resources/a-practical-guide-to-building-agents.pdf
3. Anthropic, Forward Deployed Engineer job posting. https://job-boards.greenhouse.io/anthropic/jobs/5302966008
4. Wikipedia, Forward Deployed Engineer. https://en.wikipedia.org/wiki/Forward_Deployed_Engineer
5. Palantir, AIP Bootcamp. https://www.palantir.com/platforms/aip/bootcamp/ (search snippet)
6. Sierra, The Agent Development Life Cycle. https://sierra.ai/blog/agent-development-life-cycle
7. Sierra, Shipping and scaling AI agents. https://sierra.ai/blog/shipping-and-scaling-ai-agents
8. Decagon, Complete AI customer support setup. https://decagon.ai/blog/ai-customer-support-setup
9. Decagon, What is an AI escalation policy? https://decagon.ai/glossary/what-is-an-ai-escalation-policy (search snippet)
10. Salesforce, Best Practices for Secure Agentforce Implementation. https://www.salesforce.com/blog/best-practices-for-secure-agentforce-implementation/
11. Microsoft Learn, Agent development lifecycle. https://learn.microsoft.com/en-us/agents/architecture/deployment-lifecycle
12. Perspective AI, How FDEs run customer discovery (2026). https://getperspective.ai/blog/how-forward-deployed-engineers-run-customer-discovery-2026
13. a16z, Trading Margin for Moat. https://a16z.com/services-led-growth/
14. Microsoft Learn, Dynamics 365 go-live checklist. https://learn.microsoft.com/en-us/dynamics365/guidance/implementation-guide/prepare-go-live-checklist
15. SaaS onboarding/kickoff checklists (search snippets): https://www.valuecase.com/articles/customer-onboarding-checklist ; https://lyniro.com/blog/customer-onboarding-checklist-saas/
16. Intercom, Manage Fin AI Agent's escalation guidance and rules. https://www.intercom.com/help/en/articles/12396892-manage-fin-ai-agent-s-escalation-guidance-and-rules
17. Cloud Security Alliance, What is CAIQ? https://cloudsecurityalliance.org/blog/2021/09/01/what-is-caiq
18. Wolfia, CAIQ v4 questions by domain. https://wolfia.com/blog/we-mapped-all-261-caiq-v4-questions-by-domain (search snippet)
19. Shared Assessments, About the SIG. https://sharedassessments.org/about-sig/ ; summary: https://www.upguard.com/blog/sig-questionnaire (search snippet)
20. PMI, Requirements Management: a core competency (Pulse 2014). https://www.pmi.org/learning/thought-leadership/pulse/core-competency-project-program-success (search snippet)
21. Panorama Consulting, 2026 ERP report press release. https://www.panorama-consulting.com/panorama-consulting-group-releases-latest-study-of-erp-implementation-outcomes-across-the-globe/
22. Salesforce/MuleSoft, 2025 Connectivity Benchmark insights. https://www.salesforce.com/blog/mulesoft-connectivity-benchmark-2025/
23. LangChain, State of Agent Engineering. https://www.langchain.com/state-of-agent-engineering
24. Gartner press release, 2025-06-25. https://www.gartner.com/en/newsroom/press-releases/2025-06-25-gartner-predicts-over-40-percent-of-agentic-ai-projects-will-be-canceled-by-end-of-2027 (search snippet)
25. Wikipedia, Moffatt v. Air Canada. https://en.wikipedia.org/wiki/Moffatt_v._Air_Canada ; ABA: https://www.americanbar.org/groups/business_law/resources/business-law-today/2024-february/bc-tribunal-confirms-companies-remain-liable-information-provided-ai-chatbot/
26. AI Incident Database, Incident 1039 (Cursor). https://incidentdatabase.ai/cite/1039/
27. Entrepreneur, Klarna CEO reverses course. https://www.entrepreneur.com/business-news/klarna-ceo-reverses-course-by-hiring-more-humans-not-ai/491396 (search snippet)
28. TSIA, Streamline your customer onboarding through early evaluation. https://www.tsia.com/blog/streamline-your-customer-onboarding-through-early-evaluation
29. Onboard.io, Days to launch and time to value. https://onboard.io/blog/onboarding-metrics-days-to-launch-time-to-value (search snippet)

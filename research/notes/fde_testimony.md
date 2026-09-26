# FDE testimony: do discovery decisions fit a four-area frame?

Researched 2026-09-26. Frame under test: (1) data inflow, (2) current SOP / policy, (3) who we build for, (4) metrics / acceptance bar.

Evidence conventions:
- **[1P]** first-person practitioner (FDE, deployment strategist, agent engineer, or a named exec describing their own deployments).
- **[Co]** a company or vendor voice (blog, case study). It describes practice but isn't one person's own account.
- **[Rep]** a named practitioner's words as relayed by a journalist or summary.
- **(snippet)**: seen only in a search-result snippet, not verified on the page.
- Quotes marked "via fetch" came through a page-summarizing fetch tool. Treat the wording as close, not guaranteed exact.

Caveat: the first-person, first-weeks testimony I could find is thin and skews Palantir-lineage. AI-agent CX vendors (Sierra, Decagon, Fin, Cresta) mostly publish company voice, not individual FDE diaries. Hacker News FDE threads held almost no practitioner detail (HN 47542553, 47951082, 44361334 checked).

---

## Area 1: Data inflow (exists vs must be built)

- **Nabeel Qureshi, ex-Palantir FDE, 8 yrs [1P]**: data integration means "(a) gaining access to enterprise data...which usually means negotiating with 'data owners'... (b) cleaning it and sometimes transforming it so that it's usable". Also: "you'd have a company buying an 8-12 week pilot, and we'd spend all 8-12 weeks just getting data access, and the final week scrambling to have something to demo." (via fetch) https://nabeelqu.substack.com/p/reflections-on-palantir
- **Vinoo Ganesh, ex-Palantir FDE [1P]**: "I once spent a week at a customer site and noticed that every morning, an analyst spent 45 minutes manually downloading data from three different systems and combining them in Excel... A good FDE would have built what she asked for. I built a pipeline that did her morning routine automatically." He also describes a production crash when bad data with empty date columns was read as the Unix epoch, which generated 2.3M keyspaces. He "spent hours in SCIFs working through data integrations across multiple networks." (via fetch) https://nextplayso.substack.com/p/the-definitive-guide-to-forward-deployed
- **Leo Mehr (Ramp, FDE lead) and Tony Gentilcore (Glean) episodes [Rep, episode page]**: "data access is 'the longest pole in the tent'". The hardest part is "getting it access to data buried across a dozen internal systems, and capturing the tribal knowledge... never written down." https://www.forwardeployed.com/episodes/leo-mehr-ramps-44b-bet-on-services
- **Bret Taylor, Sierra co-founder [1P exec]**: one client "had acquired three companies, and they had three identity systems, three CRM systems, three of everything". The agent reasoned across all three instead of waiting for them to be unified. This is a *take as-is* decision. https://cheekypint.substack.com/p/bret-taylor-of-sierra-on-ai-agents
- **Jesse Zhang, Decagon CEO [1P exec]**: the agent needs "context of the user itself" and "context of the business logic... here are the account details of the user. If you need to fetch more things, you can hit these APIs." https://a16z.com/podcast/can-ai-agents-finally-fix-customer-support/
- **Sierra agent engineers [Co]**: they "understand the relevant policies across regions and interact with the right systems of record." https://sierra.ai/blog/meet-the-ai-agent-engineer
- **Colin Jarvis, OpenAI Head of FDE [Rep, Pragmatic Engineer]**: early steps are "Get data from the customer" and "Prototype with synthetic data". https://newsletter.pragmaticengineer.com/p/forward-deployed-engineers
- **Stanford "Enterprise AI Playbook", 51 deployments, interview-based [1P quotes, anonymized]**: 59% had data "scattered across multiple systems"; only 16% were centralized. "Success did not require centralization. It required access." Other quotes: "Majority of customers don't do a good job maintaining their knowledge bases" (software exec); "OCR was not giving us good results. And the quality of the structured data we were matching to is also not consistent" (AI practice lead). https://digitaleconomy.stanford.edu/app/uploads/2026/03/EnterpriseAIPlaybook_PereiraGraylinBrynjolfsson.pdf

**Build-vs-take (d).** Practitioners describe three recurring "build" items:
1. Access paths and integrations. Access, not cleanliness, is the usual blocker.
2. Pipelines that replace manual assembly (Ganesh).
3. Eval / ground-truth sets that did not exist before:
   - Morgan Stanley: "We created a regression suite of testing, where we picked 500 questions", plus "a whole team of annotators with a rubric". https://scale.com/blog/hitl-ep13-ai-evals-in-practice
   - Jarvis: "Building evals... with user input and labeling".

"Take" items: messy multi-CRM estates (Taylor), and scattered repositories reached through RAG/MCP without centralizing them (Stanford telecom case).

## Area 2: Current SOP / policy, from docs and from shadowing

- **Hooshmand, self-identified FDE [1P]**: "You watch the operation. You ask why someone is doing something. You notice the spreadsheet under the keyboard, the paper checklist taped to a wall, the unofficial WhatsApp group, the queue nobody measures, or the workaround everyone has accepted as normal." Also: "The requirements are incomplete, contradictory, political, human, and frequently not written down at all." https://hooshmand.net/forward-deployed-engineer/
- **Adam Judelson, ex-Palantir [1P]**: "You have to be the user to unlock this concept. I don't mean that spiritually... I mean literally do their same job with your product as an extended member of their team and see what you learn." https://embracingemergence.beehiiv.com/p/what-s-in-a-name-forward-deployed . Also "You don't embed for 20 minutes, either." (snippet)
- **Chris Walker, Palantir 2010-16 [1P, quoted]**: "You observe the workarounds, the informal protocols, the tribal knowledge passed between colleagues. None of this is written down." (second sentence from snippet). Also: "Code is a key output, but it's downstream of something that doesn't exist in any database: an understanding of how work actually gets done." https://www.unregistered.world/p/palantir-forward-deployed-engineers-humanities
- **Nabeel Qureshi [1P]**: "moved out to Toulouse for a year and worked in the factory alongside the manufacturing people four days a week." (link above)
- **Kevin Bai, Anthropic applied AI, ex-Palantir, founding FDE at Rippling [1P]**: "you sit with the people who live the work, from ICs to VPs, and figure out how the business actually runs... find the root problem hiding under the symptoms, which is almost never the one people walk in describing." https://fdepod.substack.com/p/what-it-means-to-be-a-forward-deployed
- **Colin Jarvis [Rep]**: "Sit with users, map out their processes." Also: "An FDE might spend the full day talking with the payments team to understand what specific things are important to them" https://newsletter.eng-leadership.com/p/inside-openais-forward-deployed-engineer
- **Shantanu Kale, Palantir-ecosystem FDE, year 1 [1P]**: "If you need three meetings to clarify a requirement, there's probably an unclear policy driving the confusion." https://www.linkedin.com/posts/shantanu-kale_palantirfoundry-palantir-forwarddeployedengineer-activity-7424911631479930880-9XWu
- **Decagon [Co]**: "Standard Operating Procedures written for humans tend to make a lot of assumptions. They expect the reader to fill in gaps, use judgment... AI... needs explicit instructions for every scenario". https://decagon.ai/blog/from-sops-to-agent-operating-procedures Its onboarding runs a "pre-kickoff audit of your current workflows" and then converts SOPs to AOPs (snippet, third-party summary).
- **Stanford playbook**: "All the hard work is in process documentation and data architecture." "Process Documentation Gaps" slowed 21% of projects. Failed first attempts "applied to broken workflows."

**Shadowing (c): what it reveals that docs don't.** Four things come up: informal artifacts (the spreadsheet, the WhatsApp group), unmeasured queues, workarounds, and the real problem behind the stated request (Ganesh's analyst; Bai's "root problem"). Caveat: explicit shadowing testimony is mostly Palantir-lineage. AI-CX vendors describe SOP conversion and daily conversation review instead ("customer experience teams formally evaluate samples of conversations every single day", https://sierra.ai/blog/agent-development-life-cycle). I found no first-person CX-agent FDE describing sitting beside human support reps.

## Area 3: Who we build for (users, customers, stakeholders)

- **Sarah Khalid, Salesforce FDE Director [1P]**: "We often engage with business stakeholders and executive stakeholders, and they definitely don't understand technical jargon." https://www.salesforce.com/blog/forward-deployed-engineer/
- **Ben Kracker, Salesforce FDE Director [1P]**: "the customer, who does not know what they do not know... peel back the layers of the onion... give them the right solution, as opposed to the solution they're asking for." (same URL)
- **Nabeel Qureshi [1P]**: "The CEO told us his biggest problem was scaling up A350 manufacturing." The build targeted the exec's problem and was delivered through factory users.
- **Kevin Bai [1P]**: "from ICs to VPs" (above).
- **Hooshmand [1P]**: "Explain the whole thing to senior management without making everyone sit through a 100-page deck."
- **Morgan Stanley / Kaitlin Elliott [1P customer-side]**: advisors and annotators graded outputs. End users set the quality bar. Result: "98% adoption among wealth advisors" (OpenAI case via ZenML summary). https://www.zenml.io/llmops-database/forward-deployed-engineering-bringing-enterprise-llm-applications-to-production
- **Stanford playbook**: the acceleration factors are executive sponsorship (43%) and end-user willingness (25%). "Executive sponsorship is about actions, not approval." "Failed... when led by technical teams without business ownership."
- **forwardeployed.com [Co]**: entry criteria are "a workflow that matters, an accountable owner, and systems and data we can reach". https://www.forwardeployed.com/

## Area 4: Metrics / acceptance bar

**(a) Accuracy thresholds.** I found no first-person source naming ~95% as a typical bar. What I did find:
- **Stanford playbook [1P exec]**: "Look guys, 80% is perfect for us... at one point the model is going to be 95%, but we don't care. What we care is immediate cost saving and getting rid of these backlogs." (President, Logistics). Another sponsor "accepted 80% accuracy as good enough". A shipped case reports 85% accuracy. And: "We shifted from 'this is your requirement...' to 'what does good enough look like?'"
- **Kaitlin Elliott, Morgan Stanley [1P, banking]**: "As a financial institution, it's important that what we're doing is accurate. We don't have a lot of room for error." "Many of our governance and control reviews weren't built for generative AI." https://scale.com/blog/hitl-ep13-ai-evals-in-practice
- **Harvey, legal [Co]**: reports ~1 hallucinated claim in 500 (0.2%) on BigLaw Bench, versus 0.7–1.9% for foundation models. https://www.harvey.ai/blog/biglaw-bench-hallucinations
- **Colin Jarvis / OpenAI FDE [Rep]**: "determinism wherever possible". Hard constraints are "checked 100% of the time through deterministic code". (ZenML link above)
- **Russ Salakhutdinov episode [Rep, episode page]**: agents at "60% when you need 99.9%". https://www.forwardeployed.com/episodes

**How regulated industries raise the bar.** Evidence points to more human review and routing, not a higher accuracy number:
- Decagon: "sensitive industries like healthcare, financial services, and legal, where certain cases should always go to a human" (https://www.zenml.io/llmops-database/building-a-production-ai-agent-system-for-customer-support)
- Sierra builds "custom supervisors... in heavily regulated environments like healthcare or financial services"
- Stanford: "physicians must approve every AI generated note because these are legal documents". Regulatory constraints "extend timelines regardless of technical readiness."

**(b) Operational metrics used in agent deployments:**
- Resolution / containment:
  - Taylor: automation of "anywhere between 70-90%"; Ramp "automating 90%".
  - Fin: "average resolution rate across customers... now stands at 76%" (https://www.intercom.com/blog/from-resolutions-to-outcomes-evolving-how-fin-delivers-value/). Customer case studies show 42–50% (snippet).
  - Decagon [Co]: "70-80% deflection rates while maintaining or improving customer satisfaction".
  - Stanford: 82% deflection and 71% resolution in one case; "90 or 95% are now fully automated" (food delivery).
- Cost per resolution:
  - Fin prices at $0.99 per resolution. "Resolutions... gave support teams a clear way to measure ROI, easily comparing the cost of AI versus human support."
  - Human tickets cost "$5–$15 per ticket" (third-party, snippet).
  - Sierra: "if the AI agent resolves the case... there's a pre-negotiated rate... If we do have to escalate to a person, that's free."
- CSAT / NPS: Zhang: "The other metric for us is customer satisfaction". Taylor cites SoFi "improved their net promoter score by 33 points".
- AHT: vendor figures only. Cresta reports United Airlines −15% AHT and Sunbit −10% AHT with 50% containment (snippet). https://cresta.com/customer-stories
- Latency, throughput, cost: Baseten FDE [1P]: customers must "hit their requirements for latency, throughput, and cost". https://www.baseten.co/blog/what-i-learned-as-a-forward-deployed-engineer-working-at-an-ai-startup/ Stanford: a gateway to "solve for cost, accuracy, relevance, latency based on the query."

---

## Decided in discovery but outside the four areas

1. **Security, access, and data governance.** Data-owner negotiation (Qureshi). SCIF work (Ganesh). A bank sends "a minimum scrubbed set... We swap in fake names, a fake dollar amount" (Stanford). Governance reviews "weren't built for generative AI" (Elliott). Salesforce: "customer data, processes, and permissions are where deployments tend to fail" (snippet, Apex Hours/Salesforce).
2. **Problem selection, scope, and value.** Jarvis: "Identify the biggest value areas". "Generalizing too early" was the biggest mistake. forwardeployed.com: "One named operating workflow" by day 30. Decagon picks "high volume and repetitive" procedures and skips those needing "emotional intelligence".
3. **Autonomy / escalation design (HITL level).** Stanford: escalation vs approval vs collaboration, by function. Decagon: which cases "always go to a human".
4. **Eval construction and ownership.** Who labels, and what rubric. Jarvis; Morgan Stanley's 500-question suite. Arguably part of area 4, but it is a build task with its own owners.
5. **Rollout, go-live, and handover.** Decagon's phased A/B traffic ramp (snippet). forwardeployed.com: engagement ends when "your team operates the result on its own". Morgan Stanley: a 6–8 week build, then "an additional 4 months of pilots".
6. **Change management / workforce adoption.** Stanford: 77% of the hardest challenges were "invisible costs" (change management, data quality, process redesign). "Technology wasn't the bottleneck - organizational adoption was the failure point."

## Where reversals / rework happen

- **The stated problem gets replaced by the real one.** Ganesh (pipeline instead of the ask), Kracker, Bai ("almost never the one people walk in describing").
- **Data access eats the timeline.** Qureshi's 8–12 weeks, with a final-week demo scramble.
- **Bad or unexpected data breaks assumptions in production.** Ganesh's epoch/keyspace crash.
- **The accuracy bar is renegotiated downward to "good enough" plus HITL.** Stanford: "We shifted from 'this is your requirement'... to 'what does good enough look like?'"
- **Requirements churn from unclear policy.** Kale: three meetings means an unclear policy. Also: "Your first solution is usually over-engineered."
- **Whole-project restarts.** Stanford: 61% had a failed AI project before the current success. Failures came from "broken workflows", "technical teams without business ownership", and "assumed the model would fix problems that required redesigning the work itself".
- **Pilot to production.** Salesforce: "thousands of customers stuck in pilot purgatory" (Khalid). Early customers "asked for more ways to measure their agents' performance", so the metrics had to be added after deployment (snippet).

## Fit verdict

| Area | Verdict | Independent testimonies |
| --- | --- | --- |
| 1 Data inflow | **Strongly supported.** Access, not cleanliness, is the dominant sub-issue. | ~8 (Qureshi, Ganesh, Mehr/Gentilcore ep., Taylor, Zhang, Jarvis, Stanford, Morgan Stanley) |
| 2 SOP/policy + shadowing | **Strongly supported.** Shadowing is mostly Palantir-lineage; CX-agent vendors do SOP conversion plus transcript review. | ~10 (Hooshmand, Judelson, Walker, Qureshi, Ganesh, Bai, Jarvis, Kale, Decagon, Stanford) |
| 3 Who we build for | **Strongly supported for user vs exec sponsor. Partly for the "approver / ops owner" split.** Sources name sponsor and users; approvers show up as compliance/governance, not as a named role. | ~7 (Khalid, Kracker, Qureshi, Bai, Hooshmand, Elliott, Stanford) |
| 4 Metrics / bar | **Area strongly supported. The "~95% typical" figure is weakly supported or contradicted.** Bars run 80–85% with HITL in ops use cases. Regulated industries raise the bar mainly through mandatory human approval, deterministic checks, and governance. AHT has vendor-only evidence. | ~9 (Stanford x2 execs, Elliott, Harvey, Jarvis, Taylor, Zhang, Fin, Baseten) |

## Missing areas practitioners raise

1. Security/access/governance, as its own track.
2. Problem/value selection and scope.
3. Autonomy/escalation (HITL) design.
4. Eval-set construction and labeling ownership.
5. Rollout, go-live, and handover to an operating owner.
6. Change management and adoption.

## Sources

- https://nabeelqu.substack.com/p/reflections-on-palantir
- https://nextplayso.substack.com/p/the-definitive-guide-to-forward-deployed
- https://hooshmand.net/forward-deployed-engineer/
- https://embracingemergence.beehiiv.com/p/what-s-in-a-name-forward-deployed
- https://www.unregistered.world/p/palantir-forward-deployed-engineers-humanities
- https://fdepod.substack.com/p/what-it-means-to-be-a-forward-deployed
- https://www.linkedin.com/posts/shantanu-kale_palantirfoundry-palantir-forwarddeployedengineer-activity-7424911631479930880-9XWu
- https://www.salesforce.com/blog/forward-deployed-engineer/
- https://newsletter.pragmaticengineer.com/p/forward-deployed-engineers
- https://newsletter.eng-leadership.com/p/inside-openais-forward-deployed-engineer
- https://www.zenml.io/llmops-database/forward-deployed-engineering-bringing-enterprise-llm-applications-to-production
- https://scale.com/blog/hitl-ep13-ai-evals-in-practice
- https://cheekypint.substack.com/p/bret-taylor-of-sierra-on-ai-agents
- https://a16z.com/podcast/can-ai-agents-finally-fix-customer-support/
- https://sierra.ai/blog/meet-the-ai-agent-engineer
- https://sierra.ai/blog/agent-development-life-cycle
- https://decagon.ai/blog/from-sops-to-agent-operating-procedures
- https://www.zenml.io/llmops-database/building-a-production-ai-agent-system-for-customer-support
- https://www.intercom.com/blog/from-resolutions-to-outcomes-evolving-how-fin-delivers-value/
- https://www.harvey.ai/blog/biglaw-bench-hallucinations
- https://cresta.com/customer-stories (snippet figures)
- https://www.baseten.co/blog/what-i-learned-as-a-forward-deployed-engineer-working-at-an-ai-startup/
- https://www.forwardeployed.com/ and https://www.forwardeployed.com/episodes
- https://digitaleconomy.stanford.edu/app/uploads/2026/03/EnterpriseAIPlaybook_PereiraGraylinBrynjolfsson.pdf (Stanford DEL, Apr 2026; some pages marked DRAFT)

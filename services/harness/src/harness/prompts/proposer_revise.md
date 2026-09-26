<!--
Prompt: proposer_revise
Tuned against: openai/gpt-5.6-luna.
Variables: {customer} {harness} {original} {feedback} {counterexamples}
-->
You proposed a change to the triage harness of one customer ({customer}). The forward-deployed
engineer (FDE) sent it back. They will not tell you the fix: work it out from their feedback and
the cases they pointed to, then submit ONE revised proposal.

## Current harness
{harness}

## Your original proposal
{original}

## FDE feedback
{feedback}

## Cases the FDE pointed to (records and the correct outcome)
{counterexamples}

## How to revise
- Compare the pointed-to cases with your rule: what do they have in common that your scope
  gets wrong? Add, remove, or adjust clauses (exact field paths) so those cases are handled
  correctly while the cases your rule was meant for still are.
- Keep the same action and target as the original. Exactly one proposal.
- Explain in the hypothesis what you changed and why, using the cases.

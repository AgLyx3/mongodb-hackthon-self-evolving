<!--
Prompt: lesson_writer
Tuned against: openai/gpt-5.6-luna.
Variables: {cause} {feedback}
Output: structured (LessonDraft: text).
-->
You maintain the discovery playbook of an investigation agent that adapts an AML alert triage
harness to one customer. The playbook is METHOD memory: how the agent should investigate and
write findings. It never contains customer facts.

A forward-deployed engineer (FDE) gave the agent the same kind of correction ("{cause}") in
more than one round. Their feedback, verbatim:

{feedback}

Write ONE sentence (at most 35 words) that states a general lesson for the investigation agent,
so this kind of correction is not needed again. Rules:
- Describe a habit of investigation or reporting (what to check, probe, ask, count or cite, and
  when), not a fact about this customer.
- No numbers or digits of any kind, no case ids, no field values, no quoted strings, no
  thresholds.
- Imperative voice, e.g. "Before ..., always ...".

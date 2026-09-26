"""The shared base harness every customer starts from (frozen while customers evolve).

Generic AML triage policy written in customer-neutral terms. Customer field
names differ; the runtime agent maps concepts to fields using the onboarding
field glossary.
"""

from harness.core.units import Unit


def base_units() -> list[Unit]:
    return [
        Unit(unit_id="anchor.output", kind="rule", layer="anchor", title="Output contract",
             text="Choose exactly one disposition: close_false_positive, request_info, or "
                  "escalate. List the ids of every harness section you relied on in "
                  "applied_unit_ids. Decide only from this case's records and this harness."),
        Unit(unit_id="anchor.kyc_first", kind="rule", layer="anchor",
             title="Incomplete due diligence comes first",
             text="If the customer's KYC / due-diligence status is incomplete or unverified, "
                  "the disposition is request_info, regardless of any other rule.",
             disposition="request_info"),
        Unit(unit_id="base.large_amount", kind="rule", layer="truth",
             title="Large single transaction",
             text="If the flagged transaction amount is $10,000 or more, escalate.",
             disposition="escalate"),
        Unit(unit_id="base.high_risk_geo", kind="rule", layer="truth",
             title="High-risk jurisdiction",
             text="If the counterparty is in a high-risk jurisdiction, escalate.",
             disposition="escalate"),
        Unit(unit_id="base.structuring", kind="rule", layer="truth", title="Structuring",
             text="If the alert is a structuring alert (several payments just below a "
                  "reporting threshold), escalate.",
             disposition="escalate"),
        Unit(unit_id="base.default_close", kind="rule", layer="truth", title="Default",
             text="If no rule above or in the customer-specific section applies, close as "
                  "close_false_positive.",
             disposition="close_false_positive"),
    ]

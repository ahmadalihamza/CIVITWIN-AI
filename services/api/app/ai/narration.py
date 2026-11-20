"""Select prewritten evidence claims through an optional structured provider."""

from typing import Annotated, Literal

from pydantic import Field

from app.ai.evidence import Claim, Explanation
from app.ai.provider import JsonProvider, ProviderError
from app.domain.dataset import canonical_json
from app.schemas.dataset import Contract

PresetId = Literal["coverage", "demand", "equity", "cost"]

# Each sentence has an exact evidence contract. Only the application inserts values.
PRESETS: dict[PresetId, tuple[tuple[str, ...], str]] = {
    "coverage": (
        ("metric.covered_visits", "metric.total_demand", "metric.coverage_pct"),
        "Within-threshold service covers {0:,} of {1:,} requested visits ({2:.1f}%).",
    ),
    "demand": (
        ("metric.served_visits", "metric.unmet_visits"),
        "The model assigns {0:,} weekly visits and leaves {1:,} requests unserved.",
    ),
    "equity": (
        ("metric.worst_cluster_id", "metric.worst_cluster_coverage_pct"),
        "Cluster {0} has the lowest within-threshold coverage at {1:.1f}%.",
    ),
    "cost": (
        ("metric.cost_pkr", "metric.budget_pkr"),
        "The selected sites cost an additional PKR {0:,} per modeled week within a PKR {1:,} budget.",
    ),
}

SYSTEM_PROMPT = (
    "Choose an order for these four verified synthetic planning claims. Return each preset "
    "exactly once with the evidence IDs provided for that preset, in their listed order. "
    "Return structured JSON only. The application writes the prose and inserts result values."
)


class ClaimChoice(Contract):
    preset: PresetId
    evidence_ids: Annotated[tuple[str, ...], Field(min_length=2, max_length=3)]


class NarrationChoices(Contract):
    claims: Annotated[tuple[ClaimChoice, ...], Field(min_length=4, max_length=4)]


def narrate(explanation: Explanation, provider: JsonProvider | None) -> Explanation:
    """Reorder preset claims using provider instructions or return the offline template."""
    packet = explanation.packet
    if provider is None or explanation.mode != "template" or not packet.is_synthetic:
        return explanation

    by_id = {metric.id: metric.value for metric in packet.metrics}
    choices = [
        {"preset": preset, "evidence_ids": list(evidence_ids)}
        for preset, (evidence_ids, _) in PRESETS.items()
    ]
    used_evidence = {key for keys, _ in PRESETS.values() for key in keys}
    # Keep imported labels, identifiers and assumptions out of model inputs.
    grounded = {
        row.id: {"value": row.value, "unit": row.unit}
        for row in packet.metrics
        if row.id in used_evidence and isinstance(row.value, (int, float))
    }
    try:
        response = provider.generate(
            SYSTEM_PROMPT,
            {
                "language": explanation.language,
                "solver_status": packet.solver_status,
                "audit_passed": packet.audit_passed,
                "presets": choices,
                "metrics": grounded,
            },
            NarrationChoices.model_json_schema(),
        )
        ordered = NarrationChoices.model_validate_json(canonical_json(response)).claims
        if {choice.preset for choice in ordered} != PRESETS.keys():
            return explanation
        claims = []
        for choice in ordered:
            keys, template = PRESETS[choice.preset]
            if choice.evidence_ids != keys:
                return explanation
            claims.append(
                Claim(text=template.format(*(by_id[key] for key in keys)), evidence_ids=keys)
            )
        return Explanation(
            mode="provider", language=explanation.language, packet=packet, claims=tuple(claims)
        )
    except (ProviderError, TimeoutError, ValueError, TypeError, KeyError):
        return explanation

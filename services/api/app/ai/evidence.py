"""Turn a verified planning snapshot into an immutable evidence packet."""

from hashlib import sha256
from typing import Any, Literal

from pydantic import TypeAdapter

from app.domain.dataset import canonical_json
from app.domain.optimizer import Result
from app.schemas.dataset import Contract, Digest, Identifier
from app.schemas.plan import PlanSpec

METRIC_FIELDS = (
    ("total_demand", "Total demand", "visits/week"),
    ("served_visits", "Served visits", "visits/week"),
    ("unmet_visits", "Unmet visits", "visits/week"),
    ("covered_visits", "Within-threshold visits", "visits/week"),
    ("visit_minutes", "Assigned travel", "visit-minutes/week"),
    ("served_rate_pct", "Served rate", "%"),
    ("unmet_rate_pct", "Unmet rate", "%"),
    ("coverage_pct", "Within-threshold coverage", "%"),
    ("mean_assigned_travel_minutes", "Mean assigned travel", "minutes"),
    ("worst_cluster_id", "Worst-served cluster", "cluster ID"),
    ("worst_cluster_coverage_pct", "Worst-served cluster coverage", "%"),
    ("equity_gap_pp", "Gap between highest and lowest cluster coverage", "percentage points"),
    ("cost_pkr", "Weekly-equivalent additional cost", "PKR/week"),
    ("budget_pkr", "Weekly-equivalent budget", "PKR/week"),
    ("budget_utilization_pct", "Budget utilization", "%"),
)


class EvidenceMetric(Contract):
    id: str
    path: str
    label: str
    value: int | float | str | None
    unit: str


class EvidencePacket(Contract):
    run_id: Identifier
    dataset_sha256: Digest
    plan_hash: Digest
    model_version: str
    solver_status: Literal["OPTIMAL", "FEASIBLE"]
    audit_passed: Literal[True] = True
    audit_result_hash: Digest
    dataset_label: str
    is_synthetic: bool
    assumptions: tuple[str, ...]
    plan: PlanSpec
    metrics: tuple[EvidenceMetric, ...]


class Claim(Contract):
    text: str
    evidence_ids: tuple[str, ...]


class Explanation(Contract):
    mode: Literal["template", "provider"] = "template"
    language: Literal["en"] = "en"
    packet: EvidencePacket
    claims: tuple[Claim, ...]


_ASSUMPTIONS = TypeAdapter(tuple[str, ...])


def _packet(
    snapshot: dict[str, Any],
    plan_data: dict[str, Any],
    dataset: dict[str, Any],
) -> EvidencePacket:
    if snapshot.get("status") != "COMPLETED":
        raise ValueError("The evidence packet requires a completed audited result.")
    core = {
        key: value
        for key, value in snapshot.items()
        if key not in {"run_id", "scenario_id", "status"}
    }
    result = Result.model_validate_json(canonical_json(core))
    plan = PlanSpec.model_validate(plan_data)
    audited = {
        field: core[field]
        for field in ("selected_candidate_ids", "assignments", "unmet_by_community", "metrics")
    }
    digest = sha256(canonical_json(audited)).hexdigest()
    if (
        not result.audit.passed
        or not result.audit.checks
        or not all(check.passed for check in result.audit.checks)
        or result.audit.result_hash != digest
        or result.plan_hash != plan.plan_hash
        or result.dataset_sha256 != dataset.get("sha256")
        or plan.dataset_version_id != dataset.get("id")
    ):
        raise ValueError("The evidence inputs do not match the audited allocation and plan.")

    metrics = result.metrics.model_dump(mode="json")
    return EvidencePacket(
        run_id=snapshot["run_id"],
        dataset_sha256=result.dataset_sha256,
        plan_hash=result.plan_hash,
        model_version=result.model_version,
        solver_status=result.solver_status,
        audit_result_hash=digest,
        dataset_label=dataset["district_label"],
        is_synthetic=dataset["is_synthetic"],
        assumptions=_ASSUMPTIONS.validate_python(dataset["assumptions"]),
        plan=plan,
        metrics=tuple(
            EvidenceMetric(
                id=f"metric.{field}",
                path=f"result.metrics.{field}",
                label=label,
                value=metrics[field],
                unit=unit,
            )
            for field, label, unit in METRIC_FIELDS
        ),
    )


def explain(result: dict[str, Any], plan: dict[str, Any], dataset: dict[str, Any]) -> Explanation:
    packet = _packet(result, plan, dataset)
    evidence = {metric.id: metric.value for metric in packet.metrics}

    def count(field: str) -> str:
        value = evidence[f"metric.{field}"]
        assert isinstance(value, int)
        return f"{value:,}"

    def percent(field: str) -> str:
        value = evidence[f"metric.{field}"]
        assert isinstance(value, float)
        return f"{value:.1f}%"

    claims = (
        Claim(
            text=(
                f"{count('covered_visits')} of {count('total_demand')} modeled visits are "
                f"assigned within the confirmed threshold ({percent('coverage_pct')})."
            ),
            evidence_ids=("metric.covered_visits", "metric.total_demand", "metric.coverage_pct"),
        ),
        Claim(
            text=(
                f"The allocation serves {count('served_visits')} visits and leaves "
                f"{count('unmet_visits')} modeled visits unmet in the week."
            ),
            evidence_ids=("metric.served_visits", "metric.unmet_visits"),
        ),
        Claim(
            text=(
                f"The worst-served cluster is {evidence['metric.worst_cluster_id']}, with "
                f"{percent('worst_cluster_coverage_pct')} of demand within the threshold."
            ),
            evidence_ids=("metric.worst_cluster_id", "metric.worst_cluster_coverage_pct"),
        ),
        Claim(
            text=(
                f"The additional weekly-equivalent cost is PKR {count('cost_pkr')} "
                f"against the confirmed budget of PKR {count('budget_pkr')}."
            ),
            evidence_ids=("metric.cost_pkr", "metric.budget_pkr"),
        ),
    )
    return Explanation(packet=packet, claims=claims)

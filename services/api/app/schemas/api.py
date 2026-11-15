from typing import Annotated, Literal

from pydantic import StringConstraints

from app.schemas.dataset import Contract, Digest, Identifier

JobKey = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")]


class Confirmation(Contract):
    plan_hash: Digest


class RunRequest(Contract):
    kind: Literal["baseline", "optimized"]


class ComparisonRequest(Contract):
    baseline_run_id: Identifier
    alternative_run_id: Identifier

import json
import logging
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from threading import BoundedSemaphore
from typing import Annotated, Any, Literal
from uuid import uuid4

from fastapi import APIRouter, FastAPI, Header, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import ValidationError
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.ai.evidence import explain
from app.ai.narration import narrate
from app.ai.parser import ParseRequest, ParseResponse, parse_plan
from app.ai.provider import HttpJsonProvider
from app.config import Settings
from app.db.models import DatasetVersion, Run, Scenario, StressRun
from app.db.store import (
    DatasetConflict,
    Store,
    append_event,
    load_version,
    persist_dataset,
    utc_now,
)
from app.domain.comparison import compare_metrics
from app.domain.dataset import MAX_UPLOAD_BYTES, dataset_payload
from app.domain.dataset_import import load_import
from app.domain.optimizer import SOLVER_VERSION
from app.domain.results import Metrics
from app.domain.travel import travel_matrix
from app.errors import ApiError
from app.schemas.api import ComparisonRequest, Confirmation, JobKey, RunRequest, StressRequest
from app.schemas.plan import PlanSpec
from app.workflows.export import export_csv, export_document
from app.workflows.jobs import JobError, JobManager

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1")


def _store(request: Request) -> Store:
    return request.app.state.store


def _jobs(request: Request) -> JobManager:
    return request.app.state.jobs


def _fail(
    request: Request, status: int, code: str, message: str, fields: list[Any]
) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={
            "code": code,
            "message": message,
            "field_errors": fields,
            "request_id": getattr(request.state, "request_id", None),
        },
    )


def _safe_errors(errors: Sequence[Any]) -> list[dict[str, Any]]:
    return [
        {"field": list(error["loc"]), "code": error["type"], "message": error["msg"]}
        for error in errors
    ]


def _published(run: Run | None) -> dict[str, Any]:
    if run is None:
        raise ApiError(404, "RUN_NOT_FOUND", "The run was not found.")
    if (
        run.status != "COMPLETED"
        or run.result_json is None
        or not run.result_json.get("audit", {}).get("passed")
    ):
        raise ApiError(409, "RUN_NOT_AUDITED", "This run has no completed audited allocation.")
    return run.result_json


def _scenario_view(row: Scenario) -> dict[str, Any]:
    return {
        "scenario_id": row.id,
        "plan": row.plan_json,
        "plan_hash": row.plan_hash,
        "status": row.status,
        "created_at": row.created_at,
        "confirmed_at": row.confirmed_at,
    }


def _run_view(row: Run) -> dict[str, Any]:
    view = {
        "run_id": row.id,
        "scenario_id": row.scenario_id,
        "kind": row.kind,
        "status": row.status,
        "progress_stage": row.progress_stage,
        "solver_status": row.solver_status,
        "runtime_ms": row.runtime_ms,
        "created_at": row.created_at,
        "started_at": row.started_at,
        "completed_at": row.completed_at,
        "updated_at": row.updated_at,
    }
    if row.status == "COMPLETED":
        return {**view, "result": _published(row)}
    if row.error_json:
        return {**view, "error": row.error_json}
    return view


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
def ready(request: Request) -> dict[str, Any]:
    with _store(request).sessions() as session:
        dataset_id = session.scalar(select(DatasetVersion.id).limit(1))
    if dataset_id is None:
        raise ApiError(503, "NO_DATASET", "Publish an approved aggregate dataset to begin.")
    return {
        "status": "ready",
        "solver_version": SOLVER_VERSION,
        "ai_enabled": request.app.state.provider is not None,
    }


@router.get("/datasets")
def datasets(request: Request) -> list[dict[str, Any]]:
    with _store(request).sessions() as session:
        rows = session.scalars(select(DatasetVersion).order_by(DatasetVersion.id)).all()
        return [row.manifest_json for row in rows]


@router.get("/datasets/{dataset_id}")
def dataset_detail(dataset_id: str, request: Request) -> dict[str, Any]:
    with _store(request).sessions() as session:
        row = session.get(DatasetVersion, dataset_id)
        if row is None:
            raise ApiError(404, "DATASET_NOT_FOUND", "The dataset version was not found.")
        dataset = load_version(row)
        matrix = travel_matrix(dataset)
        result = dataset_payload(dataset)
        result["reachable_pair_count"] = len(matrix)
        result["unreachable_pair_count"] = len(dataset.communities) * len(dataset.sites) - len(
            matrix
        )
        return result


@router.post("/datasets/import", status_code=201)
async def import_dataset(request: Request) -> dict[str, Any]:
    settings: Settings = request.app.state.settings
    client = request.client
    if not settings.demo_mode or client is None or client.host not in {"127.0.0.1", "::1"}:
        raise ApiError(403, "LOCAL_STEWARD_ONLY", "Dataset import requires a local demo session.")
    if request.headers.get("content-type", "").split(";")[0].strip().lower() != "application/json":
        raise ApiError(
            400, "IMPORT_CONTENT_TYPE", "Upload a JSON dataset or JSON-wrapped CSV bundle."
        )
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > MAX_UPLOAD_BYTES:
            raise ApiError(422, "IMPORT_SIZE", "The bundle exceeds 2 MB.")
        body.extend(chunk)
    try:
        dataset = load_import(bytes(body))
    except ValidationError as exc:
        raise ApiError(
            422, "INVALID_DATASET", "Check the dataset rows.", _safe_errors(exc.errors())
        )
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise ApiError(
            400, "MALFORMED_JSON", "The dataset bundle is not valid UTF-8 JSON."
        ) from exc
    except ValueError as exc:
        raise ApiError(422, "INVALID_DATASET", str(exc)) from exc
    if not dataset.is_synthetic:
        raise ApiError(
            422, "DEMO_SYNTHETIC_ONLY", "The local demonstration accepts synthetic data."
        )
    try:
        with _store(request).sessions.begin() as session:
            row = persist_dataset(session, dataset)
            manifest = row.manifest_json
    except (DatasetConflict, IntegrityError) as exc:
        raise ApiError(409, "DATASET_CONFLICT", "An immutable dataset version conflicts.") from exc
    return manifest


@router.post("/scenarios", status_code=201)
def create_scenario(plan: PlanSpec, request: Request) -> dict[str, Any]:
    with _store(request).sessions.begin() as session:
        dataset = session.get(DatasetVersion, plan.dataset_version_id)
        if dataset is None:
            raise ApiError(422, "UNKNOWN_DATASET", "Select a published dataset version.")
        try:
            plan.validate_for(load_version(dataset))
        except ValueError as exc:
            raise ApiError(422, "INVALID_PLAN", str(exc)) from exc
        scenario = Scenario(
            id=f"scenario-{uuid4().hex}",
            dataset_id=dataset.id,
            plan_json=plan.model_dump(mode="json"),
            plan_hash=plan.plan_hash,
            status="VALIDATED",
            created_at=utc_now(),
        )
        session.add(scenario)
        append_event(session, "scenario", scenario.id, "VALIDATED", {"plan_hash": plan.plan_hash})
        return _scenario_view(scenario)


@router.post("/plans/parse")
def parse_draft(body: ParseRequest, request: Request) -> ParseResponse:
    with _store(request).sessions() as session:
        version = session.get(DatasetVersion, body.dataset_version_id)
        if version is None:
            raise ApiError(422, "UNKNOWN_DATASET", "Select a published dataset version.")
        dataset = load_version(version)
    slot: BoundedSemaphore = request.app.state.provider_slot
    if not slot.acquire(blocking=False):
        raise ApiError(429, "AI_BUSY", "The optional provider is handling another request.")
    try:
        return parse_plan(body, dataset, request.app.state.provider)
    finally:
        slot.release()


@router.get("/scenarios/{scenario_id}")
def get_scenario(scenario_id: str, request: Request) -> dict[str, Any]:
    with _store(request).sessions() as session:
        scenario = session.get(Scenario, scenario_id)
        if scenario is None:
            raise ApiError(404, "SCENARIO_NOT_FOUND", "The scenario was not found.")
        return _scenario_view(scenario)


@router.post("/scenarios/{scenario_id}/confirm")
def confirm_scenario(scenario_id: str, body: Confirmation, request: Request) -> dict[str, Any]:
    with _store(request).sessions.begin() as session:
        scenario = session.get(Scenario, scenario_id)
        if scenario is None:
            raise ApiError(404, "SCENARIO_NOT_FOUND", "The scenario was not found.")
        if scenario.plan_hash != body.plan_hash:
            raise ApiError(409, "PLAN_HASH_MISMATCH", "Review and confirm the current plan hash.")
        confirmed_at = utc_now()
        changed = session.execute(
            update(Scenario)
            .where(Scenario.id == scenario_id, Scenario.status == "VALIDATED")
            .values(status="CONFIRMED", confirmed_at=confirmed_at)
        )
        if getattr(changed, "rowcount", 0):
            append_event(
                session, "scenario", scenario_id, "CONFIRMED", {"plan_hash": body.plan_hash}
            )
        session.refresh(scenario)
        return _scenario_view(scenario)


@router.post("/scenarios/{scenario_id}/runs", status_code=202)
def submit_run(
    scenario_id: str,
    body: RunRequest,
    request: Request,
    idempotency_key: Annotated[JobKey | None, Header()] = None,
) -> dict[str, str]:
    return {"run_id": _jobs(request).submit(scenario_id, body.kind, idempotency_key)}


@router.get("/runs")
def list_runs(request: Request) -> list[dict[str, Any]]:
    with _store(request).sessions() as session:
        rows = session.scalars(select(Run).order_by(Run.created_at.desc(), Run.id).limit(30)).all()
        return [
            {key: value for key, value in _run_view(row).items() if key != "result"} for row in rows
        ]


@router.get("/runs/{run_id}")
def get_run(run_id: str, request: Request) -> dict[str, Any]:
    with _store(request).sessions() as session:
        row = session.get(Run, run_id)
        if row is None:
            raise ApiError(404, "RUN_NOT_FOUND", "The run was not found.")
        return _run_view(row)


@router.post("/runs/{run_id}/cancel")
def cancel_run(run_id: str, request: Request) -> dict[str, Any]:
    _jobs(request).cancel(run_id)
    return get_run(run_id, request)


@router.post("/comparisons")
def comparison(body: ComparisonRequest, request: Request) -> dict[str, Any]:
    with _store(request).sessions() as session:
        base = _published(session.get(Run, body.baseline_run_id))
        alt = _published(session.get(Run, body.alternative_run_id))
        if base["dataset_sha256"] != alt["dataset_sha256"] or base["plan_hash"] != alt["plan_hash"]:
            raise ApiError(
                409, "INCOMPATIBLE_COMPARISON", "Compare runs with the same dataset and plan hash."
            )
        if base["kind"] != "baseline" or alt["kind"] == "baseline":
            raise ApiError(422, "INVALID_RUN_KINDS", "Choose one baseline and one alternative run.")
        scenario = session.get(Scenario, base["scenario_id"])
        assert scenario is not None
        return {
            "baseline": base,
            "alternative": alt,
            "plan": scenario.plan_json,
            "deltas": compare_metrics(
                Metrics.model_validate_json(json.dumps(base["metrics"])),
                Metrics.model_validate_json(json.dumps(alt["metrics"])),
            ),
        }


@router.get("/runs/{run_id}/export")
def download(run_id: str, request: Request, format: Literal["json", "csv"] = "json") -> Response:
    with _store(request).sessions() as session:
        result = _published(session.get(Run, run_id))
        scenario = session.get(Scenario, result["scenario_id"])
        assert scenario is not None
        dataset = session.get(DatasetVersion, scenario.dataset_id)
        assert dataset is not None
        document = export_document(result, scenario.plan_json, dataset.payload_json)
    headers = {"Content-Disposition": f'attachment; filename="civitwin-{run_id}.{format}"'}
    if format == "csv":
        return Response(export_csv(document), media_type="text/csv", headers=headers)
    return JSONResponse(document, headers=headers)


@router.get("/runs/{run_id}/explanation")
def explanation(run_id: str, request: Request) -> dict[str, Any]:
    return _explain(run_id, request, use_provider=False)


@router.post("/runs/{run_id}/explanation")
def provider_explanation(run_id: str, request: Request) -> dict[str, Any]:
    return _explain(run_id, request, use_provider=True)


def _explain(run_id: str, request: Request, *, use_provider: bool) -> dict[str, Any]:
    with _store(request).sessions() as session:
        result = _published(session.get(Run, run_id))
        scenario = session.get(Scenario, result["scenario_id"])
        assert scenario is not None
        dataset = session.get(DatasetVersion, scenario.dataset_id)
        assert dataset is not None
        generated = explain(result, scenario.plan_json, dataset.manifest_json)
    slot: BoundedSemaphore = request.app.state.provider_slot
    if use_provider and slot.acquire(blocking=False):
        try:
            generated = narrate(generated, request.app.state.provider)
        finally:
            slot.release()
    return generated.model_dump(mode="json")


@router.post("/stress-runs", status_code=202)
def submit_stress(
    body: StressRequest,
    request: Request,
    idempotency_key: Annotated[JobKey | None, Header()] = None,
) -> dict[str, str]:
    return {"stress_run_id": _jobs(request).submit_stress(body, idempotency_key)}


@router.get("/stress-runs/{run_id}")
def get_stress(run_id: str, request: Request) -> dict[str, Any]:
    with _store(request).sessions() as session:
        row = session.get(StressRun, run_id)
        if row is None:
            raise ApiError(404, "STRESS_RUN_NOT_FOUND", "The stress run was not found.")
        view = {
            "stress_run_id": row.id,
            "baseline_run_id": row.baseline_run_id,
            "alternative_run_id": row.alternative_run_id,
            "seed": row.seed,
            "case_count": row.case_count,
            "status": row.status,
            "progress_stage": row.progress_stage,
            "runtime_ms": row.runtime_ms,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }
        if row.results_json is not None:
            view["results"] = row.results_json
        if row.error_json:
            view["error"] = row.error_json
        return view


def create_app(settings: Settings | None = None) -> FastAPI:
    configuration = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        store = Store(configuration)
        try:
            store.prepare()
            jobs = JobManager(
                store, configuration.solver_timeout_seconds, configuration.stress_timeout_seconds
            )
            application.state.store = store
            application.state.jobs = jobs
            try:
                yield
            finally:
                jobs.close()
        finally:
            store.close()

    application = FastAPI(title="CIVITWIN AI", version="1.0", lifespan=lifespan)
    application.state.settings = configuration
    application.state.provider_slot = BoundedSemaphore(1)
    application.state.provider = None
    if configuration.provider_configured:
        try:
            application.state.provider = HttpJsonProvider(
                configuration.llm_endpoint, configuration.llm_model, configuration.llm_api_key
            )
        except ValueError:
            log.warning(
                "Optional provider configuration is invalid. Offline planning remains available."
            )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[configuration.allowed_origin],
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "Idempotency-Key"],
        expose_headers=["Content-Disposition", "X-Request-ID"],
    )
    application.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["localhost", "127.0.0.1", "[::1]", "testserver", "api"],
    )

    @application.middleware("http")
    async def request_id(request: Request, call_next: Any) -> Response:
        request.state.request_id = uuid4().hex
        try:
            origin = request.headers.get("origin")
            trusted_origins = {configuration.allowed_origin}
            if not configuration.web_origin:
                trusted_origins.add(f"http://127.0.0.1:{configuration.web_port}")
            if request.method == "POST" and origin is not None and origin not in trusted_origins:
                response = _fail(
                    request, 403, "UNTRUSTED_ORIGIN", "Use the local planning workspace.", []
                )
            else:
                response = await call_next(request)
        except Exception as exc:
            log.error(
                "request_failed request_id=%s error_type=%s",
                request.state.request_id,
                type(exc).__name__,
            )
            response = _fail(
                request, 500, "INTERNAL_ERROR", "The request could not be completed.", []
            )
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    @application.exception_handler(ApiError)
    async def api_error(request: Request, exc: ApiError) -> JSONResponse:
        return _fail(request, exc.status_code, exc.code, exc.message, exc.field_errors)

    @application.exception_handler(JobError)
    async def job_error(request: Request, exc: JobError) -> JSONResponse:
        return _fail(request, exc.status_code, exc.code, exc.message, [])

    @application.exception_handler(RequestValidationError)
    async def request_validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = exc.errors()
        if any(error["type"] == "json_invalid" for error in errors):
            return _fail(request, 400, "MALFORMED_JSON", "Supply a valid JSON request body.", [])
        return _fail(
            request, 422, "INVALID_REQUEST", "Check the submitted fields.", _safe_errors(errors)
        )

    @application.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException) -> JSONResponse:
        return _fail(request, exc.status_code, "HTTP_ERROR", str(exc.detail), [])

    application.include_router(router)
    return application


app = create_app()

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from app.api.dependencies import get_experimental_answer_service
from app.schemas.experiments import (
    ExperimentAdminVerifyRequest,
    ExperimentAdminVerifyResponse,
    ExperimentCompareRequest,
    ExperimentDeleteSessionResponse,
    ExperimentalAnswerRequest,
)
from app.services.experimental_answer_service import ExperimentalAnswerError, ExperimentalAnswerService


router = APIRouter(prefix="/experiments", tags=["experiments"])


@router.get("/capabilities")
def experiment_capabilities(
    service: ExperimentalAnswerService = Depends(get_experimental_answer_service),
) -> dict:
    return service.get_capabilities().model_dump(mode="json")


@router.post("/admin/verify")
def verify_experiment_admin(
    payload: ExperimentAdminVerifyRequest,
    service: ExperimentalAnswerService = Depends(get_experimental_answer_service),
) -> dict:
    return ExperimentAdminVerifyResponse(authenticated=service.verify_admin_secret(payload.secret)).model_dump(mode="json")


@router.post("/answer")
def experimental_answer(
    payload: ExperimentalAnswerRequest,
    x_experiment_admin_secret: str | None = Header(default=None),
    service: ExperimentalAnswerService = Depends(get_experimental_answer_service),
) -> dict:
    try:
        _require_admin_for_persistence(payload.persist, x_experiment_admin_secret, service)
        return service.answer(
            query=payload.query,
            mode=payload.mode,
            document_id=payload.document_id,
            expansion_options=payload.expansion_options,
            persist=payload.persist,
            include_trace=payload.include_trace,
        ).model_dump(mode="json")
    except ExperimentalAnswerError as exc:
        raise _http_error(exc)


@router.post("/compare")
def experimental_compare(
    payload: ExperimentCompareRequest,
    x_experiment_admin_secret: str | None = Header(default=None),
    service: ExperimentalAnswerService = Depends(get_experimental_answer_service),
) -> dict:
    try:
        _require_admin_for_persistence(payload.persist, x_experiment_admin_secret, service)
        return service.compare(
            query=payload.query,
            modes=payload.modes,
            document_id=payload.document_id,
            expansion_options=payload.expansion_options,
            persist=payload.persist,
            include_trace=payload.include_trace,
        ).model_dump(mode="json")
    except ExperimentalAnswerError as exc:
        raise _http_error(exc)


@router.delete("/sessions/{session_id}")
def delete_experiment_session(
    session_id: UUID,
    x_experiment_admin_secret: str | None = Header(default=None),
    service: ExperimentalAnswerService = Depends(get_experimental_answer_service),
) -> dict:
    try:
        deleted = service.delete_session(session_id, admin_secret=x_experiment_admin_secret)
    except ExperimentalAnswerError as exc:
        raise _http_error(exc)
    if not deleted:
        raise HTTPException(status_code=404, detail="Experiment session not found")
    return ExperimentDeleteSessionResponse(deleted=True, session_id=session_id).model_dump(mode="json")


@router.get("/sessions")
def list_experiment_sessions(
    service: ExperimentalAnswerService = Depends(get_experimental_answer_service),
    status: str | None = None,
    mode: str | None = None,
    created_after: datetime | None = None,
    created_before: datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict:
    sessions = service.list_sessions(
        status=status,
        mode=mode,
        created_after=created_after,
        created_before=created_before,
        limit=limit,
        offset=offset,
    )
    return {"sessions": [session.model_dump(mode="json") for session in sessions], "limit": limit, "offset": offset}


@router.get("/sessions/{session_id}")
def get_experiment_session(
    session_id: UUID,
    service: ExperimentalAnswerService = Depends(get_experimental_answer_service),
) -> dict:
    detail = service.get_session_detail(session_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Experiment session not found")
    return detail.model_dump(mode="json")


@router.get("/mode-runs/{mode_run_id}")
def get_experiment_mode_run(
    mode_run_id: UUID,
    include_trace: bool = False,
    include_context_text: bool = False,
    service: ExperimentalAnswerService = Depends(get_experimental_answer_service),
) -> dict:
    detail = service.get_mode_run_detail(
        mode_run_id,
        include_trace=include_trace,
        include_context_text=include_context_text,
    )
    if detail is None:
        raise HTTPException(status_code=404, detail="Experiment mode run not found")
    return detail.model_dump(mode="json")


def _http_error(exc: ExperimentalAnswerError) -> HTTPException:
    status_code = 400
    if exc.error_code == "experiment_admin_auth_required":
        status_code = 403
    if exc.error_code in {
        "retrieval_failed",
        "answer_generation_failed",
        "experiment_persistence_failed",
        "baseline_parity_failed",
        "invalid_retrieval_trace",
        "context_snapshot_failed",
    }:
        status_code = 503
    return HTTPException(
        status_code=status_code,
        detail={
            "error_code": exc.error_code,
            "message": str(exc),
            "session_id": str(exc.session_id) if exc.session_id else None,
            "failed_mode": exc.failed_mode,
        },
    )


def _require_admin_for_persistence(
    persist_requested: bool,
    admin_secret: str | None,
    service: ExperimentalAnswerService,
) -> None:
    if persist_requested and not service.verify_admin_secret(admin_secret):
        raise ExperimentalAnswerError("experiment_admin_auth_required", "Experiment admin unlock is required.")

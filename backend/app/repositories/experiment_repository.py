from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.db.connection import get_connection
from app.schemas.experiments import RetrievalMode


class ExperimentPersistenceError(RuntimeError):
    """Raised when experiment persistence fails."""


class ExperimentRepository:
    def experiment_schema_ready(self) -> bool:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        to_regclass('public.experiment_sessions') IS NOT NULL
                        AND to_regclass('public.experiment_mode_runs') IS NOT NULL;
                    """
                )
                row = cur.fetchone()
                return bool(row[0]) if row else False

    def create_session(
        self,
        *,
        query_text: str,
        requested_modes: tuple[RetrievalMode, ...],
        alias_dataset_sha256: str,
        corpus_content_sha256: str | None,
        git_commit: str | None,
        metadata_warnings: list[str],
        embedding_model: str | None,
        vector_metric: str | None,
        answer_model: str | None,
        answer_provider: str | None,
        query_expansion_config: dict[str, Any],
        retrieval_config: dict[str, Any],
        generation_config: dict[str, Any],
        prompt_template_sha256: str | None,
    ) -> UUID:
        session_id = uuid4()
        now = _now()
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO experiment_sessions (
                        id, query_text, requested_modes, status, started_at,
                        alias_dataset_sha256, corpus_content_sha256, git_commit, metadata_warnings,
                        embedding_model, vector_metric, answer_model, answer_provider,
                        query_expansion_config, retrieval_config, generation_config,
                        prompt_template_sha256, requested_mode_count
                    )
                    VALUES (
                        %(id)s, %(query_text)s, %(requested_modes)s, 'running', %(started_at)s,
                        %(alias_dataset_sha256)s, %(corpus_content_sha256)s, %(git_commit)s, %(metadata_warnings)s,
                        %(embedding_model)s, %(vector_metric)s, %(answer_model)s, %(answer_provider)s,
                        %(query_expansion_config)s, %(retrieval_config)s, %(generation_config)s,
                        %(prompt_template_sha256)s, %(requested_mode_count)s
                    );
                    """,
                    {
                        "id": session_id,
                        "query_text": query_text,
                        "requested_modes": Jsonb(list(requested_modes)),
                        "started_at": now,
                        "alias_dataset_sha256": alias_dataset_sha256,
                        "corpus_content_sha256": corpus_content_sha256,
                        "git_commit": git_commit,
                        "metadata_warnings": Jsonb(metadata_warnings),
                        "embedding_model": embedding_model,
                        "vector_metric": vector_metric,
                        "answer_model": answer_model,
                        "answer_provider": answer_provider,
                        "query_expansion_config": Jsonb(query_expansion_config),
                        "retrieval_config": Jsonb(retrieval_config),
                        "generation_config": Jsonb(generation_config),
                        "prompt_template_sha256": prompt_template_sha256,
                        "requested_mode_count": len(requested_modes),
                    },
                )
            conn.commit()
        return session_id

    def create_mode_run(
        self,
        *,
        session_id: UUID,
        mode: RetrievalMode,
        retrieval_executed: bool = True,
        retrieval_source_mode: RetrievalMode | None = None,
        retrieval_source_mode_run_id: UUID | None = None,
    ) -> UUID:
        mode_run_id = uuid4()
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO experiment_mode_runs (
                        id, session_id, mode, status, retrieval_executed,
                        retrieval_source_mode, retrieval_source_mode_run_id, created_at
                    )
                    VALUES (
                        %(id)s, %(session_id)s, %(mode)s, 'pending', %(retrieval_executed)s,
                        %(retrieval_source_mode)s, %(retrieval_source_mode_run_id)s, %(created_at)s
                    );
                    """,
                    {
                        "id": mode_run_id,
                        "session_id": session_id,
                        "mode": mode,
                        "retrieval_executed": retrieval_executed,
                        "retrieval_source_mode": retrieval_source_mode,
                        "retrieval_source_mode_run_id": retrieval_source_mode_run_id,
                        "created_at": _now(),
                    },
                )
            conn.commit()
        return mode_run_id

    def mark_mode_running(self, mode_run_id: UUID) -> None:
        self._update_mode_status(mode_run_id, "running")

    def save_mode_retrieval_completed(
        self,
        *,
        mode_run_id: UUID,
        retrieval_reason: str | None,
        generated_variant_count: int,
        vector_search_call_count: int,
        final_context_count: int,
        retrieval_duration_ms: float | None,
        context_chunk_uids: tuple[str, ...],
        context_records: tuple[dict[str, Any], ...],
        prompt_context_snapshot: tuple[dict[str, Any], ...],
        context_snapshot_sha256: str | None,
        expansion_trace: dict[str, Any] | None,
        retrieval_trace: dict[str, Any] | None,
        retrieval_summary: dict[str, Any],
    ) -> None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE experiment_mode_runs
                    SET status='retrieval_completed',
                        retrieval_executed=%(retrieval_executed)s,
                        retrieval_source_mode=%(retrieval_source_mode)s,
                        retrieval_source_mode_run_id=%(retrieval_source_mode_run_id)s,
                        retrieval_reason=%(retrieval_reason)s,
                        generated_variant_count=%(generated_variant_count)s,
                        vector_search_call_count=%(vector_search_call_count)s,
                        final_context_count=%(final_context_count)s,
                        retrieval_duration_ms=%(retrieval_duration_ms)s,
                        context_chunk_uids=%(context_chunk_uids)s,
                        context_records=%(context_records)s,
                        prompt_context_snapshot=%(prompt_context_snapshot)s,
                        context_snapshot_sha256=%(context_snapshot_sha256)s,
                        expansion_trace=%(expansion_trace)s,
                        retrieval_trace=%(retrieval_trace)s,
                        retrieval_summary=%(retrieval_summary)s
                    WHERE id=%(id)s;
                    """,
                    {
                        "id": mode_run_id,
                        "retrieval_executed": retrieval_summary.get("retrieval_executed", True),
                        "retrieval_source_mode": retrieval_summary.get("retrieval_source_mode"),
                        "retrieval_source_mode_run_id": retrieval_summary.get("retrieval_source_mode_run_id"),
                        "retrieval_reason": retrieval_reason,
                        "generated_variant_count": generated_variant_count,
                        "vector_search_call_count": vector_search_call_count,
                        "final_context_count": final_context_count,
                        "retrieval_duration_ms": retrieval_duration_ms,
                        "context_chunk_uids": Jsonb(list(context_chunk_uids)),
                        "context_records": Jsonb(list(context_records)),
                        "prompt_context_snapshot": Jsonb(list(prompt_context_snapshot)),
                        "context_snapshot_sha256": context_snapshot_sha256,
                        "expansion_trace": Jsonb(expansion_trace) if expansion_trace is not None else None,
                        "retrieval_trace": Jsonb(retrieval_trace) if retrieval_trace is not None else None,
                        "retrieval_summary": Jsonb(retrieval_summary),
                    },
                )
            conn.commit()

    def save_mode_completed(
        self,
        *,
        mode_run_id: UUID,
        answer_text: str,
        answer_payload: dict[str, Any],
        generation_duration_ms: float,
        total_duration_ms: float | None,
        prompt_template_sha256: str,
        rendered_prompt_sha256: str,
        input_token_count: int | None,
        output_token_count: int | None,
    ) -> None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE experiment_mode_runs
                    SET status='completed',
                        answer_text=%(answer_text)s,
                        answer_payload=%(answer_payload)s,
                        generation_duration_ms=%(generation_duration_ms)s,
                        total_duration_ms=%(total_duration_ms)s,
                        prompt_template_sha256=%(prompt_template_sha256)s,
                        rendered_prompt_sha256=%(rendered_prompt_sha256)s,
                        input_token_count=%(input_token_count)s,
                        output_token_count=%(output_token_count)s,
                        completed_at=%(completed_at)s
                    WHERE id=%(id)s;
                    """,
                    {
                        "id": mode_run_id,
                        "answer_text": answer_text,
                        "answer_payload": Jsonb(answer_payload),
                        "generation_duration_ms": generation_duration_ms,
                        "total_duration_ms": total_duration_ms,
                        "prompt_template_sha256": prompt_template_sha256,
                        "rendered_prompt_sha256": rendered_prompt_sha256,
                        "input_token_count": input_token_count,
                        "output_token_count": output_token_count,
                        "completed_at": _now(),
                    },
                )
            conn.commit()

    def save_mode_failed(self, *, mode_run_id: UUID, error_code: str, error_message: str) -> None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE experiment_mode_runs
                    SET status='failed',
                        error_code=%(error_code)s,
                        error_message=%(error_message)s,
                        completed_at=%(completed_at)s
                    WHERE id=%(id)s;
                    """,
                    {
                        "id": mode_run_id,
                        "error_code": error_code,
                        "error_message": error_message,
                        "completed_at": _now(),
                    },
                )
            conn.commit()

    def finalize_session(
        self,
        *,
        session_id: UUID,
        status: str,
        retrieval_execution_count: int,
        answer_generation_count: int,
        total_vector_search_call_count: int,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE experiment_sessions
                    SET status=%(status)s,
                        completed_at=%(completed_at)s,
                        retrieval_execution_count=%(retrieval_execution_count)s,
                        answer_generation_count=%(answer_generation_count)s,
                        total_vector_search_call_count=%(total_vector_search_call_count)s,
                        error_code=%(error_code)s,
                        error_message=%(error_message)s
                    WHERE id=%(id)s;
                    """,
                    {
                        "id": session_id,
                        "status": status,
                        "completed_at": _now(),
                        "retrieval_execution_count": retrieval_execution_count,
                        "answer_generation_count": answer_generation_count,
                        "total_vector_search_call_count": total_vector_search_call_count,
                        "error_code": error_code,
                        "error_message": error_message,
                    },
                )
            conn.commit()

    def list_sessions(
        self,
        *,
        status: str | None = None,
        mode: str | None = None,
        created_after: datetime | None = None,
        created_before: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if status:
            clauses.append("s.status = %(status)s")
            params["status"] = status
        if created_after:
            clauses.append("s.started_at >= %(created_after)s")
            params["created_after"] = created_after
        if created_before:
            clauses.append("s.started_at <= %(created_before)s")
            params["created_before"] = created_before
        if mode:
            clauses.append("EXISTS (SELECT 1 FROM experiment_mode_runs m WHERE m.session_id=s.id AND m.mode=%(mode)s)")
            params["mode"] = mode
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with get_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    f"""
                    SELECT id, query_text, requested_modes, status, started_at, completed_at,
                           requested_mode_count, retrieval_execution_count, answer_generation_count,
                           total_vector_search_call_count
                    FROM experiment_sessions s
                    {where}
                    ORDER BY started_at DESC, id DESC
                    LIMIT %(limit)s OFFSET %(offset)s;
                    """,
                    params,
                )
                return list(cur.fetchall())

    def get_session(self, session_id: UUID) -> dict[str, Any] | None:
        with get_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute("SELECT * FROM experiment_sessions WHERE id=%s;", (session_id,))
                row = cur.fetchone()
                return dict(row) if row else None

    def list_mode_runs_for_session(self, session_id: UUID) -> list[dict[str, Any]]:
        with get_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT * FROM experiment_mode_runs
                    WHERE session_id=%s
                    ORDER BY CASE mode WHEN 'baseline' THEN 1 WHEN 'strong_only' THEN 2 ELSE 3 END;
                    """,
                    (session_id,),
                )
                return list(cur.fetchall())

    def get_mode_run(self, mode_run_id: UUID) -> dict[str, Any] | None:
        with get_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute("SELECT * FROM experiment_mode_runs WHERE id=%s;", (mode_run_id,))
                row = cur.fetchone()
                return dict(row) if row else None

    def delete_session(self, session_id: UUID) -> bool:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM experiment_sessions WHERE id=%s;", (session_id,))
                deleted = cur.rowcount > 0
            conn.commit()
        return deleted

    def _update_mode_status(self, mode_run_id: UUID, status: str) -> None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE experiment_mode_runs SET status=%s WHERE id=%s;", (status, mode_run_id))
            conn.commit()


def _now() -> datetime:
    return datetime.now(timezone.utc)

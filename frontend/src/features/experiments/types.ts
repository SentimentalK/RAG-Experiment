export type RetrievalMode = "baseline" | "strong_only" | "strong_story";
export type ModeRunStatus = "not_requested" | "pending" | "running" | "retrieval_completed" | "completed" | "failed";
export type SessionStatus = "running" | "completed" | "partial" | "failed";
export type VariantStatus = "generated" | "searched" | "skipped" | "failed";

export interface ExperimentCapabilities {
  available_modes: RetrievalMode[];
  persistence: {
    enabled: boolean;
    required: boolean;
  };
  expansion: {
    enabled: boolean;
    max_query_variants: number;
    allow_story_scoped: boolean;
    allow_story_scoped_single_token: boolean;
  };
  trace_persistence_enabled: boolean;
  evaluation_catalog_available: boolean;
}

export interface ExpansionOptions {
  enabled?: boolean;
  max_query_variants?: number;
  allow_story_scoped?: boolean;
  allow_story_scoped_single_token?: boolean;
}

export interface ExperimentContextRecord {
  rank: number;
  chunk_uid: string;
  section_title: string;
  chunk_text: string | null;
  raw_similarity: number | null;
  raw_distance: number | null;
  document_id: string | null;
  section_id: string | null;
  section_order: number | null;
  chunk_index: number | null;
  chunk_order: number | null;
  token_count: number | null;
  alias_only_candidate: boolean;
}

export interface ExperimentVariantStatus {
  variant_id: string;
  variant_index: number;
  variant_kind: string;
  status: VariantStatus | string;
  error_code: string | null;
  error_message: string | null;
}

export interface ExperimentRetrievalSummary {
  retrieval_reason: string | null;
  generated_variant_count: number;
  vector_search_call_count: number;
  final_context_count: number;
  retrieval_executed: boolean;
  retrieval_source_mode: RetrievalMode | null;
  retrieval_reused: boolean;
  variant_statuses: ExperimentVariantStatus[];
}

export interface ExperimentTiming {
  retrieval_duration_ms: number | null;
  generation_duration_ms: number | null;
  total_duration_ms: number | null;
}

export interface ExperimentModeResult {
  mode: RetrievalMode;
  mode_run_id: string | null;
  status: ModeRunStatus;
  answer: string | null;
  evidence_sufficient: boolean | null;
  citations: { chunk_uid: string; reason: string }[];
  confidence: number | null;
  contexts: ExperimentContextRecord[];
  context_chunk_uids: string[];
  context_snapshot_sha256: string | null;
  prompt_template_sha256: string | null;
  rendered_prompt_sha256: string | null;
  retrieval_summary: ExperimentRetrievalSummary;
  timing: ExperimentTiming;
  trace: Record<string, unknown> | null;
  warnings: string[];
  error_code: string | null;
  error_message: string | null;
}

export interface ModeComparisonSummary {
  baseline_mode: RetrievalMode;
  compared_mode: RetrievalMode;
  shared_context_count: number;
  new_context_count: number;
  displaced_context_count: number;
  context_jaccard_at_10: number;
  new_chunk_uids: string[];
  displaced_chunk_uids: string[];
  alias_only_context_count: number;
  answer_text_equal: boolean;
  answer_text_normalized_equal: boolean;
  validation_warnings: string[];
}

export interface ExperimentCompareResponse {
  session_id: string | null;
  persisted: boolean;
  query: string;
  status: SessionStatus;
  results: Partial<Record<RetrievalMode, ExperimentModeResult>>;
  comparisons: ModeComparisonSummary[];
  requested_mode_count: number;
  retrieval_execution_count: number;
  answer_generation_count: number;
  total_vector_search_call_count: number;
  warnings: string[];
}

export interface ExperimentalAnswerResponse {
  session_id: string | null;
  mode_run_id: string | null;
  persisted: boolean;
  query: string;
  mode: RetrievalMode;
  result: ExperimentModeResult;
  warnings: string[];
}

export interface ExperimentSessionSummary {
  session_id: string;
  query: string;
  requested_modes: RetrievalMode[];
  status: SessionStatus;
  started_at: string;
  completed_at: string | null;
  requested_mode_count: number;
  retrieval_execution_count: number;
  answer_generation_count: number;
  total_vector_search_call_count: number;
}

export interface ExperimentSessionDetail {
  session: ExperimentSessionSummary;
  modes: ExperimentModeResult[];
  alias_dataset_sha256: string;
  corpus_content_sha256: string | null;
  git_commit: string | null;
  query_expansion_config: Record<string, unknown>;
  retrieval_config: Record<string, unknown>;
  generation_config: Record<string, unknown>;
}

export interface ApiErrorDetail {
  error_code?: string;
  message?: string;
  session_id?: string | null;
  failed_mode?: RetrievalMode | null;
}

export interface ExperimentApiError extends Error {
  status: number;
  detail: ApiErrorDetail | null;
}

export interface ModeRunViewModel {
  mode: RetrievalMode;
  label: string;
  status: ModeRunStatus | string;
  unsupportedTraceSchema: boolean;
  traceSchemaVersion: string | null;
  variantStatuses: ExperimentVariantStatus[];
  result: ExperimentModeResult;
}

export const MODE_ORDER: RetrievalMode[] = ["baseline", "strong_only", "strong_story"];

export const MODE_LABELS: Record<RetrievalMode, string> = {
  baseline: "Baseline",
  strong_only: "Strong Only",
  strong_story: "Strong + Story",
};

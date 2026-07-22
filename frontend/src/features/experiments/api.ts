import type {
  ExperimentApiError,
  ExperimentCapabilities,
  ExperimentCompareResponse,
  ExperimentalAnswerResponse,
  ExperimentSessionDetail,
  ExperimentSessionSummary,
  ExpansionOptions,
  RetrievalMode,
} from "./types";

async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    const error = new Error(payload?.detail?.message ?? payload?.detail ?? `Request failed with status ${response.status}.`) as ExperimentApiError;
    error.status = response.status;
    error.detail = typeof payload?.detail === "object" ? payload.detail : null;
    throw error;
  }
  return payload as T;
}

function adminHeaders(adminSecret?: string | null): HeadersInit {
  return adminSecret ? { "X-Experiment-Admin-Secret": adminSecret } : {};
}

export function getExperimentCapabilities(signal?: AbortSignal): Promise<ExperimentCapabilities> {
  return requestJson<ExperimentCapabilities>("/api/experiments/capabilities", { signal });
}

export function verifyExperimentAdmin(secret: string, signal?: AbortSignal): Promise<{ authenticated: boolean }> {
  return requestJson<{ authenticated: boolean }>("/api/experiments/admin/verify", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ secret }),
    signal,
  });
}

export interface CompareExperimentPayload {
  query: string;
  modes: RetrievalMode[];
  document_id?: string;
  expansion_options?: ExpansionOptions;
  persist?: boolean;
  include_trace?: boolean;
}

export function compareExperiment(payload: CompareExperimentPayload, signal?: AbortSignal, adminSecret?: string | null): Promise<ExperimentCompareResponse> {
  return requestJson<ExperimentCompareResponse>("/api/experiments/compare", {
    method: "POST",
    headers: { "Content-Type": "application/json", ...adminHeaders(adminSecret) },
    body: JSON.stringify(payload),
    signal,
  });
}

export interface AnswerExperimentPayload {
  query: string;
  mode: RetrievalMode;
  document_id?: string;
  expansion_options?: ExpansionOptions;
  persist?: boolean;
  include_trace?: boolean;
}

export function answerExperiment(payload: AnswerExperimentPayload, signal?: AbortSignal, adminSecret?: string | null): Promise<ExperimentalAnswerResponse> {
  return requestJson<ExperimentalAnswerResponse>("/api/experiments/answer", {
    method: "POST",
    headers: { "Content-Type": "application/json", ...adminHeaders(adminSecret) },
    body: JSON.stringify(payload),
    signal,
  });
}

export interface SessionFilters {
  status?: string;
  mode?: string;
  created_after?: string;
  created_before?: string;
  limit?: number;
  offset?: number;
}

export function listExperimentSessions(filters: SessionFilters, signal?: AbortSignal): Promise<{
  sessions: ExperimentSessionSummary[];
  limit: number;
  offset: number;
}> {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== null && String(value) !== "") {
      params.set(key, String(value));
    }
  });
  return requestJson(`/api/experiments/sessions?${params.toString()}`, { signal });
}

export function getExperimentSession(sessionId: string, signal?: AbortSignal): Promise<ExperimentSessionDetail> {
  return requestJson<ExperimentSessionDetail>(`/api/experiments/sessions/${sessionId}`, { signal });
}

export function getExperimentModeRun(
  modeRunId: string,
  options: { include_trace?: boolean; include_context_text?: boolean } = {},
  signal?: AbortSignal,
) {
  const params = new URLSearchParams();
  if (options.include_trace) params.set("include_trace", "true");
  if (options.include_context_text) params.set("include_context_text", "true");
  const suffix = params.toString() ? `?${params.toString()}` : "";
  return requestJson(`/api/experiments/mode-runs/${modeRunId}${suffix}`, { signal });
}

export function deleteExperimentSession(sessionId: string, adminSecret: string, signal?: AbortSignal): Promise<{ deleted: boolean; session_id: string }> {
  return requestJson<{ deleted: boolean; session_id: string }>(`/api/experiments/sessions/${sessionId}`, {
    method: "DELETE",
    headers: adminHeaders(adminSecret),
    signal,
  });
}

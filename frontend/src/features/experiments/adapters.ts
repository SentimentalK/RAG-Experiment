import type { ExperimentModeResult, ExperimentVariantStatus, ModeRunViewModel, RetrievalMode } from "./types";
import { MODE_LABELS } from "./types";

const SUPPORTED_TRACE_SCHEMA_VERSION = "1";

export function normalizeModeRunDetail(result: ExperimentModeResult): ModeRunViewModel {
  const trace = result.trace as { trace_schema_version?: unknown } | null;
  const rawVersion = trace?.trace_schema_version;
  const traceSchemaVersion = typeof rawVersion === "string" ? rawVersion : rawVersion == null ? null : String(rawVersion);
  const unsupportedTraceSchema = traceSchemaVersion !== null && traceSchemaVersion !== SUPPORTED_TRACE_SCHEMA_VERSION;
  return {
    mode: result.mode,
    label: modeLabel(result.mode),
    status: result.status,
    unsupportedTraceSchema,
    traceSchemaVersion,
    variantStatuses: result.retrieval_summary.variant_statuses ?? [],
    result,
  };
}

export function modeLabel(mode: RetrievalMode | string): string {
  return MODE_LABELS[mode as RetrievalMode] ?? `${mode} (Unknown)`;
}

export function enumLabel(value: string | null | undefined): string {
  if (!value) return "None";
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export function variantStatusLabel(status: ExperimentVariantStatus): string {
  const known = new Set(["generated", "searched", "skipped", "failed"]);
  return known.has(status.status) ? enumLabel(status.status) : `${status.status} (Unknown)`;
}

export function extractCitations(answer: string | null): number[] {
  if (!answer) return [];
  const seen = new Set<number>();
  for (const match of answer.matchAll(/\[(\d+)\]/g)) {
    const value = Number(match[1]);
    if (Number.isInteger(value) && value > 0) {
      seen.add(value);
    }
  }
  return [...seen].sort((a, b) => a - b);
}

export function normalizedAnswerText(value: string | null): string {
  return (value ?? "").trim().replace(/\s+/g, " ");
}

export function formatDuration(ms: number | null | undefined): string {
  if (ms == null) return "n/a";
  if (ms < 1000) return `${ms.toFixed(0)} ms`;
  return `${(ms / 1000).toFixed(2)} s`;
}

export function safeLimit(value: string | null): number {
  const parsed = Number(value ?? 50);
  if (!Number.isFinite(parsed)) return 50;
  return Math.min(200, Math.max(1, Math.trunc(parsed)));
}

export function safeOffset(value: string | null): number {
  const parsed = Number(value ?? 0);
  if (!Number.isFinite(parsed)) return 0;
  return Math.max(0, Math.trunc(parsed));
}

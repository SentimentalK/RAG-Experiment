import { useEffect, useState } from "react";
import { Link } from "react-router";
import { AlertCircle, Boxes, ChevronDown, FileSearch, Loader2, Route, SearchCheck } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { getExperimentModeRun } from "./api";
import { enumLabel, extractCitations, formatDuration, modeLabel, normalizeModeRunDetail, variantStatusLabel } from "./adapters";
import type { ExperimentContextRecord, ExperimentModeResult, ModeComparisonSummary } from "./types";

export function ModeResultCard({
  result,
  comparison,
  persisted,
}: {
  result: ExperimentModeResult;
  comparison?: ModeComparisonSummary;
  persisted: boolean;
}) {
  const [detail, setDetail] = useState<ExperimentModeResult>(result);
  const [loadingTrace, setLoadingTrace] = useState(false);
  const [loadingText, setLoadingText] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const view = normalizeModeRunDetail(detail);
  const invalidCitations = extractCitations(detail.answer).filter((rank) => rank > detail.contexts.length);
  const hasInlineTrace = !!detail.trace;
  const canLazyFetch = !!detail.mode_run_id;

  useEffect(() => setDetail(result), [result]);

  async function loadDetail(options: { include_trace?: boolean; include_context_text?: boolean }) {
    if (!detail.mode_run_id) return;
    setDetailError(null);
    if (options.include_trace) setLoadingTrace(true);
    if (options.include_context_text) setLoadingText(true);
    try {
      const response = (await getExperimentModeRun(detail.mode_run_id, {
        include_trace: options.include_trace || !!detail.trace,
        include_context_text: options.include_context_text || detail.contexts.some((context) => context.chunk_text),
      })) as ExperimentModeResult;
      setDetail(response);
    } catch (error) {
      setDetailError(error instanceof Error ? error.message : "Unable to load mode detail.");
    } finally {
      setLoadingTrace(false);
      setLoadingText(false);
    }
  }

  return (
    <Card className="border-slate-200 shadow-sm dark:border-slate-800">
      <CardHeader className="space-y-3">
        <div className="flex items-start justify-between gap-3">
          <div>
            <CardTitle className="text-lg">{modeLabel(detail.mode)}</CardTitle>
            <p className="text-sm text-muted-foreground">{enumLabel(detail.status)}</p>
          </div>
          <StatusBadge status={detail.status} />
        </div>
        <div className="grid grid-cols-2 gap-2 text-xs text-muted-foreground">
          <Metric label="Searches" value={String(detail.retrieval_summary.vector_search_call_count)} />
          <Metric label="Contexts" value={String(detail.contexts.length)} />
          <Metric label="Retrieval" value={detail.retrieval_summary.retrieval_executed ? "Executed" : "Reused"} />
          <Metric label="Total" value={formatDuration(detail.timing.total_duration_ms)} />
        </div>
        {detail.retrieval_summary.retrieval_reused && (
          <Badge variant="outline" className="w-fit">
            Retrieval reused from {modeLabel(detail.retrieval_summary.retrieval_source_mode ?? "baseline")}
          </Badge>
        )}
        {detail.status === "failed" && detail.contexts.length > 0 && (
          <Alert className="border-amber-200 bg-amber-50/70 dark:border-amber-900/50 dark:bg-amber-950/20">
            <AlertCircle className="h-4 w-4" />
            <AlertTitle>Answer unavailable</AlertTitle>
            <AlertDescription>Retrieval completed successfully, so contexts and inspectors remain available.</AlertDescription>
          </Alert>
        )}
      </CardHeader>
      <CardContent className="space-y-4">
        <AnswerBlock answer={detail.answer} contextCount={detail.contexts.length} invalidCitations={invalidCitations} />
        <ContextList contexts={detail.contexts} comparison={comparison} onLoadText={() => loadDetail({ include_context_text: true })} loading={loadingText} />
        {detailError && <p className="text-sm text-red-600">{detailError}</p>}
        <div className="flex flex-wrap gap-2">
          {detail.mode_run_id && (
            <Button variant="outline" size="sm" render={<Link to={`/experiments/mode-runs/${detail.mode_run_id}`} />}>
              Open Detail
            </Button>
          )}
          {!hasInlineTrace && canLazyFetch && (
            <Button type="button" variant="outline" size="sm" onClick={() => loadDetail({ include_trace: true })} disabled={loadingTrace}>
              {loadingTrace ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <FileSearch className="mr-2 h-4 w-4" />}
              Load Trace
            </Button>
          )}
        </div>
        {hasInlineTrace ? (
          <TraceInspectors result={detail} />
        ) : !persisted && !detail.mode_run_id ? (
          <p className="text-sm text-muted-foreground">Detailed trace is unavailable because this experiment was not saved or returned with trace data.</p>
        ) : null}
        {view.unsupportedTraceSchema && (
          <Alert>
            <AlertCircle className="h-4 w-4" />
            <AlertTitle>Unsupported Trace Schema</AlertTitle>
            <AlertDescription>
              This trace was created with schema {view.traceSchemaVersion}. Overview and answer metadata remain available.
            </AlertDescription>
          </Alert>
        )}
      </CardContent>
    </Card>
  );
}

function StatusBadge({ status }: { status: string }) {
  const variant = status === "completed" ? "outline" : status === "failed" ? "destructive" : "secondary";
  return <Badge variant={variant}>{enumLabel(status)}</Badge>;
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border bg-slate-50 px-2 py-1.5 dark:bg-slate-900/40">
      <span className="block font-medium text-foreground">{value}</span>
      <span>{label}</span>
    </div>
  );
}

function AnswerBlock({ answer, contextCount, invalidCitations }: { answer: string | null; contextCount: number; invalidCitations: number[] }) {
  if (!answer) {
    return <div className="rounded-md border border-dashed p-4 text-sm text-muted-foreground">No answer text was generated for this mode.</div>;
  }
  const citations = extractCitations(answer);
  return (
    <div className="space-y-2">
      <p className="whitespace-pre-wrap rounded-md border bg-white p-4 font-serif leading-relaxed dark:bg-slate-950">{answer}</p>
      <div className="flex flex-wrap gap-2 text-xs">
        {citations.map((citation) => (
          <Badge key={citation} variant={citation <= contextCount ? "outline" : "destructive"}>
            [{citation}] {citation <= contextCount ? "Context" : "Missing"}
          </Badge>
        ))}
      </div>
      {invalidCitations.length > 0 && (
        <p className="text-xs text-amber-700 dark:text-amber-400">Citation warning: missing context rank(s) {invalidCitations.join(", ")}.</p>
      )}
    </div>
  );
}

function ContextList({
  contexts,
  comparison,
  onLoadText,
  loading,
}: {
  contexts: ExperimentContextRecord[];
  comparison?: ModeComparisonSummary;
  onLoadText: () => void;
  loading: boolean;
}) {
  const hasText = contexts.some((context) => context.chunk_text);
  const newSet = new Set(comparison?.new_chunk_uids ?? []);
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold">Contexts</h3>
        {!hasText && contexts.length > 0 && (
          <Button type="button" variant="outline" size="sm" onClick={onLoadText} disabled={loading}>
            {loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <ChevronDown className="mr-2 h-4 w-4" />}
            Load Text
          </Button>
        )}
      </div>
      <div className="space-y-2">
        {contexts.map((context) => (
          <div key={`${context.rank}-${context.chunk_uid}`} className="rounded-md border bg-slate-50 p-3 dark:bg-slate-900/40">
            <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
              <Badge variant="outline">[{context.rank}]</Badge>
              <span className="font-mono">{context.chunk_uid}</span>
              <span>{context.section_title}</span>
              {comparison && <Badge variant={newSet.has(context.chunk_uid) ? "secondary" : "outline"}>{newSet.has(context.chunk_uid) ? "New" : "Shared"}</Badge>}
              {context.alias_only_candidate && <Badge variant="outline">Alias-only</Badge>}
            </div>
            {context.chunk_text && <p className="mt-2 line-clamp-6 text-sm leading-relaxed">{context.chunk_text}</p>}
          </div>
        ))}
      </div>
    </div>
  );
}

export function TraceInspectors({ result }: { result: ExperimentModeResult }) {
  const trace = result.trace as any;
  const view = normalizeModeRunDetail(result);
  if (!trace) return null;
  return (
    <Tabs defaultValue="expansion" className="w-full">
      <TabsList className="grid w-full grid-cols-2">
        <TabsTrigger value="expansion">
          <Route className="mr-2 h-4 w-4" />
          Expansion
        </TabsTrigger>
        <TabsTrigger value="retrieval">
          <Boxes className="mr-2 h-4 w-4" />
          Retrieval
        </TabsTrigger>
      </TabsList>
      <TabsContent value="expansion" className="space-y-3 pt-3">
        <VariantStatusList statuses={view.variantStatuses} />
        <Separator />
        <TraceList title="Mentions" items={(trace.expansion_trace?.detected_mentions ?? []) as TraceRecord[]} render={(item) => String(item.original_text ?? item.normalized_surface ?? item.mention_id ?? "mention")} />
        <TraceList title="Blocked Mentions" items={(trace.expansion_trace?.blocked_mentions ?? []) as TraceRecord[]} render={(item) => `${String(item.original_text ?? item.mention_id ?? "mention")}: ${String(item.blocked_reason ?? "blocked")}`} />
      </TabsContent>
      <TabsContent value="retrieval" className="space-y-3 pt-3">
        <div className="grid grid-cols-2 gap-2 text-xs md:grid-cols-4">
          <Metric label="Reason" value={trace.retrieval_reason ?? "n/a"} />
          <Metric label="Calls" value={String(trace.vector_search_call_count ?? 0)} />
          <Metric label="Variants" value={String(trace.total_variant_count ?? 0)} />
          <Metric label="Final" value={String(trace.final_result_count ?? 0)} />
        </div>
        <TraceList title="Variant Retrievals" items={(trace.variant_retrievals ?? []) as TraceRecord[]} render={(item) => `${String(item.variant_index ?? "?")}. ${String(item.variant_kind ?? "variant")} · ${item.success ? "searched" : "failed"} · top ${String(item.requested_top_k ?? "?")}`} />
        <TraceList title="Fused Results" items={(trace.fused_results ?? []) as TraceRecord[]} render={(item) => `#${String(item.final_rank ?? "?")} ${String(item.chunk_id ?? "chunk")} · ${Number(item.fusion_score ?? 0).toFixed(4)}`} />
      </TabsContent>
    </Tabs>
  );
}

function VariantStatusList({ statuses }: { statuses: ReturnType<typeof normalizeModeRunDetail>["variantStatuses"] }) {
  if (statuses.length === 0) return <p className="text-sm text-muted-foreground">No explicit variant status metadata is available.</p>;
  return (
    <div className="grid gap-2 text-xs md:grid-cols-2">
      {statuses.map((status) => (
        <div key={status.variant_id} className="rounded-md border p-2">
          <div className="flex items-center justify-between gap-2">
            <span className="font-mono">{status.variant_id}</span>
            <Badge variant={status.status === "failed" ? "destructive" : "outline"}>{variantStatusLabel(status)}</Badge>
          </div>
          <p className="mt-1 text-muted-foreground">
            {status.variant_index}. {status.variant_kind}
          </p>
        </div>
      ))}
    </div>
  );
}

type TraceRecord = Record<string, unknown>;

function TraceList<T>({ title, items, render }: { title: string; items: T[]; render: (item: T) => string }) {
  return (
    <div className="space-y-2">
      <h4 className="flex items-center gap-2 text-sm font-semibold">
        <SearchCheck className="h-4 w-4" />
        {title}
      </h4>
      {items.length === 0 ? (
        <p className="text-sm text-muted-foreground">None recorded.</p>
      ) : (
        <div className="max-h-64 space-y-1 overflow-auto rounded-md border p-2">
          {items.map((item, index) => (
            <p key={index} className="text-xs text-muted-foreground">
              {render(item)}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}

export function ComparisonStrip({ comparison }: { comparison: ModeComparisonSummary }) {
  return (
    <div className="grid gap-2 text-xs md:grid-cols-4">
      <Metric label="Shared" value={String(comparison.shared_context_count)} />
      <Metric label="New" value={String(comparison.new_context_count)} />
      <Metric label="Displaced" value={String(comparison.displaced_context_count)} />
      <Metric label="Jaccard" value={comparison.context_jaccard_at_10.toFixed(2)} />
    </div>
  );
}

import { useEffect, useState } from "react";
import { AlertCircle, ChevronRight, FileSearch, Loader2 } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getExperimentModeRun } from "./api";
import { enumLabel, extractCitations, formatDuration, modeLabel, normalizeModeRunDetail, variantStatusLabel } from "./adapters";
import type { ExperimentContextRecord, ExperimentModeResult, ModeComparisonSummary } from "./types";

export function ModeResultCard({
  result,
  comparison,
}: {
  result: ExperimentModeResult;
  comparison?: ModeComparisonSummary;
}) {
  const [detail, setDetail] = useState<ExperimentModeResult>(result);
  const [loadingTrace, setLoadingTrace] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const view = normalizeModeRunDetail(detail);
  const invalidCitations = extractCitations(detail.answer).filter((rank) => rank > detail.contexts.length);
  const hasInlineTrace = !!detail.trace;
  const canLazyFetch = !!detail.mode_run_id;

  useEffect(() => setDetail(result), [result]);

  async function loadDetail(options: { include_trace?: boolean }) {
    if (!detail.mode_run_id) return;
    setDetailError(null);
    if (options.include_trace) setLoadingTrace(true);
    try {
      const response = (await getExperimentModeRun(detail.mode_run_id, {
        include_trace: options.include_trace || !!detail.trace,
      })) as ExperimentModeResult;
      setDetail(response);
    } catch (error) {
      setDetailError(error instanceof Error ? error.message : "Unable to load mode detail.");
    } finally {
      setLoadingTrace(false);
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
          <Metric label="Time" value={formatDuration(detail.timing.total_duration_ms ?? detail.timing.retrieval_duration_ms)} />
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
            <AlertDescription>
              Retrieval completed successfully, so contexts and inspectors remain available.
              {detail.error_code && (
                <span className="mt-2 block font-mono text-xs">
                  {detail.error_code}: {detail.error_message ?? "Generation did not return a valid answer payload."}
                </span>
              )}
            </AlertDescription>
          </Alert>
        )}
      </CardHeader>
      <CardContent className="space-y-4">
        <AnswerBlock answer={detail.answer} contextCount={detail.contexts.length} invalidCitations={invalidCitations} />
        {detailError && <p className="text-sm text-red-600">{detailError}</p>}
        <div className="flex flex-wrap gap-2">
          {!hasInlineTrace && canLazyFetch && (
            <Button type="button" variant="outline" size="sm" onClick={() => loadDetail({ include_trace: true })} disabled={loadingTrace}>
              {loadingTrace ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <FileSearch className="mr-2 h-4 w-4" />}
              Load Trace
            </Button>
          )}
        </div>
        {hasInlineTrace ? <TraceInspectors result={detail} /> : null}
        {view.unsupportedTraceSchema && (
          <Alert>
            <AlertCircle className="h-4 w-4" />
            <AlertTitle>Unsupported Trace Schema</AlertTitle>
            <AlertDescription>
              This trace was created with schema {view.traceSchemaVersion}. Overview and answer metadata remain available.
            </AlertDescription>
          </Alert>
        )}
        <AnswerModelInputSummary result={detail} />
        <ContextList contexts={detail.contexts} citations={detail.citations ?? []} comparison={comparison} />
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
  citations,
  comparison,
}: {
  contexts: ExperimentContextRecord[];
  citations: { chunk_uid: string; reason: string }[];
  comparison?: ModeComparisonSummary;
}) {
  const newSet = new Set(comparison?.new_chunk_uids ?? []);
  const displacedSet = new Set(comparison?.displaced_chunk_uids ?? []);
  const citationByChunk = new Map(citations.map((citation) => [citation.chunk_uid, citation]));
  return (
    <div className="space-y-4">
      <h3 className="text-sm font-semibold">Contexts</h3>
      {contexts.map((context) => {
        const citation = citationByChunk.get(context.chunk_uid);
        return (
          <ExperimentChunkCard
            key={`${context.rank}-${context.chunk_uid}`}
            context={context}
            isCited={!!citation}
            citationReason={citation?.reason}
            comparisonLabel={comparison ? (newSet.has(context.chunk_uid) ? "New" : displacedSet.has(context.chunk_uid) ? "Displaced" : "Shared") : null}
          />
        );
      })}
    </div>
  );
}

function ExperimentChunkCard({
  context,
  isCited,
  citationReason,
  comparisonLabel,
}: {
  context: ExperimentContextRecord;
  isCited: boolean;
  citationReason?: string;
  comparisonLabel: "Shared" | "New" | "Displaced" | null;
}) {
  return (
    <Card className={`overflow-hidden border-slate-200 shadow-sm transition-all dark:border-slate-800 ${isCited ? "border-blue-500 ring-1 ring-blue-100 dark:ring-blue-950/30" : ""}`}>
      <div className="flex flex-col justify-between gap-4 border-b bg-slate-50 p-4 dark:bg-slate-900/50 md:flex-row md:items-center">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/10 text-sm font-bold text-primary">
            #{context.rank}
          </div>
          <div>
            <div className="flex items-center gap-2 text-sm font-medium">
              <span className="max-w-[200px] truncate text-muted-foreground sm:max-w-[300px]">
                {context.section_title || "Unknown section"}
              </span>
              <ChevronRight className="h-3 w-3 text-muted-foreground" />
              <span className="rounded bg-slate-200 px-1.5 py-0.5 text-xs text-muted-foreground dark:bg-slate-800">
                Chunk {context.chunk_order ?? context.chunk_index ?? "n/a"}
              </span>
            </div>
            <div className="mt-1 flex flex-wrap gap-3 text-xs text-muted-foreground">
              <span>Distance: {context.raw_distance == null ? "n/a" : context.raw_distance.toFixed(4)}</span>
              <span>Tokens: {context.token_count ?? "n/a"}</span>
              <span className="font-mono">{context.chunk_uid}</span>
            </div>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="outline" className="border-slate-200 bg-slate-100 text-slate-800 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-400">
            Relevance not evaluated
          </Badge>
          {comparisonLabel && (
            <Badge variant="outline" className={comparisonLabel === "New" ? "border-blue-200 bg-blue-100 text-blue-800 dark:border-blue-800 dark:bg-blue-900/30 dark:text-blue-400" : "border-slate-200 bg-slate-100 text-slate-800 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-400"}>
              {comparisonLabel}
            </Badge>
          )}
          {context.alias_only_candidate && (
            <Badge variant="outline" className="border-violet-200 bg-violet-100 text-violet-800 dark:border-violet-800 dark:bg-violet-900/30 dark:text-violet-400">
              Alias-only
            </Badge>
          )}
          {isCited && (
            <Badge variant="outline" className="whitespace-nowrap border-blue-200 bg-blue-100 text-blue-800 dark:border-blue-800 dark:bg-blue-900/30 dark:text-blue-400">
              Cited by RAG
            </Badge>
          )}
        </div>
      </div>

      <CardContent className="p-0">
        <Accordion>
          <AccordionItem value="text" className="border-none">
            <AccordionTrigger className="px-4 py-3 text-sm font-medium hover:bg-slate-50 dark:hover:bg-slate-900/50">
              View Chunk Content
            </AccordionTrigger>
            <AccordionContent className="px-4 pb-4">
              <div className="space-y-4 pt-2">
                {isCited && citationReason && (
                  <div className="rounded-md border border-blue-100/50 bg-blue-50/50 p-3 text-sm italic text-muted-foreground dark:border-blue-900/20 dark:bg-blue-950/20">
                    <span className="mb-1 block font-semibold not-italic text-foreground">RAG Citation Reason:</span>
                    {citationReason}
                  </div>
                )}
                <div>
                  {context.chunk_text ? (
                    <p className="whitespace-pre-wrap font-serif text-sm leading-relaxed text-foreground">
                      {context.chunk_text}
                    </p>
                  ) : (
                    <p className="text-sm text-muted-foreground">Context text is unavailable in this summary response.</p>
                  )}
                </div>
              </div>
            </AccordionContent>
          </AccordionItem>
        </Accordion>
      </CardContent>
    </Card>
  );
}

export function TraceInspectors({ result }: { result: ExperimentModeResult }) {
  const trace = result.trace as any;
  const view = normalizeModeRunDetail(result);
  if (!trace) return null;
  const expansion = trace.expansion_trace ?? {};
  const variants = (expansion.generated_variants ?? []) as TraceRecord[];
  const retrievals = (trace.variant_retrievals ?? []) as TraceRecord[];
  const retrievalByVariantId = new Map(retrievals.map((item) => [String(item.variant_id), item]));
  const statusByVariantId = new Map(view.variantStatuses.map((status) => [status.variant_id, status]));
  const selectedMentions = (expansion.selected_mentions ?? []) as TraceRecord[];
  const alternativesByMention = (expansion.alternatives_by_mention ?? {}) as Record<string, TraceRecord[]>;
  return (
    <div className="space-y-5">
      <section className="space-y-3 rounded-md border p-4">
        <h3 className="text-sm font-semibold">Retrieval Summary</h3>
        <div className="grid grid-cols-2 gap-2 text-xs md:grid-cols-4">
          <Metric label="Status" value={humanRetrievalReason(String(trace.retrieval_reason ?? ""))} />
          <Metric label="Query variants" value={String(trace.total_variant_count ?? variants.length)} />
          <Metric label="Vector searches" value={String(trace.vector_search_call_count ?? retrievals.length)} />
          <Metric label="Final contexts" value={String(trace.final_result_count ?? result.contexts.length)} />
        </div>
      </section>

      <section className="space-y-4 rounded-md border p-4">
        <div>
          <h3 className="text-sm font-semibold">Expansion Trace</h3>
          <p className="mt-1 text-sm text-muted-foreground">Input question</p>
          <p className="mt-1 rounded-md bg-slate-50 p-3 font-medium dark:bg-slate-900/50">{String(expansion.original_query ?? trace.original_query ?? "")}</p>
        </div>
        <div className="grid gap-3 md:grid-cols-2">
          {((expansion.detected_mentions ?? []) as TraceRecord[]).map((mention) => (
            <div key={String(mention.mention_id)} className="rounded-md border bg-white p-3 dark:bg-slate-950">
              <p className="text-xs text-muted-foreground">Detected mention</p>
              <p className="text-base font-semibold">“{String(mention.original_text ?? "")}”</p>
              <div className="mt-2 grid grid-cols-2 gap-2 text-xs text-muted-foreground">
                <span>Characters {String(mention.start_offset)}-{String(mention.end_offset)}</span>
                <span>{scopeLabel(String(mention.approval_status ?? mention.scope ?? ""))}</span>
                <span>Alias group: {String(mention.canonical_name ?? "Unknown")}</span>
                <span>Status: {selectedMentions.some((item) => item.mention_id === mention.mention_id) ? "Selected" : enumLabel(String(mention.eligibility ?? "blocked"))}</span>
              </div>
              <p className="mt-2 text-xs text-muted-foreground">
                Safe alternatives: {(alternativesByMention[String(mention.mention_id)] ?? []).length}
              </p>
            </div>
          ))}
        </div>
        {selectedMentions.map((mention, index) => (
          <ExpansionSlot
            key={String(mention.mention_id)}
            index={index + 1}
            mention={mention}
            alternatives={alternativesByMention[String(mention.mention_id)] ?? []}
          />
        ))}
        <p className="text-sm text-muted-foreground">
          {selectedMentions.length} slot{selectedMentions.length === 1 ? "" : "s"} · {String(expansion.candidate_combination_count ?? 0)} alias candidate combination{Number(expansion.candidate_combination_count ?? 0) === 1 ? "" : "s"} · maximum allowed variants {String(expansion.config_snapshot?.max_query_variants ?? "n/a")} · generated variants {variants.length}
        </p>
        <GeneratedQueries variants={variants} retrievalByVariantId={retrievalByVariantId} statusByVariantId={statusByVariantId} />
      </section>

      <section className="space-y-4 rounded-md border p-4">
        <h3 className="text-sm font-semibold">Queries sent to embedding/vector retrieval</h3>
        <div className="space-y-3">
          {retrievals.map((retrieval, index) => (
            <VectorSearchCard key={String(retrieval.variant_id)} retrieval={retrieval} index={index + 1} />
          ))}
        </div>
      </section>

      <section className="space-y-4 rounded-md border p-4">
        <h3 className="text-sm font-semibold">Weighted RRF fused results</h3>
        <FusedResults results={(trace.fused_results ?? []) as TraceRecord[]} />
      </section>

      <details className="rounded-md border p-3">
        <summary className="cursor-pointer text-sm font-medium">Technical details</summary>
        <pre className="mt-3 max-h-72 overflow-auto rounded bg-slate-950 p-3 text-xs text-slate-100">
          {JSON.stringify({ retrieval_reason: trace.retrieval_reason, variant_statuses: view.variantStatuses }, null, 2)}
        </pre>
      </details>
    </div>
  );
}

function ExpansionSlot({ index, mention, alternatives }: { index: number; mention: TraceRecord; alternatives: TraceRecord[] }) {
  return (
    <div className="rounded-md border bg-slate-50 p-3 dark:bg-slate-900/40">
      <h4 className="text-sm font-semibold">Expansion slot {index}</h4>
      <p className="mt-1 text-sm">Source mention: <span className="font-medium">{String(mention.original_text ?? "")}</span></p>
      <div className="mt-2 grid gap-2 text-sm md:grid-cols-2">
        <Choice label={`Keep original: ${String(mention.original_text ?? "")}`} />
        {alternatives.map((alternative) => (
          <Choice
            key={String(alternative.candidate_uid)}
            label={String(alternative.candidate_text ?? "")}
            detail={enumLabel(String(alternative.relation_type ?? ""))}
          />
        ))}
      </div>
    </div>
  );
}

function Choice({ label, detail }: { label: string; detail?: string }) {
  return (
    <div className="rounded-md border bg-white px-3 py-2 dark:bg-slate-950">
      <span className="mr-2 text-muted-foreground">○</span>
      <span>{label}</span>
      {detail && <span className="ml-2 text-xs text-muted-foreground">{detail}</span>}
    </div>
  );
}

function GeneratedQueries({
  variants,
  retrievalByVariantId,
  statusByVariantId,
}: {
  variants: TraceRecord[];
  retrievalByVariantId: Map<string, TraceRecord>;
  statusByVariantId: Map<string, ReturnType<typeof normalizeModeRunDetail>["variantStatuses"][number]>;
}) {
  return (
    <div className="space-y-3">
      <h4 className="text-sm font-semibold">Generated full queries</h4>
      {variants.map((variant) => {
        const retrieval = retrievalByVariantId.get(String(variant.variant_id));
        const status = statusByVariantId.get(String(variant.variant_id));
        const replacements = (variant.replacements ?? []) as TraceRecord[];
        return (
          <div key={String(variant.variant_id)} className="rounded-md border bg-white p-3 dark:bg-slate-950">
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="outline">Variant {String(variant.variant_index)}</Badge>
              <Badge variant={String(variant.variant_kind) === "original" ? "secondary" : "outline"}>{humanVariantKind(String(variant.variant_kind))}</Badge>
              {status && <Badge variant={status.status === "failed" ? "destructive" : "outline"}>{variantStatusLabel(status)}</Badge>}
            </div>
            <p className="mt-2 text-base font-medium">{String(variant.query_text ?? "")}</p>
            <div className="mt-2 grid gap-2 text-sm md:grid-cols-2">
              <span>Top K: {String(retrieval?.requested_top_k ?? (String(variant.variant_kind) === "original" ? 10 : 5))}</span>
              <span>Replacement: {replacements.length === 0 ? "None" : replacements.map((r) => `${String(r.source_text)} → ${String(r.target_text)}`).join(", ")}</span>
              {replacements.map((replacement) => (
                <span key={`${String(variant.variant_id)}-${String(replacement.target_candidate_uid)}`} className="text-muted-foreground">
                  {String(replacement.canonical_name)} · target relation {enumLabel(String(replacement.target_relation_type))}
                </span>
              ))}
            </div>
            <details className="mt-2">
              <summary className="cursor-pointer text-xs text-muted-foreground">Technical metadata</summary>
              <p className="mt-1 font-mono text-xs text-muted-foreground">variant_id: {String(variant.variant_id)}</p>
            </details>
          </div>
        );
      })}
    </div>
  );
}

function VectorSearchCard({ retrieval, index }: { retrieval: TraceRecord; index: number }) {
  const hits = (retrieval.hits ?? []) as TraceRecord[];
  return (
    <details className="rounded-md border bg-white p-3 open:bg-slate-50 dark:bg-slate-950 dark:open:bg-slate-900/40">
      <summary className="cursor-pointer list-none">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-xs text-muted-foreground">Search {index} · {humanVariantKind(String(retrieval.variant_kind))}</p>
            <p className="mt-1 font-medium">{String(retrieval.query_text ?? "")}</p>
          </div>
          <div className="flex flex-wrap gap-2 text-xs">
            <Badge variant="outline">Top {String(retrieval.requested_top_k ?? "?")}</Badge>
            <Badge variant={retrieval.success ? "outline" : "destructive"}>{retrieval.success ? "Completed" : "Failed"}</Badge>
            <Badge variant="outline">Weight {Number(retrieval.variant_weight ?? 0).toFixed(2)}</Badge>
            <Badge variant="outline">{hits.length} chunks</Badge>
          </div>
        </div>
      </summary>
      <div className="mt-3 overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead className="text-muted-foreground">
            <tr>
              <th className="py-1 pr-3">Rank</th>
              <th className="py-1 pr-3">Story</th>
              <th className="py-1 pr-3">Chunk</th>
              <th className="py-1 pr-3">Preview</th>
            </tr>
          </thead>
          <tbody>
            {hits.map((hit) => (
              <tr key={`${String(retrieval.variant_id)}-${String(hit.chunk_id)}`} className="border-t">
                <td className="py-1 pr-3">{String(hit.rank)}</td>
                <td className="py-1 pr-3">{String(hit.section_title ?? "Unknown")}</td>
                <td className="py-1 pr-3 font-mono">{String(hit.chunk_id)}</td>
                <td className="py-1 pr-3">{preview(String(hit.chunk_text ?? ""))}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}

function FusedResults({ results }: { results: TraceRecord[] }) {
  return (
    <div className="space-y-2">
      {results.map((result) => {
        const contributions = (result.contributions ?? []) as TraceRecord[];
        return (
          <details key={String(result.chunk_id)} className="rounded-md border bg-white p-3 dark:bg-slate-950">
            <summary className="cursor-pointer list-none">
              <div className="grid gap-2 text-sm md:grid-cols-[4rem_1fr_6rem_6rem_6rem] md:items-center">
                <span className="font-semibold">#{String(result.final_rank)}</span>
                <span>
                  <span className="font-medium">{String(result.section_title ?? "Unknown story")}</span>
                  <span className="ml-2 font-mono text-xs text-muted-foreground">{String(result.chunk_id)}</span>
                  <span className="mt-1 block text-xs text-muted-foreground">{preview(String(result.chunk_text ?? ""))}</span>
                </span>
                <span>{String(result.contributing_variant_count ?? contributions.length)} queries</span>
                <span>Orig {result.original_query_rank == null ? "–" : String(result.original_query_rank)}</span>
                <span>{Number(result.fusion_score ?? 0).toFixed(4)}</span>
              </div>
            </summary>
            <div className="mt-3 space-y-2 text-xs">
              <p className="font-medium">Why this chunk ranked #{String(result.final_rank)}</p>
              {contributions.map((contribution) => (
                <div key={`${String(result.chunk_id)}-${String(contribution.variant_id)}`} className="rounded border p-2">
                  <p className="font-medium">{String(contribution.query_text ?? "")}</p>
                  <p className="text-muted-foreground">
                    {humanVariantKind(String(contribution.variant_kind))} · rank {String(contribution.rank)} × weight {Number(contribution.variant_weight ?? 0).toFixed(2)} · contribution {Number(contribution.rrf_contribution ?? 0).toFixed(5)}
                  </p>
                </div>
              ))}
            </div>
          </details>
        );
      })}
    </div>
  );
}

type TraceRecord = Record<string, unknown>;

function AnswerModelInputSummary({ result }: { result: ExperimentModeResult }) {
  return (
    <div className="space-y-3 rounded-md border p-4">
      <h3 className="text-sm font-semibold">What was sent to the answer model</h3>
      <div className="grid gap-2 text-xs md:grid-cols-3">
        <Metric label="Question" value="Original only" />
        <Metric label="Final contexts" value={String(result.contexts.length)} />
        <Metric label="Prompt hash" value={result.rendered_prompt_sha256?.slice(0, 10) ?? "n/a"} />
      </div>
      <p className="text-sm text-muted-foreground">
        Query variants are used only for embedding/vector retrieval. The answer model receives the original user question plus the final fused contexts shown below.
      </p>
    </div>
  );
}

function humanRetrievalReason(reason: string): string {
  if (reason === "alias_expanded_retrieval") return "Alias expansion applied";
  if (reason === "baseline_only_expansion_disabled") return "Baseline only";
  if (reason === "baseline_only_no_variants") return "No alias variants";
  if (reason === "baseline_only_retrieval_disabled") return "Alias retrieval disabled";
  return enumLabel(reason || "unknown");
}

function humanVariantKind(kind: string): string {
  if (kind === "original") return "Original query";
  if (kind === "strong_single") return "Strong single replacement";
  if (kind === "strong_multi") return "Strong multi replacement";
  if (kind === "story_scoped_single") return "Story-scoped replacement";
  if (kind === "mixed") return "Mixed replacements";
  return enumLabel(kind || "variant");
}

function scopeLabel(value: string): string {
  if (value === "approved_strong" || value === "global") return "Global strong alias";
  if (value === "approved_story_scoped" || value === "story_scoped") return "Story-scoped alias";
  return enumLabel(value || "alias");
}

function preview(text: string): string {
  return text.replace(/\s+/g, " ").trim().slice(0, 120) + (text.trim().length > 120 ? "..." : "");
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

import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router";
import { AlertCircle, FlaskConical, Loader2, SlidersHorizontal } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Input } from "@/components/ui/input";
import { compareExperiment, getExperimentCapabilities } from "./api";
import { ComparisonStrip, ModeResultCard } from "./ExperimentViews";
import { MODE_LABELS, MODE_ORDER, type ExperimentApiError, type ExperimentCapabilities, type ExperimentCompareResponse, type RetrievalMode } from "./types";

export default function ExperimentComparePage() {
  const [capabilities, setCapabilities] = useState<ExperimentCapabilities | null>(null);
  const [query, setQuery] = useState("What did Mr. Holmes discover?");
  const [modes, setModes] = useState<RetrievalMode[]>(["baseline", "strong_only", "strong_story"]);
  const [persist, setPersist] = useState(false);
  const [includeTrace, setIncludeTrace] = useState(false);
  const [maxVariants, setMaxVariants] = useState(8);
  const [allowStoryScoped, setAllowStoryScoped] = useState(true);
  const [allowSingleToken, setAllowSingleToken] = useState(true);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ExperimentCompareResponse | null>(null);
  const [error, setError] = useState<ExperimentApiError | Error | null>(null);
  const requestRef = useRef(0);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    getExperimentCapabilities(controller.signal)
      .then((value) => {
        setCapabilities(value);
        setMaxVariants(value.expansion.max_query_variants);
        setAllowStoryScoped(value.expansion.allow_story_scoped);
        setAllowSingleToken(value.expansion.allow_story_scoped_single_token);
        setPersist(value.persistence.required);
      })
      .catch((err) => setError(err instanceof Error ? err : new Error("Unable to load capabilities.")));
    return () => controller.abort();
  }, []);

  const storyControlsEnabled = modes.includes("strong_story") && !!capabilities?.expansion.allow_story_scoped;
  const effectiveIncludeTrace = !persist ? includeTrace : false;
  const comparisonsByMode = useMemo(
    () => new Map(result?.comparisons.map((comparison) => [comparison.compared_mode, comparison]) ?? []),
    [result],
  );

  function toggleMode(mode: RetrievalMode) {
    setModes((current) => {
      if (current.includes(mode)) return current.filter((item) => item !== mode);
      return MODE_ORDER.filter((item) => [...current, mode].includes(item));
    });
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!query.trim() || modes.length === 0 || loading) return;
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    const token = requestRef.current + 1;
    requestRef.current = token;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const response = await compareExperiment(
        {
          query,
          modes,
          persist,
          include_trace: effectiveIncludeTrace,
          expansion_options: {
            max_query_variants: Math.min(maxVariants, capabilities?.expansion.max_query_variants ?? maxVariants),
            allow_story_scoped: storyControlsEnabled ? allowStoryScoped : false,
            allow_story_scoped_single_token: storyControlsEnabled ? allowSingleToken : false,
          },
        },
        controller.signal,
      );
      if (requestRef.current === token) setResult(response);
    } catch (err) {
      if ((err as Error).name !== "AbortError" && requestRef.current === token) {
        setError(err instanceof Error ? err : new Error("Experiment request failed."));
      }
    } finally {
      if (requestRef.current === token) setLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <div className="flex flex-col justify-between gap-4 md:flex-row md:items-end">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Experiment Workbench</h1>
          <p className="text-muted-foreground">Run isolated alias retrieval answer modes without changing the live Ask pipeline.</p>
        </div>
        <Button variant="outline" render={<Link to="/experiments/sessions" />}>Session History</Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FlaskConical className="h-5 w-5" />
            Compare Modes
          </CardTitle>
          <CardDescription>Baseline, strong alias, and story-scoped alias modes share one question and controlled server limits.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={submit} className="space-y-5">
            <textarea
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              className="min-h-28 w-full resize-y rounded-md border bg-white px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring dark:bg-slate-950"
            />
            <div className="grid gap-3 md:grid-cols-3">
              {MODE_ORDER.map((mode) => (
                <button
                  key={mode}
                  type="button"
                  onClick={() => toggleMode(mode)}
                  className={`rounded-md border p-3 text-left transition ${modes.includes(mode) ? "border-primary bg-primary/5" : "bg-white dark:bg-slate-950"}`}
                  aria-pressed={modes.includes(mode)}
                >
                  <span className="block font-medium">{MODE_LABELS[mode]}</span>
                  <span className="text-xs text-muted-foreground">{mode === "baseline" ? "Original query" : mode === "strong_only" ? "Global aliases only" : "Strong plus story aliases"}</span>
                </button>
              ))}
            </div>
            <Collapsible>
              <CollapsibleTrigger
                render={
                  <Button type="button" variant="outline" size="sm">
                    <SlidersHorizontal className="mr-2 h-4 w-4" />
                    Advanced Options
                  </Button>
                }
              />
              <CollapsibleContent className="mt-4 grid gap-4 rounded-md border p-4 md:grid-cols-3">
                <label className="space-y-1 text-sm">
                  <span className="font-medium">Max Variants</span>
                  <Input
                    type="number"
                    min={1}
                    max={capabilities?.expansion.max_query_variants ?? 8}
                    value={maxVariants}
                    onChange={(event) => setMaxVariants(Number(event.target.value))}
                  />
                </label>
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={allowStoryScoped && storyControlsEnabled}
                    disabled={!storyControlsEnabled}
                    onChange={(event) => setAllowStoryScoped(event.target.checked)}
                  />
                  <span>Allow story-scoped aliases</span>
                </label>
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={allowSingleToken && storyControlsEnabled}
                    disabled={!storyControlsEnabled}
                    onChange={(event) => setAllowSingleToken(event.target.checked)}
                  />
                  <span>Allow single-token story aliases</span>
                </label>
                <p className="md:col-span-3 text-xs text-muted-foreground">
                  These options apply only to Strong + Story. Strong Only always disables story-scoped aliases.
                </p>
              </CollapsibleContent>
            </Collapsible>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex flex-wrap items-center gap-3 text-sm">
                {capabilities?.persistence.enabled ? (
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={persist}
                      disabled={capabilities.persistence.required}
                      onChange={(event) => setPersist(event.target.checked)}
                    />
                    <span>{capabilities.persistence.required ? "Save required" : "Save experiment"}</span>
                  </label>
                ) : (
                  <Badge variant="outline">Persistence disabled</Badge>
                )}
                {!persist && (
                  <label className="flex items-center gap-2">
                    <input type="checkbox" checked={includeTrace} onChange={(event) => setIncludeTrace(event.target.checked)} />
                    <span>Return trace for unsaved run</span>
                  </label>
                )}
              </div>
              <Button type="submit" disabled={loading || modes.length === 0 || !query.trim()}>
                {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                Run Comparison
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      {error && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>{(error as ExperimentApiError).detail?.error_code ?? "Experiment failed"}</AlertTitle>
          <AlertDescription className="space-y-2">
            <p>{(error as ExperimentApiError).detail?.message ?? error.message}</p>
            {(error as ExperimentApiError).detail?.error_code === "experiment_persistence_failed" && (
              <p>Turn off Save experiment for an unsaved run, or apply database migration 003 before saving sessions.</p>
            )}
            {(error as ExperimentApiError).detail?.session_id && (
              <Button variant="outline" size="sm" render={<Link to={`/experiments/sessions/${(error as ExperimentApiError).detail?.session_id}`} />}>
                Open saved session
              </Button>
            )}
          </AlertDescription>
        </Alert>
      )}

      {result && (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
            <Badge variant="outline">{result.status}</Badge>
            <span>{result.retrieval_execution_count} retrieval execution(s)</span>
            <span>{result.answer_generation_count} answer generation(s)</span>
            {result.session_id && <Link className="text-primary underline-offset-4 hover:underline" to={`/experiments/sessions/${result.session_id}`}>Open saved session</Link>}
          </div>
          {result.comparisons.map((comparison) => (
            <Card key={comparison.compared_mode}>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm">{MODE_LABELS[comparison.compared_mode]} context comparison</CardTitle>
              </CardHeader>
              <CardContent>
                <ComparisonStrip comparison={comparison} />
              </CardContent>
            </Card>
          ))}
          <div className="grid gap-4 xl:grid-cols-3">
            {MODE_ORDER.filter((mode) => result.results[mode]).map((mode) => (
              <ModeResultCard
                key={mode}
                result={result.results[mode]!}
                comparison={comparisonsByMode.get(mode)}
                persisted={result.persisted}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

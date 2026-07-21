import { useEffect, useState } from "react";
import { Link, useParams } from "react-router";
import { ArrowLeft, Database } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getExperimentSession } from "./api";
import { ModeResultCard } from "./ExperimentViews";
import { enumLabel, modeLabel } from "./adapters";
import type { ExperimentSessionDetail } from "./types";

export default function ExperimentSessionDetailPage() {
  const { sessionId } = useParams();
  const [detail, setDetail] = useState<ExperimentSessionDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!sessionId) return;
    const controller = new AbortController();
    getExperimentSession(sessionId, controller.signal)
      .then((payload) => {
        setDetail(payload);
        setError(null);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Unable to load session."));
    return () => controller.abort();
  }, [sessionId]);

  if (error) return <p className="text-sm text-red-600">{error}</p>;
  if (!detail) return <p className="text-sm text-muted-foreground">Loading session...</p>;

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <Button variant="outline" render={<Link to="/experiments/sessions" />}>
        <ArrowLeft className="mr-2 h-4 w-4" />
        Sessions
      </Button>
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between gap-4">
            <span className="line-clamp-2">{detail.session.query}</span>
            <Badge variant={detail.session.status === "failed" ? "destructive" : "outline"}>{enumLabel(detail.session.status)}</Badge>
          </CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3 text-sm md:grid-cols-4">
          <Meta label="Session" value={detail.session.session_id} />
          <Meta label="Modes" value={detail.session.requested_modes.map(modeLabel).join(", ")} />
          <Meta label="Retrieval Executions" value={String(detail.session.retrieval_execution_count)} />
          <Meta label="Vector Calls" value={String(detail.session.total_vector_search_call_count)} />
          <Meta label="Alias SHA" value={detail.alias_dataset_sha256.slice(0, 12)} />
          <Meta label="Corpus SHA" value={detail.corpus_content_sha256?.slice(0, 12) ?? "n/a"} />
          <Meta label="Git" value={detail.git_commit?.slice(0, 12) ?? "n/a"} />
          <Meta label="Answer Model" value={String(detail.generation_config.model ?? "n/a")} />
        </CardContent>
      </Card>
      <div className="grid gap-4 xl:grid-cols-3">
        {detail.modes.map((mode) => (
          <ModeResultCard key={mode.mode} result={mode} />
        ))}
      </div>
    </div>
  );
}

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border bg-slate-50 p-3 dark:bg-slate-900/40">
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <Database className="h-3.5 w-3.5" />
        {label}
      </div>
      <p className="mt-1 break-all font-mono text-xs">{value}</p>
    </div>
  );
}

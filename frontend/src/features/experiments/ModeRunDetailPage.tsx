import { useEffect, useState } from "react";
import { Link, useParams } from "react-router";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { getExperimentModeRun } from "./api";
import { ModeResultCard } from "./ExperimentViews";
import type { ExperimentModeResult } from "./types";

export default function ExperimentModeRunDetailPage() {
  const { modeRunId } = useParams();
  const [detail, setDetail] = useState<ExperimentModeResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!modeRunId) return;
    const controller = new AbortController();
    getExperimentModeRun(modeRunId, {}, controller.signal)
      .then((payload) => {
        setDetail(payload as ExperimentModeResult);
        setError(null);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Unable to load mode run."));
    return () => controller.abort();
  }, [modeRunId]);

  if (error) return <p className="text-sm text-red-600">{error}</p>;
  if (!detail) return <p className="text-sm text-muted-foreground">Loading mode run...</p>;

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <Button variant="outline" render={<Link to="/experiments/sessions" />}>
        <ArrowLeft className="mr-2 h-4 w-4" />
        Session History
      </Button>
      <ModeResultCard result={detail} />
    </div>
  );
}

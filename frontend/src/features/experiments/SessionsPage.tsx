import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router";
import { History, Search } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { listExperimentSessions } from "./api";
import { enumLabel, modeLabel, safeLimit, safeOffset } from "./adapters";
import { ExperimentNav } from "./ExperimentNav";
import type { ExperimentSessionSummary } from "./types";

export default function ExperimentSessionsPage() {
  const [params, setParams] = useSearchParams();
  const [sessions, setSessions] = useState<ExperimentSessionSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const filters = useMemo(
    () => ({
      status: params.get("status") ?? "",
      mode: params.get("mode") ?? "",
      created_after: params.get("created_after") ?? "",
      created_before: params.get("created_before") ?? "",
      limit: safeLimit(params.get("limit")),
      offset: safeOffset(params.get("offset")),
    }),
    [params],
  );

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    listExperimentSessions(filters, controller.signal)
      .then((payload) => {
        setSessions(payload.sessions);
        setError(null);
      })
      .catch((err) => {
        if ((err as Error).name !== "AbortError") setError(err instanceof Error ? err.message : "Unable to load sessions.");
      })
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, [filters]);

  function updateFilter(key: string, value: string) {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    next.set("offset", "0");
    setParams(next);
  }

  function page(delta: number) {
    const next = new URLSearchParams(params);
    next.set("offset", String(Math.max(0, filters.offset + delta * filters.limit)));
    next.set("limit", String(filters.limit));
    setParams(next);
  }

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <div className="flex flex-col justify-between gap-4 md:flex-row md:items-end">
        <div>
          <h1 className="flex items-center gap-2 text-3xl font-bold tracking-tight">
            <History className="h-7 w-7" />
            Experiment Sessions
          </h1>
          <p className="text-muted-foreground">Saved interactive experiment runs, loaded without full traces or context text by default.</p>
        </div>
        <ExperimentNav active="history" />
      </div>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Filters</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-5">
          <Input placeholder="status" value={filters.status} onChange={(event) => updateFilter("status", event.target.value)} />
          <Input placeholder="mode" value={filters.mode} onChange={(event) => updateFilter("mode", event.target.value)} />
          <Input type="datetime-local" value={filters.created_after.slice(0, 16)} onChange={(event) => updateFilter("created_after", event.target.value ? new Date(event.target.value).toISOString() : "")} />
          <Input type="datetime-local" value={filters.created_before.slice(0, 16)} onChange={(event) => updateFilter("created_before", event.target.value ? new Date(event.target.value).toISOString() : "")} />
          <Input type="number" min={1} max={200} value={filters.limit} onChange={(event) => updateFilter("limit", event.target.value)} />
        </CardContent>
      </Card>
      {error && <p className="text-sm text-red-600">{error}</p>}
      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Started</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Modes</TableHead>
                <TableHead>Query</TableHead>
                <TableHead className="text-right">Calls</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {sessions.map((session) => (
                <TableRow key={session.session_id}>
                  <TableCell className="whitespace-nowrap text-sm">{new Date(session.started_at).toLocaleString()}</TableCell>
                  <TableCell>
                    <Badge variant={session.status === "failed" ? "destructive" : "outline"}>{enumLabel(session.status)}</Badge>
                  </TableCell>
                  <TableCell className="space-x-1">
                    {session.requested_modes.map((mode) => (
                      <Badge key={mode} variant="secondary">{modeLabel(mode)}</Badge>
                    ))}
                  </TableCell>
                  <TableCell>
                    <Link className="line-clamp-2 text-primary underline-offset-4 hover:underline" to={`/experiments/sessions/${session.session_id}`}>
                      {session.query}
                    </Link>
                  </TableCell>
                  <TableCell className="text-right">{session.total_vector_search_call_count}</TableCell>
                </TableRow>
              ))}
              {!loading && sessions.length === 0 && (
                <TableRow>
                  <TableCell colSpan={5} className="h-24 text-center text-muted-foreground">
                    <Search className="mx-auto mb-2 h-5 w-5" />
                    No sessions found.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
      <div className="flex justify-end gap-2">
        <Button variant="outline" onClick={() => page(-1)} disabled={filters.offset === 0}>Previous</Button>
        <Button variant="outline" onClick={() => page(1)} disabled={sessions.length < filters.limit}>Next</Button>
      </div>
    </div>
  );
}

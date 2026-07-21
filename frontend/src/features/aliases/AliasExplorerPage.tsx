import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router";
import { Search, Tags } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { getAliasStatus, listAliasGroups, lookupAliasSurface } from "./api";
import type { AliasGroupsResponse, AliasLookupResponse, AliasStatus } from "./types";

export default function AliasExplorerPage() {
  const [params, setParams] = useSearchParams();
  const [status, setStatus] = useState<AliasStatus | null>(null);
  const [groups, setGroups] = useState<AliasGroupsResponse | null>(null);
  const [lookupText, setLookupText] = useState("Mr. Holmes");
  const [lookup, setLookup] = useState<AliasLookupResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const filters = useMemo(
    () => ({
      search: params.get("search") ?? "",
      scope: params.get("scope") ?? "",
      entity_type: params.get("entity_type") ?? "",
      story_id: params.get("story_id") ?? "",
      limit: Number(params.get("limit") ?? 50),
      offset: Number(params.get("offset") ?? 0),
    }),
    [params],
  );

  useEffect(() => {
    const controller = new AbortController();
    getAliasStatus(controller.signal).then(setStatus).catch((err) => setError(err instanceof Error ? err.message : "Unable to load alias status."));
    return () => controller.abort();
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    listAliasGroups(filters, controller.signal).then(setGroups).catch((err) => setError(err instanceof Error ? err.message : "Unable to load aliases."));
    return () => controller.abort();
  }, [filters]);

  function updateFilter(key: string, value: string) {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    next.set("offset", "0");
    setParams(next);
  }

  async function runLookup(event: React.FormEvent) {
    event.preventDefault();
    try {
      setLookup(await lookupAliasSurface(lookupText));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Lookup failed.");
    }
  }

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <div>
        <h1 className="flex items-center gap-2 text-3xl font-bold tracking-tight">
          <Tags className="h-7 w-7" />
          Alias Explorer
        </h1>
        <p className="text-muted-foreground">Browse the frozen alias dataset and run exact normalized surface lookup.</p>
      </div>
      {error && <p className="text-sm text-red-600">{error}</p>}
      {status && (
        <div className="grid gap-3 md:grid-cols-4">
          <Stat label="Dataset" value={status.file_name} />
          <Stat label="Groups" value={String(status.approved_group_count)} />
          <Stat label="Generatable" value={String(status.generatable_member_count)} />
          <Stat label="SHA" value={status.sha256.slice(0, 12)} />
        </div>
      )}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Surface Lookup</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">Exact normalized surface lookup, not sentence mention detection.</p>
          <form onSubmit={runLookup} className="flex flex-col gap-2 md:flex-row">
            <Input value={lookupText} onChange={(event) => setLookupText(event.target.value)} />
            <Button type="submit">
              <Search className="mr-2 h-4 w-4" />
              Lookup
            </Button>
          </form>
          {lookup && (
            <div className="grid gap-3 md:grid-cols-2">
              <LookupColumn title="Generatable" members={lookup.generatable_matches} />
              <LookupColumn title="Normalization Only" members={lookup.normalization_only_matches} />
            </div>
          )}
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Groups</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-2 md:grid-cols-4">
            <Input placeholder="Search" value={filters.search} onChange={(event) => updateFilter("search", event.target.value)} />
            <Input placeholder="Scope" value={filters.scope} onChange={(event) => updateFilter("scope", event.target.value)} />
            <Input placeholder="Entity Type" value={filters.entity_type} onChange={(event) => updateFilter("entity_type", event.target.value)} />
            <Input placeholder="Story ID" value={filters.story_id} onChange={(event) => updateFilter("story_id", event.target.value)} />
          </div>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Scope</TableHead>
                <TableHead>Type</TableHead>
                <TableHead className="text-right">Members</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(groups?.groups ?? []).map((group) => (
                <TableRow key={group.group_id}>
                  <TableCell>
                    <Link className="text-primary underline-offset-4 hover:underline" to={`/aliases/groups/${group.group_id}`}>
                      {group.canonical_name}
                    </Link>
                    {!group.canonical_name_is_generatable && <Badge className="ml-2" variant="outline">Display only</Badge>}
                  </TableCell>
                  <TableCell>{group.scope}</TableCell>
                  <TableCell>{group.entity_type}</TableCell>
                  <TableCell className="text-right">{group.generatable_member_count}/{group.member_count}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <Card>
      <CardContent className="p-4">
        <p className="text-xs text-muted-foreground">{label}</p>
        <p className="mt-1 truncate font-mono text-sm">{value}</p>
      </CardContent>
    </Card>
  );
}

function LookupColumn({ title, members }: { title: string; members: AliasLookupResponse["generatable_matches"] }) {
  return (
    <div className="rounded-md border p-3">
      <h3 className="font-medium">{title}</h3>
      {members.length === 0 ? (
        <p className="mt-2 text-sm text-muted-foreground">No matches.</p>
      ) : (
        <div className="mt-2 space-y-2">
          {members.map((member) => (
            <div key={member.candidate_uid} className="text-sm">
              <Link className="text-primary underline-offset-4 hover:underline" to={`/aliases/groups/${member.group_id}`}>
                {member.candidate_text}
              </Link>
              <p className="text-xs text-muted-foreground">{member.canonical_name} · {member.relation_type}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

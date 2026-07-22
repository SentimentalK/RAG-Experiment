import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Link, useSearchParams } from "react-router";
import { ArrowDown, ArrowUp, ArrowUpDown, Search, Tags } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { getAliasStatus, listAliasGroups, lookupAliasSurface } from "./api";
import type { AliasGroupSummary, AliasGroupsResponse, AliasLookupResponse, AliasStatus } from "./types";

type SortKey = "canonical_name" | "scope" | "entity_type" | "generatable_member_count";
type SortDirection = "asc" | "desc";

export default function AliasExplorerPage({ embedded = false }: { embedded?: boolean }) {
  const [params, setParams] = useSearchParams();
  const [status, setStatus] = useState<AliasStatus | null>(null);
  const [groups, setGroups] = useState<AliasGroupsResponse | null>(null);
  const [allGroups, setAllGroups] = useState<AliasGroupSummary[]>([]);
  const [lookupText, setLookupText] = useState("Mr. Holmes");
  const [lookup, setLookup] = useState<AliasLookupResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sort, setSort] = useState<{ key: SortKey; direction: SortDirection }>({
    key: "canonical_name",
    direction: "asc",
  });
  const filters = useMemo(
    () => ({
      search: params.get("search") ?? "",
      scope: params.get("scope") ?? "",
      entity_type: params.get("entity_type") ?? "",
      story_id: params.get("story_id") ?? "",
      showcase_only: params.get("showcase_only") === "true",
      review_status: params.get("review_status") ?? "",
      retrieval_value: params.get("retrieval_value") ?? "",
      pattern_tag: params.get("pattern_tag") ?? "",
      limit: clampNumber(params.get("limit"), 50, 1, 200),
      offset: clampNumber(params.get("offset"), 0, 0, Number.MAX_SAFE_INTEGER),
    }),
    [params],
  );
  const sortedGroups = useMemo(() => sortGroups(groups?.groups ?? [], sort), [groups, sort]);
  const scopeOptions = useMemo(() => uniqueOptions(allGroups.map((group) => group.scope)), [allGroups]);
  const entityTypeOptions = useMemo(() => uniqueOptions(allGroups.map((group) => group.entity_type)), [allGroups]);
  const storyOptions = useMemo(() => uniqueOptions(allGroups.flatMap((group) => group.story_ids)), [allGroups]);
  const patternTagOptions = useMemo(() => uniqueOptions(allGroups.flatMap((group) => group.curation.pattern_tags)), [allGroups]);
  const searchOptions = useMemo(
    () => [...allGroups].sort((a, b) => a.canonical_name.localeCompare(b.canonical_name) || a.group_id.localeCompare(b.group_id)),
    [allGroups],
  );
  const detailBasePath = embedded ? "/data/aliases/groups" : "/aliases/groups";
  const detailSearch = params.toString();

  useEffect(() => {
    const controller = new AbortController();
    getAliasStatus(controller.signal).then(setStatus).catch((err) => setError(err instanceof Error ? err.message : "Unable to load alias status."));
    return () => controller.abort();
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    listAliasGroups({ limit: 200, offset: 0 }, controller.signal)
      .then((payload) => setAllGroups(payload.groups))
      .catch((err) => setError(err instanceof Error ? err.message : "Unable to load alias filters."));
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

  function updateLimit(value: string | null) {
    const next = new URLSearchParams(params);
    next.set("limit", value || "50");
    next.set("offset", "0");
    setParams(next);
  }

  function updatePage(delta: number) {
    const next = new URLSearchParams(params);
    next.set("limit", String(filters.limit));
    next.set("offset", String(Math.max(0, filters.offset + delta * filters.limit)));
    setParams(next);
  }

  function toggleSort(key: SortKey) {
    setSort((current) => ({
      key,
      direction: current.key === key && current.direction === "asc" ? "desc" : "asc",
    }));
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
    <div className={embedded ? "space-y-6" : "mx-auto max-w-7xl space-y-6"}>
      {!embedded && (
        <div>
          <h1 className="flex items-center gap-2 text-3xl font-bold tracking-tight">
            <Tags className="h-7 w-7" />
            Alias Explorer
          </h1>
          <p className="text-muted-foreground">Browse the frozen alias dataset and run exact normalized surface lookup.</p>
          <p className="mt-2 max-w-4xl text-sm text-muted-foreground">
            Global aliases are safe to substitute across the whole corpus. Story aliases are only safe inside one specific story, where that surface stays tied to the same entity.
          </p>
        </div>
      )}
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
              <LookupColumn title="Generatable" members={lookup.generatable_matches} detailBasePath={detailBasePath} detailSearch={detailSearch} />
              <LookupColumn
                title="Normalization Only"
                members={lookup.normalization_only_matches}
                detailBasePath={detailBasePath}
                detailSearch={detailSearch}
              />
            </div>
          )}
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Groups</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-2 md:grid-cols-5">
            <AliasSelect label="Group" value={filters.search || "all"} onValueChange={(value) => updateFilter("search", value === "all" ? "" : value ?? "")}>
              <SelectItem value="all">All groups</SelectItem>
              {searchOptions.map((group) => (
                <SelectItem key={group.group_id} value={group.canonical_name}>
                  {group.canonical_name}
                </SelectItem>
              ))}
            </AliasSelect>
            <AliasSelect label="Scope" value={filters.scope || "all"} onValueChange={(value) => updateFilter("scope", value === "all" ? "" : value ?? "")}>
              <SelectItem value="all">All scopes</SelectItem>
              {scopeOptions.map((scope) => (
                <SelectItem key={scope} value={scope}>{formatAliasScope(scope)}</SelectItem>
              ))}
            </AliasSelect>
            <AliasSelect label="Entity" value={filters.entity_type || "all"} onValueChange={(value) => updateFilter("entity_type", value === "all" ? "" : value ?? "")}>
              <SelectItem value="all">All entity types</SelectItem>
              {entityTypeOptions.map((entityType) => (
                <SelectItem key={entityType} value={entityType}>{entityType}</SelectItem>
              ))}
            </AliasSelect>
            <AliasSelect label="Story" value={filters.story_id || "all"} onValueChange={(value) => updateFilter("story_id", value === "all" ? "" : value ?? "")}>
              <SelectItem value="all">All stories</SelectItem>
              {storyOptions.map((storyId) => (
                <SelectItem key={storyId} value={storyId}>{storyId}</SelectItem>
              ))}
            </AliasSelect>
            <AliasSelect label="Page size" value={String(filters.limit)} onValueChange={updateLimit}>
              {[25, 50, 100, 200].map((size) => (
                <SelectItem key={size} value={String(size)}>{size} rows</SelectItem>
              ))}
            </AliasSelect>
          </div>
          <div className="grid gap-2 md:grid-cols-4">
            <AliasSelect label="Showcase" value={filters.showcase_only ? "true" : "all"} onValueChange={(value) => updateFilter("showcase_only", value === "true" ? "true" : "")}>
              <SelectItem value="all">All groups</SelectItem>
              <SelectItem value="true">Showcase only</SelectItem>
            </AliasSelect>
            <AliasSelect label="Review" value={filters.review_status || "all"} onValueChange={(value) => updateFilter("review_status", value === "all" ? "" : value ?? "")}>
              <SelectItem value="all">All review statuses</SelectItem>
              <SelectItem value="reviewed">Reviewed</SelectItem>
              <SelectItem value="pending">Pending</SelectItem>
            </AliasSelect>
            <AliasSelect label="Retrieval value" value={filters.retrieval_value || "all"} onValueChange={(value) => updateFilter("retrieval_value", value === "all" ? "" : value ?? "")}>
              <SelectItem value="all">All values</SelectItem>
              <SelectItem value="high">High</SelectItem>
              <SelectItem value="medium">Medium</SelectItem>
              <SelectItem value="low">Low</SelectItem>
              <SelectItem value="not_reviewed">Not reviewed</SelectItem>
            </AliasSelect>
            <AliasSelect label="Pattern" value={filters.pattern_tag || "all"} onValueChange={(value) => updateFilter("pattern_tag", value === "all" ? "" : value ?? "")}>
              <SelectItem value="all">All patterns</SelectItem>
              {patternTagOptions.map((tag) => (
                <SelectItem key={tag} value={tag}>{formatTag(tag)}</SelectItem>
              ))}
            </AliasSelect>
          </div>
          <Table>
            <TableHeader>
              <TableRow>
                <SortableHead label="Name" sortKey="canonical_name" activeSort={sort} onSort={toggleSort} />
                <SortableHead label="Scope" sortKey="scope" activeSort={sort} onSort={toggleSort} />
                <SortableHead label="Type" sortKey="entity_type" activeSort={sort} onSort={toggleSort} />
                <TableHead>Curation</TableHead>
                <SortableHead label="Members" sortKey="generatable_member_count" activeSort={sort} onSort={toggleSort} className="text-right" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {sortedGroups.map((group) => (
                <TableRow key={group.group_id}>
                  <TableCell>
                    <Link
                      className="text-primary underline-offset-4 hover:underline"
                      to={`${detailBasePath}/${group.group_id}${detailSearch ? `?${detailSearch}` : ""}`}
                    >
                      {group.canonical_name}
                    </Link>
                    {!group.canonical_name_is_generatable && <Badge className="ml-2" variant="outline">Display only</Badge>}
                  </TableCell>
                  <TableCell>{formatAliasScope(group.scope)}</TableCell>
                  <TableCell>{group.entity_type}</TableCell>
                  <TableCell>
                    <div className="flex flex-wrap gap-1">
                      {group.curation.showcase && <Badge variant="secondary">Showcase #{group.curation.showcase_rank}</Badge>}
                      <Badge variant="outline">{formatReviewStatus(group.curation.review_status)}</Badge>
                      <Badge variant="outline">{formatRetrievalValue(group.curation.retrieval_value)}</Badge>
                      {group.curation.pattern_tags.slice(0, 2).map((tag) => (
                        <Badge key={tag} variant="outline">{formatTag(tag)}</Badge>
                      ))}
                    </div>
                  </TableCell>
                  <TableCell className="text-right">{group.generatable_member_count}/{group.member_count}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <div className="flex flex-col gap-3 border-t pt-4 text-sm text-muted-foreground md:flex-row md:items-center md:justify-between">
            <span>
              Showing {groups ? Math.min(groups.offset + 1, groups.total) : 0}-
              {groups ? Math.min(groups.offset + groups.groups.length, groups.total) : 0} of {groups?.total ?? 0}
            </span>
            <div className="flex gap-2">
              <Button type="button" variant="outline" onClick={() => updatePage(-1)} disabled={filters.offset === 0}>
                Previous
              </Button>
              <Button type="button" variant="outline" onClick={() => updatePage(1)} disabled={!groups || filters.offset + filters.limit >= groups.total}>
                Next
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function AliasSelect({
  label,
  value,
  onValueChange,
  children,
}: {
  label: string;
  value: string;
  onValueChange: (value: string | null) => void;
  children: ReactNode;
}) {
  return (
    <label className="space-y-1 text-xs font-medium text-muted-foreground">
      <span>{label}</span>
      <Select value={value} onValueChange={onValueChange}>
        <SelectTrigger className="w-full">
          <SelectValue />
        </SelectTrigger>
        <SelectContent align="start">{children}</SelectContent>
      </Select>
    </label>
  );
}

function SortableHead({
  label,
  sortKey,
  activeSort,
  onSort,
  className,
}: {
  label: string;
  sortKey: SortKey;
  activeSort: { key: SortKey; direction: SortDirection };
  onSort: (key: SortKey) => void;
  className?: string;
}) {
  const active = activeSort.key === sortKey;
  const Icon = !active ? ArrowUpDown : activeSort.direction === "asc" ? ArrowUp : ArrowDown;
  return (
    <TableHead className={className}>
      <Button type="button" variant="ghost" size="sm" className={className?.includes("text-right") ? "ml-auto" : ""} onClick={() => onSort(sortKey)}>
        {label}
        <Icon className="ml-1 h-3.5 w-3.5" />
      </Button>
    </TableHead>
  );
}

function sortGroups(groups: AliasGroupSummary[], sort: { key: SortKey; direction: SortDirection }): AliasGroupSummary[] {
  const direction = sort.direction === "asc" ? 1 : -1;
  return [...groups].sort((left, right) => {
    const leftValue = left[sort.key];
    const rightValue = right[sort.key];
    if (typeof leftValue === "number" && typeof rightValue === "number") {
      return (leftValue - rightValue || left.canonical_name.localeCompare(right.canonical_name)) * direction;
    }
    return (String(leftValue).localeCompare(String(rightValue)) || left.canonical_name.localeCompare(right.canonical_name)) * direction;
  });
}

function uniqueOptions(values: string[]): string[] {
  return [...new Set(values.filter(Boolean))].sort((left, right) => left.localeCompare(right));
}

function formatAliasScope(scope: string): string {
  if (scope === "global") return "Global";
  if (scope === "story_scoped") return "Story";
  return scope;
}

function formatReviewStatus(status: string): string {
  if (status === "reviewed") return "Reviewed";
  if (status === "pending") return "Pending review";
  return status;
}

function formatRetrievalValue(value: string | null): string {
  if (value === "high") return "High value";
  if (value === "medium") return "Medium value";
  if (value === "low") return "Low value";
  return "Not reviewed";
}

function formatTag(tag: string): string {
  return tag.replaceAll("_", " ");
}

function clampNumber(value: string | null, fallback: number, min: number, max: number): number {
  const parsed = Number(value ?? fallback);
  if (!Number.isFinite(parsed)) return fallback;
  return Math.min(max, Math.max(min, Math.trunc(parsed)));
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

function LookupColumn({
  title,
  members,
  detailBasePath,
  detailSearch,
}: {
  title: string;
  members: AliasLookupResponse["generatable_matches"];
  detailBasePath: string;
  detailSearch: string;
}) {
  return (
    <div className="rounded-md border p-3">
      <h3 className="font-medium">{title}</h3>
      {members.length === 0 ? (
        <p className="mt-2 text-sm text-muted-foreground">No matches.</p>
      ) : (
        <div className="mt-2 space-y-2">
          {members.map((member) => (
            <div key={member.candidate_uid} className="text-sm">
              <Link
                className="text-primary underline-offset-4 hover:underline"
                to={`${detailBasePath}/${member.group_id}${detailSearch ? `?${detailSearch}` : ""}`}
              >
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

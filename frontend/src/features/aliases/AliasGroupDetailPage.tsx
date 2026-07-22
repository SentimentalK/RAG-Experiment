import { useEffect, useMemo, useState } from "react";
import { Link, useLocation, useParams } from "react-router";
import { ArrowLeft, Tags } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getAliasGroup } from "./api";
import type { AliasGroupDetail, AliasMember } from "./types";

export default function AliasGroupDetailPage() {
  const { groupId } = useParams();
  const location = useLocation();
  const [group, setGroup] = useState<AliasGroupDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const backHref = useMemo(() => {
    const search = location.search || "?tab=aliases";
    return location.pathname.startsWith("/data/") ? `/data${search}` : `/data${search}`;
  }, [location.pathname, location.search]);

  useEffect(() => {
    if (!groupId) return;
    const controller = new AbortController();
    getAliasGroup(groupId, controller.signal)
      .then((payload) => {
        setGroup(payload);
        setError(null);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Unable to load alias group."));
    return () => controller.abort();
  }, [groupId]);

  if (error) return <p className="text-sm text-red-600">{error}</p>;
  if (!group) return <p className="text-sm text-muted-foreground">Loading group...</p>;

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <Button variant="outline" render={<Link to={backHref} />}>
        <ArrowLeft className="mr-2 h-4 w-4" />
        Alias Explorer
      </Button>
      <Card>
        <CardHeader>
          <CardTitle className="flex flex-wrap items-center gap-2">
            <Tags className="h-5 w-5" />
            {group.canonical_name}
            {!group.canonical_name_is_generatable && <Badge variant="outline">Display label only</Badge>}
          </CardTitle>
          <p className="text-sm text-muted-foreground">
            Global groups are safe to substitute across the whole corpus. Story groups are only safe inside the specific story context where that surface remains unambiguous.
          </p>
        </CardHeader>
        <CardContent className="grid gap-3 text-sm md:grid-cols-4">
          <Meta label="Group ID" value={group.group_id} />
          <Meta label="Scope" value={formatAliasScope(group.scope)} />
          <Meta label="Entity Type" value={group.entity_type} />
          <Meta label="Story IDs" value={group.story_ids.join(", ") || "Global"} />
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Human Curation</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4 text-sm">
          <div className="flex flex-wrap gap-2">
            <Badge variant="outline">{group.curation.source === "explicit" ? "Explicit curation" : "Implicit default"}</Badge>
            <Badge variant="outline">{formatReviewStatus(group.curation.review_status)}</Badge>
            <Badge variant="outline">{formatRetrievalValue(group.curation.retrieval_value)}</Badge>
            {group.curation.showcase && <Badge variant="secondary">Showcase #{group.curation.showcase_rank}</Badge>}
            {group.curation.pattern_tags.map((tag) => (
              <Badge key={tag} variant="outline">{formatTag(tag)}</Badge>
            ))}
          </div>
          {group.curation.review_note ? (
            <p className="leading-relaxed text-muted-foreground">{group.curation.review_note}</p>
          ) : (
            <p className="text-muted-foreground">No human review note yet.</p>
          )}
          <RecommendedPairs group={group} />
          <ExampleQuestions group={group} />
        </CardContent>
      </Card>
      <div className="grid gap-4 lg:grid-cols-2">
        <MemberPanel title="Generatable Members" members={group.generatable_members} />
        <MemberPanel title="Normalization-only Members" members={group.normalization_only_members} />
      </div>
      <MemberPanel title="All Members" members={group.members} />
    </div>
  );
}

function formatReviewStatus(status: string): string {
  if (status === "reviewed") return "Reviewed";
  if (status === "pending") return "Pending review";
  return status;
}

function formatRetrievalValue(value: string | null): string {
  if (value === "high") return "High retrieval value";
  if (value === "medium") return "Medium retrieval value";
  if (value === "low") return "Low retrieval value";
  return "Retrieval value not reviewed";
}

function formatTag(tag: string): string {
  return tag.replaceAll("_", " ");
}

function RecommendedPairs({ group }: { group: AliasGroupDetail }) {
  const members = new Map(group.members.map((member) => [member.candidate_uid, member]));
  if (group.curation.recommended_pairs.length === 0) {
    return <p className="text-muted-foreground">No recommended demo pairs yet.</p>;
  }
  return (
    <div className="space-y-2">
      <h3 className="font-medium">Recommended demo pairs</h3>
      {group.curation.recommended_pairs.map((pair) => {
        const source = members.get(pair.source_candidate_uid);
        const target = members.get(pair.target_candidate_uid);
        return (
          <div key={`${pair.source_candidate_uid}-${pair.target_candidate_uid}`} className="rounded-md border p-3">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-medium">{pair.label || `${source?.candidate_text ?? pair.source_candidate_uid} to ${target?.candidate_text ?? pair.target_candidate_uid}`}</span>
              <Badge variant="outline">{pair.value}</Badge>
            </div>
            <p className="mt-1 font-mono text-xs text-muted-foreground">
              {pair.source_candidate_uid} to {pair.target_candidate_uid}
            </p>
          </div>
        );
      })}
    </div>
  );
}

function ExampleQuestions({ group }: { group: AliasGroupDetail }) {
  if (group.curation.example_questions.length === 0) {
    return <p className="text-muted-foreground">No example questions yet.</p>;
  }
  return (
    <div className="space-y-2">
      <h3 className="font-medium">Example questions</h3>
      {group.curation.example_questions.map((question) => (
        <div key={question.question} className="rounded-md border p-3">
          <p className="font-medium">{question.question}</p>
          <p className="mt-1 text-muted-foreground">{question.expected_answer}</p>
          <p className="mt-1 text-xs text-muted-foreground">{question.purpose}</p>
        </div>
      ))}
    </div>
  );
}

function formatAliasScope(scope: string): string {
  if (scope === "global") return "Global";
  if (scope === "story_scoped") return "Story";
  return scope;
}

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border bg-slate-50 p-3 dark:bg-slate-900/40">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-1 break-all font-mono text-xs">{value}</p>
    </div>
  );
}

function MemberPanel({ title, members }: { title: string; members: AliasMember[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{title}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {members.length === 0 ? (
          <p className="text-sm text-muted-foreground">No members.</p>
        ) : (
          members.map((member) => (
            <div key={member.candidate_uid} className="rounded-md border p-3">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-medium">{member.candidate_text}</span>
                <Badge variant="outline">{member.relation_type}</Badge>
                {member.dataset_unique_active_surface ? <Badge variant="secondary">Unique active</Badge> : <Badge variant="outline">Active conflict</Badge>}
                {member.dataset_unique_generatable_surface && <Badge variant="outline">Unique generatable</Badge>}
              </div>
              <p className="mt-1 font-mono text-xs text-muted-foreground">{member.candidate_uid}</p>
              {member.substitution_constraints.length > 0 && (
                <p className="mt-1 text-xs text-muted-foreground">Constraints: {member.substitution_constraints.join(", ")}</p>
              )}
              {member.evidence_sentences.length > 0 && (
                <p className="mt-2 line-clamp-3 text-sm leading-relaxed">{member.evidence_sentences[0]}</p>
              )}
            </div>
          ))
        )}
      </CardContent>
    </Card>
  );
}

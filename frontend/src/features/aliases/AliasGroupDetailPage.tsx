import { useEffect, useState } from "react";
import { Link, useParams } from "react-router";
import { ArrowLeft, Tags } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getAliasGroup } from "./api";
import type { AliasGroupDetail, AliasMember } from "./types";

export default function AliasGroupDetailPage() {
  const { groupId } = useParams();
  const [group, setGroup] = useState<AliasGroupDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

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
      <Button variant="outline" render={<Link to="/data?tab=aliases" />}>
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
        </CardHeader>
        <CardContent className="grid gap-3 text-sm md:grid-cols-4">
          <Meta label="Group ID" value={group.group_id} />
          <Meta label="Scope" value={group.scope} />
          <Meta label="Entity Type" value={group.entity_type} />
          <Meta label="Story IDs" value={group.story_ids.join(", ") || "Global"} />
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

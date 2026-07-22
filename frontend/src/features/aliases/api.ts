import type { AliasGroupDetail, AliasGroupsResponse, AliasLookupResponse, AliasStatus } from "./types";

async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    throw new Error(payload?.detail ?? `Request failed with status ${response.status}.`);
  }
  return payload as T;
}

export function getAliasStatus(signal?: AbortSignal): Promise<AliasStatus> {
  return requestJson<AliasStatus>("/api/aliases/status", { signal });
}

export function listAliasGroups(
  filters: {
    scope?: string;
    entity_type?: string;
    story_id?: string;
    search?: string;
    showcase_only?: boolean;
    review_status?: string;
    retrieval_value?: string;
    pattern_tag?: string;
    limit?: number;
    offset?: number;
  },
  signal?: AbortSignal,
): Promise<AliasGroupsResponse> {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== null && String(value) !== "") params.set(key, String(value));
  });
  return requestJson(`/api/aliases/groups?${params.toString()}`, { signal });
}

export function getAliasGroup(groupId: string, signal?: AbortSignal): Promise<AliasGroupDetail> {
  return requestJson<AliasGroupDetail>(`/api/aliases/groups/${encodeURIComponent(groupId)}`, { signal });
}

export function lookupAliasSurface(surface: string, signal?: AbortSignal): Promise<AliasLookupResponse> {
  const params = new URLSearchParams({ surface });
  return requestJson<AliasLookupResponse>(`/api/aliases/lookup?${params.toString()}`, { signal });
}

export interface AliasStatus {
  loaded: boolean;
  dataset_filename: string;
  dataset_sha256: string;
  expected_sha256: string | null;
  strict_validation: boolean;
  group_count: number;
  approved_strong_group_count: number;
  approved_story_scoped_group_count: number;
  generatable_member_count: number;
  normalization_only_member_count: number;
  final_disposition_count: number;
  warning_count: number;
  warnings: string[];
}

export interface AliasMember {
  candidate_uid: string;
  candidate_text: string;
  normalized_surface: string;
  group_id: string;
  canonical_name: string;
  entity_type: string;
  approval_status: string;
  scope: string;
  story_ids: string[];
  relation_type: string;
  safe_to_substitute: boolean;
  substitution_constraints: string[];
  dataset_unique_active_surface: boolean;
  dataset_unique_generatable_surface: boolean;
  token_count: number;
  character_count: number;
  is_generatable: boolean;
  is_normalization_only: boolean;
  evidence_story_ids: string[];
  evidence_sentences: string[];
  review_reason: string | null;
}

export interface AliasGroupSummary {
  group_id: string;
  canonical_name: string;
  canonical_name_is_generatable: boolean;
  entity_type: string;
  scope: string;
  story_ids: string[];
  approval_status: string;
  group_confidence: number | null;
  safe_for_query_substitution: boolean;
  member_count: number;
  generatable_member_count: number;
  normalization_only_member_count: number;
}

export interface AliasGroupDetail extends AliasGroupSummary {
  group_review_reason: string | null;
  members: AliasMember[];
  generatable_members: AliasMember[];
  normalization_only_members: AliasMember[];
}

export interface AliasGroupsResponse {
  total: number;
  limit: number;
  offset: number;
  groups: AliasGroupSummary[];
}

export interface AliasLookupResponse {
  input_surface: string;
  normalized_surface: string;
  generatable_matches: AliasMember[];
  normalization_only_matches: AliasMember[];
  dataset_unique_active_surface: boolean;
  dataset_unique_generatable_surface: boolean;
}

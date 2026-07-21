import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator


EXPECTED_ALIAS_DATASET_SHA256 = "2b16f62f2537c0703985585a8e467cda14d0790a3fad3258c31439322cfd5dd7"
APPROVED_STATUSES = {"approved_strong", "approved_story_scoped"}
DASH_CHARS = {
    "\u2010",
    "\u2011",
    "\u2012",
    "\u2013",
    "\u2014",
    "\u2015",
    "\u2212",
}
APOSTROPHE_CHARS = {
    "\u2018",
    "\u2019",
    "\u201a",
    "\u201b",
    "\u2032",
    "\uff07",
}


class AliasDatasetError(RuntimeError):
    """Raised when alias dataset loading or validation fails."""


class AliasMember(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    candidate_uid: str
    candidate_text: str
    relation_type: str
    same_entity: bool
    member_disposition: str
    safe_to_substitute: bool
    substitution_constraints: tuple[str, ...] = ()
    evidence_story_ids: tuple[str, ...] = ()
    evidence_sentences: tuple[str, ...] = ()
    review_reason: str | None = None

    @field_validator("candidate_uid", "candidate_text")
    @classmethod
    def non_empty_required_string(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("must be non-empty")
        return value


class AliasGroup(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    group_id: str
    canonical_name: str
    entity_type: str
    scope: str
    story_ids: tuple[str, ...] = ()
    approval_status: str
    group_confidence: str
    safe_for_query_substitution: bool
    members: tuple[AliasMember, ...]
    removed_members: tuple[Any, ...] = ()
    group_review_reason: str | None = None

    @field_validator("group_id", "canonical_name")
    @classmethod
    def non_empty_required_string(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("must be non-empty")
        return value

    @field_validator("scope")
    @classmethod
    def allowed_scope(cls, value: str) -> str:
        if value not in {"global", "story_scoped"}:
            raise ValueError("unsupported scope")
        return value

    @field_validator("approval_status")
    @classmethod
    def allowed_approval_status(cls, value: str) -> str:
        if value not in APPROVED_STATUSES:
            raise ValueError("unsupported approval_status")
        return value


class CandidateFinalDisposition(BaseModel):
    model_config = ConfigDict(frozen=True, extra="allow")

    candidate_uid: str
    candidate_text: str
    final_category: str
    group_id: str | None = None
    notes: str | None = None

    @field_validator("candidate_uid", "candidate_text")
    @classmethod
    def non_empty_required_string(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("must be non-empty")
        return value


class AliasDatasetDocument(BaseModel):
    model_config = ConfigDict(frozen=True, extra="allow")

    metadata: Mapping[str, Any]
    validation_summary: Mapping[str, Any]
    approved_groups: tuple[AliasGroup, ...]
    rejected_groups: tuple[Any, ...] = ()
    excluded_candidates: tuple[Any, ...] = ()
    ambiguous_candidates: tuple[Any, ...] = ()
    review_required_groups: tuple[Any, ...] = ()
    split_required: tuple[Any, ...] = ()
    singletons: tuple[Any, ...] = ()
    invalid_generated_candidates: tuple[Any, ...] = ()
    narrative_identity_relations: tuple[Any, ...] = ()
    candidate_final_dispositions: tuple[CandidateFinalDisposition, ...]


class AliasMemberReference(BaseModel):
    model_config = ConfigDict(frozen=True)

    candidate_uid: str
    candidate_text: str
    normalized_surface: str
    group_id: str
    canonical_name: str
    entity_type: str
    approval_status: str
    scope: str
    story_ids: tuple[str, ...]
    relation_type: str
    same_entity: bool
    safe_to_substitute: bool
    substitution_constraints: tuple[str, ...]
    member_disposition: str
    evidence_story_ids: tuple[str, ...]
    evidence_sentences: tuple[str, ...]
    review_reason: str | None
    dataset_unique_active_surface: bool
    dataset_unique_generatable_surface: bool
    token_count: int
    character_count: int
    is_generatable: bool
    is_normalization_only: bool


class CompiledAliasGroup(BaseModel):
    model_config = ConfigDict(frozen=True)

    group_id: str
    canonical_name: str
    entity_type: str
    scope: str
    story_ids: tuple[str, ...]
    approval_status: str
    group_confidence: str
    safe_for_query_substitution: bool
    members: tuple[AliasMemberReference, ...]
    generatable_members: tuple[AliasMemberReference, ...]
    normalization_only_members: tuple[AliasMemberReference, ...]
    removed_members: tuple[Any, ...]
    group_review_reason: str | None


class AliasValidationSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    computed_counts: Mapping[str, int] = Field(default_factory=dict)


class AliasDatasetSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    source_file_name: str
    source_file_path: str
    sha256: str
    loaded_at: datetime
    metadata: Mapping[str, Any]
    validation_summary: AliasValidationSummary
    groups: tuple[CompiledAliasGroup, ...]
    rejected_groups: tuple[Any, ...]
    excluded_candidates: tuple[Any, ...]
    singletons: tuple[Any, ...]
    split_required: tuple[Any, ...]
    narrative_identity_relations: tuple[Any, ...]
    final_dispositions: tuple[CandidateFinalDisposition, ...]


class AliasDatasetStatus(BaseModel):
    model_config = ConfigDict(frozen=True)

    loaded: bool
    file_name: str
    sha256: str
    loaded_at: datetime
    approved_group_count: int
    approved_strong_group_count: int
    approved_story_scoped_group_count: int
    generatable_member_count: int
    normalization_only_member_count: int
    final_disposition_count: int
    validation_warning_count: int


def normalize_alias_surface(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text)
    normalized = "".join("'" if char in APOSTROPHE_CHARS else char for char in normalized)
    normalized = "".join("-" if char in DASH_CHARS else char for char in normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized.casefold()


def _token_count(normalized_surface: str) -> int:
    if not normalized_surface:
        return 0
    return len(normalized_surface.split())


def _is_generatable(group: AliasGroup, member: AliasMember) -> bool:
    return (
        group.approval_status in APPROVED_STATUSES
        and member.same_entity
        and member.safe_to_substitute
        and "do_not_generate" not in member.substitution_constraints
    )


def _is_normalization_only(member: AliasMember) -> bool:
    return member.same_entity and not member.safe_to_substitute


def _metadata_bool(document: AliasDatasetDocument, key: str) -> bool:
    return bool(document.metadata.get(key))


def _freeze_json_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: _freeze_json_value(item) for key, item in value.items()})
    if isinstance(value, list | tuple):
        return tuple(_freeze_json_value(item) for item in value)
    return value


def _validate_document_semantics(document: AliasDatasetDocument, strict: bool) -> AliasValidationSummary:
    errors: list[str] = []
    warnings: list[str] = []

    group_ids = [group.group_id for group in document.approved_groups]
    duplicate_group_ids = sorted(group_id for group_id, count in Counter(group_ids).items() if count > 1)
    if duplicate_group_ids:
        errors.append(f"duplicate active group_id values: {duplicate_group_ids}")

    active_uids = [member.candidate_uid for group in document.approved_groups for member in group.members]
    duplicate_active_uids = sorted(uid for uid, count in Counter(active_uids).items() if count > 1)
    if duplicate_active_uids:
        errors.append(f"duplicate active candidate_uid values: {duplicate_active_uids}")

    disposition_uids = [item.candidate_uid for item in document.candidate_final_dispositions]
    duplicate_disposition_uids = sorted(uid for uid, count in Counter(disposition_uids).items() if count > 1)
    if duplicate_disposition_uids:
        errors.append(f"duplicate final disposition candidate_uid values: {duplicate_disposition_uids}")

    for group in document.approved_groups:
        if group.approval_status == "approved_strong" and group.scope != "global":
            errors.append(f"{group.group_id}: approved_strong must have global scope")
        if group.approval_status == "approved_story_scoped":
            if group.scope != "story_scoped":
                errors.append(f"{group.group_id}: approved_story_scoped must have story_scoped scope")
            if not group.story_ids:
                errors.append(f"{group.group_id}: story_scoped group must have story_ids")
        generatable_count = sum(1 for member in group.members if _is_generatable(group, member))
        if generatable_count < 2:
            errors.append(f"{group.group_id}: approved group must have at least two generatable members")
        group_member_texts = {member.candidate_text for member in group.members if _is_generatable(group, member)}
        if group.canonical_name not in group_member_texts:
            warnings.append(f"{group.group_id}: canonical_name is not a generatable member")
        if any(_token_count(normalize_alias_surface(member.candidate_text)) == 1 for member in group.members if _is_generatable(group, member)):
            warnings.append(f"{group.group_id}: contains single-token generatable members")

    for key in ("all_input_candidates_accounted_for", "all_output_uids_in_allowlist", "active_group_members_unique"):
        if not _metadata_bool(document, key):
            errors.append(f"metadata.{key} must be true")

    if int(document.validation_summary.get("unresolved_status_count", -1)) != 0:
        errors.append("validation_summary.unresolved_status_count must be 0")

    computed_counts = {
        "approved_group_count": len(document.approved_groups),
        "approved_strong_group_count": sum(1 for group in document.approved_groups if group.approval_status == "approved_strong"),
        "approved_story_scoped_group_count": sum(1 for group in document.approved_groups if group.approval_status == "approved_story_scoped"),
        "generatable_member_count": sum(1 for group in document.approved_groups for member in group.members if _is_generatable(group, member)),
        "active_normalization_only_member_count": sum(
            1 for group in document.approved_groups for member in group.members if _is_normalization_only(member)
        ),
        "final_disposition_count": len(document.candidate_final_dispositions),
    }
    metadata_count_checks = {
        "approved_strong_group_count": computed_counts["approved_strong_group_count"],
        "approved_story_scoped_group_count": computed_counts["approved_story_scoped_group_count"],
        "input_candidate_count": computed_counts["final_disposition_count"],
    }
    for key, computed in metadata_count_checks.items():
        metadata_value = document.metadata.get(key)
        if metadata_value is not None and int(metadata_value) != computed:
            message = f"metadata.{key}={metadata_value} does not match computed value {computed}"
            if strict:
                errors.append(message)
            else:
                warnings.append(message)

    metadata_norm_only = document.metadata.get("normalization_only_candidate_count")
    if metadata_norm_only is not None:
        final_norm_only = sum(
            1 for item in document.candidate_final_dispositions if item.final_category.startswith("normalization_only")
        )
        if int(metadata_norm_only) != final_norm_only:
            message = (
                "metadata.normalization_only_candidate_count="
                f"{metadata_norm_only} does not match final disposition normalization-only count {final_norm_only}"
            )
            if strict:
                errors.append(message)
            else:
                warnings.append(message)

    return AliasValidationSummary(errors=tuple(errors), warnings=tuple(warnings), computed_counts=MappingProxyType(computed_counts))


def _compile_groups(
    document: AliasDatasetDocument,
) -> tuple[
    tuple[CompiledAliasGroup, ...],
    Mapping[str, AliasMemberReference],
    Mapping[str, tuple[AliasMemberReference, ...]],
    Mapping[str, tuple[AliasMemberReference, ...]],
    Mapping[str, tuple[AliasMemberReference, ...]],
    Mapping[str, frozenset[str]],
    Mapping[str, frozenset[str]],
]:
    active_surface_group_ids: dict[str, set[str]] = defaultdict(set)
    generatable_surface_group_ids: dict[str, set[str]] = defaultdict(set)

    for group in document.approved_groups:
        for member in group.members:
            if not member.same_entity:
                continue
            normalized = normalize_alias_surface(member.candidate_text)
            active_surface_group_ids[normalized].add(group.group_id)
            if _is_generatable(group, member):
                generatable_surface_group_ids[normalized].add(group.group_id)

    compiled_groups: list[CompiledAliasGroup] = []
    member_by_uid: dict[str, AliasMemberReference] = {}
    members_by_surface: dict[str, list[AliasMemberReference]] = defaultdict(list)
    generatable_by_surface: dict[str, list[AliasMemberReference]] = defaultdict(list)
    normalization_only_by_surface: dict[str, list[AliasMemberReference]] = defaultdict(list)

    for group in document.approved_groups:
        refs: list[AliasMemberReference] = []
        generatable_refs: list[AliasMemberReference] = []
        normalization_refs: list[AliasMemberReference] = []
        for member in group.members:
            normalized = normalize_alias_surface(member.candidate_text)
            is_generatable = _is_generatable(group, member)
            is_normalization_only = _is_normalization_only(member)
            reference = AliasMemberReference(
                candidate_uid=member.candidate_uid,
                candidate_text=member.candidate_text,
                normalized_surface=normalized,
                group_id=group.group_id,
                canonical_name=group.canonical_name,
                entity_type=group.entity_type,
                approval_status=group.approval_status,
                scope=group.scope,
                story_ids=group.story_ids,
                relation_type=member.relation_type,
                same_entity=member.same_entity,
                safe_to_substitute=member.safe_to_substitute,
                substitution_constraints=member.substitution_constraints,
                member_disposition=member.member_disposition,
                evidence_story_ids=member.evidence_story_ids,
                evidence_sentences=member.evidence_sentences,
                review_reason=member.review_reason,
                dataset_unique_active_surface=len(active_surface_group_ids.get(normalized, set())) == 1,
                dataset_unique_generatable_surface=len(generatable_surface_group_ids.get(normalized, set())) == 1,
                token_count=_token_count(normalized),
                character_count=len(normalized),
                is_generatable=is_generatable,
                is_normalization_only=is_normalization_only,
            )
            refs.append(reference)
            member_by_uid[reference.candidate_uid] = reference
            if member.same_entity:
                members_by_surface[normalized].append(reference)
            if is_generatable:
                generatable_refs.append(reference)
                generatable_by_surface[normalized].append(reference)
            elif is_normalization_only:
                normalization_refs.append(reference)
                normalization_only_by_surface[normalized].append(reference)

        compiled_groups.append(
            CompiledAliasGroup(
                group_id=group.group_id,
                canonical_name=group.canonical_name,
                entity_type=group.entity_type,
                scope=group.scope,
                story_ids=group.story_ids,
                approval_status=group.approval_status,
                group_confidence=group.group_confidence,
                safe_for_query_substitution=group.safe_for_query_substitution,
                members=tuple(_sort_members(refs)),
                generatable_members=tuple(_sort_members(generatable_refs)),
                normalization_only_members=tuple(_sort_members(normalization_refs)),
                removed_members=group.removed_members,
                group_review_reason=group.group_review_reason,
            )
        )

    return (
        tuple(sorted(compiled_groups, key=lambda item: (item.canonical_name.casefold(), item.group_id))),
        MappingProxyType(member_by_uid),
        _freeze_surface_mapping(members_by_surface),
        _freeze_surface_mapping(generatable_by_surface),
        _freeze_surface_mapping(normalization_only_by_surface),
        MappingProxyType({key: frozenset(value) for key, value in active_surface_group_ids.items()}),
        MappingProxyType({key: frozenset(value) for key, value in generatable_surface_group_ids.items()}),
    )


def _sort_members(members: list[AliasMemberReference] | tuple[AliasMemberReference, ...]) -> list[AliasMemberReference]:
    return sorted(
        members,
        key=lambda member: (-member.token_count, -member.character_count, member.candidate_text.casefold(), member.candidate_uid),
    )


def _lookup_sort_key(member: AliasMemberReference) -> tuple[int, int, str, str]:
    scope_rank = 0 if member.approval_status == "approved_strong" else 1
    return (scope_rank, member.canonical_name.casefold(), member.candidate_uid, member.candidate_text.casefold())


def _freeze_surface_mapping(
    mapping: Mapping[str, list[AliasMemberReference]],
) -> Mapping[str, tuple[AliasMemberReference, ...]]:
    return MappingProxyType({key: tuple(sorted(value, key=_lookup_sort_key)) for key, value in mapping.items()})


class AliasRegistry:
    def __init__(
        self,
        *,
        snapshot: AliasDatasetSnapshot,
        group_by_id: Mapping[str, CompiledAliasGroup],
        member_by_uid: Mapping[str, AliasMemberReference],
        final_disposition_by_uid: Mapping[str, CandidateFinalDisposition],
        members_by_normalized_surface: Mapping[str, tuple[AliasMemberReference, ...]],
        generatable_members_by_surface: Mapping[str, tuple[AliasMemberReference, ...]],
        normalization_only_members_by_surface: Mapping[str, tuple[AliasMemberReference, ...]],
        groups_by_scope: Mapping[str, tuple[CompiledAliasGroup, ...]],
        groups_by_story_id: Mapping[str, tuple[CompiledAliasGroup, ...]],
        normalized_surface_to_active_group_ids: Mapping[str, frozenset[str]],
        normalized_surface_to_generatable_group_ids: Mapping[str, frozenset[str]],
        matchable_surfaces_sorted: tuple[str, ...],
    ) -> None:
        self.snapshot = snapshot
        self.group_by_id = MappingProxyType(dict(group_by_id))
        self.member_by_uid = MappingProxyType(dict(member_by_uid))
        self.final_disposition_by_uid = MappingProxyType(dict(final_disposition_by_uid))
        self.members_by_normalized_surface = members_by_normalized_surface
        self.generatable_members_by_surface = generatable_members_by_surface
        self.normalization_only_members_by_surface = normalization_only_members_by_surface
        self.groups_by_scope = MappingProxyType(dict(groups_by_scope))
        self.groups_by_story_id = MappingProxyType(dict(groups_by_story_id))
        self.normalized_surface_to_active_group_ids = normalized_surface_to_active_group_ids
        self.normalized_surface_to_generatable_group_ids = normalized_surface_to_generatable_group_ids
        self.matchable_surfaces_sorted = matchable_surfaces_sorted

    @classmethod
    def load(
        cls,
        path: str | Path,
        *,
        expected_sha256: str | None = EXPECTED_ALIAS_DATASET_SHA256,
        strict_validation: bool = True,
    ) -> "AliasRegistry":
        source_path = Path(path).expanduser().resolve()
        try:
            raw_bytes = source_path.read_bytes()
        except FileNotFoundError as exc:
            raise AliasDatasetError(f"Alias dataset file not found: {source_path}") from exc

        actual_sha256 = hashlib.sha256(raw_bytes).hexdigest()
        hash_warning: str | None = None
        if expected_sha256 and actual_sha256 != expected_sha256:
            message = f"Alias dataset SHA-256 mismatch: expected {expected_sha256}, actual {actual_sha256}"
            if strict_validation:
                raise AliasDatasetError(message)
            hash_warning = message

        try:
            raw_document = json.loads(raw_bytes)
        except json.JSONDecodeError as exc:
            raise AliasDatasetError(f"Alias dataset is not valid JSON: {exc}") from exc

        try:
            document = AliasDatasetDocument.model_validate(raw_document)
        except ValidationError as exc:
            raise AliasDatasetError(f"Alias dataset schema validation failed: {exc}") from exc

        summary = _validate_document_semantics(document, strict_validation)
        if summary.errors:
            raise AliasDatasetError("; ".join(summary.errors))

        (
            compiled_groups,
            member_by_uid,
            members_by_surface,
            generatable_by_surface,
            normalization_only_by_surface,
            active_surface_group_ids,
            generatable_surface_group_ids,
        ) = _compile_groups(document)

        compiled_warnings = list(summary.warnings)
        if hash_warning:
            compiled_warnings.append(hash_warning)
        for surface, group_ids in active_surface_group_ids.items():
            if len(group_ids) > 1:
                compiled_warnings.append(f"surface conflict for {surface!r}: {sorted(group_ids)}")

        compiled_errors = _validate_compiled_indexes(
            compiled_groups=compiled_groups,
            member_by_uid=member_by_uid,
            generatable_by_surface=generatable_by_surface,
            normalization_only_by_surface=normalization_only_by_surface,
        )
        if compiled_errors:
            raise AliasDatasetError("; ".join(compiled_errors))

        final_summary = AliasValidationSummary(
            errors=(),
            warnings=tuple(sorted(compiled_warnings)),
            computed_counts=summary.computed_counts,
        )
        snapshot = AliasDatasetSnapshot(
            source_file_name=source_path.name,
            source_file_path=str(source_path),
            sha256=actual_sha256,
            loaded_at=datetime.now(timezone.utc),
            metadata=MappingProxyType(dict(document.metadata)),
            validation_summary=final_summary,
            groups=compiled_groups,
            rejected_groups=_freeze_json_value(document.rejected_groups),
            excluded_candidates=_freeze_json_value(document.excluded_candidates),
            singletons=_freeze_json_value(document.singletons),
            split_required=_freeze_json_value(document.split_required),
            narrative_identity_relations=_freeze_json_value(document.narrative_identity_relations),
            final_dispositions=document.candidate_final_dispositions,
        )

        group_by_id = MappingProxyType({group.group_id: group for group in compiled_groups})
        final_disposition_by_uid = MappingProxyType({item.candidate_uid: item for item in document.candidate_final_dispositions})
        groups_by_scope = {
            "global": tuple(group for group in compiled_groups if group.scope == "global"),
            "story_scoped": tuple(group for group in compiled_groups if group.scope == "story_scoped"),
        }
        story_groups: dict[str, list[CompiledAliasGroup]] = defaultdict(list)
        for group in compiled_groups:
            if group.scope != "story_scoped":
                continue
            for story_id in group.story_ids:
                story_groups[story_id].append(group)
        groups_by_story_id = MappingProxyType(
            {story_id: tuple(sorted(groups, key=lambda item: (item.canonical_name.casefold(), item.group_id))) for story_id, groups in story_groups.items()}
        )
        matchable_surfaces = tuple(
            sorted(
                generatable_by_surface.keys(),
                key=lambda surface: (-_token_count(surface), -len(surface), surface),
            )
        )

        return cls(
            snapshot=snapshot,
            group_by_id=group_by_id,
            member_by_uid=member_by_uid,
            final_disposition_by_uid=final_disposition_by_uid,
            members_by_normalized_surface=members_by_surface,
            generatable_members_by_surface=generatable_by_surface,
            normalization_only_members_by_surface=normalization_only_by_surface,
            groups_by_scope=MappingProxyType(groups_by_scope),
            groups_by_story_id=groups_by_story_id,
            normalized_surface_to_active_group_ids=active_surface_group_ids,
            normalized_surface_to_generatable_group_ids=generatable_surface_group_ids,
            matchable_surfaces_sorted=matchable_surfaces,
        )

    def get_group(self, group_id: str) -> CompiledAliasGroup | None:
        return self.group_by_id.get(group_id)

    def get_member_by_uid(self, candidate_uid: str) -> AliasMemberReference | None:
        return self.member_by_uid.get(candidate_uid)

    def find_by_surface(
        self,
        surface: str,
        include_normalization_only: bool = False,
    ) -> tuple[AliasMemberReference, ...]:
        normalized = normalize_alias_surface(surface)
        generatable = self.generatable_members_by_surface.get(normalized, ())
        if not include_normalization_only:
            return generatable
        normalization_only = self.normalization_only_members_by_surface.get(normalized, ())
        return tuple(sorted((*generatable, *normalization_only), key=lambda item: (not item.is_generatable, *_lookup_sort_key(item))))

    def lookup_surface(self, surface: str) -> tuple[str, tuple[AliasMemberReference, ...], tuple[AliasMemberReference, ...]]:
        normalized = normalize_alias_surface(surface)
        return (
            normalized,
            self.generatable_members_by_surface.get(normalized, ()),
            self.normalization_only_members_by_surface.get(normalized, ()),
        )

    def get_generatable_members(self, group_id: str) -> tuple[AliasMemberReference, ...]:
        group = self.get_group(group_id)
        if group is None:
            return ()
        return group.generatable_members

    def get_groups_for_story(self, story_id: str) -> tuple[CompiledAliasGroup, ...]:
        return self.groups_by_story_id.get(story_id, ())

    def is_dataset_unique_surface(self, surface: str) -> bool:
        normalized = normalize_alias_surface(surface)
        return len(self.normalized_surface_to_active_group_ids.get(normalized, frozenset())) == 1

    def get_status(self) -> AliasDatasetStatus:
        counts = self.snapshot.validation_summary.computed_counts
        return AliasDatasetStatus(
            loaded=True,
            file_name=self.snapshot.source_file_name,
            sha256=self.snapshot.sha256,
            loaded_at=self.snapshot.loaded_at,
            approved_group_count=counts["approved_group_count"],
            approved_strong_group_count=counts["approved_strong_group_count"],
            approved_story_scoped_group_count=counts["approved_story_scoped_group_count"],
            generatable_member_count=counts["generatable_member_count"],
            normalization_only_member_count=counts["active_normalization_only_member_count"],
            final_disposition_count=counts["final_disposition_count"],
            validation_warning_count=len(self.snapshot.validation_summary.warnings),
        )


def _validate_compiled_indexes(
    *,
    compiled_groups: tuple[CompiledAliasGroup, ...],
    member_by_uid: Mapping[str, AliasMemberReference],
    generatable_by_surface: Mapping[str, tuple[AliasMemberReference, ...]],
    normalization_only_by_surface: Mapping[str, tuple[AliasMemberReference, ...]],
) -> tuple[str, ...]:
    errors: list[str] = []
    group_ids = {group.group_id for group in compiled_groups}
    for surface, members in generatable_by_surface.items():
        for member in members:
            if member.group_id not in group_ids or member.candidate_uid not in member_by_uid:
                errors.append(f"generatable index has dangling reference for surface {surface!r}")
            if not member.same_entity or not member.safe_to_substitute or "do_not_generate" in member.substitution_constraints:
                errors.append(f"generatable index contains unsafe member {member.candidate_uid}")
    for surface, members in normalization_only_by_surface.items():
        for member in members:
            if member.group_id not in group_ids or member.candidate_uid not in member_by_uid:
                errors.append(f"normalization-only index has dangling reference for surface {surface!r}")
            if member.safe_to_substitute:
                errors.append(f"normalization-only index contains substitutable member {member.candidate_uid}")
    return tuple(errors)

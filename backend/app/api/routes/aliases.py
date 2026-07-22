from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from app.api.dependencies import get_alias_registry, get_expanded_retrieval_service, get_query_expansion_service
from app.services.alias_registry import (
    AliasMemberReference,
    AliasRegistry,
    CompiledAliasGroup,
    RuntimeAliasGroupCuration,
    normalize_alias_surface,
)
from app.services.expanded_retrieval_service import ExpandedRetrievalError, ExpandedRetrievalService
from app.services.query_expansion_service import QueryExpansionRequestOptions, QueryExpansionService


router = APIRouter(prefix="/aliases", tags=["aliases"])


class AliasExpandRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1)
    options: QueryExpansionRequestOptions | None = None


class AliasRetrieveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1)
    document_id: str = Field(default="gutenberg-1661", min_length=1)
    expansion_options: QueryExpansionRequestOptions | None = None


def _member_payload(member: AliasMemberReference) -> dict:
    return {
        "candidate_uid": member.candidate_uid,
        "candidate_text": member.candidate_text,
        "normalized_surface": member.normalized_surface,
        "group_id": member.group_id,
        "canonical_name": member.canonical_name,
        "entity_type": member.entity_type,
        "approval_status": member.approval_status,
        "scope": member.scope,
        "story_ids": list(member.story_ids),
        "relation_type": member.relation_type,
        "safe_to_substitute": member.safe_to_substitute,
        "substitution_constraints": list(member.substitution_constraints),
        "dataset_unique_active_surface": member.dataset_unique_active_surface,
        "dataset_unique_generatable_surface": member.dataset_unique_generatable_surface,
        "token_count": member.token_count,
        "character_count": member.character_count,
        "is_generatable": member.is_generatable,
        "is_normalization_only": member.is_normalization_only,
        "evidence_story_ids": list(member.evidence_story_ids),
        "evidence_sentences": list(member.evidence_sentences),
        "review_reason": member.review_reason,
    }


def _curation_payload(curation: RuntimeAliasGroupCuration) -> dict:
    return {
        "source": curation.source,
        "review_status": curation.review_status,
        "retrieval_value": curation.retrieval_value,
        "showcase": curation.showcase,
        "showcase_rank": curation.showcase_rank,
        "pattern_tags": list(curation.pattern_tags),
        "review_note": curation.review_note,
        "recommended_pairs": [pair.model_dump(mode="json") for pair in curation.recommended_pairs],
        "example_questions": [question.model_dump(mode="json") for question in curation.example_questions],
    }


def _group_summary(group: CompiledAliasGroup, curation: RuntimeAliasGroupCuration) -> dict:
    canonical_surface = normalize_alias_surface(group.canonical_name)
    return {
        "group_id": group.group_id,
        "canonical_name": group.canonical_name,
        "canonical_name_is_generatable": any(
            member.normalized_surface == canonical_surface for member in group.generatable_members
        ),
        "entity_type": group.entity_type,
        "scope": group.scope,
        "story_ids": list(group.story_ids),
        "approval_status": group.approval_status,
        "group_confidence": group.group_confidence,
        "safe_for_query_substitution": group.safe_for_query_substitution,
        "member_count": len(group.members),
        "generatable_member_count": len(group.generatable_members),
        "normalization_only_member_count": len(group.normalization_only_members),
        "curation": _curation_payload(curation),
    }


def _group_detail(group: CompiledAliasGroup, curation: RuntimeAliasGroupCuration) -> dict:
    payload = _group_summary(group, curation)
    payload.update(
        {
            "group_review_reason": group.group_review_reason,
            "members": [_member_payload(member) for member in group.members],
            "generatable_members": [_member_payload(member) for member in group.generatable_members],
            "normalization_only_members": [_member_payload(member) for member in group.normalization_only_members],
        }
    )
    return payload


@router.get("/status")
def alias_status(registry: AliasRegistry = Depends(get_alias_registry)) -> dict:
    status = registry.get_status()
    return status.model_dump(mode="json")


@router.get("/groups")
def list_alias_groups(
    registry: AliasRegistry = Depends(get_alias_registry),
    scope: str | None = None,
    entity_type: str | None = None,
    story_id: str | None = None,
    search: str | None = None,
    showcase_only: bool = False,
    review_status: str | None = None,
    retrieval_value: str | None = None,
    pattern_tag: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict:
    groups = list(registry.snapshot.groups)
    if scope is not None:
        groups = [group for group in groups if group.scope == scope]
    if entity_type is not None:
        groups = [group for group in groups if group.entity_type == entity_type]
    if story_id is not None:
        groups = [group for group in groups if story_id in group.story_ids]
    if showcase_only:
        groups = [group for group in groups if registry.get_curation(group.group_id).showcase]
    if review_status is not None:
        groups = [group for group in groups if registry.get_curation(group.group_id).review_status == review_status]
    if retrieval_value is not None:
        if retrieval_value == "not_reviewed":
            groups = [group for group in groups if registry.get_curation(group.group_id).retrieval_value is None]
        else:
            groups = [group for group in groups if registry.get_curation(group.group_id).retrieval_value == retrieval_value]
    if pattern_tag is not None:
        groups = [group for group in groups if pattern_tag in registry.get_curation(group.group_id).pattern_tags]
    if search:
        needle = search.casefold()
        groups = [
            group
            for group in groups
            if needle in group.canonical_name.casefold()
            or needle in group.group_id.casefold()
            or any(needle in member.candidate_text.casefold() for member in group.members)
        ]

    if showcase_only:
        groups = sorted(
            groups,
            key=lambda group: (
                registry.get_curation(group.group_id).showcase_rank or 10**9,
                group.canonical_name.casefold(),
                group.group_id,
            ),
        )
    else:
        groups = sorted(groups, key=lambda group: (group.canonical_name.casefold(), group.group_id))
    total = len(groups)
    page = groups[offset : offset + limit]
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "groups": [_group_summary(group, registry.get_curation(group.group_id)) for group in page],
    }


@router.get("/groups/{group_id}")
def get_alias_group(group_id: str, registry: AliasRegistry = Depends(get_alias_registry)) -> dict:
    group = registry.get_group(group_id)
    if group is None:
        raise HTTPException(status_code=404, detail="Alias group not found")
    return _group_detail(group, registry.get_curation(group_id))


@router.get("/lookup")
def lookup_alias_surface(
    surface: Annotated[str, Query(min_length=1)],
    registry: AliasRegistry = Depends(get_alias_registry),
) -> dict:
    normalized_surface, generatable_matches, normalization_only_matches = registry.lookup_surface(surface)
    return {
        "input_surface": surface,
        "normalized_surface": normalized_surface,
        "generatable_matches": [_member_payload(member) for member in generatable_matches],
        "normalization_only_matches": [_member_payload(member) for member in normalization_only_matches],
        "dataset_unique_active_surface": registry.is_dataset_unique_surface(surface),
        "dataset_unique_generatable_surface": (
            len(registry.normalized_surface_to_generatable_group_ids.get(normalize_alias_surface(surface), frozenset())) == 1
        ),
    }


@router.post("/expand")
def expand_alias_query(
    payload: AliasExpandRequest,
    service: QueryExpansionService = Depends(get_query_expansion_service),
) -> dict:
    trace = service.expand(payload.query, config_override=payload.options)
    return trace.model_dump(mode="json")


@router.post("/retrieve")
def retrieve_alias_query(
    payload: AliasRetrieveRequest,
    service: ExpandedRetrievalService = Depends(get_expanded_retrieval_service),
) -> dict:
    try:
        trace = service.retrieve(
            payload.query,
            document_id=payload.document_id,
            expansion_options=payload.expansion_options,
        )
    except ExpandedRetrievalError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception:
        raise HTTPException(status_code=503, detail="Expanded retrieval failed.")
    return trace.model_dump(mode="json")

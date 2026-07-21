import hashlib
import itertools
import logging
import re
import unicodedata
from collections import defaultdict
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.services.alias_registry import (
    APOSTROPHE_CHARS,
    DASH_CHARS,
    AliasMemberReference,
    AliasRegistry,
    normalize_alias_surface,
)


logger = logging.getLogger("app.services.query_expansion")

BLOCKING_GENERATION_CONSTRAINTS = {
    "do_not_generate",
    "possessive_slot_only",
    "boundary_cleanup_required",
    "plural_or_collective",
}
SUPPORTED_SINGLE_TOKEN_STORY_ENTITY_TYPES = {
    "PERSON",
    "ORGANIZATION",
    "PRODUCT",
    "PROJECT_CODENAME",
}
HIGH_VALUE_RELATIONS = {
    "surname_variant",
    "first_name_variant",
    "shortened_name",
    "initials",
    "abbreviation",
    "extended_name",
    "contextual_reference",
    "spelling_variant",
    "orthographic_variant",
}
RELATION_SCORES = {
    "initials": 40,
    "abbreviation": 40,
    "shortened_name": 35,
    "surname_variant": 35,
    "first_name_variant": 30,
    "extended_name": 30,
    "contextual_reference": 25,
    "spelling_variant": 20,
    "orthographic_variant": 20,
    "title_variant": 10,
    "exact_name": 10,
    "determiner_variant": 2,
}
VARIANT_KIND_RANK = {
    "strong_single": 1,
    "strong_multi": 2,
    "story_scoped_single": 3,
    "mixed": 4,
}


class OffsetSpan(BaseModel):
    model_config = ConfigDict(frozen=True)

    original_start: int
    original_end: int


class NormalizedQuery(BaseModel):
    model_config = ConfigDict(frozen=True)

    original_text: str
    normalized_text: str
    normalized_to_original_offsets: tuple[OffsetSpan, ...]

    def original_span(self, normalized_start: int, normalized_end: int) -> OffsetSpan:
        if normalized_start < 0 or normalized_end > len(self.normalized_to_original_offsets) or normalized_start >= normalized_end:
            raise ValueError("Invalid normalized span.")
        return OffsetSpan(
            original_start=self.normalized_to_original_offsets[normalized_start].original_start,
            original_end=self.normalized_to_original_offsets[normalized_end - 1].original_end,
        )


class QueryExpansionConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    enabled: bool = True
    max_query_variants: int = 8
    max_selected_mentions: int = 3
    max_strong_alternatives_per_mention: int = 3
    max_story_scoped_alternatives_per_mention: int = 2
    strong_variant_budget: int = 5
    story_scoped_variant_budget: int = 2
    max_story_scoped_replacements_per_variant: int = 1
    max_replacements_per_variant: int = 3
    allow_story_scoped: bool = True
    allow_story_scoped_single_token: bool = True
    require_unique_story_scoped_surface: bool = True
    preserve_original_query: bool = True

    @classmethod
    def from_settings(cls, settings: Any) -> "QueryExpansionConfig":
        return cls(
            enabled=settings.QUERY_EXPANSION_ENABLED,
            max_query_variants=settings.QUERY_EXPANSION_MAX_QUERY_VARIANTS,
            max_selected_mentions=settings.QUERY_EXPANSION_MAX_SELECTED_MENTIONS,
            max_strong_alternatives_per_mention=settings.QUERY_EXPANSION_MAX_STRONG_ALTERNATIVES_PER_MENTION,
            max_story_scoped_alternatives_per_mention=settings.QUERY_EXPANSION_MAX_STORY_SCOPED_ALTERNATIVES_PER_MENTION,
            strong_variant_budget=settings.QUERY_EXPANSION_STRONG_VARIANT_BUDGET,
            story_scoped_variant_budget=settings.QUERY_EXPANSION_STORY_SCOPED_VARIANT_BUDGET,
            max_story_scoped_replacements_per_variant=settings.QUERY_EXPANSION_MAX_STORY_SCOPED_REPLACEMENTS_PER_VARIANT,
            max_replacements_per_variant=settings.QUERY_EXPANSION_MAX_REPLACEMENTS_PER_VARIANT,
            allow_story_scoped=settings.QUERY_EXPANSION_ALLOW_STORY_SCOPED,
            allow_story_scoped_single_token=settings.QUERY_EXPANSION_ALLOW_STORY_SCOPED_SINGLE_TOKEN,
            require_unique_story_scoped_surface=settings.QUERY_EXPANSION_REQUIRE_UNIQUE_STORY_SCOPED_SURFACE,
            preserve_original_query=settings.QUERY_EXPANSION_PRESERVE_ORIGINAL_QUERY,
        )

    def tightened(self, override: "QueryExpansionRequestOptions | None") -> "QueryExpansionConfig":
        if override is None:
            return self
        return self.model_copy(
            update={
                "enabled": self.enabled and (override.enabled if override.enabled is not None else self.enabled),
                "allow_story_scoped": self.allow_story_scoped
                and (override.allow_story_scoped if override.allow_story_scoped is not None else self.allow_story_scoped),
                "allow_story_scoped_single_token": self.allow_story_scoped_single_token
                and (
                    override.allow_story_scoped_single_token
                    if override.allow_story_scoped_single_token is not None
                    else self.allow_story_scoped_single_token
                ),
                "max_query_variants": min(
                    self.max_query_variants,
                    override.max_query_variants if override.max_query_variants is not None else self.max_query_variants,
                ),
            }
        )


class QueryExpansionRequestOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool | None = None
    max_query_variants: int | None = Field(default=None, ge=1)
    allow_story_scoped: bool | None = None
    allow_story_scoped_single_token: bool | None = None


class MentionMatch(BaseModel):
    model_config = ConfigDict(frozen=True)

    mention_id: str
    original_text: str
    normalized_surface: str
    normalized_start: int
    normalized_end: int
    start_offset: int
    end_offset: int
    group_id: str | None
    canonical_name: str | None
    entity_type: str | None
    source_candidate_uid: str | None
    source_candidate_text: str | None
    relation_type: str | None
    approval_status: str | None
    scope: str | None
    story_ids: tuple[str, ...] = ()
    safe_to_substitute: bool
    normalization_only: bool
    dataset_unique_active_surface: bool
    dataset_unique_generatable_surface: bool
    token_count: int
    character_count: int
    eligibility: str
    blocked_reason: str | None = None
    single_token_story_scoped: bool = False
    reference_candidate_uids: tuple[str, ...] = ()


class AliasAlternative(BaseModel):
    model_config = ConfigDict(frozen=True)

    candidate_uid: str
    candidate_text: str
    normalized_surface: str
    relation_type: str
    scope: str
    story_ids: tuple[str, ...]
    priority_class: str
    priority_score: int
    token_count: int
    character_count: int
    single_token_story_scoped: bool = False


class ReplacementOperation(BaseModel):
    model_config = ConfigDict(frozen=True)

    mention_id: str
    start_offset: int
    end_offset: int
    source_text: str
    target_text: str
    group_id: str
    canonical_name: str
    scope: str
    story_ids: tuple[str, ...]
    source_candidate_uid: str
    source_relation_type: str
    target_candidate_uid: str
    target_relation_type: str


class QueryVariant(BaseModel):
    model_config = ConfigDict(frozen=True)

    variant_id: str
    query_text: str
    normalized_query_text: str
    variant_index: int
    variant_kind: str
    replacement_count: int
    strong_replacement_count: int
    story_scoped_replacement_count: int
    replacements: tuple[ReplacementOperation, ...]
    generation_priority: int


class QueryExpansionTrace(BaseModel):
    model_config = ConfigDict(frozen=True)

    original_query: str
    normalized_query: str
    config_snapshot: QueryExpansionConfig
    detected_mentions: tuple[MentionMatch, ...]
    selected_mentions: tuple[MentionMatch, ...]
    blocked_mentions: tuple[MentionMatch, ...]
    alternatives_by_mention: dict[str, tuple[AliasAlternative, ...]]
    generated_variants: tuple[QueryVariant, ...]
    candidate_combination_count: int
    invalid_combination_count: int
    duplicate_variant_count: int
    truncated_variant_count: int
    expansion_applied: bool
    expansion_reason: str


class _SpanCandidate(BaseModel):
    model_config = ConfigDict(frozen=True)

    normalized_start: int
    normalized_end: int
    original_start: int
    original_end: int
    normalized_surface: str
    original_text: str
    references: tuple[AliasMemberReference, ...]
    has_generatable: bool
    has_normalization_only: bool
    token_count: int
    character_count: int


class QueryExpansionService:
    def __init__(self, alias_registry: AliasRegistry, config: QueryExpansionConfig) -> None:
        self._alias_registry = alias_registry
        self._config = config
        self._active_surfaces_sorted = tuple(
            sorted(
                set(alias_registry.generatable_members_by_surface) | set(alias_registry.normalization_only_members_by_surface),
                key=lambda surface: (-len(surface.split()), -len(surface), surface),
            )
        )

    def expand(
        self,
        query: str,
        config_override: QueryExpansionRequestOptions | None = None,
    ) -> QueryExpansionTrace:
        config = self._config.tightened(config_override)
        normalized_query = normalize_query_with_offsets(query)
        original_variant = _original_variant(query)
        if not config.enabled:
            return QueryExpansionTrace(
                original_query=query,
                normalized_query=normalized_query.normalized_text,
                config_snapshot=config,
                detected_mentions=(),
                selected_mentions=(),
                blocked_mentions=(),
                alternatives_by_mention={},
                generated_variants=(original_variant,),
                candidate_combination_count=0,
                invalid_combination_count=0,
                duplicate_variant_count=0,
                truncated_variant_count=0,
                expansion_applied=False,
                expansion_reason="expansion_disabled",
            )

        span_candidates = self._detect_span_candidates(normalized_query)
        resolved_candidates = self._resolve_overlaps(span_candidates)
        detected_mentions = tuple(self._candidate_to_mention(candidate, config) for candidate in resolved_candidates)
        selected_mentions, budget_blocked = self._select_mentions(detected_mentions, config)
        blocked_mentions = tuple(
            sorted(
                [mention for mention in detected_mentions if mention.blocked_reason is not None and mention not in selected_mentions]
                + list(budget_blocked),
                key=lambda mention: (mention.start_offset, mention.end_offset, mention.mention_id),
            )
        )

        alternatives_by_mention = {
            mention.mention_id: self._alternatives_for_mention(mention, config)
            for mention in selected_mentions
        }
        (
            generated_variants,
            candidate_combination_count,
            invalid_combination_count,
            duplicate_variant_count,
            truncated_variant_count,
        ) = self._generate_variants(query, selected_mentions, alternatives_by_mention, config)

        expansion_reason = _expansion_reason(
            config=config,
            detected_mentions=detected_mentions,
            selected_mentions=selected_mentions,
            alternatives_by_mention=alternatives_by_mention,
            generated_variants=generated_variants,
        )
        trace = QueryExpansionTrace(
            original_query=query,
            normalized_query=normalized_query.normalized_text,
            config_snapshot=config,
            detected_mentions=detected_mentions,
            selected_mentions=selected_mentions,
            blocked_mentions=blocked_mentions,
            alternatives_by_mention=alternatives_by_mention,
            generated_variants=generated_variants,
            candidate_combination_count=candidate_combination_count,
            invalid_combination_count=invalid_combination_count,
            duplicate_variant_count=duplicate_variant_count,
            truncated_variant_count=truncated_variant_count,
            expansion_applied=expansion_reason == "aliases_expanded",
            expansion_reason=expansion_reason,
        )
        logger.info(
            "Alias expansion completed query_length=%s detected_mentions=%s selected_mentions=%s "
            "generated_variants=%s strong_variants=%s story_scoped_variants=%s blocked_mentions=%s "
            "duplicates_removed=%s truncated=%s",
            len(query),
            len(detected_mentions),
            len(selected_mentions),
            len(generated_variants),
            sum(1 for variant in generated_variants if variant.strong_replacement_count > 0),
            sum(1 for variant in generated_variants if variant.story_scoped_replacement_count > 0),
            len(blocked_mentions),
            duplicate_variant_count,
            truncated_variant_count,
        )
        return trace

    def _detect_span_candidates(self, normalized_query: NormalizedQuery) -> tuple[_SpanCandidate, ...]:
        by_key: dict[tuple[int, int, str], list[AliasMemberReference]] = defaultdict(list)
        text = normalized_query.normalized_text
        for surface in self._active_surfaces_sorted:
            start = 0
            while True:
                idx = text.find(surface, start)
                if idx == -1:
                    break
                end = idx + len(surface)
                if _valid_boundaries(text, idx, end):
                    refs = (
                        *self._alias_registry.generatable_members_by_surface.get(surface, ()),
                        *self._alias_registry.normalization_only_members_by_surface.get(surface, ()),
                    )
                    by_key[(idx, end, surface)].extend(refs)
                start = idx + 1

        candidates: list[_SpanCandidate] = []
        for (start, end, surface), refs in by_key.items():
            original_span = normalized_query.original_span(start, end)
            deduped_refs = tuple(sorted({ref.candidate_uid: ref for ref in refs}.values(), key=lambda ref: ref.candidate_uid))
            candidates.append(
                _SpanCandidate(
                    normalized_start=start,
                    normalized_end=end,
                    original_start=original_span.original_start,
                    original_end=original_span.original_end,
                    normalized_surface=surface,
                    original_text=normalized_query.original_text[original_span.original_start : original_span.original_end],
                    references=deduped_refs,
                    has_generatable=any(ref.is_generatable for ref in deduped_refs),
                    has_normalization_only=any(ref.is_normalization_only for ref in deduped_refs),
                    token_count=len(surface.split()),
                    character_count=len(surface),
                )
            )
        return tuple(candidates)

    def _resolve_overlaps(self, candidates: tuple[_SpanCandidate, ...]) -> tuple[_SpanCandidate, ...]:
        sorted_candidates = sorted(candidates, key=_span_priority)
        selected: list[_SpanCandidate] = []
        for candidate in sorted_candidates:
            if any(_spans_overlap(candidate, existing) for existing in selected):
                continue
            selected.append(candidate)
        return tuple(sorted(selected, key=lambda item: (item.original_start, item.original_end, item.normalized_surface)))

    def _candidate_to_mention(self, candidate: _SpanCandidate, config: QueryExpansionConfig) -> MentionMatch:
        group_ids = {ref.group_id for ref in candidate.references}
        common = {
            "mention_id": _mention_id(candidate.original_start, candidate.original_end, candidate.normalized_surface),
            "original_text": candidate.original_text,
            "normalized_surface": candidate.normalized_surface,
            "normalized_start": candidate.normalized_start,
            "normalized_end": candidate.normalized_end,
            "start_offset": candidate.original_start,
            "end_offset": candidate.original_end,
            "dataset_unique_active_surface": len(group_ids) == 1,
            "dataset_unique_generatable_surface": len({ref.group_id for ref in candidate.references if ref.is_generatable}) == 1,
            "token_count": candidate.token_count,
            "character_count": candidate.character_count,
            "reference_candidate_uids": tuple(ref.candidate_uid for ref in candidate.references),
        }
        if len(group_ids) > 1:
            return MentionMatch(
                **common,
                group_id=None,
                canonical_name=None,
                entity_type=None,
                source_candidate_uid=None,
                source_candidate_text=None,
                relation_type=None,
                approval_status=None,
                scope=None,
                story_ids=(),
                safe_to_substitute=False,
                normalization_only=candidate.has_normalization_only and not candidate.has_generatable,
                eligibility="ambiguous_surface",
                blocked_reason="ambiguous_surface",
            )
        reference = _best_source_reference(candidate.references)
        if reference is None:
            return MentionMatch(
                **common,
                group_id=None,
                canonical_name=None,
                entity_type=None,
                source_candidate_uid=None,
                source_candidate_text=None,
                relation_type=None,
                approval_status=None,
                scope=None,
                story_ids=(),
                safe_to_substitute=False,
                normalization_only=True,
                eligibility="normalization_only",
                blocked_reason="normalization_only",
            )

        eligibility, blocked_reason, single_token_story = _eligibility(reference, candidate.original_text, config)
        return MentionMatch(
            **common,
            group_id=reference.group_id,
            canonical_name=reference.canonical_name,
            entity_type=reference.entity_type,
            source_candidate_uid=reference.candidate_uid,
            source_candidate_text=reference.candidate_text,
            relation_type=reference.relation_type,
            approval_status=reference.approval_status,
            scope=reference.scope,
            story_ids=reference.story_ids,
            safe_to_substitute=reference.safe_to_substitute,
            normalization_only=False,
            eligibility=eligibility,
            blocked_reason=blocked_reason,
            single_token_story_scoped=single_token_story,
        )

    def _select_mentions(
        self,
        mentions: tuple[MentionMatch, ...],
        config: QueryExpansionConfig,
    ) -> tuple[tuple[MentionMatch, ...], tuple[MentionMatch, ...]]:
        eligible = [mention for mention in mentions if mention.eligibility in {"eligible_strong", "eligible_story_scoped"}]
        selected_single_story = False
        preselected: list[MentionMatch] = []
        extra_blocked: list[MentionMatch] = []
        for mention in sorted(eligible, key=_mention_selection_priority):
            if mention.single_token_story_scoped:
                if selected_single_story:
                    extra_blocked.append(_block_mention(mention, "single_token_story_budget_exceeded"))
                    continue
                selected_single_story = True
            preselected.append(mention)
        selected = tuple(sorted(preselected[: config.max_selected_mentions], key=lambda item: (item.start_offset, item.end_offset)))
        extra_blocked.extend(_block_mention(mention, "mention_budget_exceeded") for mention in preselected[config.max_selected_mentions :])
        return selected, tuple(extra_blocked)

    def _alternatives_for_mention(
        self,
        mention: MentionMatch,
        config: QueryExpansionConfig,
    ) -> tuple[AliasAlternative, ...]:
        if not mention.group_id or not mention.source_candidate_uid:
            return ()
        group = self._alias_registry.get_group(mention.group_id)
        if group is None:
            return ()
        limit = (
            config.max_strong_alternatives_per_mention
            if mention.eligibility == "eligible_strong"
            else config.max_story_scoped_alternatives_per_mention
        )
        alternatives: list[AliasAlternative] = []
        story_single_token_used = False
        for target in group.generatable_members:
            if target.candidate_uid == mention.source_candidate_uid:
                continue
            if target.normalized_surface == mention.normalized_surface:
                continue
            if BLOCKING_GENERATION_CONSTRAINTS.intersection(target.substitution_constraints):
                continue
            if mention.eligibility == "eligible_story_scoped":
                if not target.dataset_unique_active_surface:
                    continue
                target_single = target.token_count == 1
                if target_single:
                    if story_single_token_used:
                        continue
                    if target.entity_type not in SUPPORTED_SINGLE_TOKEN_STORY_ENTITY_TYPES:
                        continue
                    if target.relation_type == "determiner_variant":
                        continue
                    if not any(char.isupper() for char in target.candidate_text):
                        continue
                    story_single_token_used = True
            priority_score = _alternative_score(target)
            alternatives.append(
                AliasAlternative(
                    candidate_uid=target.candidate_uid,
                    candidate_text=target.candidate_text,
                    normalized_surface=target.normalized_surface,
                    relation_type=target.relation_type,
                    scope=target.scope,
                    story_ids=target.story_ids,
                    priority_class=_priority_class(target.relation_type),
                    priority_score=priority_score,
                    token_count=target.token_count,
                    character_count=target.character_count,
                    single_token_story_scoped=mention.eligibility == "eligible_story_scoped" and target.token_count == 1,
                )
            )
        return tuple(sorted(alternatives, key=_alternative_sort_key)[:limit])

    def _generate_variants(
        self,
        query: str,
        selected_mentions: tuple[MentionMatch, ...],
        alternatives_by_mention: dict[str, tuple[AliasAlternative, ...]],
        config: QueryExpansionConfig,
    ) -> tuple[tuple[QueryVariant, ...], int, int, int, int]:
        original = _original_variant(query)
        slots = []
        for mention in selected_mentions:
            alternatives = alternatives_by_mention.get(mention.mention_id, ())
            if alternatives:
                slots.append((mention, alternatives))
        if not slots:
            return (original,), 0, 0, 0, 0

        candidate_combination_count = 0
        invalid_combination_count = 0
        structural_candidates: list[QueryVariant] = []
        option_lists = [[None, *alternatives] for _, alternatives in slots]
        for combination in itertools.product(*option_lists):
            if all(option is None for option in combination):
                continue
            candidate_combination_count += 1
            mention_alt_pairs = [
                (slots[idx][0], option)
                for idx, option in enumerate(combination)
                if option is not None
            ]
            story_count = sum(1 for mention, _ in mention_alt_pairs if mention.eligibility == "eligible_story_scoped")
            replacement_count = len(mention_alt_pairs)
            if (
                story_count > config.max_story_scoped_replacements_per_variant
                or replacement_count > config.max_replacements_per_variant
                or story_count > 1
            ):
                invalid_combination_count += 1
                continue
            structural_candidates.append(_build_variant(query, mention_alt_pairs))

        deduped: dict[str, QueryVariant] = {}
        duplicate_variant_count = 0
        original_key = normalize_alias_surface(query)
        for variant in sorted(structural_candidates, key=_global_variant_sort_key):
            key = variant.normalized_query_text
            if key == original_key:
                duplicate_variant_count += 1
                continue
            if key in deduped:
                duplicate_variant_count += 1
                deduped[key] = min(deduped[key], variant, key=_duplicate_preference_key)
            else:
                deduped[key] = variant

        non_duplicates = sorted(deduped.values(), key=_global_variant_sort_key)
        selected_non_original, truncated_variant_count = _select_variant_budget(non_duplicates, config)
        generated = [original]
        for index, variant in enumerate(selected_non_original, start=1):
            generated.append(variant.model_copy(update={"variant_index": index}))
        return tuple(generated), candidate_combination_count, invalid_combination_count, duplicate_variant_count, truncated_variant_count


def normalize_query_with_offsets(text: str) -> NormalizedQuery:
    pieces: list[tuple[str, OffsetSpan]] = []
    for index, char in enumerate(text):
        normalized = unicodedata.normalize("NFKC", char)
        normalized = "".join("'" if item in APOSTROPHE_CHARS else item for item in normalized)
        normalized = "".join("-" if item in DASH_CHARS else item for item in normalized)
        normalized = normalized.casefold()
        for output_char in normalized:
            pieces.append((output_char, OffsetSpan(original_start=index, original_end=index + 1)))

    start = 0
    end = len(pieces)
    while start < end and pieces[start][0].isspace():
        start += 1
    while end > start and pieces[end - 1][0].isspace():
        end -= 1

    normalized_chars: list[str] = []
    offsets: list[OffsetSpan] = []
    idx = start
    while idx < end:
        char, span = pieces[idx]
        if char.isspace():
            whitespace_start = span.original_start
            whitespace_end = span.original_end
            idx += 1
            while idx < end and pieces[idx][0].isspace():
                whitespace_end = pieces[idx][1].original_end
                idx += 1
            normalized_chars.append(" ")
            offsets.append(OffsetSpan(original_start=whitespace_start, original_end=whitespace_end))
        else:
            normalized_chars.append(char)
            offsets.append(span)
            idx += 1

    return NormalizedQuery(
        original_text=text,
        normalized_text="".join(normalized_chars),
        normalized_to_original_offsets=tuple(offsets),
    )


def _valid_boundaries(text: str, start: int, end: int) -> bool:
    if start > 0 and _is_word_connector(text[start - 1]):
        return False
    if end < len(text):
        next_char = text[end]
        if _is_word_connector(next_char):
            return False
        if next_char == "'" and text[end : end + 2] in {"'s", "'S"}:
            return False
    return True


def _is_word_connector(char: str) -> bool:
    return char == "_" or char.isalpha() or char.isdigit()


def _span_priority(candidate: _SpanCandidate) -> tuple:
    group_ids = {ref.group_id for ref in candidate.references}
    best_ref = _best_source_reference(candidate.references)
    strong_rank = 0 if best_ref and best_ref.approval_status == "approved_strong" else 1
    unique_rank = 0 if len(group_ids) == 1 else 1
    blocker_rank = 0 if candidate.has_normalization_only and not candidate.has_generatable else 1
    return (
        -(candidate.normalized_end - candidate.normalized_start),
        -candidate.token_count,
        blocker_rank,
        strong_rank,
        unique_rank,
        candidate.normalized_surface,
        sorted(group_ids)[0] if group_ids else "",
    )


def _spans_overlap(left: _SpanCandidate, right: _SpanCandidate) -> bool:
    return left.normalized_start < right.normalized_end and right.normalized_start < left.normalized_end


def _best_source_reference(references: tuple[AliasMemberReference, ...]) -> AliasMemberReference | None:
    generatable = [ref for ref in references if ref.is_generatable]
    if not generatable:
        return None
    return sorted(
        generatable,
        key=lambda ref: (
            0 if ref.approval_status == "approved_strong" else 1,
            -ref.token_count,
            -ref.character_count,
            ref.candidate_text.casefold(),
            ref.candidate_uid,
        ),
    )[0]


def _eligibility(
    reference: AliasMemberReference,
    original_text: str,
    config: QueryExpansionConfig,
) -> tuple[str, str | None, bool]:
    if not reference.is_generatable:
        return "not_generatable", "not_generatable", False
    if reference.approval_status == "approved_strong" and reference.scope == "global":
        return "eligible_strong", None, False
    if reference.approval_status == "approved_story_scoped" and reference.scope == "story_scoped":
        if not config.allow_story_scoped:
            return "blocked_story_scoped_disabled", "story_scoped_disabled", False
        if not reference.story_ids:
            return "blocked_story_scoped_without_story", "story_scoped_without_story", False
        if config.require_unique_story_scoped_surface and not reference.dataset_unique_active_surface:
            return "ambiguous_surface", "ambiguous_surface", False
        if reference.token_count == 1:
            if not config.allow_story_scoped_single_token:
                return "blocked_single_token", "single_token_story_scoped_disabled", True
            if reference.entity_type not in SUPPORTED_SINGLE_TOKEN_STORY_ENTITY_TYPES:
                return "blocked_single_token", "unsupported_single_token_entity_type", True
            if not any(char.isupper() for char in original_text):
                return "blocked_single_token", "lowercase_single_token_story_scoped", True
            return "eligible_story_scoped", None, True
        return "eligible_story_scoped", None, False
    return "not_generatable", "unsupported_scope_or_status", False


def _mention_id(start: int, end: int, surface: str) -> str:
    digest = hashlib.sha256(f"{start}:{end}:{surface}".encode("utf-8")).hexdigest()[:10]
    return f"m_{digest}"


def _block_mention(mention: MentionMatch, reason: str) -> MentionMatch:
    return mention.model_copy(update={"eligibility": reason, "blocked_reason": reason})


def _relation_value_rank(relation_type: str | None) -> int:
    if relation_type in HIGH_VALUE_RELATIONS:
        return 0
    if relation_type in {"title_variant", "exact_name"}:
        return 1
    return 2


def _mention_selection_priority(mention: MentionMatch) -> tuple:
    scope_rank = 0 if mention.eligibility == "eligible_strong" else 1
    token_rank = 0 if mention.token_count > 1 else 1
    return (
        scope_rank,
        token_rank,
        _relation_value_rank(mention.relation_type),
        -mention.character_count,
        1 if mention.single_token_story_scoped else 0,
        mention.start_offset,
        mention.mention_id,
    )


def _alternative_score(target: AliasMemberReference) -> int:
    return (
        (100 if target.approval_status == "approved_strong" else 60)
        + RELATION_SCORES.get(target.relation_type, 0)
        + (5 if target.token_count > 1 else 0)
        + (12 if target.candidate_text == target.canonical_name else 0)
    )


def _priority_class(relation_type: str) -> str:
    if relation_type in HIGH_VALUE_RELATIONS:
        return "high_value"
    if relation_type in {"title_variant", "exact_name"}:
        return "medium_value"
    return "low_value"


def _alternative_sort_key(alternative: AliasAlternative) -> tuple:
    return (
        -alternative.priority_score,
        1 if alternative.single_token_story_scoped else 0,
        -alternative.token_count,
        -alternative.character_count,
        alternative.candidate_text.casefold(),
        alternative.candidate_uid,
    )


def _build_variant(
    query: str,
    mention_alt_pairs: list[tuple[MentionMatch, AliasAlternative]],
) -> QueryVariant:
    replacements = []
    query_text = query
    for mention, alternative in sorted(mention_alt_pairs, key=lambda pair: pair[0].start_offset, reverse=True):
        query_text = query_text[: mention.start_offset] + alternative.candidate_text + query_text[mention.end_offset :]
        replacements.append(
            ReplacementOperation(
                mention_id=mention.mention_id,
                start_offset=mention.start_offset,
                end_offset=mention.end_offset,
                source_text=mention.original_text,
                target_text=alternative.candidate_text,
                group_id=mention.group_id or "",
                canonical_name=mention.canonical_name or "",
                scope=mention.scope or "",
                story_ids=mention.story_ids,
                source_candidate_uid=mention.source_candidate_uid or "",
                source_relation_type=mention.relation_type or "",
                target_candidate_uid=alternative.candidate_uid,
                target_relation_type=alternative.relation_type,
            )
        )
    replacements = tuple(sorted(replacements, key=lambda item: item.start_offset))
    strong_count = sum(1 for item in replacements if item.scope == "global")
    story_count = sum(1 for item in replacements if item.scope == "story_scoped")
    if story_count and strong_count:
        kind = "mixed"
    elif story_count:
        kind = "story_scoped_single"
    elif strong_count > 1:
        kind = "strong_multi"
    else:
        kind = "strong_single"
    priority = sum(alternative.priority_score for _, alternative in mention_alt_pairs)
    return QueryVariant(
        variant_id=_variant_id(query, replacements),
        query_text=query_text,
        normalized_query_text=normalize_alias_surface(query_text),
        variant_index=-1,
        variant_kind=kind,
        replacement_count=len(replacements),
        strong_replacement_count=strong_count,
        story_scoped_replacement_count=story_count,
        replacements=replacements,
        generation_priority=priority,
    )


def _variant_id(query: str, replacements: tuple[ReplacementOperation, ...]) -> str:
    payload = "|".join(
        [
            query,
            *(
                f"{replacement.start_offset}:{replacement.end_offset}:"
                f"{replacement.source_candidate_uid}>{replacement.target_candidate_uid}"
                for replacement in replacements
            ),
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _original_variant(query: str) -> QueryVariant:
    return QueryVariant(
        variant_id="original",
        query_text=query,
        normalized_query_text=normalize_alias_surface(query),
        variant_index=0,
        variant_kind="original",
        replacement_count=0,
        strong_replacement_count=0,
        story_scoped_replacement_count=0,
        replacements=(),
        generation_priority=0,
    )


def _global_variant_sort_key(variant: QueryVariant) -> tuple:
    return (
        VARIANT_KIND_RANK.get(variant.variant_kind, 99),
        -variant.generation_priority,
        variant.replacement_count,
        min((replacement.start_offset for replacement in variant.replacements), default=0),
        variant.normalized_query_text,
        variant.variant_id,
    )


def _duplicate_preference_key(variant: QueryVariant) -> tuple:
    return (
        -variant.generation_priority,
        variant.replacement_count,
        VARIANT_KIND_RANK.get(variant.variant_kind, 99),
        variant.variant_id,
    )


def _select_variant_budget(
    variants: list[QueryVariant],
    config: QueryExpansionConfig,
) -> tuple[list[QueryVariant], int]:
    total_capacity = max(0, config.max_query_variants - 1)
    strong_candidates = [variant for variant in variants if variant.story_scoped_replacement_count == 0]
    story_candidates = [variant for variant in variants if variant.story_scoped_replacement_count > 0]
    selected_strong = strong_candidates[: config.strong_variant_budget]
    selected_story = story_candidates[: config.story_scoped_variant_budget]
    selected_ids = {variant.variant_id for variant in selected_strong + selected_story}
    remaining_capacity = max(0, total_capacity - len(selected_ids))
    remaining_candidates = [
        variant for variant in variants
        if variant.variant_id not in selected_ids
    ]
    fill = remaining_candidates[:remaining_capacity]
    selected = sorted([*selected_strong, *selected_story, *fill], key=_global_variant_sort_key)[:total_capacity]
    return selected, max(0, len(variants) - len(selected))


def _expansion_reason(
    *,
    config: QueryExpansionConfig,
    detected_mentions: tuple[MentionMatch, ...],
    selected_mentions: tuple[MentionMatch, ...],
    alternatives_by_mention: dict[str, tuple[AliasAlternative, ...]],
    generated_variants: tuple[QueryVariant, ...],
) -> str:
    if not config.enabled:
        return "expansion_disabled"
    if len(generated_variants) > 1:
        return "aliases_expanded"
    if not detected_mentions:
        return "no_alias_mentions"
    if all(mention.normalization_only for mention in detected_mentions):
        return "only_normalization_only_mentions"
    if any(mention.eligibility == "ambiguous_surface" for mention in detected_mentions) and not any(
        mention.eligibility not in {"ambiguous_surface", "normalization_only"} for mention in detected_mentions
    ):
        return "all_mentions_ambiguous"
    if selected_mentions and any(alternatives_by_mention.get(mention.mention_id) for mention in selected_mentions):
        return "no_distinct_variants"
    return "all_mentions_blocked"

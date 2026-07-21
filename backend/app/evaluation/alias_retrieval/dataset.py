import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.services.alias_registry import AliasRegistry


QuestionSplit = Literal["legacy_regression", "alias_challenge", "negative_control"]
QuestionCategory = Literal[
    "entity_alias",
    "causal_reasoning",
    "hidden_identity",
    "symbolic_meaning",
    "multiple_identity",
    "event_chain",
    "indirect_reference",
    "cross_story",
    "alias_challenge",
    "negative_control",
]


class GoldEvidenceGroup(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_group_id: str
    description: str
    alternative_chunk_uids: tuple[str, ...]

    @field_validator("evidence_group_id", "description")
    @classmethod
    def non_empty_string(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("must be non-empty")
        return value

    @field_validator("alternative_chunk_uids")
    @classmethod
    def non_empty_alternatives(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value:
            raise ValueError("must contain at least one chunk uid")
        if any(not item.strip() for item in value):
            raise ValueError("chunk uid values must be non-empty")
        return value


class AliasEvaluationQuestion(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    question_id: str
    split: QuestionSplit
    category: QuestionCategory
    question: str
    reference_answer: str
    gold_evidence_groups: tuple[GoldEvidenceGroup, ...]
    supporting_chunk_uids: tuple[str, ...] = ()
    contradictory_chunk_uids: tuple[str, ...] = ()
    expected_alias_group_ids: tuple[str, ...] = ()
    expected_query_mentions: tuple[str, ...] = ()

    @field_validator("question_id", "question", "reference_answer")
    @classmethod
    def non_empty_string(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("must be non-empty")
        return value


class AliasEvaluationDataset(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = "1"
    dataset_id: str
    document_id: str
    questions: tuple[AliasEvaluationQuestion, ...]


class DatasetManifest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    dataset_version: str
    annotation_status: Literal["seed", "frozen"]
    legacy_question_count: int = Field(ge=0)
    alias_challenge_question_count: int = Field(ge=0)
    negative_control_count: int = Field(ge=0)
    official_evaluation_ready: bool
    notes: str | None = None


class DatasetValidationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    warnings: tuple[str, ...] = ()


def load_evaluation_dataset(path: Path) -> AliasEvaluationDataset:
    with path.open("r", encoding="utf-8") as handle:
        return AliasEvaluationDataset.model_validate(json.load(handle))


def load_dataset_manifest(path: Path) -> DatasetManifest:
    with path.open("r", encoding="utf-8") as handle:
        return DatasetManifest.model_validate(json.load(handle))


def validate_dataset(
    dataset: AliasEvaluationDataset,
    *,
    manifest: DatasetManifest,
    known_chunk_uids: set[str],
    alias_registry: AliasRegistry,
    strict: bool = True,
) -> DatasetValidationResult:
    errors: list[str] = []
    warnings: list[str] = []
    qids: set[str] = set()
    split_counts = {"legacy_regression": 0, "alias_challenge": 0, "negative_control": 0}
    group_ids = {group.group_id for group in alias_registry.snapshot.groups}

    for question in dataset.questions:
        if question.question_id in qids:
            errors.append(f"Duplicate question_id: {question.question_id}")
        qids.add(question.question_id)
        split_counts[question.split] += 1

        evidence_ids: set[str] = set()
        if not question.gold_evidence_groups:
            errors.append(f"{question.question_id}: missing direct evidence groups")
        for group in question.gold_evidence_groups:
            if group.evidence_group_id in evidence_ids:
                errors.append(f"{question.question_id}: duplicate evidence_group_id {group.evidence_group_id}")
            evidence_ids.add(group.evidence_group_id)
            for uid in group.alternative_chunk_uids:
                if uid not in known_chunk_uids:
                    errors.append(f"{question.question_id}: unknown gold chunk uid {uid}")
        for uid in question.supporting_chunk_uids + question.contradictory_chunk_uids:
            if uid not in known_chunk_uids:
                errors.append(f"{question.question_id}: unknown supporting/contradictory chunk uid {uid}")
        for group_id in question.expected_alias_group_ids:
            if group_id not in group_ids:
                message = f"{question.question_id}: unknown expected alias group {group_id}"
                if strict:
                    errors.append(message)
                else:
                    warnings.append(message)
        if question.split != "negative_control" and not question.expected_alias_group_ids:
            warnings.append(f"{question.question_id}: no expected alias group configured")

    if split_counts["legacy_regression"] != manifest.legacy_question_count:
        errors.append("Manifest legacy_question_count does not match questions")
    if split_counts["alias_challenge"] != manifest.alias_challenge_question_count:
        errors.append("Manifest alias_challenge_question_count does not match questions")
    if split_counts["negative_control"] != manifest.negative_control_count:
        errors.append("Manifest negative_control_count does not match questions")
    if manifest.official_evaluation_ready and manifest.annotation_status != "frozen":
        errors.append("Official evaluation datasets must have annotation_status='frozen'")

    if errors:
        raise ValueError("; ".join(errors))
    return DatasetValidationResult(warnings=tuple(sorted(warnings)))


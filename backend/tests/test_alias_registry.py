import copy
import hashlib
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_alias_registry
from app.api.main import app, create_app
from app.core.config import settings
from app.services.alias_registry import (
    EXPECTED_ALIAS_DATASET_SHA256,
    AliasDatasetError,
    AliasRegistry,
    normalize_alias_surface,
)


def make_member(uid: str, text: str, *, safe: bool = True, constraints: list[str] | None = None) -> dict:
    return {
        "candidate_uid": uid,
        "candidate_text": text,
        "relation_type": "alias",
        "same_entity": True,
        "member_disposition": "approved_member" if safe else "normalization_only",
        "safe_to_substitute": safe,
        "substitution_constraints": constraints or [],
        "evidence_story_ids": ["s01-a-scandal-in-bohemia"],
        "evidence_sentences": ["Example evidence."],
        "review_reason": None,
    }


def make_group(
    group_id: str,
    canonical_name: str,
    members: list[dict],
    *,
    status: str = "approved_story_scoped",
    scope: str = "story_scoped",
    story_ids: list[str] | None = None,
) -> dict:
    return {
        "group_id": group_id,
        "canonical_name": canonical_name,
        "entity_type": "PERSON",
        "scope": scope,
        "story_ids": story_ids if story_ids is not None else ["s01-a-scandal-in-bohemia"],
        "approval_status": status,
        "group_confidence": "high",
        "safe_for_query_substitution": True,
        "members": members,
        "removed_members": [],
        "group_review_reason": None,
    }


def make_document(groups: list[dict] | None = None) -> dict:
    if groups is None:
        groups = [
            make_group(
                "entity-alpha",
                "Alpha One",
                [
                    make_member("uid-alpha-one", "Alpha One"),
                    make_member("uid-alpha", "Alpha"),
                    make_member("uid-alpha-raw", "the Alpha One", safe=False, constraints=["do_not_generate"]),
                ],
            )
        ]
    dispositions = []
    for group in groups:
        for member in group["members"]:
            dispositions.append(
                {
                    "candidate_uid": member["candidate_uid"],
                    "candidate_text": member["candidate_text"],
                    "final_category": "approved_group_member" if member["safe_to_substitute"] else "normalization_only_group_member",
                    "group_id": group["group_id"],
                    "notes": None,
                }
            )
    return {
        "metadata": {
            "all_input_candidates_accounted_for": True,
            "all_output_uids_in_allowlist": True,
            "active_group_members_unique": True,
            "approved_strong_group_count": sum(1 for group in groups if group["approval_status"] == "approved_strong"),
            "approved_story_scoped_group_count": sum(1 for group in groups if group["approval_status"] == "approved_story_scoped"),
            "input_candidate_count": len(dispositions),
            "normalization_only_candidate_count": sum(
                1 for item in dispositions if item["final_category"].startswith("normalization_only")
            ),
        },
        "validation_summary": {
            "active_group_members_unique": True,
            "all_input_candidates_accounted_for": True,
            "all_output_uids_in_allowlist": True,
            "candidate_texts_match_source": True,
            "duplicate_active_memberships": [],
            "missing_source_candidates": [],
            "unknown_uids": [],
            "unresolved_status_count": 0,
        },
        "approved_groups": groups,
        "rejected_groups": [],
        "excluded_candidates": [],
        "ambiguous_candidates": [],
        "review_required_groups": [],
        "split_required": [],
        "singletons": [],
        "invalid_generated_candidates": [],
        "narrative_identity_relations": [],
        "candidate_final_dispositions": dispositions,
    }


def write_dataset(tmp_path: Path, document: dict) -> Path:
    path = tmp_path / "aliases.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def load_fixture(tmp_path: Path, document: dict | None = None, *, strict: bool = True) -> AliasRegistry:
    path = write_dataset(tmp_path, document or make_document())
    return AliasRegistry.load(path, expected_sha256=None, strict_validation=strict)


def test_normalize_alias_surface_preserves_meaningful_punctuation():
    assert normalize_alias_surface("Mr. Holmes") == "mr. holmes"
    assert normalize_alias_surface("MR. HOLMES") == "mr. holmes"
    assert normalize_alias_surface("St. George’s") == "st. george's"
    assert normalize_alias_surface("St. George's") == "st. george's"
    assert normalize_alias_surface(" THE  MORNING POST ") == "the morning post"
    assert normalize_alias_surface("Lone Star\u2014Barque") == "lone star-barque"
    assert normalize_alias_surface("L. S.") == "l. s."
    assert normalize_alias_surface("K. K. K.") == "k. k. k."


def test_loads_frozen_alias_dataset_counts_and_known_groups():
    registry = AliasRegistry.load(
        settings.ALIAS_DATASET_PATH,
        expected_sha256=EXPECTED_ALIAS_DATASET_SHA256,
        strict_validation=True,
    )

    status = registry.get_status()
    assert status.sha256 == EXPECTED_ALIAS_DATASET_SHA256
    assert status.approved_group_count == 87
    assert status.approved_strong_group_count == 5
    assert status.approved_story_scoped_group_count == 82
    assert status.generatable_member_count == 226
    assert status.normalization_only_member_count == 13
    assert status.final_disposition_count == 359

    for surface in ["Holmes", "Mr. Holmes", "Sherlock Holmes"]:
        assert registry.lookup_surface(surface)[1][0].group_id == "entity-sherlock-holmes"

    for surface in ["Hosmer", "Mr. Angel", "Hosmer Angel"]:
        match = registry.lookup_surface(surface)[1][0]
        assert match.group_id == "entity-hosmer-angel"
        assert match.scope == "story_scoped"
        assert match.story_ids == ("s03-a-case-of-identity",)

    assert registry.lookup_surface("K. K. K.")[1]
    assert registry.lookup_surface("Ku Klux Klan")[1]
    assert registry.lookup_surface("this K. K. K.")[1] == ()
    assert registry.lookup_surface("this K. K. K.")[2][0].is_normalization_only
    assert registry.lookup_surface("Klux Klan")[1] == ()
    assert registry.lookup_surface("Klux Klan")[2][0].is_normalization_only

    lone_star_group_ids = {registry.lookup_surface(surface)[1][0].group_id for surface in ["L. S.", "Lone Star", "Barque Lone Star"]}
    assert lone_star_group_ids == {"entity-lone-star"}

    assert not registry.lookup_surface("Elias Openshaw")[1]
    assert not registry.lookup_surface("Jephro Rucastle")[1]
    assert not registry.lookup_surface("Theological College of St. George's")[1]


def test_missing_invalid_json_and_hash_errors(tmp_path):
    missing = tmp_path / "missing.json"
    with pytest.raises(AliasDatasetError, match="not found"):
        AliasRegistry.load(missing, expected_sha256=None)

    invalid = tmp_path / "invalid.json"
    invalid.write_text("{not json", encoding="utf-8")
    with pytest.raises(AliasDatasetError, match="not valid JSON"):
        AliasRegistry.load(invalid, expected_sha256=None)

    path = write_dataset(tmp_path, make_document())
    with pytest.raises(AliasDatasetError, match="SHA-256 mismatch"):
        AliasRegistry.load(path, expected_sha256="deadbeef", strict_validation=True)

    assert AliasRegistry.load(path, expected_sha256=None, strict_validation=True).get_status().loaded
    non_strict = AliasRegistry.load(path, expected_sha256="deadbeef", strict_validation=False)
    assert any("SHA-256 mismatch" in warning for warning in non_strict.snapshot.validation_summary.warnings)


def test_empty_approved_groups_loads_when_metadata_accounts_for_empty_dataset(tmp_path):
    registry = load_fixture(tmp_path, make_document([]))

    status = registry.get_status()
    assert status.approved_group_count == 0
    assert status.generatable_member_count == 0
    assert registry.matchable_surfaces_sorted == ()


def test_validation_rejects_duplicate_ids_and_invalid_scope(tmp_path):
    document = make_document()
    duplicate_group = copy.deepcopy(document)
    duplicate_group["approved_groups"].append(copy.deepcopy(duplicate_group["approved_groups"][0]))
    duplicate_group["metadata"]["approved_story_scoped_group_count"] = 2
    with pytest.raises(AliasDatasetError, match="duplicate active group_id"):
        load_fixture(tmp_path, duplicate_group)

    duplicate_uid = make_document()
    duplicate_uid["approved_groups"][0]["members"][1]["candidate_uid"] = "uid-alpha-one"
    duplicate_uid["candidate_final_dispositions"][1]["candidate_uid"] = "uid-alpha-one"
    with pytest.raises(AliasDatasetError, match="duplicate active candidate_uid"):
        load_fixture(tmp_path, duplicate_uid)

    duplicate_disposition = make_document()
    duplicate_disposition["candidate_final_dispositions"][1]["candidate_uid"] = "uid-alpha-one"
    with pytest.raises(AliasDatasetError, match="duplicate final disposition"):
        load_fixture(tmp_path, duplicate_disposition)

    invalid_scope = make_document(
        [
            make_group(
                "entity-strong-bad-scope",
                "Strong Bad Scope",
                [make_member("uid-a", "Strong Bad Scope"), make_member("uid-b", "Strong")],
                status="approved_strong",
                scope="story_scoped",
                story_ids=["s01-a-scandal-in-bohemia"],
            )
        ]
    )
    with pytest.raises(AliasDatasetError, match="approved_strong must have global scope"):
        load_fixture(tmp_path, invalid_scope)

    no_story = make_document(
        [
            make_group(
                "entity-no-story",
                "No Story",
                [make_member("uid-a", "No Story"), make_member("uid-b", "Story")],
                story_ids=[],
            )
        ]
    )
    with pytest.raises(AliasDatasetError, match="must have story_ids"):
        load_fixture(tmp_path, no_story)


def test_compiled_indexes_keep_unsafe_out_of_generatable(tmp_path):
    registry = load_fixture(tmp_path)

    assert "the alpha one" not in registry.generatable_members_by_surface
    assert registry.normalization_only_members_by_surface["the alpha one"][0].safe_to_substitute is False
    assert registry.lookup_surface("the Alpha One")[1] == ()
    assert registry.lookup_surface("the Alpha One")[2][0].candidate_uid == "uid-alpha-raw"


def test_surface_conflict_fixture_marks_non_unique_and_returns_both(tmp_path):
    document = make_document(
        [
            make_group(
                "entity-alpha",
                "Alpha One",
                [make_member("uid-alpha-one", "Alpha One"), make_member("uid-alpha", "Alpha")],
            ),
            make_group(
                "entity-beta",
                "Beta One",
                [make_member("uid-beta-one", "Beta One"), make_member("uid-beta-alpha", "Alpha")],
            ),
        ]
    )
    registry = load_fixture(tmp_path, document)

    matches = registry.lookup_surface("Alpha")[1]
    assert len(matches) == 2
    assert {match.group_id for match in matches} == {"entity-alpha", "entity-beta"}
    assert all(not match.dataset_unique_active_surface for match in matches)
    assert any("surface conflict" in warning for warning in registry.snapshot.validation_summary.warnings)


def test_groups_by_story_excludes_global_groups(tmp_path):
    document = make_document(
        [
            make_group(
                "entity-global",
                "Global Entity",
                [make_member("uid-global-one", "Global Entity"), make_member("uid-global", "Global")],
                status="approved_strong",
                scope="global",
                story_ids=[],
            ),
            make_group(
                "entity-story",
                "Story Entity",
                [make_member("uid-story-one", "Story Entity"), make_member("uid-story", "Story")],
            ),
        ]
    )
    registry = load_fixture(tmp_path, document)

    assert [group.group_id for group in registry.groups_by_scope["global"]] == ["entity-global"]
    assert [group.group_id for group in registry.get_groups_for_story("s01-a-scandal-in-bohemia")] == ["entity-story"]


def test_alias_api_status_groups_lookup_and_no_absolute_path():
    registry = AliasRegistry.load(
        settings.ALIAS_DATASET_PATH,
        expected_sha256=EXPECTED_ALIAS_DATASET_SHA256,
        strict_validation=True,
    )
    app.dependency_overrides[get_alias_registry] = lambda: registry
    try:
        client = TestClient(app)
        status = client.get("/api/aliases/status")
        assert status.status_code == 200
        status_json = status.json()
        assert status_json["file_name"] == "sherlock_entity_alias_groups_final.json"
        assert "source_file_path" not in status_json
        assert status_json["generatable_member_count"] == 226

        groups = client.get("/api/aliases/groups", params={"search": "Holmes", "limit": 5})
        assert groups.status_code == 200
        group_names = [group["canonical_name"] for group in groups.json()["groups"]]
        assert group_names == sorted(group_names, key=str.casefold)

        detail = client.get("/api/aliases/groups/entity-sherlock-holmes")
        assert detail.status_code == 200
        assert detail.json()["group_id"] == "entity-sherlock-holmes"
        assert detail.json()["generatable_member_count"] >= 2

        lookup = client.get("/api/aliases/lookup", params={"surface": "this K. K. K."})
        assert lookup.status_code == 200
        assert lookup.json()["generatable_matches"] == []
        assert lookup.json()["normalization_only_matches"][0]["safe_to_substitute"] is False
    finally:
        app.dependency_overrides.clear()


def test_lifespan_loads_alias_registry_once(monkeypatch):
    fake_registry = MagicMock()
    fake_registry.get_status.return_value.file_name = "aliases.json"
    fake_registry.get_status.return_value.sha256 = "abc"
    fake_registry.get_status.return_value.approved_strong_group_count = 1
    fake_registry.get_status.return_value.approved_story_scoped_group_count = 1
    fake_registry.get_status.return_value.generatable_member_count = 2
    fake_registry.get_status.return_value.normalization_only_member_count = 0
    fake_registry.get_status.return_value.validation_warning_count = 0
    fake_registry.snapshot.source_file_path = "/tmp/aliases.json"

    load_mock = MagicMock(return_value=fake_registry)
    monkeypatch.setattr("app.api.main.AliasRegistry.load", load_mock)

    class DummyProvider:
        def encode(self, text):
            return [0.0]

    class DummyGroqClient:
        def __init__(self, settings):
            pass

        def close(self):
            pass

    class DummyCursor:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, sql):
            pass

        def fetchone(self):
            return (1,)

    class DummyConnection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def cursor(self):
            return DummyCursor()

    monkeypatch.setattr("app.api.main.MiniLMProvider", DummyProvider)
    monkeypatch.setattr("app.api.main.GroqGptOssClient", DummyGroqClient)
    monkeypatch.setattr("app.api.main.get_connection", lambda: DummyConnection())

    local_app = create_app()
    with TestClient(local_app) as client:
        assert client.app.state.alias_registry is fake_registry
        assert client.get("/api/health/live").status_code == 200

    assert load_mock.call_count == 1
    assert getattr(local_app.state, "ready") is False

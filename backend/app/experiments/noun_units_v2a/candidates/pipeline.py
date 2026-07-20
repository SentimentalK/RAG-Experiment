import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.experiments.noun_units_v2a.candidates.baseline_coverage import analyze_question_units, extract_question_units_with_spacy
from app.experiments.noun_units_v2a.candidates.boundary_filter import default_leading_noise_terms
from app.experiments.noun_units_v2a.candidates.comparison_normalizer import default_orthographic_map
from app.experiments.noun_units_v2a.candidates.consolidator import consolidate_units
from app.experiments.noun_units_v2a.candidates.report import build_report, deterministic_sample
from app.experiments.noun_units_v2a.candidates.statistics import build_statistics
from app.experiments.noun_units_v2a.candidates.writer import load_json, load_jsonl, sha256_data, sha256_file, write_json, write_jsonl, write_text


EXPERIMENT_ID = "noun-units-v2a-candidate-pool"
SCHEMA_VERSION = "1.0"
DEFAULT_SEED = 1661
REPO_ROOT = settings.DATA_DIR.parent


def default_candidate_config() -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "schema_version": SCHEMA_VERSION,
        "random_seed": DEFAULT_SEED,
        "exclude_generic_single_nouns": True,
        "max_example_contexts_per_candidate": 5,
    }


def ensure_candidate_config(output_root: Path) -> tuple[dict[str, Any], dict[str, str], set[str]]:
    config_dir = output_root / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "candidate_config.json"
    noise_path = config_dir / "leading_noise_terms.txt"
    ortho_path = config_dir / "orthographic_map.json"
    if not config_path.exists():
        write_json(config_path, default_candidate_config())
    if not noise_path.exists():
        write_text(noise_path, "\n".join(default_leading_noise_terms()) + "\n")
    if not ortho_path.exists():
        write_json(ortho_path, default_orthographic_map())
    config = load_json(config_path)
    orthographic_map = load_json(ortho_path)
    leading_noise_terms = {line.strip().casefold() for line in noise_path.read_text(encoding="utf-8").splitlines() if line.strip() and not line.startswith("#")}
    return config, orthographic_map, leading_noise_terms


def read_generic_nouns(path: Path) -> set[str]:
    return {line.strip().casefold() for line in path.read_text(encoding="utf-8").splitlines() if line.strip() and not line.startswith("#")}


def stable_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return path.name


def source_paths(v2a_root: Path) -> dict[str, Path]:
    generated = v2a_root / "generated"
    return {
        "normalized_units": generated / "noun_units_normalized.jsonl",
        "accepted_units": generated / "noun_units_accepted.jsonl",
        "review_units": generated / "noun_units_review.jsonl",
        "manifest": generated / "noun_unit_manifest.json",
        "statistics": generated / "noun_unit_statistics.json",
        "generic_nouns": v2a_root / "config" / "generic_nouns.txt",
    }


def run_candidate_pool(v2a_root: Path, output_root: Path, questions_path: Path, model_name: str = "en_core_web_sm", skip_baseline_extraction: bool = False) -> dict[str, Any]:
    config, orthographic_map, leading_noise_terms = ensure_candidate_config(output_root)
    paths = source_paths(v2a_root)
    source_hashes_before = {name: sha256_file(path) for name, path in paths.items()}
    units = load_jsonl(paths["normalized_units"])
    generic_nouns = read_generic_nouns(paths["generic_nouns"])
    candidates, merge_map = consolidate_units(units, generic_nouns, leading_noise_terms, orthographic_map, config)
    if skip_baseline_extraction:
        question_units = []
    else:
        question_units = extract_question_units_with_spacy(questions_path, model_name)
    coverage_rows, candidate_matches = analyze_question_units(question_units, candidates, orthographic_map)
    for candidate in candidates:
        matches = sorted(set(candidate_matches.get(candidate["candidate_uid"], [])))
        candidate["baseline_question_matches"] = matches
        candidate["baseline_diagnostic_only"] = True
    stats = build_statistics(len(units), candidates, merge_map, coverage_rows)
    generated = output_root / "generated"
    review = output_root / "review"
    reports = output_root / "reports"
    tiers = {
        "noun_embedding_candidates_all.jsonl": candidates,
        "noun_embedding_candidates_tier_a.jsonl": [c for c in candidates if c["tier"] == "tier_a"],
        "noun_embedding_candidates_tier_b.jsonl": [c for c in candidates if c["tier"] == "tier_b"],
        "noun_embedding_candidates_review.jsonl": [c for c in candidates if c["tier"] == "review"],
        "noun_embedding_candidates_excluded.jsonl": [c for c in candidates if c["tier"] == "excluded"],
    }
    for filename, rows in tiers.items():
        write_jsonl(generated / filename, rows)
    write_jsonl(generated / "noun_candidate_merge_map.jsonl", merge_map)
    write_json(generated / "noun_candidate_statistics.json", stats)
    sample = deterministic_sample(candidates, config.get("random_seed", DEFAULT_SEED))
    write_jsonl(review / "noun_candidate_manual_sample.jsonl", sample)
    config_hash = sha256_data(config)
    report = build_report(stats, candidates, merge_map, coverage_rows, source_hashes_before, config_hash)
    write_text(reports / "embedding_candidate_report.md", report)
    output_hashes = {
        path.name: sha256_file(path)
        for path in sorted(list(generated.glob("*.jsonl")) + [generated / "noun_candidate_statistics.json", review / "noun_candidate_manual_sample.jsonl", reports / "embedding_candidate_report.md"])
    }
    manifest_stub = {
        "experiment_id": EXPERIMENT_ID,
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_artifact_paths": {name: stable_path(path) for name, path in paths.items()},
        "source_artifact_hashes": source_hashes_before,
        "candidate_configuration_hash": config_hash,
        "normalization_map_hash": sha256_data(orthographic_map),
        "generic_noun_list_hash": source_hashes_before["generic_nouns"],
        "random_seed": config.get("random_seed", DEFAULT_SEED),
        "candidate_counts": stats["tier_counts"],
        "output_hashes": output_hashes,
    }
    reproducibility = {
        "source_artifact_hashes": source_hashes_before,
        "candidate_configuration_hash": manifest_stub["candidate_configuration_hash"],
        "normalization_map_hash": manifest_stub["normalization_map_hash"],
        "generic_noun_list_hash": manifest_stub["generic_noun_list_hash"],
        "random_seed": manifest_stub["random_seed"],
        "candidate_counts": manifest_stub["candidate_counts"],
        "output_hashes": output_hashes,
    }
    manifest = {**manifest_stub, "reproducibility_content_hash": sha256_data(reproducibility), "reproducibility": reproducibility}
    write_json(generated / "noun_candidate_manifest.json", manifest)
    source_hashes_after = {name: sha256_file(path) for name, path in paths.items()}
    if source_hashes_after != source_hashes_before:
        raise RuntimeError("Existing V2A source artifacts changed during candidate generation.")
    return {"statistics": stats, "manifest": manifest}


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build V2A.1 noun embedding candidate pool.")
    parser.add_argument("--v2a-root", type=Path, default=REPO_ROOT / "experiments" / "noun_units_v2a")
    parser.add_argument("--output-root", type=Path, default=REPO_ROOT / "experiments" / "noun_units_v2a" / "candidates")
    parser.add_argument("--questions", type=Path, default=REPO_ROOT / "experiments" / "baseline_v1" / "questions.json")
    parser.add_argument("--model", default="en_core_web_sm")
    parser.add_argument("--skip-baseline-extraction", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_arg_parser().parse_args(argv)
    result = run_candidate_pool(args.v2a_root, args.output_root, args.questions, args.model, args.skip_baseline_extraction)
    stats = result["statistics"]
    print(f"Built {stats['consolidated_lexical_candidate_count']} candidates.")
    print(f"Tier counts: {json.dumps(stats['tier_counts'], sort_keys=True)}")
    print(f"Output: {args.output_root}")

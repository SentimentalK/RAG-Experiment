import csv
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any


def json_sha256(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8192):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
            handle.write("\n")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _csv_value(row.get(key)) for key in fieldnames})


def _csv_value(value: Any) -> Any:
    if isinstance(value, list | tuple | dict):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value


class AtomicRunPublisher:
    def __init__(self, output_root: Path, run_id: str) -> None:
        self.output_root = output_root
        self.run_id = run_id
        self.final_dir = output_root / run_id
        self.tmp_dir = output_root / f".tmp_{run_id}"

    def __enter__(self) -> Path:
        if self.final_dir.exists():
            raise FileExistsError(f"Run directory already exists: {self.final_dir}")
        if self.tmp_dir.exists():
            shutil.rmtree(self.tmp_dir)
        self.tmp_dir.mkdir(parents=True)
        (self.tmp_dir / "traces").mkdir()
        return self.tmp_dir

    def __exit__(self, exc_type, exc, tb) -> bool:
        if exc_type is not None:
            failed_dir = self.output_root / f"{self.run_id}_failed"
            if failed_dir.exists():
                shutil.rmtree(failed_dir)
            if self.tmp_dir.exists():
                self.tmp_dir.rename(failed_dir)
            return False
        self.tmp_dir.rename(self.final_dir)
        return False


def validate_run_artifacts(run_dir: Path, trace_refs: list[dict[str, str]]) -> None:
    for relative in ["question_results.jsonl", "summary.json", "summary.csv", "failures.jsonl"]:
        path = run_dir / relative
        if not path.exists():
            raise ValueError(f"Missing run artifact: {relative}")
    for ref in trace_refs:
        path = run_dir / ref["trace_path"]
        if not path.exists():
            raise ValueError(f"Missing trace artifact: {ref['trace_path']}")
        if file_sha256(path) != ref["trace_sha256"]:
            raise ValueError(f"Trace hash mismatch: {ref['trace_path']}")
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if payload.get("original_query") is None:
            raise ValueError(f"Trace is not an ExpandedRetrievalTrace JSON: {ref['trace_path']}")


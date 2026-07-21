import argparse
import logging
from pathlib import Path

from app.core.config import settings
from app.evaluation.alias_retrieval.runner import run_alias_retrieval_evaluation


def parse_args() -> argparse.Namespace:
    root = settings.DATA_DIR.parent
    default_questions = root / "experiments" / "alias_query_expansion" / "evaluation" / "questions.json"
    default_output = root / "experiments" / "alias_query_expansion" / "evaluation" / "runs"
    parser = argparse.ArgumentParser(description="Run offline alias retrieval evaluation.")
    parser.add_argument("--questions", type=Path, default=default_questions)
    parser.add_argument("--modes", default="baseline,strong_only,strong_story")
    parser.add_argument("--output", type=Path, default=default_output)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--require-official-dataset", action="store_true")
    parser.add_argument("--continue-on-question-error", action="store_true")
    parser.add_argument("--document-id", default=None)
    parser.add_argument("--chunks", type=Path, default=settings.PROCESSED_DATA_DIR / "chunks.jsonl")
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    args = parse_args()
    modes = tuple(item.strip() for item in args.modes.split(",") if item.strip())
    result = run_alias_retrieval_evaluation(
        questions_path=args.questions,
        output_root=args.output,
        modes=modes,
        run_id=args.run_id,
        require_official_dataset=args.require_official_dataset,
        continue_on_question_error=args.continue_on_question_error,
        document_id=args.document_id,
        chunks_path=args.chunks,
    )
    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()


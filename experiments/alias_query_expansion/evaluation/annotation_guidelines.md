# Alias Retrieval Evaluation Annotation Guidelines

This seed dataset evaluates retrieval only. Gold evidence must identify chunks that directly support the answer.

Rules:

- Keep question text unchanged for `legacy_regression` questions.
- Put required direct facts only in `gold_evidence_groups`.
- Put helpful but insufficient context in `supporting_chunk_uids`.
- Put misleading chunks in `contradictory_chunk_uids`.
- Do not use reference answers, expected aliases, story IDs, or gold chunks to influence retrieval.
- Mark `dataset_manifest.json` as `official_evaluation_ready=true` only after independent review.


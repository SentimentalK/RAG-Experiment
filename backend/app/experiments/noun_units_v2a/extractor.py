import argparse
import hashlib
import json
import random
import re
import shutil
import string
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from app.core.config import settings


EXPERIMENT_ID = "noun-units-v2a"
SCHEMA_VERSION = "1.0"
DOCUMENT_ID = "gutenberg-1661"
DEFAULT_SEED = 1661
REPO_ROOT = settings.DATA_DIR.parent
ENTITY_TYPES = {"PERSON", "GPE", "LOC", "FAC", "ORG", "EVENT", "WORK_OF_ART", "PRODUCT"}
TITLE_PREFIXES = {"Mr.", "Mrs.", "Miss", "Dr.", "Sir", "Lord", "Lady", "Count", "King"}
PRONOUNS = {"i", "me", "you", "he", "him", "she", "her", "it", "we", "us", "they", "them", "myself", "himself", "herself", "itself", "ourselves", "themselves"}
DETERMINERS = {"a", "an", "the", "this", "that", "these", "those", "my", "your", "his", "her", "its", "our", "their"}
STOP_WORDS = DETERMINERS | {"and", "or", "but", "of", "to", "in", "on", "at", "by", "for", "with", "from", "as"}
QUOTE_PUNCT = "\"'`“”‘’«»"
SOURCE_PRIORITY = {"named_entity": 0, "proper_noun": 1, "noun_phrase": 2, "common_noun": 3}


@dataclass(frozen=True)
class NormalizedText:
    text: str
    norm_to_original: list[int]


def normalize_surface(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("’", "'").replace("‘", "'").replace("`", "'")
    text = re.sub(r"\s+", " ", text).strip()
    return text.strip(QUOTE_PUNCT + string.whitespace)


def normalize_for_matching(text: str) -> NormalizedText:
    chars: list[str] = []
    index: list[int] = []
    in_space = False
    for pos, char in enumerate(unicodedata.normalize("NFKC", text)):
        char = "'" if char in {"’", "‘", "`"} else char
        if char.isspace():
            if chars and not in_space:
                chars.append(" ")
                index.append(pos)
                in_space = True
        else:
            chars.append(char)
            index.append(pos)
            in_space = False
    if chars and chars[-1] == " ":
        chars.pop()
        index.pop()
    return NormalizedText("".join(chars), index)


def slugify(text: str) -> str:
    value = normalize_surface(text).lower()
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value or "untitled"


def story_id(section: dict[str, Any]) -> str:
    return f"s{section['section_order']:02d}-{slugify(section['title'])}"


def stable_uid(prefix: str, key: str, length: int = 16) -> str:
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:length]
    return f"{prefix}-{digest}"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_data(data: Any) -> str:
    raw = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False, sort_keys=True)
        handle.write("\n")
    tmp.replace(path)


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    tmp.replace(path)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def default_config() -> dict[str, Any]:
    return {
        "experiment_id": EXPERIMENT_ID,
        "schema_version": SCHEMA_VERSION,
        "entity_types": sorted(ENTITY_TYPES),
        "title_prefixes": sorted(TITLE_PREFIXES),
        "max_phrase_tokens": 8,
        "accept_phrase_token_min": 2,
        "accept_phrase_token_max": 6,
        "random_seed": DEFAULT_SEED,
    }


def default_generic_nouns() -> list[str]:
    return [
        "thing", "something", "anything", "nothing", "one", "person", "people", "man", "men",
        "woman", "women", "time", "way", "case", "matter", "part", "place", "fact", "point",
        "kind", "sort",
    ]


def ensure_config(output_root: Path) -> tuple[dict[str, Any], set[str]]:
    config_dir = output_root / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "extraction_config.json"
    generic_path = config_dir / "generic_nouns.txt"
    if not config_path.exists():
        write_json(config_path, default_config())
    if not generic_path.exists():
        write_text(generic_path, "\n".join(default_generic_nouns()) + "\n")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    generic = {line.strip().lower() for line in generic_path.read_text(encoding="utf-8").splitlines() if line.strip() and not line.startswith("#")}
    return config, generic


def token_texts(span: Any) -> list[str]:
    return [token.text for token in span]


def strip_title(tokens: list[str]) -> tuple[str | None, str]:
    if tokens and tokens[0] in TITLE_PREFIXES:
        return tokens[0], normalize_surface(" ".join(tokens[1:]))
    return None, normalize_surface(" ".join(tokens))


def normalized_key(candidate: dict[str, Any]) -> str:
    unit_type = candidate["primary_unit_type"]
    if unit_type in {"named_entity", "proper_noun"}:
        title, stripped = strip_title(candidate["surface_text"].split())
        return f"{unit_type}|{candidate.get('entity_type') or ''}|{(stripped or candidate['surface_text']).casefold()}"
    if unit_type == "common_noun":
        return f"common_noun|{candidate.get('head_lemma') or candidate.get('lemma_text') or candidate['surface_text'].lower()}"
    return f"noun_phrase|{candidate.get('lemma_text') or candidate['surface_text'].lower()}"


def candidate_from_span(span: Any, source: str, entity_type: str | None = None) -> dict[str, Any]:
    root = getattr(span, "root", None)
    toks = list(span)
    leading_det = toks[0].text if toks and toks[0].pos_ == "DET" else None
    modifiers = [t.text for t in toks if t.i != root.i and t.pos_ in {"ADJ", "NOUN", "PROPN", "NUM"}] if root else []
    possessor = None
    for token in toks:
        if token.dep_ in {"poss", "nmod:poss"}:
            possessor = token.text
            break
    return {
        "span_start": span.start_char,
        "span_end": span.end_char,
        "surface_text": normalize_surface(span.text),
        "lemma_text": normalize_surface(" ".join(t.lemma_ for t in toks)),
        "source": source,
        "entity_type": entity_type,
        "pos_pattern": [t.pos_ for t in toks],
        "head_text": root.text if root else toks[-1].text if toks else "",
        "head_lemma": root.lemma_ if root else toks[-1].lemma_ if toks else "",
        "dependency_root": root.dep_ if root else None,
        "leading_determiner": leading_det,
        "modifiers": modifiers,
        "possessor": possessor,
    }


def extract_candidates(doc: Any) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for ent in doc.ents:
        if ent.label_ in ENTITY_TYPES:
            candidates.append(candidate_from_span(ent, "named_entity", ent.label_))
    tokens = list(doc)
    i = 0
    while i < len(tokens):
        start = i
        title_offset = 0
        if tokens[i].text in TITLE_PREFIXES and i + 1 < len(tokens) and tokens[i + 1].pos_ == "PROPN":
            i += 1
            title_offset = 1
        if tokens[i].pos_ == "PROPN":
            while i + 1 < len(tokens) and tokens[i + 1].pos_ == "PROPN":
                i += 1
            span = doc[tokens[start].i:tokens[i].i + 1]
            if len(span) > title_offset:
                candidates.append(candidate_from_span(span, "proper_noun"))
        i += 1
    for chunk in doc.noun_chunks:
        candidates.append(candidate_from_span(chunk, "noun_phrase"))
    for token in doc:
        if token.pos_ == "NOUN":
            candidates.append(candidate_from_span(doc[token.i:token.i + 1], "common_noun"))
    return [c for c in candidates if c["surface_text"]]


def primary_type(sources: Iterable[str]) -> str:
    return sorted(sources, key=lambda item: SOURCE_PRIORITY[item])[0]


def build_chunk_intervals(sections: list[dict[str, Any]], chunks: list[dict[str, Any]]) -> tuple[dict[int, list[dict[str, Any]]], list[dict[str, Any]]]:
    sections_by_order = {s["section_order"]: s for s in sections}
    normalized_sections = {order: normalize_for_matching(sec["text"]) for order, sec in sections_by_order.items()}
    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    failures: list[dict[str, Any]] = []
    for chunk in sorted(chunks, key=lambda c: (c["section_order"], c["chunk_order"])):
        grouped[chunk["section_order"]].append(chunk)
    intervals: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for order, ordered_chunks in grouped.items():
        normalized = normalized_sections.get(order)
        if not normalized:
            continue
        cursor = 0
        for chunk in ordered_chunks:
            chunk_norm = normalize_for_matching(chunk["text"]).text
            overlap_start = max(0, cursor - max(250, len(chunk_norm) // 2))
            found = normalized.text.find(chunk_norm, overlap_start)
            if found < 0:
                found = normalized.text.find(chunk_norm)
            if found < 0:
                failures.append({"chunk_uid": chunk["chunk_id"], "section_order": order, "mapping_reason": "chunk_text_not_found"})
                continue
            norm_end = found + len(chunk_norm)
            orig_start = normalized.norm_to_original[found] if found < len(normalized.norm_to_original) else 0
            orig_end = normalized.norm_to_original[norm_end - 1] + 1 if norm_end - 1 < len(normalized.norm_to_original) else len(sections_by_order[order]["text"])
            intervals[order].append({
                "chunk_uid": chunk["chunk_id"],
                "chunk_order": chunk["chunk_order"],
                "normalized_start": found,
                "normalized_end": norm_end,
                "start": orig_start,
                "end": orig_end,
            })
            cursor = found + max(1, len(chunk_norm) // 2)
    return intervals, failures


def map_occurrence_to_chunks(occ: dict[str, Any], intervals: dict[int, list[dict[str, Any]]]) -> None:
    containing = [
        interval for interval in intervals.get(occ["section_order"], [])
        if interval["start"] <= occ["span_start"] and interval["end"] >= occ["span_end"]
    ]
    if not containing:
        containing = [
            interval for interval in intervals.get(occ["section_order"], [])
            if interval["start"] <= occ["sentence_start"] and interval["end"] >= occ["sentence_end"]
        ]
    if containing:
        containing.sort(key=lambda item: item["chunk_order"])
        occ["containing_chunk_uids"] = [item["chunk_uid"] for item in containing]
        occ["primary_chunk_uid"] = containing[0]["chunk_uid"]
        occ["mapping_status"] = "mapped"
        occ["mapping_reason"] = None
    else:
        occ["containing_chunk_uids"] = []
        occ["primary_chunk_uid"] = None
        occ["mapping_status"] = "unmapped"
        occ["mapping_reason"] = "no_containing_chunk_interval"


def merge_span_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[int, int, str], list[dict[str, Any]]] = defaultdict(list)
    for candidate in candidates:
        grouped[(candidate["span_start"], candidate["span_end"], normalize_surface(candidate["surface_text"]).casefold())].append(candidate)
    merged = []
    for (_, _, _), items in grouped.items():
        sources = sorted({item["source"] for item in items}, key=lambda s: SOURCE_PRIORITY[s])
        primary_source = primary_type(sources)
        primary = next(item for item in items if item["source"] == primary_source)
        entity_types = sorted({item["entity_type"] for item in items if item.get("entity_type")})
        source_metadata = {item["source"]: {k: v for k, v in item.items() if k != "source"} for item in items}
        record = dict(primary)
        record["extraction_sources"] = sources
        record["primary_unit_type"] = primary_source
        record["entity_type"] = entity_types[0] if entity_types else primary.get("entity_type")
        record["entity_types"] = entity_types
        record["source_metadata"] = source_metadata
        merged.append(record)
    return sorted(merged, key=lambda c: (c["span_start"], c["span_end"], SOURCE_PRIORITY[c["primary_unit_type"]], c["surface_text"]))


def build_occurrences(sections: list[dict[str, Any]], chunks: list[dict[str, Any]], nlp: Any, model_name: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    chunk_intervals, chunk_mapping_failures = build_chunk_intervals(sections, chunks)
    model_version = getattr(getattr(nlp, "meta", {}), "get", lambda *_: None)("version") if hasattr(nlp, "meta") else None
    if not model_version and hasattr(nlp, "meta"):
        model_version = nlp.meta.get("version")
    occurrences: list[dict[str, Any]] = []
    sentence_count = 0
    token_count = 0
    per_section_counter: dict[int, int] = defaultdict(int)
    for section in sections:
        doc = nlp(section["text"])
        token_count += len(doc)
        sentences = list(doc.sents)
        sentence_count += len(sentences)
        candidates_by_sentence: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for candidate in merge_span_candidates(extract_candidates(doc)):
            for idx, sent in enumerate(sentences, start=1):
                if sent.start_char <= candidate["span_start"] and sent.end_char >= candidate["span_end"]:
                    candidates_by_sentence[idx].append(candidate)
                    break
        for idx, sent in enumerate(sentences, start=1):
            sent_candidates = candidates_by_sentence.get(idx, [])
            prev_sentence = sentences[idx - 2].text if idx > 1 else None
            next_sentence = sentences[idx].text if idx < len(sentences) else None
            for candidate in sent_candidates:
                per_section_counter[section["section_order"]] += 1
                occ = {
                    "occurrence_uid": f"noun-occ-s{section['section_order']:02d}-{per_section_counter[section['section_order']]:06d}",
                    "document_id": DOCUMENT_ID,
                    "section_order": section["section_order"],
                    "story_id": story_id(section),
                    "story_title": section["title"],
                    "sentence_index": idx,
                    "sentence_start": sent.start_char,
                    "sentence_end": sent.end_char,
                    "span_start": candidate["span_start"],
                    "span_end": candidate["span_end"],
                    "surface_text": candidate["surface_text"],
                    "lemma_text": candidate["lemma_text"],
                    "unit_type": candidate["primary_unit_type"],
                    "primary_unit_type": candidate["primary_unit_type"],
                    "extraction_sources": candidate["extraction_sources"],
                    "entity_type": candidate.get("entity_type"),
                    "entity_types": candidate.get("entity_types", []),
                    "pos_pattern": candidate.get("pos_pattern", []),
                    "head_text": candidate.get("head_text"),
                    "head_lemma": candidate.get("head_lemma"),
                    "dependency_root": candidate.get("dependency_root"),
                    "leading_determiner": candidate.get("leading_determiner"),
                    "modifiers": candidate.get("modifiers", []),
                    "possessor": candidate.get("possessor"),
                    "source_sentence": sent.text,
                    "previous_sentence": prev_sentence,
                    "next_sentence": next_sentence,
                    "source_metadata": candidate.get("source_metadata", {}),
                    "extractor": "spacy",
                    "model_name": model_name,
                    "model_version": model_version,
                }
                map_occurrence_to_chunks(occ, chunk_intervals)
                occurrences.append(occ)
    metadata = {
        "sentence_count": sentence_count,
        "token_count": token_count,
        "chunk_mapping_failures": chunk_mapping_failures,
    }
    return occurrences, metadata


def classify_unit(unit: dict[str, Any], generic_nouns: set[str], config: dict[str, Any]) -> tuple[str, list[str], str, list[str]]:
    text = unit["canonical_text"]
    key_text = normalize_surface(text).casefold()
    bare_key_text = key_text.strip(".")
    token_count = len(text.split())
    reasons: list[str] = []
    if not text:
        return "rejected", ["empty"], "not_expandable", ["invalid_unit"]
    if all(ch in string.punctuation for ch in text):
        return "rejected", ["punctuation_only"], "not_expandable", ["invalid_unit"]
    if key_text.isnumeric():
        return "rejected", ["numeric_only"], "not_expandable", ["invalid_unit"]
    if len(key_text) == 1:
        return "rejected", ["single_character_fragment"], "not_expandable", ["invalid_unit"]
    if key_text in PRONOUNS or bare_key_text in PRONOUNS:
        return "rejected", ["pronoun"], "not_expandable", ["invalid_unit"]
    abbreviated_titles = {"mr.", "mrs.", "dr."}
    title_words = {title.casefold() for title in TITLE_PREFIXES if title.casefold() not in abbreviated_titles}
    if key_text in abbreviated_titles:
        return "rejected", ["parser_artifact", "title_only"], "not_expandable", ["invalid_unit"]
    if key_text in title_words and unit["unit_type"] in {"proper_noun", "named_entity"}:
        return "review", ["title_or_role_only"], "possibly_expandable", ["title_or_role"]
    if re.fullmatch(r"[ivxlcdm]+\.", key_text):
        return "rejected", ["parser_artifact", "roman_numeral_heading"], "not_expandable", ["invalid_unit"]
    if key_text in DETERMINERS:
        return "rejected", ["determiner"], "not_expandable", ["invalid_unit"]
    if all(part in STOP_WORDS for part in key_text.split()):
        return "rejected", ["stop_word_only"], "not_expandable", ["invalid_unit"]
    if token_count > config.get("max_phrase_tokens", 8):
        return "rejected", ["too_long"], "not_expandable", ["malformed_or_too_long"]
    if not any(pos in {"NOUN", "PROPN"} for pattern in unit["pos_patterns"] for pos in pattern):
        return "rejected", ["without_noun_content"], "not_expandable", ["invalid_unit"]
    if unit["unit_type"] == "common_noun" and key_text in generic_nouns:
        return "review", ["generic_single_noun"], "not_expandable", ["generic_term"]
    if unit["unit_type"] in {"named_entity", "proper_noun"}:
        if unit["unit_type"] == "proper_noun" and token_count == 1 and unit["occurrence_count"] == 1:
            return "review", ["single_occurrence_proper_noun"], "possibly_expandable", ["rare_name"]
        return "accepted", ["well_formed_name_or_entity"], "expandable", ["named_or_proper_unit"]
    if unit["unit_type"] == "noun_phrase":
        if unit.get("possessors"):
            return "review", ["possessive_phrase"], "possibly_expandable", ["relational_phrase"]
        if token_count >= 5:
            return "review", ["long_noun_phrase"], "possibly_expandable", ["complex_phrase"]
        head = (unit.get("head_noun") or "").casefold()
        if head in generic_nouns:
            return "review", ["generic_head_with_modifiers"], "possibly_expandable", ["specific_modifier_generic_head"]
        return "accepted", ["specific_multiword_noun_phrase"], "expandable", ["specific_phrase"]
    if unit["unit_type"] == "common_noun":
        return "accepted", ["concrete_non_generic_common_noun"], "possibly_expandable", ["common_noun"]
    reasons.append("fallback_review")
    return "review", reasons, "possibly_expandable", ["fallback"]


def aggregate_units(occurrences: list[dict[str, Any]], generic_nouns: set[str], config: dict[str, Any]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for occ in occurrences:
        groups[normalized_key(occ)].append(occ)
    units: list[dict[str, Any]] = []
    for key, items in groups.items():
        items = sorted(items, key=lambda o: (o["section_order"], o["span_start"], o["span_end"], o["surface_text"]))
        primary = sorted(items, key=lambda o: SOURCE_PRIORITY[o["primary_unit_type"]])[0]
        surface_counts = Counter(o["surface_text"] for o in items)
        canonical = surface_counts.most_common(1)[0][0]
        story_ids = sorted({o["story_id"] for o in items})
        chunk_ids = sorted({cid for o in items for cid in o["containing_chunk_uids"]})
        unit = {
            "unit_uid": stable_uid("noun-unit", key),
            "normalized_key": key,
            "canonical_text": canonical,
            "surface_forms": sorted(surface_counts),
            "unit_type": primary["primary_unit_type"],
            "extraction_sources": sorted({src for o in items for src in o["extraction_sources"]}, key=lambda s: SOURCE_PRIORITY[s]),
            "entity_types": sorted({etype for o in items for etype in o.get("entity_types", [])}),
            "pos_patterns": sorted({tuple(o["pos_pattern"]) for o in items}),
            "head_noun": primary.get("head_text"),
            "head_lemma": primary.get("head_lemma"),
            "possessors": sorted({o["possessor"] for o in items if o.get("possessor")}),
            "occurrence_count": len(items),
            "story_count": len(story_ids),
            "story_ids": story_ids,
            "source_chunk_uids": chunk_ids,
            "example_sentences": [o["source_sentence"] for o in items[:3]],
            "example_contexts": [
                {
                    "occurrence_uid": o["occurrence_uid"],
                    "story_id": o["story_id"],
                    "source_sentence": o["source_sentence"],
                    "primary_chunk_uid": o["primary_chunk_uid"],
                }
                for o in items[:3]
            ],
            "first_occurrence": items[0]["occurrence_uid"],
            "last_occurrence": items[-1]["occurrence_uid"],
        }
        classification, reasons, expandable, expandable_reasons = classify_unit(unit, generic_nouns, config)
        unit["classification"] = classification
        unit["classification_reasons"] = reasons
        unit["expandability_label"] = expandable
        unit["expandability_reasons"] = expandable_reasons
        units.append(unit)
    return sorted(units, key=lambda u: (u["classification"], u["unit_type"], u["canonical_text"].casefold(), u["unit_uid"]))


def quality_issues(units: list[dict[str, Any]], occurrences: list[dict[str, Any]]) -> list[dict[str, Any]]:
    issues = []
    by_text: dict[str, set[str]] = defaultdict(set)
    for unit in units:
        for entity_type in unit["entity_types"]:
            by_text[unit["canonical_text"].casefold()].add(entity_type)
        if len(unit["canonical_text"].split()) > 8:
            issues.append({"issue_type": "possibly_overlong_phrase", "unit_uid": unit["unit_uid"], "text": unit["canonical_text"]})
        if "generic_single_noun" in unit["classification_reasons"] and unit["classification"] == "accepted":
            issues.append({"issue_type": "possible_generic_false_positive", "unit_uid": unit["unit_uid"], "text": unit["canonical_text"]})
        if unit["classification"] == "rejected" and unit["occurrence_count"] >= 2:
            issues.append({"issue_type": "possible_specific_false_rejection", "unit_uid": unit["unit_uid"], "text": unit["canonical_text"]})
    for text, labels in by_text.items():
        if len(labels) > 1:
            issues.append({"issue_type": "possible_entity_conflict", "text": text, "entity_types": sorted(labels)})
    for occ in occurrences:
        if occ["mapping_status"] == "unmapped":
            issues.append({"issue_type": "unmapped_source_occurrence", "occurrence_uid": occ["occurrence_uid"], "text": occ["surface_text"]})
    return sorted(issues, key=lambda i: (i["issue_type"], i.get("text", ""), i.get("unit_uid", ""), i.get("occurrence_uid", "")))


def sample_units(units: list[dict[str, Any]], seed: int) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    selected: dict[str, dict[str, Any]] = {}
    strata = [
        ("named_or_proper", [u for u in units if u["unit_type"] in {"named_entity", "proper_noun"}]),
        ("common_noun", [u for u in units if u["unit_type"] == "common_noun"]),
        ("noun_phrase", [u for u in units if u["unit_type"] == "noun_phrase"]),
        ("review_or_rejected", [u for u in units if u["classification"] in {"review", "rejected"}]),
    ]
    for name, rows in strata:
        rows = sorted(rows, key=lambda u: u["unit_uid"])
        rng.shuffle(rows)
        count = 0
        for unit in rows:
            if unit["unit_uid"] in selected:
                continue
            row = {
                "unit_uid": unit["unit_uid"],
                "canonical_text": unit["canonical_text"],
                "unit_type": unit["unit_type"],
                "frequency": unit["occurrence_count"],
                "story_ids": unit["story_ids"],
                "example_sentence": unit["example_sentences"][0] if unit["example_sentences"] else None,
                "chunk_uid": unit["example_contexts"][0]["primary_chunk_uid"] if unit["example_contexts"] else None,
                "classification": unit["classification"],
                "classification_reasons": unit["classification_reasons"],
                "sampling_stratum": name,
                "sampling_seed": seed,
            }
            selected[unit["unit_uid"]] = row
            count += 1
            if count >= 50:
                break
    return sorted(selected.values(), key=lambda r: (r["sampling_stratum"], r["canonical_text"].casefold(), r["unit_uid"]))


def extract_question_units(questions_path: Path, nlp: Any) -> list[dict[str, Any]]:
    if not questions_path.exists():
        return []
    data = json.loads(questions_path.read_text(encoding="utf-8"))
    rows = []
    for question in data.get("questions", []):
        doc = nlp(question["question"])
        for candidate in merge_span_candidates(extract_candidates(doc)):
            rows.append({
                "question_id": question["question_id"],
                "question": question["question"],
                "surface_text": candidate["surface_text"],
                "normalized_key": normalized_key({
                    **candidate,
                    "primary_unit_type": candidate["primary_unit_type"],
                }),
                "unit_type": candidate["primary_unit_type"],
            })
    return sorted(rows, key=lambda r: (r["question_id"], r["surface_text"].casefold()))


def build_statistics(sections: list[dict[str, Any]], chunks: list[dict[str, Any]], occurrences: list[dict[str, Any]], units: list[dict[str, Any]], metadata: dict[str, Any]) -> dict[str, Any]:
    occ_by_type = Counter(o["primary_unit_type"] for o in occurrences)
    unit_by_type = Counter(u["unit_type"] for u in units)
    classification = Counter(u["classification"] for u in units)
    mapped = sum(1 for o in occurrences if o["mapping_status"] == "mapped")
    phrase_lengths = Counter()
    for unit in units:
        token_count = len(unit["canonical_text"].split())
        if token_count <= 5:
            phrase_lengths[str(token_count)] += 1
        elif token_count <= 8:
            phrase_lengths["6-8"] += 1
        else:
            phrase_lengths[">8"] += 1
    return {
        "story_count": len(sections),
        "chunk_count": len(chunks),
        "sentence_count": metadata["sentence_count"],
        "token_count": metadata["token_count"],
        "raw_occurrence_count": len(occurrences),
        "normalized_unit_count": len(units),
        "occurrences_by_type": dict(sorted(occ_by_type.items())),
        "units_by_type": dict(sorted(unit_by_type.items())),
        "classification_counts": dict(sorted(classification.items())),
        "mapping": {
            "successfully_mapped_occurrences": mapped,
            "unmapped_occurrences": len(occurrences) - mapped,
            "mapping_success_percentage": round((mapped / len(occurrences) * 100) if occurrences else 100.0, 2),
            "chunk_mapping_failures": metadata.get("chunk_mapping_failures", []),
        },
        "phrase_length_distribution": dict(sorted(phrase_lengths.items())),
        "frequency_thresholds": {
            "frequency_gte_2": sum(1 for u in units if u["occurrence_count"] >= 2),
            "frequency_gte_3": sum(1 for u in units if u["occurrence_count"] >= 3),
            "frequency_gte_5": sum(1 for u in units if u["occurrence_count"] >= 5),
            "frequency_gte_10": sum(1 for u in units if u["occurrence_count"] >= 10),
        },
    }


def markdown_table(rows: list[list[Any]], headers: list[str]) -> str:
    if not rows:
        return "_None._\n"
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(str(cell).replace("\n", " ") for cell in row) + " |")
    return "\n".join(lines) + "\n"


def build_report(stats: dict[str, Any], units: list[dict[str, Any]], occurrences: list[dict[str, Any]], manifest_stub: dict[str, Any], issues: list[dict[str, Any]], question_rows: list[dict[str, Any]]) -> str:
    by_uid = {u["unit_uid"]: u for u in units}
    key_to_unit = {u["normalized_key"]: u for u in units}
    top = sorted(units, key=lambda u: (-u["occurrence_count"], u["canonical_text"].casefold()))
    def top_rows(unit_type: str | None = None, limit: int = 20) -> list[list[Any]]:
        rows = [u for u in top if unit_type is None or u["unit_type"] == unit_type][:limit]
        return [[u["canonical_text"], u["unit_type"], u["occurrence_count"], u["story_count"], u["classification"]] for u in rows]
    coverage_rows = []
    for row in question_rows:
        match = key_to_unit.get(row["normalized_key"])
        coverage_rows.append([row["question_id"], row["surface_text"], row["unit_type"], "yes" if match else "no", match["canonical_text"] if match else ""])
    sample_rows = [[u["canonical_text"], u["unit_type"], u["occurrence_count"], ", ".join(u["story_ids"][:3]), u["classification"], ";".join(u["classification_reasons"])] for u in top[:50]]
    issue_rows = [[i["issue_type"], i.get("text") or i.get("unit_uid") or i.get("occurrence_uid"), json.dumps(i, ensure_ascii=False, sort_keys=True)] for i in issues[:50]]
    review_workload = [
        ["accepted + review units", sum(1 for u in units if u["classification"] in {"accepted", "review"})],
        ["named entities only", sum(1 for u in units if u["unit_type"] == "named_entity")],
        ["proper nouns only", sum(1 for u in units if u["unit_type"] == "proper_noun")],
        ["multiword noun phrases only", sum(1 for u in units if u["unit_type"] == "noun_phrase" and len(u["canonical_text"].split()) > 1)],
        ["frequency >= 2", stats["frequency_thresholds"]["frequency_gte_2"]],
        ["frequency >= 3", stats["frequency_thresholds"]["frequency_gte_3"]],
        ["possibly_expandable only", sum(1 for u in units if u["expandability_label"] == "possibly_expandable")],
    ]
    duplicate_examples = []
    for stem in ["holmes", "pawnbroker", "woman", "adler"]:
        matches = [u for u in units if stem in u["canonical_text"].casefold()]
        for u in sorted(matches, key=lambda x: (len(x["canonical_text"]), x["canonical_text"]))[:8]:
            duplicate_examples.append([stem, u["canonical_text"], u["unit_type"], u["classification"]])
    return "\n".join([
        "# Corpus Noun Report",
        "",
        "This report is exploratory. Accepted/review/rejected and expandability labels are provisional rule-based labels, not validated query-expansion decisions.",
        "",
        "## Corpus Summary",
        markdown_table([
            ["Stories processed", stats["story_count"]],
            ["Chunks loaded for provenance", stats["chunk_count"]],
            ["Sentences processed", stats["sentence_count"]],
            ["Tokens processed", stats["token_count"]],
            ["spaCy version", manifest_stub["spacy_version"]],
            ["Model", f"{manifest_stub['model_name']} {manifest_stub['model_version']}"],
            ["Sections SHA-256", manifest_stub["input_hashes"].get("sections")],
            ["Chunks SHA-256", manifest_stub["input_hashes"].get("chunks")],
            ["Config hash", manifest_stub["configuration_hash"]],
        ], ["Metric", "Value"]),
        "## Extraction Counts",
        markdown_table([
            ["raw occurrences", stats["raw_occurrence_count"]],
            ["normalized units", stats["normalized_unit_count"]],
            ["accepted units", stats["classification_counts"].get("accepted", 0)],
            ["review units", stats["classification_counts"].get("review", 0)],
            ["rejected units", stats["classification_counts"].get("rejected", 0)],
            ["mapped occurrences", stats["mapping"]["successfully_mapped_occurrences"]],
            ["unmapped occurrences", stats["mapping"]["unmapped_occurrences"]],
            ["mapping success %", stats["mapping"]["mapping_success_percentage"]],
        ], ["Metric", "Count"]),
        "Occurrences by type: `" + json.dumps(stats["occurrences_by_type"], sort_keys=True) + "`",
        "",
        "Units by type: `" + json.dumps(stats["units_by_type"], sort_keys=True) + "`",
        "",
        "## Frequency Distribution",
        "### Top Common Nouns",
        markdown_table(top_rows("common_noun"), ["Expression", "Type", "Frequency", "Stories", "Class"]),
        "### Top Proper Nouns",
        markdown_table(top_rows("proper_noun"), ["Expression", "Type", "Frequency", "Stories", "Class"]),
        "### Top Named Entities",
        markdown_table(top_rows("named_entity"), ["Expression", "Type", "Frequency", "Stories", "Class"]),
        "### Top Noun Phrases",
        markdown_table(top_rows("noun_phrase"), ["Expression", "Type", "Frequency", "Stories", "Class"]),
        "Thresholds: `" + json.dumps(stats["frequency_thresholds"], sort_keys=True) + "`",
        "",
        "## Phrase-Length Distribution",
        "`" + json.dumps(stats["phrase_length_distribution"], sort_keys=True) + "`",
        "",
        "## Overlap and Duplication",
        "Same-span duplicate extractor hits are merged into one occurrence with multiple `extraction_sources`; nested spans remain separate units.",
        markdown_table(duplicate_examples[:30], ["Family", "Expression", "Type", "Class"]),
        "## Estimated Human-Review Workload",
        markdown_table(review_workload, ["Slice", "Units"]),
        "The vocabulary is likely practical for staged human review if the first pass focuses on named/proper units, multiword phrases, and frequency >= 2 candidates before reviewing all single generic nouns.",
        "",
        "## Quality Samples",
        markdown_table(sample_rows, ["Surface", "Type", "Frequency", "Story IDs", "Class", "Reasons"]),
        "## Potential Extraction Quality Issues",
        markdown_table(issue_rows, ["Issue", "Item", "Details"]),
        "## Baseline-Question Noun Coverage",
        markdown_table(coverage_rows, ["Question", "Question Noun", "Type", "In Corpus", "Corpus Match"]),
    ])


def load_spacy_model(model_name: str) -> Any:
    try:
        import spacy
    except ImportError as exc:
        raise RuntimeError("spaCy is not installed. Run `poetry install --with nlp,dev`.") from exc
    try:
        return spacy.load(model_name)
    except OSError as exc:
        raise RuntimeError(f"spaCy model {model_name!r} is not installed. Run `poetry install --with nlp,dev`.") from exc


def run_experiment(sections_path: Path, chunks_path: Path, output_root: Path, model_name: str = "en_core_web_sm", seed: int = DEFAULT_SEED, nlp: Any | None = None) -> dict[str, Any]:
    config, generic_nouns = ensure_config(output_root)
    sections = load_jsonl(sections_path)
    chunks = load_jsonl(chunks_path)
    nlp = nlp or load_spacy_model(model_name)
    occurrences, metadata = build_occurrences(sections, chunks, nlp, model_name)
    units = aggregate_units(occurrences, generic_nouns, config)
    stats = build_statistics(sections, chunks, occurrences, units, metadata)
    issues = quality_issues(units, occurrences)
    samples = sample_units(units, seed)
    question_rows = extract_question_units(REPO_ROOT / "experiments" / "baseline_v1" / "questions.json", nlp)
    generated = output_root / "generated"
    review = output_root / "review"
    reports = output_root / "reports"
    accepted = [u for u in units if u["classification"] == "accepted"]
    review_units = [u for u in units if u["classification"] == "review"]
    rejected = [u for u in units if u["classification"] == "rejected"]
    write_jsonl(generated / "noun_occurrences_raw.jsonl", occurrences)
    write_jsonl(generated / "noun_units_normalized.jsonl", units)
    write_jsonl(generated / "noun_units_accepted.jsonl", accepted)
    write_jsonl(generated / "noun_units_review.jsonl", review_units)
    write_jsonl(generated / "noun_units_rejected.jsonl", rejected)
    write_json(generated / "noun_unit_statistics.json", stats)
    write_jsonl(review / "manual_evaluation_sample.jsonl", samples)
    try:
        import spacy
        spacy_version = spacy.__version__
    except ImportError:
        spacy_version = None
    model_version = nlp.meta.get("version") if hasattr(nlp, "meta") else None
    manifest_stub = {
        "experiment_id": EXPERIMENT_ID,
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "input_paths": {"sections": str(sections_path), "chunks": str(chunks_path)},
        "input_hashes": {"sections": sha256_file(sections_path), "chunks": sha256_file(chunks_path)},
        "spacy_version": spacy_version,
        "model_name": model_name,
        "model_version": model_version,
        "configuration_hash": sha256_data(config),
        "random_seed": seed,
        "story_count": stats["story_count"],
        "sentence_count": stats["sentence_count"],
        "token_count": stats["token_count"],
        "raw_occurrence_count": stats["raw_occurrence_count"],
        "normalized_unit_count": stats["normalized_unit_count"],
        "accepted_count": len(accepted),
        "review_count": len(review_units),
        "rejected_count": len(rejected),
    }
    report = build_report(stats, units, occurrences, manifest_stub, issues, question_rows)
    write_text(reports / "corpus_noun_report.md", report)
    output_hashes = {
        path.name: sha256_file(path)
        for path in sorted(generated.glob("*"))
        if path.name != "noun_unit_manifest.json"
    }
    output_hashes["manual_evaluation_sample.jsonl"] = sha256_file(review / "manual_evaluation_sample.jsonl")
    output_hashes["corpus_noun_report.md"] = sha256_file(reports / "corpus_noun_report.md")
    reproducibility = {
        "input_hashes": manifest_stub["input_hashes"],
        "configuration_hash": manifest_stub["configuration_hash"],
        "model_name": model_name,
        "model_version": model_version,
        "content_hash": sha256_data({"stats": stats, "output_hashes": output_hashes}),
    }
    manifest = {**manifest_stub, "output_hashes": output_hashes, "reproducibility": reproducibility}
    write_json(generated / "noun_unit_manifest.json", manifest)
    return {"stats": stats, "manifest": manifest}


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Extract corpus noun units for the V2A experiment.")
    parser.add_argument("--sections", type=Path, default=settings.PROCESSED_DATA_DIR / "sections.jsonl")
    parser.add_argument("--chunks", type=Path, default=settings.PROCESSED_DATA_DIR / "chunks.jsonl")
    parser.add_argument("--output-root", type=Path, default=REPO_ROOT / "experiments" / "noun_units_v2a")
    parser.add_argument("--model", default="en_core_web_sm")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_arg_parser().parse_args(argv)
    result = run_experiment(args.sections, args.chunks, args.output_root, args.model, args.seed)
    stats = result["stats"]
    print(f"Extracted {stats['raw_occurrence_count']} occurrences and {stats['normalized_unit_count']} units.")
    print(f"Mapping success: {stats['mapping']['mapping_success_percentage']}%")
    print(f"Output: {args.output_root}")

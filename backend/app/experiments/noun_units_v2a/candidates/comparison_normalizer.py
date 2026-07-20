import re
import string
import unicodedata
from typing import Any


QUOTE_PUNCT = "\"'`“”‘’«»"
DASHES = {"\u2010", "\u2011", "\u2012", "\u2013", "\u2014", "\u2212"}
LIGATURES = {"æ": "ae", "Æ": "AE", "œ": "oe", "Œ": "OE"}
SURROUNDING_PUNCT_RE = re.compile(r"^[\s,;:!?\-—–]+|[\s,;:!?\-—–]+$")


def default_orthographic_map() -> dict[str, str]:
    return {
        "encyclopædia": "encyclopaedia",
        "encyclopædic": "encyclopaedic",
    }


def normalize_display(text: str) -> tuple[str, list[str]]:
    actions: list[str] = []
    original = text
    value = unicodedata.normalize("NFKC", text).replace("\u00a0", " ")
    for src, dst in LIGATURES.items():
        if src in value:
            value = value.replace(src, dst)
            actions.append("ligature_expanded")
    for src, dst in {"’": "'", "‘": "'", "`": "'", "“": '"', "”": '"'}.items():
        if src in value:
            value = value.replace(src, dst)
            actions.append("quote_normalized")
    value = "".join("-" if char in DASHES else char for char in value)
    if value != original and "unicode_normalized" not in actions:
        actions.append("unicode_normalized")
    collapsed = re.sub(r"\s+", " ", value).strip()
    if collapsed != value:
        actions.append("whitespace_collapsed")
    value = collapsed
    stripped_quotes = value.strip(QUOTE_PUNCT + string.whitespace)
    if stripped_quotes != value:
        actions.append("surrounding_quotes_removed")
    value = stripped_quotes
    if '"' in value:
        value = value.replace('"', "")
        actions.append("quote_punctuation_removed")
    stripped_punct = SURROUNDING_PUNCT_RE.sub("", value).strip()
    if stripped_punct != value:
        actions.append("surrounding_punctuation_removed")
    return stripped_punct, sorted(set(actions))


def comparison_form(text: str, orthographic_map: dict[str, str] | None = None) -> tuple[str, list[str]]:
    display, actions = normalize_display(text)
    value = display.casefold()
    if value != display:
        actions.append("case_folded")
    for src, dst in (orthographic_map or {}).items():
        pattern = re.compile(re.escape(src.casefold()))
        new_value = pattern.sub(dst.casefold(), value)
        if new_value != value:
            actions.append("orthographic_map_applied")
            value = new_value
    value = re.sub(r"\s+", " ", value).strip()
    return value, sorted(set(actions))


def token_count(text: str) -> int:
    return len([part for part in text.split(" ") if part])


CONTENT_FUNCTION_WORDS = {
    "a", "an", "the", "this", "that", "these", "those", "my", "your", "his", "her", "its", "our", "their",
    "of", "to", "in", "on", "at", "by", "for", "with", "from", "and", "or", "but",
    "who", "whom", "whose", "what", "which", "each", "all",
}


def content_tokens(text: str) -> list[str]:
    clean, _ = normalize_display(text)
    tokens = []
    for raw in re.findall(r"[A-Za-z0-9]+(?:[.'-][A-Za-z0-9]+)*", clean):
        token = raw.casefold().strip(".")
        if token in CONTENT_FUNCTION_WORDS:
            continue
        if token in {"mr", "mrs", "dr"} and len(clean.split()) > 1:
            continue
        tokens.append(raw)
    return tokens


def is_natural_capitalization(text: str) -> bool:
    letters = [char for char in text if char.isalpha()]
    if not letters:
        return False
    return not (all(char.isupper() for char in letters) or all(char.islower() for char in letters))


def representative_surface(forms: list[str], unit_lookup: dict[str, dict[str, Any]], flags_by_form: dict[str, set[str]], repaired_by_form: dict[str, bool], target_comparison_form: str | None = None) -> str:
    def score(form: str) -> tuple[int, int, int, int, int, str]:
        clean, _ = normalize_display(form)
        form_comparison, _ = comparison_form(form, {})
        flags = flags_by_form.get(form, set())
        source_units = [u for u in unit_lookup.values() if form in u.get("surface_forms", []) or form == u.get("canonical_text")]
        has_name_type = any(u.get("unit_type") in {"named_entity", "proper_noun"} for u in source_units)
        return (
            0 if target_comparison_form is None or form_comparison == target_comparison_form else 1,
            1 if flags else 0,
            1 if repaired_by_form.get(form) else 0,
            0 if has_name_type else 1,
            0 if is_natural_capitalization(clean) else 1,
            token_count(clean),
            clean.casefold(),
        )

    return normalize_display(sorted(forms, key=score)[0])[0]

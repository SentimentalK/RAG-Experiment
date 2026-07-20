import re
import string


PRONOUNS = {"i", "me", "you", "he", "him", "she", "her", "it", "we", "us", "they", "them", "myself", "himself", "herself", "itself", "ourselves", "themselves"}
DETERMINERS = {"a", "an", "the", "this", "that", "these", "those", "my", "your", "his", "her", "its", "our", "their"}
FUNCTION_WORDS = DETERMINERS | {
    "and", "or", "but", "of", "to", "in", "on", "at", "by", "for", "with", "from", "as",
    "who", "whom", "whose", "what", "which", "whoever", "whatever", "each", "all",
}
STOP_WORDS = FUNCTION_WORDS


def default_leading_noise_terms() -> list[str]:
    return ["and", "again", "ah", "oh", "well", "why", "yes", "no", "indeed", "now", "then", "awake"]


def is_address_like(text: str, comparison_form: str) -> bool:
    if re.fullmatch(r"\d+[A-Z]", text.strip()):
        return True
    if re.fullmatch(r"\d+\s+[A-Z][A-Za-z'.-]+(?:\s+[A-Z][A-Za-z'.-]+)*", text.strip()):
        return True
    suffixes = {"street", "st", "square", "court", "avenue", "road", "lane", "place", "yard"}
    parts = comparison_form.replace(".", "").split()
    return len(parts) >= 2 and parts[0].isdigit() and parts[-1] in suffixes


def quality_flags(text: str, comparison_form: str, generic_nouns: set[str], leading_noise_terms: set[str]) -> list[str]:
    flags: set[str] = set()
    lower = comparison_form
    bare = lower.strip(".")
    if not lower:
        flags.add("empty")
    if lower in PRONOUNS or bare in PRONOUNS:
        flags.add("pronoun")
    if lower in DETERMINERS:
        flags.add("determiner")
    address_like = is_address_like(text, lower)
    if address_like:
        flags.add("address_like")
    if lower and all(part in STOP_WORDS for part in lower.split()):
        flags.add("function_word_only")
    if lower in generic_nouns:
        flags.add("generic_single_noun")
    if re.fullmatch(r"\d+[a-z]?", lower) and not address_like:
        flags.add("numeric_expression")
    if re.fullmatch(r"\d+(st|nd|rd|th)", lower):
        flags.add("ordinal_expression")
    if "£" in text or re.fullmatch(r"\d+s|\d+d|s\.|d\.", lower):
        flags.add("currency_expression")
    if re.fullmatch(r"[a-z]\.", lower) or lower in {"no"}:
        flags.add("isolated_abbreviation")
    if re.fullmatch(r"[ivxlcdm]+\.", lower):
        flags.add("isolated_abbreviation")
    if text and text[0] in ",;:!?—–-":
        flags.add("leading_punctuation_removed")
    first = re.split(r"[\s,]+", lower, maxsplit=1)[0] if lower else ""
    if first in leading_noise_terms and len(lower.split()) > 1:
        flags.add("leading_discourse_marker")
    if lower in leading_noise_terms:
        flags.add("leading_discourse_marker")
    if re.search(r",\s*(who|and|i|he|she|which)\b", lower) or "—i" in lower:
        flags.add("suspected_sentence_fragment")
    if any(char in lower for char in [":", ";"]) or lower.count('"') % 2 == 1:
        flags.add("excessive_punctuation")
    if lower and all(char in string.punctuation for char in lower):
        flags.add("punctuation_only")
    letters = [char for char in text if char.isalpha()]
    if letters and all(char.isupper() for char in letters) and len(letters) >= 3:
        flags.add("all_caps_fragment")
    if re.fullmatch(r"[ivxlcdm]+\.", lower) or lower in {"chapter", "dear mr"}:
        flags.add("heading_fragment")
    return sorted(flags)

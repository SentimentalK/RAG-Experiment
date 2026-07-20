import re
import string


PRONOUNS = {"i", "me", "you", "he", "him", "she", "her", "it", "we", "us", "they", "them", "myself", "himself", "herself", "itself", "ourselves", "themselves"}
DETERMINERS = {"a", "an", "the", "this", "that", "these", "those", "my", "your", "his", "her", "its", "our", "their"}
STOP_WORDS = DETERMINERS | {"and", "or", "but", "of", "to", "in", "on", "at", "by", "for", "with", "from", "as"}


def default_leading_noise_terms() -> list[str]:
    return ["and", "again", "ah", "oh", "well", "why", "yes", "no", "indeed", "now", "then", "awake"]


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
    if lower and all(part in STOP_WORDS for part in lower.split()):
        flags.add("stop_word_only")
    if lower in generic_nouns:
        flags.add("generic_single_noun")
    if re.fullmatch(r"\d+[a-z]?", lower):
        flags.add("numeric_expression")
    if re.fullmatch(r"\d+(st|nd|rd|th)", lower):
        flags.add("ordinal_expression")
    if "£" in text or re.fullmatch(r"\d+s|s\.|d\.", lower):
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
    if re.search(r",\s*(who|and|i|he|she|which)\b", lower) or "—i" in lower:
        flags.add("suspected_sentence_fragment")
    if any(char in lower for char in [":", ";"]) or lower.count('"') % 2 == 1:
        flags.add("excessive_punctuation")
    if lower and all(char in string.punctuation for char in lower):
        flags.add("punctuation_only")
    return sorted(flags)

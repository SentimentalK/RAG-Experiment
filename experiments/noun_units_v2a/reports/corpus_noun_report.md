# Corpus Noun Report

This report is exploratory. Accepted/review/rejected and expandability labels are provisional rule-based labels, not validated query-expansion decisions.

## Corpus Summary
| Metric | Value |
| --- | --- |
| Stories processed | 12 |
| Chunks loaded for provenance | 909 |
| Sentences processed | 5966 |
| Tokens processed | 136294 |
| spaCy version | 3.7.5 |
| Model | en_core_web_sm 3.7.1 |
| Sections SHA-256 | 49fdcfeb58bd9d811aa574323966182515131256083a41ccaf001b7a045d0ff5 |
| Chunks SHA-256 | ad1ba3003ceb81589683d0b560f5ee934ceae671e5505674fbb21f696d7b2a04 |
| Config hash | 3787a8f238134a3fd691cda0e51f3e8e7b36f3f8c26d42a60a0b43d3c1e33e43 |

## Extraction Counts
| Metric | Count |
| --- | --- |
| raw occurrences | 47314 |
| normalized units | 13365 |
| accepted units | 10398 |
| review units | 2838 |
| rejected units | 129 |
| mapped occurrences | 47314 |
| unmapped occurrences | 0 |
| mapping success % | 100.0 |

Occurrences by type: `{"common_noun": 15008, "named_entity": 2086, "noun_phrase": 28830, "proper_noun": 1390}`

Units by type: `{"common_noun": 2789, "named_entity": 662, "noun_phrase": 9385, "proper_noun": 529}`

## Frequency Distribution
### Top Common Nouns
| Expression | Type | Frequency | Stories | Class |
| --- | --- | --- | --- | --- |
| man | common_noun | 324 | 12 | review |
| room | common_noun | 195 | 11 | accepted |
| hand | common_noun | 177 | 12 | accepted |
| door | common_noun | 149 | 12 | accepted |
| day | common_noun | 139 | 12 | accepted |
| time | common_noun | 137 | 12 | review |
| matter | common_noun | 136 | 12 | review |
| case | common_noun | 135 | 12 | review |
| house | common_noun | 128 | 12 | accepted |
| way | common_noun | 125 | 12 | review |
| face | common_noun | 123 | 12 | accepted |
| eyes | common_noun | 106 | 12 | accepted |
| morning | common_noun | 101 | 12 | accepted |
| night | common_noun | 98 | 12 | accepted |
| window | common_noun | 94 | 12 | accepted |
| friend | common_noun | 89 | 12 | accepted |
| years | common_noun | 88 | 12 | accepted |
| side | common_noun | 87 | 12 | accepted |
| words | common_noun | 81 | 12 | accepted |
| papers | common_noun | 77 | 12 | accepted |

### Top Proper Nouns
| Expression | Type | Frequency | Stories | Class |
| --- | --- | --- | --- | --- |
| Mr. Holmes | proper_noun | 75 | 11 | accepted |
| Mr. | proper_noun | 32 | 9 | rejected |
| Mr. Rucastle | proper_noun | 32 | 1 | accepted |
| sir | proper_noun | 30 | 9 | review |
| God | proper_noun | 29 | 9 | accepted |
| Doctor | proper_noun | 25 | 7 | accepted |
| Lord St. Simon | proper_noun | 25 | 1 | accepted |
| King | proper_noun | 23 | 5 | review |
| No | proper_noun | 18 | 8 | accepted |
| £ | proper_noun | 17 | 7 | rejected |
| Miss Hunter | proper_noun | 16 | 1 | accepted |
| City | proper_noun | 14 | 5 | accepted |
| Mr. Sherlock Holmes | proper_noun | 14 | 7 | accepted |
| Monday | proper_noun | 13 | 5 | accepted |
| Mr. Holder | proper_noun | 13 | 1 | accepted |
| Mr. Wilson | proper_noun | 13 | 1 | accepted |
| League | proper_noun | 12 | 1 | accepted |
| Mr. Hosmer Angel | proper_noun | 12 | 1 | accepted |
| Dr. Watson | proper_noun | 11 | 7 | accepted |
| Majesty | proper_noun | 11 | 1 | accepted |

### Top Named Entities
| Expression | Type | Frequency | Stories | Class |
| --- | --- | --- | --- | --- |
| Holmes | named_entity | 358 | 12 | accepted |
| Watson | named_entity | 76 | 11 | accepted |
| Sherlock Holmes | named_entity | 67 | 12 | accepted |
| Lestrade | named_entity | 38 | 2 | accepted |
| London | named_entity | 37 | 11 | accepted |
| McCarthy | named_entity | 31 | 1 | accepted |
| Rucastle | named_entity | 30 | 1 | accepted |
| St. Simon | named_entity | 27 | 1 | accepted |
| Baker Street | named_entity | 26 | 11 | accepted |
| England | named_entity | 20 | 9 | accepted |
| Arthur | named_entity | 19 | 1 | accepted |
| Frank | named_entity | 19 | 1 | accepted |
| Hunter | named_entity | 18 | 1 | accepted |
| Miss Stoner | named_entity | 16 | 1 | accepted |
| Sherlock Holmes | named_entity | 16 | 8 | accepted |
| Hosmer Angel | named_entity | 14 | 1 | accepted |
| Irene Adler | named_entity | 14 | 3 | accepted |
| Holder | named_entity | 13 | 1 | accepted |
| Wilson | named_entity | 13 | 1 | accepted |
| I. | named_entity | 12 | 7 | rejected |

### Top Noun Phrases
| Expression | Type | Frequency | Stories | Class |
| --- | --- | --- | --- | --- |
| I | noun_phrase | 3630 | 12 | rejected |
| he | noun_phrase | 1911 | 12 | rejected |
| it | noun_phrase | 1733 | 12 | rejected |
| you | noun_phrase | 1492 | 12 | rejected |
| which | noun_phrase | 764 | 12 | rejected |
| we | noun_phrase | 712 | 12 | rejected |
| she | noun_phrase | 575 | 11 | rejected |
| them | noun_phrase | 346 | 12 | rejected |
| that | noun_phrase | 321 | 12 | rejected |
| what | noun_phrase | 319 | 12 | rejected |
| who | noun_phrase | 268 | 12 | rejected |
| all | noun_phrase | 119 | 12 | rejected |
| this | noun_phrase | 117 | 12 | rejected |
| nothing | noun_phrase | 106 | 12 | rejected |
| the door | noun_phrase | 87 | 12 | accepted |
| the matter | noun_phrase | 81 | 12 | review |
| a man | noun_phrase | 75 | 12 | review |
| himself | noun_phrase | 73 | 12 | rejected |
| myself | noun_phrase | 72 | 12 | rejected |
| his hand | noun_phrase | 68 | 12 | review |

Thresholds: `{"frequency_gte_10": 567, "frequency_gte_2": 3858, "frequency_gte_3": 2354, "frequency_gte_5": 1332}`

## Phrase-Length Distribution
`{"1": 4437, "2": 4923, "3": 3025, "4": 766, "5": 153, "6-8": 60, ">8": 1}`

## Overlap and Duplication
Same-span duplicate extractor hits are merged into one occurrence with multiple `extraction_sources`; nested spans remain separate units.
| Family | Expression | Type | Class |
| --- | --- | --- | --- |
| holmes | Holmes | named_entity | accepted |
| holmes | Holmes | named_entity | accepted |
| holmes | Holmes | noun_phrase | accepted |
| holmes | HOLMES,—I | named_entity | accepted |
| holmes | Mr. Holmes | noun_phrase | accepted |
| holmes | Mr. Holmes | proper_noun | accepted |
| holmes | , Mr. Holmes | noun_phrase | accepted |
| holmes | Again Holmes | named_entity | accepted |
| pawnbroker | pawnbroker | common_noun | accepted |
| pawnbroker | the pawnbroker | noun_phrase | accepted |
| pawnbroker | the good pawnbroker | noun_phrase | accepted |
| pawnbroker | a pawnbroker's business | noun_phrase | review |
| pawnbroker | not over-bright pawnbroker | noun_phrase | accepted |
| pawnbroker | a small pawnbroker's business | noun_phrase | review |
| pawnbroker | this smooth-faced pawnbroker's assistant | noun_phrase | review |
| woman | woman | common_noun | review |
| woman | a woman | noun_phrase | review |
| woman | one woman | noun_phrase | review |
| woman | the woman | noun_phrase | review |
| woman | womanhood | common_noun | accepted |
| woman | Some woman | noun_phrase | review |
| woman | that woman | noun_phrase | review |
| woman | this woman | noun_phrase | review |
| adler | née ADLER | proper_noun | accepted |
| adler | Miss Adler | named_entity | accepted |
| adler | Irene Adler | named_entity | accepted |
| adler | And Irene Adler | noun_phrase | accepted |
| adler | Miss Irene Adler | proper_noun | accepted |
| adler | the late Irene Adler | noun_phrase | accepted |
| adler | the Irene Adler papers | noun_phrase | accepted |

## Estimated Human-Review Workload
| Slice | Units |
| --- | --- |
| accepted + review units | 13236 |
| named entities only | 662 |
| proper nouns only | 529 |
| multiword noun phrases only | 8425 |
| frequency >= 2 | 3858 |
| frequency >= 3 | 2354 |
| possibly_expandable only | 5583 |

The vocabulary is likely practical for staged human review if the first pass focuses on named/proper units, multiword phrases, and frequency >= 2 candidates before reviewing all single generic nouns.

## Quality Samples
| Surface | Type | Frequency | Story IDs | Class | Reasons |
| --- | --- | --- | --- | --- | --- |
| I | noun_phrase | 3630 | s01-a-scandal-in-bohemia, s02-the-red-headed-league, s03-a-case-of-identity | rejected | single_character_fragment |
| he | noun_phrase | 1911 | s01-a-scandal-in-bohemia, s02-the-red-headed-league, s03-a-case-of-identity | rejected | pronoun |
| it | noun_phrase | 1733 | s01-a-scandal-in-bohemia, s02-the-red-headed-league, s03-a-case-of-identity | rejected | pronoun |
| you | noun_phrase | 1492 | s01-a-scandal-in-bohemia, s02-the-red-headed-league, s03-a-case-of-identity | rejected | pronoun |
| which | noun_phrase | 764 | s01-a-scandal-in-bohemia, s02-the-red-headed-league, s03-a-case-of-identity | rejected | without_noun_content |
| we | noun_phrase | 712 | s01-a-scandal-in-bohemia, s02-the-red-headed-league, s03-a-case-of-identity | rejected | pronoun |
| she | noun_phrase | 575 | s01-a-scandal-in-bohemia, s03-a-case-of-identity, s04-the-boscombe-valley-mystery | rejected | pronoun |
| Holmes | named_entity | 358 | s01-a-scandal-in-bohemia, s02-the-red-headed-league, s03-a-case-of-identity | accepted | well_formed_name_or_entity |
| them | noun_phrase | 346 | s01-a-scandal-in-bohemia, s02-the-red-headed-league, s03-a-case-of-identity | rejected | pronoun |
| man | common_noun | 324 | s01-a-scandal-in-bohemia, s02-the-red-headed-league, s03-a-case-of-identity | review | generic_single_noun |
| that | noun_phrase | 321 | s01-a-scandal-in-bohemia, s02-the-red-headed-league, s03-a-case-of-identity | rejected | determiner |
| what | noun_phrase | 319 | s01-a-scandal-in-bohemia, s02-the-red-headed-league, s03-a-case-of-identity | rejected | without_noun_content |
| who | noun_phrase | 268 | s01-a-scandal-in-bohemia, s02-the-red-headed-league, s03-a-case-of-identity | rejected | without_noun_content |
| room | common_noun | 195 | s01-a-scandal-in-bohemia, s02-the-red-headed-league, s04-the-boscombe-valley-mystery | accepted | concrete_non_generic_common_noun |
| hand | common_noun | 177 | s01-a-scandal-in-bohemia, s02-the-red-headed-league, s03-a-case-of-identity | accepted | concrete_non_generic_common_noun |
| door | common_noun | 149 | s01-a-scandal-in-bohemia, s02-the-red-headed-league, s03-a-case-of-identity | accepted | concrete_non_generic_common_noun |
| day | common_noun | 139 | s01-a-scandal-in-bohemia, s02-the-red-headed-league, s03-a-case-of-identity | accepted | concrete_non_generic_common_noun |
| time | common_noun | 137 | s01-a-scandal-in-bohemia, s02-the-red-headed-league, s03-a-case-of-identity | review | generic_single_noun |
| matter | common_noun | 136 | s01-a-scandal-in-bohemia, s02-the-red-headed-league, s03-a-case-of-identity | review | generic_single_noun |
| case | common_noun | 135 | s01-a-scandal-in-bohemia, s02-the-red-headed-league, s03-a-case-of-identity | review | generic_single_noun |
| house | common_noun | 128 | s01-a-scandal-in-bohemia, s02-the-red-headed-league, s03-a-case-of-identity | accepted | concrete_non_generic_common_noun |
| way | common_noun | 125 | s01-a-scandal-in-bohemia, s02-the-red-headed-league, s03-a-case-of-identity | review | generic_single_noun |
| face | common_noun | 123 | s01-a-scandal-in-bohemia, s02-the-red-headed-league, s03-a-case-of-identity | accepted | concrete_non_generic_common_noun |
| all | noun_phrase | 119 | s01-a-scandal-in-bohemia, s02-the-red-headed-league, s03-a-case-of-identity | rejected | without_noun_content |
| this | noun_phrase | 117 | s01-a-scandal-in-bohemia, s02-the-red-headed-league, s03-a-case-of-identity | rejected | determiner |
| eyes | common_noun | 106 | s01-a-scandal-in-bohemia, s02-the-red-headed-league, s03-a-case-of-identity | accepted | concrete_non_generic_common_noun |
| nothing | noun_phrase | 106 | s01-a-scandal-in-bohemia, s02-the-red-headed-league, s03-a-case-of-identity | rejected | without_noun_content |
| morning | common_noun | 101 | s01-a-scandal-in-bohemia, s02-the-red-headed-league, s03-a-case-of-identity | accepted | concrete_non_generic_common_noun |
| night | common_noun | 98 | s01-a-scandal-in-bohemia, s02-the-red-headed-league, s03-a-case-of-identity | accepted | concrete_non_generic_common_noun |
| window | common_noun | 94 | s01-a-scandal-in-bohemia, s02-the-red-headed-league, s03-a-case-of-identity | accepted | concrete_non_generic_common_noun |
| friend | common_noun | 89 | s01-a-scandal-in-bohemia, s02-the-red-headed-league, s03-a-case-of-identity | accepted | concrete_non_generic_common_noun |
| years | common_noun | 88 | s01-a-scandal-in-bohemia, s02-the-red-headed-league, s03-a-case-of-identity | accepted | concrete_non_generic_common_noun |
| side | common_noun | 87 | s01-a-scandal-in-bohemia, s02-the-red-headed-league, s03-a-case-of-identity | accepted | concrete_non_generic_common_noun |
| the door | noun_phrase | 87 | s01-a-scandal-in-bohemia, s02-the-red-headed-league, s03-a-case-of-identity | accepted | specific_multiword_noun_phrase |
| the matter | noun_phrase | 81 | s01-a-scandal-in-bohemia, s02-the-red-headed-league, s03-a-case-of-identity | review | generic_head_with_modifiers |
| words | common_noun | 81 | s01-a-scandal-in-bohemia, s02-the-red-headed-league, s03-a-case-of-identity | accepted | concrete_non_generic_common_noun |
| papers | common_noun | 77 | s01-a-scandal-in-bohemia, s02-the-red-headed-league, s03-a-case-of-identity | accepted | concrete_non_generic_common_noun |
| lady | common_noun | 76 | s01-a-scandal-in-bohemia, s03-a-case-of-identity, s04-the-boscombe-valley-mystery | accepted | concrete_non_generic_common_noun |
| Watson | named_entity | 76 | s01-a-scandal-in-bohemia, s02-the-red-headed-league, s03-a-case-of-identity | accepted | well_formed_name_or_entity |
| a man | noun_phrase | 75 | s01-a-scandal-in-bohemia, s02-the-red-headed-league, s03-a-case-of-identity | review | generic_head_with_modifiers |
| head | common_noun | 75 | s01-a-scandal-in-bohemia, s02-the-red-headed-league, s03-a-case-of-identity | accepted | concrete_non_generic_common_noun |
| Mr. Holmes | proper_noun | 75 | s01-a-scandal-in-bohemia, s02-the-red-headed-league, s03-a-case-of-identity | accepted | well_formed_name_or_entity |
| one | common_noun | 75 | s01-a-scandal-in-bohemia, s02-the-red-headed-league, s03-a-case-of-identity | review | generic_single_noun |
| himself | noun_phrase | 73 | s01-a-scandal-in-bohemia, s02-the-red-headed-league, s03-a-case-of-identity | rejected | pronoun |
| myself | noun_phrase | 72 | s01-a-scandal-in-bohemia, s02-the-red-headed-league, s03-a-case-of-identity | rejected | pronoun |
| woman | common_noun | 72 | s01-a-scandal-in-bohemia, s03-a-case-of-identity, s04-the-boscombe-valley-mystery | review | generic_single_noun |
| father | common_noun | 71 | s03-a-case-of-identity, s04-the-boscombe-valley-mystery, s05-the-five-orange-pips | accepted | concrete_non_generic_common_noun |
| his hand | noun_phrase | 68 | s01-a-scandal-in-bohemia, s02-the-red-headed-league, s03-a-case-of-identity | review | possessive_phrase |
| thing | common_noun | 68 | s01-a-scandal-in-bohemia, s02-the-red-headed-league, s03-a-case-of-identity | review | generic_single_noun |
| Sherlock Holmes | named_entity | 67 | s01-a-scandal-in-bohemia, s02-the-red-headed-league, s03-a-case-of-identity | accepted | well_formed_name_or_entity |

## Potential Extraction Quality Issues
| Issue | Item | Details |
| --- | --- | --- |
| possible_entity_conflict | ah, watson | {"entity_types": ["ORG", "WORK_OF_ART"], "issue_type": "possible_entity_conflict", "text": "ah, watson"} |
| possible_entity_conflict | aloysius doran | {"entity_types": ["ORG", "PERSON"], "issue_type": "possible_entity_conflict", "text": "aloysius doran"} |
| possible_entity_conflict | assizes | {"entity_types": ["ORG", "PRODUCT"], "issue_type": "possible_entity_conflict", "text": "assizes"} |
| possible_entity_conflict | ballarat | {"entity_types": ["GPE", "LOC"], "issue_type": "possible_entity_conflict", "text": "ballarat"} |
| possible_entity_conflict | bohemia | {"entity_types": ["GPE", "ORG", "PERSON"], "issue_type": "possible_entity_conflict", "text": "bohemia"} |
| possible_entity_conflict | boscombe pool | {"entity_types": ["FAC", "ORG"], "issue_type": "possible_entity_conflict", "text": "boscombe pool"} |
| possible_entity_conflict | boscombe valley | {"entity_types": ["FAC", "LOC"], "issue_type": "possible_entity_conflict", "text": "boscombe valley"} |
| possible_entity_conflict | bradstreet | {"entity_types": ["ORG", "PERSON"], "issue_type": "possible_entity_conflict", "text": "bradstreet"} |
| possible_entity_conflict | breckinridge | {"entity_types": ["ORG", "PERSON", "WORK_OF_ART"], "issue_type": "possible_entity_conflict", "text": "breckinridge"} |
| possible_entity_conflict | briony lodge | {"entity_types": ["FAC", "ORG", "PERSON"], "issue_type": "possible_entity_conflict", "text": "briony lodge"} |
| possible_entity_conflict | bristol | {"entity_types": ["GPE", "ORG"], "issue_type": "possible_entity_conflict", "text": "bristol"} |
| possible_entity_conflict | countess | {"entity_types": ["GPE", "PERSON"], "issue_type": "possible_entity_conflict", "text": "countess"} |
| possible_entity_conflict | dundee | {"entity_types": ["FAC", "GPE"], "issue_type": "possible_entity_conflict", "text": "dundee"} |
| possible_entity_conflict | ezekiah hopkins | {"entity_types": ["FAC", "ORG"], "issue_type": "possible_entity_conflict", "text": "ezekiah hopkins"} |
| possible_entity_conflict | fairbank | {"entity_types": ["ORG", "PERSON"], "issue_type": "possible_entity_conflict", "text": "fairbank"} |
| possible_entity_conflict | farintosh | {"entity_types": ["PERSON", "PRODUCT"], "issue_type": "possible_entity_conflict", "text": "farintosh"} |
| possible_entity_conflict | ferguson | {"entity_types": ["ORG", "PERSON"], "issue_type": "possible_entity_conflict", "text": "ferguson"} |
| possible_entity_conflict | fordham | {"entity_types": ["ORG", "PERSON"], "issue_type": "possible_entity_conflict", "text": "fordham"} |
| possible_entity_conflict | frisco | {"entity_types": ["ORG", "PRODUCT"], "issue_type": "possible_entity_conflict", "text": "frisco"} |
| possible_entity_conflict | gladstone | {"entity_types": ["ORG", "PERSON"], "issue_type": "possible_entity_conflict", "text": "gladstone"} |
| possible_entity_conflict | godfrey norton | {"entity_types": ["ORG", "PERSON"], "issue_type": "possible_entity_conflict", "text": "godfrey norton"} |
| possible_entity_conflict | gordon square | {"entity_types": ["FAC", "PERSON"], "issue_type": "possible_entity_conflict", "text": "gordon square"} |
| possible_entity_conflict | harrow | {"entity_types": ["GPE", "PERSON", "WORK_OF_ART"], "issue_type": "possible_entity_conflict", "text": "harrow"} |
| possible_entity_conflict | hatherley | {"entity_types": ["GPE", "ORG", "PERSON", "WORK_OF_ART"], "issue_type": "possible_entity_conflict", "text": "hatherley"} |
| possible_entity_conflict | holder | {"entity_types": ["ORG", "PERSON"], "issue_type": "possible_entity_conflict", "text": "holder"} |
| possible_entity_conflict | holmes | {"entity_types": ["GPE", "PERSON"], "issue_type": "possible_entity_conflict", "text": "holmes"} |
| possible_entity_conflict | horner | {"entity_types": ["GPE", "ORG", "PERSON"], "issue_type": "possible_entity_conflict", "text": "horner"} |
| possible_entity_conflict | hudson | {"entity_types": ["ORG", "PERSON"], "issue_type": "possible_entity_conflict", "text": "hudson"} |
| possible_entity_conflict | hugh boone | {"entity_types": ["ORG", "PERSON"], "issue_type": "possible_entity_conflict", "text": "hugh boone"} |
| possible_entity_conflict | i. | {"entity_types": ["ORG", "PERSON"], "issue_type": "possible_entity_conflict", "text": "i."} |
| possible_entity_conflict | inspector bradstreet | {"entity_types": ["PERSON", "WORK_OF_ART"], "issue_type": "possible_entity_conflict", "text": "inspector bradstreet"} |
| possible_entity_conflict | kilburn | {"entity_types": ["GPE", "PERSON"], "issue_type": "possible_entity_conflict", "text": "kilburn"} |
| possible_entity_conflict | lascar | {"entity_types": ["PRODUCT", "WORK_OF_ART"], "issue_type": "possible_entity_conflict", "text": "lascar"} |
| possible_entity_conflict | mccarthys | {"entity_types": ["ORG", "PERSON"], "issue_type": "possible_entity_conflict", "text": "mccarthys"} |
| possible_entity_conflict | morcar | {"entity_types": ["ORG", "WORK_OF_ART"], "issue_type": "possible_entity_conflict", "text": "morcar"} |
| possible_entity_conflict | moulton | {"entity_types": ["ORG", "PERSON"], "issue_type": "possible_entity_conflict", "text": "moulton"} |
| possible_entity_conflict | neville | {"entity_types": ["GPE", "ORG"], "issue_type": "possible_entity_conflict", "text": "neville"} |
| possible_entity_conflict | neville st. clair | {"entity_types": ["ORG", "PERSON"], "issue_type": "possible_entity_conflict", "text": "neville st. clair"} |
| possible_entity_conflict | openshaw | {"entity_types": ["ORG", "PERSON"], "issue_type": "possible_entity_conflict", "text": "openshaw"} |
| possible_entity_conflict | paddington | {"entity_types": ["GPE", "ORG"], "issue_type": "possible_entity_conflict", "text": "paddington"} |
| possible_entity_conflict | pondicherry | {"entity_types": ["EVENT", "LOC", "PERSON"], "issue_type": "possible_entity_conflict", "text": "pondicherry"} |
| possible_entity_conflict | rucastle | {"entity_types": ["GPE", "ORG", "PERSON"], "issue_type": "possible_entity_conflict", "text": "rucastle"} |
| possible_entity_conflict | rucastles | {"entity_types": ["LOC", "PERSON"], "issue_type": "possible_entity_conflict", "text": "rucastles"} |
| possible_entity_conflict | saxe-coburg square | {"entity_types": ["ORG", "PRODUCT"], "issue_type": "possible_entity_conflict", "text": "saxe-coburg square"} |
| possible_entity_conflict | scarlet | {"entity_types": ["GPE", "ORG"], "issue_type": "possible_entity_conflict", "text": "scarlet"} |
| possible_entity_conflict | sherlock holmes | {"entity_types": ["LOC", "ORG", "PERSON", "PRODUCT", "WORK_OF_ART"], "issue_type": "possible_entity_conflict", "text": "sherlock holmes"} |
| possible_entity_conflict | st. simon | {"entity_types": ["GPE", "PERSON"], "issue_type": "possible_entity_conflict", "text": "st. simon"} |
| possible_entity_conflict | stoke moran | {"entity_types": ["LOC", "PERSON", "PRODUCT", "WORK_OF_ART"], "issue_type": "possible_entity_conflict", "text": "stoke moran"} |
| possible_entity_conflict | the copper beeches | {"entity_types": ["FAC", "ORG"], "issue_type": "possible_entity_conflict", "text": "the copper beeches"} |
| possible_entity_conflict | the duke of balmoral | {"entity_types": ["EVENT", "GPE"], "issue_type": "possible_entity_conflict", "text": "the duke of balmoral"} |

## Baseline-Question Noun Coverage
| Question | Question Noun | Type | In Corpus | Corpus Match |
| --- | --- | --- | --- | --- |
| q001 | Sherlock Holmes | named_entity | yes | Sherlock Holmes |
| q001 | the woman | noun_phrase | yes | the woman |
| q001 | Who | noun_phrase | yes | who |
| q001 | whom | noun_phrase | yes | whom |
| q001 | woman | common_noun | yes | woman |
| q002 | Encyclopaedia Britannica | proper_noun | no |  |
| q002 | Jabez Wilson | named_entity | yes | Jabez Wilson |
| q002 | the Encyclopaedia Britannica | named_entity | no |  |
| q003 | he | noun_phrase | yes | he |
| q003 | Hosmer Angel | named_entity | yes | Hosmer Angel |
| q003 | Who | noun_phrase | yes | who |
| q004 | orange | common_noun | yes | orange |
| q004 | pips | common_noun | yes | pips |
| q004 | the five orange pips | noun_phrase | no |  |
| q004 | they | noun_phrase | yes | them |
| q004 | What | noun_phrase | yes | what |
| q005 | his life | noun_phrase | yes | his life |
| q005 | Hugh Boone | named_entity | yes | Hugh Boone |
| q005 | life | common_noun | yes | life |
| q005 | Neville St. Clair | named_entity | yes | Neville St. Clair |
| q005 | part | noun_phrase | yes | part |
| q005 | the beggar Hugh Boone | noun_phrase | no |  |
| q006 | a Christmas goose | noun_phrase | no |  |
| q006 | carbuncle | common_noun | yes | carbuncle |
| q006 | Christmas | proper_noun | yes | Christmas |
| q006 | goose | common_noun | yes | goose |
| q006 | the stolen blue carbuncle | noun_phrase | no |  |
| q007 | band | common_noun | yes | band |
| q007 | death | common_noun | yes | death |
| q007 | Julia Stoner | proper_noun | no |  |
| q007 | Julia Stoner's | named_entity | no |  |
| q007 | Julia Stoner's death | noun_phrase | no |  |
| q007 | that | noun_phrase | yes | that |
| q007 | the "speckled band | noun_phrase | no |  |
| q007 | What | noun_phrase | yes | what |
| q008 | cases | common_noun | yes | case |
| q008 | each | noun_phrase | yes | each |
| q008 | employment | common_noun | no |  |
| q008 | offers | common_noun | yes | offer |
| q008 | purpose | common_noun | yes | purpose |
| q008 | suspiciously generous employment offers | noun_phrase | no |  |
| q008 | what hidden purpose | noun_phrase | no |  |
| q008 | Which two cases | noun_phrase | no |  |

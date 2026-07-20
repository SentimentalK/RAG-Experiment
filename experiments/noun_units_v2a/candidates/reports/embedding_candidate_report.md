# Embedding Candidate Report

This candidate pool is lexical-only. Baseline question matches are diagnostic metadata only and do not affect tiering.

## Input Summary
| Metric | Value |
| --- | --- |
| V2A normalized units | 13365 |
| Source hashes | {"accepted_units": "fba75d08a425dfce0b45421a01471d10d911a43d10814ab45fac5187096b2384", "generic_nouns": "358256a758305e79aa03407aaeedfcc50edecbb8d8848d2f6a32689e130de079", "manifest": "0c67d17cc650af81c96ea310dea4be6cb64866fb0957b715df3d4ba63f5d4691", "normalized_units": "e05ed6213783c753b75592b38784f9190e071b15d0f180a2ad1a2bffd8ce8054", "review_units": "48eca1a82bf65d53d8f0ca790f55bf1c2062d41b5b3230b14e33d58e74c9c708", "statistics": "4e5b5ab8456c5b0ca0e636636aaf23960612423ffd0f724e71d1a3cd4b21b380"} |
| Candidate configuration hash | 7ed22c978dbfa55e15c6134a2f82c7e1da1844053566b97646acda8a2bf731de |

## Consolidation Summary
| Metric | Count |
| --- | --- |
| Units before consolidation | 13365 |
| Candidates after consolidation | 12517 |
| Lexical duplicate groups | 736 |
| Cross-type duplicate groups | 673 |
| Conflicting entity-label groups | 61 |

| Candidate | Comparison | Source Units | Unit Types | Entity Types |
| --- | --- | --- | --- | --- |
| Sherlock Holmes | sherlock holmes | 6 | named_entity, noun_phrase | LOC, ORG, PERSON, PRODUCT, WORK_OF_ART |
| Stoke Moran | stoke moran | 6 | named_entity, noun_phrase, proper_noun | LOC, PERSON, PRODUCT, WORK_OF_ART |
|  |  | 5 | common_noun, noun_phrase, proper_noun |  |
| Ballarat | ballarat | 4 | named_entity, noun_phrase, proper_noun | GPE, LOC |
| Bohemia | bohemia | 4 | named_entity, proper_noun | GPE, ORG, PERSON |
| Bradstreet | bradstreet | 4 | named_entity, noun_phrase, proper_noun | ORG, PERSON |
| Briony Lodge | briony lodge | 4 | named_entity, proper_noun | FAC, ORG, PERSON |
| Clay | clay | 4 | common_noun, named_entity, noun_phrase, proper_noun | PRODUCT |
| Danger | danger | 4 | common_noun, noun_phrase, proper_noun |  |
| Data | data | 4 | common_noun, noun_phrase, proper_noun |  |
| Fire | fire | 4 | common_noun, noun_phrase, proper_noun |  |
| fuller's | fuller's | 4 | common_noun, named_entity, noun_phrase, proper_noun | GPE |
| Hatherley | hatherley | 4 | named_entity | GPE, ORG, PERSON, WORK_OF_ART |
| Hum | hum | 4 | named_entity, noun_phrase, proper_noun | GPE |
| I. | i. | 4 | named_entity, noun_phrase, proper_noun | ORG, PERSON |
| Inspector Bradstreet | inspector bradstreet | 4 | named_entity, noun_phrase, proper_noun | PERSON, WORK_OF_ART |
| No | no | 4 | common_noun, noun_phrase, proper_noun |  |
| Pondicherry | pondicherry | 4 | named_entity, proper_noun | EVENT, LOC, PERSON |
| The Copper Beeches | the copper beeches | 4 | named_entity, noun_phrase | FAC, ORG |
| Ah, Watson | ah, watson | 3 | named_entity, noun_phrase | ORG, WORK_OF_ART |

## Boundary Cleanup
| Candidate | Tier | Quality Flags | Normalization Actions |
| --- | --- | --- | --- |
|  | excluded | empty, leading_punctuation_removed | surrounding_punctuation_removed |
| . | excluded | punctuation_only |  |
| 10s | excluded | currency_expression, numeric_expression |  |
| 12s | excluded | currency_expression, numeric_expression |  |
| 12th | excluded | ordinal_expression |  |
| 19th | excluded | ordinal_expression |  |
| 1s | excluded | currency_expression, numeric_expression |  |
| 221B | excluded | numeric_expression | case_folded |
| 22nd | excluded | ordinal_expression |  |
| 26s | excluded | currency_expression, numeric_expression |  |
| 2nd | excluded | ordinal_expression |  |
| 2s | excluded | currency_expression, numeric_expression |  |
| 3rd | excluded | ordinal_expression |  |
| 4d | excluded | numeric_expression |  |
| 4th | excluded | ordinal_expression |  |
| 6d | excluded | numeric_expression |  |
| 7s | excluded | currency_expression, numeric_expression |  |
| 8s | excluded | currency_expression, numeric_expression |  |
| A | excluded | determiner, stop_word_only | case_folded |
| A. | excluded | isolated_abbreviation | case_folded |
| And this | excluded | leading_discourse_marker, stop_word_only | case_folded |
| Anything | excluded | generic_single_noun | case_folded |
| B. | excluded | isolated_abbreviation | case_folded |
| by | excluded | stop_word_only |  |
| C. | excluded | isolated_abbreviation | case_folded |
| case | excluded | generic_single_noun |  |
| fact | excluded | generic_single_noun |  |
| fifty £ 1000 notes | excluded | currency_expression |  |
| H. | excluded | isolated_abbreviation | case_folded |
| He | excluded | pronoun | case_folded |

`{"currency_expression": 11, "determiner": 11, "empty": 1, "excessive_punctuation": 12, "generic_single_noun": 21, "isolated_abbreviation": 7, "leading_discourse_marker": 190, "leading_punctuation_removed": 24, "numeric_expression": 10, "ordinal_expression": 6, "pronoun": 15, "punctuation_only": 1, "stop_word_only": 13}`

## Tier Distribution
| Tier | Count |
| --- | --- |
| excluded | 76 |
| review | 8753 |
| tier_a | 2105 |
| tier_b | 1583 |

By unit type: `{"common_noun": 2781, "named_entity": 587, "noun_phrase": 9343, "proper_noun": 529}`

By frequency: `{"frequency_gte_10": 548, "frequency_gte_2": 3686, "frequency_gte_3": 2296, "frequency_gte_5": 1309}`

By token length: `{"0": 1, "1": 3732, "2": 4823, "3": 2992, "4": 757, "5": 152, "6-8": 59, ">8": 1}`

By story count: `{"1": 9628, "2-3": 1844, "4-6": 626, "7+": 419}`

## Candidate Examples
| Candidate | Tier | Frequency | Stories | Reasons |
| --- | --- | --- | --- | --- |
| I | excluded | 3630 | 12 | pronoun |
| He | excluded | 1911 | 12 | pronoun |
| It | excluded | 1733 | 12 | pronoun |
| You | excluded | 1492 | 12 | pronoun |
| We | excluded | 712 | 12 | pronoun |
| She | excluded | 575 | 11 | pronoun |
| them | excluded | 346 | 12 | pronoun |
| man | excluded | 324 | 12 | generic_single_noun |
| That | excluded | 321 | 12 | determiner, stop_word_only |
| time | excluded | 137 | 12 | generic_single_noun |
| matter | excluded | 136 | 12 | generic_single_noun |
| case | excluded | 135 | 12 | generic_single_noun |
| way | excluded | 125 | 12 | generic_single_noun |
| This | excluded | 117 | 12 | determiner, stop_word_only |
| Nothing | excluded | 106 | 12 | generic_single_noun |
| One | excluded | 75 | 12 | generic_single_noun |
| himself | excluded | 73 | 12 | pronoun |
| myself | excluded | 72 | 12 | pronoun |
| woman | excluded | 72 | 10 | generic_single_noun |
| thing | excluded | 68 | 12 | generic_single_noun |
| Something | excluded | 65 | 12 | generic_single_noun |
| point | excluded | 60 | 12 | generic_single_noun |
| Anything | excluded | 48 | 12 | generic_single_noun |
| place | excluded | 45 | 11 | generic_single_noun |
| part | excluded | 29 | 11 | generic_single_noun |
| sort | excluded | 23 | 8 | generic_single_noun |
| Those | excluded | 21 | 9 | determiner, stop_word_only |
| person | excluded | 20 | 12 | generic_single_noun |
| ourselves | excluded | 19 | 11 | pronoun |
| itself | excluded | 18 | 9 | pronoun |
| No | excluded | 18 | 11 | isolated_abbreviation |
| These | excluded | 18 | 10 | determiner, stop_word_only |
| Men | excluded | 17 | 9 | generic_single_noun |
| £ | excluded | 17 | 7 | currency_expression |
| People | excluded | 16 | 9 | generic_single_noun |
| fact | excluded | 12 | 8 | generic_single_noun |
| I. | excluded | 12 | 9 | isolated_abbreviation, pronoun |
|  | excluded | 11 | 9 | empty |
| his | excluded | 11 | 7 | determiner, stop_word_only |
| herself | excluded | 10 | 5 | pronoun |
| my | excluded | 7 | 4 | determiner, stop_word_only |
| Women | excluded | 7 | 4 | generic_single_noun |
| kind | excluded | 6 | 5 | generic_single_noun |
| . | excluded | 4 | 3 | punctuation_only |
| themselves | excluded | 4 | 4 | pronoun |
| 22nd | excluded | 3 | 1 | ordinal_expression |
| A | excluded | 3 | 2 | determiner, stop_word_only |
| C. | excluded | 3 | 2 | isolated_abbreviation |
| her | excluded | 3 | 3 | determiner, pronoun, stop_word_only |
| our | excluded | 3 | 2 | determiner, stop_word_only |

## Baseline Coverage
| Question | Question Unit | Comparison | Match Type | Coverage | Candidate | Tier |
| --- | --- | --- | --- | --- | --- | --- |
| q001 | Sherlock Holmes | sherlock holmes | exact_surface_match | strong | Mr. Sherlock Holmes | tier_a |
| q001 | the woman | the woman | exact_surface_match | strong | The woman | tier_a |
| q001 | Who | who | exact_surface_match | strong | Who | tier_b |
| q001 | whom | whom | exact_surface_match | strong | Whom | tier_b |
| q001 | woman | woman | exact_surface_match | strong | woman | excluded |
| q002 | Encyclopaedia Britannica | encyclopaedia britannica | comparison_form_match | strong | Encyclopaedia Britannica | tier_a |
| q002 | Jabez Wilson | jabez wilson | exact_surface_match | strong | Jabez Wilson | tier_a |
| q002 | the Encyclopaedia Britannica | the encyclopaedia britannica | comparison_form_match | strong | the Encyclopaedia Britannica | tier_a |
| q003 | he | he | exact_surface_match | strong | He | excluded |
| q003 | Hosmer Angel | hosmer angel | exact_surface_match | strong | Hosmer Angel | tier_a |
| q003 | Who | who | exact_surface_match | strong | Who | tier_b |
| q004 | orange | orange | exact_surface_match | strong | orange | tier_b |
| q004 | pips | pips | exact_surface_match | strong | pips | tier_b |
| q004 | the five orange pips | the five orange pips | longest_contained_candidate | partial | the orange pips | review |
| q004 | they | they | exact_surface_match | strong | them | excluded |
| q004 | What | what | exact_surface_match | strong | What | tier_b |
| q005 | his life | his life | exact_surface_match | strong | his life | review |
| q005 | Hugh Boone | hugh boone | exact_surface_match | strong | Hugh Boone | tier_a |
| q005 | life | life | exact_surface_match | strong | life | tier_b |
| q005 | Neville St. Clair | neville st. clair | exact_surface_match | strong | Mr. Neville St. Clair | tier_a |
| q005 | part | part | exact_surface_match | strong | part | excluded |
| q005 | the beggar Hugh Boone | the beggar hugh boone | longest_contained_candidate | partial | Hugh Boone | tier_a |
| q006 | a Christmas goose | a christmas goose | longest_contained_candidate | partial | Christmas | tier_a |
| q006 | carbuncle | carbuncle | exact_surface_match | strong | carbuncle | tier_b |
| q006 | Christmas | christmas | exact_surface_match | strong | Christmas | tier_a |
| q006 | goose | goose | exact_surface_match | strong | goose | tier_b |
| q006 | the stolen blue carbuncle | the stolen blue carbuncle | longest_contained_candidate | partial | the blue carbuncle | tier_a |
| q007 | band | band | exact_surface_match | strong | band | tier_b |
| q007 | death | death | exact_surface_match | strong | Death | review |
| q007 | Julia Stoner | julia stoner | longest_contained_candidate | partial | Julia | tier_a |
| q007 | Julia Stoner's | julia stoner's | longest_contained_candidate | partial | Julia | tier_a |
| q007 | Julia Stoner's death | julia stoner's death | longest_contained_candidate | partial | Death | review |
| q007 | that | that | exact_surface_match | strong | That | excluded |
| q007 | the "speckled band | the speckled band | comparison_form_match | strong | The speckled band | tier_a |
| q007 | What | what | exact_surface_match | strong | What | tier_b |
| q008 | cases | cases | exact_surface_match | strong | case | excluded |
| q008 | each | each | exact_surface_match | strong | each | tier_b |
| q008 | employment | employment | exact_surface_match | strong | employment | review |
| q008 | offers | offers | exact_surface_match | strong | offer | tier_b |
| q008 | purpose | purpose | exact_surface_match | strong | purpose | tier_b |
| q008 | suspiciously generous employment offers | suspiciously generous employment offers | longest_contained_candidate | partial | employment | review |
| q008 | what hidden purpose | what hidden purpose | longest_contained_candidate | partial | what purpose | tier_a |
| q008 | Which two cases | which two cases | longest_contained_candidate | partial | Which | tier_b |

`{"no_coverage_count": 0, "partial_coverage_count": 10, "strong_coverage_count": 33}`

## Estimated Next-Stage Workload
| Workload | Count |
| --- | --- |
| Tier A embedding computations | 2105 |
| Tier A Top-10 pairs for inspection | 21050 |
| Tier A + Tier B embedding computations | 3688 |
| Tier A + Tier B Top-10 pairs for inspection | 36880 |

Embedding computation workload is the number of candidate vectors. Human pair-review workload is the candidate count multiplied by the nearest-neighbour depth.

## Recommendation
Proceed with Tier A embedding experiment
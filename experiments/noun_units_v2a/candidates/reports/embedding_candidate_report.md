# Embedding Candidate Report

This candidate pool is lexical-only. Baseline question matches are diagnostic metadata only and do not affect tiering.

## Input Summary
| Metric | Value |
| --- | --- |
| V2A normalized units | 13365 |
| Source hashes | {"accepted_units": "fba75d08a425dfce0b45421a01471d10d911a43d10814ab45fac5187096b2384", "generic_nouns": "358256a758305e79aa03407aaeedfcc50edecbb8d8848d2f6a32689e130de079", "manifest": "0c67d17cc650af81c96ea310dea4be6cb64866fb0957b715df3d4ba63f5d4691", "normalized_units": "e05ed6213783c753b75592b38784f9190e071b15d0f180a2ad1a2bffd8ce8054", "review_units": "48eca1a82bf65d53d8f0ca790f55bf1c2062d41b5b3230b14e33d58e74c9c708", "statistics": "4e5b5ab8456c5b0ca0e636636aaf23960612423ffd0f724e71d1a3cd4b21b380"} |
| Candidate configuration hash | 64da4b3dbb61be3b0f6b7c7550c24eb00880717b0316cfee922805bdfabc33aa |

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
|  | excluded | empty | surrounding_punctuation_removed |
| . | excluded | punctuation_only |  |
| 10s | excluded | currency_expression, numeric_expression |  |
| 12s | excluded | currency_expression, numeric_expression |  |
| 12th | excluded | ordinal_expression |  |
| 19th | excluded | ordinal_expression |  |
| 1s | excluded | currency_expression, numeric_expression |  |
| 22nd | excluded | ordinal_expression |  |
| 26s | excluded | currency_expression, numeric_expression |  |
| 2nd | excluded | ordinal_expression |  |
| 2s | excluded | currency_expression, numeric_expression |  |
| 3rd | excluded | ordinal_expression |  |
| 4d | excluded | currency_expression, numeric_expression |  |
| 4th | excluded | ordinal_expression |  |
| 6d | excluded | currency_expression, numeric_expression |  |
| 7s | excluded | currency_expression, numeric_expression |  |
| 8s | excluded | currency_expression, numeric_expression |  |
| A | excluded | determiner, function_word_only | case_folded |
| A. | excluded | isolated_abbreviation | case_folded |
| All | excluded | function_word_only | case_folded |
| All my medical instincts | excluded |  | case_folded |
| all that | excluded | function_word_only |  |
| All this | excluded | function_word_only | case_folded |
| all those | excluded | function_word_only |  |
| And this | excluded | function_word_only, leading_discourse_marker | case_folded |
| And what | excluded | function_word_only, leading_discourse_marker | case_folded |
| Anybody | excluded |  | case_folded |
| Anyhow | excluded |  | case_folded |
| Anything | excluded | generic_single_noun | case_folded |
| B | excluded |  | case_folded |

`{"address_like": 3, "all_caps_fragment": 18, "currency_expression": 13, "determiner": 11, "empty": 1, "excessive_punctuation": 12, "function_word_only": 28, "generic_single_noun": 21, "heading_fragment": 4, "isolated_abbreviation": 7, "leading_discourse_marker": 194, "numeric_expression": 9, "ordinal_expression": 6, "pronoun": 15, "punctuation_only": 1}`

## Tier Distribution
| Tier | Count |
| --- | --- |
| excluded | 2706 |
| review | 210 |
| tier_a | 4749 |
| tier_b | 4852 |

By unit type: `{"common_noun": 2781, "named_entity": 587, "noun_phrase": 9343, "proper_noun": 529}`

By frequency: `{"frequency_gte_10": 548, "frequency_gte_2": 3686, "frequency_gte_3": 2296, "frequency_gte_5": 1309}`

By token length: `{"0": 1, "1": 3732, "2": 4823, "3": 2992, "4": 757, "5": 152, "6-8": 59, ">8": 1}`

By content-token count: `{"0": 30, "1": 7259, "2": 3916, "3": 1084, "4": 187, "5": 31, "6": 7, "7": 3}`

By possessor type: `{"common": 175, "mixed": 1, "named": 164, "none": 10372, "pronoun": 1805}`

Tier reasons: `{"clean_common_noun_frequency_gte_threshold": 1109, "clean_multiword_named_or_proper_expression": 393, "clean_repeated_single_token_name": 322, "currency_expression": 12, "excessive_punctuation": 12, "generic_single_noun": 18, "heading_fragment": 1, "isolated_abbreviation": 5, "leading_discourse_marker": 187, "long_or_complex_phrase": 10, "low_priority_pronoun_possessive": 1417, "mixed_possessor": 1, "numeric_expression": 9, "ordinal_expression": 6, "pronoun_possessive_frequency_gte_threshold": 379, "rare_clean_single_token_name": 268, "singleton_common_noun_low_priority": 1140, "specific_content_phrase": 4034, "upstream_rejected_only": 108, "valid_one_content_token_phrase": 3096}`

Review reasons: `{"excessive_punctuation": 12, "heading_fragment": 1, "leading_discourse_marker": 187, "long_or_complex_phrase": 10, "mixed_possessor": 1}`

Exclusion reasons: `{"currency_expression": 12, "generic_single_noun": 18, "isolated_abbreviation": 5, "low_priority_pronoun_possessive": 1417, "numeric_expression": 9, "ordinal_expression": 6, "singleton_common_noun_low_priority": 1140, "upstream_rejected_only": 108}`

By story count: `{"1": 9628, "2-3": 1844, "4-6": 626, "7+": 419}`

## Candidate Examples
| Candidate | Tier | Frequency | Stories | Reasons |
| --- | --- | --- | --- | --- |
| I | excluded | 3630 | 12 | upstream_rejected_only |
| He | excluded | 1911 | 12 | upstream_rejected_only |
| It | excluded | 1733 | 12 | upstream_rejected_only |
| You | excluded | 1492 | 12 | upstream_rejected_only |
| Which | excluded | 764 | 12 | upstream_rejected_only |
| We | excluded | 712 | 12 | upstream_rejected_only |
| She | excluded | 575 | 11 | upstream_rejected_only |
| them | excluded | 346 | 12 | upstream_rejected_only |
| man | excluded | 324 | 12 | generic_single_noun |
| That | excluded | 321 | 12 | upstream_rejected_only |
| What | excluded | 319 | 12 | upstream_rejected_only |
| Who | excluded | 268 | 12 | upstream_rejected_only |
| time | excluded | 137 | 12 | generic_single_noun |
| matter | excluded | 136 | 12 | generic_single_noun |
| case | excluded | 135 | 12 | generic_single_noun |
| way | excluded | 125 | 12 | generic_single_noun |
| All | excluded | 119 | 12 | upstream_rejected_only |
| This | excluded | 117 | 12 | upstream_rejected_only |
| Nothing | excluded | 106 | 12 | upstream_rejected_only |
| One | excluded | 75 | 12 | generic_single_noun |
| himself | excluded | 73 | 12 | upstream_rejected_only |
| myself | excluded | 72 | 12 | upstream_rejected_only |
| woman | excluded | 72 | 10 | generic_single_noun |
| thing | excluded | 68 | 12 | generic_single_noun |
| Something | excluded | 65 | 12 | upstream_rejected_only |
| point | excluded | 60 | 12 | generic_single_noun |
| Anything | excluded | 48 | 12 | upstream_rejected_only |
| place | excluded | 45 | 11 | generic_single_noun |
| Whom | excluded | 39 | 11 | upstream_rejected_only |
| Mr. | excluded | 32 | 9 | upstream_rejected_only |
| part | excluded | 29 | 11 | generic_single_noun |
| anyone | excluded | 24 | 12 | upstream_rejected_only |
| sort | excluded | 23 | 8 | generic_single_noun |
| Those | excluded | 21 | 9 | upstream_rejected_only |
| everything | excluded | 20 | 8 | upstream_rejected_only |
| person | excluded | 20 | 12 | generic_single_noun |
| ourselves | excluded | 19 | 11 | upstream_rejected_only |
| itself | excluded | 18 | 9 | upstream_rejected_only |
| No | excluded | 18 | 11 | isolated_abbreviation |
| Some | excluded | 18 | 8 | upstream_rejected_only |
| Someone | excluded | 18 | 8 | upstream_rejected_only |
| These | excluded | 18 | 10 | upstream_rejected_only |
| Men | excluded | 17 | 9 | generic_single_noun |
| £ | excluded | 17 | 7 | upstream_rejected_only |
| Both | excluded | 16 | 11 | upstream_rejected_only |
| People | excluded | 16 | 9 | generic_single_noun |
| another | excluded | 12 | 7 | upstream_rejected_only |
| fact | excluded | 12 | 8 | generic_single_noun |
| I. | excluded | 12 | 9 | upstream_rejected_only |
| Whatever | excluded | 12 | 7 | upstream_rejected_only |

## Baseline Coverage
| Question | Question Unit | Comparison | Inventory Match | Inventory Coverage | Inventory Candidate | Inventory Tier | Eligible Match | Eligible Coverage | Eligible Candidate | Eligible Tier | Token Ratio |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| q001 | Sherlock Holmes | sherlock holmes | candidate_text_exact_match | strong | Sherlock Holmes | tier_a | candidate_text_exact_match | strong | Sherlock Holmes | tier_a | 1.0 |
| q001 | the woman | the woman | candidate_text_exact_match | strong | The woman | tier_b | candidate_text_exact_match | strong | The woman | tier_b | 1.0 |
| q001 | Who | who | candidate_text_exact_match | strong | Who | excluded | no_match | none |  |  | 1.0 |
| q001 | whom | whom | candidate_text_exact_match | strong | Whom | excluded | no_match | none |  |  | 1.0 |
| q001 | woman | woman | candidate_text_exact_match | strong | woman | excluded | contiguous_contained_candidate | partial_phrase | that woman | tier_b | 1.0 |
| q002 | Encyclopaedia Britannica | encyclopaedia britannica | candidate_text_exact_match | strong | Encyclopaedia Britannica | tier_a | candidate_text_exact_match | strong | Encyclopaedia Britannica | tier_a | 1.0 |
| q002 | Jabez Wilson | jabez wilson | candidate_text_exact_match | strong | Jabez Wilson | tier_a | candidate_text_exact_match | strong | Jabez Wilson | tier_a | 1.0 |
| q002 | the Encyclopaedia Britannica | the encyclopaedia britannica | candidate_text_exact_match | strong | the Encyclopaedia Britannica | tier_a | candidate_text_exact_match | strong | the Encyclopaedia Britannica | tier_a | 1.0 |
| q003 | he | he | candidate_text_exact_match | strong | He | excluded | no_match | none |  |  | 1.0 |
| q003 | Hosmer Angel | hosmer angel | candidate_text_exact_match | strong | Hosmer Angel | tier_a | candidate_text_exact_match | strong | Hosmer Angel | tier_a | 1.0 |
| q003 | Who | who | candidate_text_exact_match | strong | Who | excluded | no_match | none |  |  | 1.0 |
| q004 | orange | orange | candidate_text_exact_match | strong | orange | tier_b | candidate_text_exact_match | strong | orange | tier_b | 1.0 |
| q004 | pips | pips | candidate_text_exact_match | strong | pips | tier_b | candidate_text_exact_match | strong | pips | tier_b | 1.0 |
| q004 | the five orange pips | the five orange pips | contiguous_contained_candidate | partial_phrase | the orange pips | tier_a | contiguous_contained_candidate | partial_phrase | the orange pips | tier_a | 0.75 |
| q004 | they | they | alternate_surface_match | strong | them | excluded | no_match | none |  |  | 1.0 |
| q004 | What | what | candidate_text_exact_match | strong | What | excluded | no_match | none |  |  | 1.0 |
| q005 | his life | his life | candidate_text_exact_match | strong | his life | tier_b | candidate_text_exact_match | strong | his life | tier_b | 1.0 |
| q005 | Hugh Boone | hugh boone | candidate_text_exact_match | strong | Hugh Boone | tier_a | candidate_text_exact_match | strong | Hugh Boone | tier_a | 1.0 |
| q005 | life | life | candidate_text_exact_match | strong | life | tier_b | candidate_text_exact_match | strong | life | tier_b | 1.0 |
| q005 | Neville St. Clair | neville st. clair | candidate_text_exact_match | strong | Neville St. Clair | tier_a | candidate_text_exact_match | strong | Neville St. Clair | tier_a | 1.0 |
| q005 | part | part | candidate_text_exact_match | strong | part | excluded | contiguous_contained_candidate | partial_phrase | that part | tier_b | 1.0 |
| q005 | the beggar Hugh Boone | the beggar hugh boone | contiguous_contained_candidate | partial_phrase | Hugh Boone | tier_a | contiguous_contained_candidate | partial_phrase | Hugh Boone | tier_a | 0.5 |
| q006 | a Christmas goose | a christmas goose | contiguous_contained_candidate | partial_phrase | that goose | tier_b | contiguous_contained_candidate | partial_phrase | that goose | tier_b | 0.6667 |
| q006 | carbuncle | carbuncle | candidate_text_exact_match | strong | carbuncle | tier_b | candidate_text_exact_match | strong | carbuncle | tier_b | 1.0 |
| q006 | Christmas | christmas | candidate_text_exact_match | strong | Christmas | tier_a | candidate_text_exact_match | strong | Christmas | tier_a | 1.0 |
| q006 | goose | goose | candidate_text_exact_match | strong | goose | tier_b | candidate_text_exact_match | strong | goose | tier_b | 1.0 |
| q006 | the stolen blue carbuncle | the stolen blue carbuncle | contiguous_contained_candidate | partial_phrase | the blue carbuncle | tier_a | contiguous_contained_candidate | partial_phrase | the blue carbuncle | tier_a | 0.75 |
| q007 | band | band | candidate_text_exact_match | strong | band | tier_b | candidate_text_exact_match | strong | band | tier_b | 1.0 |
| q007 | death | death | candidate_text_exact_match | strong | Death | tier_b | candidate_text_exact_match | strong | Death | tier_b | 1.0 |
| q007 | Julia Stoner | julia stoner | contiguous_contained_candidate | partial_phrase | Julia | tier_a | contiguous_contained_candidate | partial_phrase | Julia | tier_a | 0.5 |
| q007 | Julia Stoner's | julia stoner's | contiguous_contained_candidate | partial_phrase | Julia | tier_a | contiguous_contained_candidate | partial_phrase | Julia | tier_a | 0.5 |
| q007 | Julia Stoner's death | julia stoner's death | contiguous_contained_candidate | partial_phrase | her death | tier_b | contiguous_contained_candidate | partial_phrase | her death | tier_b | 0.6667 |
| q007 | that | that | candidate_text_exact_match | strong | That | excluded | no_match | none |  |  | 1.0 |
| q007 | the "speckled band | the speckled band | comparison_form_match | strong | The speckled band | tier_a | comparison_form_match | strong | The speckled band | tier_a | 1.0 |
| q007 | What | what | candidate_text_exact_match | strong | What | excluded | no_match | none |  |  | 1.0 |
| q008 | cases | cases | alternate_surface_match | strong | case | excluded | contiguous_contained_candidate | partial_phrase | these cases | tier_b | 1.0 |
| q008 | each | each | candidate_text_exact_match | strong | each | excluded | no_match | none |  |  | 1.0 |
| q008 | employment | employment | candidate_text_exact_match | strong | employment | tier_b | candidate_text_exact_match | strong | employment | tier_b | 1.0 |
| q008 | offers | offers | alternate_surface_match | strong | offer | tier_b | alternate_surface_match | strong | offer | tier_b | 1.0 |
| q008 | purpose | purpose | candidate_text_exact_match | strong | purpose | tier_b | candidate_text_exact_match | strong | purpose | tier_b | 1.0 |
| q008 | suspiciously generous employment offers | suspiciously generous employment offers | contiguous_contained_candidate | partial_phrase | employment | tier_b | contiguous_contained_candidate | partial_phrase | employment | tier_b | 0.25 |
| q008 | what hidden purpose | what hidden purpose | contiguous_contained_candidate | partial_phrase | their purpose | excluded | contiguous_contained_candidate | partial_phrase | that purpose | tier_b | 0.6667 |
| q008 | Which two cases | which two cases | contiguous_contained_candidate | partial_phrase | all our cases | excluded | contiguous_contained_candidate | partial_phrase | these cases | tier_b | 0.6667 |

Inventory: `{"inventory_head_only": 0, "inventory_none": 0, "inventory_partial_phrase": 10, "inventory_strong": 33}`

Eligible: `{"eligible_head_only": 0, "eligible_none": 9, "eligible_partial_phrase": 13, "eligible_strong": 21}`

## Structural Quality Gates
| Gate | Count |
| --- | --- |
| Rejected-only in Tier A | 0 |
| Rejected-only in Tier B | 0 |
| Eligible candidates with hard flags | 0 |
| Eligible candidates with unresolved boundary flags | 0 |

Manual quality decision pending. Suggested future Go criteria: Tier A boundary correctness >= 95%, appropriate-for-embedding precision >= 90%, and tier-correct precision >= 85%.

## Estimated Next-Stage Workload
| Workload | Count |
| --- | --- |
| Tier A embedding computations | 4749 |
| Tier A Top-10 pairs for inspection | 47490 |
| Tier A + Tier B embedding computations | 9601 |
| Tier A + Tier B Top-10 pairs for inspection | 96010 |

Embedding computation workload is the number of candidate vectors. Human pair-review workload is the candidate count multiplied by the nearest-neighbour depth.

## Recommendation
Structural gates passed - complete manual sample review before embedding
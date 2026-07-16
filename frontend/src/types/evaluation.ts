export interface ExperimentMetadata {
  experiment_id: string;
  evaluation_type: string;
  question_count: number;
  top_k: number;
  retrieval_method: string;
  generated_at_utc: string;
  generation_id: string;
  judgment_schema_version: string;
}

export interface PipelineStep {
  step_id: string;
  name: string;
  status: string;
  section_count?: number;
  chunk_count?: number;
  maximum_tokens?: number;
  model_name?: string;
  dimensions?: number;
  normalized?: boolean;
  embedding_count?: number;
  question_count?: number;
}

export interface PipelineMetadata {
  steps: PipelineStep[];
}

export interface DocumentMetadata {
  document_id: string;
  title: string;
  author: string;
  source_name: string;
  source_reference: string;
}

export interface Story {
  section_order: number;
  section_title: string;
  section_text: string;
}

export interface Chunk {
  chunk_uid: string;
  section_order: number;
  section_title: string;
  chunk_order: number;
  token_count: number;
  overlap_tokens: number;
  chunk_text: string;
}

export interface AggregateMetrics {
  direct_hit_rate_at_1: number;
  direct_hit_rate_at_3: number;
  direct_hit_rate_at_5: number;
  direct_hit_rate_at_10: number;
  answer_sufficiency_rate_at_1: number;
  answer_sufficiency_rate_at_3: number;
  answer_sufficiency_rate_at_5: number;
  answer_sufficiency_rate_at_10: number;
  mrr: number;
  average_noise_rate_at_10: number;
  label_totals: Record<string, number>;
}

export interface QuestionMetrics {
  first_direct_evidence_rank: number | null;
  direct_hit_at_1: number;
  direct_hit_at_3: number;
  direct_hit_at_5: number;
  direct_hit_at_10: number;
  reciprocal_rank: number;
  noise_rate_at_10: number;
  useful_precision_at_1: number;
  useful_precision_at_3: number;
  useful_precision_at_5: number;
  useful_precision_at_10: number;
}

export interface ChunkJudgment {
  label: string;
  supports_answer: boolean;
  reason: string;
}

export interface EvaluatedChunk {
  rank: number;
  chunk_uid: string;
  section_order: number;
  section_title: string;
  chunk_order: number;
  token_count: number;
  cosine_distance: number;
  cosine_similarity: number;
  chunk_text: string;
  judgment: ChunkJudgment;
}

export interface MissingEvidence {
  section_order: number;
  section_title: string;
  evidence_quote: string;
  reason: string;
}

export interface CandidateStoryJudgment {
  section_order: number;
  section_title: string;
  label: string;
  reason: string;
}

export interface JudgeAssessment {
  retrieval_quality: string;
  score_0_to_100: number;
  summary: string;
  confidence: number;
}

export interface RetrievalMetadata {
  query_token_count: number;
  embedding_duration_ms: number;
  database_duration_ms: number;
  candidate_story_orders: number[];
}

export interface QuestionEvaluation {
  question_id: string;
  category: string;
  question: string;
  question_interpretation: string;
  reference_answer: string;
  retrieval: RetrievalMetadata;
  candidate_story_judgments: CandidateStoryJudgment[];
  retrieved_chunks: EvaluatedChunk[];
  missing_evidence_within_candidate_stories: MissingEvidence[];
  judge_assessment: JudgeAssessment;
  computed_metrics: QuestionMetrics;
  rag_answer?: BaselineRagAnswer | null;
}

export interface SourceProvenance {
  questions_sha256: string;
  retrieval_results_sha256: string;
  document_sha256: string;
  sections_sha256: string;
  chunks_sha256: string;
  judgments_sha256: Record<string, string>;
}

export interface BaselineEvaluation {
  schema_version: string;
  experiment: ExperimentMetadata;
  pipeline: PipelineMetadata;
  document: DocumentMetadata;
  stories: Story[];
  chunks: Chunk[];
  aggregate_metrics: AggregateMetrics;
  questions: QuestionEvaluation[];
  source_provenance: SourceProvenance;
}

export interface RagCitation {
  chunk_uid: string;
  reason: string;
}

export interface TokenUsage {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
}

export interface BaselineRagAnswer {
  generation_id: string;
  prompt_version: string;
  model_name: string;
  answer: string;
  evidence_sufficient: boolean;
  citations: RagCitation[];
  confidence: number;
  generation_duration_ms: number;
  attempt_count: number;
  usage: TokenUsage | null;
  context_chunk_uids: string[];
}

export interface LiveRetrievalResult {
  rank: number;
  chunk_uid: string;
  section_order: number;
  section_title: string;
  chunk_order: number;
  token_count: number;
  chunk_text: string;
  cosine_distance: number;
  cosine_similarity: number;
}

export interface LiveRagAnswerResponse {
  request_id: string;
  question: string;
  document_id: string;

  retrieval: {
    model_name: string;
    top_k: number;
    embedding_duration_ms: number;
    database_duration_ms: number;
    results: LiveRetrievalResult[];
  };

  generation: {
    model_name: string;
    answer: string;
    evidence_sufficient: boolean;
    citations: RagCitation[];
    confidence: number;
    generation_duration_ms: number;
    attempt_count: number;
    usage: TokenUsage | null;
  };
}

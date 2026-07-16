import { useParams, useNavigate } from "react-router";
import { useBaselineEvaluation } from "@/hooks/use-baseline-evaluation";
import { useQuestionEvaluation } from "@/hooks/use-question-evaluation";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { AlertCircle, Clock, FileText, ChevronRight, HelpCircle } from "lucide-react";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import type { EvaluatedChunk } from "@/types/evaluation";

export default function BaselineQuestionPage() {
  const { questionId } = useParams();
  const navigate = useNavigate();
  const { data, loading: baselineLoading } = useBaselineEvaluation();
  const { question, loading, error } = useQuestionEvaluation(questionId || "");

  if (loading || baselineLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-10 w-[200px]" />
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (error || !question || !data) {
    return (
      <Alert variant="destructive">
        <AlertCircle className="h-4 w-4" />
        <AlertTitle>Error loading question</AlertTitle>
        <AlertDescription>{error?.message || "Question not found."}</AlertDescription>
      </Alert>
    );
  }

  const handleQuestionChange = (val: string | null) => {
    if (val) navigate(`/baseline/${val}`);
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Question Evaluation</h1>
          <p className="text-muted-foreground mt-1 text-sm">
            Detailed breakdown of retrieval and judgments for this query.
          </p>
        </div>
        
        <Select value={question.question_id} onValueChange={handleQuestionChange}>
          <SelectTrigger className="w-[280px]">
            <SelectValue placeholder="Select a question" />
          </SelectTrigger>
          <SelectContent>
            {data.questions.map(q => (
              <SelectItem key={q.question_id} value={q.question_id}>
                {q.question_id} - {q.question.substring(0, 30)}...
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <Card className="border-slate-200 shadow-sm dark:border-slate-800">
        <CardHeader className="bg-slate-50/50 dark:bg-slate-900/50 border-b">
          <div className="flex items-center justify-between mb-2">
            <Badge variant="outline" className="capitalize text-primary bg-primary/5">
              {question.category.replace('_', ' ')}
            </Badge>
            <div className="flex items-center gap-4 text-sm text-muted-foreground">
              <span className="flex items-center gap-1"><Clock className="h-3 w-3" /> {question.retrieval.embedding_duration_ms + question.retrieval.database_duration_ms}ms</span>
              <span className="flex items-center gap-1"><FileText className="h-3 w-3" /> {question.retrieval.query_token_count} tokens</span>
            </div>
          </div>
          <CardTitle className="text-xl leading-relaxed">{question.question}</CardTitle>
          {question.question_interpretation && (
            <CardDescription className="text-sm italic mt-2">
              Interpretation: {question.question_interpretation}
            </CardDescription>
          )}
        </CardHeader>
        <CardContent className="pt-6">
          <div className="grid grid-cols-1 gap-6 mb-6">
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <h3 className="font-semibold text-sm text-muted-foreground uppercase tracking-wider">Reference Answer</h3>
                <span className="text-xs text-muted-foreground bg-slate-100 dark:bg-slate-800 px-2 py-0.5 rounded">
                  LLM-assisted · Human-reviewed
                </span>
              </div>
              <p className="text-sm bg-primary/5 border border-primary/10 rounded-md p-4 text-foreground/90 min-h-[120px]">
                {question.reference_answer}
              </p>
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <h3 className="font-semibold text-sm text-muted-foreground uppercase tracking-wider">Generated RAG Answer</h3>
                <span className="text-xs text-muted-foreground bg-slate-100 dark:bg-slate-800 px-2 py-0.5 rounded">
                  GPT-OSS-120B · Based only on Top 10
                </span>
              </div>
              {question.rag_answer ? (
                <div className="text-sm bg-blue-50/30 dark:bg-blue-950/10 border border-blue-100 dark:border-blue-900/30 rounded-md p-4 text-foreground/90 min-h-[120px] flex flex-col justify-between">
                  <p>{question.rag_answer.answer}</p>
                  <div className="mt-4 pt-3 border-t border-blue-100/50 dark:border-blue-900/20 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
                    <span>Evidence: {question.rag_answer.evidence_sufficient ? "Sufficient" : "Insufficient"}</span>
                    <span>Confidence: {(question.rag_answer.confidence * 100).toFixed(0)}%</span>
                    <span>Time: {question.rag_answer.generation_duration_ms.toFixed(0)}ms</span>
                  </div>
                </div>
              ) : (
                <p className="text-sm bg-slate-50 border border-dashed rounded-md p-4 text-muted-foreground min-h-[120px] flex items-center justify-center">
                  No RAG answer generated for this question.
                </p>
              )}
            </div>
          </div>
          
          <div className="mt-6 grid grid-cols-2 md:grid-cols-4 gap-4">
            <TooltipProvider>
              <MetricItem
                label="Hit @1"
                value={question.computed_metrics.direct_hit_at_1 ? 'Yes' : 'No'}
                valueClass={question.computed_metrics.direct_hit_at_1 ? 'text-green-600 dark:text-green-400' : 'text-muted-foreground'}
                tooltip="Whether the top 1 retrieved result directly answers the question. Yes = precise hit; No = top result is not the most relevant. Target is Yes."
              />
              <MetricItem
                label="Reciprocal Rank"
                value={question.computed_metrics.reciprocal_rank.toFixed(3)}
                tooltip="The reciprocal of the rank of the first 'directly relevant' result. E.g., rank 1 → 1.000, rank 5 → 0.200, rank 9 → 0.111. Higher is better, max is 1.000."
              />
              <MetricItem
                label="Noise @10"
                value={(question.computed_metrics.noise_rate_at_10 * 100).toFixed(0) + '%'}
                valueClass={question.computed_metrics.noise_rate_at_10 > 0.6 ? 'text-red-500 dark:text-red-400' : question.computed_metrics.noise_rate_at_10 > 0.3 ? 'text-amber-500' : 'text-green-600 dark:text-green-400'}
                tooltip="The proportion of irrelevant/noisy chunks in the top 10 retrieved results. E.g., 80% means 8 out of 10 chunks are not useful. Lower is better, ideal is 0%."
              />
              <MetricItem
                label="Judge Score"
                value={question.judge_assessment.score_0_to_100 + '/100'}
                tooltip="The score comprehensively evaluated by the AI Judge on whether the retrieved results can sufficiently answer the question. Higher is better, max is 100."
              />
            </TooltipProvider>
          </div>
        </CardContent>
      </Card>

      <div className="space-y-4 mt-8">
        <h2 className="text-xl font-bold tracking-tight">Top 10 Retrieved Chunks</h2>
        <div className="space-y-4">
          {question.retrieved_chunks.map((chunk) => {
            const citation = question.rag_answer?.citations?.find(c => c.chunk_uid === chunk.chunk_uid);
            const isCited = !!citation;
            const citationReason = citation?.reason;
            return (
              <ChunkCard 
                key={chunk.chunk_uid} 
                chunk={chunk} 
                isCited={isCited}
                citationReason={citationReason}
              />
            );
          })}
        </div>
      </div>
    </div>
  );
}

function ChunkCard({ 
  chunk, 
  isCited, 
  citationReason 
}: { 
  chunk: EvaluatedChunk; 
  isCited?: boolean; 
  citationReason?: string; 
}) {
  const getLabelColor = (label: string) => {
    switch (label) {
      case "direct_evidence":
      case "directly_relevant":
        return "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400 border-green-200 dark:border-green-800";
      case "topically_related":
      case "supporting_context":
        return "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400 border-amber-200 dark:border-amber-800";
      default:
        return "bg-slate-100 text-slate-800 dark:bg-slate-800 dark:text-slate-400 border-slate-200 dark:border-slate-700";
    }
  };

  const getLabelText = (label: string) => {
    switch (label) {
      case "direct_evidence": return "Direct Evidence";
      case "directly_relevant": return "Directly Relevant";
      case "topically_related": return "Topically Related";
      case "supporting_context": return "Supporting Context";
      case "irrelevant": return "Irrelevant";
      default: return label;
    }
  };

  return (
    <Card className={`border-slate-200 shadow-sm dark:border-slate-800 overflow-hidden group transition-all ${isCited ? "border-blue-500 ring-1 ring-blue-100 dark:ring-blue-950/30" : ""}`}>
      <div className="flex flex-col md:flex-row md:items-center justify-between p-4 bg-slate-50 dark:bg-slate-900/50 border-b gap-4">
        <div className="flex items-center gap-3">
          <div className="flex items-center justify-center h-8 w-8 rounded-full bg-primary/10 text-primary font-bold text-sm">
            #{chunk.rank}
          </div>
          <div>
            <div className="text-sm font-medium flex items-center gap-2">
              <span className="text-muted-foreground truncate max-w-[200px] sm:max-w-[300px]">
                {chunk.section_title}
              </span>
              <ChevronRight className="h-3 w-3 text-muted-foreground" />
              <span className="text-xs text-muted-foreground bg-slate-200 dark:bg-slate-800 px-1.5 py-0.5 rounded">
                Chunk {chunk.chunk_order}
              </span>
            </div>
            <div className="text-xs text-muted-foreground mt-1 flex gap-3">
              <span>Distance: {chunk.cosine_distance.toFixed(4)}</span>
              <span>Tokens: {chunk.token_count}</span>
            </div>
          </div>
        </div>
        
        <div className="flex items-center gap-2 flex-wrap">
          <Badge variant="outline" className={`${getLabelColor(chunk.judgment.label)} whitespace-nowrap`}>
            {getLabelText(chunk.judgment.label)}
          </Badge>
          {isCited && (
            <Badge variant="outline" className="bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400 border-blue-200 dark:border-blue-800 whitespace-nowrap">
              Cited by RAG
            </Badge>
          )}
        </div>
      </div>
      
      <CardContent className="p-0">
        <Accordion>
          <AccordionItem value="text" className="border-none">
            <AccordionTrigger className="px-4 py-3 hover:bg-slate-50 dark:hover:bg-slate-900/50 text-sm font-medium">
              View Chunk Content & Reasoning
            </AccordionTrigger>
            <AccordionContent className="px-4 pb-4">
              <div className="space-y-4 pt-2">
                <div className="bg-slate-50 dark:bg-slate-900 rounded-md p-3 text-sm text-muted-foreground italic border border-slate-100 dark:border-slate-800">
                  <span className="font-semibold text-foreground not-italic block mb-1">Judge Reasoning:</span>
                  {chunk.judgment.reason}
                </div>
                {isCited && citationReason && (
                  <div className="bg-blue-50/50 dark:bg-blue-950/20 rounded-md p-3 text-sm text-muted-foreground italic border border-blue-100/50 dark:border-blue-900/20">
                    <span className="font-semibold text-foreground not-italic block mb-1">RAG Citation Reason:</span>
                    {citationReason}
                  </div>
                )}
                <div>
                  <p className="text-sm leading-relaxed text-foreground whitespace-pre-wrap font-serif">
                    {chunk.chunk_text}
                  </p>
                </div>
              </div>
            </AccordionContent>
          </AccordionItem>
        </Accordion>
      </CardContent>
    </Card>
  );
}

function MetricItem({
  label,
  value,
  tooltip,
  valueClass,
}: {
  label: string;
  value: string;
  tooltip: string;
  valueClass?: string;
}) {
  return (
    <div className="flex flex-col">
      <Tooltip>
        <TooltipTrigger
          render={
            <span className="text-xs text-muted-foreground flex items-center gap-1 cursor-help w-fit" />
          }
        >
          {label}
          <HelpCircle className="h-3 w-3 opacity-50" />
        </TooltipTrigger>
        <TooltipContent side="top" className="max-w-[220px] text-xs leading-relaxed">
          {tooltip}
        </TooltipContent>
      </Tooltip>
      <span className={`font-semibold text-lg ${valueClass ?? ""}`}>{value}</span>
    </div>
  );
}

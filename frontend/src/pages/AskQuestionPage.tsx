import { useState, useRef, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { 
  Search, 
  Sparkles, 
  Loader2, 
  AlertCircle, 
  CheckCircle2, 
  Clock, 
  FileText, 
  ChevronRight, 
  HelpCircle,
  XCircle
} from "lucide-react";
import { askQuestion } from "@/api/rag-api";
import type { LiveRagAnswerResponse, LiveRetrievalResult } from "@/types/evaluation";

export default function AskQuestionPage() {
  const [questionText, setQuestionText] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [response, setResponse] = useState<LiveRagAnswerResponse | null>(null);
  
  const abortControllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmedQuestion = questionText.trim();
    if (!trimmedQuestion || loading) return;

    setLoading(true);
    setError(null);
    setResponse(null);

    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    abortControllerRef.current = new AbortController();

    try {
      const res = await askQuestion(trimmedQuestion, abortControllerRef.current.signal);
      setResponse(res);
    } catch (err: any) {
      if (err.name === "AbortError") return;
      setError(err.message || "An unexpected error occurred.");
    } finally {
      setLoading(false);
    }
  };

  const handleCancel = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      setLoading(false);
      setError("Request cancelled by user.");
    }
  };

  const totalDuration = response
    ? response.retrieval.embedding_duration_ms +
      response.retrieval.database_duration_ms +
      response.generation.generation_duration_ms
    : 0;

  return (
    <div className="space-y-6 animate-in fade-in duration-500 max-w-4xl mx-auto mt-8">
      <div className="text-center space-y-2 mb-8">
        <h1 className="text-3xl font-bold tracking-tight">Ask the Sherlock Holmes Collection</h1>
        <p className="text-muted-foreground">
          Query the Holmes corpus in real-time using the live retrieval and generation pipeline.
        </p>
      </div>

      <Card className="border-slate-200 shadow-md dark:border-slate-800">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Search className="h-5 w-5 text-primary" />
            Your Question
          </CardTitle>
          <CardDescription>
            Enter a question about the Sherlock Holmes stories to query the live vector database and generate a grounded answer.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <textarea 
              placeholder="e.g., What was the color of the ribbon in The Speckled Band?"
              value={questionText}
              onChange={(e) => setQuestionText(e.target.value)}
              className="flex min-h-[100px] w-full rounded-md border border-input bg-slate-50 dark:bg-slate-900/50 px-3 py-2 text-base ring-offset-background placeholder:text-muted-foreground focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 resize-none"
              disabled={loading}
            />
            <div className="flex justify-end gap-3">
              {loading && (
                <Button type="button" variant="outline" onClick={handleCancel} className="gap-2">
                  <XCircle className="h-4 w-4" />
                  Cancel
                </Button>
              )}
              <Button type="submit" disabled={loading || !questionText.trim()} className="gap-2">
                {loading ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Sparkles className="h-4 w-4" />
                )}
                {loading ? "Generating Answer..." : "Ask Question"}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      {error && (
        <Alert variant="destructive" className="border-red-200 bg-red-50/50 dark:bg-red-950/10 dark:border-red-900/30">
          <AlertCircle className="h-4 w-4 text-red-600 dark:text-red-400" />
          <AlertTitle className="text-red-800 dark:text-red-400 font-semibold">Pipeline Error</AlertTitle>
          <AlertDescription className="text-red-700 dark:text-red-300">{error}</AlertDescription>
        </Alert>
      )}

      {(loading || response) && (
        <Card className="border-slate-200 shadow-sm dark:border-slate-800">
          <CardHeader className="border-b bg-slate-50/50 dark:bg-slate-900/50">
            <CardTitle className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
              Live Pipeline
            </CardTitle>
          </CardHeader>
          <CardContent className="pt-6">
            <div className="flex flex-col space-y-4 md:flex-row md:space-x-4 md:space-y-0">
              <PipelineStep 
                label="Question" 
                status={loading ? "processing" : "completed"} 
                detail={loading ? "Submitted" : "Complete"} 
              />
              <PipelineStep 
                label="MiniLM Embedding" 
                status={loading ? "processing" : "completed"} 
                detail={loading ? "Processing" : `${response?.retrieval.embedding_duration_ms.toFixed(1)} ms`} 
              />
              <PipelineStep 
                label="Exact Cosine Top 10" 
                status={loading ? "processing" : "completed"} 
                detail={loading ? "Processing" : `${response?.retrieval.database_duration_ms.toFixed(1)} ms`} 
              />
              <PipelineStep 
                label="GPT-OSS-120B" 
                status={loading ? "processing" : "completed"} 
                detail={loading ? "Processing" : `${response?.generation.generation_duration_ms.toFixed(1)} ms`} 
              />
              <PipelineStep 
                label="Generated Answer" 
                status={loading ? "pending" : "completed"} 
                detail={loading ? "Waiting" : "Complete"} 
                isLast
              />
            </div>
          </CardContent>
        </Card>
      )}

      {response && (
        <div className="space-y-6 animate-in fade-in duration-500">
          <Card className="border-slate-200 shadow-md dark:border-slate-800 overflow-hidden">
            <CardHeader className="bg-slate-50/50 dark:bg-slate-900/50 border-b">
              <div className="flex items-center justify-between flex-wrap gap-2">
                <div className="flex items-center gap-2">
                  <Badge variant={response.generation.evidence_sufficient ? "outline" : "destructive"} className={response.generation.evidence_sufficient ? "bg-green-50 text-green-700 border-green-200 dark:bg-green-950/20 dark:text-green-400 dark:border-green-900/30" : ""}>
                    Evidence: {response.generation.evidence_sufficient ? "Sufficient" : "Insufficient"}
                  </Badge>
                  <Badge variant="outline" className="bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950/20 dark:text-blue-400 dark:border-blue-900/30">
                    Confidence: {(response.generation.confidence * 100).toFixed(0)}%
                  </Badge>
                </div>
                <div className="flex items-center gap-4 text-xs text-muted-foreground">
                  <span className="flex items-center gap-1"><Clock className="h-3.5 w-3.5" /> Total: {totalDuration.toFixed(0)}ms</span>
                  <span className="flex items-center gap-1"><FileText className="h-3.5 w-3.5" /> {response.generation.usage ? `${response.generation.usage.total_tokens} tokens` : "N/A"}</span>
                </div>
              </div>
              <CardTitle className="text-lg font-bold mt-2">Generated RAG Answer</CardTitle>
            </CardHeader>
            <CardContent className="pt-6 space-y-4">
              {!response.generation.evidence_sufficient && (
                <Alert className="bg-amber-50/50 border-amber-200 text-amber-800 dark:bg-amber-950/10 dark:border-amber-900/30 dark:text-amber-400">
                  <AlertCircle className="h-4 w-4 text-amber-600 dark:text-amber-400" />
                  <AlertTitle className="font-semibold">Insufficient Evidence</AlertTitle>
                  <AlertDescription>
                    The retrieved evidence was not sufficient to fully answer this question. The answer below only summarizes what could be supported.
                  </AlertDescription>
                </Alert>
              )}
              
              <div className="prose dark:prose-invert max-w-none">
                <p className="text-base leading-relaxed text-foreground/90 whitespace-pre-wrap font-serif bg-slate-50/50 dark:bg-slate-900/30 p-4 rounded-lg border border-slate-100 dark:border-slate-800">
                  {response.generation.answer}
                </p>
              </div>

              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 pt-4 border-t border-slate-100 dark:border-slate-800 text-xs text-muted-foreground">
                <div>
                  <span className="block font-medium text-foreground">Model</span>
                  <span>{response.generation.model_name}</span>
                </div>
                <div>
                  <span className="block font-medium text-foreground">Embedding Time</span>
                  <span>{response.retrieval.embedding_duration_ms.toFixed(1)} ms</span>
                </div>
                <div>
                  <span className="block font-medium text-foreground">Database Time</span>
                  <span>{response.retrieval.database_duration_ms.toFixed(1)} ms</span>
                </div>
                <div>
                  <span className="block font-medium text-foreground">Generation Time</span>
                  <span>{response.generation.generation_duration_ms.toFixed(1)} ms</span>
                </div>
              </div>
            </CardContent>
          </Card>

          <div className="space-y-4">
            <h2 className="text-xl font-bold tracking-tight">Top 10 Retrieved Chunks</h2>
            <div className="space-y-4">
              {response.retrieval.results.map((chunk) => {
                const citation = response.generation.citations.find(c => c.chunk_uid === chunk.chunk_uid);
                const isCited = !!citation;
                const citationReason = citation?.reason;
                return (
                  <LiveChunkCard 
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
      )}
    </div>
  );
}

function PipelineStep({ 
  label, 
  status, 
  detail, 
  isLast = false 
}: { 
  label: string; 
  status: "pending" | "processing" | "completed"; 
  detail: string; 
  isLast?: boolean; 
}) {
  return (
    <div className="flex-1 flex flex-col items-center p-4 border rounded-xl bg-slate-50/50 dark:bg-slate-900/50 text-center relative">
      <div className={`w-10 h-10 rounded-full flex items-center justify-center mb-3 transition-colors ${
        status === "completed" 
          ? "bg-green-100 text-green-700 dark:bg-green-950/50 dark:text-green-400" 
          : status === "processing"
          ? "bg-blue-100 text-blue-700 dark:bg-blue-950/50 dark:text-blue-400 animate-pulse"
          : "bg-slate-100 text-slate-400 dark:bg-slate-800 dark:text-slate-600"
      }`}>
        {status === "completed" ? (
          <CheckCircle2 className="h-5 w-5" />
        ) : status === "processing" ? (
          <Loader2 className="h-5 w-5 animate-spin" />
        ) : (
          <HelpCircle className="h-5 w-5" />
        )}
      </div>
      <h3 className="font-semibold text-sm mb-1">{label}</h3>
      <p className="text-xs text-muted-foreground font-mono">
        {detail}
      </p>
      {!isLast && (
        <div className="hidden md:block absolute -right-2 top-1/2 -translate-y-1/2 text-muted-foreground z-10">
          <ChevronRight className="h-4 w-4" />
        </div>
      )}
    </div>
  );
}

interface LiveChunkCardProps {
  chunk: LiveRetrievalResult;
  isCited: boolean;
  citationReason?: string;
}

function LiveChunkCard({ chunk, isCited, citationReason }: LiveChunkCardProps) {
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
              View Chunk Content
            </AccordionTrigger>
            <AccordionContent className="px-4 pb-4">
              <div className="space-y-4 pt-2">
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

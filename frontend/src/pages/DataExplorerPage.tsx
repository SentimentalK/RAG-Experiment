import { useState, useMemo, useEffect } from "react";
import { useSearchParams } from "react-router";
import { useBaselineEvaluation } from "@/hooks/use-baseline-evaluation";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { AlertCircle, BookOpen, Database, Search, Tags } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import AliasExplorerPage from "@/features/aliases/AliasExplorerPage";

export default function DataExplorerPage() {
  const { data, loading, error } = useBaselineEvaluation();
  const [params, setParams] = useSearchParams();
  const activeTab = params.get("tab") === "chunks" || params.get("tab") === "aliases" ? params.get("tab")! : "stories";

  function setActiveTab(value: string | null) {
    const next = new URLSearchParams(params);
    if (value && value !== "stories") next.set("tab", value);
    else next.delete("tab");
    setParams(next);
  }

  if (loading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-10 w-[300px]" />
        <Skeleton className="h-12 w-full max-w-[400px]" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <Alert variant="destructive">
        <AlertCircle className="h-4 w-4" />
        <AlertTitle>Error loading data</AlertTitle>
        <AlertDescription>{error?.message || "Data could not be loaded."}</AlertDescription>
      </Alert>
    );
  }

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full flex flex-col gap-6">
        <div className="flex items-center justify-between gap-4 border-b pb-4">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Data Explorer</h1>
            <p className="text-muted-foreground mt-1 text-sm">
              Browse the original stories and the extracted vector chunks.
            </p>
          </div>
          <TabsList className="shrink-0 flex items-center">
            <TabsTrigger value="stories" className="flex items-center gap-2">
              <BookOpen className="h-4 w-4" />
              Full Stories ({data.stories.length})
            </TabsTrigger>
            <TabsTrigger value="chunks" className="flex items-center gap-2">
              <Database className="h-4 w-4" />
              Cleaned Chunks ({data.chunks.length})
            </TabsTrigger>
            <TabsTrigger value="aliases" className="flex items-center gap-2">
              <Tags className="h-4 w-4" />
              Alias Explorer
            </TabsTrigger>
          </TabsList>
        </div>
        
        <TabsContent value="stories" className="mt-0 w-full">
          <StoriesTab stories={data.stories} />
        </TabsContent>
        
        <TabsContent value="chunks" className="mt-0 w-full">
          <ChunksTab chunks={data.chunks} />
        </TabsContent>

        <TabsContent value="aliases" className="mt-0 w-full">
          <AliasExplorerPage />
        </TabsContent>
      </Tabs>
    </div>
  );
}

function StoriesTab({ stories }: { stories: import("@/types/evaluation").Story[] }) {
  return (
    <div className="space-y-6">
      {stories.map((story) => (
        <Card key={story.section_order} className="border-slate-200 shadow-sm dark:border-slate-800">
          <CardHeader className="bg-slate-50/50 dark:bg-slate-900/50 border-b">
            <div className="flex items-center justify-between">
              <CardTitle className="text-xl">{story.section_title}</CardTitle>
              <Badge variant="secondary">Section {story.section_order}</Badge>
            </div>
            <CardDescription>
              {story.section_text.length} characters
            </CardDescription>
          </CardHeader>
          <CardContent className="p-0">
            <div className="p-6 max-h-[400px] overflow-y-auto">
              <p className="whitespace-pre-wrap font-serif text-sm leading-relaxed text-foreground/90">
                {story.section_text}
              </p>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

function ChunksTab({ chunks }: { chunks: import("@/types/evaluation").Chunk[] }) {
  const [searchTerm, setSearchTerm] = useState("");
  const [page, setPage] = useState(1);
  const CHUNKS_PER_PAGE = 20;

  const filteredChunks = useMemo(() => {
    if (!searchTerm.trim()) return chunks;
    const term = searchTerm.toLowerCase();
    return chunks.filter(c => 
      c.chunk_text.toLowerCase().includes(term) || 
      c.section_title.toLowerCase().includes(term)
    );
  }, [chunks, searchTerm]);

  const totalPages = Math.ceil(filteredChunks.length / CHUNKS_PER_PAGE);
  const paginatedChunks = filteredChunks.slice((page - 1) * CHUNKS_PER_PAGE, page * CHUNKS_PER_PAGE);

  // Reset page when search changes
  useEffect(() => {
    setPage(1);
  }, [searchTerm]);

  return (
    <div className="space-y-4">
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input 
          placeholder="Search chunks by text or story title..." 
          className="pl-9 bg-background"
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
        />
      </div>

      <div className="flex items-center justify-between text-sm text-muted-foreground">
        <span>Showing {paginatedChunks.length} of {filteredChunks.length} chunks</span>
        <div className="flex items-center gap-2">
          <Button 
            variant="outline" 
            size="sm" 
            onClick={() => setPage(p => Math.max(1, p - 1))}
            disabled={page === 1}
          >
            Previous
          </Button>
          <span className="min-w-[60px] text-center">Page {page} of {totalPages || 1}</span>
          <Button 
            variant="outline" 
            size="sm" 
            onClick={() => setPage(p => Math.min(totalPages, p + 1))}
            disabled={page === totalPages || totalPages === 0}
          >
            Next
          </Button>
        </div>
      </div>

      <div className="space-y-4">
        {paginatedChunks.length > 0 ? (
          paginatedChunks.map((chunk) => (
            <Card key={chunk.chunk_uid} className="border-slate-200 shadow-sm dark:border-slate-800">
              <CardHeader className="py-3 px-4 bg-slate-50/50 dark:bg-slate-900/50 border-b">
                <div className="flex items-center justify-between">
                  <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4">
                    <span className="font-semibold text-sm truncate max-w-[300px]" title={chunk.section_title}>
                      {chunk.section_title}
                    </span>
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                      <Badge variant="outline" className="font-mono bg-background">Chunk {chunk.chunk_order}</Badge>
                      <span>•</span>
                      <span>{chunk.token_count} tokens</span>
                    </div>
                  </div>
                  <span className="text-[10px] text-muted-foreground font-mono hidden sm:block">
                    {chunk.chunk_uid}
                  </span>
                </div>
              </CardHeader>
              <CardContent className="p-4">
                <p className="whitespace-pre-wrap font-serif text-sm leading-relaxed">
                  {chunk.chunk_text}
                </p>
              </CardContent>
            </Card>
          ))
        ) : (
          <div className="text-center py-12 border rounded-xl bg-slate-50 dark:bg-slate-900/50">
            <Database className="h-8 w-8 text-muted-foreground mx-auto mb-3" />
            <h3 className="text-lg font-medium">No chunks found</h3>
            <p className="text-sm text-muted-foreground mt-1">Try adjusting your search query</p>
          </div>
        )}
      </div>
      
      {totalPages > 1 && (
        <div className="flex justify-center mt-6">
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}>Previous</Button>
            <span className="text-sm text-muted-foreground mx-2">Page {page} of {totalPages}</span>
            <Button variant="outline" size="sm" onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages}>Next</Button>
          </div>
        </div>
      )}
    </div>
  );
}

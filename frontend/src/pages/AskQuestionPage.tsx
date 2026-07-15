import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Search, Sparkles } from "lucide-react";

export default function AskQuestionPage() {
  return (
    <div className="space-y-6 animate-in fade-in duration-500 max-w-4xl mx-auto mt-8">
      <div className="text-center space-y-2 mb-8">
        <h1 className="text-3xl font-bold tracking-tight">Ask Sherlock</h1>
        <p className="text-muted-foreground">
          Query the Holmes corpus using the configured retrieval pipeline.
        </p>
      </div>

      <Card className="border-slate-200 shadow-md dark:border-slate-800">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Search className="h-5 w-5 text-primary" />
            Your Question
          </CardTitle>
          <CardDescription>
            Enter a question about the Sherlock Holmes stories. (Coming Soon)
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <textarea 
            placeholder="e.g., What was the color of the ribbon in The Speckled Band?"
            className="flex min-h-[100px] w-full rounded-md border border-input bg-slate-50 dark:bg-slate-900/50 px-3 py-2 text-base ring-offset-background placeholder:text-muted-foreground focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 resize-none"
            disabled
          />
          <div className="flex justify-end">
            <Button disabled className="gap-2">
              <Sparkles className="h-4 w-4" />
              Generate Answer
            </Button>
          </div>
        </CardContent>
      </Card>

      <div className="mt-8 text-center p-8 border border-dashed rounded-xl bg-slate-50/50 dark:bg-slate-900/20 text-muted-foreground">
        <h3 className="font-medium text-foreground mb-2">Feature in Development</h3>
        <p className="text-sm max-w-md mx-auto">
          The interactive answering module will connect to the python backend to perform live embedding generation, vector search, and LLM synthesis.
        </p>
      </div>
    </div>
  );
}

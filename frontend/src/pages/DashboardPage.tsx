import { useBaselineEvaluation } from "@/hooks/use-baseline-evaluation";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { AlertCircle, Target, CheckCircle2, TrendingUp, Filter, HelpCircle, Database, Server } from "lucide-react";
import { CartesianGrid, Line, LineChart, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer, PieChart, Pie, Cell } from "recharts";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#8884d8'];

export default function DashboardPage() {
  const { data, loading, error } = useBaselineEvaluation();

  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-10 w-[300px]" />
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-32 w-full" />
          ))}
        </div>
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

  const { aggregate_metrics: metrics, pipeline, questions } = data;

  const qualityData = [
    { k: 'Top 1', DirectHit: metrics.direct_hit_rate_at_1 * 100, AnswerSufficiency: metrics.answer_sufficiency_rate_at_1 * 100 },
    { k: 'Top 3', DirectHit: metrics.direct_hit_rate_at_3 * 100, AnswerSufficiency: metrics.answer_sufficiency_rate_at_3 * 100 },
    { k: 'Top 5', DirectHit: metrics.direct_hit_rate_at_5 * 100, AnswerSufficiency: metrics.answer_sufficiency_rate_at_5 * 100 },
    { k: 'Top 10', DirectHit: metrics.direct_hit_rate_at_10 * 100, AnswerSufficiency: metrics.answer_sufficiency_rate_at_10 * 100 },
  ];

  const labelDistribution = Object.entries(metrics.label_totals).map(([name, value]) => ({
    name,
    value
  })).sort((a, b) => b.value - a.value);

  return (
    <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Sherlock Holmes Retrieval Baseline</h1>
          <p className="text-muted-foreground mt-2">
            Evaluating the Exact Cosine retrieval approach on {data.questions.length} baseline questions.
          </p>
        </div>
        <Badge variant="outline" className="px-4 py-1 text-sm bg-primary/10 text-primary border-primary/20">
          v1.0 Baseline
        </Badge>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
        <MetricCard title="Direct Hit Rate @1" value={(metrics.direct_hit_rate_at_1 * 100).toFixed(1) + "%"} icon={<Target className="h-4 w-4 text-primary" />} />
        <MetricCard title="Answer Sufficiency @3" value={(metrics.answer_sufficiency_rate_at_3 * 100).toFixed(1) + "%"} icon={<CheckCircle2 className="h-4 w-4 text-green-500" />} />
        <MetricCard title="Mean Reciprocal Rank" value={metrics.mrr.toFixed(3)} icon={<TrendingUp className="h-4 w-4 text-blue-500" />} />
        <MetricCard title="Avg Noise @10" value={formatPercent(metrics.average_noise_rate_at_10)} icon={<Filter className="h-4 w-4 text-orange-500" />} />
        <MetricCard title="Total Questions" value={data.questions.length.toString()} icon={<HelpCircle className="h-4 w-4 text-purple-500" />} />
        <MetricCard title="Total Chunks" value={data.chunks.length.toString()} icon={<Database className="h-4 w-4 text-indigo-500" />} />
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-7">
        <Card className="col-span-4 border-slate-200 shadow-sm dark:border-slate-800">
          <CardHeader>
            <CardTitle>Retrieval Quality by K</CardTitle>
            <CardDescription>Direct hit rate and answer sufficiency rate at different K values.</CardDescription>
          </CardHeader>
          <CardContent className="h-[300px]">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={qualityData} margin={{ top: 20, right: 30, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="hsl(var(--border))" />
                <XAxis dataKey="k" axisLine={false} tickLine={false} tick={{fill: 'hsl(var(--muted-foreground))'}} />
                <YAxis axisLine={false} tickLine={false} tickFormatter={(v) => `${v}%`} tick={{fill: 'hsl(var(--muted-foreground))'}} />
                <Tooltip 
                  formatter={(value: any) => [`${Number(value).toFixed(1)}%`, undefined]}
                  contentStyle={{ borderRadius: '8px', border: '1px solid hsl(var(--border))' }}
                />
                <Legend iconType="circle" wrapperStyle={{ paddingTop: '20px' }} />
                <Line type="monotone" dataKey="DirectHit" name="Direct Hit Rate" stroke="hsl(var(--primary))" strokeWidth={3} dot={{ r: 4, strokeWidth: 2 }} activeDot={{ r: 6 }} />
                <Line type="monotone" dataKey="AnswerSufficiency" name="Answer Sufficiency" stroke="#10b981" strokeWidth={3} dot={{ r: 4, strokeWidth: 2 }} activeDot={{ r: 6 }} />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card className="col-span-3 border-slate-200 shadow-sm dark:border-slate-800">
          <CardHeader>
            <CardTitle>Label Distribution (Top 10)</CardTitle>
            <CardDescription>Distribution of judgments across all retrieved chunks.</CardDescription>
          </CardHeader>
          <CardContent className="h-[300px] flex items-center justify-center">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={labelDistribution}
                  cx="50%"
                  cy="50%"
                  innerRadius={60}
                  outerRadius={80}
                  paddingAngle={5}
                  dataKey="value"
                >
                  {labelDistribution.map((_, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip 
                  formatter={(value: any, name: any) => [value, name]}
                  contentStyle={{ borderRadius: '8px', border: '1px solid hsl(var(--border))' }}
                />
                <Legend iconType="circle" layout="vertical" verticalAlign="middle" align="right" />
              </PieChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>

      <Card className="border-slate-200 shadow-sm dark:border-slate-800">
        <CardHeader>
          <CardTitle>Pipeline Steps</CardTitle>
          <CardDescription>The sequence of operations used to generate this baseline.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col space-y-4 lg:flex-row lg:space-x-4 lg:space-y-0">
            {pipeline.steps.map((step, idx) => (
              <div key={step.step_id} className="flex-1 flex flex-col items-center p-4 border rounded-xl bg-slate-50/50 dark:bg-slate-900/50 text-center relative">
                <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center mb-3">
                  <Server className="h-5 w-5 text-primary" />
                </div>
                <h3 className="font-semibold text-sm mb-1">{step.name}</h3>
                <p className="text-xs text-muted-foreground flex-1">
                  {step.status === "completed" && step.model_name && `Model: ${step.model_name}`}
                  {step.status === "completed" && step.chunk_count && `${step.chunk_count} Chunks`}
                  {step.status === "completed" && step.question_count && `${step.question_count} Questions`}
                </p>
                {idx < pipeline.steps.length - 1 && (
                  <div className="hidden lg:block absolute -right-2 top-1/2 -translate-y-1/2 text-muted-foreground">
                    →
                  </div>
                )}
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card className="border-slate-200 shadow-sm dark:border-slate-800">
        <CardHeader>
          <CardTitle>Question Summary</CardTitle>
          <CardDescription>Overview of metrics for each of the {questions.length} questions.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="rounded-md border overflow-hidden">
            <Table>
              <TableHeader className="bg-slate-50 dark:bg-slate-900/50">
                <TableRow>
                  <TableHead className="w-[80px]">ID</TableHead>
                  <TableHead className="w-[120px]">Category</TableHead>
                  <TableHead>Question</TableHead>
                  <TableHead className="text-right w-[100px]">Hit @1</TableHead>
                  <TableHead className="text-right w-[100px]">RR</TableHead>
                  <TableHead className="text-right w-[100px]">Noise @10</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {questions.map((q) => (
                  <TableRow key={q.question_id} className="hover:bg-slate-50/50 dark:hover:bg-slate-900/50 transition-colors">
                    <TableCell className="font-medium">{q.question_id}</TableCell>
                    <TableCell>
                      <Badge variant="outline" className="font-normal capitalize">{q.category.replace('_', ' ')}</Badge>
                    </TableCell>
                    <TableCell className="max-w-md truncate" title={q.question}>{q.question}</TableCell>
                    <TableCell className="text-right">
                      {q.computed_metrics.direct_hit_at_1 === 1 ? (
                        <CheckCircle2 className="h-4 w-4 text-green-500 inline" />
                      ) : (
                        <span className="text-muted-foreground">-</span>
                      )}
                    </TableCell>
                    <TableCell className="text-right">{q.computed_metrics.reciprocal_rank.toFixed(2)}</TableCell>
                    <TableCell className="text-right">{formatPercent(q.computed_metrics.noise_rate_at_10, 0)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function MetricCard({ title, value, icon }: { title: string, value: string, icon: React.ReactNode }) {
  return (
    <Card className="border-slate-200 shadow-sm dark:border-slate-800">
      <CardContent className="p-4 flex flex-col items-center justify-center text-center h-full gap-2">
        <div className="p-2 rounded-full bg-slate-100 dark:bg-slate-800">
          {icon}
        </div>
        <p className="text-xs font-medium text-muted-foreground line-clamp-1">{title}</p>
        <h3 className="text-2xl font-bold tracking-tight">{value}</h3>
      </CardContent>
    </Card>
  );
}

function formatPercent(value: number | null | undefined, digits = 1): string {
  if (value == null || !Number.isFinite(value)) return "n/a";
  return `${(value * 100).toFixed(digits)}%`;
}

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function EvaluationUnavailablePage() {
  return (
    <div className="mx-auto max-w-3xl">
      <Card>
        <CardHeader>
          <CardTitle>Evaluation Catalog</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            Evaluation catalog APIs are unavailable in this environment. Offline Phase 4 artifacts remain outside the interactive workbench.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}

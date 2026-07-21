import { Link } from "react-router";
import { FlaskConical, History } from "lucide-react";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";

export function ExperimentNav({ active }: { active: "workbench" | "history" }) {
  return (
    <Tabs value={active} className="w-auto">
      <TabsList className="shrink-0">
        <TabsTrigger value="workbench" render={<Link to="/experiments" />} className="flex items-center gap-2">
          <FlaskConical className="h-4 w-4" />
          Experiment Workbench
        </TabsTrigger>
        <TabsTrigger value="history" render={<Link to="/experiments/sessions" />} className="flex items-center gap-2">
          <History className="h-4 w-4" />
          History
        </TabsTrigger>
      </TabsList>
    </Tabs>
  );
}

import { 
  Sidebar, 
  SidebarContent, 
  SidebarFooter, 
  SidebarGroup, 
  SidebarGroupContent, 
  SidebarGroupLabel, 
  SidebarHeader, 
  SidebarMenu, 
  SidebarMenuButton, 
  SidebarMenuItem 
} from "@/components/ui/sidebar";
import { useBaselineEvaluation } from "@/hooks/use-baseline-evaluation";
import { LayoutDashboard, CheckSquare, Database, MessageSquare, FlaskConical, History, BarChart3 } from "lucide-react";
import { Link, useLocation } from "react-router";
import { Badge } from "@/components/ui/badge";
import { useEffect, useState } from "react";
import { getExperimentCapabilities } from "@/features/experiments/api";

export function AppSidebar() {
  const { data } = useBaselineEvaluation();
  const location = useLocation();
  const [evaluationAvailable, setEvaluationAvailable] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    getExperimentCapabilities(controller.signal)
      .then((capabilities) => setEvaluationAvailable(capabilities.evaluation_catalog_available))
      .catch(() => setEvaluationAvailable(false));
    return () => controller.abort();
  }, []);

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader className="p-4 pt-6">
        <h2 className="text-lg font-bold tracking-tight text-foreground truncate group-data-[collapsible=icon]:hidden">
          Sherlock Retrieval
        </h2>
      </SidebarHeader>
      
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>Navigation</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              <SidebarMenuItem>
                <SidebarMenuButton render={<Link to="/" />} tooltip="Dashboard" isActive={location.pathname === "/"}>
                  <LayoutDashboard className="h-4 w-4" />
                  <span>Dashboard</span>
                </SidebarMenuButton>
              </SidebarMenuItem>
              
              <SidebarMenuItem>
                <SidebarMenuButton render={<Link to="/baseline/q001" />} tooltip="Baseline Evaluation" isActive={location.pathname.startsWith("/baseline")}>
                  <CheckSquare className="h-4 w-4" />
                  <span>Baseline Evaluation</span>
                </SidebarMenuButton>
              </SidebarMenuItem>
              
              <SidebarMenuItem>
                <SidebarMenuButton render={<Link to="/data" />} tooltip="Data Explorer" isActive={location.pathname.startsWith("/data") || location.pathname.startsWith("/aliases")}>
                  <Database className="h-4 w-4" />
                  <span>Data Explorer</span>
                </SidebarMenuButton>
              </SidebarMenuItem>
              
              <SidebarMenuItem>
                <SidebarMenuButton render={<Link to="/ask" />} tooltip="Ask a Question" isActive={location.pathname.startsWith("/ask")}>
                  <MessageSquare className="h-4 w-4" />
                  <span className="flex-1">Ask a Question</span>
                  <Badge variant="outline" className="text-[10px] uppercase font-bold py-0 h-4 bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400 border-green-200 dark:border-green-800">Live</Badge>
                </SidebarMenuButton>
              </SidebarMenuItem>

              <SidebarMenuItem>
                <SidebarMenuButton render={<Link to="/experiments/compare" />} tooltip="Experiment Workbench" isActive={location.pathname.startsWith("/experiments/compare")}>
                  <FlaskConical className="h-4 w-4" />
                  <span>Experiment Workbench</span>
                </SidebarMenuButton>
              </SidebarMenuItem>

              <SidebarMenuItem>
                <SidebarMenuButton render={<Link to="/experiments/sessions" />} tooltip="Experiment Sessions" isActive={location.pathname.startsWith("/experiments/sessions") || location.pathname.startsWith("/experiments/mode-runs")}>
                  <History className="h-4 w-4" />
                  <span>Experiment Sessions</span>
                </SidebarMenuButton>
              </SidebarMenuItem>

              {evaluationAvailable && (
                <SidebarMenuItem>
                  <SidebarMenuButton render={<Link to="/evaluation" />} tooltip="Evaluation" isActive={location.pathname.startsWith("/evaluation")}>
                    <BarChart3 className="h-4 w-4" />
                    <span>Evaluation</span>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              )}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      <SidebarFooter className="p-4 border-t group-data-[collapsible=icon]:hidden">
        {data ? (
          <div className="space-y-3 text-xs text-muted-foreground">
            <div>
              <p className="font-semibold text-foreground">Experiment</p>
              <p>{data.experiment.experiment_id}</p>
            </div>
            <div>
              <p className="font-semibold text-foreground">Model</p>
              <p>all-MiniLM-L6-v2</p>
            </div>
            <div>
              <p className="font-semibold text-foreground">Mode</p>
              <p>Exact Cosine</p>
            </div>
          </div>
        ) : (
          <div className="h-24" />
        )}
      </SidebarFooter>
    </Sidebar>
  );
}

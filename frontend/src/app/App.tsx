import { BrowserRouter, Navigate, Routes, Route } from "react-router";
import { BaselineProvider } from "../contexts/BaselineContext";
import DashboardLayout from "../layouts/DashboardLayout";
import DashboardPage from "../pages/DashboardPage";
import BaselineQuestionPage from "../pages/BaselineQuestionPage";
import DataExplorerPage from "../pages/DataExplorerPage";
import AskQuestionPage from "../pages/AskQuestionPage";
import ExperimentComparePage from "../features/experiments/ComparePage";
import ExperimentSessionsPage from "../features/experiments/SessionsPage";
import ExperimentSessionDetailPage from "../features/experiments/SessionDetailPage";
import ExperimentModeRunDetailPage from "../features/experiments/ModeRunDetailPage";
import AliasGroupDetailPage from "../features/aliases/AliasGroupDetailPage";
import EvaluationUnavailablePage from "../features/experiments/EvaluationUnavailablePage";

function App() {
  return (
    <BaselineProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<DashboardLayout />}>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/baseline/:questionId" element={<BaselineQuestionPage />} />
            <Route path="/data" element={<DataExplorerPage />} />
            <Route path="/data/aliases/groups/:groupId" element={<AliasGroupDetailPage />} />
            <Route path="/ask" element={<AskQuestionPage />} />
            <Route path="/experiments" element={<ExperimentComparePage />} />
            <Route path="/experiments/compare" element={<Navigate to="/experiments" replace />} />
            <Route path="/experiments/sessions" element={<ExperimentSessionsPage />} />
            <Route path="/experiments/sessions/:sessionId" element={<ExperimentSessionDetailPage />} />
            <Route path="/experiments/mode-runs/:modeRunId" element={<ExperimentModeRunDetailPage />} />
            <Route path="/aliases" element={<Navigate to="/data?tab=aliases" replace />} />
            <Route path="/aliases/groups/:groupId" element={<AliasGroupDetailPage />} />
            <Route path="/evaluation" element={<EvaluationUnavailablePage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </BaselineProvider>
  );
}

export default App;

import { BrowserRouter, Routes, Route } from "react-router";
import { BaselineProvider } from "../contexts/BaselineContext";
import DashboardLayout from "../layouts/DashboardLayout";
import DashboardPage from "../pages/DashboardPage";
import BaselineQuestionPage from "../pages/BaselineQuestionPage";
import DataExplorerPage from "../pages/DataExplorerPage";
import AskQuestionPage from "../pages/AskQuestionPage";

function App() {
  return (
    <BaselineProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<DashboardLayout />}>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/baseline/:questionId" element={<BaselineQuestionPage />} />
            <Route path="/data" element={<DataExplorerPage />} />
            <Route path="/ask" element={<AskQuestionPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </BaselineProvider>
  );
}

export default App;

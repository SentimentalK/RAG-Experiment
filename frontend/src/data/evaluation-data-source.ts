import type { BaselineEvaluation } from "../types/evaluation";

export interface EvaluationDataSource {
  loadBaseline(): Promise<BaselineEvaluation>;
}

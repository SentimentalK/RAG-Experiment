import type { BaselineEvaluation } from "../types/evaluation";
import type { EvaluationDataSource } from "./evaluation-data-source";

export class StaticEvaluationDataSource implements EvaluationDataSource {
  async loadBaseline(): Promise<BaselineEvaluation> {
    const response = await fetch("/data/baseline_evaluation.json");

    if (!response.ok) {
      throw new Error(`Unable to load baseline evaluation data: ${response.statusText}`);
    }

    return response.json();
  }
}

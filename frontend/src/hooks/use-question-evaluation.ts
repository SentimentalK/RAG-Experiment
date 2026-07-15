import { useBaselineEvaluation } from "../contexts/BaselineContext";

export const useQuestionEvaluation = (questionId: string) => {
  const { data, loading, error } = useBaselineEvaluation();

  if (loading || error || !data) {
    return { question: null, loading, error };
  }

  const question = data.questions.find((q) => q.question_id === questionId);

  return {
    question: question || null,
    loading,
    error: question ? null : new Error(`Question ${questionId} not found`),
  };
};

import type { LiveRagAnswerResponse } from "@/types/evaluation";

export async function askQuestion(
  question: string,
  signal?: AbortSignal,
): Promise<LiveRagAnswerResponse> {
  const response = await fetch("/api/rag/answer", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      question,
      document_id: "gutenberg-1661",
      top_k: 10,
    }),
    signal,
  });

  const payload = await response.json().catch(() => null);

  if (!response.ok) {
    let message = "";
    if (response.status === 422) {
      message = "Invalid input format. Please check your question.";
    } else if (response.status === 429) {
      message = "Groq API rate limit exceeded. Please wait a moment and try again.";
    } else if (response.status === 502) {
      message = "Upstream LLM error. The model output was invalid or the Groq API failed.";
    } else if (response.status === 503) {
      message = "Retrieval service or database is not ready. Please ensure the database is loaded and try again.";
    } else if (response.status === 504) {
      message = "Groq request timed out. Please try again.";
    } else {
      message = payload?.detail ?? `Request failed with status ${response.status}.`;
    }

    throw new Error(message);
  }

  return payload as LiveRagAnswerResponse;
}

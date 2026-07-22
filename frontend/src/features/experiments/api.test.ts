import { afterEach, describe, expect, it, vi } from "vitest";

import { compareExperiment } from "./api";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("experiment api headers", () => {
  it("forwards an optional session Groq API key on compare requests", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          session_id: null,
          persisted: false,
          query: "Question?",
          status: "completed",
          results: {},
          comparisons: [],
          requested_mode_count: 1,
          retrieval_execution_count: 1,
          answer_generation_count: 1,
          total_vector_search_call_count: 2,
          warnings: [],
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );

    await compareExperiment(
      {
        query: "Question?",
        modes: ["strong_story"],
        persist: false,
      },
      undefined,
      "xx",
      "session-groq-key",
    );

    const init = fetchSpy.mock.calls[0]?.[1];
    const headers = new Headers(init?.headers);
    expect(headers.get("X-Experiment-Admin-Secret")).toBe("xx");
    expect(headers.get("X-Experiment-Groq-Api-Key")).toBe("session-groq-key");
  });
});

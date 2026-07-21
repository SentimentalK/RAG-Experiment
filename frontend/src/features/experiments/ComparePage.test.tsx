import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import ExperimentComparePage from "./ComparePage";
import { normalizeModeRunDetail } from "./adapters";
import type { ExperimentModeResult } from "./types";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("ExperimentComparePage", () => {
  it("keeps story controls enabled when Strong + Story is selected alongside Strong Only", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          available_modes: ["baseline", "strong_only", "strong_story"],
          persistence: { enabled: true, required: false },
          expansion: {
            enabled: true,
            max_query_variants: 8,
            allow_story_scoped: true,
            allow_story_scoped_single_token: true,
          },
          trace_persistence_enabled: true,
          evaluation_catalog_available: false,
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );

    render(
      <MemoryRouter>
        <ExperimentComparePage />
      </MemoryRouter>,
    );

    await waitFor(() => expect(screen.getByText("Compare Modes")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Advanced Options"));

    const storyControl = screen.getByLabelText("Allow story-scoped aliases");
    expect(storyControl).toBeEnabled();
    expect(screen.getByLabelText("Save experiment")).toBeChecked();
  });
});

describe("normalizeModeRunDetail", () => {
  it("keeps overview usable for unsupported trace schema versions", () => {
    const result = {
      mode: "strong_story",
      mode_run_id: "run-1",
      status: "completed",
      answer: "Answer [1].",
      evidence_sufficient: true,
      citations: [],
      confidence: 0.8,
      contexts: [],
      context_chunk_uids: [],
      context_snapshot_sha256: null,
      prompt_template_sha256: null,
      rendered_prompt_sha256: null,
      retrieval_summary: {
        retrieval_reason: "alias_expanded_retrieval",
        generated_variant_count: 1,
        vector_search_call_count: 1,
        final_context_count: 0,
        retrieval_executed: true,
        retrieval_source_mode: null,
        retrieval_reused: false,
        variant_statuses: [],
      },
      timing: { retrieval_duration_ms: null, generation_duration_ms: null, total_duration_ms: null },
      trace: { trace_schema_version: "99" },
      warnings: [],
      error_code: null,
      error_message: null,
    } satisfies ExperimentModeResult;

    const view = normalizeModeRunDetail(result);

    expect(view.unsupportedTraceSchema).toBe(true);
    expect(view.label).toBe("Strong + Story");
  });
});

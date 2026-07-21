import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import AliasExplorerPage from "./AliasExplorerPage";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("AliasExplorerPage", () => {
  it("renders backend alias status fields without crashing", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const url = String(input);
      if (url.startsWith("/api/aliases/status")) {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              loaded: true,
              file_name: "sherlock_entity_alias_groups_final.json",
              sha256: "2b16f62f2537c0703985585a8e467cda14d0790a3fad3258c31439322cfd5dd7",
              expected_sha256: "2b16f62f2537c0703985585a8e467cda14d0790a3fad3258c31439322cfd5dd7",
              strict_validation: true,
              approved_group_count: 87,
              approved_strong_group_count: 5,
              approved_story_scoped_group_count: 82,
              generatable_member_count: 226,
              normalization_only_member_count: 13,
              final_disposition_count: 359,
              validation_warning_count: 40,
              loaded_at: "2026-07-21T21:55:09.584470Z",
            }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        );
      }
      return Promise.resolve(
        new Response(
          JSON.stringify({
            total: 1,
            limit: 50,
            offset: 0,
            groups: [
              {
                group_id: "entity-sherlock-holmes",
                canonical_name: "Sherlock Holmes",
                canonical_name_is_generatable: true,
                entity_type: "PERSON",
                scope: "global",
                story_ids: [],
                approval_status: "approved_strong",
                group_confidence: "high",
                safe_for_query_substitution: true,
                member_count: 2,
                generatable_member_count: 2,
                normalization_only_member_count: 0,
              },
            ],
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      );
    });

    render(
      <MemoryRouter>
        <AliasExplorerPage />
      </MemoryRouter>,
    );

    await waitFor(() => expect(screen.getByText("sherlock_entity_alias_groups_final.json")).toBeInTheDocument());
    expect(screen.getByText("87")).toBeInTheDocument();
    expect(screen.getByText("2b16f62f2537")).toBeInTheDocument();
    expect(screen.getByText("Sherlock Holmes")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Name/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Members/i })).toBeInTheDocument();
    expect(screen.getByText("Showing 1-1 of 1")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Previous" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
  });
});

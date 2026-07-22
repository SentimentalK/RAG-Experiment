import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import AliasGroupDetailPage from "./AliasGroupDetailPage";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("AliasGroupDetailPage", () => {
  it("keeps alias explorer filters in the back link", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          group_id: "entity-sherlock-holmes",
          canonical_name: "Sherlock Holmes",
          canonical_name_is_generatable: true,
          entity_type: "PERSON",
          scope: "global",
          story_ids: [],
          approval_status: "approved_strong",
          group_confidence: "high",
          safe_for_query_substitution: true,
          member_count: 1,
          generatable_member_count: 1,
          normalization_only_member_count: 0,
          group_review_reason: null,
          curation: {
            source: "implicit_default",
            review_status: "pending",
            retrieval_value: null,
            showcase: false,
            showcase_rank: null,
            pattern_tags: [],
            review_note: "",
            recommended_pairs: [],
            example_questions: [],
          },
          members: [],
          generatable_members: [],
          normalization_only_members: [],
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );

    render(
      <MemoryRouter initialEntries={["/data/aliases/groups/entity-sherlock-holmes?tab=aliases&scope=global&showcase_only=true"]}>
        <Routes>
          <Route path="/data/aliases/groups/:groupId" element={<AliasGroupDetailPage />} />
        </Routes>
      </MemoryRouter>,
    );

    await waitFor(() => expect(screen.getByText("Sherlock Holmes")).toBeInTheDocument());
    expect(screen.getByRole("link", { name: /Alias Explorer/i })).toHaveAttribute(
      "href",
      "/data?tab=aliases&scope=global&showcase_only=true",
    );
  });
});

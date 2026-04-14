import { render, screen } from "@testing-library/react";
import type { Deployment } from "../types";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

jest.mock(
  "@/components/common/genericIconComponent",
  () =>
    function MockIcon({ name }: { name: string }) {
      return <span data-testid={`icon-${name}`} />;
    },
);

import DeploymentInfoGrid from "../components/deployment-details-modal/deployment-info-grid";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const makeDeployment = (overrides: Partial<Deployment> = {}): Deployment => ({
  id: "dep-1",
  provider_id: "prov-1",
  name: "My Agent",
  description: "A sales agent",
  type: "agent",
  created_at: "2025-05-01T00:00:00Z",
  updated_at: "2025-06-10T00:00:00Z",
  provider_data: {},
  resource_key: "rk-1",
  attached_count: 2,
  ...overrides,
});

function renderGrid(
  deployment: Deployment | null = makeDeployment(),
  providerName = "watsonx Prod",
  llm = "",
) {
  return render(
    <DeploymentInfoGrid
      deployment={deployment}
      providerName={providerName}
      llm={llm}
    />,
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("DeploymentInfoGrid", () => {
  describe("date formatting", () => {
    it("formats ISO date strings to a localized date", () => {
      const iso = "2025-05-15T12:00:00Z";
      renderGrid(makeDeployment({ created_at: iso }));
      // formatDate uses toLocaleDateString({ year: "numeric", month: "short", day: "numeric" })
      const expected = new Date(iso).toLocaleDateString(undefined, {
        year: "numeric",
        month: "short",
        day: "numeric",
      });
      expect(screen.getByText(expected)).toBeInTheDocument();
    });

    it('shows "—" when created_at is falsy (null deployment)', () => {
      renderGrid(null);
      // With null deployment, both Created and Modified should show "—"
      const dashes = screen.getAllByText("—");
      expect(dashes.length).toBeGreaterThanOrEqual(2);
    });
  });

  describe("description", () => {
    it("renders the description when present", () => {
      renderGrid(makeDeployment({ description: "A helpful bot" }));
      expect(screen.getByText("A helpful bot")).toBeInTheDocument();
      expect(screen.getByText("Desc")).toBeInTheDocument();
    });

    it("omits the description row when description is undefined", () => {
      renderGrid(makeDeployment({ description: undefined }));
      expect(screen.queryByText("Desc")).not.toBeInTheDocument();
    });

    it("omits the description row when description is empty string (falsy)", () => {
      renderGrid(makeDeployment({ description: "" }));
      expect(screen.queryByText("Desc")).not.toBeInTheDocument();
    });
  });

  describe("LLM model", () => {
    it("renders the model name when llm prop is provided", () => {
      renderGrid(makeDeployment(), "watsonx Prod", "granite-13b-chat");
      expect(screen.getByText("granite-13b-chat")).toBeInTheDocument();
      expect(screen.getByText("Model")).toBeInTheDocument();
    });

    it("omits the Model row when llm is empty", () => {
      renderGrid(makeDeployment(), "watsonx Prod", "");
      expect(screen.queryByText("Model")).not.toBeInTheDocument();
    });
  });
});

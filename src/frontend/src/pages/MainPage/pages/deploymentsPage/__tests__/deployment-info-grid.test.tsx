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
  provider_data: { display_name: "My Agent", name: "my_agent" },
  description: "A sales agent",
  type: "agent",
  created_at: "2025-05-01T00:00:00Z",
  updated_at: "2025-06-10T00:00:00Z",
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
  it("renders environment label and selected environment name", () => {
    renderGrid(makeDeployment(), "Production");
    expect(screen.getByText("Environment")).toBeInTheDocument();
    expect(screen.getByText("Production")).toBeInTheDocument();
  });

  it("renders display name and technical name without exposing the short ID", () => {
    renderGrid(makeDeployment());
    expect(screen.getByText("Name")).toBeInTheDocument();
    expect(screen.getByText("My Agent")).toBeInTheDocument();
    expect(screen.getByText("Technical Name")).toBeInTheDocument();
    expect(screen.getByText("my_agent")).toBeInTheDocument();
    expect(screen.queryByText("Display Name")).not.toBeInTheDocument();
    expect(screen.queryByText("ID")).not.toBeInTheDocument();
  });

  it("falls back to resource key when provider data is missing", () => {
    renderGrid(
      makeDeployment({ provider_data: null, resource_key: "agent-1" }),
    );

    expect(screen.getAllByText("agent-1")).toHaveLength(2);
  });

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

    it("keeps long descriptions in the value columns", () => {
      const longDescription =
        "Langflow deployment OK AGENT 5 more words that should wrap inside the description value column";
      renderGrid(
        makeDeployment({ description: longDescription }),
        "prod-dl",
        "groq/openai/gpt-oss-120b",
      );

      expect(screen.getByText(longDescription)).toHaveClass(
        "col-span-3",
        "break-words",
      );
      expect(screen.getByText("Model")).toBeInTheDocument();
      expect(screen.getByText("Environment")).toBeInTheDocument();
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

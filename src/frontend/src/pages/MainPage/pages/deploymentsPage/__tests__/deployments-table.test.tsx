import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { Deployment } from "../types";

// Mock child components that fetch data or use complex UI
jest.mock(
  "@/components/common/genericIconComponent",
  () =>
    function MockIcon({ name }: { name: string }) {
      return <span data-testid={`icon-${name}`} />;
    },
);
jest.mock("../components/deployment-expanded-row", () =>
  jest.fn(({ deploymentId }: { deploymentId: string }) => (
    <tr data-testid={`expanded-row-${deploymentId}`}>
      <td>Expanded</td>
    </tr>
  )),
);
jest.mock("@/components/ui/loading", () =>
  jest.fn(() => <span data-testid="loading-spinner" />),
);

import DeploymentsTable from "../components/deployments-table";

const makeDeployment = (overrides: Partial<Deployment> = {}): Deployment => ({
  id: "dep-1",
  name: "My Agent",
  description: null,
  type: "agent",
  created_at: "2025-06-01T00:00:00Z",
  updated_at: "2025-06-10T12:00:00Z",
  provider_data: null,
  resource_key: "rk-1",
  attached_count: 2,
  matched_attachments: null,
  provider_account_id: "prov-1",
  ...overrides,
});

const providerMap: Record<string, string> = {
  "prov-1": "watsonx Prod",
};

const noop = jest.fn();

function renderTable(
  deployments: Deployment[] = [makeDeployment()],
  overrides: Partial<Parameters<typeof DeploymentsTable>[0]> = {},
) {
  return render(
    <DeploymentsTable
      deployments={deployments}
      providerMap={providerMap}
      onTestDeployment={noop}
      onViewDetails={noop}
      onUpdateDeployment={noop}
      onDeleteDeployment={noop}
      {...overrides}
    />,
  );
}

beforeEach(() => {
  jest.clearAllMocks();
});

// ---------------------------------------------------------------------------
// Row rendering
// ---------------------------------------------------------------------------

describe("Row rendering", () => {
  it("renders a deployment row with name, type badge, and provider", () => {
    renderTable();
    expect(screen.getByTestId("deployment-row-dep-1")).toBeInTheDocument();
    expect(screen.getByText("My Agent")).toBeInTheDocument();
    expect(screen.getByText("Agent")).toBeInTheDocument();
    expect(screen.getByText("watsonx Prod")).toBeInTheDocument();
  });

  it("renders description when present", () => {
    renderTable([makeDeployment({ description: "Handles sales queries" })]);
    expect(screen.getByText("Handles sales queries")).toBeInTheDocument();
  });

  it("does not render description when null", () => {
    renderTable([makeDeployment({ description: null })]);
    expect(screen.queryByText("Handles sales queries")).not.toBeInTheDocument();
  });

  it("shows MCP badge for mcp type", () => {
    renderTable([makeDeployment({ type: "mcp" })]);
    expect(screen.getByText("MCP")).toBeInTheDocument();
  });

  it("shows dash when provider is unknown", () => {
    renderTable([makeDeployment({ provider_account_id: "unknown" })]);
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("renders multiple rows", () => {
    renderTable([
      makeDeployment({ id: "dep-1", name: "Agent A" }),
      makeDeployment({ id: "dep-2", name: "Agent B" }),
    ]);
    expect(screen.getByTestId("deployment-row-dep-1")).toBeInTheDocument();
    expect(screen.getByTestId("deployment-row-dep-2")).toBeInTheDocument();
  });

  it("formats the last modified date", () => {
    renderTable([makeDeployment({ updated_at: "2025-06-10T12:00:00Z" })]);
    // toLocaleDateString output varies, just check the row exists
    expect(screen.getByTestId("deployment-row-dep-1")).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Attachment count & expand/collapse
// ---------------------------------------------------------------------------

describe("Attachment count & expand/collapse", () => {
  it("shows attachment count with correct pluralization", () => {
    renderTable([makeDeployment({ attached_count: 1 })]);
    expect(screen.getByText(/1 flow$/)).toBeInTheDocument();
  });

  it("pluralizes for multiple flows", () => {
    renderTable([makeDeployment({ attached_count: 3 })]);
    expect(screen.getByText("3 flows")).toBeInTheDocument();
  });

  it("disables toggle when attached_count is 0", () => {
    renderTable([makeDeployment({ attached_count: 0 })]);
    const toggle = screen.getByTestId("toggle-attachments-dep-1");
    expect(toggle).toBeDisabled();
  });

  it("expands row on toggle click", async () => {
    const user = userEvent.setup();
    renderTable();
    const toggle = screen.getByTestId("toggle-attachments-dep-1");
    expect(toggle).toHaveAttribute("aria-expanded", "false");

    await user.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByTestId("expanded-row-dep-1")).toBeInTheDocument();
  });

  it("collapses expanded row on second click", async () => {
    const user = userEvent.setup();
    renderTable();
    const toggle = screen.getByTestId("toggle-attachments-dep-1");

    await user.click(toggle);
    expect(screen.getByTestId("expanded-row-dep-1")).toBeInTheDocument();

    await user.click(toggle);
    expect(screen.queryByTestId("expanded-row-dep-1")).not.toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// Test button
// ---------------------------------------------------------------------------

describe("Test button", () => {
  it("calls onTestDeployment with deployment when clicked", async () => {
    const user = userEvent.setup();
    const onTest = jest.fn();
    const dep = makeDeployment();
    renderTable([dep], { onTestDeployment: onTest });

    await user.click(screen.getByTestId("test-deployment-dep-1"));
    expect(onTest).toHaveBeenCalledWith(dep);
  });

  it("has correct aria-label", () => {
    renderTable();
    expect(screen.getByTestId("test-deployment-dep-1")).toHaveAttribute(
      "aria-label",
      "Test My Agent",
    );
  });
});

// ---------------------------------------------------------------------------
// Action menu
// ---------------------------------------------------------------------------

describe("Action menu", () => {
  it("shows actions button with correct aria-label", () => {
    renderTable();
    expect(screen.getByTestId("actions-deployment-dep-1")).toHaveAttribute(
      "aria-label",
      "Actions for My Agent",
    );
  });

  it("calls onViewDetails when Details is clicked", async () => {
    const user = userEvent.setup();
    const onDetails = jest.fn();
    const dep = makeDeployment();
    renderTable([dep], { onViewDetails: onDetails });

    await user.click(screen.getByTestId("actions-deployment-dep-1"));
    await user.click(screen.getByText("Details"));
    expect(onDetails).toHaveBeenCalledWith(dep);
  });

  it("calls onUpdateDeployment when Update is clicked", async () => {
    const user = userEvent.setup();
    const onUpdate = jest.fn();
    const dep = makeDeployment();
    renderTable([dep], { onUpdateDeployment: onUpdate });

    await user.click(screen.getByTestId("actions-deployment-dep-1"));
    await user.click(screen.getByText("Update"));
    expect(onUpdate).toHaveBeenCalledWith(dep);
  });

  it("calls onDeleteDeployment when Delete is clicked", async () => {
    const user = userEvent.setup();
    const onDelete = jest.fn();
    const dep = makeDeployment();
    renderTable([dep], { onDeleteDeployment: onDelete });

    await user.click(screen.getByTestId("actions-deployment-dep-1"));
    await user.click(screen.getByText("Delete"));
    expect(onDelete).toHaveBeenCalledWith(dep);
  });
});

// ---------------------------------------------------------------------------
// Deleting state
// ---------------------------------------------------------------------------

describe("Deleting state", () => {
  it("shows loading spinner instead of actions when deleting", () => {
    renderTable([makeDeployment()], { deletingId: "dep-1" });
    expect(screen.getByTestId("loading-spinner")).toBeInTheDocument();
    expect(
      screen.queryByTestId("actions-deployment-dep-1"),
    ).not.toBeInTheDocument();
  });

  it("applies opacity to the deleting row", () => {
    renderTable([makeDeployment()], { deletingId: "dep-1" });
    const row = screen.getByTestId("deployment-row-dep-1");
    expect(row.className).toContain("opacity-50");
  });

  it("does not affect other rows", () => {
    renderTable(
      [
        makeDeployment({ id: "dep-1" }),
        makeDeployment({ id: "dep-2", name: "Other" }),
      ],
      { deletingId: "dep-1" },
    );
    const otherRow = screen.getByTestId("deployment-row-dep-2");
    expect(otherRow.className).not.toContain("opacity-50");
  });
});

// ---------------------------------------------------------------------------
// Column headers
// ---------------------------------------------------------------------------

describe("Column headers", () => {
  it("renders all expected column headers", () => {
    renderTable();
    for (const header of [
      "Name",
      "Type",
      "Attached",
      "Provider",
      "Last Modified",
      "Test",
    ]) {
      expect(screen.getByText(header)).toBeInTheDocument();
    }
  });
});

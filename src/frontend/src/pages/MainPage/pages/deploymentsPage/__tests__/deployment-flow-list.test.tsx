import { render, screen } from "@testing-library/react";
import type { DeploymentFlowVersionItem } from "@/controllers/API/queries/deployments/use-get-deployment-attachments";

// ---------------------------------------------------------------------------
// Mocks — child components rendered as simple divs
// ---------------------------------------------------------------------------

jest.mock(
  "../components/deployment-details-modal/flow-version-item",
  () =>
    function MockFlowVersionItem({
      flowName,
      versionNumber,
      toolName,
      connectionNames,
    }: {
      flowName: string | null;
      versionNumber: number;
      toolName: string | null;
      connectionNames: string[];
    }) {
      return (
        <div data-testid="flow-version-item">
          <span data-testid="flow-name">{flowName ?? "null"}</span>
          <span data-testid="version-number">{versionNumber}</span>
          <span data-testid="tool-name">{toolName ?? "null"}</span>
          <span data-testid="connection-names">
            {connectionNames.join(",")}
          </span>
        </div>
      );
    },
);

import DeploymentFlowList from "../components/deployment-details-modal/deployment-flow-list";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeFlowVersion(
  overrides: Partial<DeploymentFlowVersionItem> = {},
): DeploymentFlowVersionItem {
  return {
    id: "fv-1",
    flow_id: "f-1",
    flow_name: "My Flow",
    version_number: 1,
    attached_at: null,
    provider_snapshot_id: null,
    provider_data: null,
    ...overrides,
  };
}

function renderList(
  flowVersions: DeploymentFlowVersionItem[] = [],
  getConnectionNames: (fv: DeploymentFlowVersionItem) => string[] = () => [],
) {
  return render(
    <DeploymentFlowList
      flowVersions={flowVersions}
      getConnectionNames={getConnectionNames}
    />,
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("DeploymentFlowList", () => {
  it("renders the correct flow count in the header", () => {
    const versions = [
      makeFlowVersion({ id: "fv-1", flow_name: "Flow A" }),
      makeFlowVersion({ id: "fv-2", flow_name: "Flow B" }),
      makeFlowVersion({ id: "fv-3", flow_name: "Flow C" }),
    ];
    renderList(versions);
    expect(screen.getByText("Attached Flows (3)")).toBeInTheDocument();
  });

  it('shows "No flows attached" when the list is empty', () => {
    renderList([]);
    expect(screen.getByText("Attached Flows (0)")).toBeInTheDocument();
    expect(screen.getByText("No flows attached")).toBeInTheDocument();
  });

  it("renders a FlowVersionItem for each flow version", () => {
    const versions = [
      makeFlowVersion({ id: "fv-1", flow_name: "Alpha" }),
      makeFlowVersion({ id: "fv-2", flow_name: "Beta" }),
    ];
    renderList(versions);
    const items = screen.getAllByTestId("flow-version-item");
    expect(items).toHaveLength(2);
  });

  it("invokes getConnectionNames callback for each flow version", () => {
    const getConnectionNames = jest.fn().mockReturnValue(["conn-a", "conn-b"]);
    const versions = [
      makeFlowVersion({ id: "fv-1", flow_name: "Flow X" }),
    ];
    renderList(versions, getConnectionNames);
    expect(getConnectionNames).toHaveBeenCalledTimes(1);
    expect(getConnectionNames).toHaveBeenCalledWith(versions[0]);
    expect(screen.getByTestId("connection-names")).toHaveTextContent(
      "conn-a,conn-b",
    );
  });

  it("handles undefined provider_data by passing null tool_name", () => {
    const versions = [
      makeFlowVersion({ id: "fv-1", provider_data: null }),
    ];
    renderList(versions);
    // provider_data?.tool_name ?? null → null, mock renders "null"
    expect(screen.getByTestId("tool-name")).toHaveTextContent("null");
  });

});

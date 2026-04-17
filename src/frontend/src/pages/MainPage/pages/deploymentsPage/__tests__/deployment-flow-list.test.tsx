import { render, screen } from "@testing-library/react";
import type { DeploymentFlowVersionItem } from "@/controllers/API/queries/deployments/use-get-deployment-attachments";

jest.mock(
  "@/components/common/genericIconComponent",
  () =>
    function MockIcon({ name }: { name: string }) {
      return <span data-testid={`icon-${name}`} />;
    },
);

import DeploymentFlowList from "../components/deployment-details-modal/deployment-flow-list";

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

describe("DeploymentFlowList", () => {
  it("shows the empty state when there are no attached flows", () => {
    renderList([]);

    expect(screen.getByText("Attached Flows (0)")).toBeInTheDocument();
    expect(screen.getByText("No flows attached")).toBeInTheDocument();
  });

  it("renders real flow details instead of mocked child props", () => {
    const flowVersions = [
      makeFlowVersion({
        id: "fv-1",
        flow_name: "Alpha",
        version_number: 2,
        provider_data: { tool_name: "search_docs" },
      }),
      makeFlowVersion({
        id: "fv-2",
        flow_name: null,
        version_number: 5,
        provider_data: null,
      }),
    ];

    renderList(flowVersions, (flowVersion) =>
      flowVersion.id === "fv-1" ? ["Prod Connection", "Backup Connection"] : [],
    );

    expect(screen.getByText("Attached Flows (2)")).toBeInTheDocument();
    expect(screen.getByText("Alpha")).toBeInTheDocument();
    expect(screen.getByText("Unknown flow")).toBeInTheDocument();
    expect(screen.getByText("v2")).toBeInTheDocument();
    expect(screen.getByText("v5")).toBeInTheDocument();
    expect(screen.getByText("search_docs")).toBeInTheDocument();
    expect(screen.getByText("Prod Connection")).toBeInTheDocument();
    expect(screen.getByText("Backup Connection")).toBeInTheDocument();
  });
});

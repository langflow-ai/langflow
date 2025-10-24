import {
  extractInstalledClientNames,
  mapFlowsToTools,
} from "../../utils/mcpServerUtils";

// Note: useMcpServer hook is fully tested via integration tests in McpServerTab.test.tsx
describe("useMcpServer hook dependencies", () => {
  it("mapFlowsToTools transforms flow data correctly", () => {
    const flows = [
      {
        id: "flow-1",
        name: "User Flow",
        description: "User desc",
        action_name: "user_flow",
        action_description: "Action desc",
        mcp_enabled: true,
      },
    ];

    const result = mapFlowsToTools(flows);

    expect(result).toHaveLength(1);
    expect(result[0]).toEqual({
      id: "flow-1",
      name: "user_flow",
      description: "Action desc",
      display_name: "User Flow",
      display_description: "User desc",
      status: true,
      tags: ["User Flow"],
    });
  });

  it("extractInstalledClientNames filters correctly", () => {
    const data = [
      { name: "cursor", installed: true },
      { name: "claude", installed: false },
      { name: undefined, installed: true },
    ];

    const result = extractInstalledClientNames(data);

    expect(result).toEqual(["cursor"]);
  });
});

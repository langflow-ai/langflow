import { render, screen } from "@testing-library/react";
import { BuildStatus } from "@/constants/enums";
import useAlertStore from "@/stores/alertStore";
import useFlowStore from "@/stores/flowStore";
import { useShortcutsStore } from "@/stores/shortcuts";
import { useUtilityStore } from "@/stores/utilityStore";
import type { VertexBuildTypeAPI } from "@/types/api";
import type { NodeDataType } from "@/types/flow";
import type { shortcutsStoreType } from "@/types/store";
import type { AlertStoreType } from "@/types/zustand/alert";
import type { FlowStoreType } from "@/types/zustand/flow";
import type { UtilityStoreType } from "@/types/zustand/utility";
import BuildStatusDisplay from "../components/build-status-display";
import NodeStatus from "../index";

jest.mock("@/CustomNodes/helpers/mutate-template", () => ({
  mutateTemplate: jest.fn(),
}));

jest.mock("@/controllers/API/queries/nodes/use-post-template-value", () => ({
  usePostTemplateValue: () => jest.fn(),
}));

jest.mock("@/customization/utils/analytics", () => ({
  track: jest.fn(),
}));

jest.mock("@/customization/utils/custom-open-new-tab", () => ({
  customOpenNewTab: jest.fn(),
}));

jest.mock("../../HumanInputNodeBadge", () => ({
  __esModule: true,
  default: () => <div data-testid="human-input-badge" />,
  useAwaitingHumanInput: () => false,
}));

jest.mock("../../../../../components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name }: { name: string }) => (
    <span data-testid={`icon-${name}`}>{name}</span>
  ),
}));

const NODE_ID = "TextOutput-fffff";

// The build a node keeps in flowPool after a later run routes away from it.
const staleBuild: VertexBuildTypeAPI = {
  id: NODE_ID,
  inactivated_vertices: null,
  next_vertices_ids: [],
  top_level_vertices: [],
  valid: true,
  data: {
    results: {},
    outputs: {},
    logs: {},
    messages: [],
    duration: "7ms",
  },
  timestamp: "2026-09-23T14:44:43.000Z",
  params: null,
  messages: [],
  artifacts: null,
};

function resetStores() {
  useFlowStore.setState({
    flowBuildStatus: {},
    flowPool: { [NODE_ID]: [staleBuild] },
    buildFlow: jest.fn(),
    isBuilding: false,
    setNode: jest.fn(),
    currentFlow: {
      id: "flow-1",
      locked: false,
    } as FlowStoreType["currentFlow"],
    setFlowPool: jest.fn(),
  } as Partial<FlowStoreType>);
  useUtilityStore.setState({
    eventDelivery: undefined,
  } as Partial<UtilityStoreType>);
  useAlertStore.setState({
    setErrorData: jest.fn(),
  } as Partial<AlertStoreType>);
  useShortcutsStore.setState({} as Partial<shortcutsStoreType>);
}

const renderStatus = (buildStatus: BuildStatus) =>
  render(
    <NodeStatus
      nodeId={NODE_ID}
      display_name="False Branch"
      setBorderColor={jest.fn()}
      showNode
      data={{ node: { template: {} } } as unknown as NodeDataType}
      buildStatus={buildStatus}
      dismissAll={false}
      isOutdated={false}
      isUserEdited={false}
      isBreakingChange={false}
      getValidationStatus={jest.fn(() => null)}
    />,
  );

/**
 * A node on an If-Else branch that was not taken is marked INACTIVE, but runs that do not
 * clear flowPool (Playground, webhook, play shortcut) leave its last successful build there.
 * The badge used to show that stale duration instead of the Execution blocked icon.
 */
describe("NodeStatus on a blocked node with an earlier successful build", () => {
  beforeEach(() => {
    resetStores();
  });

  it("should_show_the_blocked_icon_instead_of_the_stale_duration", () => {
    renderStatus(BuildStatus.INACTIVE);

    expect(
      screen.getByTestId("node_status_icon_false branch_inactive"),
    ).toBeInTheDocument();
    expect(
      screen.queryByTestId("node_duration_false branch"),
    ).not.toBeInTheDocument();
  });

  it("should_still_show_the_duration_when_the_node_ran", () => {
    renderStatus(BuildStatus.BUILT);

    expect(screen.getByTestId("node_duration_false branch")).toHaveTextContent(
      "7ms",
    );
  });
});

describe("BuildStatusDisplay for a blocked node", () => {
  it("should_keep_the_last_run_duration_under_execution_blocked", () => {
    render(
      <BuildStatusDisplay
        buildStatus={BuildStatus.INACTIVE}
        validationStatus={staleBuild}
        validationString=""
        lastRunTime={undefined}
      />,
    );

    expect(screen.getByText("Execution blocked")).toBeInTheDocument();
    // The formatted date depends on the runner's time zone, so only the prefix is asserted.
    expect(screen.getByText("Last Run:", { exact: false })).toBeInTheDocument();
    expect(screen.getByText("7ms")).toBeInTheDocument();
  });

  it("should_show_only_execution_blocked_when_the_node_never_ran", () => {
    render(
      <BuildStatusDisplay
        buildStatus={BuildStatus.INACTIVE}
        validationStatus={null}
        validationString=""
        lastRunTime={undefined}
      />,
    );

    expect(screen.getByText("Execution blocked")).toBeInTheDocument();
    expect(screen.queryByText("Duration:")).not.toBeInTheDocument();
  });
});

import { render, screen } from "@testing-library/react";
import { BuildStatus } from "@/constants/enums";
import useAlertStore from "@/stores/alertStore";
import useFlowStore from "@/stores/flowStore";
import { useShortcutsStore } from "@/stores/shortcuts";
import { useUtilityStore } from "@/stores/utilityStore";
import type { NodeDataType } from "@/types/flow";
import type { shortcutsStoreType } from "@/types/store";
import type { AlertStoreType } from "@/types/zustand/alert";
import type { FlowStoreType } from "@/types/zustand/flow";
import type { UtilityStoreType } from "@/types/zustand/utility";
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

jest.mock("../components/build-status-display", () => ({
  __esModule: true,
  default: () => <div data-testid="build-status-display" />,
}));

jest.mock("../../../../../components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name }: { name: string }) => (
    <span data-testid={`icon-${name}`}>{name}</span>
  ),
}));

function resetStores() {
  useFlowStore.setState({
    flowBuildStatus: {},
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

const baseProps = {
  nodeId: "node-1",
  setBorderColor: jest.fn(),
  showNode: true,
  data: { node: { template: {} } } as unknown as NodeDataType,
  dismissAll: false,
  isOutdated: false,
  isUserEdited: false,
  isBreakingChange: false,
  getValidationStatus: jest.fn(() => null),
};

/**
 * A node dropped on the canvas while the backend is unreachable is persisted with
 * no type and no display_name. Dereferencing it took down the whole node tree, so
 * one malformed node made the flow unopenable — and the only way out was editing
 * the row by hand.
 */
describe("NodeStatus with a malformed node", () => {
  beforeEach(() => {
    resetStores();
  });

  it("should_render_when_display_name_is_undefined", () => {
    expect(() =>
      render(
        <NodeStatus
          {...baseProps}
          display_name={undefined as unknown as string}
          buildStatus={BuildStatus.TO_BUILD}
        />,
      ),
    ).not.toThrow();
  });

  it("should_still_expose_the_run_button_when_display_name_is_undefined", () => {
    render(
      <NodeStatus
        {...baseProps}
        display_name={undefined as unknown as string}
        buildStatus={BuildStatus.TO_BUILD}
      />,
    );

    expect(
      screen.getByRole("button", { name: "Run component" }),
    ).toBeInTheDocument();
  });

  it("should_render_when_display_name_is_an_empty_string", () => {
    expect(() =>
      render(
        <NodeStatus
          {...baseProps}
          display_name=""
          buildStatus={BuildStatus.TO_BUILD}
        />,
      ),
    ).not.toThrow();
  });

  it("should_keep_the_named_test_id_when_display_name_is_present", () => {
    render(
      <NodeStatus
        {...baseProps}
        display_name="Chat Input"
        buildStatus={BuildStatus.TO_BUILD}
      />,
    );

    expect(screen.getByTestId("button_run_chat input")).toBeInTheDocument();
  });
});

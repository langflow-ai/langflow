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
import { axe } from "@/utils/a11y-test";
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
  display_name: "Chat Input",
  setBorderColor: jest.fn(),
  showNode: true,
  data: { node: { template: {} } } as unknown as NodeDataType,
  dismissAll: false,
  isOutdated: false,
  isUserEdited: false,
  isBreakingChange: false,
  getValidationStatus: jest.fn(() => null),
};

describe("NodeStatus accessibility", () => {
  beforeEach(() => {
    resetStores();
  });

  it("should_have_no_axe_violations_when_idle", async () => {
    const { container } = render(
      <NodeStatus {...baseProps} buildStatus={BuildStatus.TO_BUILD} />,
    );

    expect(await axe(container)).toHaveNoViolations();
  });

  it("should_expose_run_component_as_accessible_name_when_idle", () => {
    render(<NodeStatus {...baseProps} buildStatus={BuildStatus.TO_BUILD} />);

    expect(
      screen.getByRole("button", { name: "Run component" }),
    ).toBeInTheDocument();
  });

  it("should_expose_connect_button_with_fallback_accessible_name", () => {
    render(
      <NodeStatus
        {...baseProps}
        data={
          {
            node: {
              template: {
                auth_link: { type: "auth", value: "" },
              },
            },
          } as unknown as NodeDataType
        }
        buildStatus={BuildStatus.TO_BUILD}
      />,
    );

    expect(screen.getByRole("button", { name: "Connect" })).toBeInTheDocument();
  });

  it("should_expose_connect_button_with_custom_auth_tooltip", () => {
    render(
      <NodeStatus
        {...baseProps}
        data={
          {
            node: {
              template: {
                auth_link: {
                  type: "auth",
                  value: "",
                  auth_tooltip: "Sign in with Google",
                },
              },
            },
          } as unknown as NodeDataType
        }
        buildStatus={BuildStatus.TO_BUILD}
      />,
    );

    expect(
      screen.getByRole("button", { name: "Sign in with Google" }),
    ).toBeInTheDocument();
  });
});

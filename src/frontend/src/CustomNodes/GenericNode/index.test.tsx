import { render, screen } from "@testing-library/react";
import type {
  ButtonHTMLAttributes,
  ComponentProps,
  PropsWithChildren,
} from "react";

let mockCloudOnly = false;
type Selector<TState, TResult = unknown> = (state: TState) => TResult;
type CloudModeState = {
  cloudOnly: boolean;
  setCloudOnly: jest.Mock;
};
type AlertStoreState = {
  setErrorData: jest.Mock;
};
type FlowsManagerStoreState = {
  takeSnapshot: jest.Mock;
};
type ShortcutsStoreState = {
  shortcuts: Record<string, unknown>;
  update: string;
};
type TypesStoreState = {
  types: Record<string, unknown>;
  templates: Record<string, unknown>;
};

const typesStoreState: TypesStoreState = {
  types: {},
  templates: {},
};

const flowStoreState = {
  deleteNode: jest.fn(),
  setNode: jest.fn(),
  edges: [],
  setEdges: jest.fn(),
  dismissedNodes: [],
  addDismissedNodes: jest.fn(),
  removeDismissedNodes: jest.fn(),
  dismissedNodesLegacy: [],
  addDismissedNodesLegacy: jest.fn(),
  rightClickedNodeId: null,
  componentsToUpdate: [],
  nodes: [],
};

const useFlowStoreMock = Object.assign(
  <TResult,>(selector: Selector<typeof flowStoreState, TResult>) =>
    selector(flowStoreState),
  {
    getState: () => flowStoreState,
  },
);

jest.mock("@xyflow/react", () => ({
  useUpdateNodeInternals: () => jest.fn(),
}));

jest.mock("react-hotkeys-hook", () => ({
  useHotkeys: jest.fn(),
}));

jest.mock("zustand/react/shallow", () => ({
  useShallow: <T,>(selector: T) => selector,
}));

jest.mock("@/customization/components/custom-NodeStatus", () => ({
  CustomNodeStatus: () => <div data-testid="node-status" />,
}));

jest.mock("@/shared/hooks/use-alternate", () => ({
  useAlternate: (initial: boolean) => [initial, jest.fn(), jest.fn()],
}));

jest.mock(
  "../../controllers/API/queries/nodes/use-post-validate-component-code",
  () => ({
    usePostValidateComponentCode: () => ({ mutate: jest.fn() }),
  }),
);

jest.mock("../../pages/FlowPage/components/nodeToolbarComponent", () => ({
  __esModule: true,
  default: () => <div data-testid="node-toolbar" />,
}));

jest.mock("../../shared/hooks/use-change-on-unfocus", () => ({
  useChangeOnUnfocus: jest.fn(),
}));

jest.mock("../../stores/alertStore", () => ({
  __esModule: true,
  default: <T,>(selector: Selector<AlertStoreState, T>) =>
    selector({
      setErrorData: jest.fn(),
    }),
}));

jest.mock("../../stores/cloudModeStore", () => ({
  useCloudModeStore: <T,>(selector: Selector<CloudModeState, T>) =>
    selector({ cloudOnly: mockCloudOnly, setCloudOnly: jest.fn() }),
}));

jest.mock("../../stores/flowStore", () => ({
  __esModule: true,
  default: useFlowStoreMock,
}));

jest.mock("../../stores/flowsManagerStore", () => ({
  __esModule: true,
  default: <T,>(selector: Selector<FlowsManagerStoreState, T>) =>
    selector({
      takeSnapshot: jest.fn(),
    }),
}));

jest.mock("../../stores/shortcuts", () => ({
  useShortcutsStore: <T,>(selector: Selector<ShortcutsStoreState, T>) =>
    selector({
      shortcuts: {},
      update: "mod+u",
    }),
}));

jest.mock("../../stores/typesStore", () => ({
  useTypesStore: <T,>(selector: Selector<TypesStoreState, T>) =>
    selector(typesStoreState),
}));

jest.mock("../helpers/process-node-advanced-fields", () => ({
  processNodeAdvancedFields: jest.fn(),
}));

jest.mock("../hooks/use-update-node-code", () => ({
  __esModule: true,
  default: () => jest.fn(),
}));

jest.mock("./components/NodeCloudIncompatibleComponent", () => ({
  __esModule: true,
  default: () => (
    <div data-testid="cloud-incompatible-banner">Not available in cloud</div>
  ),
}));

jest.mock("./components/NodeDescription", () => ({
  __esModule: true,
  default: () => <div data-testid="node-description" />,
}));

jest.mock("./components/NodeLegacyComponent", () => ({
  __esModule: true,
  default: () => <div>Legacy</div>,
}));

jest.mock("./components/NodeName", () => ({
  __esModule: true,
  default: ({ display_name }: { display_name: string }) => (
    <div>{display_name}</div>
  ),
}));

jest.mock("./components/NodeOutputParameter/NodeOutputs", () => ({
  __esModule: true,
  default: () => <div data-testid="node-outputs" />,
}));

jest.mock("./components/NodeUpdateComponent", () => ({
  __esModule: true,
  default: () => <div>Update available</div>,
}));

jest.mock("./components/nodeIcon", () => ({
  NodeIcon: () => <div data-testid="node-icon" />,
}));

jest.mock("./components/RenderInputParameters", () => ({
  __esModule: true,
  default: () => <div data-testid="render-input-parameters" />,
}));

jest.mock("./hooks/use-get-build-status", () => ({
  useBuildStatus: () => null,
}));

jest.mock("../../components/common/genericIconComponent", () => ({
  __esModule: true,
  default: () => <span data-testid="icon" />,
}));

jest.mock("../../components/ui/button", () => ({
  Button: ({
    children,
    ...props
  }: PropsWithChildren<ButtonHTMLAttributes<HTMLButtonElement>>) => (
    <button {...props}>{children}</button>
  ),
}));

import GenericNode from ".";

describe("GenericNode", () => {
  beforeEach(() => {
    mockCloudOnly = false;
    flowStoreState.dismissedNodes = [];
    flowStoreState.dismissedNodesLegacy = [];
    flowStoreState.componentsToUpdate = [];
    flowStoreState.nodes = [];
    typesStoreState.types = {};
    typesStoreState.templates = {};
  });

  it("renders legacy and cloud incompatibility warnings together", () => {
    mockCloudOnly = true;
    const data: ComponentProps<typeof GenericNode>["data"] = {
      id: "directory-node",
      type: "Directory",
      showNode: true,
      node: {
        display_name: "Directory",
        description: "Reads local directories",
        documentation: "",
        template: {},
        outputs: [],
        legacy: true,
        replacement: ["data.File"],
        cloud_compatible: false,
      },
    };

    render(<GenericNode data={data} />);

    expect(screen.getByText("Legacy")).toBeInTheDocument();
    expect(screen.getByTestId("cloud-incompatible-banner")).toBeInTheDocument();
  });

  it("backfills cloud incompatibility from the current catalog for older saved nodes", () => {
    mockCloudOnly = true;
    typesStoreState.templates = {
      Directory: {
        description: "Reads local directories",
        display_name: "Directory",
        documentation: "",
        template: {},
        cloud_compatible: false,
      },
    };

    const data: ComponentProps<typeof GenericNode>["data"] = {
      id: "legacy-directory-node",
      type: "Directory",
      showNode: true,
      node: {
        display_name: "Directory",
        description: "Reads local directories",
        documentation: "",
        template: {},
        outputs: [],
      },
    };

    render(<GenericNode data={data} />);

    expect(screen.getByTestId("cloud-incompatible-banner")).toBeInTheDocument();
  });
});

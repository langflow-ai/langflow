import { render, screen } from "@testing-library/react";
import GenericNode from "../index";

type ComponentUpdate = {
  id: string;
  outdated: boolean;
  blocked: boolean;
  breakingChange: boolean;
  userEdited: boolean;
};

let mockAllowCustomComponents: boolean;
let mockBlockedComponentTypes: Set<string>;
let mockComponentsToUpdate: ComponentUpdate[];
let mockDismissedNodes: string[];

jest.mock("@xyflow/react", () => ({
  useUpdateNodeInternals: () => jest.fn(),
}));

jest.mock("react-hotkeys-hook", () => ({
  useHotkeys: jest.fn(),
}));

jest.mock("zustand/react/shallow", () => ({
  useShallow: (selector: (state: unknown) => unknown) => selector,
}));

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: () => null,
}));

jest.mock("@/components/ui/button", () => ({
  Button: ({ children }: { children: React.ReactNode }) => (
    <button>{children}</button>
  ),
}));

jest.mock(
  "@/controllers/API/queries/nodes/use-post-validate-component-code",
  () => ({
    usePostValidateComponentCode: () => ({ mutateAsync: jest.fn() }),
  }),
);

jest.mock("@/shared/hooks/use-alternate", () => ({
  useAlternate: () => [false, jest.fn(), jest.fn()],
}));

jest.mock("../../../pages/FlowPage/components/nodeToolbarComponent", () => ({
  __esModule: true,
  default: () => null,
}));

jest.mock("../../../shared/hooks/use-change-on-unfocus", () => ({
  useChangeOnUnfocus: jest.fn(),
}));

jest.mock("../../../stores/alertStore", () => ({
  __esModule: true,
  default: (selector: (state: unknown) => unknown) =>
    selector({ setErrorData: jest.fn() }),
}));

jest.mock("../../../stores/flowStore", () => {
  const state = () => ({
    deleteNode: jest.fn(),
    setNode: jest.fn(),
    edges: [],
    setEdges: jest.fn(),
    dismissedNodes: mockDismissedNodes,
    addDismissedNodes: jest.fn(),
    removeDismissedNodes: jest.fn(),
    dismissedNodesLegacy: [],
    addDismissedNodesLegacy: jest.fn(),
    componentsToUpdate: mockComponentsToUpdate,
    nodes: [{ id: "node-1", selected: false }],
    rightClickedNodeId: null,
  });
  const useFlowStore = (selector?: (value: unknown) => unknown) =>
    selector ? selector(state()) : state();
  useFlowStore.getState = state;

  return {
    __esModule: true,
    default: useFlowStore,
    registerNodeUpdate: jest.fn(),
    completeNodeUpdate: jest.fn(),
  };
});

jest.mock("../../../stores/flowsManagerStore", () => ({
  __esModule: true,
  default: (selector: (state: unknown) => unknown) =>
    selector({ takeSnapshot: jest.fn() }),
}));

jest.mock("../../../stores/utilityStore", () => ({
  useUtilityStore: (selector: (state: unknown) => unknown) =>
    selector({
      allowCustomComponents: mockAllowCustomComponents,
      blockedComponentTypes: mockBlockedComponentTypes,
    }),
}));

jest.mock("../../../stores/shortcuts", () => ({
  useShortcutsStore: (selector: (state: unknown) => unknown) =>
    selector({ shortcuts: [] }),
}));

jest.mock("../../../stores/typesStore", () => ({
  // A loaded registry: an empty one means "still fetching", where a missing
  // template says nothing about the node.
  useTypesStore: (selector: (state: unknown) => unknown) =>
    selector({ types: {}, templates: { SomeKnownType: {} } }),
}));

jest.mock("../../hooks/use-update-node-code", () => ({
  __esModule: true,
  default: () => jest.fn(),
}));

jest.mock("../../helpers/process-node-advanced-fields", () => ({
  processNodeAdvancedFields: jest.fn(),
}));

jest.mock("../components/NodeDescription", () => ({
  __esModule: true,
  default: () => null,
}));

jest.mock("../components/NodeName", () => ({
  __esModule: true,
  default: () => null,
}));

jest.mock("../components/NodeOutputParameter/NodeOutputs", () => ({
  __esModule: true,
  default: () => null,
}));

// Stand in for the banner so this suite asserts whether it renders and what it
// is told, and leaves its copy to the NodeUpdateComponent suite.
jest.mock("../components/NodeUpdateComponent", () => ({
  __esModule: true,
  default: ({
    blocked,
    blockedByCatalogPolicy,
  }: {
    blocked?: boolean;
    blockedByCatalogPolicy?: boolean;
  }) => (
    <div
      data-testid="node-update-banner"
      data-blocked={String(!!blocked)}
      data-blocked-by-policy={String(!!blockedByCatalogPolicy)}
    />
  ),
}));

jest.mock("../components/NodeLegacyComponent", () => ({
  __esModule: true,
  default: () => null,
}));

jest.mock("../components/nodeIcon", () => ({
  NodeIcon: () => null,
}));

jest.mock("../components/RenderInputParameters", () => ({
  __esModule: true,
  default: () => null,
}));

jest.mock("../hooks/use-get-build-status", () => ({
  useBuildStatus: () => null,
}));

jest.mock("@/customization/components/custom-NodeStatus", () => ({
  CustomNodeStatus: () => null,
}));

jest.mock("@/modals/updateComponentModal", () => ({
  __esModule: true,
  default: () => null,
}));

jest.mock("@/utils/reactflowUtils", () => ({
  scapedJSONStringfy: jest.fn(),
}));

jest.mock("@/utils/utils", () => ({
  cn: (...classes: unknown[]) => classes.filter(Boolean).join(" "),
  classNames: (...classes: unknown[]) => classes.filter(Boolean).join(" "),
}));

const componentUpdate = (
  overrides: Partial<ComponentUpdate> = {},
): ComponentUpdate => ({
  id: "node-1",
  outdated: false,
  blocked: false,
  breakingChange: false,
  userEdited: false,
  ...overrides,
});

const renderNode = () =>
  render(
    <GenericNode
      selected={false}
      data={{
        id: "node-1",
        type: "Prompt",
        node: {
          display_name: "Prompt",
          description: "Prompt node",
          documentation: "",
          template: {
            code: {
              type: "code",
              required: true,
              list: false,
              show: true,
              readonly: false,
              value: "stored_code",
            },
          },
          outputs: [],
        },
      }}
    />,
  );

describe("GenericNode blocked banner", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockAllowCustomComponents = true;
    // The fixture node is a Prompt; the policy names it by default.
    mockBlockedComponentTypes = new Set(["Prompt"]);
    mockDismissedNodes = [];
    mockComponentsToUpdate = [];
  });

  it("names the catalog policy when one is in force", () => {
    // The catalog dropped this component, so its template is gone. Before, the
    // node looked healthy here and only failed once the flow was run.
    mockComponentsToUpdate = [componentUpdate({ blocked: true })];

    renderNode();

    const banner = screen.getByTestId("node-update-banner");
    expect(banner).toHaveAttribute("data-blocked", "true");
    expect(banner).toHaveAttribute("data-blocked-by-policy", "true");
  });

  it("leaves a custom component alone when no policy is in force", () => {
    // A user-authored component has code and no registry template, exactly
    // like a policy-blocked one. With custom components allowed and no policy
    // it is legitimate, so flagging it would stop people running their own work.
    mockBlockedComponentTypes = new Set<string>();
    mockComponentsToUpdate = [componentUpdate({ blocked: true })];

    renderNode();

    expect(screen.queryByTestId("node-update-banner")).not.toBeInTheDocument();
  });

  it("leaves a node alone when the policy names a different component", () => {
    // LE-2226: a policy that blocks some other component — or only a starter
    // template — must not brand this node "disabled by an administrator". A
    // missing template is equally an uninstalled bundle or an imported flow.
    mockBlockedComponentTypes = new Set(["SomeOtherComponent"]);
    mockComponentsToUpdate = [componentUpdate({ blocked: true })];

    renderNode();

    expect(screen.queryByTestId("node-update-banner")).not.toBeInTheDocument();
  });

  it("keeps surfacing a blocked node the user dismissed", () => {
    // Dismissal silences update nudges. A blocked node has no update to take,
    // so it stays visible.
    mockComponentsToUpdate = [
      componentUpdate({ blocked: true, userEdited: true }),
    ];
    mockDismissedNodes = ["node-1"];

    renderNode();

    expect(screen.getByTestId("node-update-banner")).toBeInTheDocument();
  });

  it("reports restricted mode rather than catalog policy", () => {
    mockAllowCustomComponents = false;
    mockComponentsToUpdate = [componentUpdate({ blocked: true })];

    renderNode();

    const banner = screen.getByTestId("node-update-banner");
    expect(banner).toHaveAttribute("data-blocked", "true");
    expect(banner).toHaveAttribute("data-blocked-by-policy", "false");
  });

  it("leaves a dismissed outdated node silent", () => {
    // Drift is unchanged by this fix: it still respects dismissal.
    mockComponentsToUpdate = [
      componentUpdate({ outdated: true, userEdited: true }),
    ];
    mockDismissedNodes = ["node-1"];

    renderNode();

    expect(screen.queryByTestId("node-update-banner")).not.toBeInTheDocument();
  });

  it("shows no banner for a healthy node", () => {
    renderNode();

    expect(screen.queryByTestId("node-update-banner")).not.toBeInTheDocument();
  });
});

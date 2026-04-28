import { act, render, screen } from "@testing-library/react";
import { useUtilityStore } from "@/stores/utilityStore";
import NodeToolbarComponent from "../index";

const mockFreezeAllVertices = jest.fn();
const mockAddFlow = jest.fn();
const mockSetNoticeData = jest.fn();
const mockSetErrorData = jest.fn();
const mockSetSuccessData = jest.fn();

jest.mock("@xyflow/react", () => ({
  useUpdateNodeInternals: () => jest.fn(),
}));

jest.mock("@/CustomNodes/hooks/use-handle-new-value", () => ({
  __esModule: true,
  default: () => ({
    handleOnNewValue: jest.fn(),
  }),
}));

jest.mock("@/CustomNodes/hooks/use-handle-node-class", () => ({
  __esModule: true,
  default: () => ({
    handleNodeClass: jest.fn(),
  }),
}));

jest.mock("@/components/common/shadTooltipComponent", () => ({
  __esModule: true,
  default: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

jest.mock(
  "@/components/core/parameterRenderComponent/components/toggleShadComponent",
  () => ({
    __esModule: true,
    default: () => null,
  }),
);

jest.mock("@/components/ui/button", () => ({
  Button: ({
    children,
    onClick,
    "data-testid": dataTestId,
    asChild: _asChild,
    ...props
  }: {
    children: React.ReactNode;
    onClick?: () => void;
    "data-testid"?: string;
    asChild?: boolean;
  }) => (
    <button onClick={onClick} data-testid={dataTestId} {...props}>
      {children}
    </button>
  ),
}));

jest.mock("@/controllers/API/queries/nodes/use-post-template-value", () => ({
  usePostTemplateValue: () => ({}),
}));

jest.mock("@/controllers/API/queries/vertex", () => ({
  usePostRetrieveVertexOrder: () => ({
    mutate: mockFreezeAllVertices,
  }),
}));

jest.mock("@/customization/utils/custom-open-new-tab", () => ({
  customOpenNewTab: jest.fn(),
}));

jest.mock("@/hooks/flows/use-add-flow", () => ({
  __esModule: true,
  default: () => mockAddFlow,
}));

jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: (selector: (state: unknown) => unknown) =>
    selector({
      setSuccessData: mockSetSuccessData,
      setNoticeData: mockSetNoticeData,
      setErrorData: mockSetErrorData,
    }),
}));

jest.mock("@/stores/darkStore", () => ({
  useDarkStore: (selector: (state: unknown) => unknown) =>
    selector({
      version: "test-version",
    }),
}));

const mockFlowStoreState = {
  updateFreezeStatus: jest.fn(),
  paste: jest.fn(),
  setNodes: jest.fn(),
  setEdges: jest.fn(),
  edges: [],
  getNodePosition: jest.fn(() => ({ x: 0, y: 0 })),
  inspectionPanelVisible: false,
};

jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: (selector: (state: typeof mockFlowStoreState) => unknown) =>
    selector(mockFlowStoreState),
}));

const mockFlowsManagerStoreState = {
  currentFlowId: "flow-1",
  flows: [],
  takeSnapshot: jest.fn(),
};

jest.mock("@/stores/flowsManagerStore", () => ({
  __esModule: true,
  default: (selector: (state: typeof mockFlowsManagerStoreState) => unknown) =>
    selector(mockFlowsManagerStoreState),
}));

jest.mock("@/stores/shortcuts", () => ({
  useShortcutsStore: (selector: (state: unknown) => unknown) =>
    selector({
      shortcuts: [{ name: "Code", shortcut: ["Meta", "K"] }],
    }),
}));

jest.mock("@/stores/storeStore", () => ({
  useStoreStore: (selector: (state: unknown) => unknown) =>
    selector({
      hasStore: false,
      hasApiKey: false,
      validApiKey: false,
    }),
}));

jest.mock("../../../../../components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name }: { name: string }) => <span>{name}</span>,
  ForwardedIconComponent: ({ name }: { name: string }) => <span>{name}</span>,
}));

jest.mock("../../../../../components/ui/select-custom", () => ({
  Select: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  SelectContentWithoutPortal: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  SelectItem: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  SelectTrigger: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
}));

jest.mock("../../../../../utils/reactflowUtils", () => ({
  checkHasToolMode: jest.fn(() => false),
  createFlowComponent: jest.fn((data) => ({
    name: data.id,
  })),
  downloadNode: jest.fn(),
  expandGroupNode: jest.fn(),
  updateFlowPosition: jest.fn(),
}));

jest.mock("../../../../../utils/utils", () => ({
  cn: (...classes: string[]) => classes.filter(Boolean).join(" "),
  getNodeLength: jest.fn(() => 1),
}));

jest.mock("../components/toolbar-button", () => ({
  ToolbarButton: ({
    dataTestId,
    label,
    onClick,
  }: {
    dataTestId?: string;
    label?: string;
    onClick?: () => void;
  }) => (
    <button data-testid={dataTestId} onClick={onClick}>
      {label}
    </button>
  ),
}));

jest.mock("../components/toolbar-modals", () => ({
  __esModule: true,
  default: () => null,
}));

jest.mock("../hooks/use-shortcuts", () => ({
  __esModule: true,
  default: () => undefined,
}));

jest.mock("../shortcutDisplay", () => ({
  __esModule: true,
  default: () => null,
}));

jest.mock("../toolbarSelectItem", () => ({
  __esModule: true,
  default: () => null,
}));

const getProps = () => ({
  data: {
    id: "node-1",
    type: "Prompt",
    node: {
      display_name: "Prompt",
      description: "Prompt node",
      template: {
        code: { value: "print('hello')" },
      },
      outputs: [],
      frozen: false,
    },
  },
  deleteNode: jest.fn(),
  setShowNode: jest.fn(),
  numberOfOutputHandles: 0,
  showNode: true,
  onCloseAdvancedModal: jest.fn(),
  updateNode: jest.fn(),
  isOutdated: false,
  isUserEdited: false,
  hasBreakingChange: false,
});

describe("NodeToolbarComponent config transitions", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    act(() => {
      useUtilityStore.setState({ allowCustomComponents: false });
    });
  });

  it("keeps the Code entrypoint hidden until config enables custom components", () => {
    const { rerender } = render(<NodeToolbarComponent {...getProps()} />);

    expect(screen.queryByTestId("code-button-modal")).not.toBeInTheDocument();

    act(() => {
      useUtilityStore.setState({ allowCustomComponents: true });
    });

    rerender(<NodeToolbarComponent {...getProps()} />);

    expect(screen.getByTestId("code-button-modal")).toBeInTheDocument();

    act(() => {
      useUtilityStore.setState({ allowCustomComponents: false });
    });

    rerender(<NodeToolbarComponent {...getProps()} />);

    expect(screen.queryByTestId("code-button-modal")).not.toBeInTheDocument();
  });
});

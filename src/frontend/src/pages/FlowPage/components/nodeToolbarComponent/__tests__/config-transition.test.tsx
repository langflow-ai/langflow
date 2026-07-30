import { act, fireEvent, render, screen } from "@testing-library/react";
import { useUtilityStore } from "@/stores/utilityStore";
import NodeToolbarComponent from "../index";

const mockFreezeAllVertices = jest.fn();
const mockAddFlow = jest.fn();
const mockCheckHasToolMode = jest.fn(() => false);
const mockMutateTemplate = jest.fn();
const mockPostToolModeValue = { isPending: false };
const mockSetNoticeData = jest.fn();
const mockSetErrorData = jest.fn();
const mockSetSuccessData = jest.fn();

jest.mock("@xyflow/react", () => ({
  useUpdateNodeInternals: () => jest.fn(),
}));

jest.mock("@/CustomNodes/helpers/mutate-template", () => ({
  mutateTemplate: (...args: unknown[]) => mockMutateTemplate(...args),
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
  usePostTemplateValue: () => mockPostToolModeValue,
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
  checkHasToolMode: () => mockCheckHasToolMode(),
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
      documentation: "",
      template: {
        code: {
          value: "print('hello')",
          type: "code",
          required: true,
          list: false,
          show: true,
          readonly: false,
        },
      },
      outputs: [],
      frozen: false,
    },
  },
  deleteNode: jest.fn(),
  setShowNode: jest.fn(),
  numberOfOutputHandles: 0,
  showNode: true,
  updateNode: jest.fn(),
  isOutdated: false,
  isUserEdited: false,
  hasBreakingChange: false,
});

describe("NodeToolbarComponent config transitions", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockCheckHasToolMode.mockReturnValue(false);
    mockPostToolModeValue.isPending = false;
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

  it("keeps an optimistic Tool Mode toggle on while its update is pending", () => {
    mockCheckHasToolMode.mockReturnValue(true);
    const props = {
      ...getProps(),
      data: {
        ...getProps().data,
        node: {
          ...getProps().data.node,
          tool_mode: false,
        },
      },
    };
    const { rerender } = render(<NodeToolbarComponent {...props} />);
    const toolModeButton = screen.getByTestId("tool-mode-button");

    fireEvent.click(screen.getByText("Tool Mode"));
    expect(toolModeButton).toHaveClass("text-primary");

    mockPostToolModeValue.isPending = true;
    rerender(
      <NodeToolbarComponent
        {...props}
        data={{
          ...props.data,
          node: {
            ...props.data.node,
            outputs: [],
            tool_mode: false,
          },
        }}
      />,
    );

    expect(screen.getByTestId("tool-mode-button")).toHaveClass("text-primary");
  });
});

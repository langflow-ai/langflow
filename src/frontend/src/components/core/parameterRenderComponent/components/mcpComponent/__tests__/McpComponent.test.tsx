import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import type { APIClassType } from "@/types/api";
import McpComponent from "../index";

const mockRefetchMCPServers = jest.fn();
const mockMutateTemplate = jest.fn();
const mockUpdateBuildStatus = jest.fn();
const mockSetErrorData = jest.fn();
const mockPostTemplateValue = { mutateAsync: jest.fn() };

jest.mock("@/CustomNodes/helpers/mutate-template", () => ({
  mutateTemplate: (...args: unknown[]) => mockMutateTemplate(...args),
}));

jest.mock("@/controllers/API/queries/mcp/use-get-mcp-servers", () => ({
  useGetMCPServers: jest.fn(() => ({
    data: [
      {
        name: "broken-server",
        mode: null,
        toolsCount: null,
        error: "Connection refused by MCP server",
      },
    ],
    refetch: mockRefetchMCPServers,
    isFetching: false,
  })),
}));

jest.mock("@/controllers/API/queries/mcp/use-add-mcp-server", () => ({
  useAddMCPServer: jest.fn(() => ({
    mutate: jest.fn(),
  })),
}));

jest.mock("@/controllers/API/queries/nodes/use-post-template-value", () => ({
  usePostTemplateValue: jest.fn(() => mockPostTemplateValue),
}));

jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: (
    selector?: (state: { setErrorData: typeof mockSetErrorData }) => unknown,
  ) => {
    const state = { setErrorData: mockSetErrorData };
    return selector ? selector(state) : state;
  },
}));

jest.mock("@/stores/flowStore", () => {
  const mockFlowState = {
    updateBuildStatus: mockUpdateBuildStatus,
  };
  const useFlowStoreMock = jest.fn(
    (selector?: (state: typeof mockFlowState) => unknown) =>
      selector ? selector(mockFlowState) : mockFlowState,
  );
  useFlowStoreMock.getState = () => mockFlowState;
  return {
    __esModule: true,
    default: useFlowStoreMock,
  };
});

jest.mock("@/components/common/shadTooltipComponent", () => ({
  __esModule: true,
  default: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name, className }: { name: string; className?: string }) => (
    <span data-testid={`icon-${name}`} className={className}>
      {name}
    </span>
  ),
}));

jest.mock("@/modals/addMcpServerModal", () => ({
  __esModule: true,
  default: () => null,
}));

jest.mock(
  "@/CustomNodes/GenericNode/components/ListSelectionComponent",
  () => ({
    __esModule: true,
    default: () => null,
  }),
);

describe("McpComponent", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockRefetchMCPServers.mockResolvedValue({});
    mockMutateTemplate.mockImplementation(
      (
        _value,
        _nodeId,
        nodeClass,
        setNodeClass,
        _postTemplateValue,
        _setErrorData,
        _parameterName,
        callback,
      ) => {
        setNodeClass(nodeClass);
        callback();
        return Promise.resolve();
      },
    );
  });

  it("shows the MCP server error and refreshes the node on demand", async () => {
    const user = userEvent.setup();
    const nodeClass = {
      template: { code: { value: "code" } },
      tool_mode: false,
    } as APIClassType;

    render(
      <McpComponent
        id="mcp-server"
        value={{ name: "broken-server", config: {} }}
        disabled={false}
        handleOnNewValue={jest.fn()}
        editNode={false}
        nodeId="MCPTools-1"
        nodeClass={nodeClass}
        handleNodeClass={jest.fn()}
      />,
    );

    expect(screen.getByTestId("mcp-server-error")).toHaveTextContent(
      "Connection refused by MCP server",
    );

    await user.click(screen.getByTestId("refresh-mcp-server-button"));

    await waitFor(() => {
      expect(mockRefetchMCPServers).toHaveBeenCalled();
      expect(mockMutateTemplate).toHaveBeenCalledWith(
        { name: "broken-server", config: {} },
        "MCPTools-1",
        expect.any(Object),
        expect.any(Function),
        mockPostTemplateValue,
        mockSetErrorData,
        "mcp_server",
        expect.any(Function),
        false,
        true,
      );
    });

    expect(mockMutateTemplate.mock.calls[0][3]).toEqual(expect.any(Function));
  });
});

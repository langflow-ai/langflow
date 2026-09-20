import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import type { MCPServerType } from "@/types/mcp";
import AddMcpServerModal from "..";

const mockPatchMCPServer = jest.fn();
const mockAddMCPServer = jest.fn();
const mockSetQueryData = jest.fn();

jest.mock("nanoid", () => ({
  nanoid: () => "test-id",
}));

jest.mock("react-router-dom", () => ({
  useLocation: () => ({ pathname: "/settings/mcp-servers" }),
}));

jest.mock("@tanstack/react-query", () => ({
  useQueryClient: () => ({
    setQueryData: mockSetQueryData,
  }),
}));

jest.mock("@/controllers/API/queries/mcp/use-add-mcp-server", () => ({
  useAddMCPServer: () => ({
    mutateAsync: mockAddMCPServer,
    isPending: false,
  }),
}));

jest.mock("@/controllers/API/queries/mcp/use-patch-mcp-server", () => ({
  usePatchMCPServer: () => ({
    mutateAsync: mockPatchMCPServer,
    isPending: false,
  }),
}));

jest.mock("@/components/common/genericIconComponent", () => ({
  ForwardedIconComponent: ({ name }: { name: string }) => <span>{name}</span>,
}));

jest.mock("@/customization/components/custom-link", () => ({
  CustomLink: ({ children }: { children: ReactNode }) => (
    <span>{children}</span>
  ),
}));

jest.mock("@/components/ui/button", () => ({
  Button: ({
    children,
    onClick,
    ...props
  }: {
    children: ReactNode;
    onClick?: () => void;
  }) => (
    <button onClick={onClick} {...props}>
      {children}
    </button>
  ),
}));

jest.mock("@/components/ui/input", () => ({
  Input: ({
    value,
    onChange,
    "data-testid": dataTestId,
    placeholder,
    disabled,
    id,
    "aria-invalid": ariaInvalid,
    "aria-describedby": ariaDescribedby,
  }: {
    value?: string;
    onChange?: (event: { target: { value: string } }) => void;
    "data-testid"?: string;
    placeholder?: string;
    disabled?: boolean;
    id?: string;
    "aria-invalid"?: boolean;
    "aria-describedby"?: string;
  }) => (
    <input
      value={value}
      placeholder={placeholder}
      data-testid={dataTestId}
      disabled={disabled}
      id={id}
      aria-invalid={ariaInvalid}
      aria-describedby={ariaDescribedby}
      onChange={(event) =>
        onChange?.({ target: { value: event.target.value } })
      }
    />
  ),
}));

jest.mock("@/components/ui/label", () => ({
  Label: ({ children }: { children: ReactNode }) => <label>{children}</label>,
}));

jest.mock("@/components/ui/textarea", () => ({
  Textarea: ({
    value,
    onChange,
    "data-testid": dataTestId,
    id,
    "aria-invalid": ariaInvalid,
    "aria-describedby": ariaDescribedby,
  }: {
    value?: string;
    onChange?: (event: { target: { value: string } }) => void;
    "data-testid"?: string;
    id?: string;
    "aria-invalid"?: boolean;
    "aria-describedby"?: string;
  }) => (
    <textarea
      value={value}
      data-testid={dataTestId}
      id={id}
      aria-invalid={ariaInvalid}
      aria-describedby={ariaDescribedby}
      onChange={(event) =>
        onChange?.({ target: { value: event.target.value } })
      }
    />
  ),
}));

jest.mock(
  "@/components/core/parameterRenderComponent/components/inputListComponent",
  () => ({
    __esModule: true,
    default: () => <div data-testid="stdio-args-input" />,
  }),
);

jest.mock("@/components/ui/tabs-button", () => ({
  Tabs: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  TabsContent: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  TabsList: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  TabsTrigger: ({
    children,
    value,
  }: {
    children: ReactNode;
    value: string;
  }) => <button type="button">{children ?? value}</button>,
}));

jest.mock("@/modals/baseModal", () => {
  interface ChildrenProps {
    children: ReactNode;
  }

  interface BaseModalProps extends ChildrenProps {
    open?: boolean;
  }

  function MockBaseModal({ children, open }: BaseModalProps) {
    if (!open) {
      return null;
    }

    return <div data-testid="base-modal">{children}</div>;
  }

  MockBaseModal.Trigger = ({ children }: ChildrenProps) => (
    <div>{children}</div>
  );
  MockBaseModal.Content = ({ children }: ChildrenProps) => (
    <div>{children}</div>
  );
  MockBaseModal.Header = ({
    children,
    description,
  }: ChildrenProps & { description?: ReactNode }) => (
    <div>
      <h2>{children}</h2>
      {description}
    </div>
  );

  return { __esModule: true, default: MockBaseModal };
});

jest.mock(
  "@/modals/IOModal/components/IOFieldView/components/key-pair-input",
  () => ({
    __esModule: true,
    default: ({
      onChange,
      testId,
    }: {
      onChange: (value: Array<unknown>) => void;
      testId?: string;
    }) => (
      <button
        type="button"
        data-testid={`${testId}-clear`}
        onClick={() => onChange([])}
      >
        Clear
      </button>
    ),
  }),
);

jest.mock(
  "@/modals/IOModal/components/IOFieldView/components/key-pair-input-with-variables",
  () => ({
    __esModule: true,
    default: ({
      onChange,
      testId,
      value,
      enableGlobalVariables,
    }: {
      onChange: (value: Array<unknown>) => void;
      testId?: string;
      value: Array<unknown>;
      enableGlobalVariables?: boolean;
    }) => (
      <button
        type="button"
        data-testid={`${testId}-clear`}
        data-enable-global-variables={enableGlobalVariables}
        data-value={JSON.stringify(value)}
        onClick={() => onChange([])}
      >
        Clear
      </button>
    ),
  }),
);

describe("AddMcpServerModal", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockPatchMCPServer.mockResolvedValue(undefined);
    mockAddMCPServer.mockResolvedValue(undefined);
  });

  it("sends empty headers and env when deleting the last remaining HTTP entries", async () => {
    const user = userEvent.setup();
    const initialData: MCPServerType = {
      name: "my-server",
      url: "http://host/sse",
      headers: { Authorization: "Bearer token" },
      env: { TOKEN: "secret" },
    };

    render(
      <AddMcpServerModal
        open={true}
        setOpen={jest.fn()}
        initialData={initialData}
      />,
    );

    await user.click(screen.getByTestId("http-headers-clear"));
    await user.click(screen.getByTestId("http-env-clear"));
    await user.click(screen.getByTestId("add-mcp-server-button"));

    expect(mockPatchMCPServer).toHaveBeenCalledWith({
      name: "my-server",
      url: "http://host/sse",
      headers: {},
      env: {},
    });
  });

  it("locks the HTTP server name field when editing an existing server", () => {
    const initialData: MCPServerType = {
      name: "my-server",
      url: "http://host/sse",
    };

    render(
      <AddMcpServerModal
        open={true}
        setOpen={jest.fn()}
        initialData={initialData}
      />,
    );

    // The name is the server's immutable identifier, so it cannot be edited.
    expect(screen.getByTestId("http-name-input")).toBeDisabled();
  });

  it("locks the STDIO server name field when editing an existing server", () => {
    const initialData: MCPServerType = {
      name: "my-server",
      command: "uvx",
      args: ["mcp-server"],
    };

    render(
      <AddMcpServerModal
        open={true}
        setOpen={jest.fn()}
        initialData={initialData}
      />,
    );

    expect(screen.getByTestId("stdio-name-input")).toBeDisabled();
  });

  it("persists global-variable-aware headers when editing a STDIO server", async () => {
    const user = userEvent.setup();
    const initialData: MCPServerType = {
      name: "my-server",
      command: "uvx",
      args: ["mcp-proxy", "http://host/mcp"],
      headers: {
        "X-Langflow-Global-Var-OPENRAG_INGEST_TOKEN": "OPENRAG_INGEST_TOKEN",
      },
    };

    render(
      <AddMcpServerModal
        open={true}
        setOpen={jest.fn()}
        initialData={initialData}
      />,
    );

    expect(screen.getByTestId("stdio-headers-clear")).toHaveAttribute(
      "data-enable-global-variables",
      "true",
    );
    expect(screen.getByTestId("stdio-headers-clear")).toHaveAttribute(
      "data-value",
      expect.stringContaining("OPENRAG_INGEST_TOKEN"),
    );

    await user.click(screen.getByTestId("add-mcp-server-button"));

    expect(mockPatchMCPServer).toHaveBeenCalledWith({
      name: "my-server",
      command: "uvx",
      args: ["mcp-proxy", "http://host/mcp"],
      headers: {
        "X-Langflow-Global-Var-OPENRAG_INGEST_TOKEN": "OPENRAG_INGEST_TOKEN",
      },
    });
  });

  it("sends empty headers when deleting the last STDIO header", async () => {
    const user = userEvent.setup();
    const initialData: MCPServerType = {
      name: "my-server",
      command: "uvx",
      args: ["mcp-server"],
      headers: { Authorization: "TOKEN_VARIABLE" },
    };

    render(
      <AddMcpServerModal
        open={true}
        setOpen={jest.fn()}
        initialData={initialData}
      />,
    );

    await user.click(screen.getByTestId("stdio-headers-clear"));
    await user.click(screen.getByTestId("add-mcp-server-button"));

    expect(mockPatchMCPServer).toHaveBeenCalledWith({
      name: "my-server",
      command: "uvx",
      args: ["mcp-server"],
      headers: {},
    });
  });

  it("patches the original server name when editing, instead of creating a duplicate", async () => {
    const user = userEvent.setup();
    const initialData: MCPServerType = {
      name: "my-server",
      command: "uvx",
      args: ["mcp-server"],
    };

    render(
      <AddMcpServerModal
        open={true}
        setOpen={jest.fn()}
        initialData={initialData}
      />,
    );

    // The name field is locked, so the update targets the original record.
    await user.click(screen.getByTestId("add-mcp-server-button"));

    expect(mockPatchMCPServer).toHaveBeenCalledTimes(1);
    expect(mockPatchMCPServer).toHaveBeenCalledWith(
      expect.objectContaining({ name: "my-server" }),
    );
    // The create (add) flow must never fire during an edit — that is what
    // produced the duplicate server.
    expect(mockAddMCPServer).not.toHaveBeenCalled();
  });

  it("associates the invalid-JSON error with the JSON textarea", async () => {
    const user = userEvent.setup();
    render(<AddMcpServerModal open={true} setOpen={jest.fn()} />);

    await user.type(screen.getByTestId("json-input"), "{{not valid json");
    await user.click(screen.getByTestId("add-mcp-server-button"));

    const banner = await screen.findByRole("alert");
    expect(banner).toHaveAttribute("id", "mcp-server-form-error");
    const textarea = screen.getByTestId("json-input");
    expect(textarea).toHaveAttribute("aria-invalid", "true");
    expect(textarea).toHaveAttribute(
      "aria-describedby",
      "mcp-server-form-error",
    );
  });

  it("marks the empty required STDIO field invalid and points it at the banner", async () => {
    const user = userEvent.setup();
    const initialData: MCPServerType = {
      name: "my-server",
      command: "uvx",
      args: [],
    };
    render(
      <AddMcpServerModal
        open={true}
        setOpen={jest.fn()}
        initialData={initialData}
      />,
    );

    await user.clear(screen.getByTestId("stdio-command-input"));
    await user.click(screen.getByTestId("add-mcp-server-button"));

    const banner = await screen.findByRole("alert");
    expect(banner).toHaveAttribute("id", "mcp-server-form-error");
    const command = screen.getByTestId("stdio-command-input");
    expect(command).toHaveAttribute("aria-invalid", "true");
    expect(command).toHaveAttribute(
      "aria-describedby",
      "mcp-server-form-error",
    );
    // The filled (locked) name field is not blamed for the error.
    expect(screen.getByTestId("stdio-name-input")).not.toHaveAttribute(
      "aria-invalid",
    );
    expect(mockPatchMCPServer).not.toHaveBeenCalled();
  });
});

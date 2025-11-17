import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { BrowserRouter } from "react-router-dom";
import McpServerTab from "../McpServerTab";

// Mock critical dependencies only
jest.mock("@/customization/hooks/use-custom-theme", () => ({
  __esModule: true,
  default: () => ({ dark: false }),
}));

jest.mock("@/customization/hooks/use-custom-is-local-connection", () => ({
  useCustomIsLocalConnection: () => true,
}));

jest.mock("@/customization/feature-flags", () => ({
  ENABLE_MCP_COMPOSER: true,
}));

jest.mock("@/stores/foldersStore", () => ({
  useFolderStore: () => "test-collection-id",
}));

// Mock the custom hook with minimal data
const mockUseMcpServer = jest.fn(
  (_params?: {
    projectId: string;
    folderName?: string;
    selectedPlatform?: string;
  }) => ({
    flowsMCPData: [],
    currentAuthSettings: { auth_type: "none" },
    isOAuthProject: false,
    composerUrlData: {},
    installedClients: [],
    installedMCPData: [],
    apiKey: "",
    isGeneratingApiKey: false,
    generateApiKey: jest.fn(),
    isCopied: false,
    copyToClipboard: jest.fn(),
    loadingMCP: [],
    installClient: jest.fn(),
    authModalOpen: false,
    setAuthModalOpen: jest.fn(),
    isLoading: false,
    handleOnNewValue: jest.fn(),
    handleAuthSave: jest.fn(),
    mcpJson: '{"mcpServers":{}}',
    hasAuthentication: false,
    isAuthApiKey: false,
    hasOAuthError: false,
  }),
);

jest.mock("../../hooks/useMcpServer", () => ({
  useMcpServer: (params: {
    projectId: string;
    folderName?: string;
    selectedPlatform?: string;
  }) => mockUseMcpServer(params),
}));

jest.mock("react-router-dom", () => ({
  ...jest.requireActual("react-router-dom"),
  useParams: () => ({ folderId: "test-folder-id" }),
}));

// Mock common components
jest.mock("@/components/common/genericIconComponent", () => ({
  ForwardedIconComponent: ({ name }: { name: string }) => (
    <span data-testid={`icon-${name}`}>{name}</span>
  ),
}));

jest.mock("@/components/common/shadTooltipComponent", () => ({
  __esModule: true,
  default: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

jest.mock(
  "@/components/core/parameterRenderComponent/components/ToolsComponent",
  () => ({
    __esModule: true,
    default: () => <div data-testid="tools-component" />,
  }),
);

jest.mock("@/components/ui/button", () => ({
  Button: ({
    children,
    onClick,
    unstyled,
    size,
    className,
    disabled,
  }: {
    children: React.ReactNode;
    onClick?: () => void;
    unstyled?: boolean;
    size?: string;
    className?: string;
    disabled?: boolean;
  }) => (
    <button onClick={onClick} className={className} disabled={disabled}>
      {children}
    </button>
  ),
}));

jest.mock("@/components/ui/tabs-button", () => ({
  Tabs: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  TabsList: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  TabsTrigger: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
}));

jest.mock("@/utils/utils", () => ({
  cn: (...args: (string | boolean | undefined)[]) =>
    args.filter(Boolean).join(" "),
  getOS: () => "macoslinux",
}));

jest.mock("@/modals/authModal", () => ({
  __esModule: true,
  default: () => null,
}));

// Mock all child components to test only McpServerTab logic
jest.mock("../McpFlowsSection", () => ({
  McpFlowsSection: () => <div data-testid="flows-section" />,
}));

jest.mock("../McpAuthSection", () => ({
  McpAuthSection: () => <div data-testid="auth-section" />,
}));

jest.mock("../McpJsonContent", () => ({
  McpJsonContent: () => <div data-testid="json-content" />,
}));

jest.mock("../McpAutoInstallContent", () => ({
  McpAutoInstallContent: () => <div data-testid="auto-install-content" />,
}));

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });

  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>{children}</BrowserRouter>
    </QueryClientProvider>
  );
};

describe("McpServerTab - Critical User Flows", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("renders without crashing", () => {
    render(<McpServerTab folderName="Test Project" />, {
      wrapper: createWrapper(),
    });

    expect(screen.getByTestId("mcp-server-title")).toBeInTheDocument();
  });

  it("passes projectId and folderName to hook", () => {
    render(<McpServerTab folderName="My Project" />, {
      wrapper: createWrapper(),
    });

    expect(mockUseMcpServer).toHaveBeenCalledWith(
      expect.objectContaining({
        projectId: "test-folder-id",
        folderName: "My Project",
      }),
    );
  });

  it("passes selectedPlatform to hook", () => {
    render(<McpServerTab folderName="Test" />, {
      wrapper: createWrapper(),
    });

    expect(mockUseMcpServer).toHaveBeenCalledWith(
      expect.objectContaining({
        selectedPlatform: expect.any(String),
      }),
    );
  });

  it("renders flows section", () => {
    render(<McpServerTab folderName="Test" />, {
      wrapper: createWrapper(),
    });

    expect(screen.getByTestId("flows-section")).toBeInTheDocument();
  });

  it("renders auth section when ENABLE_MCP_COMPOSER is true", () => {
    render(<McpServerTab folderName="Test" />, {
      wrapper: createWrapper(),
    });

    expect(screen.getByTestId("auth-section")).toBeInTheDocument();
  });

  it("shows Auto install by default when isLocalConnection is true", () => {
    render(<McpServerTab folderName="Test" />, {
      wrapper: createWrapper(),
    });

    expect(screen.getByTestId("auto-install-content")).toBeInTheDocument();
  });

  it("can switch from Auto install to JSON mode", () => {
    render(<McpServerTab folderName="Test" />, {
      wrapper: createWrapper(),
    });

    // Initially in Auto install mode
    expect(screen.getByTestId("auto-install-content")).toBeInTheDocument();

    // Switch to JSON
    const jsonButton = screen.getByText("JSON");
    fireEvent.click(jsonButton);

    expect(screen.getByTestId("json-content")).toBeInTheDocument();
    expect(
      screen.queryByTestId("auto-install-content"),
    ).not.toBeInTheDocument();
  });

  it("can switch from JSON back to Auto install mode", () => {
    render(<McpServerTab folderName="Test" />, {
      wrapper: createWrapper(),
    });

    // Switch to JSON first
    fireEvent.click(screen.getByText("JSON"));
    expect(screen.getByTestId("json-content")).toBeInTheDocument();

    // Switch back to Auto install
    fireEvent.click(screen.getByText("Auto install"));
    expect(screen.getByTestId("auto-install-content")).toBeInTheDocument();
    expect(screen.queryByTestId("json-content")).not.toBeInTheDocument();
  });

  it("shows OAuth error message when hasOAuthError is true", () => {
    mockUseMcpServer.mockReturnValue({
      ...mockUseMcpServer(),
      hasOAuthError: true,
      composerUrlData: { error_message: "OAuth config error" },
    });

    render(<McpServerTab folderName="Test" />, {
      wrapper: createWrapper(),
    });

    expect(
      screen.getByText("MCP Server Configuration Error"),
    ).toBeInTheDocument();
    expect(screen.getByText("OAuth config error")).toBeInTheDocument();
  });

  it("hides JSON and Auto-install content when OAuth error shown", () => {
    mockUseMcpServer.mockReturnValue({
      ...mockUseMcpServer(),
      hasOAuthError: true,
      composerUrlData: { error_message: "Error" },
    });

    render(<McpServerTab folderName="Test" />, {
      wrapper: createWrapper(),
    });

    expect(screen.queryByTestId("json-content")).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("auto-install-content"),
    ).not.toBeInTheDocument();
  });
});

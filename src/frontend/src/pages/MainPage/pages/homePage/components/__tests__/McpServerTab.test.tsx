import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type React from "react";
import { MemoryRouter } from "react-router-dom";
import McpServerTab from "../McpServerTab";

// Mock react-router-dom
jest.mock("react-router-dom", () => ({
  ...jest.requireActual("react-router-dom"),
  useParams: jest.fn(),
}));

// Mock constants
jest.mock("@/constants/constants", () => ({
  MAX_MCP_SERVER_NAME_LENGTH: 50,
}));

// Mock API controller
jest.mock("@/controllers/API", () => ({
  createApiKey: jest.fn(),
}));

// Mock API hooks
jest.mock("@/controllers/API/queries/mcp", () => ({
  useGetFlowsMCP: jest.fn(),
  usePatchFlowsMCP: jest.fn(),
}));

jest.mock("@/controllers/API/queries/mcp/use-get-composer-url", () => ({
  useGetProjectComposerUrl: jest.fn(),
}));

jest.mock("@/controllers/API/queries/mcp/use-get-installed-mcp", () => ({
  useGetInstalledMCP: jest.fn(),
}));

jest.mock("@/controllers/API/queries/mcp/use-patch-install-mcp", () => ({
  usePatchInstallMCP: jest.fn(),
}));

// Mock feature flags
jest.mock("@/customization/feature-flags", () => ({
  ENABLE_MCP_COMPOSER: true,
}));

// Mock custom hooks
jest.mock("@/customization/hooks/use-custom-is-local-connection", () => ({
  useCustomIsLocalConnection: jest.fn(),
}));

jest.mock("@/customization/hooks/use-custom-theme", () => ({
  __esModule: true,
  default: jest.fn(),
}));

jest.mock("@/customization/utils/custom-mcp-url", () => ({
  customGetMCPUrl: jest.fn(),
}));

// Mock stores
jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: jest.fn((selector) =>
    selector({
      setSuccessData: jest.fn(),
      setErrorData: jest.fn(),
    }),
  ),
}));

jest.mock("@/stores/authStore", () => ({
  __esModule: true,
  default: jest.fn((selector) =>
    selector({
      autoLogin: false,
    }),
  ),
}));

jest.mock("@/stores/foldersStore", () => ({
  useFolderStore: jest.fn((selector) =>
    selector({
      myCollectionId: "test-collection-id",
    }),
  ),
}));

// Mock utils
jest.mock("@/utils/mcpUtils", () => ({
  AUTH_METHODS: {
    apikey: { label: "API Key" },
    oauth: { label: "OAuth" },
    none: { label: "None" },
  },
}));

jest.mock("@/utils/stringManipulation", () => ({
  parseString: jest.fn((str: string) => str.toLowerCase().replace(/\s+/g, "_")),
  toSpaceCase: jest.fn((str: string) => str.replace(/_/g, " ")),
}));

jest.mock("@/utils/utils", () => ({
  cn: (...args: any[]) => args.filter(Boolean).join(" "),
  getOS: jest.fn(() => "macoslinux"),
}));

// Mock UI components
jest.mock("@/components/common/genericIconComponent", () => ({
  ForwardedIconComponent: ({ name, className, ...props }: any) => (
    <span data-testid={`icon-${name}`} className={className} {...props}>
      {name}
    </span>
  ),
}));

jest.mock("@/components/common/shadTooltipComponent", () => ({
  __esModule: true,
  default: ({ children, content, side }: any) => (
    <div data-testid="tooltip" data-content={content} data-side={side}>
      {children}
    </div>
  ),
}));

jest.mock(
  "@/components/core/parameterRenderComponent/components/ToolsComponent",
  () => ({
    __esModule: true,
    default: ({ value, handleOnNewValue, button_description }: any) => (
      <div data-testid="tools-component">
        <button
          data-testid="edit-tools-button"
          onClick={() =>
            handleOnNewValue({
              value: [
                ...value,
                {
                  id: "new-flow",
                  name: "New Flow",
                  description: "New Description",
                  status: true,
                },
              ],
            })
          }
        >
          {button_description}
        </button>
      </div>
    ),
  }),
);

jest.mock("@/components/ui/button", () => ({
  Button: ({
    children,
    onClick,
    disabled,
    loading,
    unstyled,
    ...props
  }: any) => (
    <button
      onClick={onClick}
      disabled={disabled || loading}
      data-loading={loading}
      data-unstyled={unstyled}
      {...props}
    >
      {children}
    </button>
  ),
}));

jest.mock("@/components/ui/tabs-button", () => ({
  Tabs: ({ children, value, onValueChange }: any) => (
    <div data-testid="tabs" data-value={value}>
      {children}
    </div>
  ),
  TabsList: ({ children }: any) => (
    <div data-testid="tabs-list">{children}</div>
  ),
  TabsTrigger: ({ children, value, ...props }: any) => (
    <button data-testid={`tab-trigger-${value}`} data-value={value} {...props}>
      {children}
    </button>
  ),
}));

// Mock react-syntax-highlighter
jest.mock("react-syntax-highlighter", () => ({
  Light: ({ children, CodeTag }: any) => (
    <div data-testid="syntax-highlighter">
      {CodeTag ? <CodeTag>{children}</CodeTag> : children}
    </div>
  ),
}));

// Mock AuthModal
jest.mock("@/modals/authModal", () => ({
  __esModule: true,
  default: ({ open, setOpen, onSave, authSettings }: any) => (
    <div data-testid="auth-modal" data-open={open}>
      <button data-testid="close-auth-modal" onClick={() => setOpen(false)}>
        Close
      </button>
      <button
        data-testid="save-auth-modal"
        onClick={() =>
          onSave({
            auth_type: "apikey",
          })
        }
      >
        Save
      </button>
    </div>
  ),
}));

const createTestWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>{children}</MemoryRouter>
    </QueryClientProvider>
  );
};

describe("McpServerTab", () => {
  const mockUseParams = require("react-router-dom").useParams;
  const mockCreateApiKey = require("@/controllers/API").createApiKey;
  const mockUseGetFlowsMCP =
    require("@/controllers/API/queries/mcp").useGetFlowsMCP;
  const mockUsePatchFlowsMCP =
    require("@/controllers/API/queries/mcp").usePatchFlowsMCP;
  const mockUseGetProjectComposerUrl =
    require("@/controllers/API/queries/mcp/use-get-composer-url").useGetProjectComposerUrl;
  const mockUseGetInstalledMCP =
    require("@/controllers/API/queries/mcp/use-get-installed-mcp").useGetInstalledMCP;
  const mockUsePatchInstallMCP =
    require("@/controllers/API/queries/mcp/use-patch-install-mcp").usePatchInstallMCP;
  const mockUseCustomIsLocalConnection =
    require("@/customization/hooks/use-custom-is-local-connection").useCustomIsLocalConnection;
  const mockUseTheme =
    require("@/customization/hooks/use-custom-theme").default;
  const mockCustomGetMCPUrl =
    require("@/customization/utils/custom-mcp-url").customGetMCPUrl;

  const defaultFlowsMCPData = {
    tools: [
      {
        id: "flow-1",
        action_name: "Action 1",
        action_description: "Description 1",
        name: "Flow 1",
        description: "Flow Description 1",
        mcp_enabled: true,
      },
    ],
    auth_settings: {
      auth_type: "none",
    },
  };

  beforeEach(() => {
    jest.clearAllMocks();
    mockUseParams.mockReturnValue({ folderId: "test-folder-id" });
    mockUseTheme.mockReturnValue({ dark: false });
    mockUseCustomIsLocalConnection.mockReturnValue(true);
    mockCustomGetMCPUrl.mockReturnValue("http://localhost:7860/api/v1/mcp");

    mockUseGetFlowsMCP.mockReturnValue({
      data: defaultFlowsMCPData,
      isLoading: false,
    });

    mockUsePatchFlowsMCP.mockReturnValue({
      mutate: jest.fn(),
      isPending: false,
    });

    mockUseGetProjectComposerUrl.mockReturnValue({
      data: null,
      isLoading: false,
    });

    mockUseGetInstalledMCP.mockReturnValue({
      data: [
        { name: "cursor", installed: false, available: true },
        { name: "claude", installed: false, available: true },
        { name: "windsurf", installed: false, available: true },
      ],
    });

    mockUsePatchInstallMCP.mockReturnValue({
      mutate: jest.fn(),
    });
  });

  describe("Rendering", () => {
    it("renders MCP Server title", () => {
      const TestWrapper = createTestWrapper();
      render(<McpServerTab folderName="Test Project" />, {
        wrapper: TestWrapper,
      });

      expect(screen.getByTestId("mcp-server-title")).toHaveTextContent(
        "MCP Server",
      );
    });

    it("renders description with documentation link", () => {
      const TestWrapper = createTestWrapper();
      render(<McpServerTab folderName="Test Project" />, {
        wrapper: TestWrapper,
      });

      const link = screen.getByRole("link", {
        name: /Projects as MCP Servers guide/i,
      });
      expect(link).toHaveAttribute(
        "href",
        "https://docs.langflow.org/mcp-server",
      );
      expect(link).toHaveAttribute("target", "_blank");
    });

    it("renders ToolsComponent with correct props", () => {
      const TestWrapper = createTestWrapper();
      render(<McpServerTab folderName="Test Project" />, {
        wrapper: TestWrapper,
      });

      expect(screen.getByTestId("tools-component")).toBeInTheDocument();
      expect(screen.getByTestId("edit-tools-button")).toHaveTextContent(
        "Edit Tools",
      );
    });

    it("renders JSON and Auto install mode tabs", () => {
      const TestWrapper = createTestWrapper();
      render(<McpServerTab folderName="Test Project" />, {
        wrapper: TestWrapper,
      });

      expect(screen.getByText("Auto install")).toBeInTheDocument();
      expect(screen.getByText("JSON")).toBeInTheDocument();
    });
  });

  describe("Authentication", () => {
    it("displays 'None (public)' when no authentication is configured", () => {
      const TestWrapper = createTestWrapper();
      render(<McpServerTab folderName="Test Project" />, {
        wrapper: TestWrapper,
      });

      expect(screen.getByText("None (public)")).toBeInTheDocument();
    });

    it("displays API Key auth when configured", () => {
      mockUseGetFlowsMCP.mockReturnValue({
        data: {
          ...defaultFlowsMCPData,
          auth_settings: { auth_type: "apikey" },
        },
        isLoading: false,
      });

      const TestWrapper = createTestWrapper();
      render(<McpServerTab folderName="Test Project" />, {
        wrapper: TestWrapper,
      });

      expect(screen.getByText("API Key")).toBeInTheDocument();
    });

    it("displays OAuth auth when configured", () => {
      mockUseGetFlowsMCP.mockReturnValue({
        data: {
          ...defaultFlowsMCPData,
          auth_settings: { auth_type: "oauth" },
        },
        isLoading: false,
      });

      mockUseGetProjectComposerUrl.mockReturnValue({
        data: { sse_url: "http://composer-url", uses_composer: true },
        isLoading: false,
      });

      const TestWrapper = createTestWrapper();
      render(<McpServerTab folderName="Test Project" />, {
        wrapper: TestWrapper,
      });

      expect(screen.getByText("OAuth")).toBeInTheDocument();
    });

    it("opens auth modal when Add Auth button is clicked", async () => {
      const user = userEvent.setup();
      const TestWrapper = createTestWrapper();
      render(<McpServerTab folderName="Test Project" />, {
        wrapper: TestWrapper,
      });

      const addAuthButton = screen.getByRole("button", { name: /Add Auth/i });
      await user.click(addAuthButton);

      expect(screen.getByTestId("auth-modal")).toHaveAttribute(
        "data-open",
        "true",
      );
    });

    it("opens auth modal when Edit Auth button is clicked", async () => {
      const user = userEvent.setup();
      mockUseGetFlowsMCP.mockReturnValue({
        data: {
          ...defaultFlowsMCPData,
          auth_settings: { auth_type: "apikey" },
        },
        isLoading: false,
      });

      const TestWrapper = createTestWrapper();
      render(<McpServerTab folderName="Test Project" />, {
        wrapper: TestWrapper,
      });

      const editAuthButton = screen.getByRole("button", { name: /Edit Auth/i });
      await user.click(editAuthButton);

      expect(screen.getByTestId("auth-modal")).toHaveAttribute(
        "data-open",
        "true",
      );
    });

    it("calls patchFlowsMCP when auth is saved", async () => {
      const user = userEvent.setup();
      const mockPatchFlowsMCP = jest.fn();
      mockUsePatchFlowsMCP.mockReturnValue({
        mutate: mockPatchFlowsMCP,
        isPending: false,
      });

      const TestWrapper = createTestWrapper();
      render(<McpServerTab folderName="Test Project" />, {
        wrapper: TestWrapper,
      });

      const addAuthButton = screen.getByRole("button", { name: /Add Auth/i });
      await user.click(addAuthButton);

      const saveButton = screen.getByTestId("save-auth-modal");
      await user.click(saveButton);

      expect(mockPatchFlowsMCP).toHaveBeenCalledWith(
        expect.objectContaining({
          auth_settings: { auth_type: "apikey" },
        }),
        expect.any(Object),
      );
    });
  });

  describe("API Key Generation", () => {
    it("generates API key when button is clicked", async () => {
      const user = userEvent.setup();
      mockCreateApiKey.mockResolvedValue({ api_key: "test-api-key-123" });
      mockUseGetFlowsMCP.mockReturnValue({
        data: {
          ...defaultFlowsMCPData,
          auth_settings: { auth_type: "apikey" },
        },
        isLoading: false,
      });

      const TestWrapper = createTestWrapper();
      render(<McpServerTab folderName="Test Project" />, {
        wrapper: TestWrapper,
      });

      // Switch to JSON mode
      const jsonTab = screen.getByText("JSON");
      await user.click(jsonTab);

      // Find and click the Generate API key button
      const generateButton = screen.getByText("Generate API key");
      await user.click(generateButton);

      await waitFor(() => {
        expect(mockCreateApiKey).toHaveBeenCalledWith(
          "MCP Server Test Project",
        );
      });
    });
  });

  describe("Mode Switching", () => {
    it("switches to JSON mode when clicked", async () => {
      const user = userEvent.setup();
      const TestWrapper = createTestWrapper();
      render(<McpServerTab folderName="Test Project" />, {
        wrapper: TestWrapper,
      });

      const jsonTab = screen.getByText("JSON");
      await user.click(jsonTab);

      expect(screen.getByTestId("syntax-highlighter")).toBeInTheDocument();
    });

    it("displays auto install mode by default for local connections", () => {
      const TestWrapper = createTestWrapper();
      render(<McpServerTab folderName="Test Project" />, {
        wrapper: TestWrapper,
      });

      expect(
        screen.getByRole("button", { name: /Cursor/i }),
      ).toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: /Claude/i }),
      ).toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: /Windsurf/i }),
      ).toBeInTheDocument();
    });

    it("displays JSON mode by default for non-local connections", () => {
      mockUseCustomIsLocalConnection.mockReturnValue(false);
      const TestWrapper = createTestWrapper();
      render(<McpServerTab folderName="Test Project" />, {
        wrapper: TestWrapper,
      });

      expect(screen.getByTestId("syntax-highlighter")).toBeInTheDocument();
    });
  });

  describe("Auto Install", () => {
    it("installs MCP server when installer button is clicked", async () => {
      const user = userEvent.setup();
      const mockPatchInstallMCP = jest.fn((_, callbacks) => {
        callbacks?.onSuccess?.();
      });
      mockUsePatchInstallMCP.mockReturnValue({
        mutate: mockPatchInstallMCP,
      });

      const TestWrapper = createTestWrapper();
      render(<McpServerTab folderName="Test Project" />, {
        wrapper: TestWrapper,
      });

      const cursorButton = screen.getByRole("button", { name: /Cursor/i });
      await user.click(cursorButton);

      expect(mockPatchInstallMCP).toHaveBeenCalledWith(
        { client: "cursor" },
        expect.objectContaining({
          onSuccess: expect.any(Function),
          onError: expect.any(Function),
        }),
      );
    });

    it("disables auto install buttons when not local connection", () => {
      mockUseCustomIsLocalConnection.mockReturnValue(false);
      const TestWrapper = createTestWrapper();
      render(<McpServerTab folderName="Test Project" />, {
        wrapper: TestWrapper,
      });

      // Switch to Auto install mode
      const autoInstallTab = screen.getByText("Auto install");
      fireEvent.click(autoInstallTab);

      const cursorButton = screen.getByRole("button", { name: /Cursor/i });
      expect(cursorButton).toBeDisabled();
    });

    it("shows warning when auto install is disabled for non-local connections", async () => {
      const user = userEvent.setup();
      mockUseCustomIsLocalConnection.mockReturnValue(false);
      const TestWrapper = createTestWrapper();
      render(<McpServerTab folderName="Test Project" />, {
        wrapper: TestWrapper,
      });

      // Switch to Auto install mode
      const autoInstallTab = screen.getByText("Auto install");
      await user.click(autoInstallTab);

      expect(
        screen.getByText(
          /One-click install is disabled because the Langflow server is not running on your local machine/i,
        ),
      ).toBeInTheDocument();
    });

    it("displays check icon for installed clients", () => {
      mockUseGetInstalledMCP.mockReturnValue({
        data: [
          { name: "cursor", installed: true, available: true },
          { name: "claude", installed: false, available: true },
          { name: "windsurf", installed: false, available: true },
        ],
      });

      const TestWrapper = createTestWrapper();
      render(<McpServerTab folderName="Test Project" />, {
        wrapper: TestWrapper,
      });

      expect(screen.getByTestId("icon-Check")).toBeInTheDocument();
    });
  });

  describe("Platform Selection", () => {
    it("renders platform tabs", async () => {
      const user = userEvent.setup();
      const TestWrapper = createTestWrapper();
      render(<McpServerTab folderName="Test Project" />, {
        wrapper: TestWrapper,
      });

      // Switch to JSON mode
      const jsonTab = screen.getByText("JSON");
      await user.click(jsonTab);

      expect(screen.getByTestId("tab-trigger-macoslinux")).toBeInTheDocument();
      expect(screen.getByTestId("tab-trigger-windows")).toBeInTheDocument();
      expect(screen.getByTestId("tab-trigger-wsl")).toBeInTheDocument();
    });
  });

  describe("Tools Management", () => {
    it("updates flows when tools are changed", async () => {
      const user = userEvent.setup();
      const mockPatchFlowsMCP = jest.fn();
      mockUsePatchFlowsMCP.mockReturnValue({
        mutate: mockPatchFlowsMCP,
        isPending: false,
      });

      const TestWrapper = createTestWrapper();
      render(<McpServerTab folderName="Test Project" />, {
        wrapper: TestWrapper,
      });

      const editButton = screen.getByTestId("edit-tools-button");
      await user.click(editButton);

      expect(mockPatchFlowsMCP).toHaveBeenCalled();
    });
  });

  describe("OAuth Error Handling", () => {
    it("displays error message when OAuth configuration has errors", async () => {
      const user = userEvent.setup();
      mockUseGetFlowsMCP.mockReturnValue({
        data: {
          ...defaultFlowsMCPData,
          auth_settings: { auth_type: "oauth" },
        },
        isLoading: false,
      });

      mockUseGetProjectComposerUrl.mockReturnValue({
        data: {
          error_message: "OAuth configuration error",
          uses_composer: true,
        },
        isLoading: false,
      });

      const TestWrapper = createTestWrapper();
      render(<McpServerTab folderName="Test Project" />, {
        wrapper: TestWrapper,
      });

      // Switch to JSON mode
      const jsonTab = screen.getByText("JSON");
      await user.click(jsonTab);

      expect(
        screen.getByText("MCP Server Configuration Error"),
      ).toBeInTheDocument();
      expect(screen.getByText("OAuth configuration error")).toBeInTheDocument();
    });
  });

  describe("Loading States", () => {
    it("shows loading state for auth when patching", () => {
      mockUseGetFlowsMCP.mockReturnValue({
        data: {
          ...defaultFlowsMCPData,
          auth_settings: { auth_type: "apikey" },
        },
        isLoading: false,
      });

      mockUsePatchFlowsMCP.mockReturnValue({
        mutate: jest.fn(),
        isPending: true,
      });

      const TestWrapper = createTestWrapper();
      render(<McpServerTab folderName="Test Project" />, {
        wrapper: TestWrapper,
      });

      expect(screen.getByText("Loading...")).toBeInTheDocument();
      expect(screen.getByTestId("icon-Loader2")).toBeInTheDocument();
    });

    it("shows loading state when waiting for composer", () => {
      mockUseGetFlowsMCP.mockReturnValue({
        data: {
          ...defaultFlowsMCPData,
          auth_settings: { auth_type: "oauth" },
        },
        isLoading: false,
      });

      mockUseGetProjectComposerUrl.mockReturnValue({
        data: null,
        isLoading: true,
      });

      const TestWrapper = createTestWrapper();
      render(<McpServerTab folderName="Test Project" />, {
        wrapper: TestWrapper,
      });

      expect(screen.getByText("Loading...")).toBeInTheDocument();
    });
  });

  describe("Dark Mode", () => {
    it("applies dark mode styles when dark theme is active", () => {
      mockUseTheme.mockReturnValue({ dark: true });
      const TestWrapper = createTestWrapper();
      render(<McpServerTab folderName="Test Project" />, {
        wrapper: TestWrapper,
      });

      expect(screen.getByTestId("mcp-server-title")).toBeInTheDocument();
    });
  });

  describe("Copy to Clipboard", () => {
    it("copies JSON configuration to clipboard", async () => {
      const user = userEvent.setup();
      const mockWriteText = jest.fn().mockResolvedValue(undefined);

      Object.defineProperty(navigator, "clipboard", {
        value: {
          writeText: mockWriteText,
        },
        writable: true,
        configurable: true,
      });

      const TestWrapper = createTestWrapper();
      render(<McpServerTab folderName="Test Project" />, {
        wrapper: TestWrapper,
      });

      // Switch to JSON mode
      const jsonTab = screen.getByText("JSON");
      await user.click(jsonTab);

      const copyButton = screen.getByTestId("icon-copy");
      await user.click(copyButton);

      await waitFor(() => {
        expect(mockWriteText).toHaveBeenCalled();
      });
    });
  });
});

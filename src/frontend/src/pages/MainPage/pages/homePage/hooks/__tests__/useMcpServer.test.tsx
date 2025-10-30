import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { ReactNode } from "react";
import { useMcpServer } from "../useMcpServer";

// Mock API
const mockGetMCP = jest.fn();
const mockPostInstall = jest.fn();
const mockGetComposerUrl = jest.fn();
const mockGetInstalledMCP = jest.fn();
const mockPatchFlowsMCP = jest.fn();
const mockPatchInstallMCP = jest.fn();
const mockCreateApiKey = jest.fn();

jest.mock("@/controllers/API", () => ({
  getMCP: () => mockGetMCP(),
  postInstall: (client: string, folderId: string) =>
    mockPostInstall(client, folderId),
  createApiKey: (name: string) => mockCreateApiKey(name),
}));

jest.mock("@/controllers/API/queries/mcp", () => ({
  useGetFlowsMCP: () => ({ data: mockGetMCP(), isLoading: false }),
  usePatchFlowsMCP: () => ({ mutate: mockPatchFlowsMCP, isPending: false }),
}));

jest.mock("@/controllers/API/queries/mcp/use-get-composer-url", () => ({
  useGetProjectComposerUrl: () => ({ data: mockGetComposerUrl() }),
}));

jest.mock("@/controllers/API/queries/mcp/use-get-installed-mcp", () => ({
  useGetInstalledMCP: () => ({ data: mockGetInstalledMCP() }),
}));

jest.mock("@/controllers/API/queries/mcp/use-patch-install-mcp", () => ({
  usePatchInstallMCP: () => ({ mutate: mockPatchInstallMCP }),
}));

jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: () => ({
    setSuccessData: jest.fn(),
    setErrorData: jest.fn(),
  }),
}));

jest.mock("@/stores/authStore", () => ({
  __esModule: true,
  default: () => ({
    apiKey: null,
    autoLogin: false,
  }),
}));

jest.mock("@/stores/foldersStore", () => ({
  useFolderStore: () => ({
    myCollectionId: "test-folder-id",
  }),
}));

jest.mock("@/customization/feature-flags", () => ({
  ENABLE_MCP_COMPOSER: false,
}));

jest.mock("@/customization/utils/custom-mcp-url", () => ({
  customGetMCPUrl: () => "http://test.com/api",
}));

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
};

describe("useMcpServer hook", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockGetMCP.mockReturnValue({
      tools: [],
      auth_settings: { auth_type: "none" },
    });
    mockGetInstalledMCP.mockReturnValue([]);
    mockGetComposerUrl.mockReturnValue(null);
  });

  it("initializes with empty data", () => {
    const { result } = renderHook(
      () =>
        useMcpServer({
          projectId: "test-project",
          folderName: "test-folder",
          selectedPlatform: "macoslinux",
        }),
      { wrapper: createWrapper() },
    );

    expect(result.current.flowsMCPData).toEqual([]);
    expect(result.current.installedMCPData).toEqual([]);
    expect(result.current.installedClients).toEqual([]);
    expect(result.current.loadingMCP).toEqual([]);
  });

  it("computes mcpJson correctly", () => {
    const { result } = renderHook(
      () =>
        useMcpServer({
          projectId: "test-project",
          folderName: "test-folder",
          selectedPlatform: "macoslinux",
        }),
      { wrapper: createWrapper() },
    );

    expect(result.current.mcpJson).toBeDefined();
    expect(typeof result.current.mcpJson).toBe("string");
    expect(result.current.mcpJson).toContain("mcpServers");
  });

  it("detects auth type correctly", () => {
    mockGetMCP.mockReturnValue({
      tools: [],
      auth_settings: { auth_type: "apikey" },
    });

    const { result } = renderHook(
      () =>
        useMcpServer({
          projectId: "test-project",
          folderName: "test-folder",
          selectedPlatform: "macoslinux",
        }),
      { wrapper: createWrapper() },
    );

    expect(result.current.authType).toBe("apikey");
    expect(result.current.hasAuthentication).toBe(true);
  });

  it("handles OAuth projects", () => {
    mockGetMCP.mockReturnValue({
      tools: [],
      auth_settings: { auth_type: "oauth" },
    });

    const { result } = renderHook(
      () =>
        useMcpServer({
          projectId: "test-project",
          folderName: "test-folder",
          selectedPlatform: "macoslinux",
        }),
      { wrapper: createWrapper() },
    );

    expect(result.current.authType).toBe("oauth");
    expect(result.current.hasAuthentication).toBe(true);
  });

  it("provides handleOnNewValue callback", () => {
    const { result } = renderHook(
      () =>
        useMcpServer({
          projectId: "test-project",
          folderName: "test-folder",
          selectedPlatform: "macoslinux",
        }),
      { wrapper: createWrapper() },
    );

    expect(typeof result.current.handleOnNewValue).toBe("function");
  });

  it("provides generateApiKey callback", () => {
    const { result } = renderHook(
      () =>
        useMcpServer({
          projectId: "test-project",
          folderName: "test-folder",
          selectedPlatform: "macoslinux",
        }),
      { wrapper: createWrapper() },
    );

    expect(typeof result.current.generateApiKey).toBe("function");
  });

  it("copies to clipboard", () => {
    Object.assign(navigator, {
      clipboard: {
        writeText: jest.fn().mockResolvedValue(undefined),
      },
    });

    const { result } = renderHook(
      () =>
        useMcpServer({
          projectId: "test-project",
          folderName: "test-folder",
          selectedPlatform: "macoslinux",
        }),
      { wrapper: createWrapper() },
    );

    act(() => {
      result.current.copyToClipboard("test content");
    });

    expect(navigator.clipboard.writeText).toHaveBeenCalledWith("test content");
  });
});

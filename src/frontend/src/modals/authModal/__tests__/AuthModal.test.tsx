import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TooltipProvider } from "@/components/ui/tooltip";
import AuthModal from "../index";

// Mock utilities
jest.mock("@/utils/mcpUtils", () => ({
  AUTH_METHODS_ARRAY: [
    { id: "none", label: "None" },
    { id: "apikey", label: "API Key" },
    { id: "oauth", label: "OAuth" },
  ],
}));

jest.mock("@/utils/stringManipulation", () => ({
  toSpaceCase: (str: string) => str.replace(/_/g, " "),
}));

// Mock UI components
jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name, className, ...props }: any) => (
    <span data-testid={`icon-${name}`} className={className} {...props}>
      {name}
    </span>
  ),
}));

// Mock custom link
jest.mock("@/customization/components/custom-link", () => ({
  CustomLink: ({ children, to, className }: any) => (
    <a href={to} className={className}>
      {children}
    </a>
  ),
}));

// Custom render function with TooltipProvider
const renderWithTooltip = (ui: React.ReactElement) => {
  return render(<TooltipProvider>{ui}</TooltipProvider>);
};

describe("AuthModal OAuth Port Synchronization", () => {
  const mockOnSave = jest.fn();
  const mockSetOpen = jest.fn();

  const defaultProps = {
    open: true,
    setOpen: mockSetOpen,
    onSave: mockOnSave,
    installedClients: [],
    autoInstall: false,
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("should auto-sync Server URL when Port is changed", async () => {
    const user = userEvent.setup();

    renderWithTooltip(<AuthModal {...defaultProps} />);

    // Select OAuth auth type
    const oauthRadio = screen.getByLabelText(/OAuth/i);
    await user.click(oauthRadio);

    // Fill in the Port field
    const portInput = screen.getByLabelText(/^Port$/i);
    await user.clear(portInput);
    await user.type(portInput, "9001");

    // Check that Server URL was auto-updated
    const serverUrlInput = screen.getByLabelText(/Server URL/i);
    expect(serverUrlInput).toHaveValue("http://localhost:9001");
  });

  it("should auto-sync Server URL when Host is changed", async () => {
    const user = userEvent.setup();

    renderWithTooltip(<AuthModal {...defaultProps} />);

    // Select OAuth auth type
    const oauthRadio = screen.getByLabelText(/OAuth/i);
    await user.click(oauthRadio);

    // Fill in the Host first
    const hostInput = screen.getByLabelText(/^Host$/i);
    await user.clear(hostInput);
    await user.type(hostInput, "example.com");

    // Then fill in the Port
    const portInput = screen.getByLabelText(/^Port$/i);
    await user.clear(portInput);
    await user.type(portInput, "8080");

    // Check that Server URL was auto-updated with both host and port
    const serverUrlInput = screen.getByLabelText(/Server URL/i);
    expect(serverUrlInput).toHaveValue("http://example.com:8080");
  });

  it("should auto-sync Callback URL when Port is changed", async () => {
    const user = userEvent.setup();

    renderWithTooltip(<AuthModal {...defaultProps} />);

    // Select OAuth auth type
    const oauthRadio = screen.getByLabelText(/OAuth/i);
    await user.click(oauthRadio);

    // Fill in the Port field
    const portInput = screen.getByLabelText(/^Port$/i);
    await user.clear(portInput);
    await user.type(portInput, "9001");

    // Check that Callback URL was auto-updated
    const callbackUrlInput = screen.getByLabelText(/Callback URL/i);
    expect(callbackUrlInput).toHaveValue(
      "http://localhost:9001/auth/idaas/callback",
    );
  });

  it("should auto-sync both Server URL and Callback URL when Host changes", async () => {
    const user = userEvent.setup();

    renderWithTooltip(<AuthModal {...defaultProps} />);

    // Select OAuth auth type
    const oauthRadio = screen.getByLabelText(/OAuth/i);
    await user.click(oauthRadio);

    // Fill in Host and Port
    const hostInput = screen.getByLabelText(/^Host$/i);
    await user.clear(hostInput);
    await user.type(hostInput, "192.168.1.100");

    const portInput = screen.getByLabelText(/^Port$/i);
    await user.clear(portInput);
    await user.type(portInput, "9002");

    // Verify Server URL
    const serverUrlInput = screen.getByLabelText(/Server URL/i);
    expect(serverUrlInput).toHaveValue("http://192.168.1.100:9002");

    // Verify Callback URL
    const callbackUrlInput = screen.getByLabelText(/Callback URL/i);
    expect(callbackUrlInput).toHaveValue(
      "http://192.168.1.100:9002/auth/idaas/callback",
    );
  });

  it("should save correctly synced OAuth settings", async () => {
    const user = userEvent.setup();

    renderWithTooltip(<AuthModal {...defaultProps} />);

    // Select OAuth auth type
    const oauthRadio = screen.getByLabelText(/OAuth/i);
    await user.click(oauthRadio);

    // Fill in OAuth fields
    const hostInput = screen.getByLabelText(/^Host$/i);
    await user.clear(hostInput);
    await user.type(hostInput, "localhost");

    const portInput = screen.getByLabelText(/^Port$/i);
    await user.clear(portInput);
    await user.type(portInput, "9001");

    const clientIdInput = screen.getByLabelText(/Client ID/i);
    await user.type(clientIdInput, "test-client-id");

    const clientSecretInput = screen.getByLabelText(/Client Secret/i);
    await user.type(clientSecretInput, "test-secret");

    const authUrlInput = screen.getByLabelText(/Authorization URL/i);
    await user.type(authUrlInput, "http://localhost:9001/auth/authorize");

    const tokenUrlInput = screen.getByLabelText(/Token URL/i);
    await user.type(tokenUrlInput, "http://localhost:9001/auth/token");

    // Click Save
    const saveButton = screen.getByRole("button", { name: /Save/i });
    await user.click(saveButton);

    // Verify onSave was called with correct synced data
    expect(mockOnSave).toHaveBeenCalledWith(
      expect.objectContaining({
        auth_type: "oauth",
        oauth_host: "localhost",
        oauth_port: "9001",
        oauth_server_url: "http://localhost:9001",
        oauth_callback_url: "http://localhost:9001/auth/idaas/callback",
        oauth_client_id: "test-client-id",
        oauth_client_secret: "test-secret",
        oauth_auth_url: "http://localhost:9001/auth/authorize",
        oauth_token_url: "http://localhost:9001/auth/token",
      }),
    );
  });

  it("should preserve existing Server URL if manually edited after port change", async () => {
    const user = userEvent.setup();

    renderWithTooltip(<AuthModal {...defaultProps} />);

    // Select OAuth auth type
    const oauthRadio = screen.getByLabelText(/OAuth/i);
    await user.click(oauthRadio);

    // Set port (auto-syncs Server URL)
    const portInput = screen.getByLabelText(/^Port$/i);
    await user.clear(portInput);
    await user.type(portInput, "9001");

    // Manually edit Server URL to something different
    const serverUrlInput = screen.getByLabelText(/Server URL/i);
    await user.clear(serverUrlInput);
    await user.type(serverUrlInput, "http://custom.example.com:9001");

    // Verify the manual edit is preserved
    expect(serverUrlInput).toHaveValue("http://custom.example.com:9001");

    // Change port again
    await user.clear(portInput);
    await user.type(portInput, "9002");

    // Server URL should now be auto-synced again
    expect(serverUrlInput).toHaveValue("http://localhost:9002");
  });

  it("should load existing auth settings correctly", () => {
    const existingAuthSettings = {
      auth_type: "oauth",
      oauth_host: "existing.host.com",
      oauth_port: "8080",
      oauth_server_url: "http://existing.host.com:8080",
      oauth_callback_path: "http://existing.host.com:8080/auth/idaas/callback",
      oauth_client_id: "existing-client",
      oauth_client_secret: "existing-secret",
      oauth_auth_url: "http://existing.host.com:8080/auth",
      oauth_token_url: "http://existing.host.com:8080/token",
      oauth_mcp_scope: "user",
      oauth_provider_scope: "openid",
    };

    renderWithTooltip(
      <AuthModal {...defaultProps} authSettings={existingAuthSettings} />,
    );

    // Verify fields are populated
    expect(screen.getByLabelText(/^Host$/i)).toHaveValue("existing.host.com");
    expect(screen.getByLabelText(/^Port$/i)).toHaveValue("8080");
    expect(screen.getByLabelText(/Server URL/i)).toHaveValue(
      "http://existing.host.com:8080",
    );
    expect(screen.getByLabelText(/Callback URL/i)).toHaveValue(
      "http://existing.host.com:8080/auth/idaas/callback",
    );
  });

  it("should not auto-sync if auth type is not OAuth", async () => {
    const user = userEvent.setup();

    renderWithTooltip(<AuthModal {...defaultProps} />);

    // Select API Key auth type
    const apikeyRadio = screen.getByLabelText(/API Key/i);
    await user.click(apikeyRadio);

    // OAuth fields should not be visible
    expect(screen.queryByLabelText(/^Port$/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/Server URL/i)).not.toBeInTheDocument();
  });
});

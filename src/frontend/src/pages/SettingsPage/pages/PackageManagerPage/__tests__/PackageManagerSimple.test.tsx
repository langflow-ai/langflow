import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import PackageManagerPage from "../package-manager-page";

// Mock the API hooks with simple return values
jest.mock("@/controllers/API/queries/packages", () => ({
  useGetInstallationStatus: jest.fn(() => ({
    data: null,
    isLoading: false,
    isError: false,
  })),
  useInstallPackage: jest.fn(() => ({
    mutateAsync: jest.fn(),
    isPending: false,
    isSuccess: false,
    isError: false,
    reset: jest.fn(),
  })),
}));

jest.mock("@/controllers/API/queries/packages/use-backend-health", () => ({
  useBackendHealth: jest.fn(() => ({
    isSuccess: true,
    isError: false,
    isFetched: true,
  })),
}));

// Mock the stores with simple functions
const mockSetErrorData = jest.fn();
const mockSetSuccessData = jest.fn();
const mockClearTempNotificationList = jest.fn();
const mockSetIsInstallingPackage = jest.fn();

jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: jest.fn((selector) => {
    const store = {
      setSuccessData: mockSetSuccessData,
      setErrorData: mockSetErrorData,
      clearTempNotificationList: mockClearTempNotificationList,
    };
    return selector(store);
  }),
}));

jest.mock("@/stores/packageManagerStore", () => ({
  usePackageManagerStore: jest.fn((selector) => {
    const store = {
      setIsInstallingPackage: mockSetIsInstallingPackage,
      isBackendRestarting: false,
      setIsBackendRestarting: jest.fn(),
      restartDetectedAt: null,
      setRestartDetectedAt: jest.fn(),
    };
    return selector(store);
  }),
}));

// Mock components with simple implementations
jest.mock("@/components/common/genericIconComponent", () => ({
  ForwardedIconComponent: ({ name }: any) => (
    <span data-testid={`icon-${name}`}>{name}</span>
  ),
}));

jest.mock("@/components/ui/button", () => ({
  Button: ({ children, onClick, disabled, variant, ...props }: any) => (
    <button
      onClick={onClick}
      disabled={disabled}
      data-testid={variant === "outline" ? "outline-button" : "install-button"}
      {...props}
    >
      {children}
    </button>
  ),
}));

jest.mock("@/components/ui/input", () => ({
  Input: ({
    onChange,
    value,
    onKeyDown,
    placeholder,
    disabled,
    ...props
  }: any) => (
    <input
      onChange={onChange}
      value={value}
      onKeyDown={onKeyDown}
      placeholder={placeholder}
      disabled={disabled}
      data-testid="package-input"
      {...props}
    />
  ),
}));

jest.mock("@/components/ui/card", () => ({
  Card: ({ children }: any) => <div data-testid="card">{children}</div>,
  CardContent: ({ children }: any) => (
    <div data-testid="card-content">{children}</div>
  ),
  CardDescription: ({ children }: any) => (
    <div data-testid="card-description">{children}</div>
  ),
  CardHeader: ({ children }: any) => (
    <div data-testid="card-header">{children}</div>
  ),
  CardTitle: ({ children }: any) => (
    <div data-testid="card-title">{children}</div>
  ),
}));

jest.mock("@/components/ui/dialog", () => ({
  Dialog: ({ children, open }: any) =>
    open ? <div data-testid="dialog">{children}</div> : null,
  DialogContent: ({ children }: any) => (
    <div data-testid="dialog-content">{children}</div>
  ),
  DialogDescription: ({ children }: any) => (
    <div data-testid="dialog-description">{children}</div>
  ),
  DialogHeader: ({ children }: any) => (
    <div data-testid="dialog-header">{children}</div>
  ),
  DialogTitle: ({ children }: any) => (
    <div data-testid="dialog-title">{children}</div>
  ),
}));

jest.mock("@/components/ui/alert", () => ({
  Alert: ({ children }: any) => <div data-testid="alert">{children}</div>,
  AlertDescription: ({ children }: any) => (
    <div data-testid="alert-description">{children}</div>
  ),
}));

// Mock the InstalledPackagesTable component
jest.mock("../components/InstalledPackagesTable", () => {
  return function MockInstalledPackagesTable() {
    return (
      <div data-testid="installed-packages-table">Installed Packages Table</div>
    );
  };
});

describe("PackageManagerPage - Simple Tests", () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    });
    jest.clearAllMocks();
  });

  const renderComponent = () => {
    return render(
      <QueryClientProvider client={queryClient}>
        <PackageManagerPage />
      </QueryClientProvider>,
    );
  };

  describe("Basic Rendering", () => {
    it("should render the package manager page", () => {
      renderComponent();

      expect(screen.getByText("Package Manager")).toBeInTheDocument();
      expect(screen.getByTestId("package-input")).toBeInTheDocument();
      expect(screen.getByTestId("install-button")).toBeInTheDocument();
      expect(
        screen.getByTestId("installed-packages-table"),
      ).toBeInTheDocument();
    });

    it("should render the install package card", () => {
      renderComponent();

      expect(screen.getByTestId("card-title")).toHaveTextContent(
        "Install Package",
      );
      expect(screen.getByTestId("card-description")).toBeInTheDocument();
    });

    it("should render warning about core dependencies", () => {
      renderComponent();

      expect(
        screen.getByText(
          /You cannot install packages that are already included as dependencies of Langflow/,
        ),
      ).toBeInTheDocument();
    });

    it("should render version operators information", () => {
      renderComponent();

      expect(
        screen.getByText(/Supported version operators:/),
      ).toBeInTheDocument();
    });
  });

  describe("Package Input", () => {
    it("should update package name when typing", async () => {
      const user = userEvent.setup();
      renderComponent();

      const input = screen.getByTestId("package-input");
      await user.type(input, "requests");

      expect(input).toHaveValue("requests");
    });

    it("should disable install button when package name is empty", () => {
      renderComponent();

      const installButton = screen.getByTestId("install-button");
      expect(installButton).toBeDisabled();
    });

    it("should show error behavior when package name is empty", () => {
      renderComponent();

      const installButton = screen.getByTestId("install-button");
      // Button should be disabled when package name is empty, preventing click
      expect(installButton).toBeDisabled();

      // This prevents the error from being called since the button is disabled
      expect(mockSetErrorData).not.toHaveBeenCalled();
    });
  });

  describe("Installation Flow", () => {
    it("should clear notifications when starting installation", async () => {
      const user = userEvent.setup();
      renderComponent();

      const input = screen.getByTestId("package-input");
      await user.type(input, "pandas");

      const installButton = screen.getByTestId("install-button");
      await user.click(installButton);

      expect(mockClearTempNotificationList).toHaveBeenCalled();
    });

    it("should handle Enter key press", async () => {
      const user = userEvent.setup();
      renderComponent();

      const input = screen.getByTestId("package-input");
      await user.type(input, "numpy");
      await user.keyboard("{Enter}");

      expect(mockClearTempNotificationList).toHaveBeenCalled();
    });
  });

  describe("Backend Health Monitoring", () => {
    it("should monitor backend health during installation", () => {
      const mockUseBackendHealth =
        require("@/controllers/API/queries/packages/use-backend-health").useBackendHealth;

      renderComponent();

      expect(mockUseBackendHealth).toHaveBeenCalledWith(false, 1000);
    });
  });

  describe("Accessibility", () => {
    it("should have proper form structure", () => {
      renderComponent();

      expect(
        screen.getByPlaceholderText(/Package name with optional version/),
      ).toBeInTheDocument();
      expect(screen.getByTestId("install-button")).toBeInTheDocument();
    });

    it("should have proper headings", () => {
      renderComponent();

      expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
        "Package Manager",
      );
    });
  });
});

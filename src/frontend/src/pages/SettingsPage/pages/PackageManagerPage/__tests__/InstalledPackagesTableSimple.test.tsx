import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import InstalledPackagesTable from "../components/installed-package-table";

// Mock the API hooks
const mockRestoreLangflow = jest.fn();

jest.mock("@/controllers/API/queries/packages", () => ({
  useGetInstallationStatus: jest.fn(() => ({
    data: null,
    isLoading: false,
    isError: false,
  })),
  useGetInstalledPackages: jest.fn(() => ({
    data: [],
    isLoading: false,
    isError: false,
  })),
  useRestoreLangflow: jest.fn(() => ({
    mutateAsync: mockRestoreLangflow,
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

// Mock the stores
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

// Mock components
jest.mock("@/components/common/genericIconComponent", () => ({
  ForwardedIconComponent: ({ name }: any) => (
    <span data-testid={`icon-${name}`}>{name}</span>
  ),
}));

jest.mock("@/components/ui/button", () => ({
  Button: ({ children, onClick, disabled, variant }: any) => (
    <button
      onClick={onClick}
      disabled={disabled}
      data-testid={variant === "outline" ? "restore-button" : "confirm-button"}
    >
      {children}
    </button>
  ),
}));

jest.mock("@/components/ui/card", () => ({
  Card: ({ children }: any) => (
    <div data-testid="installed-packages-card">{children}</div>
  ),
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

jest.mock("@/components/ui/table", () => ({
  Table: ({ children }: any) => (
    <table data-testid="packages-table">{children}</table>
  ),
  TableBody: ({ children }: any) => (
    <tbody data-testid="table-body">{children}</tbody>
  ),
  TableCell: ({ children }: any) => (
    <td data-testid="table-cell">{children}</td>
  ),
  TableHead: ({ children }: any) => (
    <th data-testid="table-head">{children}</th>
  ),
  TableHeader: ({ children }: any) => (
    <thead data-testid="table-header">{children}</thead>
  ),
  TableRow: ({ children }: any) => <tr data-testid="table-row">{children}</tr>,
}));

// Mock BackendRestartDialog
jest.mock("@/components/common/BackendRestartDialog", () => {
  return function MockBackendRestartDialog() {
    return (
      <div data-testid="backend-restart-dialog">Backend Restart Dialog</div>
    );
  };
});

describe("InstalledPackagesTable - Simple Tests", () => {
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
        <InstalledPackagesTable />
      </QueryClientProvider>,
    );
  };

  describe("Empty State", () => {
    it("should not render card when no packages are installed", () => {
      const mockUseGetInstalledPackages =
        require("@/controllers/API/queries/packages").useGetInstalledPackages;
      mockUseGetInstalledPackages.mockReturnValue({
        data: [],
        isLoading: false,
        isError: false,
      });

      renderComponent();

      expect(
        screen.queryByTestId("installed-packages-card"),
      ).not.toBeInTheDocument();
    });
  });

  describe("With Packages", () => {
    beforeEach(() => {
      const mockUseGetInstalledPackages =
        require("@/controllers/API/queries/packages").useGetInstalledPackages;
      mockUseGetInstalledPackages.mockReturnValue({
        data: [
          { name: "pandas", version: "1.5.0" },
          { name: "numpy", version: "1.21.0" },
        ],
        isLoading: false,
        isError: false,
      });
    });

    it("should render card with packages when packages are installed", () => {
      renderComponent();

      expect(screen.getByTestId("installed-packages-card")).toBeInTheDocument();
      expect(screen.getByText("Installed Packages")).toBeInTheDocument();
      expect(
        screen.getByText("Manage your installed Python packages"),
      ).toBeInTheDocument();
    });

    it("should render restore button when packages are installed", () => {
      renderComponent();

      expect(screen.getByTestId("restore-button")).toBeInTheDocument();
      expect(screen.getByText("Restore Langflow")).toBeInTheDocument();
      expect(screen.getByTestId("icon-RotateCcw")).toBeInTheDocument();
    });

    it("should render packages table with correct headers", () => {
      renderComponent();

      expect(screen.getByTestId("packages-table")).toBeInTheDocument();
      expect(screen.getByText("Package Name")).toBeInTheDocument();
      expect(screen.getByText("Version")).toBeInTheDocument();
    });

    it("should display package information in table", () => {
      renderComponent();

      expect(screen.getByText("pandas")).toBeInTheDocument();
      expect(screen.getByText("1.5.0")).toBeInTheDocument();
      expect(screen.getByText("numpy")).toBeInTheDocument();
      expect(screen.getByText("1.21.0")).toBeInTheDocument();
    });

    it("should open restore confirmation dialog when restore button is clicked", async () => {
      const user = userEvent.setup();
      renderComponent();

      const restoreButton = screen.getByTestId("restore-button");
      await user.click(restoreButton);

      expect(screen.getByTestId("dialog")).toBeInTheDocument();
      expect(screen.getByText("Confirm Langflow Restore")).toBeInTheDocument();
    });

    it("should show restore consequences in confirmation dialog", async () => {
      const user = userEvent.setup();
      renderComponent();

      const restoreButton = screen.getByTestId("restore-button");
      await user.click(restoreButton);

      expect(
        screen.getByText("Remove ALL user-installed packages"),
      ).toBeInTheDocument();
      expect(
        screen.getByText("Restore Langflow to its original dependencies"),
      ).toBeInTheDocument();
      expect(screen.getByText("Restart the backend")).toBeInTheDocument();
      expect(screen.getByText("Clear the package list")).toBeInTheDocument();
    });

    it("should clear notifications when starting restore", async () => {
      const user = userEvent.setup();
      renderComponent();

      const restoreButton = screen.getByTestId("restore-button");
      await user.click(restoreButton);

      expect(mockClearTempNotificationList).toHaveBeenCalled();
    });
  });

  describe("Restore Button States", () => {
    it("should disable restore button during restore operation", () => {
      const mockUseGetInstalledPackages =
        require("@/controllers/API/queries/packages").useGetInstalledPackages;
      mockUseGetInstalledPackages.mockReturnValue({
        data: [{ name: "test-package", version: "1.0.0" }],
        isLoading: false,
        isError: false,
      });

      const mockUseRestoreLangflow =
        require("@/controllers/API/queries/packages").useRestoreLangflow;
      mockUseRestoreLangflow.mockReturnValue({
        mutateAsync: mockRestoreLangflow,
        isPending: true,
        isSuccess: false,
        isError: false,
        reset: jest.fn(),
      });

      renderComponent();

      const restoreButton = screen.getByTestId("restore-button");
      expect(restoreButton).toBeDisabled();
    });
  });

  describe("Backend Health Monitoring", () => {
    it("should monitor backend health during restore", () => {
      const mockUseBackendHealth =
        require("@/controllers/API/queries/packages/use-backend-health").useBackendHealth;

      renderComponent();

      expect(mockUseBackendHealth).toHaveBeenCalledWith(false, 2000);
    });
  });

  describe("Accessibility", () => {
    beforeEach(() => {
      const mockUseGetInstalledPackages =
        require("@/controllers/API/queries/packages").useGetInstalledPackages;
      mockUseGetInstalledPackages.mockReturnValue({
        data: [{ name: "test-package", version: "1.0.0" }],
        isLoading: false,
        isError: false,
      });
    });

    it("should have proper button structure", () => {
      renderComponent();

      const restoreButton = screen.getByTestId("restore-button");
      expect(restoreButton).toHaveTextContent("Restore Langflow");
      expect(screen.getByTestId("icon-RotateCcw")).toBeInTheDocument();
    });

    it("should have proper table structure", () => {
      renderComponent();

      expect(screen.getByTestId("packages-table")).toBeInTheDocument();
      expect(screen.getByTestId("table-header")).toBeInTheDocument();
      expect(screen.getByTestId("table-body")).toBeInTheDocument();
    });
  });
});

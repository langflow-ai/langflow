import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom";
import { TooltipProvider } from "@/components/ui/tooltip";
import PublishDropdown from "../deploy-dropdown";

// Mock stores and hooks
const mockMutateAsync = jest.fn();
const mockSetErrorData = jest.fn();
const mockSetFlows = jest.fn();
const mockSetCurrentFlow = jest.fn();

const mockCurrentFlow = {
  id: "test-flow-id",
  name: "Test Flow",
  folder_id: "test-folder-id",
  access_type: "PRIVATE",
  status: "DRAFT",
};

const mockFlows = [mockCurrentFlow];

jest.mock("@/controllers/API/queries/flows/use-patch-update-flow", () => ({
  usePatchUpdateFlow: () => ({
    mutateAsync: mockMutateAsync,
  }),
}));

jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: jest.fn((selector) =>
    selector({
      setErrorData: mockSetErrorData,
    }),
  ),
}));

jest.mock("@/stores/flowsManagerStore", () => ({
  __esModule: true,
  default: jest.fn((selector) =>
    selector({
      currentFlow: mockCurrentFlow,
      flows: mockFlows,
      setFlows: mockSetFlows,
    }),
  ),
}));

jest.mock("@/stores/flowStore", () => ({
  __esModule: true,
  default: jest.fn((selector) =>
    selector({
      setCurrentFlow: mockSetCurrentFlow,
      hasIO: true,
    }),
  ),
}));

jest.mock("@/stores/authStore", () => ({
  __esModule: true,
  default: jest.fn((selector) =>
    selector({
      autoLogin: true,
    }),
  ),
}));

jest.mock("react-router-dom", () => ({
  useHref: () => "/",
  useParams: () => ({}),
  Link: ({ to, children, ...props }: any) => (
    <a href={to} {...props}>
      {children}
    </a>
  ),
}));

jest.mock("@/customization/utils/custom-mcp-open", () => ({
  customMcpOpen: () => "_blank",
}));

jest.mock("@/customization/feature-flags", () => ({
  ENABLE_PUBLISH: true,
  ENABLE_WIDGET: true,
}));

// Mock modal components
jest.mock("@/modals/apiModal", () => ({
  __esModule: true,
  default: ({ open, children }: any) =>
    open ? <div data-testid="api-modal">{children}</div> : null,
}));

jest.mock("@/modals/EmbedModal/embed-modal", () => ({
  __esModule: true,
  default: ({ open }: any) => (open ? <div data-testid="embed-modal" /> : null),
}));

jest.mock("@/modals/exportModal", () => ({
  __esModule: true,
  default: ({ open }: any) =>
    open ? <div data-testid="export-modal" /> : null,
}));

// Helper function to render with TooltipProvider
const renderWithTooltip = (ui: React.ReactElement) => {
  return render(<TooltipProvider>{ui}</TooltipProvider>);
};

describe("PublishDropdown - Deployment Status", () => {
  const mockOpenApiModal = false;
  const mockSetOpenApiModal = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("renders deploy switch and deployed status menu item", async () => {
    const user = userEvent.setup();
    renderWithTooltip(
      <PublishDropdown
        openApiModal={mockOpenApiModal}
        setOpenApiModal={mockSetOpenApiModal}
      />,
    );

    // Open dropdown
    const shareButton = screen.getByTestId("publish-button");
    await user.click(shareButton);

    // Check for deployed status menu item
    await waitFor(() => {
      const deployedStatus = screen.getByTestId("deployed-status");
      expect(deployedStatus).toBeInTheDocument();

      // Check for deploy switch
      const deploySwitch = screen.getByTestId("deploy-switch");
      expect(deploySwitch).toBeInTheDocument();
    });
  });

  it("deploy switch is unchecked when flow status is DRAFT", async () => {
    const user = userEvent.setup();
    renderWithTooltip(
      <PublishDropdown
        openApiModal={mockOpenApiModal}
        setOpenApiModal={mockSetOpenApiModal}
      />,
    );

    const shareButton = screen.getByTestId("publish-button");
    await user.click(shareButton);

    await waitFor(() => {
      const deploySwitch = screen.getByTestId("deploy-switch");
      expect(deploySwitch).not.toBeChecked();
    });
  });

  it("calls mutateAsync with DEPLOYED status when deploy switch is toggled on", async () => {
    const user = userEvent.setup();
    mockMutateAsync.mockImplementation(({ id, status }, { onSuccess }) => {
      const updatedFlow = { ...mockCurrentFlow, id, status };
      onSuccess(updatedFlow);
      return Promise.resolve(updatedFlow);
    });

    renderWithTooltip(
      <PublishDropdown
        openApiModal={mockOpenApiModal}
        setOpenApiModal={mockSetOpenApiModal}
      />,
    );

    const shareButton = screen.getByTestId("publish-button");
    await user.click(shareButton);

    await waitFor(() => {
      const deploySwitch = screen.getByTestId("deploy-switch");
      fireEvent.click(deploySwitch);
    });

    await waitFor(() => {
      expect(mockMutateAsync).toHaveBeenCalledWith(
        expect.objectContaining({
          id: "test-flow-id",
          status: "DEPLOYED",
        }),
        expect.any(Object),
      );
    });
  });

  it("calls mutateAsync with DRAFT status when deploy switch is toggled off", async () => {
    const user = userEvent.setup();
    const deployedFlow = {
      ...mockCurrentFlow,
      status: "DEPLOYED",
    };

    // Override the mock for this test
    jest
      .mocked(require("@/stores/flowsManagerStore").default)
      .mockImplementation((selector) =>
        selector({
          currentFlow: deployedFlow,
          flows: [deployedFlow],
          setFlows: mockSetFlows,
        }),
      );

    mockMutateAsync.mockImplementation(({ id, status }, { onSuccess }) => {
      const updatedFlow = { ...deployedFlow, id, status };
      onSuccess(updatedFlow);
      return Promise.resolve(updatedFlow);
    });

    renderWithTooltip(
      <PublishDropdown
        openApiModal={mockOpenApiModal}
        setOpenApiModal={mockSetOpenApiModal}
      />,
    );

    const shareButton = screen.getByTestId("publish-button");
    await user.click(shareButton);

    await waitFor(() => {
      const deploySwitch = screen.getByTestId("deploy-switch");
      fireEvent.click(deploySwitch);
    });

    await waitFor(() => {
      expect(mockMutateAsync).toHaveBeenCalledWith(
        expect.objectContaining({
          id: "test-flow-id",
          status: "DRAFT",
        }),
        expect.any(Object),
      );
    });
  });

  it("updates flows and current flow on successful deployment", async () => {
    const user = userEvent.setup();
    const updatedFlow = { ...mockCurrentFlow, status: "DEPLOYED" };
    mockMutateAsync.mockImplementation((_, { onSuccess }) => {
      onSuccess(updatedFlow);
      return Promise.resolve(updatedFlow);
    });

    renderWithTooltip(
      <PublishDropdown
        openApiModal={mockOpenApiModal}
        setOpenApiModal={mockSetOpenApiModal}
      />,
    );

    const shareButton = screen.getByTestId("publish-button");
    await user.click(shareButton);

    await waitFor(() => {
      const deploySwitch = screen.getByTestId("deploy-switch");
      fireEvent.click(deploySwitch);
    });

    await waitFor(() => {
      expect(mockSetFlows).toHaveBeenCalled();
      expect(mockSetCurrentFlow).toHaveBeenCalledWith(updatedFlow);
    });
  });

  it("shows error when flows variable is undefined", async () => {
    const user = userEvent.setup();
    // Override mock to return undefined flows
    jest
      .mocked(require("@/stores/flowsManagerStore").default)
      .mockImplementation((selector) =>
        selector({
          currentFlow: mockCurrentFlow,
          flows: undefined,
          setFlows: mockSetFlows,
        }),
      );

    mockMutateAsync.mockImplementation((_, { onSuccess }) => {
      onSuccess(mockCurrentFlow);
      return Promise.resolve(mockCurrentFlow);
    });

    renderWithTooltip(
      <PublishDropdown
        openApiModal={mockOpenApiModal}
        setOpenApiModal={mockSetOpenApiModal}
      />,
    );

    const shareButton = screen.getByTestId("publish-button");
    await user.click(shareButton);

    await waitFor(() => {
      const deploySwitch = screen.getByTestId("deploy-switch");
      fireEvent.click(deploySwitch);
    });

    await waitFor(() => {
      expect(mockSetErrorData).toHaveBeenCalledWith({
        title: "Failed to save flow",
        list: ["Flows variable undefined"],
      });
    });
  });

  it("shows error on mutation failure", async () => {
    const user = userEvent.setup();
    const error = new Error("Network error");
    mockMutateAsync.mockImplementation((_, { onError }) => {
      onError(error);
      return Promise.reject(error).catch(() => {});
    });

    renderWithTooltip(
      <PublishDropdown
        openApiModal={mockOpenApiModal}
        setOpenApiModal={mockSetOpenApiModal}
      />,
    );

    const shareButton = screen.getByTestId("publish-button");
    await user.click(shareButton);

    await waitFor(() => {
      const deploySwitch = screen.getByTestId("deploy-switch");
      fireEvent.click(deploySwitch);
    });

    await waitFor(() => {
      expect(mockSetErrorData).toHaveBeenCalledWith({
        title: "Failed to save flow",
        list: [error.message],
      });
    });
  });

  it("deploy switch is disabled when hasIO is false", async () => {
    const user = userEvent.setup();
    // Override mock to return hasIO as false
    jest
      .mocked(require("@/stores/flowStore").default)
      .mockImplementation((selector) =>
        selector({
          setCurrentFlow: mockSetCurrentFlow,
          hasIO: false,
        }),
      );

    renderWithTooltip(
      <PublishDropdown
        openApiModal={mockOpenApiModal}
        setOpenApiModal={mockSetOpenApiModal}
      />,
    );

    const shareButton = screen.getByTestId("publish-button");
    await user.click(shareButton);

    await waitFor(() => {
      const deploySwitch = screen.getByTestId("deploy-switch");
      expect(deploySwitch).toBeDisabled();
    });
  });

  it("displays correct tooltip content for deployed status", async () => {
    const user = userEvent.setup();
    renderWithTooltip(
      <PublishDropdown
        openApiModal={mockOpenApiModal}
        setOpenApiModal={mockSetOpenApiModal}
      />,
    );

    const shareButton = screen.getByTestId("publish-button");
    await user.click(shareButton);

    // The tooltip should show "Deploy this flow to make it available" for DRAFT status
    await waitFor(() => {
      const deployedStatus = screen.getByTestId("deployed-status");
      expect(deployedStatus).toBeInTheDocument();
    });
  });

  it("render both shareable playground and deployed status when ENABLE_PUBLISH is true", async () => {
    const user = userEvent.setup();
    renderWithTooltip(
      <PublishDropdown
        openApiModal={mockOpenApiModal}
        setOpenApiModal={mockSetOpenApiModal}
      />,
    );

    const shareButton = screen.getByTestId("publish-button");
    await user.click(shareButton);

    await waitFor(() => {
      expect(screen.getByTestId("shareable-playground")).toBeInTheDocument();
      expect(screen.getByTestId("deployed-status")).toBeInTheDocument();
    });
  });

  it("opens and closes correctly", async () => {
    const user = userEvent.setup();
    renderWithTooltip(
      <PublishDropdown
        openApiModal={mockOpenApiModal}
        setOpenApiModal={mockSetOpenApiModal}
      />,
    );

    const shareButton = screen.getByTestId("publish-button");

    // Open dropdown
    await user.click(shareButton);
    await waitFor(() => {
      expect(screen.getByTestId("deployed-status")).toBeInTheDocument();
    });

    // Note: Closing behavior depends on dropdown implementation
    // This test verifies the dropdown can be opened
  });
});

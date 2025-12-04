import { render, screen } from "@testing-library/react";
import HeaderComponent from "../index";

interface IconProps {
  name: string;
  className?: string;
  [key: string]: unknown;
}

interface TooltipProps {
  children: React.ReactNode;
  content: string;
  [key: string]: unknown;
}

interface ButtonProps {
  children?: React.ReactNode;
  onClick?: () => void;
  variant?: string;
  size?: string;
  className?: string;
  "data-testid"?: string;
  loading?: boolean;
  unstyled?: boolean;
  [key: string]: unknown;
}

interface InputProps {
  value?: string;
  onChange?: (e: React.ChangeEvent<HTMLInputElement>) => void;
  placeholder?: string;
  [key: string]: unknown;
}

interface SidebarProps {
  children: React.ReactNode;
}

interface DeleteModalProps {
  children?: React.ReactNode;
  onConfirm?: () => void;
  description?: string;
  note?: string;
  "data-testid"?: string;
  [key: string]: unknown;
}

interface AlertStoreSelector {
  setSuccessData: jest.Mock;
}

// Mock dependencies
jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name, className, ...props }: IconProps) => (
    <div data-testid={`icon-${name}`} className={className} {...props}>
      {name}
    </div>
  ),
}));

jest.mock("@/components/common/shadTooltipComponent", () => ({
  __esModule: true,
  default: ({ children, content }: TooltipProps) => (
    <div data-testid="tooltip" data-content={content}>
      {children}
    </div>
  ),
}));

jest.mock("@/components/ui/button", () => ({
  Button: ({
    children,
    onClick,
    variant,
    size,
    className,
    "data-testid": testId,
    loading,
    unstyled,
    ...props
  }: ButtonProps) => (
    <button
      onClick={onClick}
      data-variant={variant}
      data-size={size}
      className={className}
      data-testid={testId}
      data-loading={loading}
      data-unstyled={unstyled}
      {...props}
    >
      {children}
    </button>
  ),
}));

jest.mock("@/components/ui/input", () => ({
  Input: ({ value, onChange, placeholder, ...props }: InputProps) => (
    <input
      value={value}
      onChange={onChange}
      placeholder={placeholder}
      {...props}
    />
  ),
}));

jest.mock("@/components/ui/sidebar", () => ({
  SidebarTrigger: ({ children }: SidebarProps) => (
    <button data-testid="sidebar-trigger">{children}</button>
  ),
}));

jest.mock("@/modals/deleteConfirmationModal", () => ({
  __esModule: true,
  default: ({
    children,
    onConfirm,
    description,
    note,
    "data-testid": testId,
  }: DeleteModalProps) => (
    <div
      data-testid={testId || "delete-confirmation-modal"}
      data-description={description}
    >
      {children}
      <button onClick={onConfirm} data-testid="modal-confirm">
        Confirm Delete
      </button>
    </div>
  ),
}));

jest.mock("@/controllers/API/queries/flows/use-delete-delete-flows", () => ({
  useDeleteDeleteFlows: () => ({
    mutate: jest.fn(),
    isPending: false,
  }),
}));

jest.mock("@/controllers/API/queries/flows/use-get-download-flows", () => ({
  useGetDownloadFlows: () => ({
    mutate: jest.fn(),
    isPending: false,
  }),
}));

jest.mock("@/stores/alertStore", () => ({
  __esModule: true,
  default: (selector: (arg: AlertStoreSelector) => unknown) =>
    selector({
      setSuccessData: jest.fn(),
    }),
}));

jest.mock("@/customization/feature-flags", () => ({
  ENABLE_MCP: false,
}));

describe("HeaderComponent - TabIndex Behavior with Bulk Actions", () => {
  const defaultProps = {
    flowType: "flows" as const,
    setFlowType: jest.fn(),
    view: "list" as const,
    setView: jest.fn(),
    setNewProjectModal: jest.fn(),
    setSearch: jest.fn(),
    isEmptyFolder: false,
    selectedFlows: [],
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe("DeleteConfirmationModal TabIndex - No Selections", () => {
    it("should hide bulk actions container when selectedFlows is empty", () => {
      const { container } = render(
        <HeaderComponent {...defaultProps} selectedFlows={[]} />,
      );

      // Bulk actions container should have w-0 and opacity-0 classes
      const bulkActionsContainer = container.querySelector(
        "[class*='w-0'][class*='opacity-0']",
      );
      expect(bulkActionsContainer).toBeInTheDocument();
    });
  });

  describe("DeleteConfirmationModal TabIndex - With Selections", () => {
    it("should apply normal tabIndex={0} to delete button when selections exist", () => {
      render(<HeaderComponent {...defaultProps} selectedFlows={["flow1"]} />);

      const deleteBtn = screen.getByTestId("delete-bulk-btn");
      expect(deleteBtn).toBeInTheDocument();
      expect(deleteBtn).toHaveAttribute("tabindex", "0");
    });

    it("should show download button when flows are selected", () => {
      render(
        <HeaderComponent
          {...defaultProps}
          selectedFlows={["flow1", "flow2"]}
        />,
      );

      const downloadBtn = screen.getByTestId("download-bulk-btn");
      expect(downloadBtn).toBeInTheDocument();
      expect(downloadBtn).toHaveAttribute("tabindex", "0");
    });
  });

  describe("Accessibility - TabIndex Impact", () => {
    it("should not interfere with other interactive elements when bulk actions are hidden", () => {
      render(<HeaderComponent {...defaultProps} selectedFlows={[]} />);

      // New Flow button should still be accessible
      const newFlowBtn = screen.getByTestId("new-project-btn");
      expect(newFlowBtn).toBeInTheDocument();
      expect(newFlowBtn).not.toHaveAttribute("tabindex", "-1");
    });

    it("should not interfere with other interactive elements when bulk actions are visible", () => {
      render(<HeaderComponent {...defaultProps} selectedFlows={["flow1"]} />);

      // New Flow button should still be accessible
      const newFlowBtn = screen.getByTestId("new-project-btn");
      expect(newFlowBtn).toBeInTheDocument();
      expect(newFlowBtn).not.toHaveAttribute("tabindex", "-1");

      // Delete button should be accessible
      const deleteBtn = screen.getByTestId("delete-bulk-btn");
      expect(deleteBtn).not.toHaveAttribute("tabindex", "-1");
    });
  });
});

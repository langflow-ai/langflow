import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import DisconnectWarning from "../components/DisconnectWarning";

// Mock ForwardedIconComponent
jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: ({ name, className }: { name: string; className?: string }) => (
    <span data-testid={`icon-${name}`} className={className}>
      {name}
    </span>
  ),
}));

const defaultProps = {
  show: true,
  message: "Test warning message",
  onCancel: jest.fn(),
  onConfirm: jest.fn(),
  isLoading: false,
};

describe("DisconnectWarning", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe("Rendering", () => {
    it("should render the warning message when show is true", () => {
      render(<DisconnectWarning {...defaultProps} />);

      expect(screen.getByText("Warning")).toBeInTheDocument();
      expect(screen.getByText("Test warning message")).toBeInTheDocument();
    });

    it("should render Cancel and Confirm buttons", () => {
      render(<DisconnectWarning {...defaultProps} />);

      expect(
        screen.getByRole("button", { name: /cancel/i }),
      ).toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: /confirm/i }),
      ).toBeInTheDocument();
    });

    it("should render the warning icon", () => {
      render(<DisconnectWarning {...defaultProps} />);

      expect(screen.getByTestId("icon-Circle")).toBeInTheDocument();
    });

    it("should apply opacity-0 class when show is false", () => {
      const { container } = render(
        <DisconnectWarning {...defaultProps} show={false} />,
      );

      const wrapper = container.firstChild as HTMLElement;
      expect(wrapper).toHaveClass("opacity-0");
      expect(wrapper).toHaveClass("pointer-events-none");
    });

    it("should apply opacity-100 class when show is true", () => {
      const { container } = render(<DisconnectWarning {...defaultProps} />);

      const wrapper = container.firstChild as HTMLElement;
      expect(wrapper).toHaveClass("opacity-100");
    });

    it("should apply custom className when provided", () => {
      const { container } = render(
        <DisconnectWarning {...defaultProps} className="custom-class" />,
      );

      const wrapper = container.firstChild as HTMLElement;
      expect(wrapper).toHaveClass("custom-class");
    });
  });

  describe("Button Interactions", () => {
    it("should call onCancel when Cancel button is clicked", async () => {
      const onCancel = jest.fn();
      const user = userEvent.setup();

      render(<DisconnectWarning {...defaultProps} onCancel={onCancel} />);

      const cancelButton = screen.getByRole("button", { name: /cancel/i });
      await user.click(cancelButton);

      expect(onCancel).toHaveBeenCalledTimes(1);
    });

    it("should call onConfirm when Confirm button is clicked", async () => {
      const onConfirm = jest.fn();
      const user = userEvent.setup();

      render(<DisconnectWarning {...defaultProps} onConfirm={onConfirm} />);

      const confirmButton = screen.getByRole("button", { name: /confirm/i });
      await user.click(confirmButton);

      expect(onConfirm).toHaveBeenCalledTimes(1);
    });
  });

  describe("Loading State", () => {
    it("should show loading state on Confirm button when isLoading is true", () => {
      render(<DisconnectWarning {...defaultProps} isLoading={true} />);

      const confirmButton = screen.getByRole("button", { name: /confirm/i });
      expect(confirmButton).toBeInTheDocument();
    });

    it("should not show loading state when isLoading is false", () => {
      render(<DisconnectWarning {...defaultProps} isLoading={false} />);

      const confirmButton = screen.getByRole("button", { name: /confirm/i });
      expect(confirmButton).toBeInTheDocument();
    });
  });

  describe("Different Messages", () => {
    it("should display provider-specific disconnect message", () => {
      const message =
        "Disconnecting an API key will disable all of the provider's models being used in a flow.";
      render(<DisconnectWarning {...defaultProps} message={message} />);

      expect(screen.getByText(message)).toBeInTheDocument();
    });

    it("should display provider-specific deactivate message", () => {
      const message =
        "Deactivating Ollama will disable all of the provider's models being used in a flow.";
      render(<DisconnectWarning {...defaultProps} message={message} />);

      expect(screen.getByText(message)).toBeInTheDocument();
    });
  });
});

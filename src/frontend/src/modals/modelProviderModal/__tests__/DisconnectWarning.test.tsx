import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { TooltipProvider } from "@/components/ui/tooltip";
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

const renderWarning = (
  props: Partial<typeof defaultProps> & { className?: string } = {},
) =>
  render(
    <TooltipProvider>
      <DisconnectWarning {...defaultProps} {...props} />
    </TooltipProvider>,
  );

function DisconnectWarningHarness() {
  const [show, setShow] = useState(false);
  return (
    <TooltipProvider>
      <button
        type="button"
        data-testid="disconnect-opener"
        onClick={() => setShow(true)}
      >
        Disconnect
      </button>
      <DisconnectWarning
        show={show}
        message="Test warning message"
        onCancel={() => setShow(false)}
        onConfirm={() => setShow(false)}
        isLoading={false}
      />
    </TooltipProvider>
  );
}

describe("DisconnectWarning", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe("Rendering", () => {
    it("should render the warning message when show is true", () => {
      renderWarning();

      expect(screen.getByText("Warning")).toBeInTheDocument();
      expect(screen.getByText("Test warning message")).toBeInTheDocument();
    });

    it("should render Cancel and Confirm buttons", () => {
      renderWarning();

      expect(
        screen.getByRole("button", { name: /cancel/i }),
      ).toBeInTheDocument();
      expect(
        screen.getByRole("button", { name: /confirm/i }),
      ).toBeInTheDocument();
    });

    it("should render the warning icon", () => {
      renderWarning();

      expect(screen.getByTestId("icon-Circle")).toBeInTheDocument();
    });

    it("should not render dialog content when show is false", () => {
      renderWarning({ show: false });

      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });

    it("should apply custom className when provided", () => {
      renderWarning({ className: "custom-class" });

      expect(screen.getByRole("dialog")).toHaveClass("custom-class");
    });
  });

  describe("Accessibility", () => {
    it("should expose dialog role with accessible name", () => {
      renderWarning();

      expect(
        screen.getByRole("dialog", { name: /warning/i }),
      ).toBeInTheDocument();
    });

    it("should move focus into the dialog on open", async () => {
      renderWarning();

      const dialog = screen.getByRole("dialog");
      await waitFor(() => {
        expect(dialog.contains(document.activeElement)).toBe(true);
      });
    });

    it("should call onCancel when Escape is pressed", async () => {
      const onCancel = jest.fn();
      const user = userEvent.setup();

      renderWarning({ onCancel });

      await user.keyboard("{Escape}");

      expect(onCancel).toHaveBeenCalled();
    });

    it("should keep Tab focus within dialog controls", async () => {
      const user = userEvent.setup();

      renderWarning();

      const cancelButton = screen.getByRole("button", { name: /cancel/i });
      const confirmButton = screen.getByRole("button", { name: /confirm/i });

      await waitFor(() => {
        expect(cancelButton).toHaveFocus();
      });

      await user.tab();
      expect(confirmButton).toHaveFocus();

      await user.tab();
      expect(cancelButton).toHaveFocus();

      await user.tab({ shift: true });
      expect(confirmButton).toHaveFocus();
    });

    it("should restore focus to the opener when Cancel is clicked", async () => {
      const user = userEvent.setup();
      render(<DisconnectWarningHarness />);

      const opener = screen.getByTestId("disconnect-opener");
      await user.click(opener);

      await waitFor(() => {
        expect(screen.getByRole("dialog")).toBeInTheDocument();
      });
      await waitFor(() => {
        expect(screen.getByTestId("disconnect-warning-cancel")).toHaveFocus();
      });

      await user.click(screen.getByTestId("disconnect-warning-cancel"));

      await waitFor(() => {
        expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
      });
      expect(opener).toHaveFocus();
    });

    it("should restore focus to the opener when Escape is pressed", async () => {
      const user = userEvent.setup();
      render(<DisconnectWarningHarness />);

      const opener = screen.getByTestId("disconnect-opener");
      await user.click(opener);

      await waitFor(() => {
        expect(screen.getByRole("dialog")).toBeInTheDocument();
      });

      await user.keyboard("{Escape}");

      await waitFor(() => {
        expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
      });
      expect(opener).toHaveFocus();
    });
  });

  describe("Button Interactions", () => {
    it("should call onCancel when Cancel button is clicked", async () => {
      const onCancel = jest.fn();
      const user = userEvent.setup();

      renderWarning({ onCancel });

      const cancelButton = screen.getByRole("button", { name: /cancel/i });
      await user.click(cancelButton);

      expect(onCancel).toHaveBeenCalledTimes(1);
    });

    it("should call onConfirm when Confirm button is clicked", async () => {
      const onConfirm = jest.fn();
      const user = userEvent.setup();

      renderWarning({ onConfirm });

      const confirmButton = screen.getByRole("button", { name: /confirm/i });
      await user.click(confirmButton);

      expect(onConfirm).toHaveBeenCalledTimes(1);
    });
  });

  describe("Loading State", () => {
    it("should show loading state on Confirm button when isLoading is true", () => {
      renderWarning({ isLoading: true });

      const confirmButton = screen.getByRole("button", { name: /confirm/i });
      expect(confirmButton).toBeInTheDocument();
    });

    it("should not show loading state when isLoading is false", () => {
      renderWarning({ isLoading: false });

      const confirmButton = screen.getByRole("button", { name: /confirm/i });
      expect(confirmButton).toBeInTheDocument();
    });
  });

  describe("Different Messages", () => {
    it("should display provider-specific disconnect message", () => {
      const message =
        "Disconnecting an API key will disable all of the provider's models being used in a flow.";
      renderWarning({ message });

      expect(screen.getByText(message)).toBeInTheDocument();
    });

    it("should display provider-specific deactivate message", () => {
      const message =
        "Deactivating Ollama will disable all of the provider's models being used in a flow.";
      renderWarning({ message });

      expect(screen.getByText(message)).toBeInTheDocument();
    });
  });
});

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { TooltipProvider } from "@/components/ui/tooltip";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "../dialog";

// Mock genericIconComponent (already globally mocked, but be explicit)
jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: () => null,
}));

const renderWithProviders = (ui: React.ReactElement) => {
  return render(<TooltipProvider>{ui}</TooltipProvider>);
};

describe("DialogContent", () => {
  it("should_not_auto_focus_close_button_when_dialog_opens", () => {
    // Arrange — open dialog with default behavior (no custom onOpenAutoFocus)
    renderWithProviders(
      <Dialog open>
        <DialogContent>
          <DialogTitle>Test Dialog</DialogTitle>
          <DialogDescription>Test description</DialogDescription>
          <p>Content</p>
        </DialogContent>
      </Dialog>,
    );

    // Act — dialog is already open, focus should have been handled

    // Assert — close button must NOT have focus
    const closeButton = screen.getByRole("button", { name: /close/i });
    expect(closeButton).not.toHaveFocus();

    // Assert — "Close" tooltip must NOT be visible on open
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
  });

  it("should_call_custom_onOpenAutoFocus_when_provided", () => {
    // Arrange — provide a custom onOpenAutoFocus handler
    const customHandler = jest.fn((e: Event) => {
      e.preventDefault();
    });

    renderWithProviders(
      <Dialog open>
        <DialogContent onOpenAutoFocus={customHandler}>
          <DialogTitle>Test Dialog</DialogTitle>
          <DialogDescription>Test description</DialogDescription>
          <p>Content</p>
        </DialogContent>
      </Dialog>,
    );

    // Assert — custom handler was called
    expect(customHandler).toHaveBeenCalledTimes(1);
  });

  it("should_hide_close_button_when_requested", () => {
    renderWithProviders(
      <Dialog open>
        <DialogContent hideCloseButton>
          <DialogTitle>Test Dialog</DialogTitle>
          <DialogDescription>Test description</DialogDescription>
          <p>Content</p>
        </DialogContent>
      </Dialog>,
    );

    expect(
      screen.queryByRole("button", { name: /close/i }),
    ).not.toBeInTheDocument();
  });

  it("should_detect_dialog_title_and_description_inside_dialog_header", () => {
    renderWithProviders(
      <Dialog open>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Nested title</DialogTitle>
            <DialogDescription>Nested description</DialogDescription>
          </DialogHeader>
        </DialogContent>
      </Dialog>,
    );

    const dialog = screen.getByRole("dialog", { name: "Nested title" });
    expect(dialog).toBeInTheDocument();
    expect(dialog).toHaveAccessibleDescription("Nested description");
    expect(screen.queryByText("Dialog")).not.toBeInTheDocument();
    expect(document.querySelectorAll("p")).toHaveLength(1);
  });

  it("should_stop_scanning_for_dialog_title_after_safe_depth", () => {
    renderWithProviders(
      <Dialog open>
        <DialogContent>
          <div>
            <div>
              <div>
                <div>
                  <div>
                    <div>
                      <DialogTitle>Too deep</DialogTitle>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
          <DialogDescription>Test description</DialogDescription>
        </DialogContent>
      </Dialog>,
    );

    expect(screen.getByText("Dialog")).toBeInTheDocument();
  });

  it("should_restore_focus_to_opener_on_escape_without_dialog_trigger", async () => {
    const user = userEvent.setup();

    function Harness() {
      const [open, setOpen] = useState(false);
      return (
        <TooltipProvider>
          <button
            type="button"
            data-testid="dialog-opener"
            onClick={() => setOpen(true)}
          >
            Open
          </button>
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogContent hideCloseButton>
              <DialogTitle>Controlled dialog</DialogTitle>
              <DialogDescription>Focus restore check</DialogDescription>
              <button type="button">Inside</button>
            </DialogContent>
          </Dialog>
        </TooltipProvider>
      );
    }

    render(<Harness />);
    const opener = screen.getByTestId("dialog-opener");

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

  it("should_restore_focus_to_dialog_trigger_on_escape", async () => {
    const user = userEvent.setup();

    renderWithProviders(
      <Dialog>
        <DialogTrigger asChild>
          <button type="button">Open dialog</button>
        </DialogTrigger>
        <DialogContent hideCloseButton>
          <DialogTitle>Triggered dialog</DialogTitle>
          <DialogDescription>Focus restore check</DialogDescription>
          <button type="button">Inside</button>
        </DialogContent>
      </Dialog>,
    );

    const trigger = screen.getByRole("button", { name: "Open dialog" });
    await user.click(trigger);
    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeInTheDocument();
    });

    await user.keyboard("{Escape}");
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });

    expect(trigger).toHaveFocus();
  });

  it("should_respect_custom_onCloseAutoFocus_preventDefault", async () => {
    const user = userEvent.setup();
    const customClose = jest.fn((e: Event) => {
      e.preventDefault();
    });

    function Harness() {
      const [open, setOpen] = useState(false);
      return (
        <TooltipProvider>
          <button
            type="button"
            data-testid="dialog-opener"
            onClick={() => setOpen(true)}
          >
            Open
          </button>
          <button type="button" data-testid="other-target">
            Other
          </button>
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogContent hideCloseButton onCloseAutoFocus={customClose}>
              <DialogTitle>Custom close focus</DialogTitle>
              <DialogDescription>Focus restore check</DialogDescription>
              <button type="button">Inside</button>
            </DialogContent>
          </Dialog>
        </TooltipProvider>
      );
    }

    render(<Harness />);
    const opener = screen.getByTestId("dialog-opener");

    await user.click(opener);
    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeInTheDocument();
    });

    await user.keyboard("{Escape}");
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });

    expect(customClose).toHaveBeenCalled();
    // Custom handler prevented default restore — opener should not be forced.
    expect(opener).not.toHaveFocus();
  });
});

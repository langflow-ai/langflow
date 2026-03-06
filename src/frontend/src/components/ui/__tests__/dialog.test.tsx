import { render, screen } from "@testing-library/react";
import { TooltipProvider } from "@/components/ui/tooltip";
import {
  Dialog,
  DialogContent,
  DialogTitle,
  DialogDescription,
} from "../dialog";

// Mock genericIconComponent (already globally mocked, but be explicit)
jest.mock("@/components/common/genericIconComponent", () => ({
  __esModule: true,
  default: () => null,
}));

import type { ReactElement } from "react";
import { render, screen } from "@testing-library/react";
import { TooltipProvider } from "@/components/ui/tooltip";

const renderWithProviders = (ui: ReactElement) => {
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
});

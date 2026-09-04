import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { TooltipProvider } from "@/components/ui/tooltip";
import { axe } from "@/utils/a11y-test";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "../dialog";

const renderOpenDialog = () =>
  render(
    <TooltipProvider>
      <Dialog open>
        <DialogContent>
          <DialogTitle>Delete flow</DialogTitle>
          <DialogDescription>This action cannot be undone.</DialogDescription>
          <button type="button">Confirm</button>
        </DialogContent>
      </Dialog>
    </TooltipProvider>,
  );

describe("Dialog accessibility", () => {
  it("should_have_no_axe_violations_when_open", async () => {
    renderOpenDialog();

    // Radix portals dialog content to document.body, outside the
    // render container.
    expect(await axe(document.body)).toHaveNoViolations();
  });

  it("should_expose_dialog_role_with_accessible_name", () => {
    renderOpenDialog();

    expect(
      screen.getByRole("dialog", { name: "Delete flow" }),
    ).toBeInTheDocument();
  });

  it("should_move_focus_inside_dialog_on_open", () => {
    renderOpenDialog();

    const dialog = screen.getByRole("dialog");
    expect(dialog.contains(document.activeElement)).toBe(true);
  });

  it("should_restore_focus_to_opener_on_cancel_and_escape", async () => {
    const user = userEvent.setup();

    function Harness() {
      const [open, setOpen] = useState(false);
      return (
        <TooltipProvider>
          <button
            type="button"
            data-testid="a11y-dialog-opener"
            onClick={() => setOpen(true)}
          >
            Open dialog
          </button>
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogContent hideCloseButton>
              <DialogTitle>Confirm disconnect</DialogTitle>
              <DialogDescription>
                This will disable provider models in flows.
              </DialogDescription>
              <button type="button" onClick={() => setOpen(false)}>
                Cancel
              </button>
            </DialogContent>
          </Dialog>
        </TooltipProvider>
      );
    }

    render(<Harness />);
    const opener = screen.getByTestId("a11y-dialog-opener");

    await user.click(opener);
    await waitFor(() => {
      expect(
        screen.getByRole("dialog", { name: "Confirm disconnect" }),
      ).toBeInTheDocument();
    });
    expect(screen.getByRole("dialog").contains(document.activeElement)).toBe(
      true,
    );

    await user.click(screen.getByRole("button", { name: "Cancel" }));
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
    expect(opener).toHaveFocus();

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

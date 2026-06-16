import { render, screen } from "@testing-library/react";
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

  // Known gap (a11y-action-plan 0.4): DialogContent calls preventDefault on
  // onOpenAutoFocus when no custom handler is provided, so focus stays on
  // <body> instead of moving into the dialog.
  it("should_move_focus_inside_dialog_on_open", () => {
    renderOpenDialog();

    const dialog = screen.getByRole("dialog");
    expect(dialog.contains(document.activeElement)).toBe(true);
  });
});
